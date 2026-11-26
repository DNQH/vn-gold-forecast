"""Dự báo SƠ BỘ buổi tối (19h giờ VN) cho phiên kế tiếp + kiểm định walk-forward của nó.

Bối cảnh: dự báo chính thức phát hành ~7h sáng ngày T+1, dùng giá trong nước chốt ngày T và phiên Mỹ
ngày T (đóng cửa ~4–5h sáng T+1 giờ VN). Lúc 19h ngày T (= 12:00 UTC):
  * giá trong nước ngày T coi như đã chốt (CafeF hiếm khi đổi giá sau 19h);
  * phiên Mỹ ngày T CHƯA đóng cửa, nhưng vàng/đô la/bạc giao dịch gần 24h nên có giá "đang chạy".
Dự báo sơ bộ = đúng các mô hình h=1 của bản sáng, áp lên hàng T trong đó các biến thế giới
(xau_usd, dxy, us10y, usd_vnd, silver_usd, vix) được thay bằng giá mới nhất lúc 19h ("giá đóng cửa tạm").

Chống rò rỉ khi kiểm định: tại hàng T chỉ thay giá thế giới bằng giá của thanh 1 giờ ĐÃ ĐÓNG trước
12:00 UTC ngày T (thanh bắt đầu <= 11:00 UTC); các hàng < T giữ nguyên giá đóng cửa thật (đã biết lúc 19h).
Mô hình được huấn luyện đúng lịch walk-forward của bản sáng (huấn luyện lại mỗi 21 phiên, chỉ học nhãn
đã biết), nên dự báo "sáng" tái tạo được phải trùng với backtest_{target}_h1.csv (kiểm tra trong báo cáo).
"""
from __future__ import annotations

import json
import pickle
from datetime import datetime

import numpy as np
import pandas as pd

from vngold.config import (DATA_PROCESSED, DATA_RAW, ECM_PARAMS, EDGE_MAX_DM_P, EDGE_MAX_THEILU,
                           LOCK_DATE, MODELS_DIR, RETRAIN_EVERY, YAHOO_TICKERS)
from vngold.data.process import add_derived

WORLD_COLS = list(YAHOO_TICKERS.values())   # xau_usd, dxy, us10y, usd_vnd, silver_usd, vix
CUTOFF_BAR_UTC = 11        # thanh 1 giờ bắt đầu 11:00 UTC đóng lúc 12:00 UTC = 19:00 giờ VN
HOURLY_CACHE = DATA_RAW / "yahoo_hourly.csv"    # gitignored (chỉ dùng để kiểm định)
EVAL_JSON = DATA_PROCESSED / "evening_eval.json"
MIN_TRAIN = {"sjc_sell": 500, "ring_sell": 250}   # giống pipeline.run
FEATURE_WINDOW = 400       # số hàng lịch sử dùng để tính đặc trưng cho một hàng (EWM span 26 -> sai số ~1e-13)


# ------------------------------------------------------------------ dữ liệu thế giới theo giờ
def fetch_hourly(period: str = "730d", cache=HOURLY_CACHE) -> pd.DataFrame:
    """Giá đóng cửa thanh 1 giờ (UTC, không tz) cho các mã Yahoo của dự án. Yahoo giữ tối đa ~730 ngày;
    cache được gộp dần để lịch sử dài thêm theo thời gian."""
    import yfinance as yf

    raw = yf.download(list(YAHOO_TICKERS), period=period, interval="1h", progress=False,
                      threads=False, auto_adjust=False)
    c = raw["Close"].rename(columns=YAHOO_TICKERS)
    c.index = pd.DatetimeIndex(c.index).tz_convert("UTC").tz_localize(None)
    c = c.dropna(how="all")
    if "usd_vnd" in c:
        v = c["usd_vnd"]
        c.loc[(v < 15000) | (v > 40000), "usd_vnd"] = np.nan
    if cache is not None:
        if cache.exists():
            old = pd.read_csv(cache, index_col=0, parse_dates=True)
            c = c.combine_first(old)
        c = c.sort_index()[[k for k in WORLD_COLS if k in c.columns]]
        c.to_csv(cache)
    return c


