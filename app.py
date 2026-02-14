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

# --- スマホ最適化CSSの注入 ---
st.markdown("""
    <style>
    /* 全体の余白を削ってフルスクリーンに近づける */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        padding-left: 0.5rem;
        padding-right: 0.5rem;
    }
    
    /* ボタンを指で押しやすく大きくする */
    div.stButton > button {
        width: 100%;
        height: 3.5rem;
        border-radius: 15px;
        font-size: 1.1rem;
        font-weight: bold;
    }
    
    /* チャット入力欄のフォントサイズ調整（ズーム防止） */
    input {
        font-size: 16px !important;
    }
    
    /* タブの文字を大きくする */
    .stTabs [data-baseweb="tab"] {
        font-size: 1.1rem;
    }
    </style>
""", unsafe_allow_html=True)

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
    # スマホでは縦に並び、PCでは横に並ぶ設定
    # gap="small" にして間隔を詰めます
    col_vis, col_chat = st.columns([1, 1.2], gap="small")

    with col_vis:
        st.subheader("🖼️ 見た目チェック")
        # カメラ入力を少し小さめに表示する工夫
        img_cam = st.camera_input("タップして撮影")
        
        # ファイルアップローダーは「参照」ボタンが小さいので、
        # スマホではカメラ入力をメインに使う想定で、アップローダーはexpanderに隠すのもアリ
        with st.expander("または画像をアップロード"):
            img_file = st.file_uploader("", type=['png', 'jpg', 'jpeg'])

        # 音量モニターも高さを抑える
        st.write("🎙️ 声の大きさ")
        components.html("""
            <canvas id="m" width="300" height="15" style="width:100%; height:15px; background:#eee; border-radius:10px;"></canvas>
            <script>
                navigator.mediaDevices.getUserMedia({audio:true}).then(s=>{
                    const ac=new AudioContext(); const an=ac.createAnalyser();
                    ac.createMediaStreamSource(s).connect(an); const d=new Uint8Array(an.frequencyBinCount);
                    const cv=document.getElementById('m'), cx=cv.getContext('2d');
                    function draw(){
                        an.getByteFrequencyData(d); let v=d.reduce((a,b)=>a+b)/d.length;
                        cx.clearRect(0,0,300,15); cx.fillStyle='#FF4B4B'; cx.fillRect(0,0,v*5,15);
                        requestAnimationFrame(draw);
                    }
                    draw();
                });
            </script>
        """, height=25)

    with col_chat:
        st.subheader("💬 チャット")

        # --- 1. 音声認識（STT）: allow属性を追加して権限を確保 ---
        st.write("🎙️ 音声入力")
        components.html("""
            <div style="padding: 5px;">
                <button id="stt_btn" onclick="startRecognition()" style="width:100%; height:60px; background:linear-gradient(135deg, #FF4B4B, #FF7676); color:white; border:none; border-radius:15px; font-size:18px; font-weight:bold; box-shadow: 0 4px 15px rgba(255,75,75,0.3); cursor:pointer;">
                    🎙️ タップして喋る
                </button>
            </div>
            <script>
            function startRecognition() {
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                if (!SpeechRecognition) {
                    alert("音声認識未対応のブラウザです。ChromeやSafariをお試しください。");
                    return;
                }
                const recognition = new SpeechRecognition();
                recognition.lang = 'ja-JP';
                recognition.onstart = () => {
                    document.getElementById('stt_btn').innerText = "👂 聞き取り中...";
                    document.getElementById('stt_btn').style.background = "#4CAF50";
                };
                recognition.onresult = (e) => {
                    const text = e.results[0][0].transcript;
                    // クリップボードにコピー
                    const el = document.createElement('textarea');
                    el.value = text; document.body.appendChild(el); el.select();
                    document.execCommand('copy'); document.body.removeChild(el);
                    alert("完了！入力欄を長押しして「ペースト」してください。");
                    document.getElementById('stt_btn').innerText = "🎙️ タップして喋る";
                    document.getElementById('stt_btn').style.background = "linear-gradient(135deg, #FF4B4B, #FF7676)";
                };
                recognition.onerror = (e) => {
                    alert("エラー: " + e.error + "\\nマイクの使用を許可してください。");
                    document.getElementById('stt_btn').innerText = "🎙️ 再試行";
                };
                recognition.start();
            }
            </script>
        """, height=100) # ここに allow="microphone" はStreamlit Cloud側で自動付与されますが、JS側でエラーハンドリングを強化

        # --- 2. 履歴表示 & 読み上げボタン ---
        chat_box = st.container(height=350)
        with chat_box:
            for i, m in enumerate(st.session_state.messages):
                with st.chat_message(m["role"]):
                    st.write(m["content"])
                    # AIの最新の返答にだけ「読み上げボタン」を表示（スマホ用）
                    if m["role"] == "assistant" and i == len(st.session_state.messages) - 1:
                        if st.button(f"🔊 声を聴く"):
                            speech_js = f"""
                                <script>
                                var msg = new SpeechSynthesisUtterance("{m['content'].replace('\\n', ' ')}");
                                msg.lang = 'ja-JP';
                                window.speechSynthesis.speak(msg);
                                </script>
                            """
                            components.html(speech_js, height=0)

        # --- 3. メッセージ入力 ---
        prompt = st.chat_input("ここに貼り付けて送信", disabled=not api_key)

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
                        var msg = new SpeechSynthesisUtterance("{display_text.replace('\\n', ' ')}");
                        msg.lang = 'ja-JP';
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
