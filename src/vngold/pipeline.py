"""Điều phối toàn bộ hệ thống: thu thập -> xử lý -> EDA -> backtest -> tự học -> dự báo."""
from __future__ import annotations

import json
import pickle
import time
from datetime import datetime

import numpy as np
import pandas as pd

from vngold.config import (DATA_PROCESSED, EDGE_MAX_DM_P, EDGE_MAX_THEILU, HORIZONS,
                           LOCK_DATE, MODELS_DIR, REPORTS)
from vngold.evaluation import evaluate_table, walk_forward
from vngold.explain import explain_row, global_importance, label, shap_values
from vngold.features import build_features, build_targets
from vngold.models import (LinearRegressionModel, Naive, WFData, XGBoostModel,
                           default_models)
from vngold.online import _sigma_series, apply_state, online_ablation, run_online

TARGET_NAMES = {"sjc_sell": "Vàng miếng SJC", "ring_sell": "Vàng nhẫn 9999"}

FEATURE_GROUPS = {
    "Technical indicators": lambda c: c.startswith(("dom_", "xau_rsi", "xau_macd", "xau_ma", "xau_bb", "xau_vol")),
    "Macro (DXY, lợi suất, Fed, CPI...)": lambda c: c.startswith(("dxy", "us10y", "real_rate", "breakeven", "fed_", "cpi", "unemployment", "vix")),
    "Domestic premium & pass-through": lambda c: c.startswith(("premium", "passthrough")),
    "Vàng thế giới (XAU)": lambda c: c.startswith(("xau_ret", "silver", "gold_")),
    "Tỷ giá USD/VND": lambda c: c.startswith("usdvnd"),
}


def _prepare(df: pd.DataFrame, target: str):
    X = build_features(df, target)
    Y = build_targets(df, list(HORIZONS), target)
    ok = df[target].notna()
    X, Y, price = X[ok], Y[ok], df.loc[ok, target]
    ds = WFData(X, Y, price, np.log(price).diff())
    core = X.dropna(subset=["ret_63d", "dom_ma50_gap"]).index[0]
    start = int(np.argmax(X.index >= core))
    return ds, start


def build_models(target: str, h: int, lstm: bool, df: pd.DataFrame | None = None,
                 ds: WFData | None = None, use_ecm: bool | None = None) -> list:
    """Danh sách mô hình cho một mục tiêu/kỳ hạn. ECM (thử nghiệm) chỉ thêm khi USE_ECM bật."""
    from vngold import config
    models = default_models(include_lstm=lstm) if target == "sjc_sell" else \
        [Naive(), LinearRegressionModel(), XGBoostModel()]
    use_ecm = config.USE_ECM if use_ecm is None else use_ecm
    if use_ecm and df is not None and ds is not None:
        from vngold.ecm import ECMModel, ecm_frame
        p = config.ECM_PARAMS
        Z = ecm_frame(df, target, p["prem_window"], p["world"]).reindex(ds.X.index)
        cols = config.ECM_COLS_H1 if h == 1 else config.ECM_COLS_LONG
        models.append(ECMModel(Z, cols=cols, halflife=p["halflife"]))
    return models


def backtest(ds: WFData, start: int, h: int, models, min_train: int):
    wf = walk_forward(ds, models, h, start, min_train=min_train)
    names = [m.name for m in models]
    on, st = run_online(wf, names, h)
    wf = wf.join(on[["Ensemble_raw", "Ensemble", "lo", "hi", "lo80", "hi80", "p_up", "alpha_t"]])
    table = evaluate_table(wf, names + ["Ensemble_raw", "Ensemble"], h)
    m = wf["lo"].notna() & wf["actual"].notna()
    table.attrs["coverage90"] = float(((wf.actual >= wf.lo) & (wf.actual <= wf.hi))[m].mean())
    table.attrs["coverage80"] = float(((wf.actual >= wf.lo80) & (wf.actual <= wf.hi80))[m].mean())
    # Brier score của xác suất tăng
    mm = wf["p_up"].notna() & wf["actual"].notna() & (wf["actual"] != 0)
    up = (wf.actual > 0)[mm]
    table.attrs["brier_up"] = float(((wf.p_up[mm] - up) ** 2).mean())
    # Brier skill so với "tần suất khí hậu" (luôn báo tỷ lệ tăng lịch sử, chỉ dùng quá khứ)
    clim = (wf.actual > 0).where(wf.actual.notna() & (wf.actual != 0)).shift(h).expanding().mean()
    b_clim = float(((clim[mm] - up) ** 2).mean())
    table.attrs["brier_skill"] = 1 - table.attrs["brier_up"] / b_clim if b_clim > 0 else np.nan
    locked = wf[wf.index > pd.Timestamp(LOCK_DATE)]
    table.attrs["locked"] = evaluate_table(locked, names + ["Ensemble_raw", "Ensemble"], h) \
        if locked["actual"].notna().sum() >= 30 else None
    if table.attrs["locked"] is not None:
        ml = locked["lo"].notna() & locked["actual"].notna()
        table.attrs["locked_cov90"] = float(((locked.actual >= locked.lo) & (locked.actual <= locked.hi))[ml].mean())
    return wf, on, st, table


