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

# 1. ページ基本設定（スマホで見やすく）
st.set_page_config(page_title="コミュ・ジム Pro", layout="centered")

# --- スマホ最適化CSS ---
st.markdown("""
    <style>
    .block-container { padding: 1rem 0.5rem; }
    div.stButton > button { 
        width: 100%; height: 3.5rem; border-radius: 15px; 
        font-size: 1.1rem; font-weight: bold; 
    }
    input { font-size: 16px !important; }
    [data-baseweb="tab"] { font-size: 1rem; padding: 10px; }
    </style>
""", unsafe_allow_html=True)

# 2. データベース準備
DB_FILE = "comm_gym_v4.db"
def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("CREATE TABLE IF NOT EXISTS history (date TEXT, mission TEXT, score INTEGER)")
    conn.commit()
    conn.close()

def save_result(mission, score):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("INSERT INTO history VALUES (?, ?, ?)", (datetime.now().strftime("%Y-%m-%d %H:%M"), mission, score))
    conn.commit()
    conn.close()

def get_history():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM history", conn)
    conn.close()
    return df

init_db()

# 3. サイドバー設定
st.sidebar.title("🏋️ 設定")

# APIキーの取得（Secretsから）
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = ""
    st.sidebar.error("APIキーをSecretsに設定してください")

# モード・ミッション・キャラ選択
mode = st.sidebar.radio("モード選択", ["ビジネス・仕事", "プライベート・恋愛"])

if mode == "ビジネス・仕事":
    mission_list = ["雑談", "要点伝達", "スマートな断り方", "クレーム対応"]
    char_defs = {
        "優しい先輩 (初級)": {"name": "佐藤さん", "trait": "穏やかで褒め上手", "diff": "初級"},
        "論理的な上司 (中級)": {"name": "田中部長", "trait": "冷静で結論を求める", "diff": "中級"},
        "気難しい顧客 (上級)": {"name": "鬼瓦社長", "trait": "威圧的で表情に厳しい", "diff": "上級"}
    }
else:
    mission_list = ["初デートに誘う", "相手を褒める", "告白する", "仲直り"]
    char_defs = {
        "気になる後輩 (初級)": {"name": "結衣", "trait": "明るく社交的", "diff": "初級"},
        "クールな憧れの人 (中級)": {"name": "麗奈", "trait": "高嶺の花で自信を求める", "diff": "中級"},
        "倦怠期のパートナー (上級)": {"name": "悟", "trait": "本心を求める厳しい態度", "diff": "上級"}
    }

mission = st.sidebar.selectbox("🎯 ミッション", mission_list)
char_choice = st.sidebar.selectbox("👤 相手", list(char_defs.keys()))
selected_char = char_defs[char_choice]

# 4. メインUI
tab_train, tab_report = st.tabs(["🔥 トレーニング", "📈 レポート"])

with tab_train:
    col_vis, col_chat = st.columns([1, 1], gap="small")

    with col_vis:
        st.subheader("🖼️ 見た目")
        img_cam = st.camera_input("タップで撮影")
        final_img = Image.open(img_cam) if img_cam else None
        
        st.write("🎙️ 声の大きさ")
        components.html("""
            <canvas id="m" width="300" height="20" style="width:100%; height:20px; background:#eee; border-radius:10px;"></canvas>
            <script>
                navigator.mediaDevices.getUserMedia({audio:true}).then(s=>{
                    const ac=new AudioContext(); const an=ac.createAnalyser();
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
        st.subheader("💬 チャット")
        
        # 音声入力ボタン（スマホ用）
        components.html("""
            <button onclick="startRec()" style="width:100%; height:50px; background:#FF4B4B; color:white; border:none; border-radius:10px; font-weight:bold;">🎙️ 声で入力（コピー）</button>
            <script>
            function startRec() {
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                const rec = new SpeechRecognition();
                rec.lang = 'ja-JP';
                rec.onresult = (e) => {
                    const text = e.results[0][0].transcript;
                    const el = document.createElement('textarea');
                    el.value = text; document.body.appendChild(el); el.select();
                    document.execCommand('copy'); document.body.removeChild(el);
                    alert("聞き取り完了！貼り付けて送信してください。");
                };
                rec.start();
            }
            </script>
        """, height=60)

        # メッセージ履歴の管理
        if "messages" not in st.session_state: st.session_state.messages = []
        if "advice" not in st.session_state: st.session_state.advice = "準備ができたら話しかけてね！"
        
        chat_box = st.container(height=350)
        with chat_box:
            for i, m in enumerate(st.session_state.messages):
                with st.chat_message(m["role"]):
                    st.write(m["content"])
                    # AIの最新発言に「声を聴く」ボタンを表示
                    if m["role"] == "assistant" and i == len(st.session_state.messages)-1:
                        if st.button("🔊 声を聴く"):
                            clean_text = m["content"].replace("\n", " ")
                            components.html(f"""<script>
                                var ut = new SpeechSynthesisUtterance("{clean_text}");
                                ut.lang = 'ja-JP'; window.speechSynthesis.speak(ut);
                            </script>""", height=0)

        prompt = st.chat_input("ここに貼り付けて送信", disabled=not api_key)

        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('models/gemini-2.5-flash')
                
                sys_msg = f"""
                あなたは『{selected_char['name']}』({selected_char['trait']})です。モード：{mode}。
                ミッション『{mission}』について対話し、最後に必ず '---DATA---' とJSONを続けてください。
                {{ "reply": "...", "emotion": "...", "cleared": bool, "score": int, "advice": "..." }}
                """
                
                content = [sys_msg]
                if final_img: content.append(final_img)
                content.append(prompt)

                with st.chat_message("assistant"):
                    placeholder = st.empty()
                    full_res = ""
                    for chunk in model.generate_content(content, stream=True):
                        full_res += chunk.text
                        display_text = full_res.split("---DATA---")[0]
                        placeholder.markdown(display_text + "▌")
                    placeholder.markdown(display_text)

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
                st.error("通信エラー")

        st.info(f"💡 AIアドバイス: {st.session_state.advice}")

with tab_report:
    st.header("📈 成長レポート")
    df = get_history()
    if not df.empty:
        st.plotly_chart(px.line(df, x='date', y='score', color='mission', markers=True))
        st.table(df.tail(5))
    else:
        st.write("まだ記録がありません。")