def world_asof(hourly: pd.DataFrame, last_bar_start) -> tuple[dict, dict]:
    """Giá mới nhất của từng biến thế giới tính tới thanh có giờ bắt đầu <= last_bar_start (UTC).

    Trả về (giá, thời điểm thanh). Mã không giao dịch giờ đó (vd. ^TNX) lấy giá gần nhất trước đó –
    đúng như khi xem giá thật lúc 19h."""
    h = hourly.loc[hourly.index <= pd.Timestamp(last_bar_start)]
    vals, ts = {}, {}
    for c in WORLD_COLS:
        if c not in h:
            continue
        s = h[c].dropna()
        if len(s):
            vals[c], ts[c] = float(s.iloc[-1]), s.index[-1]
    return vals, ts


def cutoff_bar(day) -> pd.Timestamp:
    """Thanh 1 giờ cuối cùng đã đóng lúc 19:00 giờ VN của ngày `day` (UTC)."""
    return pd.Timestamp(day).normalize() + pd.Timedelta(hours=CUTOFF_BAR_UTC)


def provisional_df(df: pd.DataFrame, day, world: dict, dom: dict | None = None,
                   macro: dict | None = None, carry_volume: bool = True) -> pd.DataFrame:
    """Bản sao df tới hết ngày `day`, trong đó hàng `day` dùng giá thế giới tạm tính lúc 19h.

    Nếu df chưa có hàng `day` (chạy thật buổi tối: dataset sáng nay dừng ở T-1) thì thêm hàng mới
    từ hàng trước (macro mặc định giữ nguyên, có thể truyền `macro`) rồi ghi đè giá trong nước `dom`.
    Các hàng < day KHÔNG bị đổi. Khối lượng vàng của phiên đang chạy chưa đủ -> giữ của phiên trước."""
    day = pd.Timestamp(day)
    out = df.loc[:day].copy()
    if len(out) == 0:
        raise ValueError("df không có dữ liệu trước ngày cần dự báo")
    if out.index[-1] != day:
        new = out.iloc[[-1]].copy()
        new.index = pd.DatetimeIndex([day], name=out.index.name)
        out = pd.concat([out, new])
    for c, v in (world or {}).items():
        out.loc[day, c] = v
    if carry_volume and "gold_volume" in out and len(out) > 1:
        out.loc[day, "gold_volume"] = out["gold_volume"].iloc[-2]
    for c, v in (macro or {}).items():
        if c in out and v is not None and v == v:
            out.loc[day, c] = v
    for c, v in (dom or {}).items():
        out.loc[day, c] = v
    return add_derived(out)


def _row_features(df: pd.DataFrame, target: str, day, world: dict,
                  carry_volume: bool = True) -> tuple[pd.Series, pd.Series]:
    from vngold.ecm import ecm_frame
    from vngold.features import build_features
    pos = df.index.get_loc(day)
    sub = df.iloc[max(0, pos - FEATURE_WINDOW): pos + 1]
    d = provisional_df(sub, day, world, carry_volume=carry_volume)
    X = build_features(d, target).iloc[-1]
    Z = ecm_frame(d, target, ECM_PARAMS["prem_window"], ECM_PARAMS["world"]).iloc[-1]
    return X, Z


# ------------------------------------------------------------------ kiểm định walk-forward
X_FREE = {"Naive", "MovingAverage", "ARIMA"}   # mô hình không dùng biến thế giới -> dự báo như bản sáng


