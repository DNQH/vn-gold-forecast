"""Cơ chế "tự nhìn lại dự đoán để học hỏi" (self-correcting forecaster).

Sau mỗi lần dự báo, khi giá thực tế của ngày đích được công bố (sau h phiên),
hệ thống so sánh dự báo với thực tế và cập nhật cho lần dự báo sau:

1. **Hiệu chỉnh độ lệch có kiểm soát** - mỗi mô hình có EWMA sai số (bias). Bản hiệu chỉnh
   chỉ được dùng khi chính nó đã chứng minh tốt hơn bản thô trên các dự báo đã đáo hạn
   (so EWMSE của hai bản) -> không "sửa" khi việc sửa làm tệ đi.
2. **Trọng số theo kỹ năng so với Naive** - skill_m = EWMSE_m / EWMSE_Naive (<1 là hơn Naive).
   w_m ∝ exp(-η·(skill_m - min skill)); mô hình có skill > `prune_above` bị loại tạm thời.
   (Bản cũ w ∝ 1/EWMSE cho trọng số gần như chia đều ~0.2 vì MSE các mô hình sát nhau.)
3. **Khoảng tin cậy thích ứng theo biến động + ACI** - sai số được chuẩn hoá theo độ biến động
   gần đây của giá (63 phiên), phân vị nhân lại với biến động hiện tại; mức alpha tự điều
   chỉnh (Adaptive Conformal Inference, Gibbs & Candès 2021) với bước γ·√h.
4. **Huấn luyện lại định kỳ** (walk-forward) - nằm ở evaluation.walk_forward / models.

Quan trọng: tại ngày t, chỉ sai số của những dự báo đã "đáo hạn" (lập tại t-h trở về
trước) mới được dùng -> không nhìn trộm tương lai.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class OnlineConfig:
    bias_halflife: float = 20.0
    bias_shrink: float = 0.5
    bias_gate: bool = True          # chỉ hiệu chỉnh khi đã chứng minh có ích
    weight_halflife: float = 60.0   # nhân với √h (sai số kỳ hạn dài chồng lấn -> cần cửa sổ dài hơn)
    weighting: str = "skill"        # "skill" | "inverse_mse" | "equal"
    eta: float = 20.0               # độ "sắc" của trọng số theo skill, chia cho √h
    prune_above: float = 1.05       # loại mô hình kém Naive > 5% (EWMSE trượt)
    resid_window: int = 250
    alpha: float = 0.10             # khoảng 90%
    aci_gamma: float = 0.01         # bước cập nhật mức alpha (ACI cổ điển)
    scale_gamma: float = 0.02       # bước cập nhật hệ số nới khoảng k (ACI nhân)
    vol_scale: bool = False         # chuẩn hoá sai số theo biến động (thử nghiệm: không giúp)
    vol_window: int = 63
    exclude_from_ensemble: tuple = ("MovingAverage",)


@dataclass
class OnlineState:
    bias: dict = field(default_factory=dict)
    use_bias: dict = field(default_factory=dict)
    ewmse: dict = field(default_factory=dict)
    weights: dict = field(default_factory=dict)
    resid: list = field(default_factory=list)   # sai số (đã chuẩn hoá nếu vol_scale)
    alpha_t: float = 0.10
    sigma: float = 1.0                          # biến động tại thời điểm cuối
    k: float = 1.0                              # hệ số nới khoảng tin cậy 90%
    k80: float = 1.0                            # hệ số nới khoảng tin cậy 80%
    cfg: OnlineConfig | None = None


def _ew_update(old, x, hl):
    a = 1 - 0.5 ** (1 / hl)
    return x if old is None or np.isnan(old) else (1 - a) * old + a * x


def _sigma_series(price: np.ndarray, h: int, window: int) -> np.ndarray:
    """Độ lệch chuẩn lợi suất ngày trong `window` phiên gần nhất × √h (chỉ dùng quá khứ)."""
    r = pd.Series(np.log(price)).diff()
    sd = r.rolling(window, min_periods=20).std()
    floor = sd.expanding().median() * 0.5          # SJC có giai đoạn giá đứng yên -> sàn
    sd = np.maximum(sd, floor)
    return (sd * np.sqrt(h)).to_numpy()


def _weights(ewmse: dict, ens_models: list[str], avail: list[str], cfg: OnlineConfig,
             h: int = 1) -> dict:
    cand = [m for m in ens_models if m in avail]
    known = {m: ewmse[m] for m in cand if ewmse.get(m) == ewmse.get(m) and ewmse[m] > 0}
    if not known or len(known) < len(cand) or cfg.weighting == "equal":
        return {m: 1 / len(cand) for m in cand}
    if cfg.weighting == "inverse_mse":
        inv = {m: 1 / v for m, v in known.items()}
        tot = sum(inv.values())
        return {m: v / tot for m, v in inv.items()}
    ref = known.get("Naive", np.median(list(known.values())))
    skill = {m: v / ref for m, v in known.items()}
    keep = {m: s for m, s in skill.items() if s <= cfg.prune_above or m == "Naive"}
    smin = min(keep.values())
    eta = cfg.eta / np.sqrt(h)
    raw = {m: np.exp(-eta * (s - smin)) for m, s in keep.items()}
    tot = sum(raw.values())
    return {m: v / tot for m, v in raw.items()}


def run_online(wf: pd.DataFrame, models: list[str], h: int,
               cfg: OnlineConfig = OnlineConfig()) -> tuple[pd.DataFrame, OnlineState]:
    """Chạy tuần tự trên kết quả walk-forward, trả về dự báo đã hiệu chỉnh + trạng thái cuối."""
    n = len(wf)
    P = wf[models].to_numpy()
    y = wf["actual"].to_numpy()
    sig = _sigma_series(wf["price_t"].to_numpy(), h, cfg.vol_window) if cfg.vol_scale \
        else np.ones(n)
    gamma = cfg.aci_gamma
    hl_w = cfg.weight_halflife * np.sqrt(h)
    log_k80 = 0.0
    log_k = 0.0   # ACI nhân: khoảng = k · phân vị sai số; k tăng khi thực tế rơi ngoài khoảng
    bias = {m: np.nan for m in models}
    mse_raw = {m: np.nan for m in models}
    mse_cor = {m: np.nan for m in models}
    use_bias = {m: False for m in models}
    ewmse = {m: np.nan for m in models}
    ens_models = [m for m in models if m not in cfg.exclude_from_ensemble]
    out = {k: np.full(n, np.nan) for k in
           ["Ensemble_raw", "Ensemble", "lo", "hi", "lo80", "hi80", "p_up", "alpha_t"]}
    candidate = {m: np.full(n, np.nan) for m in models}   # bản đã hiệu chỉnh (luôn tính)
    used = {m: np.full(n, np.nan) for m in models}        # bản thực sự dùng
    ens_hist = np.full(n, np.nan)
    resid: list[float] = []
    alpha_t = cfg.alpha
    w_hist = []

    for t in range(n):
        # 1) dự báo lập tại t-h vừa đáo hạn -> học từ sai số của nó
        j = t - h
        if j >= 0 and not np.isnan(y[j]):
            for k, m in enumerate(models):
                if np.isnan(P[j, k]):
                    continue
                e = y[j] - P[j, k]
                mse_raw[m] = _ew_update(mse_raw[m], e ** 2, hl_w)
                if not np.isnan(candidate[m][j]):
                    mse_cor[m] = _ew_update(mse_cor[m], (y[j] - candidate[m][j]) ** 2,
                                            hl_w)
                bias[m] = _ew_update(bias[m], e, cfg.bias_halflife)
                e_u = y[j] - used[m][j] if not np.isnan(used[m][j]) else e
                ewmse[m] = _ew_update(ewmse[m], e_u ** 2, hl_w)
                use_bias[m] = (not cfg.bias_gate) or (mse_cor[m] == mse_cor[m]
                                                      and mse_cor[m] < mse_raw[m])
            if not np.isnan(ens_hist[j]) and not np.isnan(sig[j]):
                r = (y[j] - ens_hist[j]) / sig[j]
                if not np.isnan(out["lo"][j]):
                    miss = float(y[j] < out["lo"][j] or y[j] > out["hi"][j])
                    alpha_t = float(np.clip(alpha_t + gamma * (cfg.alpha - miss), 0.01, 0.5))
                    log_k = float(np.clip(log_k + cfg.scale_gamma * (miss - cfg.alpha), -0.7, 1.4))
                    miss80 = float(y[j] < out["lo80"][j] or y[j] > out["hi80"][j])
                    log_k80 = float(np.clip(log_k80 + cfg.scale_gamma * (miss80 - 0.2), -0.7, 1.4))
                resid.append(r)
                resid = resid[-cfg.resid_window:]

        # 2) dự báo đã hiệu chỉnh độ lệch (chỉ dùng khi đã chứng minh có ích)
        for k, m in enumerate(models):
            b = 0.0 if np.isnan(bias[m]) else bias[m]
            candidate[m][t] = P[t, k] + cfg.bias_shrink * b
            used[m][t] = candidate[m][t] if use_bias[m] else P[t, k]

        # 3) trọng số ensemble theo kỹ năng gần đây
        avail = [m for m in ens_models if not np.isnan(P[t, models.index(m)])]
        w = _weights(ewmse, ens_models, avail, cfg, h)
        w_hist.append(w)
        out["Ensemble_raw"][t] = np.nanmean([P[t, models.index(m)] for m in ens_models])
        ens = sum(w[m] * used[m][t] for m in w)
        ens_hist[t] = ens
        out["Ensemble"][t] = ens

        # 4) khoảng tin cậy & xác suất tăng
        if len(resid) >= 30 and not np.isnan(sig[t]):
            R = np.asarray(resid) * sig[t]
            k = np.exp(log_k)
            out["lo"][t] = ens + k * np.quantile(R, alpha_t / 2)
            out["hi"][t] = ens + k * np.quantile(R, 1 - alpha_t / 2)
            k80 = np.exp(log_k80)
            out["lo80"][t] = ens + k80 * np.quantile(R, 0.10)
            out["hi80"][t] = ens + k80 * np.quantile(R, 0.90)
            out["p_up"][t] = float(np.mean(ens + R > 0))
        out["alpha_t"][t] = alpha_t

    res = pd.DataFrame(out, index=wf.index)
    for m in models:
        res[f"{m}_corr"] = used[m]
    res["actual"] = wf["actual"].to_numpy()
    res["price_t"] = wf["price_t"].to_numpy()
    st = OnlineState(bias=bias, use_bias=use_bias, ewmse=ewmse,
                     weights=w_hist[-1] if w_hist else {}, resid=resid, alpha_t=alpha_t,
                     sigma=float(sig[-1]) if n else 1.0, k=float(np.exp(log_k)),
                     k80=float(np.exp(log_k80)), cfg=cfg)
    res.attrs["weights_history"] = w_hist
    return res, st


def apply_state(preds: dict[str, float], st: OnlineState, h: int = 1,
                sigma_now: float | None = None, cfg: OnlineConfig | None = None) -> dict:
    """Áp trạng thái học được vào dự báo mới (dùng khi chạy dự báo thực tế)."""
    cfg = cfg or st.cfg or OnlineConfig()
    corr = {}
    for m, p in preds.items():
        b = st.bias.get(m, np.nan)
        corr[m] = p + cfg.bias_shrink * b if st.use_bias.get(m) and b == b else p
    ens_models = [m for m in preds if m not in cfg.exclude_from_ensemble]
    w = _weights(st.ewmse, ens_models, ens_models, cfg, h)
    ens = sum(w[m] * corr[m] for m in w)
    s = sigma_now if sigma_now is not None and sigma_now == sigma_now else st.sigma
    R0 = np.asarray(st.resid) * (s if cfg.vol_scale else 1.0)
    R = R0 * st.k
    return {
        "corrected": corr, "weights": w, "ensemble": ens,
        "lo": ens + np.quantile(R, st.alpha_t / 2), "hi": ens + np.quantile(R, 1 - st.alpha_t / 2),
        "lo80": ens + st.k80 * np.quantile(R0, 0.10), "hi80": ens + st.k80 * np.quantile(R0, 0.90),
        "p_up": float(np.mean(ens + R0 > 0)), "p_down": float(np.mean(ens + R0 < 0)),
        "alpha_t": st.alpha_t,
    }


def online_ablation(wf: pd.DataFrame, models: list[str], h: int) -> pd.DataFrame:
    """So sánh từng thành phần của lớp tự học trên cùng dự báo walk-forward."""
    from vngold.evaluation import evaluate_table
    variants = {
        "Trung bình thường (không tự học)": OnlineConfig(bias_shrink=0.0, weighting="equal", vol_scale=False),
        "Chỉ hiệu chỉnh độ lệch": OnlineConfig(weighting="equal", vol_scale=False),
        "Chỉ trọng số theo kỹ năng": OnlineConfig(bias_shrink=0.0, vol_scale=False),
        "Trọng số 1/MSE (bản cũ)": OnlineConfig(weighting="inverse_mse", bias_gate=False, vol_scale=False),
        "Đầy đủ (bản mới)": OnlineConfig(),
        "Đầy đủ, không nới khoảng (k=1)": OnlineConfig(scale_gamma=0.0),
    }
    rows = []
    for name, cfg in variants.items():
        on, _ = run_online(wf, models, h, cfg)
        tmp = wf[["actual", "price_t"]].copy()
        tmp["E"] = on["Ensemble"]
        r = evaluate_table(tmp, ["E"], h).loc["E"]
        m = on["lo"].notna() & on["actual"].notna()
        cov = ((on.actual >= on.lo) & (on.actual <= on.hi))[m].mean()
        rows.append({"Biến thể": name, "RMSE": r.RMSE, "TheilU": r.TheilU,
                     "DirAcc_%": r["DirAcc_%"], "Bao phủ 90%": cov * 100})
    return pd.DataFrame(rows)
