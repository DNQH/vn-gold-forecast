import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vngold.config import vn_today  # noqa: E402
from vngold.data.process import drop_incomplete_days  # noqa: E402


def _frame():
    idx = pd.to_datetime(["2026-11-20", "2026-11-23", "2026-11-24"])
    return pd.DataFrame({"sjc_sell": [1.0, 2.0, 3.0]}, index=idx)


def test_vn_today_env(monkeypatch):
    monkeypatch.setenv("VNGOLD_NOW", "2026-11-24 08:05")
    assert vn_today() == pd.Timestamp("2026-11-24")


def test_drops_today_morning(monkeypatch):
    monkeypatch.setenv("VNGOLD_NOW", "2026-11-24 08:05")
    out = drop_incomplete_days(_frame())
    assert out.index.max() == pd.Timestamp("2026-11-23")
    assert len(out) == 2


def test_drops_today_evening(monkeypatch):
    monkeypatch.setenv("VNGOLD_NOW", "2026-11-24 21:30")
    assert drop_incomplete_days(_frame()).index.max() == pd.Timestamp("2026-11-23")


def test_keeps_all_past(monkeypatch):
    monkeypatch.setenv("VNGOLD_NOW", "2026-11-25 07:00")
    assert len(drop_incomplete_days(_frame())) == 3
