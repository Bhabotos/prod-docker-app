#!/usr/bin/env bash
# Deploys a specific pair of images on THIS server. Called by the GitHub
# Actions self-hosted runner (as the `deploy` user) and usable by hand.
#
#   FASTAPI_IMAGE=ghcr.io/o/prod-docker-app-fastapi:sha-abc1234 \
#   FRONTEND_IMAGE=ghcr.io/o/prod-docker-app-frontend:sha-abc1234 \
#   [DEPLOY_SHA=<full git sha>] ./scripts/deploy.sh [--all]
#
# Default mode touches ONLY fastapi + frontend. postgres, redis, nginx (which
# also serves bhabotos.com and n8n) and pgadmin are never restarted, so a
# normal deploy only interrupts the API for the few seconds a container swap takes.
# --all  converges the WHOLE stack (use after changing compose/edge config;
#        this recreates any service whose definition changed, incl. nginx).
#
# Safety net: if anything fails after containers are touched, the previous
# images + git revision are restored automatically and logs are printed.
set -Eeuo pipefail
# shellcheck source=scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$PROJECT_DIR"

MODE=apps
[ "${1:-}" = "--all" ] && MODE=all
: "${FASTAPI_IMAGE:?Set FASTAPI_IMAGE, e.g. ghcr.io/OWNER/prod-docker-app-fastapi:sha-abc1234}"
: "${FRONTEND_IMAGE:?Set FRONTEND_IMAGE, e.g. ghcr.io/OWNER/prod-docker-app-frontend:sha-abc1234}"
export FASTAPI_IMAGE FRONTEND_IMAGE

[ "$(id -u)" -ne 0 ] || die "run as the deploy user, not root (file ownership + git safe.directory)"
mkdir -p "$STATE_DIR/logs"
exec 9>"$STATE_DIR/lock"
flock -n 9 || die "another deploy is already running"

# ---------------------------------------------------------------- 1. validate
log "Validating environment"
[ -f .env ] || die ".env missing - copy .env.prod.example and fill it in"
perm=$(stat -c '%a' .env)
[ "${perm: -2}" = "00" ] || die ".env is mode $perm (readable by others) - run: chmod 600 .env"

for key in APP_NAME APP_ENV LOG_LEVEL POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB POSTGRES_PORT \
           REDIS_PORT PGADMIN_DEFAULT_EMAIL PGADMIN_DEFAULT_PASSWORD PGADMIN_PORT; do
  val=$(env_get "$key" || true)
  [ -n "$val" ] || die "$key is missing/empty in .env"
  case "$val" in *change-me*) die "$key still has the placeholder value in .env" ;; esac
done

"${COMPOSE[@]}" config -q || die "docker compose config is invalid"
if ! git diff --quiet || ! git diff --cached --quiet; then
  die "tracked files have local changes on the server; commit or restore them first (git status)"
fi
if [ "$MODE" = apps ]; then
  for c in prod-docker-app-postgres prod-docker-app-redis; do
    [ "$(docker inspect -f '{{.State.Running}}' "$c" 2>/dev/null)" = true ] \
      || die "$c is not running - start the stack once with: ./scripts/deploy.sh --all"
  done
fi

# ------------------------------------------------- 2. remember what to roll back to
prev_sha=$(git rev-parse HEAD)
prev_api=$(container_image "$API_CONTAINER")
prev_web=$(container_image "$WEB_CONTAINER")
log "Currently running: api=${prev_api:-none} web=${prev_web:-none} git=${prev_sha:0:7}"

