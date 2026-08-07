#!/bin/bash
# Deploys the current code + a given FastAPI image tag on THIS server.
# Run from the project root (/opt/prod-docker-app) — used both by the
# GitHub Actions CD workflow (over SSH) and for manual deploys.
#
# Usage: FASTAPI_IMAGE=ghcr.io/owner/prod-docker-app-fastapi:sha-abc123 ./scripts/deploy.sh
set -euo pipefail

: "${FASTAPI_IMAGE:?Set FASTAPI_IMAGE, e.g. ghcr.io/OWNER/prod-docker-app-fastapi:latest}"

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

echo "==> Pulling latest code"
git pull --ff-only

echo "==> Deploying image: $FASTAPI_IMAGE"
export FASTAPI_IMAGE

echo "==> Pulling images"
$COMPOSE pull fastapi nginx postgres redis pgadmin

echo "==> Starting/updating stack"
$COMPOSE up -d --remove-orphans

echo "==> Waiting for fastapi to report healthy"
for i in $(seq 1 30); do
  status=$(docker inspect -f '{{.State.Health.Status}}' prod-docker-app-fastapi 2>/dev/null || echo "starting")
  if [ "$status" = "healthy" ]; then
    echo "fastapi is healthy"
    break
  fi
  if [ "$i" = "30" ]; then
    echo "fastapi did not become healthy in time — check: docker compose logs fastapi"
    exit 1
  fi
  sleep 5
done

echo "==> Cleaning up old images"
docker image prune -f

echo "==> Deploy complete"
