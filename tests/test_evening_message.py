"""Nội dung thông báo 19h (hàm thuần build_message) + cấu hình ntfy không bị commit."""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vngold.evening import provisional_df, world_asof  # noqa: E402
from vngold.notify import build_message, hit_from_buckets, load_config, send_ntfy  # noqa: E402
from vngold.plain import direction_label, said_direction, vn_day  # noqa: E402


def _ctx(**kw):
    base = {"day": "2026-11-26", "prev_day": "2026-11-25", "next_day": "2026-11-27", "catchup": False,
            "test": False, "notes": [], "prelim_reason": None,
            "items": [
                {"key": "sjc_sell", "name": "SJC miếng", "sell": 134.5, "buy": 129.5, "prev": 134.1, "stale": False,
                 "morning": {"said": -1, "actual": 1},
                 "prelim": {"label": "Khó đoán", "has_edge": False, "lo": 133.0, "hi": 136.17, "hit": None,
                            "unverified": False}},
                {"key": "ring_sell", "name": "Nhẫn 9999 PNJ", "sell": 132.5, "buy": 127.0, "prev": 132.5,
                 "stale": False, "morning": {"said": 0, "actual": 0},
                 "prelim": {"label": "Hơi nghiêng về giảm", "has_edge": True, "lo": 130.8, "hi": 134.2,
                            "hit": [0.68, 120], "unverified": False}}]}
    base.update(kw)
    return base


def test_numbers_and_wording():
    m = build_message(_ctx())
    assert m["title"] == "Giá vàng tối Thứ Năm 26/11"
    b = m["body"]
    assert "SJC miếng: bán 134,5 – mua 129,5 (▲ 0,4 · +0,3%)" in b
    assert "Nhẫn 9999 PNJ: bán 132,5 – mua 127,0 (không đổi)" in b
    assert "so với hôm qua" in b
    assert "Sáng nay đoán: SJC giảm → sai · Nhẫn không đoán chiều" in b
    assert "Dự báo sơ bộ cho Thứ Sáu 27/11:" in b
    assert "• SJC: Khó đoán, khoảng 133,0 – 136,2" in b
    assert "• Nhẫn: Hơi nghiêng về giảm (trước đây đúng 7/10 lần), khoảng 130,8 – 134,2" in b
    assert "sơ bộ" in b and "7h sáng" in b
    assert "Khó đoán: buổi tối" in b                 # có giải thích vì sao không nói chiều
    lines = b.splitlines()
    assert 6 <= len(lines) <= 11 and len(b.encode()) < 4096
    assert "134,5" in m["short"] and len(m["short"]) < 250


def test_friday_to_monday_and_catchup():
    m = build_message(_ctx(day="2026-11-27", prev_day="2026-11-26", next_day="2026-11-30", catchup=True))
    assert m["title"] == "Giá vàng tối Thứ Sáu 27/11 (gửi bù)"
    assert "Dự báo sơ bộ cho Thứ Hai 30/11:" in m["body"]
    m = build_message(_ctx(day="2026-11-30", prev_day="2026-11-27", next_day="2026-12-01"))
    assert "so với Thứ Sáu 27/11" in m["body"]               # thứ Hai so với thứ Sáu, không phải "hôm qua"


def test_gating_no_edge_never_shows_direction():
    ctx = _ctx()
    for it in ctx["items"]:
        it["prelim"].update(label=direction_label("strong_up", has_edge=False), has_edge=False, hit=None)
    b = build_message(ctx)["body"]
    sec = b.split("Dự báo sơ bộ")[1]
    assert "nghiêng" not in sec.lower() and "tăng (trước" not in sec and sec.count("Khó đoán") >= 2


def test_morning_flat_and_right():
    ctx = _ctx()
    ctx["items"][0]["morning"] = {"said": 1, "actual": 0}
    ctx["items"][1]["morning"] = {"said": -1, "actual": -1}
    assert "SJC tăng → giá đứng yên · Nhẫn giảm → đúng" in build_message(ctx)["body"]
    for it in ctx["items"]:
        it["morning"] = None
    assert "Sáng nay đoán" not in build_message(ctx)["body"]


def test_no_prelim_and_notes():
    ctx = _ctx(prelim_reason="số liệu sáng nay chưa cập nhật", notes=["sáng nay phần mềm cập nhật bị lỗi."])
    b = build_message(ctx)["body"]
    assert "Dự báo sơ bộ cho Thứ Sáu 27/11: chưa có (số liệu sáng nay chưa cập nhật)." in b
    assert "Lưu ý: sáng nay phần mềm cập nhật bị lỗi." in b
    assert "• SJC: Khó đoán" not in b


