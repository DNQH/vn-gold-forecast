"""Thông báo 19h (T2–T6): giá vàng hôm nay + dự báo SƠ BỘ cho phiên kế tiếp, gửi đồng thời tới
điện thoại (ntfy) và máy Mac. Gọi từ scripts/evening.sh (guard, khoá, chạy bù).

    python scripts/evening.py --dry-run        # dựng và in nội dung, không gửi, không ghi gì
    python scripts/evening.py                  # gửi thật
Tuỳ chọn: --catchup (tiêu đề "(gửi bù)"), --test (tiêu đề "(gửi thử)"), --last-attempt.
Mã thoát: 0 = đã gửi được ít nhất một kênh (hoặc dry-run); 2 = thiếu dữ liệu giá (sẽ thử lại); 3 = cả hai kênh lỗi.
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from vngold.config import DATA_PROCESSED, DATA_RAW, vn_now  # noqa: E402
from vngold.plain import NO_EDGE_LABEL, bucket_of, direction_label, prev_bday, said_direction  # noqa: E402

TARGETS = {"sjc_sell": "SJC miếng", "ring_sell": "Nhẫn 9999 PNJ"}
LOGS = ROOT / "logs"
EVAL_MAX_AGE_DAYS = 14


def _p(*a):
    print(*a, flush=True)


def morning_notes(day: pd.Timestamp, fc: dict | None, logs: Path = LOGS) -> list[str]:
    """Ghi chú khi bản 7h sáng hôm nay lỗi/chưa chạy (chỉ T3–T6; thứ Hai không có lần chạy sáng)."""
    notes = []
    if day.weekday() not in (1, 2, 3, 4):
        return notes
    st = (logs / ".morning_status").read_text().split() if (logs / ".morning_status").exists() else []
    last_ok = (logs / ".last_success").read_text().strip() if (logs / ".last_success").exists() else ""
    d = f"{day:%Y-%m-%d}"
    if st and st[0] == d and len(st) > 1 and st[1] == "fail":
        notes.append("sáng nay phần mềm cập nhật bị lỗi, ứng dụng có thể chưa có dự báo mới.")
    elif last_ok != d:
        notes.append("sáng nay phần mềm chưa chạy được (máy tắt hoặc mất mạng), ứng dụng chưa có dự báo mới.")
    elif st and st[0] == d and "push_fail" in st:
        notes.append("sáng nay chưa đăng được dự báo mới lên ứng dụng.")
    if fc is not None and pd.Timestamp(fc["as_of"]) < prev_bday(day) and not notes:
        notes.append("số liệu của ứng dụng chưa được cập nhật.")
    return notes


def build_context(now: pd.Timestamp, catchup=False, test=False, fetch_world=True) -> tuple[dict, dict]:
    """Thu thập mọi thứ cần cho tin nhắn. Trả về (ctx cho build_message, chi tiết để ghi log/JSON)."""
    from vngold.data.collect import fetch_recent_domestic
    day = now.normalize()
    prev_day = prev_bday(day)
    next_day = day + pd.offsets.BDay(1)
    fc = df = None
    try:
        fc = json.loads((DATA_PROCESSED / "forecast.json").read_text(encoding="utf-8"))
        df = pd.read_csv(DATA_PROCESSED / "dataset.csv", index_col=0, parse_dates=True)
    except (OSError, ValueError) as e:
        _p(f"không đọc được dữ liệu sáng: {e}")
    dom = fetch_recent_domestic()
    ctx = {"day": f"{day:%Y-%m-%d}", "prev_day": f"{prev_day:%Y-%m-%d}", "next_day": f"{next_day:%Y-%m-%d}",
           "catchup": catchup, "test": test, "notes": morning_notes(day, fc), "prelim_reason": None, "items": []}
    detail = {"now": f"{now:%Y-%m-%d %H:%M}", "targets": {}}

    # 1) giá hôm nay + so với phiên trước + bản sáng nay đoán đúng/sai
    for t, name in TARGETS.items():
        it = {"key": t, "name": name, "sell": None, "buy": None, "prev": None, "stale": False,
              "morning": None, "prelim": None}
        h = dom.get(t)
        if h is not None and len(h):
            last = h.iloc[-1]
            it["sell"], it["buy"] = float(last.sell), float(last.buy)
            it["stale"] = bool(h.index[-1] < day)
            prev = h[h.index <= prev_day]
            if len(prev):
                it["prev"] = float(prev.sell.iloc[-1])
            elif df is not None and t in df:
                it["prev"] = float(df.loc[:prev_day, t].dropna().iloc[-1])
        if fc is not None and it["sell"] is not None and not it["stale"]:
            r = fc["targets"].get(t, {}).get("horizons", {}).get("1")
            if r and r.get("target_date") == f"{day:%Y-%m-%d}":
                said = said_direction(bucket_of(r["p_up"])) if r.get("has_edge") else 0
                p0 = fc["targets"][t]["last_price"]
                it["morning"] = {"said": said, "actual": int(np.sign(round(it["sell"] - p0, 3)))}
        ctx["items"].append(it)

    # 2) dự báo sơ bộ cho phiên kế tiếp
    if df is None or fc is None or df.index[-1] != prev_day:
        ctx["prelim_reason"] = "số liệu sáng nay chưa cập nhật"
        return ctx, detail
    world, wts = {}, {}
    if fetch_world:
        try:
            from vngold.evening import fetch_hourly, world_asof
            hourly = fetch_hourly(period="5d", cache=None)
            now_utc = pd.Timestamp.now(tz="UTC").tz_localize(None)
            world, wts = world_asof(hourly, now_utc)
        except Exception as e:  # noqa: BLE001
            _p(f"lỗi tải giá thế giới theo giờ: {type(e).__name__}: {e}")
    gold_ts = wts.get("xau_usd")
    # phiên vàng ngày T (giờ Mỹ) mở lúc ~22:00 UTC ngày T-1: phải có giá sau mốc này
    if gold_ts is None or gold_ts < day - pd.Timedelta(hours=2):
        ctx["prelim_reason"] = "chưa lấy được giá vàng thế giới mới"
        detail["world"] = {k: str(v) for k, v in wts.items()}
        return ctx, detail
    detail["world"] = {k: {"value": world[k], "bar_utc": f"{wts[k]:%Y-%m-%d %H:%M}"} for k in world}

    from vngold.data.process import macro_frame
    from vngold.evening import load_eval, load_state, preliminary_forecast
    from vngold.notify import hit_from_buckets
    try:
        fred = pd.read_csv(DATA_RAW / "fred.csv", index_col=0, parse_dates=True)
        macro = macro_frame(pd.DatetimeIndex([day]), fred).iloc[0].to_dict()
    except Exception:  # noqa: BLE001 - thiếu thì giữ giá trị vĩ mô của hàng trước
        macro = None
    ev = load_eval()
    ev_ok = ev is not None and (pd.Timestamp.now() - pd.Timestamp(ev["generated_at"])).days <= EVAL_MAX_AGE_DAYS
    items = {it["key"]: it for it in ctx["items"]}
    dom_row = {}
    for t, it in items.items():
        if it["sell"] is None or it["stale"]:
            continue
        b = "sjc" if t == "sjc_sell" else "ring"
        dom_row.update({f"{b}_sell": it["sell"], f"{b}_buy": it["buy"], f"{t}_observed": 1})
    dom_row["dom_observed"] = int("sjc_sell" in dom_row)
    for t, it in items.items():
        if it["sell"] is None or it["stale"]:
            continue
        try:
            ei = (ev or {}).get("targets", {}).get(t) if ev_ok else None
            state = load_state(t) if ei else None
            r = preliminary_forecast(df, t, day, dom_row, world, state=state, macro=macro)
        except Exception as e:  # noqa: BLE001
            _p(f"lỗi dự báo sơ bộ {t}: {type(e).__name__}: {e}")
            continue
        morning_edge = bool(fc["targets"].get(t, {}).get("horizons", {}).get("1", {}).get("has_edge", False))
        bucket = str(bucket_of(r["p_up"]))
        unverified = ei is None or state is None
        if unverified:   # chưa kiểm chứng: chỉ nói chiều khi rất rõ
            show = morning_edge and bucket.startswith("strong")
        else:
            show = morning_edge and bool(ei.get("has_edge"))
        p0, ens = r["price"], r["ensemble"]
        shift = 0.0 if show else -ens   # không nói chiều: khoảng đặt quanh giá hôm nay (Naive)
        p = {"label": direction_label(bucket, show), "has_edge": show, "unverified": unverified and show,
             "lo": round(p0 * np.exp(r["lo80"] + shift), 3), "hi": round(p0 * np.exp(r["hi80"] + shift), 3),
             "hit": hit_from_buckets(ei.get("summary", {}).get("buckets") if ei else None, bucket) if show else None}
        it["prelim"] = p
        detail["targets"][t] = {"p_up": r["p_up"], "bucket": bucket, "ensemble_pct": ens * 100,
                                "pred_price": p0 * np.exp(ens), "lo80": p0 * np.exp(r["lo80"]),
                                "hi80": p0 * np.exp(r["hi80"]), "shown": p, "state": r["state"],
                                "eval_has_edge": None if not ei else ei.get("has_edge"),
                                "morning_has_edge": morning_edge, "weights": r["weights"]}
        if p["label"] == NO_EDGE_LABEL:
            detail["targets"][t]["why_no_direction"] = (ei or {}).get("verdict", "chưa kiểm chứng")
    return ctx, detail


def _save(ctx: dict, detail: dict, msg: dict, sent: dict) -> None:
    out = {"generated_at": pd.Timestamp.now().isoformat(timespec="seconds"), "ctx": ctx, "detail": detail,
           "message": msg, "sent": sent}
    (DATA_PROCESSED / "evening.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str),
                                                 encoding="utf-8")
    rows = [{"day": ctx["day"], "target_date": ctx["next_day"], "target": t, "price": it["sell"],
             "pred_price": detail["targets"][t]["pred_price"], "p_up": detail["targets"][t]["p_up"],
             "lo80": detail["targets"][t]["lo80"], "hi80": detail["targets"][t]["hi80"],
             "label": it["prelim"]["label"], "issued_at": out["generated_at"]}
            for t, it in ((i["key"], i) for i in ctx["items"]) if it.get("prelim") and t in detail["targets"]]
    if rows:
        f = DATA_PROCESSED / "evening_log.csv"
        log = pd.DataFrame(rows)
        if f.exists():
            log = pd.concat([pd.read_csv(f), log], ignore_index=True)
        log.drop_duplicates(["day", "target"], keep="last").to_csv(f, index=False)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--catchup", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--last-attempt", action="store_true")
    a = ap.parse_args(argv)
    from vngold.notify import build_message, load_config, send_macos, send_ntfy

    now = vn_now()
    ctx, detail = build_context(now, catchup=a.catchup, test=a.test)
    msg = build_message(ctx)
    _p("----- TIÊU ĐỀ -----\n" + msg["title"] + "\n----- NỘI DUNG -----\n" + msg["body"] +
       "\n----- macOS -----\n" + msg["short"] + "\n-------------------")
    _p("chi tiết: " + json.dumps(detail.get("targets", {}), ensure_ascii=False, default=str)[:1500])
    has_price = any(it.get("sell") is not None for it in ctx["items"])
    if not has_price and not a.last_attempt:
        _p("chưa lấy được giá hôm nay: không gửi, chờ lần thử sau")
        return 2
    if a.dry_run:
        _p("dry-run: không gửi, không ghi file")
        return 0
    cfg = load_config()
    ok_n, info_n = send_ntfy(cfg, msg["title"], msg["body"])
    ok_m, info_m = send_macos(msg["title"], msg["short"])
    _p(f"ntfy: {'OK' if ok_n else 'LỖI'} ({info_n}) · macOS: {'OK' if ok_m else 'LỖI'} ({info_m})")
    sent = {"ntfy": [ok_n, info_n], "macos": [ok_m, info_m]}
    try:
        _save(ctx, detail, msg, sent)
    except Exception as e:  # noqa: BLE001 - lưu nhật ký lỗi không làm hỏng việc gửi
        _p(f"lỗi ghi evening.json/evening_log.csv: {e}")
    return 0 if (ok_n or ok_m) else 3


if __name__ == "__main__":
    sys.exit(main())
