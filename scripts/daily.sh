#!/bin/zsh
# Chạy dự báo hằng ngày (gọi bởi launchd lúc 7h sáng T3–T7, giờ VN).
# Thu thập dữ liệu mới -> chấm điểm dự báo cũ -> backtest/tự học -> dự báo mới.
# Tự động đăng dữ liệu mới lên GitHub Pages (ứng dụng điện thoại) sau mỗi lần chạy thành công.
# Đặt AUTO_PUSH=0 để TẮT (chỉ xuất docs/data/latest.json trên máy, không commit/push). Hoặc chạy: AUTO_PUSH=0 ./scripts/daily.sh
AUTO_PUSH="${AUTO_PUSH:-1}"
# launchd có PATH rất ngắn: thêm nơi đặt gh/git (credential helper hiện là osxkeychain, không cần PATH nhưng thêm cho chắc)
export PATH="$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export GIT_TERMINAL_PROMPT=0
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT" || exit 1
mkdir -p logs
LOG="logs/daily_$(date +%Y-%m-%d).log"
PUSH_NOTE=""

# Xuất dữ liệu web, rồi (nếu AUTO_PUSH=1) commit + push. Lỗi push KHÔNG làm đổi mã thoát của pipeline.
publish() {
  echo "--- $(date '+%H:%M:%S') xuất dữ liệu web"
  if ! .venv/bin/python scripts/export_web.py 2>&1 | grep -v "streamlit.runtime"; then :; fi
  [ -s docs/data/latest.json ] || { echo "export_web lỗi: không có docs/data/latest.json"; PUSH_NOTE=" (xuất dữ liệu web lỗi)"; return 1; }
  if [ "$AUTO_PUSH" != "1" ]; then echo "AUTO_PUSH=$AUTO_PUSH: bỏ qua commit/push"; return 0; fi
  /usr/bin/git add docs/data data/processed reports
  if /usr/bin/git diff --cached --quiet; then
    echo "Không có thay đổi để commit"
  else
    /usr/bin/git commit -q -m "Daily data $(date +%Y-%m-%d)" || { echo "git commit lỗi"; PUSH_NOTE=" (commit lỗi)"; return 1; }
  fi
  if /usr/bin/git push origin main 2>&1; then
    echo "push OK"
  else
    echo "push THẤT BẠI"; PUSH_NOTE=" (chưa đăng được lên điện thoại: push lỗi)"; return 1
  fi
}

if [ "$1" = "--publish-only" ]; then
  { echo "=== $(date '+%Y-%m-%d %H:%M:%S') chỉ đăng (publish-only)"; publish; echo "=== publish-only mã $?"; } 2>&1 | tee -a "$LOG"
  exit 0
fi

{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') bắt đầu"
  .venv/bin/python -u scripts/run_pipeline.py --fast
  STATUS=$?
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') kết thúc, mã thoát $STATUS"
  if [ $STATUS -eq 0 ]; then publish; fi
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
  osascript -e "display notification \"$MSG$PUSH_NOTE\" with title \"Dự báo vàng Việt Nam\""
else
  osascript -e "display notification \"Lỗi khi chạy dự báo – xem $LOG\" with title \"Dự báo vàng Việt Nam\""
fi
# giữ log 60 ngày gần nhất
ls -1t logs/daily_*.log 2>/dev/null | tail -n +61 | xargs -I{} rm -f "{}"
exit $STATUS
