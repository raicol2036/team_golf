import streamlit as st
import pandas as pd
import qrcode
from PIL import Image, ImageDraw, ImageFont
import io
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, firestore

# ======================
# 設定
# ======================
st.set_page_config(page_title="Team Golf", layout="centered")
st.title("⛳ 球隊成績系統")

HOLES = [f"H{i}" for i in range(1,19)]
PAR = [4,4,3,5,4,4,3,4,5,4,4,3,5,4,4,3,4,5]

# ======================
# Firebase
# ======================
@st.cache_resource
def init_firebase():
    if "firebase" not in st.secrets:
        st.error("❌ Firebase 未設定")
        st.stop()

    cfg = dict(st.secrets["firebase"])
    cfg["private_key"] = cfg["private_key"].replace("\\n", "\n")

    if not firebase_admin._apps:
        cred = credentials.Certificate(cfg)
        firebase_admin.initialize_app(cred)

    return firestore.client()

db = init_firebase()

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
# 冠亞軍限制
# ======================
def assign_awards(df, history):
    champ, runner = None, None

    for _, r in df.iterrows():
        name = r["姓名"]
        h = history.get(name, {"c":0,"r":0})

        if h["c"]>=1 and h["r"]>=1:
            continue

        if champ is None and h["c"]==0:
            champ = name
            history.setdefault(name,{"c":0,"r":0})
            history[name]["c"]+=1
            continue

        if runner is None and h["r"]==0 and name!=champ:
            runner = name
            history.setdefault(name,{"c":0,"r":0})
            history[name]["r"]+=1

    return champ, runner, history

# ======================
# 分享圖
# ======================
def build_text(champ, runner, df, awards):
    lines = ["🏆 比賽結果"]

    if champ:
        lines.append(f"🥇 {champ}")
    if runner:
        lines.append(f"🥈 {runner}")

    lines.append("\n🏌️ Birdie")
    for _, r in df.iterrows():
        if r["Birdie"] > 0:
            lines.append(f"{r['姓名']} ×{r['Birdie']}")

    def add(title,data):
        lines.append(f"\n{title}")
        for p in data:
            lines.append(p)

    add("🟠 遠距", awards["ld"])
    add("🥇 一近洞", awards["one"])
    add("🥈 二近洞", awards["two"])
    add("🥉 三近洞", awards["three"])
    add("🔵 N近洞", awards["n"])
    add("❤️ 親密", awards["love"])

    return "\n".join(lines)

def text_to_img(text):
    lines = text.split("\n")
    img = Image.new("RGB",(800,40*len(lines)+80),(255,255,255))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf",28)
    except:
        font = ImageFont.load_default()

    y=40
    for l in lines:
        draw.text((40,y),l,(0,0,0),font=font)
        y+=40

    return img

# ======================
# UI
# ======================
if "history" not in st.session_state:
    st.session_state.history = {}

APP_URL = st.text_input("App網址")

game_id = st.text_input("比賽ID", gen_id())

if st.button("建立比賽"):
    db.collection("games").document(game_id).set({"created": str(datetime.now())})
    st.success(f"已建立 {game_id}")

if APP_URL:
    url = f"{APP_URL}?game_id={game_id}"
    st.image(make_qr(url))
    st.code(url)

# ======================
# 輸入
# ======================
players = []
names = []

st.subheader("輸入成績")

for i in range(4):
    name = st.text_input(f"姓名{i+1}", f"P{i+1}")
    hcp = st.number_input(f"差點{i+1}",0,50,0)

    scores = []
    cols = st.columns(3)

    for h in range(18):
        with cols[h%3]:
            s = st.number_input(f"{h+1}-{i}",0,15,0,key=f"{i}{h}")
            scores.append(s)

    row={"姓名":name,"差點":hcp}
    for h in range(18):
        row[f"H{h+1}"]=scores[h]

    players.append(row)
    names.append(name)

df = pd.DataFrame(players)

# ======================
# 獎項
# ======================
def pick(title,n,key):
    st.markdown(title)
    return [st.selectbox(f"{title}{i}",names,key=f"{key}{i}") for i in range(n)]

awards = {
    "ld": pick("遠距",2,"ld"),
    "one": pick("一近洞",2,"one"),
    "two": pick("二近洞",2,"two"),
    "three": pick("三近洞",2,"three"),
    "n": pick("N近洞",10,"n"),
    "love": pick("親密",2,"love")
}

# ======================
# 計算
# ======================
if st.button("計算"):

    result = calc(df)

    champ, runner, history = assign_awards(result, st.session_state.history)
    st.session_state.history = history

    st.success(f"🥇 {champ}")
    st.info(f"🥈 {runner}")

    st.dataframe(result)

    text = build_text(champ, runner, result, awards)
    img = text_to_img(text)

    st.image(img)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    st.download_button("下載結果", buf.getvalue(), "result.png")

# ======================
# 重置
# ======================
if st.button("重置賽季"):
    st.session_state.history = {}
