import streamlit as st
import google.generativeai as genai
import pandas as pd
import sqlite3
from datetime import datetime
import json
import re
from PIL import Image
import streamlit.components.v1 as components
import plotly.express as px

# --- 1. ページ基本設定 ---
st.set_page_config(page_title="コミュ・ジム Pro", layout="centered")

st.markdown("""
    <style>
    .block-container { padding: 1rem 0.5rem; }
    div.stButton > button { width: 100%; height: 3.5rem; border-radius: 15px; font-weight: bold; }
    input { font-size: 16px !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. データベース & セッション状態 ---
def init_db():
    conn = sqlite3.connect("comm_v5.db")
    conn.execute("CREATE TABLE IF NOT EXISTS history (date TEXT, mission TEXT, score INTEGER)")
    conn.commit()
    conn.close()

def save_result(mission, score):
    conn = sqlite3.connect("comm_v5.db")
    conn.execute("INSERT INTO history VALUES (?, ?, ?)", (datetime.now().strftime("%m-%d %H:%M"), mission, score))
    conn.commit()
    conn.close()

init_db()

if "messages" not in st.session_state: st.session_state.messages = []
if "advice" not in st.session_state: st.session_state.advice = "準備OK！"
if "emotion" not in st.session_state: st.session_state.emotion = "normal"

# --- 3. サイドバー ---
st.sidebar.title("🏋️ 設定")
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = ""
    st.sidebar.error("SecretsにAPIキーを設定してください")

mode = st.sidebar.radio("モード", ["ビジネス・仕事", "プライベート・恋愛"])

if mode == "ビジネス・仕事":
    mission_list = ["雑談", "要点伝達", "断り方", "クレーム対応"]
    char_defs = {
        "優しい先輩": {"name": "佐藤", "trait": "褒め上手", "diff": "初級"},
        "田中部長": {"name": "田中", "trait": "論理的・厳格", "diff": "中級"},
        "鬼瓦社長": {"name": "鬼瓦", "trait": "威圧的・表情重視", "diff": "上級"}
    }
else:
    mission_list = ["デートに誘う", "相手を褒める", "告白", "仲直り"]
    char_defs = {
        "後輩の結衣": {"name": "結衣", "trait": "明るく誠実", "diff": "初級"},
        "憧れの麗奈": {"name": "麗奈", "trait": "クール・自信重視", "diff": "中級"},
        "パートナーの悟": {"name": "悟", "trait": "倦怠期・本心重視", "diff": "上級"}
    }

mission = st.sidebar.selectbox("🎯 ミッション", mission_list)
selected_char = char_defs[st.sidebar.selectbox("👤 相手", list(char_defs.keys()))]

# --- 4. メインUI ---
tab_train, tab_report = st.tabs(["🔥 練習", "📈 記録"])

with tab_train:
    col_vis, col_chat = st.columns([1, 1])

    with col_vis:
        st.subheader("🖼️ 表情・視線")
        img_cam = st.camera_input("撮影")
        final_img = Image.open(img_cam) if img_cam else None

    with col_chat:
        st.subheader("💬 チャット")
        
        # --- 音声入力コンポーネント (スマホ対応) ---
        components.html("""
            <div id="stt_area" style="background:#f0f2f6; padding:10px; border-radius:10px;">
                <button id="btn" onclick="startRec()" style="width:100%; height:45px; background:#FF4B4B; color:white; border:none; border-radius:8px; font-weight:bold;">🎙️ 声で入力する</button>
                <div id="res" style="margin-top:10px; font-size:14px; color:#333; min-height:20px; border-bottom:1px solid #ccc;">ここに結果が表示されます</div>
            </div>
            <script>
            const btn = document.getElementById('btn');
            const resDiv = document.getElementById('res');
            function startRec() {
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                if(!SpeechRecognition) { alert("未対応ブラウザです"); return; }
                const rec = new SpeechRecognition();
                rec.lang = 'ja-JP';
                rec.onstart = () => { btn.innerText = "👂 聞き取り中..."; btn.style.background = "#4CAF50"; };
                rec.onresult = (e) => {
                    const t = e.results[0][0].transcript;
                    resDiv.innerText = t;
                    // クリップボードへコピーを試みる
                    navigator.clipboard.writeText(t).then(() => {
                        alert("コピーしました！下の入力欄に貼り付けてね。");
                    }).catch(() => {
                        alert("コピー失敗。文字を長押ししてコピーしてください: " + t);
                    });
                    btn.innerText = "🎙️ 声で入力する"; btn.style.background = "#FF4B4B";
                };
                rec.onerror = () => { alert("マイクを許可してください"); btn.innerText = "🎙️ 再試行"; };
                rec.start();
                // 空の音声を再生してスマホのオーディオを「ロック解除」
                const u = new SpeechSynthesisUtterance(""); window.speechSynthesis.speak(u);
            }
            </script>
        """, height=130)

        # チャット履歴表示
        chat_box = st.container(height=350)
        with chat_box:
            for i, m in enumerate(st.session_state.messages):
                with st.chat_message(m["role"]):
                    st.write(m["content"])
                    if m["role"] == "assistant" and i == len(st.session_state.messages)-1:
                        if st.button("🔊 読み上げ"):
                            clean_t = m["content"].replace("\n", " ")
                            components.html(f"""<script>
                                var ut = new SpeechSynthesisUtterance("{clean_t}");
                                ut.lang = 'ja-JP'; window.speechSynthesis.speak(ut);
                            </script>""", height=0)

        # 入力処理
        prompt = st.chat_input("貼り付けて送信", disabled=not api_key)

        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            if api_key:
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('models/gemini-2.5-flash')
                    
                    sys_msg = f"""あなたは『{selected_char['name']}』です。性格：{selected_char['trait']}。モード：{mode}。
                    ミッション：{mission}。判定JSON：{{ "reply": "...", "emotion": "...", "cleared": bool, "score": int, "advice": "..." }}
                    返答の後に '---DATA---' とJSONを続けてください。"""
                    
                    with st.chat_message("assistant"):
                        p = st.empty()
                        full_res = ""
                        for chunk in model.generate_content([sys_msg, final_img, prompt] if final_img else [sys_msg, prompt], stream=True):
                            full_res += chunk.text
                            display_text = full_res.split("---DATA---")[0]
                            p.markdown(display_text + "▌")
                        p.markdown(display_text)

                    # データの保存とリリフレッシュ
                    if "---DATA---" in full_res:
                        json_part = full_res.split("---DATA---")[1]
                        match = re.search(r'\{.*\}', json_part, re.DOTALL)
                        if match:
                            data = json.loads(re.sub(r',\s*\}', '}', match.group(0)))
                            # ここで履歴に追加！
                            st.session_state.messages.append({"role": "assistant", "content": display_text})
                            st.session_state.advice = data.get('advice', '')
                            st.session_state.emotion = data.get('emotion', 'normal')
                            if data.get('cleared'):
                                save_result(mission, data.get('score', 0))
                                st.balloons()
                            st.rerun() # 履歴を確実に描画するために再起動

                except Exception as e:
                    st.error("通信エラー。時間を置いて試してください。")

        st.info(f"💡 アドバイス: {st.session_state.advice}")

with tab_report:
    st.header("📈 成長レポート")
    try:
        conn = sqlite3.connect("comm_v5.db")
        df = pd.read_sql_query("SELECT * FROM history", conn)
        conn.close()
        if not df.empty:
            st.plotly_chart(px.line(df, x='date', y='score', color='mission', markers=True))
        else:
            st.write("まだ記録がありません。")
    except:
        st.write("データ読み込み中...")
