#!/usr/bin/env bash
# Shared helpers for deploy.sh / rollback.sh / init_ssl.sh. Sourced, not run.
# shellcheck disable=SC2034  # variables are consumed by the scripts that source this

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="$PROJECT_DIR/.deploy"
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)

API_CONTAINER=prod-docker-app-fastapi
WEB_CONTAINER=prod-docker-app-frontend
NGINX_CONTAINER=prod-docker-app-nginx

log()  { printf '==> %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# env_get KEY -> prints the value from .env. Parsed with grep, never sourced,
# so a stray `$(...)` in a password can't execute anything.
env_get() {
  local line
  line=$(grep -E "^$1=" "$PROJECT_DIR/.env" | tail -n1) || return 1
  printf '%s' "${line#*=}"
}

# set_env KEY VALUE -> replace (or append) KEY in .env atomically, keeping 600.
set_env() {
  local key=$1 value=$2 tmp
  tmp=$(mktemp "$PROJECT_DIR/.env.XXXXXX")
  chmod 600 "$tmp"
  if grep -q "^${key}=" "$PROJECT_DIR/.env"; then
    awk -v k="$key" -v v="$value" 'BEGIN{FS=OFS="="} $1==k{print k"="v; next} {print}' \
      "$PROJECT_DIR/.env" > "$tmp"
  else
    { cat "$PROJECT_DIR/.env"; printf '%s=%s\n' "$key" "$value"; } > "$tmp"
  fi
  mv "$tmp" "$PROJECT_DIR/.env"
}

container_image() { docker inspect -f '{{.Config.Image}}' "$1" 2>/dev/null || true; }

# wait_healthy CONTAINER EXPECTED_IMAGE [TRIES]
# Succeeds only when the container is running the EXPECTED image AND reports
# healthy. Checking the image guards against reading the health of the old
# container while Compose is still swapping it out.
wait_healthy() {
  local c=$1 want=$2 tries=${3:-36} i img st
  for ((i = 1; i <= tries; i++)); do
    img=$(container_image "$c")
    st=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$c" 2>/dev/null || echo missing)
    if [ "$img" = "$want" ] && [ "$st" = healthy ]; then
      log "$c is healthy ($want)"
      return 0
    fi
    echo "    waiting for $c ($i/$tries): image=${img:-none} status=$st"
    sleep 5
  done
  return 1
}

nginx_reload() {
  docker exec "$NGINX_CONTAINER" nginx -t
  docker exec "$NGINX_CONTAINER" nginx -s reload
}
