#!/bin/bash
# Renews the Let's Encrypt certificate if it's due, and reloads nginx so it
# picks up the renewed cert. Let's Encrypt certs are valid 90 days; certbot
# only actually renews when within 30 days of expiry, so this is safe to
# run daily via cron (see crontab line printed by scripts/init_ssl.sh).
set -euo pipefail

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

$COMPOSE run --rm certbot renew
$COMPOSE exec nginx nginx -s reload
