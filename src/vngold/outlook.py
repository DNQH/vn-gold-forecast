"""Triển vọng dài hạn (3 và 5 tháng): KHOẢNG GIÁ có thể xảy ra, không dự đoán chiều.

Vì sao không dự đoán chiều? Ở kỳ hạn 7 và 30 ngày, các mô hình đã không vượt được
dự báo Naive (xem reports/02_model_evaluation.md), và tỷ lệ tăng sau 3–5 tháng thay đổi
rất mạnh theo từng năm (2025: gần 100% tăng, 2026: phần lớn giảm). Đưa ra "xác suất tăng"
ở các kỳ hạn này sẽ là thông tin giả. Thay vào đó ta công bố một khoảng giá trung thực.

Phương pháp (đối xứng, không giả định xu hướng, không dùng thông tin tương lai):
  1. sigma_t = độ lệch chuẩn lợi suất ngày của giá trong nước, 126 phiên gần nhất
     (chỉ những ngày có giá niêm yết thật).
  2. Điểm chuẩn hoá s = |log(P_{t+h}/P_t)| / (sigma_t * sqrt(h)), chỉ lấy các điểm ĐÃ ĐÁO HẠN
     tại thời điểm t (tức là đã biết P_{t+h}).
  3. q_t = phân vị `level` của các điểm s đã biết (cửa sổ mở rộng) -> khoảng
     [P_t * exp(-q_t sigma_t sqrt(h)), P_t * exp(+q_t sigma_t sqrt(h))].
Cách này tự nới rộng khi thị trường từng có xu hướng mạnh (sai số dài hạn lớn hơn
mô hình bước ngẫu nhiên thuần). Độ phủ thực tế được kiểm định walk-forward và báo cáo kèm.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from vngold.config import LOCK_DATE

OUTLOOK_HORIZONS = {63: "3 tháng", 105: "5 tháng"}
VOL_WINDOW = 126
MIN_SCORES = 120
EVAL_FROM = "2019-01-01"


def _series(df: pd.DataFrame, target: str):
    obs = df[f"{target}_observed"] == 1 if f"{target}_observed" in df else df[target].notna()
    lp = np.log(df[target].where(obs)).ffill()
    r1 = lp.diff().where(obs & obs.shift(1, fill_value=False))
    sig = r1.rolling(VOL_WINDOW, min_periods=VOL_WINDOW // 2).std()
    return lp, sig


def outlook_bands(df: pd.DataFrame, target: str, h: int, level: float = 0.8) -> pd.DataFrame:
    """Khoảng log-return [lo, hi] cho từng ngày t (chỉ dùng thông tin có tại t) + thực tế."""
    lp, sig = _series(df, target)
    unit = sig * np.sqrt(h)
    fwd = lp.shift(-h) - lp
    known = (fwd / unit).abs().shift(h)          # điểm của dự báo lập tại t-h, đáo hạn tại t
    q = known.expanding(MIN_SCORES).quantile(level)
    return pd.DataFrame({"lo": -q * unit, "hi": q * unit, "actual": fwd, "logp": lp})


def long_horizon_outlook(df: pd.DataFrame, target: str, level: float = 0.8) -> dict:
    out = {}
    for h, label in OUTLOOK_HORIZONS.items():
        b = outlook_bands(df, target, h, level)
        last = b.dropna(subset=["lo", "hi", "logp"]).iloc[-1]
        p0 = float(np.exp(last.logp))
        m = b.actual.notna() & b.lo.notna() & (b.index >= EVAL_FROM)
        inside = (b.actual >= b.lo) & (b.actual <= b.hi)
        lk = m & (b.index > LOCK_DATE)
        up = (b.actual[m] > 0)
        out[str(h)] = {
            "label": label, "h": h,
            "target_date": f"{b.index[-1] + pd.offsets.BDay(h):%Y-%m-%d}",
            "price_now": p0,
            "lo": p0 * float(np.exp(last.lo)), "hi": p0 * float(np.exp(last.hi)),
            "lo_pct": (float(np.exp(last.lo)) - 1) * 100, "hi_pct": (float(np.exp(last.hi)) - 1) * 100,
            "level": level,
            "coverage": float(inside[m].mean()) if m.any() else None,
            "coverage_locked": float(inside[lk].mean()) if lk.any() else None,
            "n_eval": int(m.sum()), "n_locked": int(lk.sum()),
            "hist_up_share": float(up.mean()) if len(up) else None,
            "hist_up_by_year": {int(y): float(v) for y, v in up.groupby(up.index.year).mean().items()},
        }
    return out
