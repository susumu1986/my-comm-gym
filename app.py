import streamlit as st
import google.generativeai as genai
import json
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime
import streamlit.components.v1 as components
from PIL import Image

# --- データベースの初期化 ---
def init_db():
    conn = sqlite3.connect('comm_gym_v3.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, mission TEXT, date TEXT, score INTEGER)''')
    conn.commit()
    conn.close()

def save_result(mission, score):
    conn = sqlite3.connect('comm_gym_v3.db')
    c = conn.cursor()
    c.execute("INSERT INTO history (mission, date, score) VALUES (?, ?, ?)", 
              (mission, datetime.now().strftime("%Y-%m-%d"), score))
    conn.commit()
    conn.close()

init_db()

# --- 画面設定 ---
st.set_page_config(page_title="コミュ・ジム Pro", page_icon="🎭", layout="wide")

def set_theme(emotion):
    colors = {"happy": "#E8F5E9", "angry": "#FFEBEE", "sad": "#E3F2FD", "normal": "#F0F2F6"}
    bg = colors.get(emotion, "#F0F2F6")
    st.markdown(f"<style>.stApp {{ background-color: {bg}; transition: 0.8s; }}</style>", unsafe_allow_html=True)

# --- サイドバー設定 ---
with st.sidebar:
    st.title("🏆 あなたのランク")
    conn = sqlite3.connect('comm_gym_v3.db')
    df_h = pd.read_sql_query("SELECT * FROM history", conn)
    conn.close()
    
    level = (len(df_h) // 3) + 1
    st.metric("現在のレベル", f"Lv.{level}")
    st.progress(min((len(df_h) % 3) / 3, 1.0), text="次のレベルまで")
    
    st.divider()
    api_key = st.secrets["GEMINI_API_KEY"]

# --- サイドバー：モード選択 ---
mode = st.sidebar.radio("🏋️ トレーニングモード", ["ビジネス・仕事", "プライベート・恋愛"])

if mode == "ビジネス・仕事":
    mission_list = ["雑談（アイスブレイク）", "要点伝達（PREP法）", "スマートな断り方", "クレーム対応"]
    char_defs = {
        "優しい先輩 (初級)": {"name": "佐藤さん", "trait": "穏やかで褒め上手。新人を温かく見守っている", "diff": "初級"},
        "論理的な上司 (中級)": {"name": "田中部長", "trait": "冷静沈着。結論から言わないと『で、何が言いたいの？』と聞く", "diff": "中級"},
        "気難しい顧客 (上級)": {"name": "鬼瓦社長", "trait": "威圧的。表情や態度が少しでも不遜だと怒り出す", "diff": "上級"}
    }
else:
    # 恋愛・プライベートモード
    mission_list = ["初デートに誘う", "相手を褒めちぎる", "告白する", "喧嘩のあとの仲直り"]
    char_defs = {
        "気になる後輩 (初級)": {"name": "結衣", "trait": "明るく社交的。でも、誠実な言葉じゃないと心に響かない", "diff": "初級"},
        "クールな憧れの人 (中級)": {"name": "麗奈", "trait": "高嶺の花。自信なさげな態度はマイナス。余裕を見せる必要がある", "diff": "中級"},
        "倦怠期のパートナー (上級)": {"name": "悟", "trait": "最近会話が減っている。ありきたりな言葉は通用しない。本心を求めている", "diff": "上級"}
    }

mission = st.sidebar.selectbox("🎯 ミッション", mission_list)
char_choice = st.sidebar.selectbox("👤 対戦相手", list(char_defs.keys()))
selected_char = char_defs[char_choice]

# --- タブ構造 ---
tab1, tab2 = st.tabs(["🔥 トレーニング", "📊 成長レポート"])


with tab1:
    col_vis, col_chat = st.columns([1, 1.2])

    with col_vis:
        st.subheader("🖼️ 非言語チェック (55%)")
        
        # --- 画像入力の2つの方法 ---
        img_cam = st.camera_input("1. 今すぐカメラで撮影")
        img_file = st.file_uploader("2. または画像をアップロード", type=['png', 'jpg', 'jpeg'])
        
        # 最終的にAIに送る画像を選択（カメラ優先）
        final_img = None
        if img_cam:
            final_img = Image.open(img_cam)
            st.success("カメラ画像を使用します")
        elif img_file:
            final_img = Image.open(img_file)
            st.success("アップロード画像を使用します")

        st.divider()
        st.write("🎙️ 聴覚情報モニター (38%)")
        # 前回のJavaScript音量モニター
        components.html("""
            <canvas id="m" width="300" height="20" style="width:100%; height:20px; background:#eee;"></canvas>
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
        """, height=50)

    with col_chat:
        st.subheader("💬 対話 & 評価 (7%)")
        
        # --- 音声認識（Speech to Text）ボタン ---
        components.html("""
            <script>
            function startRecognition() {
                const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
                recognition.lang = 'ja-JP';
                recognition.onresult = (e) => {
                    const text = e.results[0][0].transcript;
                    window.parent.postMessage({type: 'streamlit:set_component_value', value: text}, '*');
                };
                recognition.start();
            }
            </script>
            <button onclick="startRecognition()" style="width:100%; padding:10px; background:#FF4B4B; color:white; border:none; border-radius:5px; cursor:pointer;">🎙️ 声で入力する（クリックして喋る）</button>
        """, height=60)

        if "messages" not in st.session_state: st.session_state.messages = []
        if "emotion" not in st.session_state: st.session_state.emotion = "normal"
        if "advice" not in st.session_state: st.session_state.advice = "準備ができたら入力してください。"
        
        set_theme(st.session_state.emotion)

	# 入力欄のガード
        chat_box = st.container(height=350)
        with chat_box:
            for m in st.session_state.messages:
                st.chat_message(m["role"]).write(m["content"])

        # チャット入力欄
        prompt = st.chat_input("メッセージを入力...", disabled=not api_key)

        if prompt:
            # 1. ユーザーのメッセージを履歴に追加
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            if api_key:
                try:
                    # AIの設定
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('models/gemini-2.5-flash')
                    
                    # 2. AIへの指示（Line 162付近の修正）
                    sys_msg = f"""
                    あなたは『{selected_char['name']}』という人物です。性格は『{selected_char['trait']}』です。
                    現在のモード：{mode}
                    現在のミッション：{mission}

                    【判定ルール】
                    - 相手の言葉だけでなく、画像がある場合は表情や清潔感も厳しく判定してください。
                    - まずユーザーへの返答を話し、その後に必ず '---DATA---' という区切り線を入れ、
                    - 最後に判定結果を以下のJSON形式のみで出力してください。
                    {{ "reply": "...", "emotion": "happy/angry/normal", "cleared": bool, "score": int, "advice": "..." }}
                    """
                    
                    content = [sys_msg]
                    if final_img:
                        content.append(final_img)
                    content.append(prompt)

                    # 3. ストリーミング表示
                    with st.chat_message("assistant"):
                        placeholder = st.empty()
                        full_response = ""
                        responses = model.generate_content(content, stream=True)
                        
                        for chunk in responses:
                            full_response += chunk.text
                            display_text = full_response.split("---DATA---")[0]
                            placeholder.markdown(display_text + "▌")
                        placeholder.markdown(display_text)

                    # 4. データ解析と音声読み上げ
                    if "---DATA---" in full_response:
                        json_part = full_response.split("---DATA---")[1]
                        import re
                        json_match = re.search(r'\{.*\}', json_part, re.DOTALL)
                        
                        if json_match:
                            json_str = re.sub(r',\s*\}', '}', json_match.group(0))
                            data = json.loads(json_str)
                            
                            # 音声読み上げの発動
                            speech_text = display_text.replace('\n', ' ')
                            components.html(f"""
                                <script>
                                var msg = new SpeechSynthesisUtterance("{speech_text}");
                                msg.lang = 'ja-JP';
                                msg.rate = 1.0;
                                window.speechSynthesis.speak(msg);
                                </script>
                            """, height=0)

                            # 判定データの反映
                            st.session_state.emotion = data.get('emotion', 'normal')
                            st.session_state.advice = data.get('advice', '')
                            st.session_state.messages.append({"role": "assistant", "content": display_text})
                            
                            if data.get('cleared'):
                                save_result(mission, data.get('score', 0))
                                st.balloons()
                            
                            st.rerun()

                except Exception as e:
                    # これが「expected 'except'」エラーを防ぐためのブロックです
                    st.error(f"AIとの通信中にエラーが発生しました。")
                    with st.expander("デバッグ情報"):
                        st.write(e)
            else:
                st.warning("APIキーを入力してください。")
                
        st.info(f"💡 AIアドバイス: {st.session_state.advice}")
with tab2:
    st.header("📈 成長レポート")
    df = pd.read_sql_query("SELECT * FROM history", sqlite3.connect('comm_gym_v3.db'))
    if not df.empty: st.plotly_chart(px.line(df, x='date', y='score', color='mission', markers=True), use_container_width=True)

    else: st.write("履歴がありません。")
