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
def ocr_scores(uploaded_file):
    try:
        if vision_client is None:
            return None

        image = Image.open(uploaded_file)
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')

        img = vision.Image(content=img_byte_arr.getvalue())

        response = vision_client.text_detection(image=img)

        texts = response.text_annotations

        if not texts:
            return None

        raw_text = texts[0].description

        # 取出數字
        nums = []
        for t in raw_text.split():
            if t.isdigit():
                nums.append(int(t))

        return nums if nums else None

    except Exception as e:
        st.error("OCR 失敗，請手動輸入")
        return None

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
