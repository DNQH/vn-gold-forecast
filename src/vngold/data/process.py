"""Module 2 - Data Processing: làm sạch, ghép nguồn, đồng bộ thời gian.

Nguyên tắc chống rò rỉ dữ liệu (data leakage) theo *thời điểm có thông tin*:
  * Giá vàng trong nước ngày t (giờ VN) được chốt trong ngày t.
  * Phiên Mỹ ngày d đóng cửa ~ 4-5h sáng ngày d+1 giờ VN. Hàng t của bộ dữ liệu là
    "thông tin có tại thời điểm phát hành dự báo" (xem ISSUE_TIME trong config).
  * FRED daily: dùng sau 2 ngày; CPI/UNRATE: dùng sau ngày công bố ước lượng
    (xem FRED_SERIES trong config).
"""
from __future__ import annotations

import pandas as pd

from vngold.config import (DATA_PROCESSED, DATA_RAW, FRED_SERIES, ISSUE_TIME,
                           OZ_PER_LUONG, WORLD_LAG_DAYS, vn_today)


def _load_raw():
    yahoo = pd.read_csv(DATA_RAW / "yahoo.csv", index_col=0, parse_dates=True)
    fred = pd.read_csv(DATA_RAW / "fred.csv", index_col=0, parse_dates=True)
    cafef = pd.read_csv(DATA_RAW / "cafef.csv", index_col=0, parse_dates=True)
    ticks = pd.read_csv(DATA_RAW / "giavang_org_ticks.csv", parse_dates=["ts"])
    pnj = pd.read_csv(DATA_RAW / "giavang_org_pnj_gap.csv", parse_dates=["ts"])
    return yahoo, fred, cafef, ticks, pnj


def merge_domestic(giavang: pd.DataFrame, cafef: pd.DataFrame,
                   pnj: pd.DataFrame | None = None) -> pd.DataFrame:
    """Ưu tiên CafeF cho SJC từ khi có dữ liệu, giavang.org cho giai đoạn trước.

    Vàng nhẫn: dùng MỘT nguồn nhất quán là nhẫn PNJ 999.9 (CafeF, có từ 03/2024);
    nhẫn SJC 99,99 (giavang.org) chỉ lấp ngày CafeF thiếu. Trước đây hai thương hiệu
    xen kẽ theo ngày, tạo lợi suất giả ~0.1-1% mỗi lần đổi nguồn.
    """
    cols = ["sjc_buy", "sjc_sell", "ring_buy", "ring_sell"]
    g = giavang[cols].copy()
    c = cafef[cols].copy()
    out = g.combine_first(c)
    ring = ["ring_buy", "ring_sell"]
    out[ring] = c[ring].reindex(out.index).combine_first(out[ring])
    has_c_sjc = c["sjc_sell"].notna()
    out.loc[has_c_sjc[has_c_sjc].index, ["sjc_buy", "sjc_sell"]] = c.loc[has_c_sjc, ["sjc_buy", "sjc_sell"]]
    out["sjc_source"] = "giavang.org"
    out.loc[has_c_sjc[has_c_sjc].index, "sjc_source"] = "cafef"
    if pnj is not None:  # lấp khoảng trống 11/2024-02/2025 (SJC niêm yết tại PNJ)
        p = pnj[cols]
        missing = p.index.difference(out.dropna(subset=["sjc_sell"]).index)
        out = out.combine_first(p.loc[missing])
        out.loc[missing, "sjc_source"] = "pnj"
    return out.sort_index()


def drop_incomplete_days(df: pd.DataFrame, today=None) -> pd.DataFrame:
    """Chỉ giữ các ngày đã khép lại: bỏ mọi hàng có ngày >= hôm nay (giờ VN).

    Giá trong ngày hôm nay chưa chốt (và chưa có phiên Mỹ của ngày đó), nên không được
    coi là giá đóng cửa. Chỉ lọc ở bước dựng dataset; cache thô giữ nguyên.
    """
    today = vn_today() if today is None else pd.Timestamp(today).normalize()
    return df[df.index < today]


