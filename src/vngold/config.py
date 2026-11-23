"""Cấu hình chung cho dự án Vietnam Gold Price Intelligence System."""
from __future__ import annotations

from pathlib import Path

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

# Chỉ công bố dự báo điểm khác Naive khi backtest cho thấy có lợi thế
EDGE_MAX_THEILU = 1.0
EDGE_MAX_DM_P = 0.10

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130 Safari/537.36"
    )
}
