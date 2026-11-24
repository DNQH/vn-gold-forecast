"""Thành phần dùng chung cho 2 phiên bản giao diện: tải dữ liệu, định dạng số kiểu Việt Nam, CSS."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
PROC = ROOT / "data" / "processed"

from vngold.config import VN_TZ, vn_now  # noqa: E402,F401
from vngold.plain import (BUCKETS, BUCKET_NAMES, RUN_HOUR_MIN, bucket_hit_rate, bucket_of,  # noqa: E402,F401
                          calibration_table, freshness, prev_bday, vn)

# Bảng màu thống nhất
INK, MUTED, LINE = "#1f2937", "#6b7280", "#e5e7eb"
UP, DOWN, FLAT = "#15803d", "#b91c1c", "#6b7280"
GOLD, NAVY, BLUE = "#b7791f", "#1e3a5f", "#2563eb"
TARGET_SHORT = {"sjc_sell": "Vàng miếng SJC", "ring_sell": "Vàng nhẫn 9999 (PNJ)"}
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
    today = pd.Timestamp(today if today is not None else vn_now()).normalize()  # giờ VN, không theo máy chủ
    d = (t - today).days
    if d == 0:
        return "Cuối ngày hôm nay"
    if d == 1:
        return "Ngày mai"
    return f"{WEEKDAYS[t.weekday()]} {t:%d/%m}"


# độ mới của dữ liệu: freshness()/vn_now() nằm ở vngold.plain / vngold.config (dùng chung với PWA)


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
