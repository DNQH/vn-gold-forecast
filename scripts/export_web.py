"""Xuất dữ liệu cho ứng dụng điện thoại (PWA): docs/data/latest.json.

Dùng đúng logic của trang Streamlit "Dễ hiểu" (app/ui.py + src/vngold) nhưng không cần chạy Streamlit và không cần mạng.
Cách dùng: python scripts/export_web.py [--out docs/data]
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "app", ROOT / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
logging.getLogger("streamlit").setLevel(logging.ERROR)

from ui import bucket_of, freshness  # noqa: E402
from vngold.plain import calibration_table, plain_reason  # noqa: E402
from vngold.tracking import historical_tracking  # noqa: E402

TARGETS = {"sjc_sell": ("Vàng miếng SJC", "sjc_buy"), "ring_sell": ("Vàng nhẫn 9999", "ring_buy")}
SHORT = ("1", "5", "21")
LONG = ("63", "105")


def _r(x, d=3):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), d)


def _d(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def build(proc_dir: Path, now=None) -> dict:
    fc = json.loads((proc_dir / "forecast.json").read_text(encoding="utf-8"))
    df = pd.read_csv(proc_dir / "dataset.csv", index_col=0, parse_dates=True)
    fr = freshness(fc, df, now=now)
    out = {"generated_at": fc["generated_at"], "as_of": _d(fc["as_of"]), "targets": {}}
    for tkey, (name, buy_col) in TARGETS.items():
        if tkey not in fc["targets"]:
            continue
        T = fc["targets"][tkey]
        s = df[[tkey, buy_col]].dropna()
        sell, buy = float(s[tkey].iloc[-1]), float(s[buy_col].iloc[-1])
        t = {"name": name,
             "last_close": {"date": _d(s.index[-1]), "sell": _r(sell), "buy": _r(buy), "spread": _r(sell - buy)},
             "prev_close": _r(s[tkey].iloc[-2]),
             "last_price": _r(T["last_price"]),
             "history": [{"date": _d(i), "sell": _r(v)} for i, v in df[tkey].dropna().iloc[-66:].items()],
             "horizons": {}, "outlook": {}}
        for h in SHORT:
            r = T["horizons"].get(h)
            if not r:
                continue
            item = {"target_date": _d(r["target_date"]), "has_edge": bool(r.get("has_edge", True)),
                    "pred_price": _r(r["pred_price"]), "lo80": _r(r["lo80"]), "hi80": _r(r["hi80"]),
                    "p_up": _r(r["p_up"], 4), "bucket": None, "hit": None}
            if item["has_edge"]:
                b = bucket_of(r["p_up"])
                item["bucket"] = str(b)
                cal = calibration_table(tkey, int(h), proc_dir)
                if len(cal) and b in cal.index and cal.loc[b, "n"] >= 20 and b != "unclear":
                    up_side = b in ("strong_up", "lean_up")
                    rate = cal.loc[b, "up"] if up_side else 1 - cal.loc[b, "up"]
                    item["hit"] = {"rate": _r(rate, 4), "n": int(cal.loc[b, "n"])}
            t["horizons"][h] = item
        o = T.get("outlook") or {}
        for h in LONG:
            if h in o:
                t["outlook"][h] = {"label": o[h]["label"], "target_date": _d(o[h]["target_date"]),
                                   "lo": _r(o[h]["lo"]), "hi": _r(o[h]["hi"])}
        H1 = T["horizons"].get("1", {})
        reasons = []
        if H1.get("has_edge") and H1.get("shap_top"):
            for d in sorted(H1["shap_top"], key=lambda d: -abs(d["contribution_pct"])):
                txt = plain_reason(d["feature"], d["value"], d["contribution_pct"])
                if txt and txt not in {x["text"] for x in reasons}:
                    reasons.append({"text": txt, "up": bool(d["contribution_pct"] > 0)})
                if len(reasons) == 3:
                    break
        t["reasons"] = reasons
        lock = (H1.get("backtest", {}).get("locked") or {}).get("from")
        tr = historical_tracking(tkey, 1, lock, None, proc_dir)
        t["track"], t["stats"] = [], None
        if len(tr):
            done = tr[tr.actual.notna() & ~tr.provisional.astype(bool)].sort_values("target_date").tail(30)
            valid = done.dir_ok.dropna()
            inband = pd.to_numeric(done.in_band, errors="coerce").dropna()
            t["track"] = [{"target_date": _d(r.target_date),
                           "dir_ok": None if pd.isna(r.dir_ok) else int(r.dir_ok),
                           "in_band": None if pd.isna(r.in_band) else int(r.in_band)} for r in done.itertuples()]
            t["stats"] = {"n": int(len(done)), "n_ok": int(valid.sum()), "n_dir": int(len(valid)),
                          "mae": _r(done.error.abs().mean()), "mape": _r(done.abs_pct.mean()),
                          "inband_ok": int(inband.sum()), "inband_n": int(len(inband))}
        t["source_stale"] = bool(fr["source_stale"].get(tkey, False))
        lo = fr["last_observed"].get(tkey)
        t["last_observed"] = _d(lo) if lo is not None else None
        out["targets"][tkey] = t
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "data"))
    ap.add_argument("--proc", default=str(ROOT / "data" / "processed"))
    a = ap.parse_args(argv)
    data = build(Path(a.proc))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    f = out / "latest.json"
    f.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Đã ghi {f} ({f.stat().st_size / 1024:.1f} KB), as_of={data['as_of']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
