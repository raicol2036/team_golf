import streamlit as st
import pandas as pd

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
# 頁面設定
# =========================
st.set_page_config(page_title="Golf System", layout="centered")
st.title("🔥 Golf 聯賽系統（穩定版）")

# =========================
# 球員資料
# =========================
player_db = [
    "謝政達","張簡榮力","翁德全","趙振明","洪忠宜","陳振孝","黃國峯","巫吉生",
    "張豪原","陳威宇","林政翰","吳建輝","彭國強","陳振元","林佳鋒","鄭振輝",
    "蔡定憲","謝依榮","湯淑蘭","范秀蘭"
]

# =========================
# Session
# =========================
if "players" not in st.session_state:
    st.session_state.players = []

# =========================
# Firebase function
# =========================
def get_record(p):
    if db is None:
        return {"gold":0,"silver":0}
    doc = db.collection("season").document(p).get()
    return doc.to_dict() if doc.exists else {"gold":0,"silver":0}

def update_record(p, rank):
    if db is None:
        return
    ref = db.collection("season").document(p)
    r = get_record(p)
    if rank == "gold":
        r["gold"] += 1
    elif rank == "silver":
        r["silver"] += 1
    ref.set(r)

# =========================
# 👥 選人
# =========================
st.subheader("👥 選擇球員（最多20人）")

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
# 📱 輸入（手機最佳🔥）
# =========================
if players:

    st.subheader("📱 成績輸入（18碼）")

    scores = {}

    for i in range(0,len(players),2):

        cols = st.columns(2)

        for j in range(2):
            if i+j < len(players):
                p = players[i+j]

                with cols[j]:

                    col1,col2 = st.columns([3,1])
                    with col1:
                        st.markdown(f"### ⛳ {p}")

                    txt = st.text_input("", key=f"in_{p}")

                    nums = [int(x) for x in txt if x.isdigit()][:18]

                    done = len(nums)==18

                    with col2:
                        if done:
                            st.success("完成")

                    # 分格顯示
                    gcols = st.columns(6)
                    for k in range(18):
                        c = gcols[k%6]
                        if k < len(nums):
                            c.markdown(f"**{nums[k]}**")
                        else:
                            c.markdown("-")

                    if done:
                        scores[p] = nums

        st.divider()

    # =========================
    # 🏆 排名（聯賽規則🔥）
    # =========================
    if len(scores)==len(players):

        st.subheader("🏆 比賽結果")

        df = pd.DataFrame(scores).T
        df.columns = [f"H{i}" for i in range(1,19)]
        df["Total"] = df.sum(axis=1)

        df = df.sort_values("Total")

        df["Rank"] = ""

        gold = False
        silver = False
        bronze = False

        for p in df.index:

            r = get_record(p)

            # 🥇
            if not gold and r["gold"]==0:
                df.loc[p,"Rank"]="🥇"
                gold=True
                continue

            # 🥈
            if gold and not silver and r["silver"]==0:
                df.loc[p,"Rank"]="🥈"
                silver=True
                continue

            # 🥉（沒拿過）
            if gold and silver and not bronze:
                if r["gold"]==0 and r["silver"]==0:
                    df.loc[p,"Rank"]="🥉"
                    bronze=True

        st.dataframe(df, use_container_width=True)

        # =========================
        # 💾 儲存
        # =========================
        if st.button("💾 儲存結果"):

            for p in df.index:
                if df.loc[p,"Rank"]=="🥇":
                    update_record(p,"gold")
                elif df.loc[p,"Rank"]=="🥈":
                    update_record(p,"silver")

            st.success("✅ 已寫入賽季紀錄")

        # =========================
        # 🏁 總表（穩定）
        # =========================
        st.subheader("🏁 總表")

        st.write(f"🥇 冠軍：{df.index[0]}（{df.iloc[0]['Total']}桿）")
        st.write(f"🥈 亞軍：{df.index[1]}（{df.iloc[1]['Total']}桿）")
        st.write(f"🥉 季軍：{df.index[2]}（{df.iloc[2]['Total']}桿）")
