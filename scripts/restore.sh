#!/bin/bash
# Restores a Postgres backup created by backup.sh. DESTRUCTIVE: drops and
# recreates all data in the target database — confirms before proceeding.
#
# Usage: ./scripts/restore.sh backups/appdb_20260101_020000.sql.gz
set -euo pipefail

BACKUP_FILE="${1:?Usage: restore.sh <path-to-backup.sql.gz>}"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "Backup file not found: $BACKUP_FILE"
  exit 1
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

set -a
source .env
set +a

echo "This will REPLACE all data in database '$POSTGRES_DB' with the contents of:"
echo "  $BACKUP_FILE"
read -r -p "Type 'yes' to continue: " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "Aborted."
  exit 1
fi

echo "==> Dropping and recreating $POSTGRES_DB"
docker exec prod-docker-app-postgres psql -U "$POSTGRES_USER" -d postgres \
  -c "DROP DATABASE IF EXISTS $POSTGRES_DB;" \
  -c "CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_USER;"

echo "==> Restoring from backup"
gunzip -c "$BACKUP_FILE" | docker exec -i prod-docker-app-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"

echo "==> Restore complete"
