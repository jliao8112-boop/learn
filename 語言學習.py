import streamlit as st
import pandas as pd

# --- 頁面設定 ---
st.set_page_config(page_title="AI 科學單字記憶教練", layout="centered")

# --- CSS 樣式 (保留原網頁視覺感，解決擠壓問題) ---
st.markdown("""
<style>
    .word-title { font-size: clamp(2rem, 8vw, 4rem); font-weight: bold; color: #1e293b; text-align: center; margin-bottom: 10px; }
    .zh-trans { font-size: 1.5rem; font-weight: bold; color: #10b981; margin-bottom: 5px; }
    .pos { color: #3b82f6; font-style: italic; font-size: 0.9em; }
    .mnemonic-box { background: linear-gradient(135deg, #fffcf0, #fff7ed); border-left: 5px solid #fbc02d; padding: 15px; border-radius: 8px; margin: 15px 0; }
    .mnemonic-title { font-weight: bold; color: #ea580c; font-size: 1rem; margin-bottom: 5px; }
    .example-box { background: #f8fafc; padding: 15px; border-radius: 8px; border-left: 4px solid #cbd5e1; margin-top: 10px; }
    .example-en { font-style: italic; font-weight: bold; color: #1e293b; font-size: 1.1rem; }
    .example-zh { color: #475569; margin-top: 5px; }
</style>
""", unsafe_allow_html=True)

# --- 初始化 Session State ---
if 'deck' not in st.session_state:
    st.session_state.deck = []
if 'total_count' not in st.session_state:
    st.session_state.total_count = 0
if 'is_flipped' not in st.session_state:
    st.session_state.is_flipped = False
if 'stats' not in st.session_state:
    st.session_state.stats = {"again": 0, "hard": 0, "good": 0, "easy": 0}

# --- 功能函式 ---
def speak(text):
    """利用瀏覽器原生 TTS 發音"""
    if not text or text == "無": return
    js_code = f"""
        <script>
            window.speechSynthesis.cancel();
            var msg = new SpeechSynthesisUtterance("{text.replace('"', '')}");
            msg.lang = 'en-US';
            msg.rate = 0.7;
            window.speechSynthesis.speak(msg);
        </script>
    """
    st.components.v1.html(js_code, height=0)

def handle_srs(rating):
    if not st.session_state.deck: return
    card = st.session_state.deck.pop(0)
    st.session_state.stats[rating] += 1
    
    if rating == 'again':
        st.session_state.deck.insert(min(1, len(st.session_state.deck)), card)
    elif rating == 'hard':
        st.session_state.deck.insert(len(st.session_state.deck)//2, card)
    elif rating == 'good':
        st.session_state.deck.append(card)
    
    st.session_state.is_flipped = False
    st.rerun()

# --- 側邊欄：匯入邏輯 (關鍵修正區) ---
with st.sidebar:
    st.title("⚙️ 記憶教練設定")
    uploaded_file = st.file_uploader("請匯入單字 CSV", type="csv")
    
    if uploaded_file:
        if st.button("確認載入並重置進度", use_container_width=True):
            # 依據你的 HTML 邏輯定義 11 個欄位
            col_names = [
                'word', 'audio_url', 'image_url', 'pos', 'zh', 
                'forms', 'example_en', 'example_zh', 'phonics', 
                'fake_pron', 'mnemonic'
            ]
            try:
                # 讀取 CSV，自動跳過第一行標題並指定名稱，補齊空白值為空字串
                df = pd.read_csv(uploaded_file, names=col_names, skiprows=1, encoding='utf-8').fillna("")
                st.session_state.deck = df.to_dict('records')
                st.session_state.total_count = len(st.session_state.deck)
                st.session_state.stats = {"again": 0, "hard": 0, "good": 0, "easy": 0}
                st.session_state.is_flipped = False
                st.success(f"✅ 已載入 {st.session_state.total_count} 個單字")
            except Exception as e:
                st.error(f"讀取失敗，請檢查格式: {e}")

    st.divider()
    if st.session_state.total_count > 0:
        st.write(f"📊 剩餘進度: **{len(st.session_state.deck)}** / {st.session_state.total_count}")
        st.progress(1 - (len(st.session_state.deck) / st.session_state.total_count))

# --- 主畫面顯示 ---
if not st.session_state.deck:
    if st.session_state.total_count > 0:
        st.balloons()
        st.title("🎉 練習完成！")
        st.success("竹南辦公室的大家辛苦了！你已經背完所有單字。")
    else:
        st.info("👋 歡迎！請先從左側邊欄匯入單字 CSV 檔案開始練習。")
else:
    card = st.session_state.deck[0]
    
    # --- 正面視圖 ---
    st.markdown(f"<div class='word-title'>{card['word']}</div>", unsafe_allow_html=True)
    
    # 圖片處理
    if card['image_url'] and card['image_url'] != "無":
        st.image(card['image_url'], use_container_width=True)
    
    if st.button(f"🔊 聽讀音 ({card['word']})", use_container_width=True):
        speak(card['word'])

    st.divider()

    # --- 翻面控制 ---
    if not st.session_state.is_flipped:
        if st.button("🔍 顯示答案 (Space / Enter)", use_container_width=True, type="primary"):
            st.session_state.is_flipped = True
            speak(card['word']) # 翻面自動再讀一次
            st.rerun()
    else:
        # --- 背面視圖 ---
        st.markdown(f"""
            <div class='zh-trans'>
                {card['zh']} <span class='pos'>({card['pos']})</span>
            </div>
        """, unsafe_allow_html=True)
        
        # 記憶秘訣區
        st.markdown(f"""
            <div class='mnemonic-box'>
                <div class='mnemonic-title'>💡 44音與記憶秘訣</div>
                <div><b>🧩 拆解：</b>{card['phonics']}</div>
                <div style='color:#b91c1c; font-size:1.1rem; margin-top:5px;'><b>🗣️ 諧音：</b>{card['fake_pron']}</div>
                <div style='margin-top:5px;'>📖 {card['mnemonic']}</div>
            </div>
        """, unsafe_allow_html=True)
        
        # 例句區
        st.markdown(f"""
            <div class='section-title' style='color:#64748b; font-weight:bold; border-bottom:1px solid #eee;'>【情境例句】</div>
            <div class='example-box'>
                <div class='example-en'>{card['example_en']}</div>
                <div class='example-zh'>{card['example_zh']}</div>
            </div>
        """, unsafe_allow_html=True)
        
        if st.button("🔊 聽例句朗讀", use_container_width=True):
            speak(card['example_en'])

        st.divider()
        
        # SRS 評分按鈕
        c1, c2, c3, c4 = st.columns(4)
        if c1.button("🔴 重複", use_container_width=True, help="放入第2張"): handle_srs('again')
        if c2.button("🟠 模糊", use_container_width=True, help="放入中間"): handle_srs('hard')
        if c3.button("🟢 記住", use_container_width=True, help="移到最後"): handle_srs('good')
        if c4.button("🔵 簡單", use_container_width=True, help="直接移除"): handle_srs('easy')

# 隱藏 Streamlit 預設選單 (選用)
st.markdown("<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;}</style>", unsafe_allow_html=True)