#!/bin/zsh
# Thông báo 19h (thứ Hai – thứ Sáu, giờ VN): giá vàng hôm nay + dự báo SƠ BỘ cho phiên kế tiếp,
# gửi cùng lúc tới điện thoại (ntfy) và máy Mac. launchd gọi script lúc 19h00, khi đăng nhập/khởi động
# và mỗi 15 phút; guard bên dưới đảm bảo mỗi ngày chỉ gửi MỘT lần, không gửi sớm, không gửi nhầm ngày.
#
#   ./scripts/evening.sh                     # chạy theo guard (dùng trong launchd)
#   ./scripts/evening.sh --check-only        # chỉ in quyết định của guard (RUN/SKIP:lý do)
#   ./scripts/evening.sh --dry-run --force   # dựng tin nhắn và in ra, KHÔNG gửi, không ghi dấu
#   ./scripts/evening.sh --force             # gửi ngay (bỏ guard). Trước 19h/cuối tuần: tiêu đề "(gửi thử)" và
#                                            # KHÔNG ghi dấu "đã gửi hôm nay" (tin 19h thật vẫn được gửi)
# Giờ giả để kiểm thử: VNGOLD_NOW='YYYY-MM-DD HH:MM'.
export PATH="$HOME/.local/bin:$(cd "$(dirname "$0")/.." && pwd)/.venv/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin:$PATH"
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT" || exit 1
mkdir -p logs

CHECK_ONLY=0; FORCE=0; DRY=0
for a in "$@"; do
  case "$a" in
    --check-only) CHECK_ONLY=1 ;;
    --force) FORCE=1 ;;
    --dry-run) DRY=1 ;;
    *) echo "tuỳ chọn không hợp lệ: $a"; exit 64 ;;
  esac
