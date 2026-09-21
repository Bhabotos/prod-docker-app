#!/usr/bin/env bash
# Renews EVERY certificate in the certbot volume that is within 30 days of
# expiry (bhabotos.com, n8n.bhabotos.com, the API domain...) and reloads nginx.
# Safe to run daily; certbot does nothing when no cert is due.
#   ./scripts/renew_ssl.sh            real renewal
#   ./scripts/renew_ssl.sh --dry-run  test against Let's Encrypt staging
set -Eeuo pipefail
# shellcheck source=scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$PROJECT_DIR"

# --entrypoint: the certbot service is defined with `entrypoint: "true"`, so
# without this override `run ... certbot renew` silently does nothing.
"${COMPOSE[@]}" run --rm --entrypoint certbot certbot renew "$@"
nginx_reload
