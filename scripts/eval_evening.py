"""Kiểm định trung thực dự báo SƠ BỘ 19h (xem src/vngold/evening.py).

    python scripts/eval_evening.py              # tải giá theo giờ (~2 năm) + kiểm định + ghi báo cáo
    python scripts/eval_evening.py --no-fetch   # dùng cache data/raw/yahoo_hourly.csv

Ghi ra:
  reports/04_evening_preliminary.md             báo cáo (so với bản 7h sáng, Naive, "luôn đoán tăng", tần suất lịch sử)
  data/processed/evening_eval.json              kết luận + cổng "có lợi thế" + tỷ lệ đúng theo mức tin cậy (dùng cho thông báo 19h)
  data/processed/backtest_evening_{target}_h1.csv
  models/online_state_evening_{target}_h1.pkl   trạng thái lớp tự học của bản sơ bộ (dùng khi chạy thật)
Dùng dataset.csv và backtest_{target}_h1.csv của lần chạy sáng gần nhất (không chạy lại bản sáng).
"""
from __future__ import annotations

import argparse
import sys
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from vngold.config import DATA_PROCESSED, LOCK_DATE, REPORTS  # noqa: E402
from vngold.evening import (HOURLY_CACHE, edge_verdict, evening_backtest, fetch_hourly,  # noqa: E402
                            save_state, summarize, write_eval)

NAMES = {"sjc_sell": "Vàng miếng SJC", "ring_sell": "Vàng nhẫn 9999 (PNJ)"}
VLABEL = {"morning": "Bản chính thức 7h sáng (có phiên Mỹ đóng cửa)",
          "evening": "**Bản sơ bộ 19h** (giá thế giới lúc 19h)",
          "prev": "19h nhưng KHÔNG dùng giá thế giới trong ngày"}
BLABEL = {"strong_up": "Nghiêng rõ về tăng", "lean_up": "Hơi nghiêng về tăng", "unclear": "Không rõ ràng",
          "lean_down": "Hơi nghiêng về giảm", "strong_down": "Nghiêng rõ về giảm"}


