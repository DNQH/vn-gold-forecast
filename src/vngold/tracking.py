"""Nhật ký dự báo thực tế + tự chấm điểm khi giá thực tế được công bố.

Mỗi lần chạy:
  1. ghi các dự báo mới vào data/processed/predictions_log.csv
  2. với các dự báo cũ đã tới ngày đích -> điền giá thực tế, sai số, đúng/sai chiều,
     có nằm trong khoảng tin cậy hay không.
Sai số này cũng được đưa vào lớp tự học (online.py) ở lần chạy sau vì walk-forward
luôn được chạy lại tới ngày dữ liệu mới nhất.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from vngold.config import DATA_PROCESSED

LOG = DATA_PROCESSED / "predictions_log.csv"


def append_predictions(rows: list[dict]) -> pd.DataFrame:
    new = pd.DataFrame(rows)
    if LOG.exists():
        old = pd.read_csv(LOG)
        new = pd.concat([old, new], ignore_index=True)
    new = new.drop_duplicates(["target", "as_of", "h", "model"], keep="last")
    new.to_csv(LOG, index=False)
    return new


def score_log(df: pd.DataFrame, target_cols=("sjc_sell", "ring_sell")) -> pd.DataFrame:
    if not LOG.exists():
        return pd.DataFrame()
    log = pd.read_csv(LOG, parse_dates=["as_of", "target_date"])
    for col in target_cols:
        m = log["target"] == col
        actual = df[col].reindex(log.loc[m, "target_date"]).to_numpy()
        log.loc[m, "actual_price"] = actual
    log["error"] = log["actual_price"] - log["pred_price"]
    log["abs_pct_error"] = (log["error"].abs() / log["actual_price"] * 100)
    # chỉ chấm đúng/sai chiều khi cả dự báo lẫn thực tế có thay đổi (giá đứng yên không tính)
    d_pred = np.sign(log["pred_price"] - log["price_at_issue"])
    d_true = np.sign(log["actual_price"] - log["price_at_issue"])
    log["dir_correct"] = np.where(log["actual_price"].notna() & (d_pred != 0) & (d_true != 0),
                                  (d_pred == d_true).astype(float), np.nan)
    log["in_interval"] = np.where(
        log["actual_price"].notna() & log["lo"].notna(),
        (log["actual_price"] >= log["lo"]) & (log["actual_price"] <= log["hi"]), np.nan)
    log.to_csv(LOG, index=False)
    return log


# ------------------------------------------------------------------ Historical tracking price
RATINGS = ["Rất gần", "Gần", "Khá xa", "Xa"]


def rating_bands(h: int) -> tuple[float, float, float]:
    """Ngưỡng sai số tuyệt đối (% giá) cho 4 mức đánh giá; nới theo √h vì kỳ hạn dài
    biến động nhiều hơn. 1 ngày: 0.5% / 1% / 2%."""
    k = float(np.sqrt(h))
    return 0.5 * k, 1.0 * k, 2.0 * k


def _rate(abs_pct: pd.Series, h: int) -> pd.Series:
    b1, b2, b3 = rating_bands(h)
    out = pd.Series(np.select([abs_pct <= b1, abs_pct <= b2, abs_pct <= b3], RATINGS[:3], RATINGS[3]),
                    index=abs_pct.index, dtype=object)
    return out.where(abs_pct.notna())


def historical_tracking(target: str, h: int, lock_date: str | None = None,
                        live_prices: dict | None = None, proc_dir=DATA_PROCESSED) -> pd.DataFrame:
    """Đối chiếu từng dự báo trong quá khứ với giá thực tế.

    * "Backtest": dự báo walk-forward - tại mỗi ngày mô hình chỉ dùng dữ liệu có đến ngày đó
      (đúng như khi chạy thật), kể cả lớp tự học.
    * "Giai đoạn khoá": phần backtest sau lock_date, cấu hình đã chốt trước đó.
    * "Live": dự báo thật đã lưu trong predictions_log.csv tại thời điểm phát hành
      (được ưu tiên khi trùng ngày với backtest). Nếu có live_prices, các dự báo đến hạn
      hôm nay được chấm tạm bằng giá niêm yết mới nhất.
    """
    f = proc_dir / f"backtest_{target}_h{h}.csv"
    if not f.exists():
        return pd.DataFrame()
    wf = pd.read_csv(f, index_col=0, parse_dates=True)
    idx = wf.index
    tdates = pd.Series(list(idx[h:]) + [pd.NaT] * h, index=idx)
    p0 = wf["price_t"]
    bt = pd.DataFrame({
        "issued": idx, "target_date": tdates.to_numpy(), "price_issue": p0.to_numpy(),
        "pred": (p0 * np.exp(wf["Ensemble"])).to_numpy(),
        "lo": (p0 * np.exp(wf["lo"])).to_numpy(), "hi": (p0 * np.exp(wf["hi"])).to_numpy(),
        "lo80": (p0 * np.exp(wf["lo80"])).to_numpy() if "lo80" in wf else np.nan,
        "hi80": (p0 * np.exp(wf["hi80"])).to_numpy() if "hi80" in wf else np.nan,
        "actual": (p0 * np.exp(wf["actual"])).to_numpy(),
    })
    bt["source"] = "Backtest"
    if lock_date:
        bt.loc[bt["issued"] > pd.Timestamp(lock_date), "source"] = "Giai đoạn khoá"
    bt = bt[bt["target_date"].notna()]

    live = pd.DataFrame()
    log_path = proc_dir / LOG.name
    if log_path.exists():
        log = pd.read_csv(log_path, parse_dates=["as_of", "target_date"])
        log = log[(log["target"] == target) & (log["h"] == h) & (log["model"] == "Ensemble")]
        if len(log):
            live = pd.DataFrame({
                "issued": log["as_of"], "target_date": log["target_date"],
                "price_issue": log["price_at_issue"], "pred": log["pred_price"],
                "lo": log["lo"], "hi": log["hi"],
                # khoảng 80% chỉ được ghi vào nhật ký từ 11/2026; bản ghi cũ để trống (không đoán bù)
                "lo80": log["lo80"] if "lo80" in log else np.nan, "hi80": log["hi80"] if "hi80" in log else np.nan,
                "actual": log["actual_price"] if "actual_price" in log else np.nan,
                "source": "Live"})
            live["provisional"] = False
            lp = (live_prices or {}).get(target)
            if lp is not None:
                today = pd.Timestamp(lp["ts"]).normalize()
                due = live["actual"].isna() & (live["target_date"] <= today)
                live.loc[due, "actual"] = lp["price"]
                live.loc[due, "provisional"] = True
    if len(live):
        bt = bt[~bt["issued"].isin(live["issued"])]
    out = pd.concat([bt.assign(provisional=False), live], ignore_index=True)
    out = out.sort_values("issued").reset_index(drop=True)

    out["error"] = out["actual"] - out["pred"]
    out["error_pct"] = out["error"] / out["actual"] * 100
    out["abs_pct"] = out["error_pct"].abs()
    out["naive_abs_pct"] = (out["actual"] - out["price_issue"]).abs() / out["actual"] * 100
    # chỉ so trong các phiên giá thực sự thay đổi (khi giá đứng yên, Naive đúng tuyệt đối)
    moved = out["actual"].notna() & (out["naive_abs_pct"] > 0)
    out["closer_than_naive"] = np.where(moved, out["abs_pct"] < out["naive_abs_pct"], np.nan)
    out["in_band"] = np.where(out["actual"].notna() & out["lo"].notna(),
                              (out["actual"] >= out["lo"]) & (out["actual"] <= out["hi"]), np.nan)
    # in_band: khoảng 90% (bản Chuyên sâu) ; in_band80: khoảng 80% "nhiều khả năng" (bản Dễ hiểu, ứng dụng điện thoại)
    out["in_band80"] = np.where(out["actual"].notna() & out["lo80"].notna(),
                                (out["actual"] >= out["lo80"]) & (out["actual"] <= out["hi80"]), np.nan)
    d_pred = np.sign(out["pred"] - out["price_issue"])
    d_true = np.sign(out["actual"] - out["price_issue"])
    out["dir_ok"] = np.where(out["actual"].notna() & (d_pred != 0) & (d_true != 0),
                             (d_pred == d_true).astype(float), np.nan)
    out["rating"] = _rate(out["abs_pct"], h)
    out["naive_rating"] = _rate(out["naive_abs_pct"], h)
    return out


def tracking_summary(tr: pd.DataFrame) -> dict:
    """Các chỉ số tóm tắt trên những dự báo đã có giá thực tế."""
    d = tr[tr["actual"].notna()]
    if not len(d):
        return {"n": 0}
    share = d["rating"].value_counts(normalize=True).reindex(RATINGS).fillna(0) * 100
    return {
        "n": int(len(d)),
        "mae": float(d["error"].abs().mean()),
        "mape": float(d["abs_pct"].mean()),
        "median_ape": float(d["abs_pct"].median()),
        "naive_mape": float(d["naive_abs_pct"].mean()),
        "closer_than_naive": float(pd.to_numeric(d["closer_than_naive"]).dropna().mean() * 100),
        "in_band": float(pd.to_numeric(d["in_band"]).dropna().mean() * 100) if d["in_band"].notna().any() else np.nan,
        "dir_ok": float(pd.to_numeric(d["dir_ok"]).dropna().mean() * 100) if d["dir_ok"].notna().any() else np.nan,
        "rating_share": share.to_dict(),
        "naive_rating_share": (d["naive_rating"].value_counts(normalize=True)
                               .reindex(RATINGS).fillna(0) * 100).to_dict(),
    }
