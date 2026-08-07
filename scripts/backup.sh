#!/bin/bash
# Dumps the Postgres database to a timestamped, gzipped SQL file and prunes
# backups older than RETENTION_DAYS. Intended to run daily via cron:
#   0 2 * * * cd /opt/prod-docker-app && ./scripts/backup.sh >> /var/log/db_backup.log 2>&1
#
# NOTE: this writes backups to a local directory on the server. For real
# durability, also sync backups/ to off-server storage (e.g. S3, another
# host) — that step needs your own cloud credentials, so it isn't automated
# here. See DEPLOYMENT.md.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

BACKUP_DIR="$PROJECT_DIR/backups"
RETENTION_DAYS=14
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

set -a
source .env
set +a

mkdir -p "$BACKUP_DIR"

OUT_FILE="$BACKUP_DIR/${POSTGRES_DB}_${TIMESTAMP}.sql.gz"

echo "==> Dumping $POSTGRES_DB to $OUT_FILE"
docker exec prod-docker-app-postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$OUT_FILE"

echo "==> Backup size: $(du -h "$OUT_FILE" | cut -f1)"

echo "==> Pruning backups older than $RETENTION_DAYS days"
find "$BACKUP_DIR" -name "${POSTGRES_DB}_*.sql.gz" -mtime "+$RETENTION_DAYS" -print -delete

echo "==> Done"
