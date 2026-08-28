import streamlit as st
import pandas as pd
import re
import io
import json
import os
from datetime import datetime

# --- 頁面設定 ---
st.set_page_config(page_title="AI 科學單字記憶教練", layout="centered")

# --- CSS 樣式 ---
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
    .resume-box { background-color: #e0f2fe; border: 1px solid #7dd3fc; padding: 15px; border-radius: 8px; margin-bottom: 15px; }
</style>
""", unsafe_allow_html=True)

PROGRESS_FILE = "vocab_progress.json"

# --- 初始化 Session State ---
if 'deck' not in st.session_state:
    st.session_state.deck = []
if 'total_count' not in st.session_state:
    st.session_state.total_count = 0
if 'is_flipped' not in st.session_state:
    st.session_state.is_flipped = False
if 'stats' not in st.session_state:
    st.session_state.stats = {"again": 0, "hard": 0, "good": 0, "easy": 0}
if 'source_name' not in st.session_state:
    st.session_state.source_name = "未命名題庫"

# --- 欄位定義 ---
COL_NAMES = [
    'word', 'audio_url', 'image_url', 'pos', 'zh', 
    'forms', 'example_en', 'example_zh', 'phonics', 
    'fake_pron', 'mnemonic'
]

# --- 斷點存檔與載入函式 ---
def save_progress_to_local():
    if st.session_state.total_count > 0:
        data = {
            "deck": st.session_state.deck,
            "total_count": st.session_state.total_count,
            "stats": st.session_state.stats,
            "source_name": st.session_state.source_name,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        try:
            with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

def get_saved_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def clear_saved_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            os.remove(PROGRESS_FILE)
        except Exception:
            pass

# --- 自動掃描專案資料夾中的 CSV/Excel 檔案 ---
def scan_local_folder_files(target_dir="."):
    """自動找出目錄下所有的 csv 與 excel 檔案"""
    found_files = []
    valid_exts = ('.csv', '.txt', '.xlsx', '.xls')
    for root, dirs, files in os.walk(target_dir):
        # 忽略隱藏資料夾
        if any(p.startswith('.') for p in root.split(os.sep)):
            continue
        for file in files:
            if file.endswith(valid_exts) and not file.startswith('.'):
                rel_path = os.path.relpath(os.path.join(root, file), target_dir)
                found_files.append(rel_path)
    return sorted(found_files)

# --- 語音發音 ---
def speak(text, rate=0.8):
    if not text or text == "無": return
    js_code = f"""
        <script>
            window.speechSynthesis.cancel();
            var msg = new SpeechSynthesisUtterance("{text.replace('"', '')}");
            msg.lang = 'en-US';
            msg.rate = {rate};
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
    if st.session_state.deck:
        save_progress_to_local()
    else:
        clear_saved_progress()
    st.rerun()

def convert_cloud_url(url: str) -> str:
    url = url.strip()
    if "docs.google.com/spreadsheets" in url:
        match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
        if match:
            sheet_id = match.group(1)
            gid_match = re.search(r'[#&]gid=([0-9]+)', url)
            gid = gid_match.group(1) if gid_match else "0"
            return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    elif "drive.google.com" in url:
        match = re.search(r'/d/([a-zA-Z0-9-_]+)', url) or re.search(r'id=([a-zA-Z0-9-_]+)', url)
        if match:
            file_id = match.group(1)
            return f"https://drive.google.com/uc?export=download&id={file_id}"
    return url

# --- 核心 DataFrame 標準化處理 ---
def set_deck_from_dataframe(df, source_label=""):
    if df is None or df.empty:
        raise ValueError("檔案內容為空或無法讀取")
    
    # 處理欄位對應
    if len(df.columns) >= len(COL_NAMES):
        df = df.iloc[:, :len(COL_NAMES)]
        df.columns = COL_NAMES
    else:
        curr_len = len(df.columns)
        df.columns = COL_NAMES[:curr_len]
        for col in COL_NAMES[curr_len:]:
            df[col] = ""
            
    df = df.fillna("").astype(str)
    
    st.session_state.deck = df.to_dict('records')
    st.session_state.total_count = len(st.session_state.deck)
    st.session_state.stats = {"again": 0, "hard": 0, "good": 0, "easy": 0}
    st.session_state.is_flipped = False
    st.session_state.source_name = source_label
    save_progress_to_local()

# --- 檔案讀取器（支援多編碼與 Excel） ---
def read_any_file(file_bytes, filename=""):
    # 判斷是否為 Excel
    if filename.endswith(('.xlsx', '.xls')):
        try:
            return pd.read_excel(io.BytesIO(file_bytes), skiprows=1, header=None)
        except Exception:
            return pd.read_excel(io.BytesIO(file_bytes))
    
    # CSV / TXT 多種編碼測試
    for enc in ['utf-8-sig', 'utf-8', 'cp950', 'big5', 'latin1']:
        try:
            df = pd.read_csv(io.BytesIO(file_bytes), skiprows=1, header=None, encoding=enc)
            if not df.empty:
                return df
        except Exception:
            continue
    raise ValueError("無法解析此檔案的編碼格式")

# --- 側邊欄 ---
with st.sidebar:
    st.title("⚙️ 記憶教練設定")
    
    # 1. 語速控制
    st.subheader("🔊 發音設定")
    speech_rate = st.slider("朗讀速度 (倍速)", 0.5, 1.5, 0.8, 0.05)
    
    st.divider()
    
    # 2. 斷點記憶區
    st.subheader("💾 斷點進度")
    saved_prog = get_saved_progress()
    if saved_prog and len(saved_prog.get("deck", [])) > 0:
        st.info(f"📌 **{saved_prog.get('source_name', '單字庫')}**\n\n剩餘: **{len(saved_prog['deck'])}** / {saved_prog['total_count']} 題")
        if st.button("▶️ 載入上次進度", use_container_width=True, type="primary"):
            st.session_state.deck = saved_prog["deck"]
            st.session_state.total_count = saved_prog["total_count"]
            st.session_state.stats = saved_prog["stats"]
            st.session_state.source_name = saved_prog.get("source_name", "未命名題庫")
            st.session_state.is_flipped = False
            st.success("✅ 已接續進度！")
            st.rerun()
            
    st.divider()

    # 3. 匯入題庫（四大模式）
    st.subheader("📁 選擇題庫來源")
    import_mode = st.radio(
        "來源方式：", 
        [
            "📂 專案資料夾直接選檔", 
            "📱 手機/平板上傳檔案", 
            "☁️ Google 試算表 / 雲端硬碟", 
            "📋 直接貼上文字"
        ]
    )
    
    # 模式一：自動掃描電腦/伺服器資料夾
    if import_mode == "📂 專案資料夾直接選檔":
        local_files = scan_local_folder_files()
        if local_files:
            selected_file = st.selectbox("請選擇資料夾內的檔案：", local_files)
            if st.button("載入所選題庫", use_container_width=True):
                try:
                    with open(selected_file, "rb") as f:
                        df = read_any_file(f.read(), selected_file)
                    set_deck_from_dataframe(df, selected_file)
                    st.success(f"✅ 成功載入：{selected_file} ({st.session_state.total_count} 題)")
                    st.rerun()
                except Exception as e:
                    st.error(f"讀取失敗：{e}")
        else:
            st.warning("⚠️ 程式所在資料夾內未發現 CSV 或 Excel 檔案。請將檔案放入專案目錄中。")

    # 模式二：手機/平板上傳（解除 iOS 檔案反灰限制）
    elif import_mode == "📱 手機/平板上傳檔案":
        # 移除副檔名強制限制，解決 iOS 反灰問題
        uploaded_file = st.file_uploader("請選擇檔案 (支援 CSV / Excel)", type=None)
        if uploaded_file:
            if st.button("確認載入並開始練習", use_container_width=True):
                try:
                    df = read_any_file(uploaded_file.getvalue(), uploaded_file.name)
                    set_deck_from_dataframe(df, uploaded_file.name)
                    st.success(f"✅ 已載入 {st.session_state.total_count} 個單字")
                    st.rerun()
                except Exception as e:
                    st.error(f"讀取失敗：{e}")

    # 模式三：Google 試算表 / 雲端硬碟
    elif import_mode == "☁️ Google 試算表 / 雲端硬碟":
        cloud_url = st.text_input("輸入 Google Sheets 或 Drive 連結：")
        if cloud_url:
            if st.button("從雲端載入題庫", use_container_width=True):
                try:
                    target_url = convert_cloud_url(cloud_url)
                    df = pd.read_csv(target_url, skiprows=1, header=None)
                    set_deck_from_dataframe(df, "Google 雲端題庫")
                    st.success(f"✅ 成功載入 {st.session_state.total_count} 個單字")
                    st.rerun()
                except Exception as e:
                    st.error(f"雲端讀取失敗，請檢查共用權限: {e}")

    # 模式四：直接貼上表格文字 (手機上最方便)
    elif import_mode == "📋 直接貼上文字":
        pasted_text = st.text_area("直接貼上 CSV 或 Excel 複製的內容：", height=150)
        if pasted_text:
            if st.button("解析並載入文字內容", use_container_width=True):
                try:
                    df = pd.read_csv(io.StringIO(pasted_text), sep=None, engine='python', skiprows=1, header=None)
                    set_deck_from_dataframe(df, "剪貼簿內容")
                    st.success(f"✅ 成功載入 {st.session_state.total_count} 個單字")
                    st.rerun()
                except Exception as e:
                    st.error(f"解析失敗：{e}")

    st.divider()
    if st.session_state.total_count > 0:
        st.write(f"📊 剩餘進度: **{len(st.session_state.deck)}** / {st.session_state.total_count}")
        st.progress(1 - (len(st.session_state.deck) / st.session_state.total_count))
        if st.button("🗑️ 清除當前進度與重置", use_container_width=True):
            st.session_state.deck = []
            st.session_state.total_count = 0
            st.session_state.stats = {"again": 0, "hard": 0, "good": 0, "easy": 0}
            clear_saved_progress()
            st.rerun()

# --- 主畫面顯示 ---
if not st.session_state.deck:
    if st.session_state.total_count > 0:
        st.balloons()
        st.title("🎉 練習完成！")
        st.success("太棒了！你已經背完所有單字。")
    else:
        saved_prog = get_saved_progress()
        if saved_prog and len(saved_prog.get("deck", [])) > 0:
            st.markdown(f"""
            <div class='resume-box'>
                <h3>📌 發現上次未完成的單字進度！</h3>
                <p><b>題庫名稱：</b>{saved_prog.get('source_name', '單字庫')}</p>
                <p><b>剩餘單字：</b>{len(saved_prog['deck'])} / {saved_prog['total_count']}</p>
                <p><b>上次紀錄時間：</b>{saved_prog.get('last_updated', '')}</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("▶️ 點此接續上次進度 (斷點續背)", type="primary", use_container_width=True):
                st.session_state.deck = saved_prog["deck"]
                st.session_state.total_count = saved_prog["total_count"]
                st.session_state.stats = saved_prog["stats"]
                st.session_state.source_name = saved_prog.get("source_name", "未命名題庫")
                st.session_state.is_flipped = False
                st.rerun()
            st.divider()
        st.info("👋 請從左側邊欄選擇題庫來源（支援專案資料夾直接選檔、手機上傳、Google 試算表或直接貼上）。")
else:
    card = st.session_state.deck[0]
    
    # --- 正面視圖 ---
    st.markdown(f"<div class='word-title'>{card['word']}</div>", unsafe_allow_html=True)
    
    if card['image_url'] and card['image_url'] != "無":
        st.image(card['image_url'], use_container_width=True)
    
    if st.button(f"🔊 聽讀音 ({card['word']})", use_container_width=True):
        speak(card['word'], rate=speech_rate)

    st.divider()

    # --- 翻面控制 ---
    if not st.session_state.is_flipped:
        if st.button("🔍 顯示答案 (Space / Enter)", use_container_width=True, type="primary"):
            st.session_state.is_flipped = True
            speak(card['word'], rate=speech_rate)
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
            speak(card['example_en'], rate=speech_rate)

        st.divider()
        
        # SRS 評分按鈕
        c1, c2, c3, c4 = st.columns(4)
        if c1.button("🔴 重複", use_container_width=True, help="放入第2張"): handle_srs('again')
        if c2.button("🟠 模糊", use_container_width=True, help="放入中間"): handle_srs('hard')
        if c3.button("🟢 記住", use_container_width=True, help="移到最後"): handle_srs('good')
        if c4.button("🔵 簡單", use_container_width=True, help="直接移除"): handle_srs('easy')

# 隱藏 Streamlit 預設選單
st.markdown("<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;}</style>", unsafe_allow_html=True)