def has_edge(table: pd.DataFrame) -> bool:
    """Ensemble có lợi thế thống kê so với Naive hay không."""
    e = table.loc["Ensemble"]
    return bool(e.TheilU < EDGE_MAX_THEILU and e.DM_p < EDGE_MAX_DM_P)


def ablation(ds: WFData, start: int, h: int, min_train: int) -> pd.DataFrame:
    """Bỏ từng nhóm đặc trưng ra khỏi XGBoost để xem nhóm đó có thực sự giúp dự báo."""
    rows = []
    base_wf = walk_forward(ds, [Naive(), XGBoostModel()], h, start, min_train=min_train, verbose=False)
    base = evaluate_table(base_wf, ["XGBoost"], h).loc["XGBoost"]
    rows.append({"Bỏ nhóm": "(đầy đủ)", "RMSE": base.RMSE, "TheilU": base.TheilU, "DirAcc_%": base["DirAcc_%"]})
    for g, fn in FEATURE_GROUPS.items():
        keep = [c for c in ds.X.columns if not fn(c)]
        ds2 = WFData(ds.X[keep], ds.Y, ds.price, ds.r1)
        wf = walk_forward(ds2, [Naive(), XGBoostModel()], h, start, min_train=min_train, verbose=False)
        r = evaluate_table(wf, ["XGBoost"], h).loc["XGBoost"]
        rows.append({"Bỏ nhóm": g, "RMSE": r.RMSE, "TheilU": r.TheilU, "DirAcc_%": r["DirAcc_%"],
                     "Δ RMSE khi bỏ": r.RMSE - base.RMSE})
    return pd.DataFrame(rows)


def final_forecast(ds: WFData, start: int, h: int, models, state, as_of_idx: int) -> dict:
    """Huấn luyện trên toàn bộ dữ liệu có nhãn rồi dự báo từ hàng mới nhất."""
    train_idx = np.arange(start, len(ds.X) - h)
    preds, fitted = {}, {}
    for m in models:
        m.fit(ds, train_idx, h)
        preds[m.name] = float(m.predict(ds, np.array([as_of_idx]), h)[0])
        fitted[m.name] = m
    sigma_now = _sigma_series(ds.price.to_numpy()[: as_of_idx + 1], h, 63)[-1]
    res = apply_state(preds, state, h=h, sigma_now=sigma_now)
    res["raw"] = preds
    # SHAP cho XGBoost
    xgb = fitted.get("XGBoost")
    if xgb is not None:
        Xrecent = ds.X.iloc[max(start, as_of_idx - 249): as_of_idx + 1]
        sv = shap_values(xgb.model, Xrecent)
        res["shap_top"] = explain_row(sv.iloc[-1], ds.X.iloc[as_of_idx])
        res["shap_base_pct"] = sv.attrs["base_value"]
        res["shap_global"] = global_importance(sv).to_dict("records")
        sv.to_csv(DATA_PROCESSED / f"shap_recent_h{h}.csv")
    return res


def what_to_watch(ds: WFData, idx: int, shap_global: list[dict]) -> list[dict]:
    """Biến số cần theo dõi: biến quan trọng trong mô hình + đang ở mức bất thường."""
    feats = [d["feature"] for d in shap_global[:10]]
    for f in ["premium_pct", "usdvnd_ret_21d", "xau_ret_5d", "dxy_ret_5d", "us10y_chg_21d", "vix"]:
        if f not in feats:
            feats.append(f)
    hist = ds.X.iloc[max(0, idx - 252): idx + 1]
    out = []
    for f in feats:
        s = hist[f].dropna()
        if len(s) < 30 or pd.isna(ds.X[f].iloc[idx]):
            continue
        z = (ds.X[f].iloc[idx] - s.mean()) / (s.std() + 1e-12)
        out.append({"feature": f, "label": label(f), "value": float(ds.X[f].iloc[idx]),
                    "z_1y": float(z), "unusual": bool(abs(z) > 1.5),
                    "in_model_top10": f in feats[:10]})
    return sorted(out, key=lambda d: -abs(d["z_1y"]))


