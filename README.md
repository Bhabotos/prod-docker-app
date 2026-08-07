# Production-Ready Dockerized Web Application

A production FastAPI service — containerized, health-checked, and deployed via a fully automated CI/CD pipeline to a live VPS. Built to demonstrate real-world Docker and DevOps practices: multi-stage builds, network-segmented services, zero-downtime-oriented health-gated startup, and push-to-deploy automation.

[![CI](https://github.com/Bhabotos/prod-docker-app/actions/workflows/ci.yml/badge.svg)](https://github.com/Bhabotos/prod-docker-app/actions/workflows/ci.yml)
[![CD](https://github.com/Bhabotos/prod-docker-app/actions/workflows/cd.yml/badge.svg)](https://github.com/Bhabotos/prod-docker-app/actions/workflows/cd.yml)

**Live:** `http://167.233.248.167/` (HTTPS pending a domain — see [Roadmap](#roadmap))

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI (Python), SQLAlchemy |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Reverse proxy | Nginx |
| Admin UI | pgAdmin (loopback-only) |
| Containerization | Docker, multi-stage builds |
| Orchestration | Docker Compose |
| CI/CD | GitHub Actions → GitHub Container Registry → SSH deploy |
| Hosting | Hetzner Cloud VPS (Ubuntu 24.04) |

## Architecture

End-to-end path from a code change to it running in production:

```
Developer
    │
    ▼
Git Push
    │
    ▼
GitHub Repository
    │
    ▼
GitHub Actions (CI/CD)
    │
    ▼
Build Docker Image
    │
    ▼
GitHub Container Registry (GHCR)
    │
    ▼
Hetzner Cloud VPS
    │
    ▼
Docker Compose
    │
    ├── Nginx
    ├── FastAPI
    ├── PostgreSQL
    └── Redis
```

A push to `main` triggers **CI** (builds the image, spins up the full stack, runs a live smoke test against every endpoint) and then **CD**: the FastAPI image is built once, pushed to GHCR, and an SSH step on the deploy server pulls that exact image and restarts the stack via Docker Compose — the same artifact that passed CI is what runs in production, nothing is rebuilt on the server itself. Deployment only proceeds if CI passed first, and only touches the `fastapi` service — Postgres, Redis, and Nginx are pulled from their pinned upstream tags, not rebuilt on every deploy.

## Request Flow

How a single HTTP request is actually handled once it reaches the server:

```
Internet
    │
    ▼
Nginx
    │
    ▼
FastAPI
   ├── PostgreSQL
   └── Redis
```

Nginx is the **only** service exposed to the public internet (ports 80/443); it reverse-proxies everything to FastAPI over the internal Docker network. FastAPI reads/writes through SQLAlchemy to PostgreSQL for persistent data, and checks Redis first on cache-eligible reads (returning `X-Cache: HIT`/`MISS` so cache behavior is directly observable) — writes invalidate the relevant cache key so stale data is never served. PostgreSQL and Redis publish no ports to the host at all; they're reachable only from other containers on the same Docker network, never directly from outside.

## Key Engineering Highlights

- **Multi-stage Docker build** — build tools (gcc, pip cache) never ship in the final image; the production FastAPI image is ~55MB.
- **Non-root containers** — the FastAPI process runs as an unprivileged `appuser`, not root.
- **Health-gated startup** — `depends_on: condition: service_healthy` means FastAPI genuinely waits for Postgres/Redis to be ready, and Nginx waits for FastAPI, on every restart — not a fixed sleep.
- **Defense-in-depth network topology** — only Nginx is publicly reachable; pgAdmin is bound to `127.0.0.1` only (accessible via SSH tunnel); Postgres/Redis/FastAPI have no published ports at all.
- **CI runs a real integration test**, not just a build check — it stands up the full Compose stack in GitHub Actions and exercises the live HTTP API before anything is allowed to merge.
- **Data persistence verified, not assumed** — named volumes were proven to survive full container teardown/recreation, both locally and on the production server.
- **Automated backups** — daily `pg_dump`, 14-day retention, with a companion restore script.
- **Structured for growth without rework** — Nginx and Docker Compose are already laid out so HTTPS/Let's Encrypt can be added later with zero rebuilding of the running stack.

## Project Structure

```
prod-docker-app/
├── app/                    FastAPI application (multi-stage Dockerfile)
├── nginx/                  Reverse proxy config (dev + prod templates)
├── scripts/                Server bootstrap, deploy, backup/restore, SSL bootstrap
├── docker-compose.yml       Base stack (local development)
├── docker-compose.prod.yml  Production overrides (registry image, SSL-ready)
├── .github/workflows/       CI (build + smoke test) and CD (build, push, deploy)
└── DEPLOYMENT.md            Full production deployment runbook
```

## Getting Started (local development)

```bash
git clone https://github.com/Bhabotos/prod-docker-app.git
cd prod-docker-app
cp .env.example .env
docker compose up -d --build
curl http://localhost/health
```

API docs (Swagger UI) are available at `http://localhost/docs` once the stack is running.

## Production Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full runbook — server bootstrap, environment setup, first deploy, GitHub Actions secrets, backups, and the SSL activation steps.

## Roadmap

- [ ] Point a domain at the server and run `scripts/init_ssl.sh` to enable HTTPS
- [ ] Security hardening pass (dependency/image scanning, secret rotation policy)

## Status

Deployed and live on a Hetzner Cloud VPS, with CI/CD verified working end-to-end on every push to `main`.