def _asof_join(grid: pd.DatetimeIndex, df: pd.DataFrame, lag_days: int) -> pd.DataFrame:
    """Với mỗi ngày VN t, lấy bản ghi mới nhất có (ngày quan sát + lag) <= t."""
    src = df.dropna(how="all").copy()
    src.index = pd.DatetimeIndex(src.index + pd.Timedelta(days=lag_days), name="avail")
    right = src.sort_index().reset_index()
    left = pd.DataFrame({"date": grid})
    m = pd.merge_asof(left, right, left_on="date", right_on="avail", direction="backward")
    return m.set_index("date").drop(columns="avail")


def macro_frame(grid: pd.DatetimeIndex, fred: pd.DataFrame) -> pd.DataFrame:
    """FRED theo lưới ngày VN: monthly -> tính YoY trước khi dời theo ngày công bố (độ trễ >= 2 ngày)."""
    parts = []
    for sid, (name, lag) in FRED_SERIES.items():
        s = fred[[name]].dropna()
        if name == "cpi_us":
            s = s.assign(cpi_yoy=s["cpi_us"].pct_change(12) * 100)[["cpi_yoy"]]
        parts.append(_asof_join(grid, s, lag_days=max(lag, 2)))
    return pd.concat(parts, axis=1)


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Các cột suy ra từ giá trong nước + giá thế giới (dùng chung cho dataset và dự báo sơ bộ buổi tối)."""
    df["world_vnd"] = df["xau_usd"] * df["usd_vnd"] * OZ_PER_LUONG / 1e6  # triệu VND/lượng
    df["premium"] = df["sjc_sell"] - df["world_vnd"]
    df["premium_pct"] = df["sjc_sell"] / df["world_vnd"] - 1
    df["ring_premium_pct"] = df["ring_sell"] / df["world_vnd"] - 1
    df["sjc_spread_pct"] = (df["sjc_sell"] - df["sjc_buy"]) / df["sjc_sell"]
    df["ring_spread_pct"] = (df["ring_sell"] - df["ring_buy"]) / df["ring_sell"]
    return df


def build_dataset(save: bool = True, issue_time: str = ISSUE_TIME) -> pd.DataFrame:
    from vngold.data.collect import giavang_daily, pnj_daily

    yahoo, fred, cafef, ticks, pnj = _load_raw()
    dom = merge_domestic(giavang_daily(ticks), cafef, pnj_daily(pnj))
    dom = dom[dom["sjc_sell"].notna() | dom["ring_sell"].notna()]
    dom = drop_incomplete_days(dom)

    # Lưới ngày làm việc T2-T6
    grid = pd.bdate_range(dom.index.min(), dom.index.max(), name="date")
    dom_g = dom.reindex(grid)
    # cờ "có giá thật" (trước khi điền tiếp) - dùng để loại ngày nghỉ khỏi nhãn
    dom_g["dom_observed"] = dom_g["sjc_sell"].notna().astype(int)
    dom_g["sjc_sell_observed"] = dom_g["dom_observed"]
    dom_g["ring_sell_observed"] = dom_g["ring_sell"].notna().astype(int)
    num = ["sjc_buy", "sjc_sell", "ring_buy", "ring_sell"]
    # ngày lễ / thiếu dữ liệu: giữ giá gần nhất tối đa 7 phiên
    dom_g[num] = dom_g[num].ffill(limit=7)
    dom_g["sjc_source"] = dom_g["sjc_source"].ffill()

    # Thế giới: phiên Mỹ ngày d đóng cửa ~4-5h sáng ngày d+1 giờ VN.
    #   morning: hàng t (dự báo phát hành sáng t+1) được dùng phiên Mỹ ngày t
    #   evening: hàng t (dự báo phát hành chiều t) chỉ dùng phiên Mỹ ngày t-1
    world = _asof_join(grid, yahoo, lag_days=WORLD_LAG_DAYS[issue_time])

    macro = macro_frame(grid, fred)
    df = add_derived(dom_g.join(world).join(macro))

    df = df[df["sjc_sell"].notna() & df["xau_usd"].notna()]
    df = drop_incomplete_days(df)
    if save:
        df.to_csv(DATA_PROCESSED / "dataset.csv")
    return df
