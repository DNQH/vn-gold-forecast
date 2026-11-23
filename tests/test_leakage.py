"""Kiểm tra chống rò rỉ dữ liệu tương lai (data leakage).

    python -m pytest tests -q
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vngold.evaluation import walk_forward  # noqa: E402
from vngold.features import build_features, build_targets  # noqa: E402
from vngold.models import Naive, WFData  # noqa: E402
from vngold.online import run_online  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "data" / "processed" / "dataset.csv"


@pytest.fixture(scope="module")
def df():
    if not DATA.exists():
        pytest.skip("chưa có dataset - chạy pipeline trước")
    return pd.read_csv(DATA, index_col=0, parse_dates=True)


def test_features_do_not_use_future(df):
    """Đặc trưng tại ngày t không đổi khi cắt bỏ toàn bộ dữ liệu sau ngày t."""
    full = build_features(df)
    for cut in (800, 1500, len(df) - 30):
        part = build_features(df.iloc[:cut])
        a, b = full.iloc[:cut], part
        diff = (a - b).abs().max().max()
        assert diff < 1e-9 or np.isnan(diff), f"leakage tại cut={cut}: {diff}"


def test_targets_are_future_returns(df):
    Y = build_targets(df, [1, 5])
    lp = np.log(df["sjc_sell"])
    assert np.allclose(Y["y_5"].iloc[10], lp.iloc[15] - lp.iloc[10])


class _Spy:
    """Mô hình 'gián điệp' ghi lại các hàng được dùng để học."""
    name = "Spy"

    def __init__(self):
        self.calls = []

    def fit(self, ds, idx, h):
        self.last = idx
        return self

    def predict(self, ds, idx, h):
        self.calls.append((self.last.max(), idx.min()))
        return np.zeros(len(idx))


def test_walk_forward_respects_label_availability(df):
    X = build_features(df)
    Y = build_targets(df, [5])
    ds = WFData(X, Y, df["sjc_sell"], np.log(df["sjc_sell"]).diff())
    spy = _Spy()
    walk_forward(ds, [Naive(), spy], 5, start=100, min_train=300, verbose=False)
    for last_train, first_test in spy.calls:
        # nhãn của hàng train cuối cùng (last_train + h) phải đã biết tại ngày first_test
        assert last_train + 5 <= first_test


def test_online_layer_only_uses_matured_errors():
    """Sửa giá trị thực tế ở tương lai không được làm thay đổi dự báo hiện tại."""
    n, h = 300, 5
    rng = np.random.default_rng(0)
    wf = pd.DataFrame({"A": rng.normal(size=n) * 0.01, "B": rng.normal(size=n) * 0.01,
                       "actual": rng.normal(size=n) * 0.01, "price_t": 100.0})
    on1, _ = run_online(wf, ["A", "B"], h)
    wf2 = wf.copy()
    t = 200
    wf2.loc[t - h + 1:, "actual"] = 99.0   # thay đổi các nhãn chưa đáo hạn tại t
    on2, _ = run_online(wf2, ["A", "B"], h)
    assert np.allclose(on1["Ensemble"].iloc[: t + 1], on2["Ensemble"].iloc[: t + 1])


def test_holiday_labels_are_masked():
    """Ngày thị trường trong nước nghỉ (giá chỉ điền tiếp) không được dùng làm nhãn."""
    idx = pd.bdate_range("2024-01-01", periods=12)
    price = pd.Series([100, 101, 101, 101, 102, 103, 104, 104, 105, 106, 107, 108.0], index=idx)
    obs = pd.Series([1, 1, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1], index=idx)
    df = pd.DataFrame({"sjc_sell": price, "sjc_sell_observed": obs})
    Y = build_targets(df, [1, 5])
    assert np.isnan(Y["y_1"].iloc[1])      # t+1 là ngày nghỉ
    assert np.isnan(Y["y_1"].iloc[2])      # t là ngày nghỉ
    assert not np.isnan(Y["y_1"].iloc[4])
    assert np.isnan(Y["y_5"].iloc[7])      # t+5 vượt quá dữ liệu


def test_online_skill_weights_prefer_better_model():
    """Mô hình gần đây đúng hơn hẳn phải được trọng số cao hơn."""
    n, h = 400, 1
    rng = np.random.default_rng(1)
    actual = rng.normal(size=n) * 0.01
    wf = pd.DataFrame({"Naive": 0.0, "Good": actual + rng.normal(size=n) * 0.002,
                       "Bad": rng.normal(size=n) * 0.02, "actual": actual, "price_t": 100.0})
    _, st = run_online(wf, ["Naive", "Good", "Bad"], h)
    assert st.weights.get("Good", 0) > 0.9
    assert "Bad" not in st.weights          # kém Naive > 5% -> bị loại


def test_historical_tracking_aligns_target_dates(tmp_path):
    """Dự báo lập ngày t với kỳ hạn h phải được so với giá thực tế của phiên t+h;
    dự báo live đã lưu được ưu tiên và chấm tạm bằng giá live khi đến hạn."""
    from vngold.tracking import historical_tracking
    idx = pd.bdate_range("2025-01-01", periods=10)
    price = pd.Series(np.linspace(100, 109, 10), index=idx)
    h = 2
    lp = np.log(price)
    wf = pd.DataFrame({"Ensemble": 0.01, "lo": -0.02, "hi": 0.03,
                       "actual": (lp.shift(-h) - lp).to_numpy(), "price_t": price.to_numpy()}, index=idx)
    wf.to_csv(tmp_path / f"backtest_x_h{h}.csv")
    pd.DataFrame([{"target": "x", "as_of": idx[-1], "h": h, "target_date": idx[-1] + pd.offsets.BDay(h),
                   "model": "Ensemble", "price_at_issue": 109.0, "pred_price": 110.0, "lo": 108.0,
                   "hi": 112.0, "actual_price": np.nan}]).to_csv(tmp_path / "predictions_log.csv", index=False)
    live = {"x": {"price": 111.0, "ts": idx[-1] + pd.offsets.BDay(h)}}
    tr = historical_tracking("x", h, None, live, proc_dir=tmp_path)
    r0 = tr.iloc[0]
    assert r0.target_date == idx[h] and np.isclose(r0.actual, price.iloc[h])
    assert np.isclose(r0.pred, price.iloc[0] * np.exp(0.01))
    last = tr.iloc[-1]
    assert last.source == "Live" and last.provisional and last.actual == 111.0
    assert (tr.issued == idx[-1]).sum() == 1      # không trùng backtest + live


def test_outlook_bands_use_only_past_data():
    """Khoảng giá dài hạn tại ngày t không được thay đổi khi cắt bỏ dữ liệu sau t."""
    import numpy as np
    import pandas as pd
    from vngold.outlook import outlook_bands
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2018-01-01", periods=900)
    price = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, len(idx))))
    df = pd.DataFrame({"sjc_sell": price, "sjc_sell_observed": 1}, index=idx)
    full = outlook_bands(df, "sjc_sell", 63)
    cut = outlook_bands(df.iloc[:700], "sjc_sell", 63)
    common = cut.dropna(subset=["lo"]).index
    assert len(common) > 100
    assert np.allclose(full.loc[common, ["lo", "hi"]], cut.loc[common, ["lo", "hi"]])
