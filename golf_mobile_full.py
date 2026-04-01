# =========================
# 總表（最終結算🔥）
# =========================
st.subheader("🏁 比賽總表")

# === 基本資料 ===
df = pd.DataFrame(temp_scores).T
df.columns = [f"H{i}" for i in range(1,19)]
df["Gross"] = df.sum(axis=1)

# 👉 假設 handicap（之後可接 CSV）
handicap = {
    p: 10 for p in df.index  # 預設10
}

df["HCP"] = df.index.map(lambda x: handicap.get(x, 10))
df["Net"] = df["Gross"] - df["HCP"]

# =========================
# 🏆 Gross 排名
# =========================
gross_rank = df.sort_values("Gross")

gross_winner = gross_rank.index[0]
gross_second = gross_rank.index[1]

# =========================
# 🏆 Net 排名
# =========================
net_rank = df.sort_values("Net")

net_winner = net_rank.index[0]
net_second = net_rank.index[1]

# =========================
# 🎯 BB（最後一名）
# =========================
bb_player = df.sort_values("Gross", ascending=False).index[0]

# =========================
# 🎯 Birdie（簡單版）
# =========================
# 假設 Par=4
birdie_count = {}

for p in df.index:
    birdie_count[p] = sum([1 for s in temp_scores[p] if s <= 3])

birdie_df = pd.DataFrame({
    "Player": list(birdie_count.keys()),
    "Birdie": list(birdie_count.values())
}).sort_values("Birdie", ascending=False)

birdie_winner = birdie_df.iloc[0]["Player"]

# =========================
# 🎯 顯示總表
# =========================

st.markdown("### 🏆 總桿（Gross）")
st.write(f"冠軍：{gross_winner}  💰 $1200")
st.write(f"亞軍：{gross_second}  💰 $600")

st.markdown("### 🏆 淨桿（Net）")
st.write(f"冠軍：{net_winner}  💰 $1200")
st.write(f"亞軍：{net_second}  💰 $600")

st.markdown("### 🎯 特殊獎項")
st.write(f"Birdie王：{birdie_winner}")
st.write(f"BB（最後）：{bb_player}")

# =========================
# 📊 詳細表
# =========================
st.dataframe(df, use_container_width=True)
