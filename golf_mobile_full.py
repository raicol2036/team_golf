import streamlit as st
import pandas as pd
import re

# =========================
# Firebase（穩定版）
# =========================
import firebase_admin
from firebase_admin import credentials, firestore

@st.cache_resource
def init_firebase():
    try:
        if not firebase_admin._apps:
            cfg = dict(st.secrets["firebase"])
            cfg["private_key"] = cfg["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(cfg)
            firebase_admin.initialize_app(cred)
        return firestore.client()
    except:
        return None

db = init_firebase()

# =========================
# 頁面
# =========================
st.set_page_config(page_title="Golf System", layout="centered")
st.title("🔥 Golf 聯賽系統（最終版）")

# =========================
# 球員
# =========================
player_db = [
    "謝政達","張簡榮力","翁德全","趙振明","洪忠宜","陳振孝",
    "黃國峯","巫吉生","張豪原","陳威宇","林政翰","吳建輝",
    "彭國強","陳振元","林佳鋒","鄭振輝","蔡定憲","謝依榮",
    "湯淑蘭","范秀蘭"
]

if "players" not in st.session_state:
    st.session_state.players = []

# =========================
# 選人
# =========================
st.subheader("👥 選擇球員")

cols = st.columns(4)
for i,p in enumerate(player_db):
    col = cols[i%4]

    if p in st.session_state.players:
        if col.button(f"✅ {p}", key=p):
            st.session_state.players.remove(p)
    else:
        if col.button(p, key=p):
            if len(st.session_state.players) < 20:
                st.session_state.players.append(p)

players = st.session_state.players
st.write("已選：", "、".join(players))

# =========================
# 🔥 容錯解析
# =========================
def parse_scores(text):
    nums = re.findall(r"\d+", text)
    nums = [int(n) for n in nums]

    flat = []
    for n in nums:
        if n >= 10:
            flat.extend([int(x) for x in str(n)])
        else:
            flat.append(n)

    flat = [x for x in flat if 1 <= x <= 12]

    if len(flat) < 18:
        flat += [0]*(18-len(flat))

    return flat[:18]

# =========================
# Firebase 差點
# =========================
def get_hcp(p):
    if db is None:
        return 36
    doc = db.collection("season_hcp").document(p).get()
    if doc.exists:
        return doc.to_dict().get("hcp",36)
    return 36

def update_hcp(p, delta):
    if db is None:
        return
    h = get_hcp(p)
    new_h = max(0, h + delta)
    db.collection("season_hcp").document(p).set({"hcp":new_h})

# =========================
# 輸入
# =========================
scores = {}

if players:

    st.subheader("📱 輸入成績（隨便貼🔥）")

    for i in range(0,len(players),2):

        cols = st.columns(2)

        for j in range(2):
            if i+j < len(players):
                p = players[i+j]

                with cols[j]:

                    c1,c2 = st.columns([3,1])

                    with c1:
                        st.markdown(f"### ⛳ {p}")

                    txt = st.text_input("", key=f"in_{p}")

                    nums = parse_scores(txt)

                    valid = len([x for x in nums if x!=0])

                    with c2:
                        if valid >= 18:
                            st.success("完成")
                        else:
                            st.info(f"{valid}/18")

                    if valid > 0:
                        scores[p] = nums

        st.divider()

# =========================
# 結果（穩定顯示🔥）
# =========================
if scores:

    st.subheader("🏆 比賽結果")

    df = pd.DataFrame(scores).T
    df.columns = [f"H{i}" for i in range(1,19)]

    df["Gross"] = df.sum(axis=1)
    gross_rank = df.sort_values("Gross")

    # 防呆（避免人數不足）
    if len(df) < 2:
        st.warning("⚠️ 至少需要2位球員")
        st.stop()

    gross_winners = list(gross_rank.index[:3])

    df["HCP"] = df.index.map(get_hcp)

    net_players = [p for p in df.index if p not in gross_winners]

    if len(net_players) < 2:
        st.warning("⚠️ 淨桿人數不足")
        st.stop()

    net_df = df.loc[net_players].copy()
    net_df["Net"] = net_df["Gross"] - net_df["HCP"]
    net_rank = net_df.sort_values("Net")

    st.dataframe(df, use_container_width=True)

    st.subheader("🏁 總表")

    st.write(f"🥇 {gross_rank.index[0]}（{gross_rank.iloc[0]['Gross']}）")
    st.write(f"🥈 {gross_rank.index[1]}（{gross_rank.iloc[1]['Gross']}）")

    st.write(f"Net🥇 {net_rank.index[0]}（{net_rank.iloc[0]['Net']}）")
    st.write(f"Net🥈 {net_rank.index[1]}（{net_rank.iloc[1]['Net']}）")
    # =========================
    # 總表
    # =========================
    st.subheader("🏁 總表")

    st.markdown("### 🏆 Gross")
    st.write(f"🥇 {gross_rank.index[0]}（{gross_rank.iloc[0]['Gross']}）")
    st.write(f"🥈 {gross_rank.index[1]}（{gross_rank.iloc[1]['Gross']}）")

    st.markdown("### 🏆 Net（排除Gross）")
    st.write(f"🥇 {net_rank.index[0]}（{net_rank.iloc[0]['Net']}）")
    st.write(f"🥈 {net_rank.index[1]}（{net_rank.iloc[1]['Net']}）")

    # =========================
    # 更新差點
    # =========================
    if st.button("💾 更新賽季差點"):

        update_hcp(net_rank.index[0], -2)
        update_hcp(net_rank.index[1], -1)

        st.success("✅ 差點已更新")
