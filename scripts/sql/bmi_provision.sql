-- One-time, idempotent provisioning of the BMI dashboard's database role + schema.
--
-- Run as the database owner (POSTGRES_USER). Everything it creates is NEW:
--   * role   $BMI_DB_USER : LOGIN only - no superuser, no createdb, no createrole,
--                           no replication, no bypassrls, max 10 connections
--   * schema bmi          : owned by that role
-- It never reads, alters or grants anything on schema "public" (items, n8n
-- invoice tables, ...) and never changes privileges of PUBLIC or other roles.
-- Inputs come from the environment (not the command line) via \getenv:
--   BMI_DB_USER, BMI_DB_PASSWORD
\set ON_ERROR_STOP on
\getenv bmi_user BMI_DB_USER
\getenv bmi_password BMI_DB_PASSWORD

SELECT (:'bmi_user' !~ '^[a-z_][a-z0-9_]{0,62}$') AS bad_user,
       (length(:'bmi_password') < 16)              AS weak_password \gset
\if :bad_user
  DO $$ BEGIN RAISE EXCEPTION 'BMI_DB_USER must be a lowercase identifier (a-z, 0-9, _)'; END $$;
\endif
\if :weak_password
  DO $$ BEGIN RAISE EXCEPTION 'BMI_DB_PASSWORD must be at least 16 characters'; END $$;
\endif

-- role (created only if missing; always re-asserted as least-privilege below)
SELECT format('CREATE ROLE %I LOGIN', :'bmi_user')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'bmi_user') \gexec
SELECT format('ALTER ROLE %I WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 10 PASSWORD %L',
              :'bmi_user', :'bmi_password') \gexec

-- schema (created only if missing)
SELECT format('CREATE SCHEMA bmi AUTHORIZATION %I', :'bmi_user')
 WHERE NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'bmi') \gexec

SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'bmi_user') \gexec
SELECT format('ALTER ROLE %I IN DATABASE %I SET search_path = bmi', :'bmi_user', current_database()) \gexec

-- refuse to continue if a pre-existing "bmi" schema belongs to somebody else
SELECT (pg_get_userbyid(nspowner) <> :'bmi_user') AS wrong_owner FROM pg_namespace WHERE nspname = 'bmi' \gset
\if :wrong_owner
  DO $$ BEGIN RAISE EXCEPTION 'schema bmi exists but is owned by a different role'; END $$;
\endif
