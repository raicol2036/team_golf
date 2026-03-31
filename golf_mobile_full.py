import streamlit as st
import pandas as pd
from PIL import Image
import io

# Firebase
import firebase_admin
from firebase_admin import credentials, firestore

# Vision
from google.cloud import vision
from google.oauth2 import service_account

# =========================
# Firebase 初始化
# =========================
def init_firebase():
    if not firebase_admin._apps:
        cfg = st.secrets["firebase"]
        cred = credentials.Certificate(dict(cfg))
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_firebase()

# =========================
# Vision 初始化（無 cache 避免錯誤）
# =========================
def init_vision():
    try:
        cfg = st.secrets["google_vision"]
        credentials_obj = service_account.Credentials.from_service_account_info(dict(cfg))
        return vision.ImageAnnotatorClient(credentials=credentials_obj)
    except Exception as e:
        st.warning("OCR 初始化失敗，改用手動輸入")
        return None

vision_client = init_vision()

# =========================
# OCR 辨識
# =========================
import re
import numpy as np

def smart_ocr_scores(raw_text):
    """
    自動解析：
    1. 抓數字
    2. 過濾異常值
    3. 判斷橫/直格式
    4. 自動分玩家
    """

    # =========================
    # 1. 抓全部數字
    # =========================
    nums = re.findall(r'\d+', raw_text)
    nums = [int(n) for n in nums]

    # =========================
    # 2. 過濾合理桿數（1~12）
    # =========================
    nums = [n for n in nums if 1 <= n <= 12]

    if len(nums) < 18:
        return None

    # =========================
    # 3. 嘗試不同玩家數切分
    # =========================
    possible_players = []

    for p in range(2, 7):  # 2~6人
        if len(nums) >= 18 * p:
            data = nums[:18 * p]
            matrix = np.array(data).reshape(p, 18)
            possible_players.append(matrix)

    if not possible_players:
        # fallback：單人18洞
        return np.array(nums[:18]).reshape(1, 18)

    # =========================
    # 4. 判斷哪個最合理（平均落在3~8）
    # =========================
    best = None
    best_score = 999

    for m in possible_players:
        avg = np.mean(m)
        score = abs(avg - 5)  # 高爾夫平均約5桿

        if score < best_score:
            best_score = score
            best = m

    return best
# =========================
# Firebase 存資料
# =========================
def save_scores(game_id, players, scores):
    data = {
        "players": players,
        "scores": scores
    }
    db.collection("golf_games").document(game_id).set(data)

# =========================
# UI
# =========================
st.title("⛳ Golf Team 記錄系統（OCR + Firebase）")

game_id = st.text_input("Game ID", "test_game")

players = st.text_input("球員（用逗號分隔）", "A,B,C,D").split(",")

uploaded = st.file_uploader("📸 上傳記分卡圖片", type=["png", "jpg", "jpeg"])

scores = None

# =========================
# OCR 辨識
# =========================
if uploaded:
    st.image(uploaded, caption="上傳圖片", use_container_width=True)

    nums = ocr_scores(uploaded)

    if nums:
        st.success(f"辨識成功：{nums}")
        scores = nums
    else:
        st.warning("辨識不到數字，請手動輸入")

# =========================
# 手動輸入（備援）
# =========================
manual_input = st.text_input("✏️ 手動輸入（18位數，例如 445544...）")

if manual_input:
    scores = [int(x) for x in manual_input if x.isdigit()]

# =========================
# 顯示結果
# =========================
if scores:
    st.subheader("📊 成績")

    df = pd.DataFrame({
        "Hole": list(range(1, len(scores)+1)),
        "Score": scores
    })

    st.dataframe(df)

    if st.button("💾 存到 Firebase"):
        save_scores(game_id, players, scores)
        st.success("已儲存！")
