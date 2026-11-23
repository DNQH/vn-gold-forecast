"""Chạy toàn bộ hệ thống.

    python scripts/run_pipeline.py              # thu thập dữ liệu mới + backtest + dự báo
    python scripts/run_pipeline.py --no-collect # dùng dữ liệu đã có
    python scripts/run_pipeline.py --fast       # bỏ LSTM, ablation, EDA (chạy hằng ngày)
"""
import argparse
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
warnings.filterwarnings("ignore")

from vngold.pipeline import run  # noqa: E402

if __name__ == "__main__":  # bắt buộc: LSTM chạy trong tiến trình con (spawn)
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-collect", action="store_true")
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--no-lstm", action="store_true")
    a = ap.parse_args()
    run(collect=not a.no_collect, include_lstm=not (a.fast or a.no_lstm),
        do_ablation=not a.fast, do_eda=not a.fast, evening_check=not a.fast)
