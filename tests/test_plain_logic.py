"""Logic dùng chung giữa Streamlit (Python) và ứng dụng điện thoại (docs/app.js)."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vngold.plain import bucket_hit_rate, calibration_table, freshness  # noqa: E402
from vngold.tracking import historical_tracking  # noqa: E402


def _backtest(tmp_path, p_up, actual, name="backtest_sjc_sell_h1.csv", lo80=-0.01, hi80=0.01):
    n = len(actual)
    idx = pd.bdate_range("2026-01-05", periods=n, name="date")
    wf = pd.DataFrame({"Naive": 0.0, "actual": actual, "price_t": 100.0, "Ensemble": 0.0,
                       "lo": -0.02, "hi": 0.02, "lo80": lo80, "hi80": hi80, "p_up": p_up}, index=idx)
    wf.to_csv(tmp_path / name)
    return wf


def test_hit_rate_counts_flat_days_as_miss(tmp_path):
    # 30 lần "tăng mạnh": 18 tăng, 6 đứng yên, 6 giảm -> 18/30 = 0.6 (không phải 18/24 = 0.75)
    actual = [0.01] * 18 + [0.0] * 6 + [-0.01] * 6
    _backtest(tmp_path, [0.9] * 30, actual)
    cal = calibration_table("sjc_sell", 1, tmp_path)
    assert cal.loc["strong_up", "n"] == 24 and abs(cal.loc["strong_up", "up"] - 0.75) < 1e-9
    rate, n = bucket_hit_rate(cal, "strong_up")
    assert n == 30 and abs(rate - 0.6) < 1e-9
    assert bucket_hit_rate(cal, "strong_down") is None  # không có mẫu
    assert bucket_hit_rate(cal, "unclear") is None


def test_hit_rate_down_side_and_min_n(tmp_path):
    actual = [-0.01] * 7 + [0.01] * 3
    _backtest(tmp_path, [0.1] * 10, actual)
    cal = calibration_table("sjc_sell", 1, tmp_path)
    assert bucket_hit_rate(cal, "strong_down") is None            # n = 10 < 20
    rate, n = bucket_hit_rate(cal, "strong_down", min_n=5)
    assert n == 10 and abs(rate - 0.7) < 1e-9


def test_tracking_in_band80_uses_80pct_band(tmp_path):
    # actual 1.5%: trong khoảng 90% (±2%) nhưng ngoài khoảng 80% (±1%)
    _backtest(tmp_path, [0.6] * 5, [0.015] * 5)
    tr = historical_tracking("sjc_sell", 1, None, None, tmp_path)
    assert (tr.in_band == 1).all() and (tr.in_band80 == 0).all()


def test_tracking_live_rows_without_lo80_are_not_guessed(tmp_path):
    _backtest(tmp_path, [0.6] * 5, [0.005] * 5)
    log = pd.DataFrame({"target": "sjc_sell", "as_of": "2026-01-06", "h": 1, "target_date": "2026-01-07",
                        "model": "Ensemble", "price_at_issue": 100.0, "pred_price": 100.2, "lo": 98.0, "hi": 102.0,
                        "p_up": 0.6, "issued_at": "2026-01-07T07:10:00", "actual_price": 100.5}, index=[0])
    log.to_csv(tmp_path / "predictions_log.csv", index=False)
    tr = historical_tracking("sjc_sell", 1, None, None, tmp_path)
    live = tr[tr.source == "Live"]
    assert len(live) == 1 and live.in_band.iloc[0] == 1 and np.isnan(live.in_band80.iloc[0])


# ------------------------------------------------------------------ JS <-> Python: freshness
JS_HARNESS = r"""
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8");
const a = src.indexOf("  // ---------- định dạng"), b = src.indexOf("  // ---------- giá niêm yết");
if (a < 0 || b < 0) throw new Error("markers not found");
const body = src.slice(a, b);
const f = new Function("WEEKDAYS", "location", body + "; return freshness;");
const freshness = f(["Thứ Hai","Thứ Ba","Thứ Tư","Thứ Năm","Thứ Sáu","Thứ Bảy","Chủ Nhật"], {search: ""});
const cases = JSON.parse(process.argv[3]);
console.log(JSON.stringify(cases.map(c => freshness(c.as_of, {date: c.date, h: c.h, m: c.m}))));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="cần Node.js để chạy docs/app.js")
def test_js_freshness_matches_python(tmp_path):
    harness = tmp_path / "h.js"
    harness.write_text(JS_HARNESS, encoding="utf-8")
    cases, expect = [], []
    df = pd.DataFrame({"sjc_sell_observed": 1}, index=pd.bdate_range("2026-11-01", "2026-12-31"))
    for day in pd.date_range("2026-11-16", "2026-11-30"):
        for hh, mm in ((6, 0), (7, 29), (7, 30), (12, 0), (23, 59)):
            for as_of in pd.bdate_range("2026-11-10", "2026-11-30"):
                now = day + pd.Timedelta(hours=hh, minutes=mm)
                r = freshness({"as_of": as_of, "targets": {}}, df, now=now)
                cases.append({"as_of": f"{as_of:%Y-%m-%d}", "date": f"{day:%Y-%m-%d}", "h": hh, "m": mm})
                expect.append({"stale": r["stale"], "expected": f"{r['expected']:%Y-%m-%d}"})
    out = subprocess.run(["node", str(harness), str(ROOT / "docs" / "app.js"), json.dumps(cases)],
                         capture_output=True, text=True, check=True)
    got = json.loads(out.stdout)
    bad = [(c, e, g) for c, e, g in zip(cases, expect, got) if e != g]
    assert not bad, bad[:5]