def evening_backtest(df: pd.DataFrame, target: str, hourly: pd.DataFrame, proc_dir=DATA_PROCESSED,
                     start_day: str | None = None, verbose: bool = True) -> dict:
    """Walk-forward cho 3 phiên bản dự báo h=1 trên cùng các ngày có giá thế giới theo giờ:
      * "morning": bản chính thức 7h sáng (tái tạo; phải trùng backtest đã lưu),
      * "evening": bản sơ bộ 19h (giá thế giới lúc 19h thay cho giá đóng cửa phiên Mỹ ngày T),
      * "prev": bản 19h KHÔNG dùng giá thế giới trong ngày (giữ giá đóng cửa phiên Mỹ T-1) – mốc so sánh.
    Lớp tự học (online.py) chạy riêng cho từng phiên bản; trước giai đoạn kiểm định nó được "khởi động"
    bằng dự báo walk-forward của bản sáng (đều chỉ dùng quá khứ)."""
    from vngold.models import WFData
    from vngold.online import run_online
    from vngold.pipeline import _prepare, build_models

    ds, start = _prepare(df, target)
    n, h = len(ds.X), 1
    first_test = start + MIN_TRAIN[target]
    dates = ds.X.index
    gold = hourly["xau_usd"].dropna()
    t0 = max(gold.index.min().normalize() + pd.Timedelta(days=3), dates[first_test])
    if start_day:
        t0 = max(t0, pd.Timestamp(start_day))
    eve_pos = np.array([i for i in range(first_test, n) if dates[i] >= t0])
    days = dates[eve_pos]

    # đặc trưng hàng T cho từng phiên bản
    X_eve, X_prev = ds.X.copy(), ds.X.copy()
    models = build_models(target, h, False, df, ds)
    ecm = next((m for m in models if m.name == "ECM"), None)
    Z_true = ecm.Z.copy() if ecm else None
    Z_eve, Z_prev = (Z_true.copy(), Z_true.copy()) if ecm else (None, None)
    wcols = [c for c in WORLD_COLS if c in df.columns]
    stale_gold, chk = 0, []
    for k, T in enumerate(days):
        w, ts = world_asof(hourly, cutoff_bar(T))
        if "xau_usd" not in ts or ts["xau_usd"] < T - pd.Timedelta(hours=2):   # chưa có giá vàng phiên T
            stale_gold += 1
        prev_row = df.loc[:T].iloc[-2]
        Xe, Ze = _row_features(df, target, T, w)
        Xp, Zp = _row_features(df, target, T, {c: prev_row[c] for c in wcols})
        X_eve.loc[T], X_prev.loc[T] = Xe[ds.X.columns].to_numpy(), Xp[ds.X.columns].to_numpy()
        if ecm:
            Z_eve.loc[T], Z_prev.loc[T] = Ze[Z_true.columns].to_numpy(), Zp[Z_true.columns].to_numpy()
        if k % 100 == 0:   # kiểm tra: tính đặc trưng trên cửa sổ cắt với giá thật = đặc trưng gốc
            Xt, _ = _row_features(df, target, T, {c: df.loc[T, c] for c in wcols}, carry_volume=False)
            chk.append(float(np.nanmax(np.abs(Xt[ds.X.columns].to_numpy(float) - ds.X.loc[T].to_numpy(float)))))
    ds_eve = WFData(X_eve, ds.Y, ds.price, ds.r1)
    ds_prev = WFData(X_prev, ds.Y, ds.price, ds.r1)

    names = [m.name for m in models]
    P = {v: {m: np.full(n, np.nan) for m in names} for v in ("morning", "evening", "prev")}
    eve_set = set(eve_pos.tolist())
    for s in range(first_test, n, RETRAIN_EVERY):
        test = np.arange(s, min(n, s + RETRAIN_EVERY))
        sel = np.array([i for i in test if i in eve_set], dtype=int)
        if not len(sel):
            continue
        train = np.arange(start, s - h + 1)
        for m in models:
            m.fit(ds, train, h)
            base = m.predict(ds, sel, h)
            P["morning"][m.name][sel] = base
            if m.name in X_FREE:
                P["evening"][m.name][sel] = base
                P["prev"][m.name][sel] = base
                continue
            for v, dsv, Zv in (("evening", ds_eve, Z_eve), ("prev", ds_prev, Z_prev)):
                if m is ecm:
                    m.Z = Zv
                P[v][m.name][sel] = m.predict(dsv, sel, h)
                if m is ecm:
                    m.Z = Z_true
        if verbose:
            print(f"  {target}: huấn luyện lại tại {dates[s]:%Y-%m-%d}", flush=True)

    # dự báo walk-forward đã lưu của bản sáng (khởi động lớp tự học + đối chiếu)
    wf_m = pd.read_csv(proc_dir / f"backtest_{target}_h1.csv", index_col=0, parse_dates=True)
    wf_m = wf_m.reindex(dates[first_test:])
    repro = float(np.nanmax(np.abs(np.column_stack([P["morning"][m][eve_pos] for m in names])
                                   - wf_m.loc[days, names].to_numpy())))
    out = {"days": days, "repro_maxdiff": repro, "feature_window_maxdiff": max(chk) if chk else np.nan,
           "stale_gold_days": stale_gold, "models": names}
    for v in ("evening", "prev"):
        wf = wf_m[names + ["actual", "price_t"]].copy()
        for m in names:
            col = wf[m].to_numpy().copy()
            col[eve_pos - first_test] = P[v][m][eve_pos]
            wf[m] = col
        on, st = run_online(wf, names, h)
        out[v] = (on, st)
    out["morning"] = (wf_m, None)
    return out


