import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_export_schema(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "export_web.py"), "--out", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    d = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    assert {"generated_at", "as_of", "targets"} <= d.keys()
    assert set(d["targets"]) == {"sjc_sell", "ring_sell"}
    assert (tmp_path / "latest.json").stat().st_size < 150_000
    for t in d["targets"].values():
        assert {"name", "last_close", "prev_close", "history", "horizons", "outlook", "reasons", "track", "stats",
                "source_stale", "last_observed"} <= t.keys()
        assert {"date", "sell", "buy", "spread"} == t["last_close"].keys()
        assert 0 < len(t["history"]) <= 66 and {"date", "sell"} == t["history"][0].keys()
        assert set(t["horizons"]) == {"1", "5", "21"}
        for h in t["horizons"].values():
            assert {"target_date", "has_edge", "pred_price", "lo80", "hi80", "p_up", "bucket", "hit"} <= h.keys()
            assert h["lo80"] <= h["pred_price"] <= h["hi80"] or not h["has_edge"]
        assert set(t["outlook"]) == {"63", "105"}
        assert {"label", "target_date", "lo", "hi"} == t["outlook"]["63"].keys()
        assert len(t["reasons"]) <= 3 and all({"text", "up"} == x.keys() for x in t["reasons"])
        assert len(t["track"]) <= 30 and all({"target_date", "dir_ok", "in_band"} == x.keys() for x in t["track"])
        assert {"n_ok", "n_dir", "mae", "mape", "inband_ok", "inband_n"} <= t["stats"].keys()
