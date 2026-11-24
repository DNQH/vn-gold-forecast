"""Thí nghiệm cải thiện độ chính xác (nhánh experiment/accuracy).

Kỷ luật chống overfit:
  * DEV  = các hàng có ngày <= LOCK_DATE: mọi lựa chọn ý tưởng / tham số chỉ dựa trên đây.
  * LOCK = các hàng sau LOCK_DATE: chỉ được tính SAU KHI đã chốt ứng viên (stage `locked`).

Các stage (chạy tuần tự, kết quả walk-forward lưu cache để stage sau dùng lại):
    python scripts/experiments/accuracy.py baseline   # kiểm tra tái lập Ensemble production
    python scripts/experiments/accuracy.py dev        # mọi ứng viên, CHỈ số liệu DEV
    python scripts/experiments/accuracy.py locked --candidate NAME   # đánh giá 1 lần trên LOCK

Ensemble production lấy từ data/processed/backtest_<target>_h<h>.csv (cùng mã, cùng dữ
liệu); stage baseline xác nhận chạy lại lớp tự học trên các cột mô hình cho đúng cột
Ensemble đã lưu.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
warnings.filterwarnings("ignore")

from vngold.config import DATA_PROCESSED, LOCK_DATE  # noqa: E402
from vngold.ecm import ECMModel, ecm_frame  # noqa: E402
from vngold.evaluation import diebold_mariano, price_metrics, walk_forward  # noqa: E402
from vngold.models import (LinearRegressionModel, Naive, RandomForestModel, WFData,  # noqa: E402
                           XGBoostModel)
from vngold.online import OnlineConfig, run_online  # noqa: E402
from vngold.pipeline import FEATURE_GROUPS, _prepare  # noqa: E402

CACHE = Path(__file__).resolve().parent / "_cache"
CACHE.mkdir(exist_ok=True)
PROD_MODELS = ["Naive", "MovingAverage", "LinearRegression", "ARIMA", "RandomForest", "XGBoost"]
RING_MODELS = ["Naive", "LinearRegression", "XGBoost"]
MIN_TRAIN = {"sjc_sell": 500, "ring_sell": 250}
LOCK = pd.Timestamp(LOCK_DATE)

# Ma trận cấu hình ECM được thử trên DEV (khai báo trước, không mở rộng sau khi xem kết quả)
ECM_GRID = {
    f"ECM_w{w}_{world}_{'hl500' if hl else 'exp'}{'_huber' if rob else ''}":
        dict(prem_window=w, world=world, halflife=hl, robust=rob)
    for w in (20, 60) for world in ("vnd", "usd") for hl in (None, 500) for rob in (False, True)
}
LEAN_DROP = ("Macro (DXY, lợi suất, Fed, CPI...)", "Tỷ giá USD/VND")


# ------------------------------------------------------------------ dữ liệu
def load_df() -> pd.DataFrame:
    return pd.read_csv(DATA_PROCESSED / "dataset.csv", index_col=0, parse_dates=True)


def load_prod(target: str, h: int) -> pd.DataFrame:
    return pd.read_csv(DATA_PROCESSED / f"backtest_{target}_h{h}.csv", index_col=0, parse_dates=True)


def prod_models(target: str) -> list[str]:
    return PROD_MODELS if target == "sjc_sell" else RING_MODELS


def cached(name: str, fn):
    p = CACHE / f"{name}.csv"
    if p.exists():
        return pd.read_csv(p, index_col=0, parse_dates=True)
    t0 = time.time()
    out = fn()
    out.to_csv(p)
    print(f"  [{name}] {time.time() - t0:.0f}s")
    return out


# ------------------------------------------------------------------ chỉ số
def metrics(wf: pd.DataFrame, col: str, mask: pd.Series, h: int, ref: str = "Ensemble") -> dict:
    m = mask & wf[col].notna() & wf[ref].notna() & wf["actual"].notna()
    w = wf[m]
    naive_err = w.price_t * (np.exp(w.actual) - 1)
    naive_rmse = float(np.sqrt((naive_err ** 2).mean()))
    r = price_metrics(w[col], w.actual, w.price_t, naive_rmse)
    e = (w.price_t * (np.exp(w.actual) - np.exp(w[col]))).to_numpy()
    e_ref = (w.price_t * (np.exp(w.actual) - np.exp(w[ref]))).to_numpy()
    r["DM_p_naive"] = diebold_mariano(e, naive_err.to_numpy(), h)[1] if col != "Naive" else np.nan
    if col != ref:
        r["DM_stat_ens"], r["DM_p_ens"] = diebold_mariano(e, e_ref, h)
    else:
        r["DM_stat_ens"], r["DM_p_ens"] = np.nan, np.nan
    r["RMSE_ens"] = float(np.sqrt((e_ref ** 2).mean()))
    return r


def period_mask(wf: pd.DataFrame, period: str) -> pd.Series:
    if period == "dev":
        return pd.Series(wf.index <= LOCK, index=wf.index)
    if period == "locked":
        return pd.Series(wf.index > LOCK, index=wf.index)
    return pd.Series(True, index=wf.index)


def table(wf, cols, period, h) -> pd.DataFrame:
    mask = period_mask(wf, period)
    rows = {c: metrics(wf, c, mask, h) for c in cols}
    keep = ["RMSE", "MAE", "TheilU", "DM_p_naive", "DM_stat_ens", "DM_p_ens", "DirAcc_%",
            "DirBase_%", "N"]
    return pd.DataFrame(rows).T[keep]


def coverage(on: pd.DataFrame, mask: pd.Series) -> tuple[float, float]:
    m = mask & on["lo"].notna() & on["actual"].notna()
    c90 = ((on.actual >= on.lo) & (on.actual <= on.hi))[m].mean()
    c80 = ((on.actual >= on.lo80) & (on.actual <= on.hi80))[m].mean()
    return float(c90), float(c80)


# ------------------------------------------------------------------ ứng viên
def ecm_wf(df, target, h, spec_name, spec) -> pd.DataFrame:
    """Walk-forward của một cấu hình ECM (cùng lưới, cùng mốc huấn luyện lại như production)."""
    def run():
        ds, start = _prepare(df, target)
        Z = ecm_frame(df, target, spec["prem_window"], spec["world"]).reindex(ds.X.index)
        cols = spec.get("cols", ("ec", "dw0", "dw1", "dp0", "dp1"))
        m = ECMModel(Z, cols=cols, halflife=spec["halflife"], robust=spec["robust"], name="ECM")
        wf = walk_forward(ds, [m], h, start, min_train=MIN_TRAIN[target], verbose=False)
        return wf[["ECM"]]
    return cached(f"{target}_h{h}_{spec_name}", run)


def lean_wf(df, target, h) -> pd.DataFrame:
    """Mô hình cây/tuyến tính trên tập đặc trưng gọn (bỏ nhóm vĩ mô & tỷ giá)."""
    def run():
        ds, start = _prepare(df, target)
        drop = [FEATURE_GROUPS[g] for g in LEAN_DROP]
        keep = [c for c in ds.X.columns if not any(fn(c) for fn in drop)]
        ds2 = WFData(ds.X[keep], ds.Y, ds.price, ds.r1)
        ms = [LinearRegressionModel(), RandomForestModel(), XGBoostModel()] if target == "sjc_sell" \
            else [LinearRegressionModel(), XGBoostModel()]
        wf = walk_forward(ds2, ms, h, start, min_train=MIN_TRAIN[target], verbose=False)
        return wf[[m.name for m in ms]].add_suffix("_lean")
    return cached(f"{target}_h{h}_lean", run)


def online_stack(wf: pd.DataFrame, cols: list[str], h: int, every: int = 21,
                 min_rows: int = 250, fallback: str = "Ensemble") -> np.ndarray:
    """Stacking không âm (NNLS) học dần: tại mỗi mốc chỉ dùng dự báo đã đáo hạn."""
    from scipy.optimize import nnls
    P, y = wf[cols].to_numpy(), wf["actual"].to_numpy()
    out = wf[fallback].to_numpy().copy()
    n = len(wf)
    for s in range(0, n, every):
        j = np.arange(0, max(0, s - h + 1))
        ok = j[~np.isnan(y[j]) & ~np.isnan(P[j]).any(axis=1)]
        if len(ok) < min_rows:
            continue
        w, _ = nnls(P[ok] * 100, y[ok] * 100)
        blk = slice(s, min(n, s + every))
        out[blk] = P[blk] @ w
    return out


def build_candidates(df, target, h, ecm_name: str | None) -> tuple[pd.DataFrame, dict]:
    """Dựng mọi ứng viên trên cùng chỉ mục với Ensemble production."""
    prod = load_prod(target, h)
    names = prod_models(target)
    wf = prod.copy()
    ons = {}
    if ecm_name:
        wf["ECM"] = ecm_wf(df, target, h, ecm_name, ECM_GRID[ecm_name])["ECM"].reindex(wf.index)
        on, _ = run_online(wf, names + ["ECM"], h)
        wf["Ens+ECM"], ons["Ens+ECM"] = on["Ensemble"], on
    lean = lean_wf(df, target, h).reindex(wf.index)
    wf = wf.join(lean)
    lean_names = ["Naive", "MovingAverage", "ARIMA"] if target == "sjc_sell" else ["Naive"]
    lean_names = [c for c in lean_names if c in wf] + list(lean.columns)
    on, _ = run_online(wf, lean_names, h)
    wf["Ens_lean"], ons["Ens_lean"] = on["Ensemble"], on
    if ecm_name:
        on, _ = run_online(wf, lean_names + ["ECM"], h)
        wf["Ens_lean+ECM"], ons["Ens_lean+ECM"] = on["Ensemble"], on
    # thành phần: bỏ ARIMA (U>1 trên DEV ở h=1) — chỉ áp dụng cho SJC (vàng nhẫn không có ARIMA)
    if target == "sjc_sell":
        sub = [c for c in names if c != "ARIMA"]
        on, _ = run_online(wf, sub, h)
        wf["Ens_noARIMA"], ons["Ens_noARIMA"] = on["Ensemble"], on
    stack_cols = [c for c in ["LinearRegression", "RandomForest", "XGBoost", "ECM"] if c in wf]
    wf["Stack_NNLS"] = online_stack(wf, stack_cols, h)
    return wf, ons


# ------------------------------------------------------------------ stage: baseline
def stage_baseline(args):
    out = {}
    for target in ("sjc_sell", "ring_sell"):
        for h in (1, 5, 21):
            prod = load_prod(target, h)
            on, _ = run_online(prod, prod_models(target), h)
            diff = float(np.nanmax(np.abs(on["Ensemble"].to_numpy() - prod["Ensemble"].to_numpy())))
            out[f"{target}_h{h}"] = diff
            print(f"{target} h={h}: max |Ensemble recomputed - saved| = {diff:.2e}  "
                  f"rows={len(prod)} dev={int((prod.index <= LOCK).sum())} locked={int((prod.index > LOCK).sum())}")
    assert max(out.values()) < 1e-10, "không tái lập được Ensemble production"


# ------------------------------------------------------------------ stage: dev
def stage_dev(args):
    df = load_df()
    res = {}
    # 1) lưới ECM - SJC h=1, chỉ DEV
    print("== ECM grid (SJC h=1, DEV)")
    prod = load_prod("sjc_sell", 1)
    rows = {}
    for name, spec in ECM_GRID.items():
        e = ecm_wf(df, "sjc_sell", 1, name, spec)["ECM"].reindex(prod.index)
        tmp = prod[["actual", "price_t", "Ensemble"]].assign(**{name: e})
        rows[name] = metrics(tmp, name, period_mask(tmp, "dev"), 1)
    grid = pd.DataFrame(rows).T[["RMSE", "TheilU", "DM_p_naive", "DM_p_ens", "DirAcc_%", "N"]]
    print(grid.sort_values("RMSE").round(4).to_string())
    best = grid["RMSE"].astype(float).idxmin()
    print("ECM tốt nhất trên DEV:", best)
    res["ecm_grid"] = grid.round(5).reset_index().to_dict("records")
    res["ecm_best"] = best

    # 2) ứng viên cho h=1 (SJC, vàng nhẫn) + h=5, h=21
    for target in ("sjc_sell", "ring_sell"):
        for h in (1, 5, 21):
            print(f"== {target} h={h} (DEV)")
            # kỳ hạn dài: ECM dài hạn (động lượng thế giới + độ lệch premium 120 phiên)
            spec = dict(ECM_GRID[best]) if h == 1 else dict(prem_window=ECM_GRID[best]["prem_window"],
                                                           world=ECM_GRID[best]["world"], halflife=500,
                                                           robust=False, cols=("ec", "ec120", "dw0", "dw5", "dw21"))
            name = best if h == 1 else f"ECMlong_h{h}"
            ECM_GRID.setdefault(name, spec)
            wf, ons = build_candidates(df, target, h, name)
            cols = prod_models(target) + [c for c in ["Ensemble", "ECM", "Ens+ECM", "Ens_lean",
                                                      "Ens_lean+ECM", "Ens_noARIMA", "Stack_NNLS"] if c in wf]
            cols = [c for c in cols if c != "MovingAverage"]
            t = table(wf, cols, "dev", h)
            for k, on in ons.items():
                t.loc[k, "Cov90"], t.loc[k, "Cov80"] = coverage(on, period_mask(on, "dev"))
            prod = load_prod(target, h)
            t.loc["Ensemble", "Cov90"], t.loc["Ensemble", "Cov80"] = coverage(prod, period_mask(prod, "dev"))
            print(t.round(4).to_string())
            res[f"{target}_h{h}"] = t.round(5).reset_index().to_dict("records")
            wf.to_csv(CACHE / f"cand_{target}_h{h}.csv")
    (CACHE / "dev_results.json").write_text(json.dumps(res, indent=1, default=float))


# ------------------------------------------------------------------ stage: extras (DEV)
class HurdleECM(ECMModel):
    """Hai tầng: P(giá đổi | x) (logistic) × E[lợi suất | giá đổi, x] (ECM trên ngày có đổi)."""
    name = "Hurdle"

    def __init__(self, Z, clf_X, **kw):
        super().__init__(Z, **kw)
        self.clf_X = clf_X

    def fit(self, ds, idx, h):
        from sklearn.linear_model import LogisticRegression
        y = ds.y(h)[idx]
        moved = ~np.isnan(y) & (y != 0)
        C = self.clf_X.to_numpy()[idx]
        ok = ~np.isnan(y) & ~np.isnan(C).any(axis=1)
        self.clf = LogisticRegression(C=1.0, max_iter=500).fit(C[ok], moved[ok])
        super().fit(ds, idx[moved], h)
        return self

    def predict(self, ds, idx, h):
        C = np.nan_to_num(self.clf_X.to_numpy()[np.asarray(idx)])
        return self.clf.predict_proba(C)[:, 1] * super().predict(ds, idx, h)


def hourly_feature(prod_index: pd.DatetimeIndex, path: Path, strict: bool = True) -> pd.Series:
    """Biến động GC=F từ lúc đóng phiên Mỹ ngày t tới trước giờ phát hành (giờ VN ngày t+1).

    strict: chỉ dùng nến 1 giờ đã KẾT THÚC trước 06:30 VN (an toàn với lịch chạy 7h).
    Không strict: nến kết thúc trước 07:00 VN (sát giờ chạy - chỉ để tham khảo).
    """
    hr = pd.read_csv(path, header=[0, 1], index_col=0)
    hr.columns = [c[0] for c in hr.columns]
    hr.index = pd.to_datetime(hr.index, utc=True)
    end_vn = (hr.index + pd.Timedelta(hours=1)).tz_convert("Asia/Ho_Chi_Minh").tz_localize(None)
    start_et = hr.index.tz_convert("America/New_York").tz_localize(None)
    close = pd.Series(hr["Close"].to_numpy(), index=end_vn)
    out = pd.Series(np.nan, index=prod_index)
    lim = pd.Timedelta(hours=6, minutes=30) if strict else pd.Timedelta(hours=7)
    for d in prod_index:
        # nến của phiên kế tiếp: mở từ 18:00 ET ngày d; kết thúc trước giờ giới hạn ngày d+1 (VN)
        sess_open = d + pd.Timedelta(hours=18)
        m = (start_et >= sess_open) & (end_vn <= d + pd.Timedelta(days=1) + lim)
        # điểm gốc: nến cuối của phiên ngày d (kết thúc 17:00 ET) ~ giá đóng cửa ngày
        base = (start_et < sess_open) & (start_et >= d)
        if not base.any():
            continue
        p0 = close[base].iloc[-1]
        out[d] = np.log(close[m].iloc[-1] / p0) if m.any() else 0.0
    return out


def stage_extras(args):
    df = load_df()
    res = {}
    prod = load_prod("sjc_sell", 1)
    dev = period_mask(prod, "dev")
    resid = prod.actual - prod.Ensemble
    # --- (a) thông tin giờ sáng (GC=F 60 phút, ~730 ngày gần nhất)
    path = Path(args.hourly) if args.hourly else None
    if path and path.exists():
        for strict in (True, False):
            x = hourly_feature(prod.index, path, strict)
            have = x.notna() & prod.actual.notna()
            nz = have & (x != 0)
            for per, pm in (("dev", dev), ("all", pd.Series(True, index=prod.index))):
                c = np.corrcoef(x[have & pm], resid[have & pm])[0, 1] if (have & pm).sum() > 10 else np.nan
                print(f"hourly strict={strict} {per}: N={int((have & pm).sum())} (≠0: {int((nz & pm).sum())}) "
                      f"corr(x, sai số Ensemble)={c:.3f}  |x| TB={x[have & pm].abs().mean() * 100:.3f}%")
                res[f"hourly_strict{strict}_{per}"] = {"N": int((have & pm).sum()), "N_nonzero": int((nz & pm).sum()),
                                                      "corr_resid": float(c)}
            # walk-forward: Ensemble + b·x, b học dần trên sai số đã đáo hạn (OLS không chặn)
            idx = np.where(have)[0]
            adj = prod.Ensemble.copy()
            xs, rs = x.to_numpy(), resid.to_numpy()
            for k, t in enumerate(idx):
                past = idx[:k][idx[:k] <= t - 1]
                past = past[~np.isnan(rs[past])]
                if len(past) >= 60 and (xs[past] ** 2).sum() > 0:
                    b = (xs[past] * rs[past]).sum() / (xs[past] ** 2).sum()
                    adj.iloc[t] = prod.Ensemble.iloc[t] + b * xs[t]
            tmp = prod[["actual", "price_t", "Ensemble"]].assign(EnsHourly=adj)
            sub = have & dev
            r = metrics(tmp, "EnsHourly", sub, 1)
            print(f"   Ens+hourly (strict={strict}) DEV-giờ: RMSE {r['RMSE']:.4f} vs Ensemble {r['RMSE_ens']:.4f} "
                  f"DM_p_ens {r['DM_p_ens']:.3f} N {r['N']}")
            res[f"hourly_strict{strict}_ens_dev"] = {k: r[k] for k in ("RMSE", "RMSE_ens", "DM_p_ens", "N", "DirAcc_%")}
            prod[f"EnsHourly_s{int(strict)}"] = adj
        prod.to_csv(CACHE / "cand_hourly_sjc_h1.csv")
    # --- (b) mô hình hai tầng (hurdle) cho tính rời rạc của giá SJC
    best = json.loads((CACHE / "dev_results.json").read_text())["ecm_best"]
    spec = ECM_GRID[best]
    ds, start = _prepare(df, "sjc_sell")
    Z = ecm_frame(df, "sjc_sell", spec["prem_window"], spec["world"]).reindex(ds.X.index)
    moved = (ds.r1 != 0).astype(float)
    C = pd.DataFrame({"abs_ec": Z.ec.abs(), "abs_dw0": Z.dw0.abs(),
                      "days_since_change": ds.X.days_since_change.clip(upper=20),
                      "chg_share20": moved.rolling(20).mean()}, index=ds.X.index)
    hm = HurdleECM(Z, C, halflife=spec["halflife"], robust=spec["robust"], name="Hurdle")
    hw = cached("sjc_sell_h1_hurdle", lambda: walk_forward(ds, [hm], 1, start, 500, verbose=False)[["Hurdle"]])
    cand = pd.read_csv(CACHE / "cand_sjc_sell_h1.csv", index_col=0, parse_dates=True)
    cand["Hurdle"] = hw["Hurdle"].reindex(cand.index)
    on, _ = run_online(cand, PROD_MODELS + ["Hurdle"], 1)
    cand["Ens+Hurdle"] = on["Ensemble"]
    t = table(cand, ["ECM", "Hurdle", "Ensemble", "Ens+ECM", "Ens+Hurdle"], "dev", 1)
    print(t.round(4).to_string())
    res["hurdle_dev"] = t.round(5).reset_index().to_dict("records")
    cand.to_csv(CACHE / "cand_sjc_sell_h1.csv")
    (CACHE / "extras_results.json").write_text(json.dumps(res, indent=1, default=float))


# ------------------------------------------------------------------ stage: locked
def stage_locked(args):
    """Đánh giá MỘT LẦN trên giai đoạn khoá cho ứng viên đã chốt (cùng các mốc so sánh)."""
    res = {}
    for target in ("sjc_sell", "ring_sell"):
        for h in (1, 5, 21):
            wf = pd.read_csv(CACHE / f"cand_{target}_h{h}.csv", index_col=0, parse_dates=True)
            cols = [c for c in ["Naive", "Ensemble", args.candidate] if c in wf]
            if args.all:   # hậu kiểm, KHÔNG dùng để lựa chọn
                cols += [c for c in ["ECM", "Ens+ECM", "Ens_lean", "Ens_lean+ECM", "Ens_noARIMA",
                                     "Stack_NNLS"] if c in wf and c not in cols]
            t = table(wf, cols, "locked", h)
            prod = load_prod(target, h)
            t.loc["Ensemble", "Cov90"], t.loc["Ensemble", "Cov80"] = coverage(prod, period_mask(prod, "locked"))
            print(f"== {target} h={h} (LOCKED)")
            print(t.round(4).to_string())
            res[f"{target}_h{h}"] = t.round(5).reset_index().to_dict("records")
    (CACHE / f"locked_results{'_all' if args.all else ''}.json").write_text(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["baseline", "dev", "extras", "locked"])
    ap.add_argument("--hourly", default=None, help="CSV GC=F 60m (yfinance) cho stage extras")
    ap.add_argument("--candidate", default="Ens+ECM")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    {"baseline": stage_baseline, "dev": stage_dev, "extras": stage_extras,
     "locked": stage_locked}[a.stage](a)
