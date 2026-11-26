"""Thông báo 19h: dựng nội dung (hàm thuần, kiểm thử được) + gửi qua ntfy (điện thoại) và macOS.

Chỉ gửi thông tin giá vàng – không có dữ liệu cá nhân. Tên chủ đề ntfy nằm trong config/notify.env
(KHÔNG commit; xem config/notify.env.example).
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd

from vngold.config import ROOT
from vngold.plain import NO_EDGE_LABEL, vn, vn_day

CONFIG_FILE = ROOT / "config" / "notify.env"
APP_URL = "https://dnqh.github.io/vn-gold-forecast/"
SHORT_NAME = {"sjc_sell": "SJC", "ring_sell": "Nhẫn"}


# ------------------------------------------------------------------ nội dung
def _chg(sell, prev) -> str:
    if prev is None or sell is None or prev != prev:
        return ""
    d = sell - prev
    if abs(d) < 0.05:
        return "không đổi"
    pct = d / prev * 100
    return f"{'▲' if d > 0 else '▼'} {vn(abs(d))} · {'+' if d > 0 else '-'}{vn(abs(pct))}%"


def _morning_word(m: dict | None) -> str | None:
    """'giảm → đúng' / 'tăng → sai' / 'giảm → giá đứng yên' / None (sáng nay không nói chiều)."""
    if not m or not m.get("said"):
        return None
    said = "tăng" if m["said"] > 0 else "giảm"
    a = m.get("actual")
    if a is None:
        return None
    res = "giá đứng yên" if a == 0 else ("đúng" if a == m["said"] else "sai")
    return f"{said} → {res}"


def build_message(ctx: dict) -> dict:
    """ctx (xem scripts/evening.py):
      day, next_day, prev_day: 'YYYY-MM-DD'; catchup, test: bool; notes: list[str];
      prelim_reason: str | None (lý do không có dự báo sơ bộ);
      items: [{key, name, sell, buy, prev, stale, morning: {said, actual} | None,
               prelim: {label, has_edge, lo, hi, hit: [rate, n] | None, unverified} | None}]
    Trả về {"title", "body", "short"}."""
    day = ctx["day"]
    title = f"Giá vàng tối {vn_day(day)}"
    if ctx.get("test"):
        title += " (gửi thử)"
    elif ctx.get("catchup"):
        title += " (gửi bù)"
    prev_day = ctx.get("prev_day")
    prev_txt = "hôm qua" if prev_day and (pd.Timestamp(day) - pd.Timestamp(prev_day)).days == 1 \
        else (vn_day(prev_day) if prev_day else "phiên trước")
    items = [it for it in ctx["items"] if it.get("sell") is not None]
    lines = [f"Giá hôm nay (triệu đồng/lượng, so với {prev_txt}):"] if items else \
        ["Chưa lấy được giá vàng hôm nay."]
    for it in items:
        c = _chg(it["sell"], it.get("prev"))
        stale = " – nguồn chưa cập nhật hôm nay" if it.get("stale") else ""
        lines.append(f"• {it['name']}: bán {vn(it['sell'])} – mua {vn(it['buy'])}" + (f" ({c})" if c else "") + stale)
    mw = [(SHORT_NAME.get(it["key"], it["name"]), _morning_word(it.get("morning"))) for it in items]
    if any(w for _, w in mw):
        lines.append("Sáng nay đoán: " + " · ".join(f"{n} {w}" if w else f"{n} không đoán chiều" for n, w in mw))
    nd = vn_day(ctx["next_day"])
    pre = [(it, it.get("prelim")) for it in items]
    any_no_edge = False
    if ctx.get("prelim_reason") or not any(p for _, p in pre):
        lines.append(f"Dự báo sơ bộ cho {nd}: chưa có" +
                     (f" ({ctx['prelim_reason']})." if ctx.get("prelim_reason") else "."))
    else:
        lines.append(f"Dự báo sơ bộ cho {nd}:")
        for it, p in pre:
            n = SHORT_NAME.get(it["key"], it["name"])
            if not p:
                lines.append(f"• {n}: chưa có")
                continue
            lab = p["label"]
            any_no_edge |= lab == NO_EDGE_LABEL
            extra = ""
            if p.get("unverified") and lab != NO_EDGE_LABEL:
                extra = " (chưa kiểm chứng)"
            elif p.get("hit") and lab != NO_EDGE_LABEL:
                extra = f" (trước đây đúng {round(p['hit'][0] * 10)}/10 lần)"
            rng = f", khoảng {vn(p['lo'])} – {vn(p['hi'])}" if p.get("lo") is not None else ""
            lines.append(f"• {n}: {lab}{extra}{rng}")
        if any_no_edge:
            lines.append("Khó đoán: buổi tối chưa có giá Mỹ đêm nay, phần mềm chưa đoán tăng/giảm "
                         "tốt hơn việc coi như giá giữ nguyên.")
    lines.append("Đây là bản sơ bộ. Bản chính thức cập nhật lúc 7h sáng trên ứng dụng.")
    for note in ctx.get("notes") or []:
        lines.append(f"Lưu ý: {note}")
    if ctx.get("test"):
        lines.append("(Tin gửi thử – giá trong ngày có thể chưa chốt.)")

    # bản rút gọn cho thông báo macOS (chỉ hiện được 2–3 dòng)
    sp = []
    for it in items:
        d = it["sell"] - it["prev"] if it.get("prev") is not None else 0.0
        arrow = "" if abs(d) < 0.05 else f" ({'▲' if d > 0 else '▼'}{vn(abs(d))})"
        sp.append(f"{SHORT_NAME.get(it['key'], it['name'])} {vn(it['sell'])}{arrow}")
    sh = " · ".join(sp) if sp else "Chưa lấy được giá hôm nay"
    labs = [f"{SHORT_NAME.get(it['key'])} {p['label'].lower()}" for it, p in pre if p]
    if labs and not ctx.get("prelim_reason"):
        sh += f". Sơ bộ {vn_day(ctx['next_day'])}: " + ", ".join(labs)
    sh += ". Chính thức: 7h sáng."
    if ctx.get("notes"):
        sh += " Lưu ý: " + ctx["notes"][0]
    return {"title": title, "body": "\n".join(lines), "short": sh}


# ------------------------------------------------------------------ cấu hình + gửi
def load_config(path: Path = CONFIG_FILE) -> dict:
    """Đọc KEY=VALUE (bỏ dòng trống/chú thích). Biến môi trường NTFY_* ghi đè."""
    import os
    cfg = {"NTFY_SERVER": "https://ntfy.sh", "NTFY_CLICK": APP_URL}
    try:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    for k in ("NTFY_TOPIC", "NTFY_SERVER", "NTFY_CLICK"):
        if os.environ.get(k):
            cfg[k] = os.environ[k]
    return cfg


def send_ntfy(cfg: dict, title: str, message: str, tags=("moneybag",), priority: int = 3,
              timeout: float = 15, retries: int = 2, sleep=time.sleep) -> tuple[bool, str]:
    """POST JSON tới máy chủ ntfy (tiêu đề tiếng Việt UTF-8 an toàn). Thử lại tối đa `retries` lần."""
    import requests
    topic = cfg.get("NTFY_TOPIC")
    if not topic:
        return False, "thiếu NTFY_TOPIC (config/notify.env)"
    payload = {"topic": topic, "title": title, "message": message, "priority": priority,
               "tags": list(tags), "click": cfg.get("NTFY_CLICK") or APP_URL}
    url = cfg.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/") + "/"
    last = "?"
    for attempt in range(retries + 1):
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            if r.status_code == 200:
                return True, "HTTP 200"
            last = f"HTTP {r.status_code}"
            if 400 <= r.status_code < 500 and r.status_code != 429:
                break   # lỗi cấu hình: thử lại vô ích
        except requests.RequestException as e:
            last = type(e).__name__
        if attempt < retries:
            sleep(3 * (attempt + 1))
    return False, last


def send_macos(title: str, body: str, timeout: float = 20) -> tuple[bool, str]:
    """Thông báo macOS; nội dung truyền qua argv (không ghép chuỗi AppleScript -> không lỗi dấu nháy)."""
    try:
        r = subprocess.run(["/usr/bin/osascript", "-e", "on run argv",
                            "-e", "display notification (item 2 of argv) with title (item 1 of argv)",
                            "-e", "end run", title, body], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, type(e).__name__
    return (r.returncode == 0), ("ok" if r.returncode == 0 else (r.stderr.strip() or f"mã {r.returncode}"))


def hit_from_buckets(buckets: dict | None, bucket: str, min_n: int = 20):
    """[tỷ lệ, n] cho câu 'trước đây đúng X/10 lần' của bản sơ bộ, hoặc None."""
    b = (buckets or {}).get(str(bucket))
    if not b or b.get("rate") is None or b.get("n", 0) < min_n or not np.isfinite(b["rate"]):
        return None
    return [float(b["rate"]), int(b["n"])]
