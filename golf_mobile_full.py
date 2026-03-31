import streamlit as st
import pandas as pd
import numpy as np
import cv2
import pytesseract
import re
from PIL import Image, ImageDraw, ImageFont
import io

st.set_page_config(page_title="Golf System", layout="centered")

st.title("⛳ Golf 比賽系統（完整版）")

HOLES = [f"H{i}" for i in range(1,19)]
PAR = [4,4,3,5,4,4,3,4,5,4,4,3,5,4,4,3,4,5]

# ======================
# 初始化
# ======================
if "history" not in st.session_state:
    st.session_state.history = {}

# ======================
# OCR
# ======================
def preprocess(img):
    img = np.array(img)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    th = cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY,31,11)
    th = cv2.resize(th, None, fx=2, fy=2)
    return th

def ocr(img):
    return pytesseract.image_to_string(img, config='--oem 3 --psm 6')

def parse(text):
    lines = text.splitlines()
    data = []
    for line in lines:
        nums = re.findall(r'\d+', line)
        if len(nums) >= 9:
            name = re.findall(r'[A-Za-z\u4e00-\u9fff]+', line)
            name = name[0] if name else f"P{len(data)+1}"
            scores = [int(x) for x in nums[:18]]
            scores += [0]*(18-len(scores))
            row = {"姓名":name,"差點":0}
            for i in range(18):
                row[f"H{i+1}"] = scores[i]
            data.append(row)

    if len(data)==0:
        data = [{"姓名":f"P{i+1}",**{h:0 for h in HOLES},"差點":0} for i in range(4)]

    return pd.DataFrame(data)

# ======================
# 計算
# ======================
def assign_awards(df, history):
    champion = None
    runner = None

    for _, row in df.iterrows():
        name = row["姓名"]
        h = history.get(name, {"champion":0,"runner":0})

        if h["champion"]>=1 and h["runner"]>=1:
            continue

        if champion is None and h["champion"]==0:
            champion = name
            history.setdefault(name, {"champion":0,"runner":0})
            history[name]["champion"] += 1
            continue

        if runner is None and h["runner"]==0 and name != champion:
            runner = name
            history.setdefault(name, {"champion":0,"runner":0})
            history[name]["runner"] += 1

    return champion, runner, history

def calc(df, history):
    df = df.copy()

    df["總桿"] = df[HOLES].sum(axis=1)
    df["淨桿"] = df["總桿"] - df["差點"]

    # Birdie
    birdies = []
    for _, row in df.iterrows():
        count = sum([1 for i in range(18) if row[f"H{i+1}"] < PAR[i]])
        birdies.append(count)
    df["Birdie"] = birdies

    df = df.sort_values("總桿").reset_index(drop=True)

    champion, runner, history = assign_awards(df, history)

    return df, champion, runner, history

# ======================
# 分享圖
# ======================
def build_summary(champ, runner, result,
                  one_near, two_near, three_near,
                  n_near, love_award, long_drive):

    lines = ["🏆 比賽結果"]

    if champ:
        s = result[result["姓名"]==champ]["總桿"].values[0]
        lines.append(f"🥇 {champ}（{s}）")

    if runner:
        s = result[result["姓名"]==runner]["總桿"].values[0]
        lines.append(f"🥈 {runner}（{s}）")

    lines.append("\n🏌️ Birdie")
    for _, r in result.iterrows():
        if r["Birdie"]>0:
            lines.append(f"{r['姓名']} ×{r['Birdie']}")

    def add(title,data):
        if data:
            lines.append(f"\n{title}")
            for p,h in data:
                lines.append(f"H{h}：{p}")

    add("🎯 一近洞", one_near)
    add("🎯 二近洞", two_near)
    add("🎯 三近洞", three_near)
    add("🎯 N近洞", n_near)
    add("❤️ 親密獎", love_award)
    add("🟠 遠距獎", long_drive)

    return "\n".join(lines)

def text_to_image(text):
    lines = text.split("\n")
    w,h = 800, 40*len(lines)+80
    img = Image.new("RGB",(w,h),(255,255,255))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf",28)
    except:
        font = ImageFont.load_default()

    y=40
    for line in lines:
        draw.text((40,y), line, fill=(0,0,0), font=font)
        y+=40

    return img

# ======================
# 上傳
# ======================
st.subheader("📸 上傳記分卡")
file = st.file_uploader("上傳照片", type=["jpg","png"])

if file:
    img = Image.open(file)
    st.image(img)
    text = ocr(preprocess(img))
    df = parse(text)
else:
    df = pd.DataFrame([
        {"姓名":f"P{i+1}",**{h:0 for h in HOLES},"差點":0}
        for i in range(4)
    ])

# ======================
# 輸入
# ======================
players = []

st.subheader("✏️ 成績輸入")

for i in range(len(df)):
    with st.expander(df.loc[i,"姓名"]):
        name = st.text_input("姓名", df.loc[i,"姓名"], key=f"name{i}")
        hcp = st.number_input("差點",0,50,0,key=f"hcp{i}")

        scores=[]
        cols = st.columns(3)

        for h in range(18):
            with cols[h%3]:
                val = st.number_input(f"{h+1}",0,15,df.loc[i,f"H{h+1}"],key=f"{i}_{h}")
                scores.append(val)

        row={"姓名":name,"差點":hcp}
        for h in range(18):
            row[f"H{h+1}"]=scores[h]

        players.append(row)

df_input = pd.DataFrame(players)

# ======================
# 獎項
# ======================
st.subheader("🎯 獎項設定")
names = list(df_input["姓名"])

def input_award(title, n, key):
    st.markdown(title)
    res=[]
    for i in range(n):
        c1,c2=st.columns(2)
        with c1:
            p=st.selectbox(f"{i+1}",names,key=f"{key}p{i}")
        with c2:
            h=st.number_input("洞",1,18,key=f"{key}h{i}")
        res.append((p,h))
    return res

one_near = input_award("🥇 一近洞",2,"one")
two_near = input_award("🥈 二近洞",2,"two")
three_near = input_award("🥉 三近洞",2,"three")
n_near = input_award("🔵 N近洞",10,"n")
love_award = input_award("❤️ 親密獎",2,"love")

ld_count = st.number_input("遠距獎數量",0,10,1)
long_drive = input_award("🟠 遠距獎",ld_count,"ld")

# ======================
# 計算
# ======================
if st.button("🔥 計算結果"):

    result, champ, runner, history = calc(df_input, st.session_state.history)
    st.session_state.history = history

    st.success(f"🥇 冠軍：{champ}")
    st.info(f"🥈 亞軍：{runner}")

    st.dataframe(result)

    # 分享圖
    st.subheader("📱 分享")

    text = build_summary(
        champ, runner, result,
        one_near, two_near, three_near,
        n_near, love_award, long_drive
    )

    img = text_to_image(text)
    st.image(img)

    buf = io.BytesIO()
    img.save(buf, format="PNG")

    st.download_button("⬇️ 下載圖片", buf.getvalue(), "result.png")

# ======================
# 重置
# ======================
if st.button("🔄 重置賽季"):
    st.session_state.history = {}
    st.success("已重置")