def _f(x, d=3):
    return "–" if x is None or x != x else f"{x:.{d}f}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args(argv)
    t0 = time.time()
    df = pd.read_csv(DATA_PROCESSED / "dataset.csv", index_col=0, parse_dates=True)
    if a.no_fetch and HOURLY_CACHE.exists():
        hourly = pd.read_csv(HOURLY_CACHE, index_col=0, parse_dates=True)
    else:
        hourly = fetch_hourly()
    print(f"Giá theo giờ: {hourly.index.min():%Y-%m-%d} -> {hourly.index.max():%Y-%m-%d %H:%M} UTC, {len(hourly)} thanh")

    md = ["# Phase 4 – Dự báo SƠ BỘ lúc 19h cho phiên kế tiếp: kiểm định walk-forward\n",
          f"Dữ liệu tới {df.index[-1]:%d/%m/%Y}. Tạo lúc {pd.Timestamp.now():%d/%m/%Y %H:%M}.\n",
          "**Câu hỏi:** lúc 19h ngày T (giờ VN) đã biết giá trong nước ngày T nhưng phiên Mỹ ngày T chưa đóng cửa. "
          "Nếu lấy giá thế giới *đang chạy* lúc 19h (thanh 1 giờ đóng lúc 12:00 UTC) thay cho giá đóng cửa phiên Mỹ "
          "rồi áp đúng các mô hình h = 1 của bản sáng, dự báo giá chốt phiên T+1 có còn lợi thế không?\n",
          "**Cách kiểm định (không nhìn trộm tương lai):** cùng lịch walk-forward với bản sáng (huấn luyện lại mỗi 21 phiên, "
          "chỉ học nhãn đã biết). Ở hàng T chỉ thay 6 biến thế giới (vàng, DXY, lợi suất 10 năm, USD/VND, bạc, VIX) bằng giá "
          "của thanh 1 giờ đã đóng trước 19h; mã không giao dịch giờ đó (vd. lợi suất 10 năm) giữ giá gần nhất trước đó; "
          "khối lượng vàng giữ của phiên trước. Các hàng trước T giữ giá đóng cửa thật (lúc 19h đã biết). Lớp tự học chạy "
          "riêng cho từng phiên bản (khởi động bằng dự báo walk-forward của bản sáng trước giai đoạn kiểm định). "
          "Ba phiên bản được so trên **cùng các ngày**. Mốc so sánh: Naive (giá giữ nguyên), "
          "\"luôn đoán tăng\"/chiều phổ biến hơn, và tần suất tăng lịch sử (cho xác suất).\n",
          "Cột: TheilU = RMSE / RMSE(Naive) (< 1 là hơn Naive); DM p: kiểm định Diebold–Mariano so với Naive; "
          "Đúng chiều: % phiên đoán đúng tăng/giảm (chỉ phiên giá có đổi); Mốc chiều: % của chiều phổ biến hơn "
          "(≥ \"luôn đoán tăng\"); p (chiều): kiểm định nhị thức một phía \"đúng chiều > mốc\"; Brier: sai số bình phương của P(tăng) (thấp là tốt), skill so với tần suất lịch sử; "
          "Phủ 80%: tỷ lệ giá thật rơi vào khoảng \"nhiều khả năng\".\n"]
    results = {"cutoff": "thanh 1 giờ đóng lúc 12:00 UTC (19:00 giờ VN)", "lock_date": LOCK_DATE, "targets": {}}
    for target in ("sjc_sell", "ring_sell"):
        print(f"== {target}")
        res = evening_backtest(df, target, hourly)
        wf_m = pd.read_csv(DATA_PROCESSED / f"backtest_{target}_h1.csv", index_col=0, parse_dates=True)
        S = summarize(res, wf_m)
        edge, why = edge_verdict(S)
        save_state(target, res["evening"][1])
        days = res["days"]
        on_e, on_p, on_m = res["evening"][0].loc[days], res["prev"][0].loc[days], res["morning"][0].loc[days]
        pd.DataFrame({"actual": on_e.actual, "price_t": on_e.price_t,
                      "Ensemble": on_e.Ensemble, "lo80": on_e.lo80, "hi80": on_e.hi80, "p_up": on_e.p_up,
                      "Ensemble_morning": on_m.Ensemble, "p_up_morning": on_m.p_up,
                      "Ensemble_prev": on_p.Ensemble, "p_up_prev": on_p.p_up}
                     ).to_csv(DATA_PROCESSED / f"backtest_evening_{target}_h1.csv")
        results["targets"][target] = {
            "has_edge": edge, "verdict": why, "period": [f"{days[0]:%Y-%m-%d}", f"{days[-1]:%Y-%m-%d}"],
            "n_days": int(len(days)), "repro_maxdiff": res["repro_maxdiff"],
            "feature_window_maxdiff": res["feature_window_maxdiff"], "stale_gold_days": res["stale_gold_days"],
            "summary": S}
        md.append(f"\n## {NAMES[target]} – {days[0]:%d/%m/%Y} → {days[-1]:%d/%m/%Y} ({len(days)} phiên)\n")
        for period, title in (("all", "Toàn giai đoạn có giá theo giờ"),
                              ("locked", f"Giai đoạn khoá (sau {LOCK_DATE}, chưa từng dùng để chỉnh tham số)")):
            if period not in S:
                continue
            P = S[period]
            md.append(f"\n### {title}\n")
            md.append("| Phiên bản | TheilU | DM p | Đúng chiều % | Mốc chiều % | p (chiều) | Brier | Brier skill | Phủ 80% | N |")
            md.append("|---|---|---|---|---|---|---|---|---|---|")
            for v in ("morning", "evening", "prev"):
                r = P[v]
                md.append(f"| {VLABEL[v]} | {_f(r['TheilU'])} | {_f(r['DM_p'])} | {_f(r['DirAcc_%'], 1)} | "
                          f"{_f(r['DirBase_%'], 1)} | {_f(r['Dir_p'])} | {_f(r['Brier'])} | {r['BrierSkill']:+.3f} | {r['cov80'] * 100:.1f}% | {r['N']} |")
            b = P["baseline"]
            md.append(f"\nMốc: \"luôn đoán tăng\" đúng **{b['always_up_%']:.1f}%** trong {b['n_moved']} phiên giá có đổi; "
                      f"{b['share_flat_%']:.1f}% phiên giá đứng yên; Brier của tần suất lịch sử = {_f(b['Brier_clim'])}.\n")
        md.append("\n**Bản sơ bộ: khi nói ... thì đúng mấy lần** (phiên giá đứng yên tính là *không đúng*):\n")
        md.append("| Mức | Số lần | Đúng |")
        md.append("|---|---|---|")
        for k, v in S["buckets"].items():
            rate = "–" if v["rate"] is None else f"{v['rate'] * 100:.0f}%"
            md.append(f"| {BLABEL[k]} | {v['n']} | {rate} |")
        md.append(f"\n**Kết luận cổng trung thực:** {'CÓ lợi thế → thông báo 19h được nói chiều (theo mức tin cậy)' if edge else 'KHÔNG đủ lợi thế → thông báo 19h ghi “Khó đoán”'} ({why}).\n")
        fw = res["feature_window_maxdiff"]
        md.append(f"\n*Kiểm tra kỹ thuật:* tái tạo dự báo bản sáng lệch tối đa {res['repro_maxdiff']:.2e} (log-return) so với "
                  f"backtest đã lưu; tính đặc trưng trên cửa sổ cắt lệch tối đa {fw:.1e} so với đặc trưng gốc; "
                  f"{res['stale_gold_days']} ngày chưa có giá vàng của phiên T trước 19h (dùng giá gần nhất).\n")
    summ = ["\n## Tóm tắt\n"]
    for t, r in results["targets"].items():
        S = r["summary"]["all"]
        e, m = S["evening"], S["morning"]
        summ.append(f"- **{NAMES[t]}** ({r['n_days']} phiên): bản 19h đoán đúng chiều {e['DirAcc_%']:.1f}% số phiên giá có đổi "
                    f"(mốc {e['DirBase_%']:.1f}%, p = {e['Dir_p']:.3f}; bản 7h sáng {m['DirAcc_%']:.1f}%), sai số bằng "
                    f"{e['TheilU'] * 100:.1f}% của Naive (DM p = {e['DM_p']:.2f}; bản sáng {m['TheilU'] * 100:.1f}%, p = {m['DM_p']:.3f}), "
                    f"Brier skill {e['BrierSkill']:+.3f} (bản sáng {m['BrierSkill']:+.3f}). "
                    f"→ **{'nói chiều theo mức tin cậy' if r['has_edge'] else 'Khó đoán'}**.")
    rates = [b["rate"] for r in results["targets"].values() for b in r["summary"]["buckets"].values()
             if b["rate"] is not None and b["n"] >= 20]
    rng = f"{min(rates) * 100:.0f}–{max(rates) * 100:.0f}%" if rates else "–"
    summ.append("\nPhần lớn lợi thế của bản sáng đến từ diễn biến **phiên Mỹ** (đêm T) mà lúc 19h chưa có. Giá thế giới lúc 19h "
                "giữ lại được một phần tín hiệu về chiều (so với khi không dùng nó), nhưng chưa đủ để vượt Naive có ý nghĩa thống kê "
                "và các mức \"nghiêng về tăng/giảm\" của bản 19h chỉ đúng " + rng + " số lần (mức có ≥ 20 lần, tính cả phiên giá đứng yên). "
                "Vì vậy thông báo 19h chỉ báo **giá hôm nay** và **khoảng giá có thể** cho phiên tới; chiều tăng/giảm ghi "
                "**\"Khó đoán\"** cho tới khi kiểm định (chạy lại mỗi tuần) cho thấy có lợi thế. Dự báo chính thức vẫn là bản 7h sáng.\n"
                if not any(r["has_edge"] for r in results["targets"].values()) else
                "\nThông báo 19h chỉ nói chiều cho mục có lợi thế; mục còn lại ghi \"Khó đoán\". Dự báo chính thức vẫn là bản 7h sáng.\n")
    md[4:4] = summ
    md.append("\n## Hạn chế\n")
    md.append("- Giá trong nước ngày T trong kiểm định là giá **cuối ngày** (bản ghi ~23h59 của CafeF). Thông báo dùng giá lúc 19h; "
              "dữ liệu CafeF cho thấy giá hầu như không đổi sau 19h (1/465 ngày khác biệt với SJC trong lịch sử CafeF), nên ảnh hưởng nhỏ.\n"
              "- Giá theo giờ của Yahoo chỉ có ~2 năm gần nhất, nên giai đoạn kiểm định ngắn hơn bản sáng.\n"
              "- Khi chạy thật, mô hình được huấn luyện trên mọi nhãn đã biết (mới hơn so với lịch huấn luyện lại 21 phiên trong kiểm định), "
              "và lớp tự học dùng trạng thái tại lần kiểm định gần nhất (chạy lại tự động mỗi tuần).\n"
              "- Nếu gửi bù muộn hơn 19h, giá thế giới dùng là giá lúc gửi (nhiều thông tin hơn, không ít hơn).\n")
    (REPORTS / "04_evening_preliminary.md").write_text("\n".join(md), encoding="utf-8")
    write_eval(results)
    print(f"Xong trong {time.time() - t0:.0f}s -> reports/04_evening_preliminary.md, data/processed/evening_eval.json")
    for t, r in results["targets"].items():
        e = r["summary"]["all"]["evening"]
        print(f"  {t}: có lợi thế={r['has_edge']} ({r['verdict']}); TheilU {e['TheilU']:.3f}, DM p {e['DM_p']:.3f}, "
              f"đúng chiều {e['DirAcc_%']:.1f}% vs mốc {e['DirBase_%']:.1f}%, Brier skill {e['BrierSkill']:+.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
