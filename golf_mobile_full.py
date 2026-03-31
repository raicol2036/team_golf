import streamlit as st
import pandas as pd
import qrcode
from PIL import Image
import io
from datetime import datetime
import re

# Firebase
import firebase_admin
from firebase_admin import credentials, firestore

# Google Vision
from google.cloud import vision
from google.oauth2 import service_account

from streamlit_autorefresh import st_autorefresh

# ======================
# 基本設定
# ======================
st.set_page_config(page_title="Golf Live", layout="centered")

HOLES = [f"H{i}" for i in range(1,19)]
PAR = [4,4,3,5,4,4,3,4,5,4,4,3,5,4,4,3,4,5]

# ======================
# Firebase
# ======================
@st.cache_resource
def init_firebase():
    cfg = dict(st.secrets["firebase"])
    cfg["private_key"] = cfg["private_key"].replace("\\n","\n")

    if not firebase_admin._apps:
        cred = credentials.Certificate(cfg)
        firebase_admin.initialize_app(cred)

    return firestore.client()

db = init_firebase()

# ======================
# Vision
# ======================
@st.cache_resource
def init_vision():
from google.cloud import vision
from google.oauth2 import service_account
import streamlit as st

@st.cache_resource
def init_vision():
    cfg = st.secrets["google_vision"]   # ❗不要轉 dict

    credentials_obj = service_account.Credentials.from_service_account_info(dict(cfg))

    return vision.ImageAnnotatorClient(credentials=credentials_obj)
    cfg["private_key"] = cfg["private_key"].replace("\\n","\n")

    credentials_obj = service_account.Credentials.from_service_account_info(cfg)
    return vision.ImageAnnotatorClient(credentials=credentials_obj)

vision_client = init_vision()

# ======================
# 工具
# ======================
def gen_id():
    return datetime.now().strftime("%y%m%d_%H%M%S")

def make_qr(url):
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")

# ======================
# OCR（強化版）
# ======================
def ocr_scores(image):

    content = image.read()
    img = vision.Image(content=content)

    res = vision_client.text_detection(image=img)
    texts = res.text_annotations

    if not texts:
        return []

    raw = texts[0].description

    nums = re.findall(r'\b\d{1,2}\b', raw)
    nums = [int(x) for x in nums if 1 <= int(x) <= 12]

    return nums

# ======================
# 自動分玩家
# ======================
def split_players(nums):
    players = []

    for i in range(0, len(nums), 18):
        chunk = nums[i:i+18]
        if len(chunk) == 18:
            players.append(chunk)

    return players[:4]

# ======================
# 計算
# ======================
def calc(df):

    df["總桿"] = df[HOLES].sum(axis=1)
    df["淨桿"] = df["總桿"] - df["差點"]

    df["Birdie"] = df.apply(
        lambda r: sum([1 for i in range(18) if r[f"H{i+1}"] < PAR[i]]),
        axis=1
    )

    df = df.sort_values("總桿").reset_index(drop=True)
    df["排名"] = df.index + 1

    return df

# ======================
# 模式判斷
# ======================
params = st.query_params
mode = params.get("mode", "edit")
game_id = params.get("game_id", gen_id())

# ======================
# Viewer 模式
# ======================
if mode == "view":

    st.title("📺 即時比分")

    st_autorefresh(interval=5000)

    doc = db.collection("games").document(game_id).get()

    if doc.exists:
        data = doc.to_dict()
        df = pd.DataFrame(data["scores"])
        st.dataframe(df)
    else:
        st.warning("尚無資料")

    st.stop()

# ======================
# 主控模式
# ======================
st.title("⛳ Golf 系統")

APP_URL = st.text_input("App網址")
game_id = st.text_input("比賽ID", game_id)

if APP_URL:
    url = f"{APP_URL}?mode=view&game_id={game_id}"
    st.image(make_qr(url))
    st.code(url)

# ======================
# OCR
# ======================
uploaded = st.file_uploader("📸 上傳計分卡", type=["jpg","png"])

auto_players = []

if uploaded:
    st.image(uploaded)

    if st.button("辨識"):
        nums = ocr_scores(uploaded)
        auto_players = split_players(nums)

        st.success(f"辨識 {len(auto_players)} 位玩家")

# ======================
# 輸入
# ======================
players = []

for i in range(4):

    name = st.text_input(f"姓名{i+1}", f"P{i+1}")
    hcp = st.number_input(f"差點{i+1}",0,50,0)

    scores = []

    for h in range(18):

        default = 0
        if i < len(auto_players):
            default = auto_players[i][h]

        s = st.number_input(f"{i+1}-{h+1}",0,15,default,key=f"{i}{h}")
        scores.append(s)

    row={"姓名":name,"差點":hcp}
    for h in range(18):
        row[f"H{h+1}"]=scores[h]

    players.append(row)

df = pd.DataFrame(players)

# ======================
# 計算 + Firebase
# ======================
if st.button("🔥 計算 & 同步"):

    result = calc(df)

    st.dataframe(result)

    # 🔥寫入Firebase
    db.collection("games").document(game_id).set({
        "scores": result.to_dict(orient="records"),
        "time": str(datetime.now())
    })

    st.success("已同步 ✔")
