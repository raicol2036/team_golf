import io
import uuid
from datetime import datetime
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st
import qrcode
from PIL import Image, ImageDraw, ImageFont

# OCR 可選
try:
    import cv2
    import numpy as np
    import pytesseract
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

# Firebase
import firebase_admin
from firebase_admin import credentials, firestore


# =========================
# 基本設定
# =========================
st.set_page_config(page_title="Golf BANK Firebase", layout="centered")

HOLES = [f"H{i}" for i in range(1, 19)]
PAR_DEFAULT = [4, 4, 3, 5, 4, 4, 3, 4, 5, 4, 4, 3, 5, 4, 4, 3, 4, 5]

APP_TITLE = "⛳ Golf BANK Firebase 版"
st.title(APP_TITLE)

st.caption("手機操作 / Firebase 儲存 / QR 分享 / 總桿冠亞軍賽季限制")


# =========================
# Firebase 初始化
# =========================
@st.cache_resource
def init_firebase():
    required_keys = [
        "type",
        "project_id",
        "private_key_id",
        "private_key",
        "client_email",
        "client_id",
        "token_uri",
    ]

    if not all(k in st.secrets["firebase"] for k in required_keys):
        missing = [k for k in required_keys if k not in st.secrets["firebase"]]
        raise RuntimeError(f"Firebase secrets 缺少欄位: {missing}")

    firebase_dict = dict(st.secrets["firebase"])
    firebase_dict["private_key"] = firebase_dict["private_key"].replace("\\n", "\n")

    if not firebase_admin._apps:
        cred = credentials.Certificate(firebase_dict)
        firebase_admin.initialize_app(cred)

    return firestore.client()


db = init_firebase()


# =========================
# Query Params
# =========================
def get_query_params():
    qp = st.query_params
    mode = qp.get("mode", "control")
    game_id = qp.get("game_id", "")
    return mode, game_id


def set_query_params(mode: str, game_id: str):
    st.query_params["mode"] = mode
    st.query_params["game_id"] = game_id


# =========================
# 工具
# =========================
def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def current_season():
    # 你也可以改成自訂賽季，例如 2026-Q1
    return str(datetime.now().year)


def gen_game_id():
    return datetime.now().strftime("%y%m%d_%H%M%S")


def safe_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default


def to_native(obj):
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    return obj


# =========================
# QR code
# =========================
def make_qr_image(url: str) -> Image.Image:
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img


# =========================
# OCR
# =========================
def preprocess_image(pil_img: Image.Image):
    img = np.array(pil_img.convert("RGB"))
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    th = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )
    th = cv2.resize(th, None, fx=2, fy=2)
    return th


def ocr_read(pil_img: Image.Image) -> str:
    processed = preprocess_image(pil_img)
    text = pytesseract.image_to_string(processed, config="--oem 3 --psm 6")
    return text


def parse_score_text(text: str, expected_players=4) -> pd.DataFrame:
    import re

    lines = text.splitlines()
    rows = []

    for line in lines:
        nums = re.findall(r"\d+", line)
        if len(nums) >= 9:
            names = re.findall(r"[A-Za-z\u4e00-\u9fff]+", line)
            name = names[0] if names else f"P{len(rows)+1}"
            scores = [int(x) for x in nums[:18]]
            scores += [0] * (18 - len(scores))
            row = {"姓名": name, "差點": 0}
            for i in range(18):
                row[f"H{i+1}"] = scores[i]
            rows.append(row)

    if not rows:
        rows = [{"姓名": f"P{i+1}", "差點": 0, **{h: 0 for h in HOLES}} for i in range(expected_players)]

    return pd.DataFrame(rows)


# =========================
# Firebase 資料存取
# =========================
def game_ref(game_id: str):
    return db.collection("golf_games").document(game_id)


def season_ref(season_id: str):
    return db.collection("golf_seasons").document(season_id)


def load_game(game_id: str):
    doc = game_ref(game_id).get()
    if doc.exists:
        return doc.to_dict()
    return None


def save_game(game_id: str, payload: dict):
    payload["updated_at"] = now_str()
    game_ref(game_id).set(payload, merge=True)


