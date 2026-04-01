import streamlit as st
import pandas as pd
import numpy as np
import re

# Firebase
import firebase_admin
from firebase_admin import credentials, firestore

# =========================
# Firebase 初始化
# =========================
@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        cfg = dict(st.secrets["firebase"])
        cfg["private_key"] = cfg["private_key"].replace("\\n", "\n")
        cred = credentials.Certificate(cfg)
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_firebase()

# =========================
# 存資料
# =========================
def save_game(game_id, players, scores):
    data = {
        "players": players,
        "scores": {players[i]: scores[i] for i in range(len(players))}
    }
    db.collection("golf_games").document(game_id).set(data)

# =========================
# 讀資料
# =========================
def load_game(game_id):
    doc = db.collection("golf_games").document(game_id).get()
    if doc.exists:
        return doc.to_dict()
    return None

# =========================
# UI
# =========================
st.set_page_config(page_title="Golf System", layout="centered")

st.title("⛳ Golf 即時比分系統（快速輸入版）")

mode = st.radio("模式", ["主控端", "查看端"])

game_id = st.text_input("Game ID", "game001")

# =========================
# 主控端
# =========================
if mode == "主控端":

    players_input = st.text_input("球員（逗號分隔）", "A,B,C,D")
    players = [p.strip() for p in players_input.split(",") if p.strip()]

    st.subheader("✏️ 快速輸入（每人18洞）")

    scores = []

    for i, p in enumerate(players):
        txt = st.text_input(f"{p} 成績（18位數）", key=f"p{i}")

        if txt:
            nums = [int(x) for x in re.findall(r'\d+', txt)]

            if len(nums) == 18:
                scores.append(nums)
            else:
                st.warning(f"{p} 必須輸入18個數字")

    # =========================
    # 顯示結果
    # =========================
    if len(scores) == len(players):

        st.subheader("📊 成績")

        for i, p in enumerate(players):
            df = pd.DataFrame({
                "Hole": range(1, 19),
                "Score": scores[i]
            })
            st.write(f"### {p}")
            st.dataframe(df, use_container_width=True)

        # =========================
        # 總桿
        # =========================
        totals = [sum(s) for s in scores]

        result_df = pd.DataFrame({
            "Player": players,
            "Total": totals
        }).sort_values("Total")

        st.subheader("🏆 總桿排名")
        st.dataframe(result_df, use_container_width=True)

        # =========================
        # 存 Firebase
        # =========================
        if st.button("💾 儲存比賽"):
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

        # 總桿
        totals = {p: sum(sc) for p, sc in data["scores"].items()}

        result_df = pd.DataFrame({
            "Player": list(totals.keys()),
            "Total": list(totals.values())
        }).sort_values("Total")

        st.subheader("🏆 排名")
        st.dataframe(result_df, use_container_width=True)

    else:
        st.warning("查無資料")
