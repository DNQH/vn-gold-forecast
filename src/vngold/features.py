"""Module 3 - Feature Engineering.

Mọi đặc trưng tại hàng t chỉ dùng thông tin có được đến hết ngày t (giờ VN).
Mục tiêu: lợi suất log của giá trong h phiên tới  r_{t,h} = ln P_{t+h} - ln P_t
(tương đương % thay đổi), sau đó quy đổi lại thành giá  P̂_{t+h} = P_t · e^{r̂}.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Ngày vía Thần Tài (mùng 10 tháng Giêng âm lịch) - đỉnh cầu vàng trong năm ở VN
THAN_TAI = pd.to_datetime([
    "2017-02-06", "2018-02-25", "2019-02-14", "2020-02-03", "2021-02-21",
    "2022-02-10", "2023-01-31", "2024-02-19", "2025-02-07", "2026-02-26", "2027-02-16",
])

# Các mốc chính sách quản lý thị trường vàng
POLICY_EVENTS = {
    "2024-04-22": 1,  # NHNN bắt đầu đấu thầu vàng miếng
    "2024-06-03": 2,  # NHNN bán vàng miếng trực tiếp qua 4 NH thương mại + SJC
    "2025-10-10": 3,  # Nghị định 232/2025/NĐ-CP có hiệu lực (bỏ độc quyền vàng miếng)
}


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    out = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    out = out.where(dn > 0, np.where(up > 0, 100.0, 50.0))
    return out


def _technical(p: pd.Series, prefix: str) -> dict[str, pd.Series]:
    lr = np.log(p).diff()
    ema12, ema26 = p.ewm(span=12, adjust=False).mean(), p.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    ma20, ma50 = p.rolling(20).mean(), p.rolling(50).mean()
    sd20 = p.rolling(20).std()
    return {
        f"{prefix}_rsi14": rsi(p, 14),
        f"{prefix}_macd": macd / p,
        f"{prefix}_macd_hist": (macd - signal) / p,
        f"{prefix}_ma20_gap": p / ma20 - 1,
        f"{prefix}_ma50_gap": p / ma50 - 1,
        f"{prefix}_ma20_50": ma20 / ma50 - 1,
        f"{prefix}_bb_pctb": (p - (ma20 - 2 * sd20)) / (4 * sd20).replace(0, np.nan),
        f"{prefix}_bb_width": 4 * sd20 / ma20,
        f"{prefix}_atr14": lr.abs().rolling(14).mean(),   # ATR xấp xỉ (không có high/low)
        f"{prefix}_roc10": p.pct_change(10),
        f"{prefix}_vol7": lr.rolling(7).std(),
        f"{prefix}_vol21": lr.rolling(21).std(),
    }


def build_features(df: pd.DataFrame, target: str = "sjc_sell") -> pd.DataFrame:
    f: dict[str, pd.Series] = {}
    p = df[target]
    lp = np.log(p)

    # --- Giá trong nước (động lượng, trễ)
    r1 = lp.diff()
    for k in (1, 2, 3, 4, 5):
        f[f"ret_lag{k}"] = r1.shift(k - 1)
    for w in (5, 10, 21, 63):
        f[f"ret_{w}d"] = lp.diff(w)
    f["days_since_change"] = (r1 != 0).cumsum().pipe(lambda c: c.groupby(c).cumcount())
    f.update(_technical(p, "dom"))
    f["spread_pct"] = (p - df[target.replace("sell", "buy")]) / p   # bid-ask spread

    # --- Nhóm 1: vàng thế giới (đã trễ 1 ngày do lệch múi giờ - xem process.py)
    lx = np.log(df["xau_usd"])
    for w in (1, 2, 5, 10, 21, 63):
        f[f"xau_ret_{w}d"] = lx.diff(w)
    f["xau_ret_lag1"] = lx.diff().shift(1)
    f.update({k: v for k, v in _technical(df["xau_usd"], "xau").items()
              if k in ("xau_rsi14", "xau_macd_hist", "xau_ma20_gap", "xau_ma50_gap",
                       "xau_vol21", "xau_bb_pctb")})
    f["gold_volume_z"] = (np.log1p(df["gold_volume"]) - np.log1p(df["gold_volume"]).rolling(63).mean()) \
        / np.log1p(df["gold_volume"]).rolling(63).std()
    f["silver_ret_5d"] = np.log(df["silver_usd"]).diff(5)
    f["gold_silver_ratio"] = df["xau_usd"] / df["silver_usd"]

    # --- Nhóm 2: vĩ mô
    lfx = np.log(df["usd_vnd"])
    for w in (1, 5, 21, 63):
        f[f"usdvnd_ret_{w}d"] = lfx.diff(w)
    ldxy = np.log(df["dxy"])
    for w in (1, 5, 21):
        f[f"dxy_ret_{w}d"] = ldxy.diff(w)
    f["us10y"] = df["us10y"]
    f["us10y_chg_5d"] = df["us10y"].diff(5)
    f["us10y_chg_21d"] = df["us10y"].diff(21)
    f["real_rate_10y"] = df["real_rate_10y"]
    f["real_rate_chg_21d"] = df["real_rate_10y"].diff(21)
    f["breakeven_10y"] = df["breakeven_10y"]
    f["fed_funds"] = df["fed_funds"]
    f["fed_funds_chg_63d"] = df["fed_funds"].diff(63)
    f["cpi_yoy"] = df["cpi_yoy"]
    f["unemployment_us"] = df["unemployment_us"]
    f["vix"] = df["vix"]
    f["vix_chg_5d"] = np.log(df["vix"]).diff(5)

    # --- Nhóm 3: thị trường trong nước - Domestic Gold Premium
    prem = (p / df["world_vnd"] - 1)
    f["premium_pct"] = prem
    for w in (1, 5, 21):
        f[f"premium_chg_{w}d"] = prem.diff(w)
    f["premium_z60"] = (prem - prem.rolling(60).mean()) / prem.rolling(60).std()
    f["premium_dev120"] = prem - prem.rolling(120).mean()
    # "độ trễ truyền dẫn": giá thế giới quy đổi đã đi bao xa mà giá trong nước chưa theo
    lw = np.log(df["world_vnd"])
    for w in (1, 5, 21):
        f[f"passthrough_gap_{w}d"] = lw.diff(w) - lp.diff(w)

    # --- Nhóm 4 (proxy tâm lý - dữ liệu tin tức/NLP để Phase 3)
    days_to = pd.Series(index=df.index, dtype=float)
    for d in df.index:
        nxt = THAN_TAI[THAN_TAI >= d]
        days_to[d] = (nxt[0] - d).days if len(nxt) else 365
    f["days_to_than_tai"] = days_to.clip(upper=60)
    # giai đoạn chính sách: one-hot (không phải biến thứ bậc 0-3)
    regime = pd.Series(0, index=df.index)
    for d, v in POLICY_EVENTS.items():
        regime[df.index >= pd.Timestamp(d)] = v
    for v in POLICY_EVENTS.values():
        f[f"policy_regime_{v}"] = (regime == v).astype(int)
    f["dow"] = pd.Series(df.index.dayofweek, index=df.index)

    X = pd.DataFrame(f, index=df.index)
    return X.replace([np.inf, -np.inf], np.nan)


def build_targets(df: pd.DataFrame, horizons, target: str = "sjc_sell") -> pd.DataFrame:
    """Nhãn y_h = ln P(t+h) - ln P(t). Nếu ngày t hoặc t+h thị trường trong nước
    không có giá thật (Tết, lễ - giá chỉ được điền tiếp) thì nhãn = NaN: không học và
    không chấm điểm trên lợi suất 0 giả."""
    lp = np.log(df[target])
    obs_col = f"{target}_observed"
    obs = df[obs_col].astype(bool) if obs_col in df else pd.Series(True, index=df.index)
    out = {}
    for h in horizons:
        y = lp.shift(-h) - lp
        ok = obs & obs.shift(-h, fill_value=False)
        out[f"y_{h}"] = y.where(ok | y.isna(), np.nan)
    return pd.DataFrame(out, index=df.index)
