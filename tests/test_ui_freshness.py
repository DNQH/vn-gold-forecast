import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "app", ROOT / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from ui import freshness  # noqa: E402


def _df(last_obs="2026-11-23", end="2026-11-23"):
    idx = pd.bdate_range("2026-11-01", end)
    obs = (idx <= pd.Timestamp(last_obs)).astype(int)
    return pd.DataFrame({"sjc_sell_observed": obs, "ring_sell_observed": 1}, index=idx)


def _fc(as_of):
    return {"as_of": as_of, "targets": {"sjc_sell": {}, "ring_sell": {}}}


def test_fresh():
    r = freshness(_fc("2026-11-23"), _df(), now="2026-11-24 09:00")  # Tue, expected Mon
    assert not r["stale"] and r["days_behind"] == 0 and r["expected"] == pd.Timestamp("2026-11-23")


def test_stale_one_business_day():
    r = freshness(_fc("2026-11-20"), _df(end="2026-11-20"), now="2026-11-24 09:00")  # as_of Fri, expected Mon
    assert r["stale"] and r["days_behind"] == 1


def test_tuesday_before_run_not_stale():
    r = freshness(_fc("2026-11-20"), _df(end="2026-11-20"), now="2026-11-24 07:10")  # run may not have happened
    assert r["expected"] == pd.Timestamp("2026-11-20") and not r["stale"]


def test_monday_expects_friday_morning_and_after():
    for t in ("2026-11-23 06:00", "2026-11-23 08:00"):
        r = freshness(_fc("2026-11-20"), _df(end="2026-11-20"), now=t)
        assert r["expected"] == pd.Timestamp("2026-11-20") and not r["stale"]
    r = freshness(_fc("2026-11-19"), _df(end="2026-11-19"), now="2026-11-23 08:00")
    assert r["stale"] and r["days_behind"] == 1


def test_source_stale():
    df = _df(last_obs="2026-11-17", end="2026-11-23")  # nguồn dừng từ 17/11, as_of 23/11 (4 ngày làm việc)
    r = freshness(_fc("2026-11-23"), df, now="2026-11-24 09:00")
    assert not r["stale"] and r["source_stale"]["sjc_sell"] is True and r["source_stale"]["ring_sell"] is False
    df = _df(last_obs="2026-11-19", end="2026-11-23")  # đúng 2 ngày làm việc: chưa cờ
    assert freshness(_fc("2026-11-23"), df, now="2026-11-24 09:00")["source_stale"]["sjc_sell"] is False
