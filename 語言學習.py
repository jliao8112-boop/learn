import streamlit as st
import pandas as pd
import random
import base64

# --- 頁面設定 ---
st.set_page_config(page_title="AI 科學單字記憶教練", layout="centered")

# --- CSS 樣式 (保留原網頁的視覺感) ---
st.markdown("""
<style>
    .word-title { font-size: 3rem; font-weight: bold; color: #1e293b; text-align: center; margin-bottom: 0; }
    .zh-trans { font-size: 1.5rem; font-weight: bold; color: #10b981; }
    .mnemonic-box { background: #fffcf0; border-left: 5px solid #fbc02d; padding: 15px; border-radius: 5px; margin: 10px 0; }
    .example-box { font-style: italic; color: #475569; border-left: 3px solid #cbd5e1; padding-left: 10px; }
    .stat-text { font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 初始化 Session State (進度儲存) ---
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
    """利用 HTML5 原生 Web Speech API 進行發音"""
    components_code = f"""
        <script>
            var msg = new SpeechSynthesisUtterance('{text}');
            msg.lang = 'en-US';
            msg.rate = 0.7;
            window.speechSynthesis.speak(msg);
        </script>
    """
    st.components.v1.html(components_code, height=0)

def handle_srs(rating):
    card = st.session_state.deck.pop(0)
    st.session_state.stats[rating] += 1
    
    if rating == 'again':
        st.session_state.deck.insert(min(1, len(st.session_state.deck)), card)
    elif rating == 'hard':
        st.session_state.deck.insert(len(st.session_state.deck)//2, card)
    elif rating == 'good':
        st.session_state.deck.append(card)
    # 'easy' 則不加回去，等於移除
    
    st.session_state.is_flipped = False
    st.rerun()

# --- 側邊欄：匯入與統計 ---
with st.sidebar:
    st.title("⚙️ 設定與統計")
    uploaded_file = st.file_uploader("匯入單字 CSV", type="csv")
    
    if uploaded_file:
        if st.button("確認載入並重置"):
            df = pd.read_csv(uploaded_file)
            st.session_state.deck = df.to_dict('records')
            st.session_state.total_count = len(st.session_state.deck)
            st.session_state.stats = {"again": 0, "hard": 0, "good": 0, "easy": 0}
            st.session_state.is_flipped = False
            st.success(f"已載入 {st.session_state.total_count} 個單字")
    
    st.divider()
    st.write(f"📊 剩餘單字: **{len(st.session_state.deck)}** / {st.session_state.total_count}")
    st.write(f"🔴 馬上重複: {st.session_state.stats['again']}")
    st.write(f"🟠 晚點複習: {st.session_state.stats['hard']}")
    st.write(f"🟢 移到最後: {st.session_state.stats['good']}")
    st.write(f"🔵 記住移除: {st.session_state.stats['easy']}")

# --- 主畫面邏輯 ---
if not st.session_state.deck:
    st.balloons()
    st.title("🎉 恭喜！練習完成！")
    st.write("請從側邊欄重新匯入檔案以開始新練習。")
else:
    current_card = st.session_state.deck[0]
    
    # 卡片容器
    with st.container():
        # 正面：單字與圖片
        st.markdown(f"<div class='word-title'>{current_card['word']}</div>", unsafe_allow_html=True)
        
        # 顯示圖片 (若 URL 效則顯示)
        if pd.notna(current_card.get('image_url')):
            st.image(current_card['image_url'], use_container_width=True)
            
        if st.button("🔊 聽讀音"):
            speak(current_card['word'])

        st.divider()

        # 翻面邏輯
        if not st.session_state.is_flipped:
            if st.button("點擊翻面 (Space)", use_container_width=True, type="primary"):
                st.session_state.is_flipped = True
                st.rerun()
        else:
            # 背面資訊
            st.markdown(f"<div class='zh-trans'>{current_card['zh']} <span style='font-size:0.8em; color:gray;'>({current_card['pos']})</span></div>", unsafe_allow_html=True)
            
            with st.markdown("<div class='mnemonic-box'>", unsafe_allow_html=True):
                st.markdown(f"**🧩 44音：** {current_card['phonics']}")
                st.markdown(f"**🗣️ 諧音記憶：** <span style='color:red;'>{current_card['fake_pron']}</span>", unsafe_allow_html=True)
                st.write(f"💡 {current_card['mnemonic']}")
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.subheader("【情境例句】")
            st.markdown(f"<div class='example-box'>{current_card['example_en']}<br>{current_card['example_zh']}</div>", unsafe_allow_html=True)
            
            if st.button("🔊 聽例句"):
                speak(current_card['example_en'])

            st.divider()
            
            # SRS 控制按鈕
            cols = st.columns(4)
            if cols[0].button("🔴 馬上重複", use_container_width=True): handle_srs('again')
            if cols[1].button("🟠 晚點複習", use_container_width=True): handle_srs('hard')
            if cols[2].button("🟢 移到最後", use_container_width=True): handle_srs('good')
            if cols[3].button("🔵 記住移除", use_container_width=True): handle_srs('easy')