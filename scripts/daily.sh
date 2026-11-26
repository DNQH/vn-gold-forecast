#!/bin/zsh
# Chạy dự báo hằng ngày (launchd: 7h sáng T3–T7 giờ VN, + khi đăng nhập/khởi động + mỗi 15 phút; guard bên dưới tránh chạy trùng/chạy sớm).
# Thu thập dữ liệu mới -> chấm điểm dự báo cũ -> backtest/tự học -> dự báo mới.
# Tự động đăng dữ liệu mới lên GitHub Pages (ứng dụng điện thoại) sau mỗi lần chạy thành công.
# Bản sáng chạy IM LẶNG (không hiện thông báo): kết quả ghi vào logs/ và logs/.morning_status
# ("YYYY-MM-DD ok|fail ..."); thông báo 19h (scripts/evening.sh) sẽ nhắc nếu sáng nay bị lỗi.
# Đặt AUTO_PUSH=0 để TẮT (chỉ xuất docs/data/latest.json trên máy, không commit/push). Hoặc chạy: AUTO_PUSH=0 ./scripts/daily.sh
#
# Phạm vi commit tự động (để repo công khai không phình to):
#   - hằng ngày: chỉ file nhỏ – docs/data (ứng dụng điện thoại), data/processed/forecast.json, predictions_log.csv
#   - lần chạy thứ Bảy (hoặc FULL_PUSH=1): thêm data/processed (backtest, dataset…), reports và data/raw (cache thô
#     cần cho bản clone mới). Các file lớn này bị ghi lại gần như toàn bộ mỗi ngày (~1 MB nén/lần).
AUTO_PUSH="${AUTO_PUSH:-1}"
FULL_PUSH="${FULL_PUSH:-0}"
# launchd có PATH rất ngắn: thêm nơi đặt gh/git (credential helper hiện là osxkeychain, không cần PATH nhưng thêm cho chắc)
export PATH="$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export GIT_TERMINAL_PROMPT=0
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT" || exit 1
mkdir -p logs
PUSH_NOTE=""

