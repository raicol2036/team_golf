import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="Golf System", layout="centered")
st.title("🔥 Golf 容錯最強版")

# =========================
# 球員
# =========================
players_db = [
    "謝政達","張簡榮力","翁德全","趙振明","洪忠宜",
    "張豪原","陳振孝","林政翰","吳建輝","黃國峯"
]

if "players" not in st.session_state:
    st.session_state.players = []

# =========================
# 選人
# =========================
st.subheader("👥 選人")

cols = st.columns(4)
for i,p in enumerate(players_db):
    col = cols[i%4]

    if p in st.session_state.players:
        if col.button(f"✅ {p}", key=p):
            st.session_state.players.remove(p)
    else:
        if col.button(p, key=p):
            st.session_state.players.append(p)

players = st.session_state.players
st.write("已選：", "、".join(players))

# =========================
# 🔥 超強解析函數
# =========================
def parse_scores(text):

    if not text:
        return []

    # 抓所有數字（支援空白/逗號/換行）
    nums = re.findall(r"\d+", text)

    nums = [int(n) for n in nums]

    # 🔥 攤平成單字元（防 10 11）
    flat = []
    for n in nums:
        if n >= 10:
            flat.extend([int(x) for x in str(n)])
        else:
            flat.append(n)

    # 🔥 保留合理桿數（1~12）
    flat = [x for x in flat if 1 <= x <= 12]

    # 🔥 補滿18
    if len(flat) < 18:
        flat += [0] * (18 - len(flat))

    return flat[:18]

# =========================
# 輸入
# =========================
scores = {}

if players:

    st.subheader("📱 輸入（隨便貼🔥）")

    for i in range(0, len(players), 2):

        cols = st.columns(2)

        for j in range(2):
            if i+j < len(players):
                p = players[i+j]

                with cols[j]:

                    col1,col2 = st.columns([3,1])

                    with col1:
                        st.markdown(f"### ⛳ {p}")

                    txt = st.text_input("輸入18洞", key=f"in_{p}")

                    nums = parse_scores(txt)

                    valid_count = len([x for x in nums if x != 0])

                    with col2:
                        if valid_count >= 18:
                            st.success("完成")
                        else:
                            st.info(f"{valid_count}/18")

                    # 👉 不顯示分格（你要求）
                    if valid_count > 0:
                        scores[p] = nums

        st.divider()

# =========================
# 🏆 結果（永遠顯示🔥）
# =========================
if len(scores) >= 2:

    st.subheader("🏆 比賽結果")

    df = pd.DataFrame(scores).T
    df.columns = [f"H{i}" for i in range(1,19)]

    df["Total"] = df.sum(axis=1)

    df = df.sort_values("Total")

    # 名次
    df["Rank"] = ""

    ranks = ["🥇","🥈","🥉"]

    for i,p in enumerate(df.index):
        if i < 3:
            df.loc[p,"Rank"] = ranks[i]

    st.dataframe(df, use_container_width=True)

    # =========================
    # 🏁 總表
    # =========================
    st.subheader("🏁 總表")

    st.write(f"🥇 冠軍：{df.index[0]}（{df.iloc[0]['Total']}桿）")
    st.write(f"🥈 亞軍：{df.index[1]}（{df.iloc[1]['Total']}桿）")
    st.write(f"🥉 季軍：{df.index[2]}（{df.iloc[2]['Total']}桿）")
