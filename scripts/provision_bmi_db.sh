#!/usr/bin/env bash
# Creates the least-privilege PostgreSQL role + `bmi` schema for the BMI dashboard
# on the running production database. ONE-TIME, idempotent, additive.
#
#   ./scripts/provision_bmi_db.sh            dry run: show state + the exact SQL, change nothing
#   ./scripts/provision_bmi_db.sh --apply    ask for confirmation, then apply and verify
#
# Needs in .env:  BMI_DB_USER, BMI_DB_PASSWORD (16+ chars; `openssl rand -hex 24` is fine).
# It runs `psql` INSIDE the existing postgres container. The container is not
# restarted or recreated, and nothing in schema "public" is touched.
# Take a backup first:  ./scripts/backup.sh
set -Eeuo pipefail
# shellcheck source=scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$PROJECT_DIR"

APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1
PG=prod-docker-app-postgres
SQL=scripts/sql/bmi_provision.sql

[ -f .env ] || die ".env missing"
perm=$(stat -c '%a' .env)
[ "${perm: -2}" = "00" ] || die ".env is mode $perm - run: chmod 600 .env"
BMI_DB_USER=$(env_get BMI_DB_USER || true)
BMI_DB_PASSWORD=$(env_get BMI_DB_PASSWORD || true)
PGUSER_=$(env_get POSTGRES_USER)
PGDB_=$(env_get POSTGRES_DB)
[ -n "$BMI_DB_USER" ] || die "BMI_DB_USER is not set in .env"
[ "${#BMI_DB_PASSWORD}" -ge 16 ] || die "BMI_DB_PASSWORD must be set in .env and be at least 16 characters"
[ "$(docker inspect -f '{{.State.Health.Status}}' "$PG" 2>/dev/null)" = healthy ] || die "$PG is not healthy"
export BMI_DB_USER BMI_DB_PASSWORD

psql_admin() { docker exec -i -e BMI_DB_USER -e BMI_DB_PASSWORD "$PG" psql -U "$PGUSER_" -d "$PGDB_" -v ON_ERROR_STOP=1 "$@"; }

log "Current state (read-only)"
psql_admin -tA -v u="$BMI_DB_USER" <<'SQL'
SELECT 'role exists:   ' || EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'u');
SELECT 'schema exists: ' || EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'bmi');
SELECT 'public tables (will NOT be touched): ' || count(*) FROM pg_tables WHERE schemaname = 'public';
SQL

if [ "$APPLY" -ne 1 ]; then
  log "DRY RUN - would execute $SQL (contains no secrets; values come from the environment):"
  sed 's/^/    /' "$SQL"
  log "Nothing was changed. Re-run with --apply to provision."
  exit 0
fi

read -r -p "Create role '$BMI_DB_USER' and schema 'bmi' in database '$PGDB_'? Type 'yes': " ok
[ "$ok" = yes ] || die "aborted"

log "Applying"
psql_admin -q < "$SQL"

log "Verifying least privilege"
psql_admin -tA -v u="$BMI_DB_USER" <<'SQL'
SELECT 'attributes:    super=' || rolsuper || ' createdb=' || rolcreatedb || ' createrole=' || rolcreaterole
       || ' replication=' || rolreplication || ' bypassrls=' || rolbypassrls || ' connlimit=' || rolconnlimit
  FROM pg_roles WHERE rolname = :'u';
SELECT 'schema owner:  ' || pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname = 'bmi';
SELECT 'can CREATE in public: ' || has_schema_privilege(:'u', 'public', 'CREATE');
SELECT 'public objects the role can read/write: ' || count(*)
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relkind IN ('r','v','m','p','f')
   AND (has_table_privilege(:'u', c.oid, 'SELECT') OR has_table_privilege(:'u', c.oid, 'INSERT')
        OR has_table_privilege(:'u', c.oid, 'UPDATE') OR has_table_privilege(:'u', c.oid, 'DELETE'));
SQL
log "Done. Next: set DASHBOARD_PASSWORD_HASH and SESSION_SECRET in .env, then deploy."
