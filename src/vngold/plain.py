"""Thành phần thuần (không cần Streamlit) dùng chung cho giao diện Dễ hiểu (Streamlit) và ứng dụng điện thoại (PWA)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from vngold.config import DATA_PROCESSED

BUCKETS = [0, 0.3, 0.45, 0.55, 0.7, 1.0001]
BUCKET_NAMES = ["strong_down", "lean_down", "unclear", "lean_up", "strong_up"]


def bucket_of(p: float) -> str:
    return pd.cut([p], BUCKETS, labels=BUCKET_NAMES, include_lowest=True)[0]


def vn(v, d: int = 1) -> str:
    """134.25 -> '134,3' ; 1234.5 -> '1.234,5' (dấu thập phân kiểu Việt Nam)."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "–"
    s = f"{v:,.{d}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def calibration_table(target: str, h: int, proc_dir=DATA_PROCESSED) -> pd.DataFrame:
    """Khi phần mềm nói P(tăng) ở mức X, giá tăng thật bao nhiêu lần? (walk-forward)."""
    f = proc_dir / f"backtest_{target}_h{h}.csv"
    if not f.exists():
        return pd.DataFrame()
    wf = pd.read_csv(f, index_col=0, parse_dates=True)
    w = wf[wf.p_up.notna() & wf.actual.notna() & (wf.actual != 0)]
    bucket = pd.cut(w.p_up, BUCKETS, labels=BUCKET_NAMES, include_lowest=True)
    up = w.actual > 0
    return pd.DataFrame({"n": up.groupby(bucket, observed=False).size(),
                         "up": up.groupby(bucket, observed=False).mean()})


def plain_reason(f: str, v, c: float) -> str | None:
    if v is None:
        v = 0.0
    pct = abs(np.expm1(v)) * 100 if abs(v) < 1 else abs(v)
    up = v > 0
    if f.startswith("xau_ret_"):
        span = {"1d": "đêm qua", "2d": "2 ngày qua", "5d": "tuần qua", "10d": "2 tuần qua", "21d": "tháng qua",
                "63d": "3 tháng qua"}.get(f.split("_")[-1], "gần đây")
        return f"Giá vàng thế giới {span} {'tăng' if up else 'giảm'} {vn(pct)}%"
    if f.startswith("passthrough_gap"):
        return ("Giá thế giới tăng nhanh hơn giá trong nước – giá trong nước có thể tăng theo" if up else
                "Giá thế giới giảm mạnh hơn giá trong nước – giá trong nước có thể giảm theo")
    if f.startswith("premium_chg"):
        return ("Giá trong nước đang cao hơn giá thế giới nhiều hơn trước" if up else
                "Khoảng cách giữa giá trong nước và thế giới đang thu hẹp")
    if f.startswith("premium"):
        return "Giá trong nước đang cao hơn giá thế giới khá nhiều"
    if f.startswith("usdvnd"):
        return f"Tỷ giá đô la Mỹ ở Việt Nam {'tăng' if up else 'giảm'}"
    if f.startswith("dxy"):
        return f"Đồng đô la Mỹ trên thế giới {'mạnh lên' if up else 'yếu đi'}"
    if f.startswith("ret_") or f.startswith("dom_ret"):
        return f"Giá vàng trong nước mấy ngày qua đã {'tăng' if up else 'giảm'}"
    if f.startswith("vix"):
        return f"Tâm lý lo ngại trên thị trường thế giới {'tăng' if up else 'giảm'}"
    if f.startswith("policy_regime"):
        return "Chính sách quản lý vàng hiện nay (Nghị định 232/2025)"
    if any(k in f for k in ("macd", "rsi", "ma20", "ma50")):
        return "Xu hướng giá vài tuần gần đây"
    if f.startswith("silver") or f == "gold_silver_ratio":
        return "Diễn biến giá bạc thế giới"
    if f.startswith("us10y") or f.startswith("real_rate") or f == "fed_funds":
        return "Lãi suất ở Mỹ"
    return None
