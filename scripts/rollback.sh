#!/usr/bin/env bash
# Manually roll back to the images recorded by the last successful deploy
# (.deploy/previous.env), or to explicit ones:
#
#   ./scripts/rollback.sh
#   ./scripts/rollback.sh <fastapi-image> <frontend-image>
#
# Restarts only fastapi + frontend. Does NOT touch the database: schema/data
# changes are not reverted (see DEPLOYMENT.md, "Rollback").
set -Eeuo pipefail
# shellcheck source=scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$PROJECT_DIR"

[ "$(id -u)" -ne 0 ] || die "run as the deploy user, not root"

if [ "$#" -eq 2 ]; then
  api=$1 web=$2 sha=""
else
  [ -f "$STATE_DIR/previous.env" ] || die "no $STATE_DIR/previous.env - pass images explicitly"
  # shellcheck disable=SC1091
  source "$STATE_DIR/previous.env"
  api=${PREV_FASTAPI_IMAGE:-} web=${PREV_FRONTEND_IMAGE:-} sha=${PREV_GIT_SHA:-}
fi
[ -n "$api" ] && [ -n "$web" ] || die "rollback target incomplete (api='$api' web='$web')"

log "Rolling back to api=$api web=$web"
read -r -p "Type 'yes' to continue: " confirm
[ "$confirm" = yes ] || die "aborted"

export FASTAPI_IMAGE=$api FRONTEND_IMAGE=$web
if [ -n "$sha" ]; then git reset --keep "$sha"; fi
set_env FASTAPI_IMAGE "$api"
set_env FRONTEND_IMAGE "$web"
"${COMPOSE[@]}" pull fastapi frontend || warn "pull failed - using local images if present"
"${COMPOSE[@]}" up -d --no-deps fastapi frontend
wait_healthy "$API_CONTAINER" "$api"
wait_healthy "$WEB_CONTAINER" "$web"
nginx_reload
printf '%s ROLLBACK to %s / %s\n' "$(date -Is)" "$api" "$web" >> "$STATE_DIR/history.log"
log "Rollback complete"
