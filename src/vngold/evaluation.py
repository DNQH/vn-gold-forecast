"""Module 5 - Model Evaluation: walk-forward validation + chỉ số đánh giá.

KHÔNG chia train/test ngẫu nhiên. Tại mỗi mốc huấn luyện lại s:
  * chỉ học trên các hàng i có nhãn đã biết tại thời điểm s, tức i + h <= s
    (nhãn y_{i,h} cần giá ngày i+h) -> không rò rỉ tương lai;
  * dự báo cho các ngày s .. s + RETRAIN_EVERY - 1 (mở rộng cửa sổ - expanding).
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
from scipy import stats

from vngold.config import MIN_TRAIN, RETRAIN_EVERY
from vngold.models import WFData


def walk_forward(ds: WFData, models, h: int, start: int, min_train: int = MIN_TRAIN,
                 retrain_every: int = RETRAIN_EVERY, verbose: bool = True) -> pd.DataFrame:
    n = len(ds.X)
    first_test = start + min_train
    preds = {m.name: np.full(n, np.nan) for m in models}
    timing = {m.name: 0.0 for m in models}
    for s in range(first_test, n, retrain_every):
        train_idx = np.arange(start, s - h + 1)
        test_idx = np.arange(s, min(n, s + retrain_every))
        for m in models:
            t0 = time.time()
            m.fit(ds, train_idx, h)
            preds[m.name][test_idx] = m.predict(ds, test_idx, h)
            timing[m.name] += time.time() - t0
    if verbose:
        print(f"  h={h}: " + ", ".join(f"{k} {v:.0f}s" for k, v in timing.items()))
    out = pd.DataFrame(preds, index=ds.X.index)
    out["actual"] = ds.y(h)
    out["price_t"] = ds.price.to_numpy()
    return out.iloc[first_test:]


# ------------------------------------------------------------------ Chỉ số
def price_metrics(pred_ret: pd.Series, actual_ret: pd.Series, price_t: pd.Series,
                  naive_rmse: float | None = None) -> dict:
    m = pred_ret.notna() & actual_ret.notna()
    pr, ar, p0 = pred_ret[m], actual_ret[m], price_t[m]
    p_hat, p_true = p0 * np.exp(pr), p0 * np.exp(ar)
    err = p_true - p_hat
    moved = ar != 0
    hits = (np.sign(pr[moved]) == np.sign(ar[moved]))
    da = hits.mean() if (pr[moved] != 0).any() else np.nan
    # Mốc so sánh: luôn đoán theo chiều phổ biến hơn trong giai đoạn kiểm định
    # (vàng tăng mạnh 2019-2026 nên "luôn đoán tăng" đã đúng > 50%).
    base = max((ar[moved] > 0).mean(), (ar[moved] < 0).mean()) if moved.any() else np.nan
    p_dir = np.nan
    if da == da and base == base and len(hits):
        from scipy.stats import binomtest
        p_dir = binomtest(int(hits.sum()), int(len(hits)), float(base), alternative="greater").pvalue
    rmse = float(np.sqrt((err ** 2).mean()))
    return {
        "MAE": float(err.abs().mean()),                # triệu VND/lượng
        "RMSE": rmse,
        "MAPE_%": float((err.abs() / p_true).mean() * 100),
        "DirAcc_%": float(da * 100) if da == da else np.nan,
        "DirBase_%": float(base * 100) if base == base else np.nan,
        "DirEdge_pp": float((da - base) * 100) if da == da else np.nan,
        "Dir_p": float(p_dir) if p_dir == p_dir else np.nan,
        "TheilU": rmse / naive_rmse if naive_rmse else np.nan,  # <1: tốt hơn Naive
        "N": int(m.sum()),
    }


def diebold_mariano(e1: np.ndarray, e2: np.ndarray, h: int) -> tuple[float, float]:
    """DM test (loss bình phương, HAC Newey-West lag h-1). stat<0: mô hình 1 tốt hơn."""
    d = e1 ** 2 - e2 ** 2
    d = d[~np.isnan(d)]
    T = len(d)
    dbar = d.mean()
    gamma = [np.sum((d[k:] - dbar) * (d[:T - k] - dbar)) / T for k in range(h)]
    var = gamma[0] + 2 * sum((1 - k / h) * gamma[k] for k in range(1, h))
    if var <= 0:
        return np.nan, np.nan
    stat = dbar / np.sqrt(var / T)
    # hiệu chỉnh Harvey-Leybourne-Newbold
    stat *= np.sqrt((T + 1 - 2 * h + h * (h - 1) / T) / T)
    p = 2 * stats.t.sf(abs(stat), df=T - 1)
    return float(stat), float(p)


def evaluate_table(wf: pd.DataFrame, model_cols: list[str], h: int) -> pd.DataFrame:
    naive_err = wf["price_t"] * (np.exp(wf["actual"]) - 1)
    m = wf["actual"].notna()
    naive_rmse = float(np.sqrt((naive_err[m] ** 2).mean()))
    rows = []
    for c in model_cols:
        r = price_metrics(wf[c], wf["actual"], wf["price_t"], naive_rmse)
        mm = m & wf[c].notna()
        e_model = (wf["price_t"] * (np.exp(wf["actual"]) - np.exp(wf[c])))[mm].to_numpy()
        e_naive = naive_err[mm].to_numpy()
        r["DM_stat"], r["DM_p"] = diebold_mariano(e_model, e_naive, h) if c != "Naive" else (np.nan, np.nan)
        r["model"] = c
        rows.append(r)
    return pd.DataFrame(rows).set_index("model")
