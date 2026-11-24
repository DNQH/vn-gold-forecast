"""Cấu hình chung cho dự án Vietnam Gold Price Intelligence System."""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"
MODELS_DIR = ROOT / "models"

for _p in (DATA_RAW, DATA_PROCESSED, REPORTS, FIGURES, MODELS_DIR):
    _p.mkdir(parents=True, exist_ok=True)

START_DATE = "2017-01-01"

# 1 lượng = 37.5 gram, 1 troy ounce = 31.1035 gram
OZ_PER_LUONG = 37.5 / 31.1035

# ---------------------------------------------------------------- Nhóm 1 + 2
# Yahoo Finance tickers (đóng cửa phiên Mỹ)
YAHOO_TICKERS = {
    "GC=F": "xau_usd",        # Gold futures (proxy cho XAU/USD giao ngay)
    "DX-Y.NYB": "dxy",        # US Dollar Index
    "^TNX": "us10y",          # Lợi suất trái phiếu Mỹ 10 năm (%)
    "VND=X": "usd_vnd",       # Tỷ giá USD/VND
    "SI=F": "silver_usd",     # Bạc - tài sản liên quan
    "^VIX": "vix",            # Chỉ số sợ hãi - proxy tâm lý rủi ro
}

# FRED series: (tên cột, độ trễ công bố tính theo ngày lịch kể từ ngày quan sát)
# Daily series: dữ liệu ngày t thường có vào cuối ngày t (giờ Mỹ) => trễ 1 ngày.
# Monthly series: FRED đánh dấu ngày đầu tháng tham chiếu; CPI công bố khoảng
# ngày 10-15 tháng sau, UNRATE công bố thứ Sáu đầu tiên tháng sau.
# Dùng độ trễ bảo thủ để tránh data leakage.
FRED_SERIES = {
    "DFII10": ("real_rate_10y", 1),    # Lãi suất thực 10Y (TIPS)
    "DFF": ("fed_funds", 1),           # Federal Funds Effective Rate
    "T10YIE": ("breakeven_10y", 1),    # Kỳ vọng lạm phát 10Y
    "CPIAUCSL": ("cpi_us", 47),        # CPI Mỹ (tháng) - ~1 tháng + 16 ngày
    "UNRATE": ("unemployment_us", 40), # Thất nghiệp Mỹ (tháng)
}

# ---------------------------------------------------------------- Dự báo
# Lưới thời gian = ngày làm việc (T2-T6). Kỳ hạn tính theo số phiên.
HORIZONS = {1: "1 ngày", 5: "7 ngày", 21: "30 ngày"}
TARGET = "sjc_sell"           # biến mục tiêu chính
SECONDARY_TARGETS = ["ring_sell"]

# Thời điểm phát hành dự báo:
#  "morning": ~6h-8h sáng giờ VN, sau khi phiên Mỹ đêm trước đóng cửa và TRƯỚC khi
#             doanh nghiệp niêm yết giá trong ngày -> dùng giá thế giới phiên Mỹ ngày t
#             cho hàng t (dự báo giá chốt ngày t+1).
#  "evening": cuối ngày VN -> chỉ dùng phiên Mỹ ngày t-1 (khắt khe hơn).
ISSUE_TIME = "morning"
WORLD_LAG_DAYS = {"morning": 0, "evening": 1}

# Walk-forward
MIN_TRAIN = 500               # số phiên tối thiểu trước khi bắt đầu dự báo
RETRAIN_EVERY = 21            # huấn luyện lại sau mỗi ~1 tháng
RANDOM_STATE = 42

# Giai đoạn "khoá": cấu hình mô hình & lớp tự học được chốt dựa trên dữ liệu tới LOCK_DATE.
# Kết quả sau mốc này là kiểm định chưa từng dùng để chỉnh tham số (gần với thực tế nhất).
LOCK_DATE = "2025-11-30"

# Thử nghiệm (nhánh experiment/accuracy, reports/03_accuracy_experiments.md): thêm mô hình hiệu chỉnh
# sai số (ECM, vngold/ecm.py) làm một thành viên của ensemble tự học. BẬT từ 24/11/2026.
# Tắt: đặt biến môi trường VNGOLD_USE_ECM=0 (hoặc "false"/"off") khi chạy pipeline.
USE_ECM = os.environ.get("VNGOLD_USE_ECM", "1").strip().lower() not in ("0", "false", "off", "no", "")
# Cấu hình đã chốt trên giai đoạn DEV (<= LOCK_DATE): premium trượt 60 phiên, giá thế giới USD,
# OLS trọng số half-life 500 phiên. Kỳ hạn > 1 dùng bộ biến dài hạn.
ECM_PARAMS = {"prem_window": 60, "world": "usd", "halflife": 500}
ECM_COLS_H1 = ("ec", "dw0", "dw1", "dp0", "dp1")
ECM_COLS_LONG = ("ec", "ec120", "dw0", "dw5", "dw21")

# Chỉ công bố dự báo điểm khác Naive khi backtest cho thấy có lợi thế
EDGE_MAX_THEILU = 1.0
EDGE_MAX_DM_P = 0.10

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130 Safari/537.36"
    )
}


# ---------------------------------------------------------------- Thời gian VN
VN_TZ = "Asia/Ho_Chi_Minh"


def vn_now() -> pd.Timestamp:
    """Giờ VN hiện tại (naive). Env VNGOLD_NOW='YYYY-MM-DD HH:MM' dùng để kiểm thử."""
    env = os.environ.get("VNGOLD_NOW")
    if env:
        return pd.Timestamp(env)
    return pd.Timestamp.now(tz=VN_TZ).tz_localize(None)


def vn_today() -> pd.Timestamp:
    """Ngày hiện tại theo giờ VN (00:00)."""
    return vn_now().normalize()
