#!/usr/bin/env bash
# ONE-TIME HTTPS bootstrap for a NEW domain (e.g. api.bhabotos.com). Safe to
# run on a server whose nginx already serves other sites: it only adds
# nginx/conf.d/<domain>.generated.conf and never edits the other site files.
#
#   ./scripts/init_ssl.sh api.bhabotos.com you@example.com
#
# Two phases (nginx can't load a server block whose cert files don't exist yet):
#   1. HTTP-only config that serves the ACME challenge
#   2. request the cert, then swap in the HTTPS config
# If the HTTPS config fails nginx -t, the HTTP-only config is restored.
set -Eeuo pipefail
# shellcheck source=scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$PROJECT_DIR"

DOMAIN="${1:?Usage: init_ssl.sh <domain> <email>}"
EMAIL="${2:?Usage: init_ssl.sh <domain> <email>}"
[[ "$DOMAIN" =~ ^[A-Za-z0-9.-]+$ ]] || die "invalid domain: $DOMAIN"
CONF="nginx/conf.d/${DOMAIN}.generated.conf"

log "Checking DNS for $DOMAIN"
resolved=$(getent ahostsv4 "$DOMAIN" | awk 'NR==1{print $1}') || true
public_ip=$(curl -4 -fsS --max-time 5 https://ifconfig.me || true)
[ -n "$resolved" ] || die "$DOMAIN does not resolve yet - add the DNS A record first"
[ -z "$public_ip" ] || [ "$resolved" = "$public_ip" ] \
  || die "$DOMAIN resolves to $resolved but this server is $public_ip"

sed "s/__DOMAIN_NAME__/$DOMAIN/g" nginx/http_only.conf.template > "$CONF"
log "Phase 1: HTTP-only config written to $CONF"
nginx_reload

log "Requesting certificate from Let's Encrypt"
# --entrypoint is required: the certbot service in docker-compose.prod.yml has
# `entrypoint: "true"` so it never runs on `up`.
"${COMPOSE[@]}" run --rm --entrypoint certbot certbot certonly \
  --webroot --webroot-path=/var/www/certbot \
  -d "$DOMAIN" --email "$EMAIL" --agree-tos --no-eff-email --keep-until-expiring

log "Phase 2: switching to HTTPS config"
cp "$CONF" "$CONF.http-only"
sed "s/__DOMAIN_NAME__/$DOMAIN/g" nginx/https.conf.template > "$CONF"
if ! nginx_reload; then
  warn "HTTPS config rejected - restoring HTTP-only config"
  mv "$CONF.http-only" "$CONF"
  nginx_reload
  exit 1
fi
rm -f "$CONF.http-only"

log "Done: https://$DOMAIN"
echo "Make sure API_DOMAIN=$DOMAIN is set in .env, and that renewal is scheduled (scripts/install_cron.sh)."
