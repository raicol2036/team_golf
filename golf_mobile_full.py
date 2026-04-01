import streamlit as st
import pandas as pd
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
# 球員資料
# =========================
player_db = [
    "謝政達","張簡榮力","翁德全","趙振明","洪忠宜","陳振孝","黃國峯","巫吉生",
    "張豪原","陳威宇","林政翰","吳建輝","彭國強","陳振元","林佳鋒","鄭振輝",
    "蔡定憲","謝依榮","湯淑蘭","范秀蘭","黃秀琴","林錦義","黃俊昇","來賓(J)"
]

# =========================
# Session
# =========================
if "selected_players" not in st.session_state:
    st.session_state.selected_players = []

# =========================
# Firebase
# =========================
def save_game(game_id, players, scores):
    data = {
        "players": players,
        "scores": {players[i]: scores[i] for i in range(len(players))}
    }
    db.collection("golf_games").document(game_id).set(data)

def load_game(game_id):
    doc = db.collection("golf_games").document(game_id).get()
    if doc.exists:
        return doc.to_dict()
    return None

# =========================
# UI
# =========================
st.set_page_config(page_title="Golf System", layout="centered")

st.title("⛳ Golf 即時比分系統")

mode = st.radio("模式", ["主控端", "查看端"])
game_id = st.text_input("Game ID", "game001")

# =========================
# 主控端
# =========================
if mode == "主控端":

    st.subheader("👥 選擇球員（最多20人）")

    cols = st.columns(4)

    for i, player in enumerate(player_db):
        col = cols[i % 4]

        if player in st.session_state.selected_players:
            if col.button(f"✅ {player}", key=player):
                st.session_state.selected_players.remove(player)
        else:
            if col.button(player, key=player):
                if len(st.session_state.selected_players) < 20:
                    st.session_state.selected_players.append(player)
                else:
                    st.warning("最多20位球員")

    if st.button("🔄 清除選擇"):
        st.session_state.selected_players = []

    players = st.session_state.selected_players

    st.subheader("📋 已選球員")
    if players:
        st.write("、".join(players))
    else:
        st.info("尚未選擇")

    # =========================
    # 兩人併列輸入
    # =========================
    if players:

        st.subheader("📱 輸入成績（連續18洞）")

        scores = []
        temp_scores = {}

        for i in range(0, len(players), 2):

            cols = st.columns(2)

            for j in range(2):
                if i + j < len(players):
                    p = players[i + j]

                    with cols[j]:
                        st.markdown(f"### ⛳ {p}")

                        txt = st.text_input(
                            f"{p}",
                            key=f"input_{p}",
                            placeholder="455465445544654554"
                        )

                        nums = [int(x) for x in txt if x.isdigit() and 1 <= int(x) <= 12]
                        nums = nums[:18]

                        # 小型分格（簡化版）
                        cols2 = st.columns(6)
                        for h in range(18):
                            col = cols2[h % 6]
                            if h < len(nums):
                                col.markdown(f"**{nums[h]}**")
                            else:
                                col.markdown("-")

                        if len(nums) == 18:
                            temp_scores[p] = nums
                            st.success("完成")
                        elif len(nums) > 0:
                            st.warning(f"{len(nums)}/18")

            st.divider()

        # =========================
        # 合併總表（重點）
        # =========================
        if len(temp_scores) == len(players):

            st.subheader("📊 成績總表")

            df = pd.DataFrame(temp_scores).T
            df.columns = [f"H{h}" for h in range(1, 19)]
            df["Total"] = df.sum(axis=1)

            df = df.sort_values("Total")

            st.dataframe(df, use_container_width=True)

            if st.button("💾 儲存比賽"):
                scores = [temp_scores[p] for p in players]
                save_game(game_id, players, scores)
                st.success("已儲存")

# =========================
# 查看端
# =========================
if mode == "查看端":

    data = load_game(game_id)

    if data:
        st.subheader("📊 即時比分")

        df = pd.DataFrame(data["scores"]).T
        df.columns = [f"H{h}" for h in range(1, len(df.columns)+1)]
        df["Total"] = df.sum(axis=1)

        df = df.sort_values("Total")

        st.dataframe(df, use_container_width=True)

    else:
        st.warning("查無資料")
