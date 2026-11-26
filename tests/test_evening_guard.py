"""Guard của scripts/evening.sh (thông báo 19h, T2–T6): chỉ quyết định, không gửi gì (--check-only)."""
import os
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _run(now, tmp, marker=None, attempts=None, morning_lock=False, extra=()):
    (tmp / "scripts").mkdir(exist_ok=True)
    shutil.copy(ROOT / "scripts/evening.sh", tmp / "scripts/evening.sh")
    (tmp / "logs").mkdir(exist_ok=True)
    day = now.split()[0]
    if marker:
        (tmp / "logs/.evening_last_success").write_text(marker)
    if attempts is not None:
        (tmp / f"logs/.evening_attempts_{day}").write_text(str(attempts))
    if morning_lock:
        (tmp / "logs/.run.lock").mkdir(exist_ok=True)
    env = dict(os.environ, VNGOLD_NOW=now)
    r = subprocess.run(["/bin/zsh", str(tmp / "scripts/evening.sh"), "--check-only", *extra],
                       capture_output=True, text=True, env=env)
    return r.stdout.strip()


pytestmark = pytest.mark.skipif(not shutil.which("zsh"), reason="needs zsh/macOS")


def test_runs_on_weekday_evening(tmp_path):
    out = _run("2026-11-26 19:00", tmp_path)            # thứ Năm, đúng 19h
    assert out.startswith("RUN") and "gửi bù=0" in out


def test_catchup_flag(tmp_path):
    assert "gửi bù=1" in _run("2026-11-26 21:40", tmp_path)
    assert "gửi bù=0" in _run("2026-11-26 19:14", tmp_path)


def test_skips_before_19h_and_weekend(tmp_path):
    assert _run("2026-11-26 18:59", tmp_path).startswith("SKIP")
    assert _run("2026-11-28 19:30", tmp_path).startswith("SKIP")    # thứ Bảy
    assert _run("2026-11-29 20:00", tmp_path).startswith("SKIP")    # Chủ Nhật
    assert _run("2026-11-30 19:01", tmp_path).startswith("RUN")     # thứ Hai
    assert _run("2026-11-27 19:30", tmp_path).startswith("RUN")     # thứ Sáu (dự báo cho thứ Hai)


def test_after_midnight_is_another_day(tmp_path):
    # máy thức dậy 00:30 thứ Sáu: không gửi bù tin của thứ Năm (đã là ngày khác, chưa tới 19h)
    assert _run("2026-11-27 00:30", tmp_path).startswith("SKIP")


def test_once_per_day_and_attempt_limit(tmp_path):
    assert _run("2026-11-26 19:30", tmp_path, marker="2026-11-26").startswith("SKIP")
    (tmp_path / "logs/.evening_last_success").write_text("2026-11-25")      # dấu của hôm qua: vẫn gửi
    assert _run("2026-11-26 19:30", tmp_path).startswith("RUN")
    assert _run("2026-11-26 19:30", tmp_path, attempts=3).startswith("SKIP")
    assert "lần thử thứ 3" in _run("2026-11-26 19:30", tmp_path, attempts=2)


def test_waits_for_running_morning_job(tmp_path):
    assert _run("2026-11-26 19:30", tmp_path, morning_lock=True).startswith("SKIP")


def test_force_bypasses_guard(tmp_path):
    assert _run("2026-11-28 10:00", tmp_path, extra=("--force",)).startswith("RUN")
