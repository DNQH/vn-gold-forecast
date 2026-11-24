"""Kiểm tra chống rò rỉ cho các đặc trưng/mô hình mới của nhánh experiment/accuracy."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "experiments"))

from vngold.ecm import ECMModel, ecm_frame  # noqa: E402
from vngold.evaluation import walk_forward  # noqa: E402
from vngold.features import build_targets  # noqa: E402
from vngold.models import Naive, WFData  # noqa: E402

DATA = ROOT / "data" / "processed" / "dataset.csv"


def _synthetic(n=900, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2019-01-01", periods=n)
    lw = np.cumsum(rng.normal(0, 0.01, n)) + np.log(100)
    # giá trong nước bám theo thế giới với độ trễ 1 phiên + premium dao động chậm
    prem = 0.1 + 0.02 * np.sin(np.arange(n) / 50)
    lp = np.r_[lw[0], lw[:-1]] + prem + rng.normal(0, 0.002, n)
    return pd.DataFrame({"sjc_sell": np.exp(lp), "world_vnd": np.exp(lw), "xau_usd": np.exp(lw) / 30,
                         "sjc_sell_observed": 1}, index=idx)


@pytest.mark.parametrize("world", ["vnd", "usd"])
def test_ecm_features_do_not_use_future(world):
    df = _synthetic()
    full = ecm_frame(df, "sjc_sell", 20, world)
    for cut in (200, 500, 850):
        part = ecm_frame(df.iloc[:cut], "sjc_sell", 20, world)
        diff = (full.iloc[:cut] - part).abs().max().max()
        assert diff < 1e-12, f"rò rỉ tại cut={cut}"


def test_ecm_features_real_data_truncation():
    if not DATA.exists():
        pytest.skip("chưa có dataset")
    df = pd.read_csv(DATA, index_col=0, parse_dates=True)
    full = ecm_frame(df, "sjc_sell", 20, "vnd")
    cut = len(df) - 40
    part = ecm_frame(df.iloc[:cut], "sjc_sell", 20, "vnd")
    diff = (full.iloc[:cut] - part).abs().max().max()
    assert diff < 1e-12


def test_ecm_prediction_invariant_to_future_labels():
    """Đổi giá ở tương lai (sau mốc dự báo) không được làm đổi dự báo ECM walk-forward."""
    df = _synthetic()
    Y = build_targets(df, [1])
    Z = ecm_frame(df)
    ds = WFData(Z, Y, df["sjc_sell"], np.log(df["sjc_sell"]).diff())
    wf1 = walk_forward(ds, [Naive(), ECMModel(Z)], 1, start=30, min_train=300, verbose=False)
    df2 = df.copy()
    t = 700
    df2.iloc[t + 1:, df2.columns.get_loc("sjc_sell")] *= 1.5
    Y2 = build_targets(df2, [1])
    Z2 = ecm_frame(df2)
    ds2 = WFData(Z2, Y2, df2["sjc_sell"], np.log(df2["sjc_sell"]).diff())
    wf2 = walk_forward(ds2, [Naive(), ECMModel(Z2)], 1, start=30, min_train=300, verbose=False)
    a, b = wf1["ECM"].loc[: df.index[t]], wf2["ECM"].loc[: df.index[t]]
    assert np.allclose(a, b)


def test_ecm_recovers_structural_pass_through():
    """Trên dữ liệu giả lập có độ trễ truyền dẫn, ECM phải dự báo tốt hơn Naive."""
    df = _synthetic()
    Y = build_targets(df, [1])
    Z = ecm_frame(df)
    ds = WFData(Z, Y, df["sjc_sell"], np.log(df["sjc_sell"]).diff())
    wf = walk_forward(ds, [Naive(), ECMModel(Z)], 1, start=30, min_train=300, verbose=False)
    m = wf.actual.notna()
    assert ((wf.actual - wf.ECM)[m] ** 2).mean() < 0.5 * (wf.actual[m] ** 2).mean()


def test_hourly_feature_uses_only_bars_closed_before_issue(tmp_path):
    """Đặc trưng giờ sáng chỉ dùng nến 1 giờ đã đóng trước 06:30 VN của ngày phát hành."""
    import accuracy as A
    # Thứ Ba 2025-06-17 (giờ hè Mỹ, UTC-4): phiên ngày 17 đóng 17:00 ET = 21:00 UTC
    ts = pd.to_datetime(["2025-06-17 20:00", "2025-06-17 22:00", "2025-06-17 23:00",
                         "2025-06-18 00:00"], utc=True)
    close = [100.0, 101.0, 150.0, 300.0]   # 22:00 UTC kết thúc 06:00 VN (được dùng); 23:00 -> 07:00 VN (cấm)
    hdr = pd.MultiIndex.from_tuples([("Close", "GC=F")])
    pd.DataFrame(np.c_[close], index=ts, columns=hdr).rename_axis("Datetime").to_csv(tmp_path / "h.csv")
    idx = pd.DatetimeIndex(["2025-06-17"])
    x = A.hourly_feature(idx, tmp_path / "h.csv", strict=True)
    assert np.isclose(x.iloc[0], np.log(101 / 100))
    x2 = A.hourly_feature(idx, tmp_path / "h.csv", strict=False)
    assert np.isclose(x2.iloc[0], np.log(150 / 100))


def test_ecm_flag_default_on_and_pipeline_smoke():
    """Cờ USE_ECM mặc định BẬT (từ 24/11/2026, tắt bằng VNGOLD_USE_ECM=0); use_ecm=False tắt hẳn; khi bật, ECM chạy trọn backtest + dự báo cuối."""
    from vngold import config
    from vngold.pipeline import _prepare, backtest, build_models, final_forecast
    assert config.USE_ECM is True
    if not DATA.exists():
        pytest.skip("chưa có dataset")
    df = pd.read_csv(DATA, index_col=0, parse_dates=True)
    ds, start = _prepare(df, "ring_sell")
    off = [m.name for m in build_models("ring_sell", 1, False, df, ds, use_ecm=False)]
    assert off == ["Naive", "LinearRegression", "XGBoost"]
    on = build_models("ring_sell", 1, False, df, ds, use_ecm=True)
    assert [m.name for m in on][-1] == "ECM"
    models = [m for m in on if m.name != "XGBoost"]          # nhanh: bỏ XGBoost
    wf, _, st, table = backtest(ds, start, 1, models, 250)
    assert "ECM" in table.index and np.isfinite(table.loc["Ensemble", "RMSE"])
    assert "ECM" in st.ewmse
    fresh = [m for m in build_models("ring_sell", 1, False, df, ds, use_ecm=True) if m.name != "XGBoost"]
    fc = final_forecast(ds, start, 1, fresh, st, len(ds.X) - 1)
    assert "ECM" in fc["weights"] and abs(fc["ensemble"]) < 0.1