def test_labels_match_app():
    assert direction_label("strong_up") == "Nghiêng rõ về tăng"
    assert direction_label("lean_down") == "Hơi nghiêng về giảm"
    assert direction_label("unclear") == "Không rõ ràng"
    assert direction_label("strong_down", has_edge=False) == "Khó đoán"
    js = (ROOT / "docs/app.js").read_text(encoding="utf-8")
    assert "Nghiêng rõ về {dir}" in js and "Hơi nghiêng về {dir}" in js and "Khó đoán" in js
    assert said_direction("lean_up") == 1 and said_direction("unclear") == 0
    assert vn_day("2026-11-30") == "Thứ Hai 30/11"
    assert hit_from_buckets({"lean_up": {"n": 19, "rate": 0.9}}, "lean_up") is None
    assert hit_from_buckets({"lean_up": {"n": 40, "rate": 0.6}}, "lean_up") == [0.6, 40]


def test_notify_config_is_gitignored_and_example_is_placeholder():
    r = subprocess.run(["git", "check-ignore", "-q", "config/notify.env"], cwd=ROOT)
    assert r.returncode == 0, "config/notify.env phải nằm trong .gitignore"
    r = subprocess.run(["git", "ls-files", "--error-unmatch", "config/notify.env"], cwd=ROOT, capture_output=True)
    assert r.returncode != 0, "config/notify.env không được commit"
    ex = (ROOT / "config/notify.env.example").read_text(encoding="utf-8")
    assert "NTFY_TOPIC=vngold-THAY-BANG-TEN-KHO-DOAN" in ex
    cfg = load_config(ROOT / "config/notify.env.example")
    assert cfg["NTFY_SERVER"] == "https://ntfy.sh" and cfg["NTFY_CLICK"].startswith("https://")


def test_send_ntfy_payload(monkeypatch):
    import requests
    calls = []

    class R:
        status_code = 200

    def fake_post(url, json=None, timeout=None):
        calls.append((url, json, timeout))
        return R()
    monkeypatch.setattr(requests, "post", fake_post)
    ok, info = send_ntfy({"NTFY_TOPIC": "vngold-test", "NTFY_SERVER": "https://ntfy.sh"}, "Giá vàng tối", "nội dung")
    assert ok and info == "HTTP 200"
    url, payload, timeout = calls[0]
    assert url == "https://ntfy.sh/" and timeout
    assert payload["topic"] == "vngold-test" and payload["title"] == "Giá vàng tối" and payload["click"].startswith("https://")
    # thiếu topic: không gửi
    assert send_ntfy({}, "a", "b")[0] is False


def test_send_ntfy_retries(monkeypatch):
    import requests
    n = {"k": 0}

    def boom(*a, **k):
        n["k"] += 1
        raise requests.ConnectionError("x")
    monkeypatch.setattr(requests, "post", boom)
    ok, info = send_ntfy({"NTFY_TOPIC": "t"}, "a", "b", sleep=lambda s: None)
    assert not ok and n["k"] == 3


def test_world_asof_and_provisional_row_do_not_leak():
    idx = pd.to_datetime(["2026-11-26 10:00", "2026-11-26 11:00", "2026-11-26 12:00", "2026-11-26 13:00"])
    hourly = pd.DataFrame({"xau_usd": [1.0, 2.0, 3.0, 4.0], "us10y": [np.nan] * 4}, index=idx)
    v, ts = world_asof(hourly, pd.Timestamp("2026-11-26 11:00"))   # thanh 11:00 đóng lúc 19h VN
    assert v == {"xau_usd": 2.0} and ts["xau_usd"] == idx[1]
    d = pd.DataFrame({"sjc_sell": [100.0, 101.0], "sjc_buy": [98.0, 99.0], "ring_sell": [99.0, 99.5],
                      "ring_buy": [97.0, 97.5], "xau_usd": [3000.0, 3010.0], "usd_vnd": [25000.0, 25010.0],
                      "gold_volume": [10.0, 20.0]}, index=pd.to_datetime(["2026-11-24", "2026-11-25"]))
    out = provisional_df(d, "2026-11-26", {"xau_usd": 3050.0}, dom={"sjc_sell": 102.0})
    assert list(out.index.strftime("%m-%d")) == ["11-24", "11-25", "11-26"]
    pd.testing.assert_frame_equal(out.iloc[:2][d.columns], d)        # các hàng cũ không đổi
    assert out.loc["2026-11-26", "xau_usd"] == 3050.0 and out.loc["2026-11-26", "sjc_sell"] == 102.0
    assert out.loc["2026-11-26", "gold_volume"] == 20.0               # khối lượng phiên đang chạy: giữ phiên trước
    assert abs(out.loc["2026-11-26", "premium_pct"] - (102.0 / out.loc["2026-11-26", "world_vnd"] - 1)) < 1e-12