def load_season_history(season_id: str) -> Dict[str, Dict[str, int]]:
    doc = season_ref(season_id).get()
    if doc.exists:
        data = doc.to_dict() or {}
        return data.get("player_awards", {})
    return {}


def save_season_history(season_id: str, history: Dict[str, Dict[str, int]]):
    season_ref(season_id).set(
        {
            "season_id": season_id,
            "player_awards": history,
            "updated_at": now_str(),
        },
        merge=True,
    )


# =========================
# 成績計算
# =========================
def calc_scores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for h in HOLES:
        df[h] = pd.to_numeric(df[h], errors="coerce").fillna(0).astype(int)

    df["差點"] = pd.to_numeric(df["差點"], errors="coerce").fillna(0).astype(int)
    df["前九"] = df[HOLES[:9]].sum(axis=1)
    df["後九"] = df[HOLES[9:]].sum(axis=1)
    df["總桿"] = df["前九"] + df["後九"]
    df["淨桿"] = df["總桿"] - df["差點"]

    birdies = []
    for _, row in df.iterrows():
        birdie_count = sum(1 for i in range(18) if row[f"H{i+1}"] > 0 and row[f"H{i+1}"] < PAR_DEFAULT[i])
        birdies.append(birdie_count)
    df["Birdie"] = birdies

    # Gross 排名
    df = df.sort_values(["總桿", "淨桿", "姓名"], ascending=[True, True, True]).reset_index(drop=True)
    df["總桿排名"] = range(1, len(df) + 1)

    # Net 排名
    net_rank = df.sort_values(["淨桿", "總桿", "姓名"], ascending=[True, True, True]).copy()
    net_rank["淨桿排名"] = range(1, len(net_rank) + 1)
    df = df.merge(net_rank[["姓名", "淨桿排名"]], on="姓名", how="left")

    return df


# =========================
# 總桿冠亞軍賽季限制
# =========================
def assign_gross_awards_once_per_season(
    result_df: pd.DataFrame,
    history: Dict[str, Dict[str, int]]
) -> Tuple[str, str, Dict[str, Dict[str, int]]]:
    champion = None
    runner = None

    working_history = {k: dict(v) for k, v in history.items()}

    for _, row in result_df.iterrows():
        name = row["姓名"]
        h = working_history.get(name, {"champion": 0, "runner": 0})

        # 冠亞軍都拿過，跳過
        if h.get("champion", 0) >= 1 and h.get("runner", 0) >= 1:
            continue

        # 冠軍只能拿一次
        if champion is None and h.get("champion", 0) == 0:
            champion = name
            working_history.setdefault(name, {"champion": 0, "runner": 0})
            working_history[name]["champion"] += 1
            continue

        # 亞軍只能拿一次；拿過冠軍的人仍可拿一次亞軍
        if runner is None and h.get("runner", 0) == 0 and name != champion:
            runner = name
            working_history.setdefault(name, {"champion": 0, "runner": 0})
            working_history[name]["runner"] += 1

        if champion is not None and runner is not None:
            break

    return champion, runner, working_history


# =========================
# 分享圖
# =========================
def build_summary_text(
    season_id: str,
    game_id: str,
    champion: str,
    runner: str,
    result_df: pd.DataFrame,
    awards: Dict[str, List[str]],
) -> str:
    lines = []
    lines.append("🏆 比賽結果")
    lines.append(f"賽季：{season_id}")
    lines.append(f"場次：{game_id}")
    lines.append("")

    if champion:
        champ_score = int(result_df.loc[result_df["姓名"] == champion, "總桿"].iloc[0])
        lines.append(f"🥇 總桿冠軍 {champion}（{champ_score}）")
    else:
        lines.append("🥇 總桿冠軍：本場無符合資格者")

    if runner:
        runner_score = int(result_df.loc[result_df["姓名"] == runner, "總桿"].iloc[0])
        lines.append(f"🥈 總桿亞軍 {runner}（{runner_score}）")
    else:
        lines.append("🥈 總桿亞軍：本場無符合資格者")

    lines.append("")
    lines.append("📊 淨桿名次")
    net_sorted = result_df.sort_values(["淨桿排名"])
    for _, row in net_sorted.iterrows():
        lines.append(f"{int(row['淨桿排名'])}. {row['姓名']}（淨桿 {int(row['淨桿'])} / 總桿 {int(row['總桿'])}）")

    lines.append("")
    lines.append("🏌️ Birdie 名單")
    birdie_rows = result_df[result_df["Birdie"] > 0]
    if birdie_rows.empty:
        lines.append("無")
    else:
        for _, row in birdie_rows.iterrows():
            lines.append(f"{row['姓名']} × {int(row['Birdie'])}")

    award_titles = {
        "long_drive": "🟠 遠距獎",
        "one_near": "🥇 一近洞",
        "two_near": "🥈 二近洞",
        "three_near": "🥉 三近洞",
        "n_near": "🔵 N近洞",
        "close_award": "❤️ 親密獎",
    }

    for key in ["long_drive", "one_near", "two_near", "three_near", "n_near", "close_award"]:
        lines.append("")
        lines.append(award_titles[key])
        items = awards.get(key, [])
        if not items:
            lines.append("無")
        else:
            for i, name in enumerate(items, start=1):
                lines.append(f"{i}. {name}")

    return "\n".join(lines)


