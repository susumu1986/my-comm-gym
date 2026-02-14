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

# スマホ向けカスタムCSS
st.markdown("""
    <style>
    .block-container { padding: 1rem 0.5rem; }
    div.stButton > button { width: 100%; height: 3.5rem; border-radius: 15px; font-weight: bold; }
    input { font-size: 16px !important; }
    .stTabs [data-baseweb="tab"] { font-size: 1rem; }
    </style>
""", unsafe_allow_html=True)

# --- 2. データベース設定 ---
DB_NAME = "comm_gym_v6.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("CREATE TABLE IF NOT EXISTS history (date TEXT, mission TEXT, score INTEGER)")
    conn.commit()
    conn.close()

def save_result(mission, score):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO history VALUES (?, ?, ?)", 
                 (datetime.now().strftime("%m-%d %H:%M"), mission, score))
    conn.commit()
    conn.close()

init_db()

# --- 3. サイドバー設定 ---
st.sidebar.title("🏋️ 設定")

# APIキーをSecretsから取得
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = ""
    st.sidebar.error("Streamlit CloudのSecretsに 'GEMINI_API_KEY' を設定してください")

mode = st.sidebar.radio("モード選択", ["ビジネス・仕事", "プライベート・恋愛"])

if mode == "ビジネス・仕事":
    mission_list = ["雑談", "要点伝達", "スマートな断り方", "クレーム対応"]
    char_defs = {
        "優しい先輩 (初級)": {"name": "佐藤さん", "trait": "穏やかで褒め上手", "diff": "初級"},
        "田中部長 (中級)": {"name": "田中", "trait": "冷静沈着で結論重視", "diff": "中級"},
        "鬼瓦社長 (上級)": {"name": "鬼瓦", "trait": "威圧的で表情に厳しい", "diff": "上級"}
    }
else:
    mission_list = ["初デートに誘う", "相手を褒める", "告白する", "喧嘩の仲直り"]
    char_defs = {
        "気になる後輩 (初級)": {"name": "結衣", "trait": "明るく誠実な反応", "diff": "初級"},
        "憧れの人 (中級)": {"name": "麗奈", "trait": "クールで自信を求める", "diff": "中級"},
        "パートナー (上級)": {"name": "悟", "trait": "最近冷たい。本心を求めている", "diff": "上級"}
    }

mission = st.sidebar.selectbox("🎯 ミッション", mission_list)
selected_char = char_defs[st.sidebar.selectbox("👤 相手", list(char_defs.keys()))]

# --- 4. メインUI ---
tab_train, tab_report = st.tabs(["🔥 練習", "📈 記録"])