def _brier(p, actual):
    m = p.notna() & actual.notna() & (actual != 0)
    return float((((p - (actual > 0)) ** 2)[m]).mean()), int(m.sum())


def summarize(res: dict, wf_morning_full: pd.DataFrame) -> dict:
    """Chỉ số so sánh trên cùng các ngày kiểm định (toàn giai đoạn và giai đoạn khoá sau LOCK_DATE)."""
    from vngold.evaluation import evaluate_table
    from vngold.plain import BUCKET_NAMES, BUCKETS
    days = res["days"]
    actual_all = wf_morning_full["actual"]
    clim_all = (actual_all > 0).where(actual_all.notna() & (actual_all != 0)).shift(1).expanding().mean()
    out = {}
    for period, sel in (("all", days), ("locked", days[days > pd.Timestamp(LOCK_DATE)])):
        if len(sel) < 30:
            continue
        rows = {}
        for v in ("morning", "evening", "prev"):
            on = res[v][0].loc[sel]
            tmp = pd.DataFrame({"actual": on["actual"], "price_t": on["price_t"], "E": on["Ensemble"]})
            t = evaluate_table(tmp, ["E"], 1).loc["E"]
            br, nb = _brier(on["p_up"], on["actual"])
            mm = on["lo80"].notna() & on["actual"].notna()
            cov = float(((on.actual >= on.lo80) & (on.actual <= on.hi80))[mm].mean())
            rows[v] = {"RMSE": float(t.RMSE), "TheilU": float(t.TheilU), "DM_p": float(t.DM_p),
                       "DirAcc_%": float(t["DirAcc_%"]), "DirBase_%": float(t["DirBase_%"]),
                       "Dir_p": float(t.Dir_p), "N": int(t.N), "Brier": br, "cov80": cov}
        a = res["morning"][0].loc[sel, "actual"]
        moved = a[a.notna() & (a != 0)]
        cb, _ = _brier(clim_all.loc[sel], a)
        for v in rows:
            rows[v]["BrierSkill"] = 1 - rows[v]["Brier"] / cb if cb > 0 else np.nan
        rows["baseline"] = {"always_up_%": float((moved > 0).mean() * 100), "n_moved": int(len(moved)),
                            "share_flat_%": float((a.dropna() == 0).mean() * 100), "Brier_clim": cb}
        out[period] = rows
    # bảng "nói tăng/giảm thì đúng mấy lần" cho bản sơ bộ (phiên đứng yên tính là không đúng)
    on = res["evening"][0].loc[days]
    a = on[on.p_up.notna() & on.actual.notna()]
    b = pd.cut(a.p_up, BUCKETS, labels=BUCKET_NAMES, include_lowest=True)
    buckets = {}
    for name in BUCKET_NAMES:
        g = a[b == name]
        if not len(g):
            continue
        rate = (g.actual > 0).mean() if name in ("strong_up", "lean_up") else \
            (g.actual < 0).mean() if name in ("strong_down", "lean_down") else np.nan
        buckets[name] = {"n": int(len(g)), "rate": None if rate != rate else float(rate)}
    out["buckets"] = buckets
    return out


