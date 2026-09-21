# Deployment Guide

Target: an **existing** Ubuntu 24.04 Hetzner VPS that already runs other
services (nginx container fronting `bhabotos.com` + `n8n.bhabotos.com`, n8n,
chromadb). Nothing here reinstalls or recreates the server.
> `scripts/bootstrap_server.sh` is for **fresh** servers only. Do not run it here.

## 1. Concepts you need

### What is a self-hosted runner?
GitHub Actions normally runs jobs on machines GitHub owns. A *self-hosted
runner* is a small agent (`actions/runner`) you install on your own machine. It
registers with your repo and executes jobs there, with your machine's files,
network and Docker.

### Why use it here?
The deploy job has to run `docker compose` on the VPS. With a runner **on the
VPS** the job is already local: no SSH key, host or port stored in GitHub, and
no inbound firewall rule. Building/testing stays on GitHub's hosted runners
(the VPS has only 3.7 GB RAM and no swap).

### How does GitHub communicate with it?
The runner makes **outbound HTTPS** long-poll requests to GitHub ("any job for
me?"). GitHub never connects in, so ufw stays at 22/80/443. When a matching job
is queued, the runner downloads it, runs the steps, and streams logs back.

### How does the workflow select it?
By labels: `runs-on: [self-hosted, linux, x64, hetzner]`. A runner is eligible
only if it carries **all** listed labels. `self-hosted`, `Linux`, `X64` are
automatic; `hetzner` is added by `scripts/setup_runner.sh`.

### Security risks (read this)
A runner executes whatever the workflow says, **as the runner's user, on your
production box** (which is in the `docker` group = effectively root).
- **Public repo + PRs from forks** is the classic attack: a malicious PR edits the workflow to `runs-on: self-hosted` and runs code on your server. Mitigations in this repo: the deploy job only runs on `push`/`workflow_dispatch` to `main`; **also** set *Settings -> Actions -> General -> Fork pull request workflows -> "Require approval for all outside collaborators"*, and keep branch protection on `main`.
- The runner runs as `deploy`, **never root**.
- Secrets are never written to disk: the GHCR login uses the job's short-lived `GITHUB_TOKEN` and `docker logout` runs afterwards.
- Anyone who can push to `main` can run code on the VPS - treat write access accordingly.
- Keep the runner updated (it self-updates) and remove it (`./config.sh remove`) if decommissioning.

## 2. Secrets

**GitHub Actions secrets: none to add.** The pipeline uses only the built-in
`GITHUB_TOKEN` (push/pull images in GHCR). The old `SERVER_HOST`,
`SERVER_USER`, `SERVER_SSH_KEY` are **no longer needed** and can be deleted.

**Server-side `/opt/prod-docker-app/.env`** (never committed; must be `chmod 600`):

| Variable | Secret? | Notes |
|---|---|---|
| `POSTGRES_PASSWORD` | yes | `openssl rand -base64 24` |
| `PGADMIN_DEFAULT_PASSWORD` | yes | |
| `POSTGRES_USER`, `POSTGRES_DB`, `PGADMIN_DEFAULT_EMAIL` | no | |
| `API_DOMAIN`, `LETSENCRYPT_EMAIL` | no | `api.bhabotos.com` |
| `FASTAPI_IMAGE`, `FRONTEND_IMAGE` | no | written by `deploy.sh` |
| `APP_*`, `LOG_LEVEL`, `*_PORT`, `NGINX_PORT` | no | see `.env.prod.example` |

`deploy.sh` refuses to run if `.env` is readable by others or still contains `change-me`.

## 3. One-time cutover on the existing server

Every step below changes the live server. Do them in order; each is reversible
or has a stated impact.

| # | Step | Impact |
|---|---|---|
| 0 | DNS: add an **A record `api.bhabotos.com` -> 167.233.248.167** | none |
| 1 | `cd /opt/prod-docker-app && ./scripts/backup.sh` (as `deploy`) | writes `backups/*.sql.gz`; read-only on the DB |
| 2 | `chmod 600 .env` | none (fixes world-readable secrets) |
| 3 | Add to `.env`: `API_DOMAIN=api.bhabotos.com`, `LETSENCRYPT_EMAIL=<you>` | none |
| 4 | Merge the PR to `main`. CI runs and `publish` pushes the images. The `deploy` job **queues** (no runner yet): **cancel that run** in the Actions tab (step 7 does the deploy) | none on server |
| 5 | Install the runner **without touching the working tree**: `cd /opt/prod-docker-app && git fetch origin && git show origin/main:scripts/setup_runner.sh > ~/setup_runner.sh && chmod +x ~/setup_runner.sh && RUNNER_TOKEN=<token> ~/setup_runner.sh` | adds a systemd service (needs sudo); token from repo Settings -> Actions -> Runners -> New runner |
| 6 | `git checkout -- docker-compose.prod.yml && git merge --ff-only origin/main` | drops the local mount edit, which the repo now contains; **do 6 immediately before 7** |
| 7 | Actions -> CI/CD -> **Run workflow** on `main`, tick **converge_all** | recreates nginx (~1-3 s blip on **all three sites**), postgres/redis/pgadmin (DB restart of a few seconds; data is on the `pgdata` volume) - because their log-rotation config changed |
| 8 | `./scripts/init_ssl.sh api.bhabotos.com you@example.com` | new cert; adds `nginx/conf.d/api.bhabotos.com.generated.conf`; reloads nginx |
| 9 | `./scripts/renew_ssl.sh --dry-run`, then `./scripts/install_cron.sh` | schedules backup (02:00), cert renewal (03:17), status (every 15 min) |
| 10 | `./scripts/status.sh` | everything should print `[OK]` |

Why 6 immediately before 7: the running nginx keeps the old file mount until
recreated, but if the box reboots in between, `docker-compose.prod.yml` would
lack the `bhabotos.com` static-site mount until step 7 completes.

The certificates for `bhabotos.com` and `n8n.bhabotos.com` (expire **2026-12-17**)
have **never been renewed automatically** - step 9 fixes that; verify with the dry run first.

## 4. Everyday deploy

Push to `main`. The pipeline tests, builds, publishes `sha-xxxxxxx` images and
the runner executes `deploy.sh`. To deploy by hand on the server (as `deploy`):

```bash
cd /opt/prod-docker-app
FASTAPI_IMAGE=ghcr.io/bhabotos/prod-docker-app-fastapi:sha-abc1234 \
FRONTEND_IMAGE=ghcr.io/bhabotos/prod-docker-app-frontend:sha-abc1234 \
./scripts/deploy.sh            # fastapi + frontend only
./scripts/deploy.sh --all      # whole stack (after changing compose / nginx config)
```

`deploy.sh` order: validate `.env` -> refuse if tracked files are dirty ->
fast-forward git -> **pull images before touching anything** -> `nginx -t` ->
swap `fastapi` + `frontend` -> wait until each runs the *new* image and is
`healthy` -> `nginx -t && reload` -> end-to-end `curl` through nginx -> record
the previous images. Any failure prints `docker compose ps` + logs and rolls back.

## 5. Nginx and HTTPS

- One file per site in `nginx/conf.d/`, mounted as a **directory**. `00-default.conf` answers the health probe and drops requests for unknown hostnames.
- `bhabotos.com.conf` and `n8n.bhabotos.com.conf` are the live configs, captured verbatim.
- `api.<domain>` is generated by `init_ssl.sh` from `nginx/http_only.conf.template` then `nginx/https.conf.template`. Generated files are gitignored.
- To add another domain later: DNS A record, then `./scripts/init_ssl.sh <domain> <email>`.
- Renewal: `renew_ssl.sh` renews **all** certs in the volume that are <30 days from expiry and reloads nginx. (The `certbot` service is defined with `entrypoint: "true"`, so the scripts pass `--entrypoint certbot`; running `docker compose run certbot renew` by hand silently does nothing.)

## 6. Rollback

Automatic: a failed `deploy.sh` restores the previous images and git revision.

Manual, to the last good deploy:
```bash
./scripts/rollback.sh
```
To any earlier build: `./scripts/rollback.sh <fastapi-image> <frontend-image>`
(tags are `sha-<7 chars of the commit>`; list them with `cat .deploy/history.log`
or GitHub -> Packages).

**Limits:** rollback restores code and images, **not data**. The app only ever
adds tables via `create_all()`, so old code runs fine on the current schema, but
if you later add destructive migrations, restore from `backups/` (`restore.sh`,
destructive, asks for confirmation) and back up **before** deploying.

## 7. Monitoring, logs and useful commands

```bash
./scripts/status.sh                       # disk, memory, load, containers, cert expiry, backup age
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f --tail 100 fastapi
docker logs --tail 100 prod-docker-app-nginx
docker stats --no-stream
cat .deploy/history.log                   # deploy/rollback history
tail .deploy/logs/{status,backup,renew}.log
sudo systemctl status 'actions.runner.*'  # runner service
journalctl -u 'actions.runner.*' -n 50 --no-pager
ssh -L 5050:localhost:5050 deploy@167.233.248.167   # pgAdmin via tunnel, then http://localhost:5050
```
Container logs use the `json-file` driver capped at 10 MB x 3 files per container.
`status.sh` exits non-zero when anything is wrong (wire it to your alerting later).

**Backups** run daily at 02:00 to `backups/` (14-day retention). That is on the
same disk as the database; copy `backups/` off the server for real disaster recovery.

## 8. Troubleshooting

| Symptom | Check / fix |
|---|---|
| `deploy.sh`: ".env is mode 664" | `chmod 600 .env` |
| `deploy.sh`: "tracked files have local changes" | `git status`; commit or `git checkout -- <file>`; never edit tracked files on the server |
| `deploy` job stays queued | runner offline: `sudo systemctl status 'actions.runner.*'`; labels must include `hetzner` |
| Deploy rolled back | read the printed `fastapi`/`frontend` logs; `cat .deploy/history.log` |
| `pull access denied` for ghcr.io | the job's `docker login` failed, or the package is not linked to the repo (GitHub -> Packages -> Package settings -> connect repository) |
| nginx container `unhealthy` | it probes `http://127.0.0.1/nginx-health` (from `00-default.conf`); `docker exec prod-docker-app-nginx nginx -t` |
| nginx won't start after a config change | an `ssl_certificate` file is missing, or `n8n` container is absent (literal upstream); `nginx -t` shows which |
| 502 for a moment during deploy | expected: one container swap; persistent 502 = `fastapi` unhealthy, see logs |
| certbot: challenge failed | DNS not pointing here yet (`dig +short api.bhabotos.com`) or port 80 blocked (`sudo ufw status`) |
| `/api/docs` shows no schema | the API must run with `--root-path /api` (set in `app/Dockerfile`) |
| Docker ports bypass ufw | published ports are opened by Docker directly; only nginx publishes 80/443 and pgAdmin is `127.0.0.1` only |

## 9. Server hygiene items found in the audit (not done by this repo)

- 29 pending package updates and a **reboot required** (kernel). Schedule a maintenance window; everything restarts (`restart: always`).
- SSH allows **root login and passwords** with ~8,000 failed attempts logged (fail2ban is active). Recommended: key-only, `PermitRootLogin no`, after confirming `deploy` key login works, keeping a second session open. Left untouched by decision.
- No swap on a 3.7 GB box that runs n8n, chroma, postgres and the app. Consider a 2 GB swap file.
- `n8n:latest` / `chroma:latest` are unpinned.