with tab_train:
    col_vis, col_chat = st.columns([1, 1], gap="small")

    with col_vis:
        st.subheader("🖼️ 見た目チェック")
        img_cam = st.camera_input("撮影して診断")
        final_img = Image.open(img_cam) if img_cam else None
        
        st.write("🎙️ 声の大きさ")
        components.html("""
            <canvas id="m" width="300" height="20" style="width:100%; height:20px; background:#eee; border-radius:10px;"></canvas>
            <script>
                navigator.mediaDevices.getUserMedia({audio:true}).then(s=>{
                    const ac=new (window.AudioContext || window.webkitAudioContext)(); 
                    const an=ac.createAnalyser();
                    ac.createMediaStreamSource(s).connect(an); const d=new Uint8Array(an.frequencyBinCount);
                    const cv=document.getElementById('m'), cx=cv.getContext('2d');
                    function draw(){
                        an.getByteFrequencyData(d); let v=d.reduce((a,b)=>a+b)/d.length;
                        cx.clearRect(0,0,300,20); cx.fillStyle='#FF4B4B'; cx.fillRect(0,0,v*5,20);
                        requestAnimationFrame(draw);
                    }
                    draw();
                });
            </script>
        """, height=30)

    with col_chat:
        st.subheader("💬 対話")
        
        # 音声入力（スマホ対応・コピー機能付）
        components.html("""
            <div style="background:#f0f2f6; padding:10px; border-radius:15px; text-align:center;">
                <button id="stt_btn" onclick="startRec()" style="width:100%; height:50px; background:linear-gradient(135deg, #FF4B4B, #FF7676); color:white; border:none; border-radius:10px; font-weight:bold; cursor:pointer;">🎙️ 声で入力（タップ）</button>
                <div id="stt_res" style="margin-top:8px; font-size:13px; color:#555; font-style:italic;">ここに結果が表示されます</div>
            </div>
            <script>
            function startRec() {
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                if(!SpeechRecognition) { alert("未対応ブラウザです"); return; }
                const rec = new SpeechRecognition();
                rec.lang = 'ja-JP';
                rec.onstart = () => { document.getElementById('stt_btn').innerText = "👂 聞き取り中..."; };
                rec.onresult = (e) => {
                    const t = e.results[0][0].transcript;
                    document.getElementById('stt_res').innerText = t;
                    navigator.clipboard.writeText(t).then(() => { alert("コピー成功！入力欄に貼り付けてね。"); })
                    .catch(() => { alert("コピー失敗。文字を長押ししてね: " + t); });
                    document.getElementById('stt_btn').innerText = "🎙️ 声で入力（タップ）";
                };
                rec.onerror = () => { alert("マイクを許可してください"); };
                rec.start();
                // スマホの音声再生制限を解除するためのダミー
                const u = new SpeechSynthesisUtterance(""); window.speechSynthesis.speak(u);
            }
            </script>
        """, height=120)

        # チャット履歴 & スマホ用読み上げボタン
        if "messages" not in st.session_state: st.session_state.messages = []
        if "advice" not in st.session_state: st.session_state.advice = "準備ができたら送信！"
        
        chat_box = st.container(height=400)
        with chat_box:
            for i, m in enumerate(st.session_state.messages):
                with st.chat_message(m["role"]):
                    st.write(m["content"])
                    if m["role"] == "assistant":
                        # JSボタンによる音声再生（スマホ対応）
                        clean_text = m["content"].replace('"', '\\"').replace('\n', ' ')
                        components.html(f"""
                            <button onclick="window.speechSynthesis.cancel(); 
                                             const u = new SpeechSynthesisUtterance('{clean_text}'); 
                                             u.lang='ja-JP'; u.rate=1.1; 
                                             window.speechSynthesis.speak(u);" 
                                    style="background:#f0f2f6; border:1px solid #ccc; border-radius:15px; padding:5px 12px; cursor:pointer; font-size:13px;">
                                🔊 声を聴く
                            </button>
                        """, height=40)

        # メッセージ送信
        prompt = st.chat_input("貼り付けて送信", disabled=not api_key)

        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            if api_key:
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('models/gemini-2.5-flash')
                    
                    sys_msg = f"""
                    あなたは『{selected_char['name']}』({selected_char['trait']})です。
                    ミッション：{mission}
                    判定結果を最後に '---DATA---' とJSONで続けてください。
                    {{ "reply": "...", "emotion": "...", "cleared": bool, "score": int, "advice": "..." }}
                    """
                    
                    with st.chat_message("assistant"):
                        p_placeholder = st.empty()
                        full_res = ""
                        # ストリーミング実行
                        contents = [sys_msg]
                        if final_img: contents.append(final_img)
                        contents.append(prompt)
                        
                        res = model.generate_content(contents, stream=True)
                        for chunk in res:
                            full_res += chunk.text
                            display_text = full_res.split("---DATA---")[0]
                            p_placeholder.markdown(display_text + "▌")
                        p_placeholder.markdown(display_text)

                    # データ解析と保存
                    if "---DATA---" in full_res:
                        json_part = full_res.split("---DATA---")[1]
                        match = re.search(r'\{.*\}', json_part, re.DOTALL)
                        if match:
                            data = json.loads(re.sub(r',\s*\}', '}', match.group(0)))
                            st.session_state.messages.append({"role": "assistant", "content": display_text})
                            st.session_state.advice = data.get('advice', '')
                            if data.get('cleared'):
                                save_result(mission, data.get('score', 0))
                                st.balloons()
                            st.rerun()

                except Exception as e:
                    st.error(f"エラーが発生しました。")

        st.info(f"💡 AIコーチの助言: {st.session_state.advice}")

# --- 5. レポートUI ---
with tab_report:
    st.header("📈 成長レポート")
    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query("SELECT * FROM history", conn)
        conn.close()
        if not df.empty:
            st.plotly_chart(px.line(df, x='date', y='score', color='mission', markers=True))
            st.write("### 過去の練習記録")
            st.dataframe(df.sort_values(by='date', ascending=False), hide_index=True)
        else:
            st.info("練習をクリアするとここに記録が表示されます！")
    except:
        st.write("データ読み込み中...")