def text_to_image(text: str) -> Image.Image:
    lines = text.split("\n")
    width = 900
    padding = 40
    line_height = 42
    height = padding * 2 + line_height * max(1, len(lines))

    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except Exception:
        font = ImageFont.load_default()

    y = padding
    for line in lines:
        draw.text((40, y), line, fill=(0, 0, 0), font=font)
        y += line_height

    return img


# =========================
# 預設資料
# =========================
def empty_players_df(player_count=4):
    return pd.DataFrame([
        {"姓名": f"P{i+1}", "差點": 0, **{h: 0 for h in HOLES}} for i in range(player_count)
    ])


def award_input_block(title: str, names: List[str], count: int, key_prefix: str) -> List[str]:
    st.markdown(f"### {title}")
    result = []
    for i in range(count):
        name = st.selectbox(
            f"{title} 第{i+1}組",
            options=names,
            key=f"{key_prefix}_{i}",
        )
        result.append(name)
    return result


# =========================
# UI 模式
# =========================
query_mode, query_game_id = get_query_params()

mode = st.radio(
    "模式",
    options=["control", "view"],
    index=0 if query_mode != "view" else 1,
    format_func=lambda x: "主控端" if x == "control" else "查看端",
    horizontal=True,
)

season_id = st.text_input("賽季代號", value=current_season())

