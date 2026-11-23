#!/bin/zsh
# Cài lịch chạy dự báo lúc 7h sáng (T3–T7) bằng launchd trên macOS.
#   ./scripts/install_schedule.sh          # cài / cập nhật lịch
#   ./scripts/install_schedule.sh remove   # gỡ lịch
set -e
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.vngold.dailyforecast"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
if [ "$1" = "remove" ]; then
  rm -f "$DEST"; echo "Đã gỡ lịch $LABEL"; exit 0
fi
mkdir -p "$PROJECT/logs" "$HOME/Library/LaunchAgents"
sed "s#__PROJECT_DIR__#$PROJECT#g" "$PROJECT/scripts/$LABEL.plist" > "$DEST"
launchctl bootstrap "gui/$(id -u)" "$DEST"
echo "Đã cài lịch: $DEST -> $PROJECT/scripts/daily.sh (7h00 sáng thứ Ba – thứ Bảy)"
