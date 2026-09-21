#!/usr/bin/env bash
# Basic server + stack health report. Exit code is non-zero if anything is
# wrong, so it works in cron or `watch`. No extra software required.
#   ./scripts/status.sh
set -uo pipefail
# shellcheck source=scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$PROJECT_DIR" || exit 1

bad=0
flag() { printf '  [%s] %s\n' "$1" "$2"; [ "$1" = OK ] || bad=1; }

echo "== Host =="
disk=$(df --output=pcent / | tail -n1 | tr -dc '0-9')
[ "$disk" -lt 85 ] && flag OK "disk / at ${disk}%" || flag FAIL "disk / at ${disk}% (>=85%)"
mem=$(free | awk '/Mem:/{printf "%d", $7/$2*100}')
[ "$mem" -gt 10 ] && flag OK "memory available ${mem}%" || flag FAIL "memory available only ${mem}%"
load=$(awk '{print $1}' /proc/loadavg); cpus=$(nproc)
awk -v l="$load" -v c="$cpus" 'BEGIN{exit !(l < c*2)}' && flag OK "load $load ($cpus cpus)" || flag FAIL "load $load on $cpus cpus"
[ -e /var/run/reboot-required ] && flag WARN "reboot required (pending kernel/security updates)" || flag OK "no reboot pending"

echo "== Containers =="
for c in prod-docker-app-{postgres,redis,fastapi,frontend,nginx,pgadmin} n8n; do
  st=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$c" 2>/dev/null || echo missing)
  case "$st" in healthy|running) flag OK "$c: $st" ;; *) flag FAIL "$c: $st" ;; esac
done

echo "== Certificates =="
for d in $(docker run --rm -v prod-docker-app_certbot_certs:/c:ro alpine ls /c/live 2>/dev/null | grep -v README); do
  end=$(docker run --rm -v prod-docker-app_certbot_certs:/c:ro alpine sh -c "cat /c/live/$d/cert.pem" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
  [ -n "$end" ] || { flag FAIL "$d: unreadable"; continue; }
  days=$(( ($(date -d "$end" +%s) - $(date +%s)) / 86400 ))
  [ "$days" -gt 14 ] && flag OK "$d expires in ${days}d" || flag FAIL "$d expires in ${days}d"
done

echo "== Backups =="
latest=$(find backups -name '*.sql.gz' -mtime -2 2>/dev/null | head -n1)
[ -n "$latest" ] && flag OK "backup < 48h old: $latest" || flag FAIL "no backup newer than 48h in backups/"

echo "== Recent deploys =="
tail -n 3 "$STATE_DIR/history.log" 2>/dev/null || echo "  (none recorded)"

exit "$bad"