if mode == "control":
    st.subheader("主控端設定")

    app_url = st.text_input(
        "App 網址（用來產生 QR / 分享連結）",
        value="https://your-streamlit-app-url.streamlit.app",
        help="部署到 Streamlit Cloud 後改成你的正式網址",
    )

    default_game_id = query_game_id if query_game_id else gen_game_id()
    game_id = st.text_input("比賽代號 game_id", value=default_game_id)

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("建立新比賽", use_container_width=True):
            initial_payload = {
                "game_id": game_id,
                "season_id": season_id,
                "created_at": now_str(),
                "updated_at": now_str(),
                "finalized": False,
                "players": empty_players_df().to_dict(orient="records"),
                "awards": {
                    "long_drive": [],
                    "one_near": [],
                    "two_near": [],
                    "three_near": [],
                    "n_near": [],
                    "close_award": [],
                },
                "champion": "",
                "runner": "",
                "share_text": "",
            }
            save_game(game_id, initial_payload)
            set_query_params("control", game_id)
            st.success(f"已建立比賽：{game_id}")

    with col_b:
        if st.button("讀取比賽", use_container_width=True):
            set_query_params("control", game_id)
            st.rerun()

    game = load_game(game_id)
    if not game:
        st.info("請先建立或讀取比賽。")
        st.stop()

    view_url = f"{app_url}?mode=view&game_id={game_id}"
    qr_img = make_qr_image(view_url)
    st.image(qr_img, caption="查看端 QR Code", use_container_width=False)
    st.code(view_url)

    st.subheader("成績輸入")

    uploaded = st.file_uploader("上傳記分卡照片（可選）", type=["jpg", "jpeg", "png"])
    base_df = pd.DataFrame(game.get("players", []))
    if base_df.empty:
        base_df = empty_players_df()

    if uploaded and OCR_AVAILABLE:
        try:
            pil_img = Image.open(uploaded)
            st.image(pil_img, caption="上傳照片", use_container_width=True)
            text = ocr_read(pil_img)
            with st.expander("OCR 結果"):
                st.text(text)
            base_df = parse_score_text(text, expected_players=max(4, len(base_df)))
            st.info("已由照片辨識帶入，可再手動修正。")
        except Exception as e:
            st.warning(f"OCR 失敗，改用目前資料。{e}")
    elif uploaded and not OCR_AVAILABLE:
        st.warning("目前環境未安裝 OCR 套件，這次請手動輸入。")

    editable_rows = []
    for i in range(len(base_df)):
        player_name = str(base_df.loc[i, "姓名"]) if "姓名" in base_df.columns else f"P{i+1}"
        with st.expander(f"👤 {player_name}", expanded=(i == 0)):
            name = st.text_input("姓名", value=player_name, key=f"name_{i}")
            handicap = st.number_input(
                "差點",
                min_value=0,
                max_value=54,
                value=safe_int(base_df.loc[i, "差點"]) if "差點" in base_df.columns else 0,
                key=f"hcp_{i}"
            )

            scores = {}
            cols = st.columns(3)
            for h in range(18):
                with cols[h % 3]:
                    hole_key = f"H{h+1}"
                    default_val = safe_int(base_df.loc[i, hole_key]) if hole_key in base_df.columns else 0
                    scores[hole_key] = st.number_input(
                        f"{h+1}",
                        min_value=0,
                        max_value=15,
                        value=default_val,
                        key=f"score_{i}_{h+1}",
                    )

            row = {"姓名": name, "差點": handicap}
            row.update(scores)
            editable_rows.append(row)

    df_input = pd.DataFrame(editable_rows)

    st.subheader("獎項設定")
    player_names = df_input["姓名"].tolist()

    awards = {
        "long_drive": award_input_block("🟠 遠距獎", player_names, 2, "ld"),
        "one_near": award_input_block("🥇 一近洞", player_names, 2, "one"),
        "two_near": award_input_block("🥈 二近洞", player_names, 2, "two"),
        "three_near": award_input_block("🥉 三近洞", player_names, 2, "three"),
        "n_near": award_input_block("🔵 N近洞", player_names, 10, "nnear"),
        "close_award": award_input_block("❤️ 親密獎", player_names, 2, "close"),
    }

    col1, col2 = st.columns(2)

    with col1:
        if st.button("先儲存資料", use_container_width=True):
            save_game(
                game_id,
                {
                    "game_id": game_id,
                    "season_id": season_id,
                    "players": df_input.to_dict(orient="records"),
                    "awards": awards,
                    "finalized": game.get("finalized", False),
                },
            )
            st.success("已儲存到 Firebase。")

    with col2:
        if st.button("計算並完賽", use_container_width=True):
            result_df = calc_scores(df_input)

            already_finalized = game.get("finalized", False)
            champion = game.get("champion", "")
            runner = game.get("runner", "")

            if not already_finalized:
                season_history = load_season_history(season_id)
                champion, runner, updated_history = assign_gross_awards_once_per_season(
                    result_df, season_history
                )
                save_season_history(season_id, updated_history)
            else:
                st.info("本場已完賽，沿用既有冠亞軍結果，不重複發獎。")

            share_text = build_summary_text(
                season_id=season_id,
                game_id=game_id,
                champion=champion,
                runner=runner,
                result_df=result_df,
                awards=awards,
            )

            save_game(
                game_id,
                {
                    "game_id": game_id,
                    "season_id": season_id,
                    "players": df_input.to_dict(orient="records"),
                    "result": result_df.to_dict(orient="records"),
                    "awards": awards,
                    "champion": champion,
                    "runner": runner,
                    "share_text": share_text,
                    "finalized": True,
                    "view_url": view_url,
                },
            )
            st.success("已計算並寫入 Firebase。")
            st.rerun()

    # 顯示當前結果
    refreshed_game = load_game(game_id)
    if refreshed_game and refreshed_game.get("result"):
        st.subheader("目前結果")
        result_df = pd.DataFrame(refreshed_game["result"])
        champion = refreshed_game.get("champion", "")
        runner = refreshed_game.get("runner", "")
        share_text = refreshed_game.get("share_text", "")
        awards = refreshed_game.get("awards", awards)

        c1, c2 = st.columns(2)
        with c1:
            if champion:
                st.success(f"🥇 總桿冠軍：{champion}")
            else:
                st.warning("🥇 本場無符合資格者")
        with c2:
            if runner:
                st.info(f"🥈 總桿亞軍：{runner}")
            else:
                st.warning("🥈 本場無符合資格者")

        st.dataframe(result_df, use_container_width=True, hide_index=True)

        st.markdown("### Birdie 名單")
        birdie_df = result_df[result_df["Birdie"] > 0]
        if birdie_df.empty:
            st.write("無")
        else:
            for _, row in birdie_df.iterrows():
                st.write(f"{row['姓名']}：{int(row['Birdie'])} 顆")

        st.markdown("### 分享圖")
        summary_img = text_to_image(share_text)
        st.image(summary_img, use_container_width=True)

        buf = io.BytesIO()
        summary_img.save(buf, format="PNG")
        st.download_button(
            "下載分享圖",
            data=buf.getvalue(),
            file_name=f"{game_id}_result.png",
            mime="image/png",
            use_container_width=True,
        )

        with st.expander("查看分享文字"):
            st.text(share_text)

    st.divider()

    st.subheader("賽季管理")
    if st.button("重置本賽季冠亞軍紀錄", use_container_width=True):
        save_season_history(season_id, {})
        st.success(f"已清空賽季 {season_id} 的冠亞軍紀錄。")

