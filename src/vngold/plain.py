"""Thành phần thuần (không cần Streamlit) dùng chung cho giao diện Dễ hiểu (Streamlit) và ứng dụng điện thoại (PWA)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from vngold.config import DATA_PROCESSED, vn_now

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
    """Khi phần mềm nói P(tăng) ở mức X, giá tăng thật bao nhiêu lần? (walk-forward).

    n/up: chỉ tính các phiên giá có thay đổi (dùng cho biểu đồ độ tin cậy của P(tăng)).
    n_all/up_all/down_all: tính MỌI phiên có kết quả, kể cả phiên giá đứng yên – dùng cho câu
    "đúng X/10 lần" trên giao diện Dễ hiểu (nói "tăng" mà giá đứng yên thì không tính là đúng).
    """
    f = proc_dir / f"backtest_{target}_h{h}.csv"
    if not f.exists():
        return pd.DataFrame()
    wf = pd.read_csv(f, index_col=0, parse_dates=True)
    a = wf[wf.p_up.notna() & wf.actual.notna()]
    ball = pd.cut(a.p_up, BUCKETS, labels=BUCKET_NAMES, include_lowest=True)
    w = a[a.actual != 0]
    bucket = ball[w.index]
    up = w.actual > 0
    return pd.DataFrame({"n": up.groupby(bucket, observed=False).size(),
                         "up": up.groupby(bucket, observed=False).mean(),
                         "n_all": a.actual.groupby(ball, observed=False).size(),
                         "up_all": (a.actual > 0).groupby(ball, observed=False).mean(),
                         "down_all": (a.actual < 0).groupby(ball, observed=False).mean()})


def bucket_hit_rate(cal: pd.DataFrame, bucket: str, min_n: int = 20):
    """Tỷ lệ "nói tăng/giảm thì đúng" cho nhóm xác suất `bucket` -> (tỷ lệ, số lần) hoặc None.

    Phiên giá đứng yên được tính là KHÔNG đúng (thận trọng). Nhóm "unclear" không có câu này.
    """
    if not len(cal) or bucket not in cal.index or bucket == "unclear" or "n_all" not in cal.columns:
        return None
    n = int(cal.loc[bucket, "n_all"])
    if n < min_n:
        return None
    rate = cal.loc[bucket, "up_all"] if bucket in ("strong_up", "lean_up") else cal.loc[bucket, "down_all"]
    return float(rate), n


# ------------------------------------------------------------------ độ mới của dữ liệu (dùng chung Streamlit + PWA)
RUN_HOUR_MIN = (7, 30)  # pipeline chạy ~07:00 (T3–T7); sau 07:30 mới coi là "đáng lẽ đã có dữ liệu mới"


def prev_bday(d) -> pd.Timestamp:
    """Ngày làm việc (T2–T6) gần nhất NHỎ HƠN ngày của d (T7/CN/T2 -> thứ Sáu trước đó)."""
    return pd.Timestamp(np.busday_offset(pd.Timestamp(d).normalize().date(), -1, roll="forward"))


def freshness(fc: dict, df: pd.DataFrame, now=None) -> dict:
    """Kiểm tra dữ liệu/dự báo có cũ không (hàm thuần; `now` truyền vào để kiểm thử).

    expected = ngày làm việc gần nhất trước hôm nay (T7, CN, T2 -> thứ Sáu). Pipeline chỉ chạy T3–T7 lúc ~07:00,
    nên nếu đang là T3–T7 và chưa tới 07:30 thì chưa trách được lần chạy sáng nay -> lùi thêm một ngày làm việc.
    source_stale[target]: ngày `{target}_observed==1` cuối cùng cách as_of hơn 2 ngày làm việc
    (nguồn giá ngừng cập nhật trong khi pipeline vẫn chạy).
    Lưu ý: dịp nghỉ dài của thị trường trong nước (Tết…) cũng làm cờ bật – giao diện dùng lời lẽ trung tính.
    """
    now = pd.Timestamp(now) if now is not None else vn_now()
    as_of = pd.Timestamp(fc["as_of"]).normalize()
    expected = prev_bday(now)
    if now.weekday() in (1, 2, 3, 4, 5) and (now.hour, now.minute) < RUN_HOUR_MIN:
        expected = prev_bday(expected)
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


# ------------------------------------------------------------------ lời lẽ chiều tăng/giảm (giống CONF/verdict trong docs/app.js)
WEEKDAYS_VN = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
CONF_LABELS = {"strong": "Nghiêng rõ về {dir}", "lean": "Hơi nghiêng về {dir}", "unclear": "Không rõ ràng"}
NO_EDGE_LABEL = "Khó đoán"


def said_direction(bucket) -> int:
    """Chiều mà giao diện đã nói với nhóm xác suất `bucket`: +1 tăng, -1 giảm, 0 không nói chiều."""
    b = str(bucket)
    return 1 if b in ("strong_up", "lean_up") else -1 if b in ("strong_down", "lean_down") else 0


def direction_label(bucket, has_edge: bool = True) -> str:
    """'Nghiêng rõ về tăng' / 'Hơi nghiêng về giảm' / 'Không rõ ràng'; không có lợi thế -> 'Khó đoán'."""
    if not has_edge or bucket is None:
        return NO_EDGE_LABEL
    d = said_direction(bucket)
    if d == 0:
        return CONF_LABELS["unclear"]
    level = "strong" if str(bucket).startswith("strong") else "lean"
    return CONF_LABELS[level].format(dir="tăng" if d > 0 else "giảm")


def vn_day(d, weekday: bool = True) -> str:
    """Timestamp -> 'Thứ Sáu 27/11' (hoặc '27/11')."""
    d = pd.Timestamp(d)
    return (f"{WEEKDAYS_VN[d.weekday()]} " if weekday else "") + f"{d.day:02d}/{d.month:02d}"
