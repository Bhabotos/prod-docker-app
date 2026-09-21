#!/usr/bin/env bash
# Installs the recurring jobs into the CURRENT user's crontab (idempotent -
# lines are tagged and replaced, other cron entries are left alone):
#   02:00 daily  database backup       (scripts/backup.sh)
#   03:17 daily  certificate renewal   (scripts/renew_ssl.sh; no-op unless <30d left)
#   */15 min     status report -> log  (scripts/status.sh)
# Run as the deploy user. Prints the resulting crontab; change nothing with --print.
set -Eeuo pipefail
# shellcheck source=scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

TAG="# prod-docker-app"
LOGS="$STATE_DIR/logs"
mkdir -p "$LOGS"
new=$(cat <<CRON
0 2 * * *    cd $PROJECT_DIR && ./scripts/backup.sh    >> $LOGS/backup.log 2>&1  $TAG
17 3 * * *   cd $PROJECT_DIR && ./scripts/renew_ssl.sh >> $LOGS/renew.log 2>&1   $TAG
*/15 * * * * cd $PROJECT_DIR && ./scripts/status.sh    >> $LOGS/status.log 2>&1  $TAG
CRON
)
current=$(crontab -l 2>/dev/null | grep -vF "$TAG" || true)
if [ "${1:-}" = "--print" ]; then printf '%s\n%s\n' "$current" "$new"; exit 0; fi
printf '%s\n%s\n' "$current" "$new" | sed '/^$/d' | crontab -
log "Installed. Current crontab:"
crontab -l