else:
    st.subheader("查看端")

    game_id = st.text_input("輸入 game_id", value=query_game_id)
    if st.button("讀取比賽", use_container_width=True):
        set_query_params("view", game_id)
        st.rerun()

    if not game_id:
        st.info("請輸入 game_id 或直接掃 QR。")
        st.stop()

    game = load_game(game_id)
    if not game:
        st.error("找不到這場比賽資料。")
        st.stop()

    st.write(f"比賽代號：{game.get('game_id', '')}")
    st.write(f"賽季：{game.get('season_id', '')}")
    st.write(f"更新時間：{game.get('updated_at', '')}")

    champion = game.get("champion", "")
    runner = game.get("runner", "")
    result = game.get("result", [])
    awards = game.get("awards", {})
    share_text = game.get("share_text", "")

    c1, c2 = st.columns(2)
    with c1:
        if champion:
            st.success(f"🥇 總桿冠軍：{champion}")
        else:
            st.warning("🥇 尚未產生或無符合資格者")
    with c2:
        if runner:
            st.info(f"🥈 總桿亞軍：{runner}")
        else:
            st.warning("🥈 尚未產生或無符合資格者")

    if result:
        result_df = pd.DataFrame(result)
        st.dataframe(result_df, use_container_width=True, hide_index=True)

        st.markdown("### Birdie 名單")
        birdie_df = result_df[result_df["Birdie"] > 0]
        if birdie_df.empty:
            st.write("無")
        else:
            for _, row in birdie_df.iterrows():
                st.write(f"{row['姓名']}：{int(row['Birdie'])} 顆")
    else:
        st.info("主控端尚未計算完賽。")

    st.markdown("### 獎項")
    show_names = {
        "long_drive": "🟠 遠距獎",
        "one_near": "🥇 一近洞",
        "two_near": "🥈 二近洞",
        "three_near": "🥉 三近洞",
        "n_near": "🔵 N近洞",
        "close_award": "❤️ 親密獎",
    }

    for key in ["long_drive", "one_near", "two_near", "three_near", "n_near", "close_award"]:
        st.markdown(f"**{show_names[key]}**")
        items = awards.get(key, [])
        if not items:
            st.write("無")
        else:
            for idx, name in enumerate(items, start=1):
                st.write(f"{idx}. {name}")

    if share_text:
        st.markdown("### 分享圖")
        summary_img = text_to_image(share_text)
        st.image(summary_img, use_container_width=True)

        buf = io.BytesIO()
        summary_img.save(buf, format="PNG")
        st.download_button(
            "下載分享圖",
            data=buf.getvalue(),
            file_name=f"{game_id}_result.png",
            mime="image/png",
            use_container_width=True,
        )

    if st.button("重新整理", use_container_width=True):
        st.rerun()
