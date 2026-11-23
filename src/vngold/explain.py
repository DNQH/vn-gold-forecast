"""Explainable AI - giải thích dự báo XGBoost bằng SHAP.

Lưu ý: SHAP đo *đóng góp của biến vào dự báo của mô hình*, KHÔNG chứng minh
quan hệ nhân quả.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Tên hiển thị tiếng Việt cho các đặc trưng chính
LABELS = {
    "xau_ret_1d": "XAU/USD thay đổi phiên gần nhất",
    "xau_ret_2d": "XAU/USD thay đổi 2 phiên",
    "xau_ret_5d": "XAU/USD thay đổi 5 phiên",
    "xau_ret_10d": "XAU/USD thay đổi 10 phiên",
    "xau_ret_21d": "XAU/USD thay đổi 1 tháng",
    "xau_ret_63d": "XAU/USD thay đổi 3 tháng",
    "passthrough_gap_1d": "Giá TG quy đổi tăng nhanh hơn giá SJC (1 phiên)",
    "passthrough_gap_5d": "Giá TG quy đổi tăng nhanh hơn giá SJC (5 phiên)",
    "passthrough_gap_21d": "Giá TG quy đổi tăng nhanh hơn giá SJC (1 tháng)",
    "premium_pct": "Domestic Gold Premium (%)",
    "premium_chg_1d": "Premium thay đổi 1 phiên",
    "premium_chg_5d": "Premium thay đổi 5 phiên",
    "premium_chg_21d": "Premium thay đổi 1 tháng",
    "premium_z60": "Premium so với trung bình 60 phiên (z-score)",
    "premium_dev120": "Premium lệch trung bình 120 phiên",
    "usdvnd_ret_1d": "USD/VND thay đổi 1 phiên",
    "usdvnd_ret_5d": "USD/VND thay đổi 5 phiên",
    "usdvnd_ret_21d": "USD/VND thay đổi 1 tháng",
    "usdvnd_ret_63d": "USD/VND thay đổi 3 tháng",
    "dxy_ret_1d": "DXY thay đổi 1 phiên",
    "dxy_ret_5d": "DXY thay đổi 5 phiên",
    "dxy_ret_21d": "DXY thay đổi 1 tháng",
    "us10y": "Lợi suất TPCP Mỹ 10 năm",
    "us10y_chg_5d": "Lợi suất 10Y thay đổi 5 phiên",
    "us10y_chg_21d": "Lợi suất 10Y thay đổi 1 tháng",
    "real_rate_10y": "Lãi suất thực 10Y",
    "real_rate_chg_21d": "Lãi suất thực thay đổi 1 tháng",
    "fed_funds": "Lãi suất Fed",
    "cpi_yoy": "CPI Mỹ (YoY)",
    "vix": "VIX (tâm lý sợ hãi)",
    "vix_chg_5d": "VIX thay đổi 5 phiên",
    "gold_silver_ratio": "Tỷ lệ vàng/bạc",
    "silver_ret_5d": "Giá bạc thay đổi 5 phiên",
    "gold_volume_z": "Khối lượng giao dịch vàng (z-score)",
    "xau_rsi14": "RSI(14) vàng thế giới",
    "xau_vol21": "Biến động vàng thế giới 21 phiên",
    "breakeven_10y": "Kỳ vọng lạm phát 10Y",
    "unemployment_us": "Thất nghiệp Mỹ",
    "days_since_change": "Số phiên kể từ lần SJC đổi giá",
    "spread_pct": "Chênh lệch mua-bán SJC",
    "dom_rsi14": "RSI(14) giá SJC",
    "dom_vol7": "Biến động giá SJC 7 phiên",
    "dom_vol21": "Biến động giá SJC 21 phiên",
    "ret_lag1": "Giá SJC thay đổi phiên gần nhất",
    "ret_5d": "Giá SJC thay đổi 5 phiên",
    "ret_21d": "Giá SJC thay đổi 1 tháng",
    "days_to_than_tai": "Số ngày tới vía Thần Tài",
    "policy_regime_1": "Giai đoạn NHNN đấu thầu vàng (2024)",
    "policy_regime_2": "Giai đoạn NHNN bán vàng trực tiếp",
    "policy_regime_3": "Giai đoạn Nghị định 232/2025",
    "ret_lag2": "Giá trong nước thay đổi 2 phiên trước",
    "ret_lag3": "Giá trong nước thay đổi 3 phiên trước",
    "ret_lag4": "Giá trong nước thay đổi 4 phiên trước",
    "ret_lag5": "Giá trong nước thay đổi 5 phiên trước",
    "ret_10d": "Giá trong nước thay đổi 10 phiên",
    "ret_63d": "Giá trong nước thay đổi 3 tháng",
    "dom_macd": "MACD giá trong nước",
    "dom_macd_hist": "MACD histogram giá trong nước",
    "dom_ma20_gap": "Giá trong nước so với MA20",
    "dom_ma50_gap": "Giá trong nước so với MA50",
    "dom_ma20_50": "MA20 so với MA50 (giá trong nước)",
    "dom_bb_pctb": "Vị trí trong dải Bollinger (giá trong nước)",
    "dom_bb_width": "Độ rộng dải Bollinger (giá trong nước)",
    "dom_atr14": "ATR(14) giá trong nước",
    "dom_roc10": "ROC(10) giá trong nước",
    "xau_ret_lag1": "XAU/USD thay đổi phiên trước nữa",
    "xau_macd_hist": "MACD histogram vàng thế giới",
    "xau_ma20_gap": "Vàng thế giới so với MA20",
    "xau_ma50_gap": "Vàng thế giới so với MA50",
    "xau_bb_pctb": "Vị trí trong dải Bollinger (vàng thế giới)",
    "fed_funds_chg_63d": "Lãi suất Fed thay đổi 3 tháng",
    "dow": "Thứ trong tuần",
}


def label(f: str) -> str:
    return LABELS.get(f, f)


def shap_values(xgb_model, X: pd.DataFrame) -> pd.DataFrame:
    """SHAP cho XGBRegressor. Dùng thư viện shap; nếu lỗi tương thích thì dùng
    pred_contribs của XGBoost (cùng thuật toán TreeSHAP)."""
    try:
        import shap
        ex = shap.TreeExplainer(xgb_model)
        vals = ex.shap_values(X)
        base = float(np.atleast_1d(ex.expected_value)[0])
    except Exception:
        import xgboost as xgb
        contrib = xgb_model.get_booster().predict(xgb.DMatrix(X), pred_contribs=True)
        vals, base = contrib[:, :-1], float(contrib[0, -1])
    df = pd.DataFrame(vals, index=X.index, columns=X.columns)
    df.attrs["base_value"] = base
    return df


def explain_row(sv: pd.Series, x: pd.Series, top: int = 8, scale: float = 100.0) -> list[dict]:
    """Top yếu tố đóng góp cho một dự báo (đơn vị: điểm % lợi suất)."""
    order = sv.abs().sort_values(ascending=False).index[:top]
    return [{
        "feature": f, "label": label(f), "value": None if pd.isna(x[f]) else float(x[f]),
        "contribution_pct": float(sv[f]) / scale * 100,   # % lợi suất
        "direction": "Tích cực (đẩy giá lên)" if sv[f] > 0 else "Tiêu cực (kéo giá xuống)",
    } for f in order]


def global_importance(sv: pd.DataFrame, top: int = 15) -> pd.DataFrame:
    imp = sv.abs().mean().sort_values(ascending=False).head(top)
    return pd.DataFrame({"feature": imp.index, "label": [label(f) for f in imp.index],
                         "mean_abs_shap": imp.values})
