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
# Session 初始化
# =========================
if "selected_players" not in st.session_state:
    st.session_state.selected_players = []

# =========================
# Firebase function
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

st.title("⛳ Golf 即時比分系統（最終版）")

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
    # 輸入分數（連續18洞）
    # =========================
    if players:
        st.subheader("📱 輸入成績（連續18洞）")

        scores = []

        for p in players:
            st.markdown(f"### ⛳ {p}")

            txt = st.text_input(
                f"{p}",
                key=f"input_{p}",
                placeholder="例如：455465445544654554"
            )

            nums = [int(x) for x in txt if x.isdigit() and 1 <= int(x) <= 12]
            nums = nums[:18]

            # 顯示分格
            cols = st.columns(6)
            for h in range(18):
                col = cols[h % 6]
                if h < len(nums):
                    col.metric(label=f"{h+1}", value=nums[h])
                else:
                    col.metric(label=f"{h+1}", value="-")

            # 驗證
            if len(nums) == 18:
                st.success(f"{p} ✅ 完成")
                scores.append(nums)
            elif len(nums) > 0:
                st.warning(f"{p} 已輸入 {len(nums)} / 18")

            st.divider()

        # =========================
        # 顯示結果
        # =========================
        if len(scores) == len(players):

            st.subheader("📊 成績總覽")

            totals = [sum(s) for s in scores]

            result_df = pd.DataFrame({
                "Player": players,
                "Total": totals
            }).sort_values("Total")

            st.dataframe(result_df, use_container_width=True)

            if st.button("💾 儲存比賽"):
                save_game(game_id, players, scores)
                st.success("已儲存")

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

        totals = {p: sum(sc) for p, sc in data["scores"].items()}

        result_df = pd.DataFrame({
            "Player": list(totals.keys()),
            "Total": list(totals.values())
        }).sort_values("Total")

        st.subheader("🏆 排名")
        st.dataframe(result_df, use_container_width=True)

    else:
        st.warning("查無資料")