# ---- Guard (chạy bù): launchd gọi script lúc 7h, lúc đăng nhập/khởi động và mỗi 15 phút.
# Bỏ qua guard khi có --force hoặc --publish-only. VNGOLD_NOW='YYYY-MM-DD HH:MM' để kiểm thử.
# --check-only: chỉ in quyết định của guard (RUN/SKIP:lý do) rồi thoát, không chạy gì.
CHECK_ONLY=0; [ "$1" = "--check-only" ] && CHECK_ONLY=1
NOW_VN="${VNGOLD_NOW:-$(TZ=Asia/Ho_Chi_Minh date '+%Y-%m-%d %H:%M')}"
TODAY="${NOW_VN%% *}"
HHMM="${NOW_VN##* }"; MINS=$(( 10#${HHMM%%:*} * 60 + 10#${HHMM##*:} ))
WDAY="$(date -j -f '%Y-%m-%d %H:%M' "$NOW_VN" +%u 2>/dev/null)"
CATCHUP=0; [ "$MINS" -ge 435 ] && CATCHUP=1   # bắt đầu muộn hơn 7h15
LOCKDIR="logs/.run.lock"; HAVE_LOCK=0
LOG="logs/daily_${TODAY}.log"
if [ "$1" != "--force" ] && [ "$1" != "--publish-only" ]; then
  skip() { [ "$CHECK_ONLY" = "1" ] && echo "SKIP: $1"; exit 0; }
  [ -n "$WDAY" ] && [ "$WDAY" -ge 2 ] && [ "$WDAY" -le 6 ] || skip "không phải ngày chạy (T3–T7)"
  [ "$MINS" -ge 420 ] || skip "chưa đến 7h00"
  [ "$(cat logs/.last_success 2>/dev/null)" = "$TODAY" ] && skip "hôm nay đã chạy thành công"
  for f in logs/.attempts_*(N); do [ "$f" = "logs/.attempts_$TODAY" ] || rm -f "$f"; done
  ATT="$(cat "logs/.attempts_$TODAY" 2>/dev/null)"; ATT=${ATT:-0}
  [ "$ATT" -lt 3 ] || skip "đã thử $ATT lần hôm nay"
  if [ "$CHECK_ONLY" = "1" ]; then echo "RUN (lần thử thứ $((ATT+1)), chạy bù=$CATCHUP)"; exit 0; fi
  if ! mkdir "$LOCKDIR" 2>/dev/null; then
    if [ -n "$(find "$LOCKDIR" -maxdepth 0 -mmin +60 2>/dev/null)" ]; then
      rm -rf "$LOCKDIR"; mkdir "$LOCKDIR" 2>/dev/null || exit 0
    else
      exit 0
    fi
  fi
  HAVE_LOCK=1
  trap '[ "$HAVE_LOCK" = "1" ] && rmdir "$LOCKDIR" 2>/dev/null' EXIT
  echo $((ATT+1)) > "logs/.attempts_$TODAY"
  # đợi mạng tối đa ~2 phút (vừa khởi động mạng có thể chưa lên)
  NET=0
  for i in {1..24}; do
    if /sbin/ping -c1 -t3 1.1.1.1 >/dev/null 2>&1 || /usr/bin/curl -sI --max-time 5 https://github.com >/dev/null 2>&1; then NET=1; break; fi
    sleep 5
  done
  if [ "$NET" != "1" ]; then
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') không có mạng sau ~2 phút (lần thử $((ATT+1))/3)" >> "$LOG"
    echo "$TODAY fail network" > logs/.morning_status
    exit 1
  fi
fi

# Xuất dữ liệu web, rồi (nếu AUTO_PUSH=1) commit + đồng bộ + push. Lỗi push KHÔNG làm đổi mã thoát của pipeline.
GIT=/usr/bin/git
publish() {
  echo "--- $(date '+%H:%M:%S') xuất dữ liệu web"
  if ! .venv/bin/python scripts/export_web.py; then
    echo "export_web lỗi: KHÔNG đăng (giữ nguyên bản cũ trên điện thoại)"; PUSH_NOTE=" (xuất dữ liệu web lỗi)"; return 1
  fi
  if [ "$AUTO_PUSH" != "1" ]; then echo "AUTO_PUSH=$AUTO_PUSH: bỏ qua commit/push"; return 0; fi
  if [ "$($GIT symbolic-ref --short -q HEAD)" != "main" ] || [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ] || [ -f .git/MERGE_HEAD ]; then
    echo "repo không ở nhánh main hoặc đang rebase/merge dở: bỏ qua commit/push"; PUSH_NOTE=" (chưa đăng: repo đang bận)"; return 1
  fi
  local -a pub
  if [ "$FULL_PUSH" = "1" ] || [ "$(date +%u)" = "6" ]; then
    pub=(docs/data data/processed reports data/raw); echo "commit đầy đủ (hằng tuần)"
  else
    pub=(docs/data data/processed/forecast.json data/processed/predictions_log.csv)
  fi
  $GIT add -- "${pub[@]}"
  if $GIT diff --cached --quiet -- "${pub[@]}"; then
    echo "Không có thay đổi để commit"
  else
    # chỉ commit đúng các đường dẫn trên (không cuốn theo thứ người dùng đang stage dở)
    $GIT commit -q -m "Daily data $(date +%Y-%m-%d)" -- "${pub[@]}" || { echo "git commit lỗi"; PUSH_NOTE=" (commit lỗi)"; return 1; }
  fi
  # origin/main có thể đã đi trước (vd. sửa README trên GitHub): rebase lên trước khi push.
  # --autostash: cache thô/tệp lớn chưa commit (thay đổi mỗi ngày) không làm hỏng rebase.
  if ! $GIT fetch -q origin main; then
    echo "fetch THẤT BẠI"; PUSH_NOTE=" (chưa đăng được lên điện thoại: không kết nối được GitHub)"; return 1
  fi
  if ! $GIT merge-base --is-ancestor origin/main HEAD; then
    if ! $GIT rebase -q --autostash origin/main; then
      $GIT rebase --abort 2>/dev/null
      echo "rebase lên origin/main bị xung đột: đã huỷ, cần xử lý tay"; PUSH_NOTE=" (chưa đăng: xung đột với GitHub)"; return 1
    fi
  fi
  if $GIT push -q origin main 2>&1 || { echo "push lỗi, thử lại"; sleep 20; $GIT -c http.postBuffer=524288000 push -q origin main 2>&1; }; then
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
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') bắt đầu (chạy bù=$CATCHUP)"
  .venv/bin/python -u scripts/run_pipeline.py --fast
  STATUS=$?
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') kết thúc, mã thoát $STATUS"
  if [ $STATUS -eq 0 ]; then
    echo "$TODAY" > logs/.last_success
    if publish; then echo "$TODAY ok" > logs/.morning_status; else echo "$TODAY ok push_fail$PUSH_NOTE" > logs/.morning_status; fi
  else
    echo "$TODAY fail pipeline_exit_$STATUS" > logs/.morning_status
  fi
} >> "$LOG" 2>&1

# Không hiện thông báo ở đây nữa: mọi thông tin (kể cả lỗi sáng nay) được gửi một lần lúc 19h (scripts/evening.sh).
# giữ log 60 ngày gần nhất
ls -1t logs/daily_*.log 2>/dev/null | tail -n +61 | xargs -I{} rm -f "{}"
exit $STATUS
