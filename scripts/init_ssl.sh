#!/bin/bash
# ONE-TIME SSL bootstrap. Run this after DNS for <domain> points at this
# server's IP, and after `docker compose ... up -d` has run at least once
# (so the postgres/redis/fastapi/pgadmin containers already exist).
#
# Two-phase bootstrap, because nginx can't start with SSL config pointing
# at certificate files that don't exist yet:
#   Phase 1: start nginx in HTTP-only mode (serves the ACME challenge)
#   Phase 2: request the cert, then switch nginx to full HTTPS config
#
# Usage: ./scripts/init_ssl.sh yourdomain.com you@example.com
set -euo pipefail

DOMAIN="${1:?Usage: init_ssl.sh <domain> <email>}"
EMAIL="${2:?Usage: init_ssl.sh <domain> <email>}"
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

echo "==> Phase 1: rendering HTTP-only nginx config for $DOMAIN"
sed "s/__DOMAIN_NAME__/$DOMAIN/g" nginx/http_only.conf.template > nginx/nginx.prod.conf

echo "==> Starting nginx (HTTP-only, to serve the ACME challenge)"
$COMPOSE up -d nginx

echo "==> Requesting certificate from Let's Encrypt"
$COMPOSE run --rm certbot certonly \
  --webroot --webroot-path=/var/www/certbot \
  -d "$DOMAIN" \
  --email "$EMAIL" \
  --agree-tos \
  --no-eff-email

echo "==> Phase 2: rendering full HTTPS nginx config for $DOMAIN"
sed "s/__DOMAIN_NAME__/$DOMAIN/g" nginx/https.conf.template > nginx/nginx.prod.conf

echo "==> Reloading nginx with HTTPS enabled"
$COMPOSE up -d nginx
$COMPOSE exec nginx nginx -s reload

echo
echo "Done. https://$DOMAIN should now be serving over TLS."
echo "Set up automatic renewal: crontab -e, add:"
echo "  0 3 * * * cd $(pwd) && ./scripts/renew_ssl.sh >> /var/log/ssl_renew.log 2>&1"