def _md_table(df: pd.DataFrame, fmt: str = "{:.3f}") -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join([df.index.name or ""] + cols) + " |",
             "|" + "---|" * (len(cols) + 1)]
    for i, r in df.iterrows():
        cells = [str(int(v)) if isinstance(v, (int, np.integer)) or (isinstance(v, (float, np.floating)) and v == v and float(v).is_integer() and abs(v) >= 100) else
                 fmt.format(v) if isinstance(v, (float, np.floating)) and v == v else
                 ("–" if isinstance(v, float) else str(v)) for v in r.values]
        lines.append("| " + " | ".join([str(i)] + cells) + " |")
    return "\n".join(lines)


def run(collect: bool = True, include_lstm: bool = True, do_ablation: bool = True,
        do_eda: bool = True, evening_check: bool = True) -> dict:
    t0 = time.time()
    from vngold.data.process import build_dataset
    if collect:
        from vngold.data.collect import collect_all
        collect_all()
    df = build_dataset()
    print(f"Dataset: {len(df)} phiên, {df.index.min():%d/%m/%Y} -> {df.index.max():%d/%m/%Y}")

    results = {"generated_at": datetime.now().isoformat(timespec="seconds"),
               "as_of": f"{df.index[-1]:%Y-%m-%d}", "targets": {}}

    ds, start = _prepare(df, "sjc_sell")
    if do_eda:
        from vngold.eda import run_eda
        results["eda"] = run_eda(df, ds.X, ds.Y)

    report = ["# Phase 2 – Đánh giá mô hình (walk-forward)\n",
              f"Dữ liệu tới {df.index[-1]:%d/%m/%Y}. Thời điểm phát hành dự báo: sáng sớm giờ VN "
              "(sau khi phiên Mỹ đóng cửa, trước khi niêm yết giá trong ngày). "
              "Huấn luyện lại mỗi 21 phiên, cửa sổ mở rộng, chỉ học trên nhãn đã biết.\n",
              "Chỉ số giá tính bằng **triệu VND/lượng**. TheilU = RMSE / RMSE(Naive) (<1 là tốt hơn Naive). "
              "DM_p: p-value kiểm định Diebold–Mariano so với Naive.\n"]

    targets = [("sjc_sell", 500, include_lstm), ("ring_sell", 250, False)]
    for target, min_train, lstm in targets:
        if target != "sjc_sell":
            ds, start = _prepare(df, target)
        tinfo = {"name": TARGET_NAMES[target], "last_price": float(ds.price.iloc[-1]),
                 "horizons": {}}
        report.append(f"\n## {TARGET_NAMES[target]}\n")
        print(f"== Backtest {target}")
        for h, hname in HORIZONS.items():
            models = build_models(target, h, lstm, df, ds)
            if len(ds.X) - start - min_train < 60 + h:
                continue
            wf, on, st, table = backtest(ds, start, h, models, min_train)
            wf.to_csv(DATA_PROCESSED / f"backtest_{target}_h{h}.csv")
            with open(MODELS_DIR / f"online_state_{target}_h{h}.pkl", "wb") as f:
                pickle.dump(st, f)
            table.round(4).to_csv(REPORTS / f"metrics_{target}_h{h}.csv")
            report.append(f"\n### Kỳ hạn {hname} (h = {h} phiên) – kiểm định {wf.index[0]:%m/%Y}–{wf.index[-1]:%m/%Y}\n")
            cols = ["MAE", "RMSE", "MAPE_%", "TheilU", "DM_p", "DirAcc_%", "DirBase_%", "DirEdge_pp", "Dir_p", "N"]
            report.append(_md_table(table[cols]))
            edge = has_edge(table)
            report.append(f"\nKhoảng tin cậy 90% bao phủ thực tế: **{table.attrs['coverage90'] * 100:.1f}%** · "
                          f"80%: **{table.attrs['coverage80'] * 100:.1f}%** · Brier score P(tăng): "
                          f"{table.attrs['brier_up']:.3f} (skill so với tần suất lịch sử: "
                          f"{table.attrs['brier_skill']:+.3f})\n")
            report.append("**Kết luận:** " + (
                "Ensemble có lợi thế có ý nghĩa thống kê so với Naive → công bố dự báo điểm.\n" if edge else
                "Ensemble **không** vượt Naive có ý nghĩa thống kê → dashboard chỉ công bố khoảng tin cậy "
                "và xác suất, điểm trung tâm = giá hiện tại (Naive).\n"))
            lk = table.attrs.get("locked")
            if lk is not None:
                report.append(f"\n*Giai đoạn khoá (sau {LOCK_DATE}, chưa từng dùng để chỉnh tham số):* "
                              f"bao phủ 90% = {table.attrs['locked_cov90'] * 100:.1f}%\n")
                report.append(_md_table(lk[["RMSE", "TheilU", "DM_p", "DirAcc_%", "DirBase_%", "DirEdge_pp", "N"]]))
            if do_ablation:
                oa = online_ablation(wf, [m.name for m in models], h)
                oa.to_csv(REPORTS / f"online_ablation_{target}_h{h}.csv", index=False)
                report.append("\n*Lớp tự học – đóng góp từng thành phần (cùng dự báo walk-forward):*\n")
                report.append(_md_table(oa.set_index("Biến thể")))

            fresh = build_models(target, h, lstm, df, ds)
            fc = final_forecast(ds, start, h, fresh, st, len(ds.X) - 1)
            p0 = float(ds.price.iloc[-1])
            target_date = ds.X.index[-1] + pd.offsets.BDay(h)
            best = table.drop(index=["Ensemble_raw"], errors="ignore")["RMSE"].idxmin()
            if not edge:
                # không có lợi thế: dời khoảng & xác suất về quanh giá hiện tại (Naive)
                shift = -fc["ensemble"]
                for k in ("lo", "hi", "lo80", "hi80"):
                    fc[k] += shift
                R0 = np.asarray(st.resid)
                fc["p_up"], fc["p_down"] = float(np.mean(R0 > 0)), float(np.mean(R0 < 0))
                fc["model_ensemble"], fc["ensemble"] = fc["ensemble"], 0.0
            tinfo["horizons"][str(h)] = {
                "label": hname, "target_date": f"{target_date:%Y-%m-%d}",
                "has_edge": edge,
                "model_return_pct": fc.get("model_ensemble", fc["ensemble"]) * 100,
                "pred_return_pct": fc["ensemble"] * 100,
                "pred_price": p0 * np.exp(fc["ensemble"]),
                "lo90": p0 * np.exp(fc["lo"]), "hi90": p0 * np.exp(fc["hi"]),
                "lo80": p0 * np.exp(fc["lo80"]), "hi80": p0 * np.exp(fc["hi80"]),
                "p_up": fc["p_up"], "p_down": fc["p_down"],
                "weights": fc["weights"],
                "models": {m: {"return_pct": v * 100, "price": p0 * np.exp(v),
                               "corrected_price": p0 * np.exp(fc["corrected"][m])}
                           for m, v in fc["raw"].items()},
                "shap_top": fc.get("shap_top", []), "shap_global": fc.get("shap_global", []),
                "backtest": {"table": table.round(4).reset_index().to_dict("records"),
                             "coverage90": table.attrs["coverage90"],
                             "coverage80": table.attrs["coverage80"],
                             "best_model": best,
                             "ensemble_theilU": float(table.loc["Ensemble", "TheilU"]),
                             "ensemble_diracc": float(table.loc["Ensemble", "DirAcc_%"]),
                             "dir_base": float(table.loc["Ensemble", "DirBase_%"]),
                             "dir_edge_pp": float(table.loc["Ensemble", "DirEdge_pp"]),
                             "ensemble_dm_p": float(table.loc["Ensemble", "DM_p"]),
                             "brier_skill": table.attrs["brier_skill"],
                             "locked": None if table.attrs.get("locked") is None else {
                                 "from": LOCK_DATE,
                                 "ensemble_theilU": float(table.attrs["locked"].loc["Ensemble", "TheilU"]),
                                 "ensemble_dm_p": float(table.attrs["locked"].loc["Ensemble", "DM_p"]),
                                 "ensemble_diracc": float(table.attrs["locked"].loc["Ensemble", "DirAcc_%"]),
                                 "dir_base": float(table.attrs["locked"].loc["Ensemble", "DirBase_%"]),
                                 "coverage90": table.attrs["locked_cov90"],
                                 "n": int(table.attrs["locked"].loc["Ensemble", "N"])},
                             "start": f"{wf.index[0]:%Y-%m-%d}"},
            }
            if target == "sjc_sell" and h == 1:
                tinfo["watch"] = what_to_watch(ds, len(ds.X) - 1, fc.get("shap_global", []))
        from vngold.outlook import long_horizon_outlook
        tinfo["outlook"] = long_horizon_outlook(df, target)
        results["targets"][target] = tinfo

    # Thí nghiệm: phát hành cuối ngày (không có phiên Mỹ đêm đó) -> cho thấy giá trị thông tin
    if evening_check:
        print("== Kiểm tra chế độ phát hành cuối ngày (evening)")
        df_e = build_dataset(save=False, issue_time="evening")
        ds_e, start_e = _prepare(df_e, "sjc_sell")
        wf_e = walk_forward(ds_e, [Naive(), LinearRegressionModel(), XGBoostModel()], 1, start_e,
                            min_train=500, verbose=False)
        te = evaluate_table(wf_e, ["Naive", "LinearRegression", "XGBoost"], 1)
        report.append("\n## Thí nghiệm: nếu phát hành dự báo vào cuối ngày (h = 1)\n")
        report.append("Khi chưa biết diễn biến phiên Mỹ đêm đó, lợi thế gần như biến mất – "
                      "phần lớn khả năng dự báo ngắn hạn đến từ độ trễ truyền dẫn giá thế giới vào giá trong nước.\n")
        report.append(_md_table(te[["RMSE", "DirAcc_%", "TheilU", "DM_p"]]))
        results["evening_check"] = te.round(4).reset_index().to_dict("records")

    if do_ablation:
        print("== Ablation nhóm đặc trưng")
        ds, start = _prepare(df, "sjc_sell")
        report.append("\n## Kiểm tra từng nhóm đặc trưng (XGBoost, bỏ lần lượt từng nhóm)\n")
        report.append("Δ RMSE > 0 nghĩa là bỏ nhóm đó làm mô hình tệ đi ⇒ nhóm có giá trị dự báo.\n")
        abl = {}
        for h in (1, 5):
            a = ablation(ds, start, h, 500)
            a.to_csv(REPORTS / f"ablation_h{h}.csv", index=False)
            report.append(f"\n### h = {h}\n")
            report.append(_md_table(a.set_index("Bỏ nhóm")))
            abl[str(h)] = a.round(4).to_dict("records")
        results["ablation"] = abl

    # Nhật ký dự báo + tự chấm điểm
    from vngold.tracking import append_predictions, score_log
    rows = []
    for target, tinfo in results["targets"].items():
        for h, r in tinfo["horizons"].items():
            for name, price, lo, hi in [("Ensemble", r["pred_price"], r["lo90"], r["hi90"])] + \
                    [(m, v["price"], np.nan, np.nan) for m, v in r["models"].items()]:
                ens = name == "Ensemble"
                rows.append({"target": target, "as_of": results["as_of"], "h": int(h),
                             "target_date": r["target_date"], "model": name,
                             "price_at_issue": tinfo["last_price"], "pred_price": price,
                             "lo": lo, "hi": hi, "p_up": r["p_up"] if ens else np.nan,
                             "issued_at": results["generated_at"],
                             "lo80": r.get("lo80", np.nan) if ens else np.nan,
                             "hi80": r.get("hi80", np.nan) if ens else np.nan})
    append_predictions(rows)
    log = score_log(df)
    done = log[log["actual_price"].notna()] if len(log) else log
    results["live_track_record"] = {
        "n_scored": int(len(done)),
        "ensemble_mape_%": float(done.loc[done.model == "Ensemble", "abs_pct_error"].mean()) if len(done) else None,
    }

    results["runtime_sec"] = round(time.time() - t0, 1)
    (REPORTS / "02_model_evaluation.md").write_text("\n".join(report), encoding="utf-8")
    with open(DATA_PROCESSED / "forecast.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=float)
    print(f"Xong trong {results['runtime_sec']}s -> data/processed/forecast.json, reports/")
    return results
