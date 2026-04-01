# =========================
# 🏆 比賽結果（聯賽淨桿🔥）
# =========================
if len(scores) >= 2:

    st.subheader("🏆 比賽結果（聯賽版）")

    df = pd.DataFrame(scores).T
    df.columns = [f"H{i}" for i in range(1,19)]

    # =========================
    # 🎯 Gross
    # =========================
    df["Gross"] = df.sum(axis=1)
    gross_rank = df.sort_values("Gross")

    gross_winners = list(gross_rank.index[:3])  # 冠亞季

    # =========================
    # 🎯 取得賽季差點（Firebase）
    # =========================
    def get_hcp(p):
        if db is None:
            return 36
        doc = db.collection("season_hcp").document(p).get()
        if doc.exists:
            return doc.to_dict().get("hcp", 36)
        return 36

    def update_hcp(p, change):
        if db is None:
            return
        h = get_hcp(p)
        new_h = max(0, h + change)

        db.collection("season_hcp").document(p).set({
            "hcp": new_h
        })

    df["HCP"] = df.index.map(get_hcp)

    # =========================
    # ❌ 排除 Gross 得獎者
    # =========================
    net_players = [p for p in df.index if p not in gross_winners]

    net_df = df.loc[net_players].copy()

    # =========================
    # 🎯 Net
    # =========================
    net_df["Net"] = net_df["Gross"] - net_df["HCP"]

    net_rank = net_df.sort_values("Net")

    # =========================
    # 🏆 標記
    # =========================
    df["Gross_Rank"] = ""
    df["Net_Rank"] = ""

    medals = ["🥇","🥈","🥉"]

    # Gross
    for i,p in enumerate(gross_rank.index[:3]):
        df.loc[p,"Gross_Rank"] = medals[i]

    # Net（只2名）
    for i,p in enumerate(net_rank.index[:2]):
        df.loc[p,"Net_Rank"] = medals[i]

    # =========================
    # 📊 顯示
    # =========================
    st.dataframe(df, use_container_width=True)

    # =========================
    # 🏁 總表
    # =========================
    st.subheader("🏁 總表")

    st.markdown("### 🏆 Gross")
    st.write(f"🥇 {gross_rank.index[0]}（{gross_rank.iloc[0]['Gross']}桿）")
    st.write(f"🥈 {gross_rank.index[1]}（{gross_rank.iloc[1]['Gross']}桿）")

    st.markdown("### 🏆 Net（排除Gross得獎）")
    st.write(f"🥇 {net_rank.index[0]}（{net_rank.iloc[0]['Net']}）")
    st.write(f"🥈 {net_rank.index[1]}（{net_rank.iloc[1]['Net']}）")

    # =========================
    # 💾 更新賽季差點
    # =========================
    if st.button("💾 更新賽季差點"):

        # 淨桿冠軍 -2
        update_hcp(net_rank.index[0], -2)

        # 淨桿亞軍 -1
        update_hcp(net_rank.index[1], -1)

        st.success("✅ 差點已更新")