def edge_verdict(summary: dict) -> tuple[bool, str]:
    """Cổng trung thực cho bản sơ bộ: chỉ nói chiều khi, trên toàn giai đoạn kiểm định, bản 19h
    (1) vượt Naive có ý nghĩa thống kê (TheilU < 1, DM p < 0,10 – cùng tiêu chí với bản sáng),
    (2) đoán chiều đúng hơn "luôn đoán tăng"/chiều phổ biến, (3) xác suất tốt hơn tần suất lịch sử (Brier skill > 0),
    và (4) giai đoạn khoá (nếu đủ dữ liệu) không tệ hơn Naive (TheilU < 1)."""
    e = summary.get("all", {}).get("evening")
    if not e:
        return False, "chưa đủ dữ liệu kiểm định"
    reasons = []
    if not (e["TheilU"] < EDGE_MAX_THEILU and e["DM_p"] < EDGE_MAX_DM_P):
        reasons.append(f"chưa vượt Naive (TheilU {e['TheilU']:.3f}, DM p {e['DM_p']:.3f})")
    if not (e["DirAcc_%"] > e["DirBase_%"]):
        reasons.append(f"đoán chiều {e['DirAcc_%']:.1f}% không hơn mốc {e['DirBase_%']:.1f}%")
    if not (e.get("BrierSkill", -1) > 0):
        reasons.append("xác suất không tốt hơn tần suất lịch sử")
    lk = summary.get("locked", {}).get("evening")
    if lk and not lk["TheilU"] < 1:
        reasons.append(f"giai đoạn khoá TheilU {lk['TheilU']:.3f} >= 1")
    return (not reasons), ("; ".join(reasons) if reasons else "có lợi thế")


def save_state(target: str, st) -> None:
    with open(MODELS_DIR / f"online_state_evening_{target}_h1.pkl", "wb") as f:
        pickle.dump(st, f)


def load_state(target: str):
    f = MODELS_DIR / f"online_state_evening_{target}_h1.pkl"
    if not f.exists():
        return None
    with open(f, "rb") as fh:
        return pickle.load(fh)


def load_eval(path=EVAL_JSON) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------------ dự báo sơ bộ (chạy thật lúc 19h)
def preliminary_forecast(df_hist: pd.DataFrame, target: str, day, dom: dict, world: dict,
                         state=None, macro: dict | None = None) -> dict:
    """Huấn luyện nhanh các mô hình h=1 (một lần, trên mọi nhãn đã biết tới hết ngày `day`) rồi dự báo
    hàng `day` với giá thế giới tạm tính. `state`: trạng thái lớp tự học của bản sơ bộ (từ kiểm định),
    thiếu thì dùng trạng thái bản sáng. Trả về lợi suất log dự báo + khoảng 80% + P(tăng)."""
    from vngold.online import apply_state
    from vngold.pipeline import _prepare, build_models

    d = provisional_df(df_hist, day, world, dom=dom, macro=macro)
    ds, start = _prepare(d, target)
    i = len(ds.X) - 1
    if ds.X.index[i] != pd.Timestamp(day):
        raise ValueError(f"thiếu giá {target} ngày {day}")
    models = build_models(target, 1, False, d, ds)
    train = np.arange(start, i)   # nhãn hàng i-1 = giá hôm nay / giá hôm qua: đã biết lúc 19h
    preds = {}
    for m in models:
        m.fit(ds, train, 1)
        preds[m.name] = float(m.predict(ds, np.array([i]), 1)[0])
    used = "evening"
    if state is None:
        used = "morning"
        with open(MODELS_DIR / f"online_state_{target}_h1.pkl", "rb") as f:
            state = pickle.load(f)
    r = apply_state(preds, state, h=1)
    return {"ensemble": r["ensemble"], "lo80": r["lo80"], "hi80": r["hi80"], "p_up": r["p_up"],
            "R0_up_share": float(np.mean(np.asarray(state.resid) > 0)) if len(state.resid) else np.nan,
            "raw": preds, "weights": r["weights"], "state": used, "price": float(ds.price.iloc[i])}


def write_eval(results: dict, path=EVAL_JSON) -> None:
    results = dict(results, generated_at=datetime.now().isoformat(timespec="seconds"))
    path.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
