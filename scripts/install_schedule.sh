#!/bin/zsh
# Cài lịch chạy tự động bằng launchd trên macOS (2 tác vụ):
#   com.vngold.dailyforecast  7h00 sáng T3–T7: cập nhật dữ liệu + dự báo chính thức, đăng lên ứng dụng (im lặng)
#   com.vngold.evening        19h00 T2–T6: thông báo giá hôm nay + dự báo sơ bộ tới điện thoại (ntfy) và máy Mac
# Cả hai có RunAtLoad + kiểm tra mỗi 15 phút để chạy bù khi máy tắt/ngủ; script tự chặn chạy trùng/chạy sớm.
#   ./scripts/install_schedule.sh          # cài / cập nhật lịch
#   ./scripts/install_schedule.sh remove   # gỡ lịch
set -e
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$PROJECT/logs" "$HOME/Library/LaunchAgents"
for LABEL in com.vngold.dailyforecast com.vngold.evening; do
  DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  if [ "$1" = "remove" ]; then
    rm -f "$DEST"; echo "Đã gỡ lịch $LABEL"; continue
  fi
  sed "s#__PROJECT_DIR__#$PROJECT#g" "$PROJECT/scripts/$LABEL.plist" > "$DEST"
  launchctl bootstrap "gui/$(id -u)" "$DEST"
  echo "Đã cài lịch: $DEST"
done
[ "$1" = "remove" ] && exit 0
echo "  - sáng: $PROJECT/scripts/daily.sh (7h00 thứ Ba – thứ Bảy)"
echo "  - tối:  $PROJECT/scripts/evening.sh (19h00 thứ Hai – thứ Sáu)"
[ -f "$PROJECT/config/notify.env" ] || echo "Chú ý: chưa có config/notify.env (chép từ config/notify.env.example rồi điền NTFY_TOPIC)."