rollback() {
  local code=$?
  trap - ERR
  warn "deploy failed (exit $code) - diagnostics follow"
  "${COMPOSE[@]}" ps || true
  "${COMPOSE[@]}" logs --no-color --tail 60 fastapi frontend nginx || true

  log "Rolling back to the previous version"
  git reset --keep "$prev_sha" || warn "could not reset git to ${prev_sha:0:7}"
  local svcs=()
  if [ -n "$prev_api" ]; then export FASTAPI_IMAGE=$prev_api; set_env FASTAPI_IMAGE "$prev_api"; svcs+=(fastapi); fi
  if [ -n "$prev_web" ]; then export FRONTEND_IMAGE=$prev_web; set_env FRONTEND_IMAGE "$prev_web"; svcs+=(frontend); fi
  if [ "${#svcs[@]}" -gt 0 ]; then
    "${COMPOSE[@]}" up -d --no-deps "${svcs[@]}" || true
    [ -z "$prev_api" ] || wait_healthy "$API_CONTAINER" "$prev_api" 24 || warn "previous api did not recover"
    [ -z "$prev_web" ] || wait_healthy "$WEB_CONTAINER" "$prev_web" 24 || warn "previous frontend did not recover"
    docker exec "$NGINX_CONTAINER" nginx -t >/dev/null 2>&1 && docker exec "$NGINX_CONTAINER" nginx -s reload || true
  else
    warn "no previous containers existed (first deploy) - nothing to roll back to"
  fi
  printf '%s FAILED deploy %s / %s -> rolled back to %s / %s\n' "$(date -Is)" "$FASTAPI_IMAGE" "$FRONTEND_IMAGE" "$prev_api" "$prev_web" \
    >> "$STATE_DIR/history.log"
  exit "$code"
}

# ---------------------------------------------------------- 3. code + images
# From here on any failure restores the previous git revision and images.
trap rollback ERR

log "Updating code (fast-forward only)"
git fetch --quiet origin main
git merge --ff-only "${DEPLOY_SHA:-origin/main}"

log "Pulling images (before touching anything running)"
"${COMPOSE[@]}" pull fastapi frontend

if docker inspect "$NGINX_CONTAINER" >/dev/null 2>&1; then
  log "Testing nginx config from the new checkout"
  docker exec "$NGINX_CONTAINER" nginx -t
fi

# ------------------------------------------------- 4. swap containers
set_env FASTAPI_IMAGE "$FASTAPI_IMAGE"
set_env FRONTEND_IMAGE "$FRONTEND_IMAGE"

if [ "$MODE" = all ]; then
  log "Converging the whole stack"
  "${COMPOSE[@]}" up -d postgres redis fastapi frontend nginx pgadmin
else
  log "Updating fastapi + frontend only"
  "${COMPOSE[@]}" up -d --no-deps fastapi frontend
fi

# ---------------------------------------------------------------- 5. verify
wait_healthy "$API_CONTAINER" "$FASTAPI_IMAGE"
wait_healthy "$WEB_CONTAINER" "$FRONTEND_IMAGE"

if docker inspect "$NGINX_CONTAINER" >/dev/null 2>&1; then
  log "Reloading nginx (picks up conf.d changes with no downtime)"
  nginx_reload
fi

api_domain=$(env_get API_DOMAIN || true)
conf="nginx/conf.d/${api_domain}.generated.conf"
if [ -n "$api_domain" ] && [ -f "$conf" ]; then
  if grep -q 'listen 443' "$conf"; then
    scheme=https port=443
  else
    scheme=http port=80
  fi
  log "End-to-end check: $scheme://$api_domain/api/health (via local nginx)"
  curl -fsS --max-time 10 --retry 5 --retry-delay 3 --retry-connrefused \
    --resolve "$api_domain:$port:127.0.0.1" "$scheme://$api_domain/api/health" | grep -q '"status":"ok"'
else
  warn "no generated nginx config for API_DOMAIN - skipped the public end-to-end check"
fi

# ------------------------------------------------------------- 6. record + tidy
trap - ERR
{
  echo "PREV_FASTAPI_IMAGE=$prev_api"
  echo "PREV_FRONTEND_IMAGE=$prev_web"
  echo "PREV_GIT_SHA=$prev_sha"
} > "$STATE_DIR/previous.env"
printf '%s OK %s / %s (git %s)\n' "$(date -Is)" "$FASTAPI_IMAGE" "$FRONTEND_IMAGE" "$(git rev-parse --short HEAD)" \
  >> "$STATE_DIR/history.log"

# Remove old images of THIS project only, keeping the running pair + the one
# just replaced (that is the rollback target). Never a global prune.
keep=$(printf '%s\n' "$FASTAPI_IMAGE" "$FRONTEND_IMAGE" "$prev_api" "$prev_web")
docker images --format '{{.Repository}}:{{.Tag}}' | grep -E '/prod-docker-app-(fastapi|frontend):' \
  | grep -vxF "$keep" | xargs -r docker rmi >/dev/null 2>&1 || true
docker image prune -f >/dev/null

log "Deploy complete: $FASTAPI_IMAGE + $FRONTEND_IMAGE"
