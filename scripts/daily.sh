#!/bin/zsh
# Chạy dự báo hằng ngày (gọi bởi launchd lúc 7h sáng T3–T7, giờ VN).
# Thu thập dữ liệu mới -> chấm điểm dự báo cũ -> backtest/tự học -> dự báo mới.
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT" || exit 1
mkdir -p logs
LOG="logs/daily_$(date +%Y-%m-%d).log"
{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') bắt đầu"
  .venv/bin/python -u scripts/run_pipeline.py --fast
  STATUS=$?
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') kết thúc, mã thoát $STATUS"
} >> "$LOG" 2>&1

# Thông báo macOS với dự báo 1 ngày
MSG=$(.venv/bin/python - <<'PY' 2>/dev/null
import json
f = json.load(open("data/processed/forecast.json", encoding="utf-8"))
r = f["targets"]["sjc_sell"]["horizons"]["1"]
p0 = f["targets"]["sjc_sell"]["last_price"]
head = (f"{r['pred_price']:.2f} tr ({r['pred_return_pct']:+.2f}%)" if r.get("has_edge", True)
        else "mô hình không vượt Naive")
print(f"SJC chốt phiên {r['target_date']}: {head}, "
      f"khoảng 90% {r['lo90']:.1f}–{r['hi90']:.1f}, P(tăng) {r['p_up']*100:.0f}%. Giá hiện tại: {p0:.2f}")
PY
)
if [ $STATUS -eq 0 ] && [ -n "$MSG" ]; then
  osascript -e "display notification \"$MSG\" with title \"Dự báo vàng Việt Nam\""
else
  osascript -e "display notification \"Lỗi khi chạy dự báo – xem $LOG\" with title \"Dự báo vàng Việt Nam\""
fi
# giữ log 60 ngày gần nhất
ls -1t logs/daily_*.log 2>/dev/null | tail -n +61 | xargs -I{} rm -f "{}"
exit $STATUS
