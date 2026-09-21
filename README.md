# Production-Ready Dockerized Web Application

A single-server 3-tier web app (static frontend, FastAPI backend, PostgreSQL + Redis) — containerized, health-checked, and deployed by GitHub Actions through a self-hosted runner on a Hetzner VPS. Built to demonstrate real-world Docker and DevOps practices: multi-stage builds, network-segmented services, zero-downtime-oriented health-gated startup, and push-to-deploy automation.

[![CI/CD](https://github.com/Bhabotos/prod-docker-app/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/Bhabotos/prod-docker-app/actions/workflows/ci-cd.yml)

**Live:** `https://api.bhabotos.com/` (after the cutover in [DEPLOYMENT.md](DEPLOYMENT.md))

## Tech Stack

| Tier / concern | Technology |
|---|---|
| Frontend | Static HTML/JS on unprivileged nginx |
| Backend / API | FastAPI, SQLAlchemy (Python 3.12) |
| Database | PostgreSQL 16 (+ Redis 7 cache) |
| Reverse proxy | Nginx (TLS via Let's Encrypt) |
| Containers | Docker, multi-stage builds, Compose |
| CI/CD | GitHub Actions -> GHCR -> **self-hosted runner** on the VPS |
| Hosting | Hetzner Cloud VPS (Ubuntu 24.04) |

## Architecture

```
Developer -> git push -> GitHub -> Actions (test, build, docker validate, publish to GHCR)
                                        |
                          Self-hosted runner [self-hosted, linux, x64, hetzner]
                                        |
                          Hetzner VPS -> scripts/deploy.sh -> Docker Compose
                                        |
   Internet -> Nginx :80/:443 -+-> frontend (/)
                               +-> fastapi  (/api) -> postgres + redis
```

Full diagrams and design decisions: **[ARCHITECTURE.md](ARCHITECTURE.md)**.
Runbook (runner, cutover, HTTPS, secrets, rollback, troubleshooting): **[DEPLOYMENT.md](DEPLOYMENT.md)**.

## BMI & Health Dashboard

A single-user wellness dashboard on top of the same stack (frontend at `/`, API under `/api`).
Profile (age, sex, height, activity), weight history, BMI / BMR / daily-calorie estimates, a target-weight goal
with progress %, weight and BMI charts and monthly progress. **General wellness information only, not medical advice.**

| Area | Endpoints (all need a login except `POST /auth/login`, `POST /auth/logout`) |
|---|---|
| Auth | `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me` |
| Profile | `GET/POST/PUT /api/profile` |
| Metrics | `GET /api/health/summary`, `GET /api/health/history`, `GET /api/health/monthly`, `GET /api/health/limits` |
| Weight | `POST /api/health/weight` (one entry per day; same date updates), `DELETE /api/health/weight/{id}` |
| Goals | `GET/POST/PUT /api/goals` |

- Calculations live in `app/bmi_dashboard/services/` (pure functions, unit-tested); the browser only displays results.
- Data is in its **own PostgreSQL schema `bmi`**, owned by a separate least-privilege role that cannot read any other table.
- Migrations (Alembic, additive only) run at API start. If the feature is not configured the API starts normally and the BMI routes answer 503.
- Setup and rollout: see [DEPLOYMENT.md](DEPLOYMENT.md#bmi--health-dashboard-rollout).

## Highlights

- **Real Test stage**: pytest (SQLite + fake Redis), shellcheck, compose validation, then a full-stack smoke test through nginx.
- **Immutable images**: every deploy is `sha-<commit>`; nothing is built on the server.
- **Safe deploys**: only `fastapi` + `frontend` are swapped; new images are pulled first; health-gated; automatic rollback with logs on failure.
- **Nginx follows container restarts**: per-request Docker DNS resolution, so redeploying the API never leaves nginx on a stale IP.
- **Least exposure**: only nginx publishes 80/443; DB/Redis/API/frontend have no host ports; pgAdmin is loopback-only; containers run non-root.
- **No deploy secrets in GitHub**: the runner dials out to GitHub; only the built-in `GITHUB_TOKEN` is used.
- **Ops included**: log rotation, `status.sh` monitoring, daily backups, automated certificate renewal.

## Project Structure

```
app/                 FastAPI service (multi-stage Dockerfile) + tests/
  bmi_dashboard/     BMI dashboard: routers, schemas, services (calculations), security
  db_migrations/     Alembic migrations (schema `bmi` only)
frontend/            static UI: dashboard (index.html, js/, dashboard.css) + original items demo (items.html); own Dockerfile + nginx.conf
nginx/               dev.conf, snippets/, conf.d/ (per-site prod config), HTTPS templates
scripts/             deploy, rollback, init_ssl, renew_ssl, setup_runner, status, install_cron, backup, restore
docker-compose.yml       base stack (local dev / CI)
docker-compose.prod.yml  production overrides
.github/workflows/ci-cd.yml
```

## Local development

```bash
cp .env.example .env
# BMI dashboard (optional): create the DB role, then set a password + session secret
docker compose up -d --build postgres redis
docker compose --profile tools run --rm bmi-provision
(cd app && python -m bmi_dashboard.cli hash-password)   # paste both printed lines into .env
docker compose up -d --build
open http://localhost/          # UI       (nginx on :80)
curl http://localhost/api/health
open http://localhost/api/docs  # Swagger UI
```

Run the tests without Docker:

```bash
cd app && pip install -r requirements-dev.txt && pytest -q            # unit + API tests
TEST_PG_ADMIN_URL=postgresql+psycopg://postgres:pw@localhost:5432/postgres pytest -q   # + real-PostgreSQL migration tests (needs psql)
cd ../frontend && npm test                                             # chart math, formatting, API client (no dependencies)
```

## Environment variables

See [`.env.example`](.env.example) (dev/CI) and [`.env.prod.example`](.env.prod.example) (server). Real `.env` files are never committed.
