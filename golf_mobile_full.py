import streamlit as st
import pandas as pd
import numpy as np
import re
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
@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        cfg = dict(st.secrets["firebase"])
        cred = credentials.Certificate(cfg)
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_firebase()

# =========================
# Vision 初始化
# =========================
@st.cache_resource
def init_vision():
    try:
        cfg = dict(st.secrets["google_vision"])
        cfg["private_key"] = cfg["private_key"].replace("\\n", "\n")
        credentials_obj = service_account.Credentials.from_service_account_info(cfg)
        return vision.ImageAnnotatorClient(credentials=credentials_obj)
    except Exception as e:
        st.warning("⚠️ OCR 初始化失敗，改用手動輸入")
        return None

vision_client = init_vision()

# =========================
# 智慧 OCR 解析
# =========================
def smart_ocr_scores(raw_text):
    nums = re.findall(r'\d+', raw_text)
    nums = [int(n) for n in nums]

    # 過濾合理桿數
    nums = [n for n in nums if 1 <= n <= 12]

    if len(nums) < 18:
        return None

    candidates = []

    for p in range(1, 7):  # 支援1~6人
        if len(nums) >= 18 * p:
            data = nums[:18 * p]
            matrix = np.array(data).reshape(p, 18)
            candidates.append(matrix)

    if not candidates:
        return None

    # 選最合理（平均接近5桿）
    best = None
    best_score = 999

    for m in candidates:
        avg = np.mean(m)
        score = abs(avg - 5)
        if score < best_score:
            best_score = score
            best = m

    return best

# =========================
# OCR
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

        st.subheader("🔍 OCR 原始內容")
        st.text(raw_text)

        matrix = smart_ocr_scores(raw_text)
        return matrix

    except Exception as e:
        st.error(f"OCR錯誤: {e}")
        return None

# =========================
# Firebase 存資料
# =========================
def save_game(game_id, players, scores):
    data = {
        "players": players,
        "scores": {players[i]: scores[i].tolist() for i in range(len(players))}
    }
    db.collection("golf_games").document(game_id).set(data)

# =========================
# Firebase 讀資料（Viewer用）
# =========================
def load_game(game_id):
    doc = db.collection("golf_games").document(game_id).get()
    if doc.exists:
        return doc.to_dict()
    return None

# =========================
# UI
# =========================
st.set_page_config(page_title="Golf OCR System", layout="centered")

st.title("⛳ Golf OCR 即時比分系統")

mode = st.radio("模式", ["主控端", "查看端"])

game_id = st.text_input("Game ID", "test_game")

# =========================
# 主控端
# =========================
if mode == "主控端":

    players_input = st.text_input("球員（逗號分隔）", "A,B,C,D")
    players = [p.strip() for p in players_input.split(",") if p.strip()]

    uploaded = st.file_uploader("📸 上傳記分卡", type=["png", "jpg", "jpeg"])

    scores = None

    if uploaded:
        st.image(uploaded, use_container_width=True)
        scores = ocr_scores(uploaded)

    manual = st.text_input("✏️ 手動輸入（18位數）")

    if manual:
        nums = [int(x) for x in re.findall(r'\d+', manual)]
        if len(nums) >= 18:
            scores = np.array(nums[:18]).reshape(1, 18)

    # 顯示結果
    if scores is not None:
        st.subheader("📊 成績解析")

        for i in range(scores.shape[0]):
            name = players[i] if i < len(players) else f"Player{i+1}"
            df = pd.DataFrame({
                "Hole": range(1, 19),
                "Score": scores[i]
            })
            st.write(f"### {name}")
            st.dataframe(df, use_container_width=True)

        if st.button("💾 存到 Firebase"):
            save_game(game_id, players, scores)
            st.success("✅ 已儲存")

# =========================
# 查看端
# =========================
if mode == "查看端":
    data = load_game(game_id)

    if data:
        st.subheader("📊 即時比分")

        for player, sc in data["scores"].items():
            df = pd.DataFrame({
                "Hole": range(1, len(sc)+1),
                "Score": sc
            })
            st.write(f"### {player}")
            st.dataframe(df, use_container_width=True)
    else:
        st.warning("查無資料")
