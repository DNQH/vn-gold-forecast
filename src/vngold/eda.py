"""Phase 1 - Exploratory Data Analysis: biểu đồ + thống kê -> reports/."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller

from vngold.config import FIGURES, REPORTS
from vngold.features import POLICY_EVENTS

plt.rcParams.update({"figure.dpi": 110, "axes.grid": True, "grid.alpha": 0.3,
                     "axes.spines.top": False, "axes.spines.right": False})
EVENT_TXT = {"2024-04-22": "NHNN đấu thầu", "2024-06-03": "NHNN bán trực tiếp",
             "2025-10-10": "NĐ 232/2025"}


def _events(ax):
    for d in POLICY_EVENTS:
        ax.axvline(pd.Timestamp(d), color="#b45309", ls="--", lw=0.8)
        ax.text(pd.Timestamp(d), ax.get_ylim()[1], EVENT_TXT[d], rotation=90, va="top",
                ha="right", fontsize=7, color="#b45309")


def run_eda(df: pd.DataFrame, X: pd.DataFrame, Y: pd.DataFrame) -> dict:
    out = {}
    # 1. Giá
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.plot(df.index, df["sjc_sell"], label="SJC (bán ra)", lw=1.2, color="#b91c1c")
    ax.plot(df.index, df["ring_sell"], label="Nhẫn 9999 (bán ra)", lw=1.0, color="#ca8a04")
    ax.plot(df.index, df["world_vnd"], label="Thế giới quy đổi (XAU×USDVND)", lw=1.0, color="#1d4ed8")
    ax.set_ylabel("triệu VND / lượng")
    ax.set_title("Giá vàng SJC, vàng nhẫn và giá thế giới quy đổi")
    ax.legend(loc="upper left")
    _events(ax)
    fig.tight_layout(); fig.savefig(FIGURES / "01_prices.png"); plt.close(fig)

    # 2. Premium
    fig, ax = plt.subplots(figsize=(11, 3.6))
    ax.fill_between(df.index, df["premium_pct"] * 100, color="#b91c1c", alpha=0.25)
    ax.plot(df.index, df["premium_pct"] * 100, color="#b91c1c", lw=1, label="SJC")
    ax.plot(df.index, df["ring_premium_pct"] * 100, color="#ca8a04", lw=1, label="Nhẫn 9999")
    ax.set_ylabel("% trên giá thế giới")
    ax.set_title("Domestic Gold Premium = giá trong nước / giá thế giới quy đổi − 1")
    ax.legend(loc="upper left")
    _events(ax)
    fig.tight_layout(); fig.savefig(FIGURES / "02_premium.png"); plt.close(fig)

    # 3. Phân phối lợi suất
    r_sjc = np.log(df["sjc_sell"]).diff().dropna()
    r_w = np.log(df["world_vnd"]).diff().dropna()
    fig, ax = plt.subplots(figsize=(8, 3.6))
    bins = np.linspace(-0.05, 0.05, 101)
    ax.hist(r_w, bins=bins, alpha=0.5, label="Thế giới quy đổi", color="#1d4ed8", density=True)
    ax.hist(r_sjc, bins=bins, alpha=0.5, label="SJC", color="#b91c1c", density=True)
    ax.set_title("Phân phối lợi suất ngày")
    ax.legend()
    fig.tight_layout(); fig.savefig(FIGURES / "03_return_dist.png"); plt.close(fig)

    # 4. Tương quan chéo trễ (lead-lag): SJC hôm nay phản ứng với thế giới các ngày trước
    lags = range(-3, 6)
    cc = [r_sjc.corr(r_w.shift(k)) for k in lags]
    fig, ax = plt.subplots(figsize=(7, 3.4))
    ax.bar(list(lags), cc, color=["#94a3b8" if k < 0 else "#1d4ed8" for k in lags])
    ax.set_xlabel("k (corr của lợi suất SJC ngày t với lợi suất thế giới ngày t−k)")
    ax.set_title("Truyền dẫn giá thế giới → SJC theo độ trễ")
    fig.tight_layout(); fig.savefig(FIGURES / "04_leadlag.png"); plt.close(fig)
    out["leadlag_corr"] = dict(zip(map(int, lags), map(float, cc)))

    # 5. Tương quan trượt 120 phiên
    roll = r_sjc.rolling(120).corr(r_w)
    fig, ax = plt.subplots(figsize=(11, 3.2))
    ax.plot(roll.index, roll, color="#334155")
    ax.set_title("Tương quan trượt 120 phiên giữa lợi suất SJC và giá thế giới quy đổi")
    _events(ax)
    fig.tight_layout(); fig.savefig(FIGURES / "05_rolling_corr.png"); plt.close(fig)

    # 6. Tương quan đặc trưng với mục tiêu
    corr = X.corrwith(Y["y_1"]).dropna().sort_values(key=abs, ascending=False).head(20)
    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.barh(corr.index[::-1], corr.values[::-1],
            color=["#15803d" if v > 0 else "#b91c1c" for v in corr.values[::-1]])
    ax.set_title("Top 20 đặc trưng tương quan với lợi suất SJC phiên kế tiếp")
    fig.tight_layout(); fig.savefig(FIGURES / "06_feature_corr.png"); plt.close(fig)
    out["top_corr_y1"] = corr.round(4).to_dict()

    # 7. Kiểm định tính dừng
    out["adf_log_price_p"] = float(adfuller(np.log(df["sjc_sell"]).dropna())[1])
    out["adf_return_p"] = float(adfuller(r_sjc)[1])
    out["zero_change_share"] = float((r_sjc == 0).mean())
    out["sjc_daily_vol_%"] = float(r_sjc.std() * 100)
    out["world_daily_vol_%"] = float(r_w.std() * 100)
    out["kurtosis_sjc"] = float(r_sjc.kurt())
    out["premium_now_%"] = float(df["premium_pct"].iloc[-1] * 100)
    out["premium_mean_%"] = float(df["premium_pct"].mean() * 100)
    out["n_days"] = int(len(df))
    out["period"] = f"{df.index.min():%d/%m/%Y} – {df.index.max():%d/%m/%Y}"
    out["source_counts"] = df["sjc_source"].value_counts().to_dict()

    md = [
        "# Phase 1 – EDA: Thị trường vàng Việt Nam\n",
        f"- Giai đoạn: **{out['period']}** ({out['n_days']} phiên làm việc)",
        f"- Nguồn giá SJC theo số phiên: {out['source_counts']}",
        f"- Biến động ngày: SJC **{out['sjc_daily_vol_%']:.2f}%** vs thế giới quy đổi "
        f"**{out['world_daily_vol_%']:.2f}%**; độ nhọn (kurtosis) SJC = {out['kurtosis_sjc']:.1f} (đuôi dày)",
        f"- {out['zero_change_share'] * 100:.0f}% số phiên giá SJC không đổi",
        f"- ADF: log giá p = {out['adf_log_price_p']:.3f} (không dừng) · lợi suất p = "
        f"{out['adf_return_p']:.2g} (dừng) ⇒ dự báo **lợi suất**, không dự báo trực tiếp giá",
        f"- Premium hiện tại **{out['premium_now_%']:.1f}%** (trung bình giai đoạn {out['premium_mean_%']:.1f}%)",
        "- Tương quan lợi suất SJC(t) với thế giới(t−k): "
        + ", ".join(f"k={k}: {v:.2f}" for k, v in out["leadlag_corr"].items()),
        "\n![](figures/01_prices.png)\n![](figures/02_premium.png)\n![](figures/04_leadlag.png)",
        "![](figures/05_rolling_corr.png)\n![](figures/03_return_dist.png)\n![](figures/06_feature_corr.png)",
    ]
    (REPORTS / "01_eda.md").write_text("\n".join(md), encoding="utf-8")
    return out
