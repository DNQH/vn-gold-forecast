import os, subprocess, pathlib, shutil, pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _run(now, tmp, success=None, attempts=None):
    (tmp / "scripts").mkdir(exist_ok=True)
    shutil.copy(ROOT / "scripts/daily.sh", tmp / "scripts/daily.sh")
    (tmp / "logs").mkdir(exist_ok=True)
    day = now.split()[0]
    if success:
        (tmp / "logs/.last_success").write_text(success)
    if attempts is not None:
        (tmp / f"logs/.attempts_{day}").write_text(str(attempts))
    env = dict(os.environ, VNGOLD_NOW=now)
    r = subprocess.run(["/bin/zsh", str(tmp / "scripts/daily.sh"), "--check-only"],
                       capture_output=True, text=True, env=env)
    return r.stdout.strip()


@pytest.mark.skipif(not shutil.which("zsh"), reason="needs zsh/macOS")
def test_guard(tmp_path):
    assert _run("2026-11-26 08:00", tmp_path).startswith("RUN")          # Thu, late
    assert _run("2026-11-26 06:30", tmp_path).startswith("SKIP")         # before 07:00
    assert _run("2026-11-29 09:00", tmp_path).startswith("SKIP")         # Sunday
    assert _run("2026-11-26 08:00", tmp_path, success="2026-11-26").startswith("SKIP")
    (tmp_path / "logs/.last_success").unlink()
    assert _run("2026-11-26 08:00", tmp_path, attempts=3).startswith("SKIP")