done
NOW_VN="${VNGOLD_NOW:-$(TZ=Asia/Ho_Chi_Minh date '+%Y-%m-%d %H:%M')}"
TODAY="${NOW_VN%% *}"
HHMM="${NOW_VN##* }"; MINS=$(( 10#${HHMM%%:*} * 60 + 10#${HHMM##*:} ))
WDAY="$(date -j -f '%Y-%m-%d %H:%M' "$NOW_VN" +%u 2>/dev/null)"
IN_WINDOW=0   # T2–T6 và từ 19h00 tới hết ngày (sau nửa đêm là ngày khác -> chưa tới 19h -> bỏ qua)
[ -n "$WDAY" ] && [ "$WDAY" -ge 1 ] && [ "$WDAY" -le 5 ] && [ "$MINS" -ge 1140 ] && IN_WINDOW=1
CATCHUP=0; [ "$MINS" -ge 1155 ] && CATCHUP=1   # bắt đầu muộn hơn 19h15
LOG="logs/evening_${TODAY}.log"
MARK="logs/.evening_last_success"
LOCKDIR="logs/.evening.lock"; HAVE_LOCK=0
ATT=0

if [ "$FORCE" != "1" ]; then
  skip() { [ "$CHECK_ONLY" = "1" ] && echo "SKIP: $1"; exit 0; }
  [ -n "$WDAY" ] && [ "$WDAY" -ge 1 ] && [ "$WDAY" -le 5 ] || skip "không phải ngày gửi (T2–T6)"
  [ "$MINS" -ge 1140 ] || skip "chưa đến 19h00"
  [ "$(cat "$MARK" 2>/dev/null)" = "$TODAY" ] && skip "hôm nay đã gửi"
  for f in logs/.evening_attempts_*(N); do [ "$f" = "logs/.evening_attempts_$TODAY" ] || rm -f "$f"; done
  ATT="$(cat "logs/.evening_attempts_$TODAY" 2>/dev/null)"; ATT=${ATT:-0}
  [ "$ATT" -lt 3 ] || skip "đã thử $ATT lần hôm nay"
  # bản 7h sáng đang chạy bù (dataset/forecast đang được ghi): đợi lần kiểm tra 15 phút sau, không tính lần thử
  if [ -d logs/.run.lock ] && [ -z "$(find logs/.run.lock -maxdepth 0 -mmin +60 2>/dev/null)" ]; then
    skip "bản sáng đang chạy, đợi lần sau"
  fi
  if [ "$CHECK_ONLY" = "1" ]; then echo "RUN (lần thử thứ $((ATT+1)), gửi bù=$CATCHUP)"; exit 0; fi
fi
if [ "$CHECK_ONLY" = "1" ]; then echo "RUN (--force, gửi bù=$CATCHUP)"; exit 0; fi

if ! mkdir "$LOCKDIR" 2>/dev/null; then
  if [ -n "$(find "$LOCKDIR" -maxdepth 0 -mmin +30 2>/dev/null)" ]; then
    rm -rf "$LOCKDIR"; mkdir "$LOCKDIR" 2>/dev/null || exit 0
  else
    echo "đang có một lần gửi khác chạy: thoát"; exit 0
  fi
fi
HAVE_LOCK=1
trap '[ "$HAVE_LOCK" = "1" ] && rmdir "$LOCKDIR" 2>/dev/null' EXIT

ARGS=()
[ "$DRY" = "1" ] && ARGS+=(--dry-run)
if [ "$FORCE" = "1" ] && [ "$IN_WINDOW" != "1" ]; then ARGS+=(--test); fi
if [ "$FORCE" != "1" ]; then
  [ "$DRY" = "1" ] || echo $((ATT+1)) > "logs/.evening_attempts_$TODAY"
  [ "$CATCHUP" = "1" ] && ARGS+=(--catchup)
  [ "$((ATT+1))" -ge 3 ] && ARGS+=(--last-attempt)
fi

if [ "$DRY" = "1" ]; then   # dry-run: in thẳng ra màn hình, không ghi log/dấu
  .venv/bin/python -u scripts/evening.py "${ARGS[@]}"
  exit $?
fi

# đợi mạng tối đa ~2 phút (máy vừa thức dậy có thể chưa có mạng)
NET=0
for i in {1..24}; do
  if /sbin/ping -c1 -t3 1.1.1.1 >/dev/null 2>&1 || /usr/bin/curl -sI --max-time 5 https://ntfy.sh >/dev/null 2>&1; then NET=1; break; fi
  sleep 5
done
if [ "$NET" != "1" ]; then
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') không có mạng sau ~2 phút (lần thử $((ATT+1))/3)" >> "$LOG"
  exit 1
fi

{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') bắt đầu (giờ VN dùng: $NOW_VN, force=$FORCE, gửi bù=$CATCHUP, args: ${ARGS[*]})"
  .venv/bin/python -u scripts/evening.py "${ARGS[@]}"
  STATUS=$?
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') kết thúc, mã thoát $STATUS"
  if [ $STATUS -eq 0 ] && [ "$IN_WINDOW" = "1" ]; then echo "$TODAY" > "$MARK"; fi
  # kiểm định lại bản sơ bộ mỗi tuần (SAU khi đã gửi, không làm chậm thông báo); lỗi thì giữ kết quả cũ
  if [ $STATUS -eq 0 ] && [ "$FORCE" != "1" ] && \
     [ -z "$(find data/processed/evening_eval.json -mtime -6 2>/dev/null)" ]; then
    echo "--- $(date '+%H:%M:%S') kiểm định lại bản sơ bộ (hằng tuần)"
    .venv/bin/python -u scripts/eval_evening.py 2>&1 | tail -4
  fi
} >> "$LOG" 2>&1
[ "$STATUS" = "" ] && STATUS=1
tail -n 4 "$LOG"
ls -1t logs/evening_*.log 2>/dev/null | tail -n +61 | xargs -I{} rm -f "{}"
exit $STATUS
