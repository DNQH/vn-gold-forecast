"""Thành phần dùng chung cho 2 phiên bản giao diện: tải dữ liệu, định dạng số kiểu Việt Nam, CSS."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
PROC = ROOT / "data" / "processed"

from vngold.plain import BUCKETS, BUCKET_NAMES, bucket_of, calibration_table, vn  # noqa: E402,F401

# Bảng màu thống nhất
INK, MUTED, LINE = "#1f2937", "#6b7280", "#e5e7eb"
UP, DOWN, FLAT = "#15803d", "#b91c1c", "#6b7280"
GOLD, NAVY, BLUE = "#b7791f", "#1e3a5f", "#2563eb"
TARGET_SHORT = {"sjc_sell": "Vàng miếng SJC", "ring_sell": "Vàng nhẫn 9999"}
WEEKDAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]


@st.cache_data(ttl=600, show_spinner=False)
def load():
    fc = json.loads((PROC / "forecast.json").read_text(encoding="utf-8"))
    df = pd.read_csv(PROC / "dataset.csv", index_col=0, parse_dates=True)
    return fc, df


@st.cache_data(ttl=300, show_spinner=False)
def live_prices() -> dict:
    from vngold.data.collect import fetch_live_prices
    return fetch_live_prices()


@st.cache_data(ttl=300, show_spinner=False)
def tracking(target: str, h: int, lock, live):
    from vngold.tracking import historical_tracking, tracking_summary
    tr = historical_tracking(target, h, lock, live)
    return tr, tracking_summary(tr)


@st.cache_data(ttl=600, show_spinner=False)
def outlook(target: str) -> dict:
    """Ưu tiên kết quả trong forecast.json; nếu bản cũ chưa có thì tính trực tiếp từ dataset."""
    fc, df = load()
    o = fc["targets"][target].get("outlook")
    if o:
        return o
    from vngold.outlook import long_horizon_outlook
    return long_horizon_outlook(df, target)


@st.cache_data(ttl=600, show_spinner=False)
def calibration(target: str, h: int) -> pd.DataFrame:
    """Khi phần mềm nói P(tăng) ở mức X, giá tăng thật bao nhiêu lần? (walk-forward)."""
    return calibration_table(target, h, PROC)


# ------------------------------------------------------------------ định dạng
def vn_date(ts, weekday: bool = True) -> str:
    ts = pd.Timestamp(ts)
    return f"{WEEKDAYS[ts.weekday()]}, {ts:%d/%m/%Y}" if weekday else f"{ts:%d/%m/%Y}"


def when_label(target_date, today=None) -> str:
    """Nhãn thân thiện cho ngày đích: 'Cuối ngày hôm nay', 'Ngày mai', 'Thứ Sáu 27/11'."""
    t = pd.Timestamp(target_date).normalize()
    today = pd.Timestamp(today or pd.Timestamp.now()).normalize()
    d = (t - today).days
    if d == 0:
        return "Cuối ngày hôm nay"
    if d == 1:
        return "Ngày mai"
    return f"{WEEKDAYS[t.weekday()]} {t:%d/%m}"


# ------------------------------------------------------------------ độ mới của dữ liệu
VN_TZ = "Asia/Ho_Chi_Minh"
RUN_HOUR_MIN = (7, 30)  # pipeline chạy ~07:00 (T3–T7); sau 07:30 mới coi là "đáng lẽ đã có dữ liệu mới"


def vn_now() -> pd.Timestamp:
    """Giờ Việt Nam hiện tại (naive). Biến môi trường VNGOLD_NOW='YYYY-MM-DD HH:MM' dùng để kiểm thử."""
    env = os.environ.get("VNGOLD_NOW")
    if env:
        return pd.Timestamp(env)
    return pd.Timestamp.now(tz=VN_TZ).tz_localize(None)


def _prev_bday(d: pd.Timestamp) -> pd.Timestamp:
    """Ngày làm việc (T2–T6) gần nhất NHỎ HƠN d."""
    return pd.Timestamp(np.busday_offset(d.normalize().date(), -1, roll="backward"))


def freshness(fc: dict, df: pd.DataFrame, now=None) -> dict:
    """Kiểm tra dữ liệu/dự báo có cũ không (hàm thuần; `now` truyền vào để kiểm thử).

    expected = ngày làm việc gần nhất trước hôm nay. Pipeline chỉ chạy T3–T7 lúc ~07:00, nên nếu đang là
    T3–T7 và chưa tới 07:30 thì chưa trách được lần chạy sáng nay -> lùi thêm một ngày làm việc.
    (T2/CN không có lần chạy nào nên không lùi: dữ liệu mới nhất đáng lẽ là thứ Sáu.)
    source_stale[target]: ngày `{target}_observed==1` cuối cùng cách as_of hơn 2 ngày làm việc
    (nguồn giá ngừng cập nhật trong khi pipeline vẫn chạy).
    """
    now = pd.Timestamp(now) if now is not None else vn_now()
    as_of = pd.Timestamp(fc["as_of"]).normalize()
    expected = _prev_bday(now)
    if now.weekday() in (1, 2, 3, 4, 5) and (now.hour, now.minute) < RUN_HOUR_MIN:
        expected = _prev_bday(expected)
    stale = as_of < expected
    days_behind = int(np.busday_count(as_of.date(), expected.date())) if stale else 0
    last_obs, source_stale = {}, {}
    for t in fc.get("targets", {}):
        col = f"{t}_observed"
        if col in df.columns:
            idx = df.index[df[col] == 1]
            if len(idx):
                last = idx.max().normalize()
                last_obs[t] = last
                source_stale[t] = bool(np.busday_count(last.date(), as_of.date()) > 2)
    return {"stale": bool(stale), "days_behind": days_behind, "as_of": as_of, "expected": expected,
            "source_stale": source_stale, "last_observed": last_obs, "now": now}


def ten(x: float) -> int:
    """Tỷ lệ 0–1 -> số lần trên 10 (làm tròn)."""
    return int(round(x * 10))


# ------------------------------------------------------------------ CSS
BASE_CSS = """
<style>
#MainMenu, footer, [data-testid="stStatusWidget"] {visibility: hidden;}
[data-testid="stHeader"] {background: transparent;}
.block-container {padding-top: 3.2rem; padding-bottom: 3rem;}
h1, h2, h3 {letter-spacing: -0.01em;}
[data-testid="stMetric"] {background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 14px 16px;}
[data-testid="stMetricLabel"] p {color: #6b7280; font-size: 0.85rem;}
.vg-muted {color: #6b7280;}
.vg-pill {display:inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.8rem;
          background:#f3f4f6; color:#374151; margin-right:6px;}
</style>
"""


def inject_css(extra: str = "") -> None:
    st.markdown(BASE_CSS + (f"<style>{extra}</style>" if extra else ""), unsafe_allow_html=True)


def plotly_layout(fig, height: int = 380, title: str | None = None, **kw):
    fig.update_layout(
        height=height, title=dict(text=title, x=0, xanchor="left", font=dict(size=15)) if title else None,
        margin=dict(l=8, r=8, t=48 if title else 16, b=8), plot_bgcolor="#ffffff", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Be Vietnam Pro, Inter, system-ui, sans-serif", color=INK, size=13),
        hoverlabel=dict(font_size=13), legend=dict(orientation="h", y=-0.18, x=0), **kw)
    fig.update_xaxes(gridcolor="#f1f2f4", zeroline=False, linecolor=LINE)
    fig.update_yaxes(gridcolor="#f1f2f4", zeroline=False, linecolor=LINE)
    return fig


def chart(fig) -> None:
    """Vẽ biểu đồ Plotly với phong cách thống nhất (giữ nguyên chiều cao/lề của từng biểu đồ)."""
    fig.update_layout(plot_bgcolor="#ffffff", paper_bgcolor="rgba(0,0,0,0)", hoverlabel=dict(font_size=13),
                      font=dict(family="Be Vietnam Pro, Inter, system-ui, sans-serif", color=INK, size=13),
                      title_font=dict(size=15), title_x=0)
    fig.update_xaxes(gridcolor="#f1f2f4", zeroline=False, linecolor=LINE)
    fig.update_yaxes(gridcolor="#f1f2f4", zeroline=False, linecolor=LINE)
    for tr in fig.data:  # dải tô màu: không vẽ điểm ở các đỉnh
        if getattr(tr, "type", "") == "scatter" and tr.mode is None and (
                tr.fill in ("toself", "tonexty") or (tr.line is not None and tr.line.width == 0)):
            tr.mode = "lines"
    if fig.layout.yaxis.title.text and (fig.layout.margin.l or 0) < 64:
        fig.update_layout(margin_l=64)
    st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})
