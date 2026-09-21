# Architecture

## The three tiers

| Tier | Container | Tech | Reachable from |
|---|---|---|---|
| Frontend | `prod-docker-app-frontend` | static HTML/JS on unprivileged nginx (`frontend/`) | nginx only |
| Backend / API | `prod-docker-app-fastapi` | FastAPI, SQLAlchemy (`app/`) | nginx only |
| Database | `prod-docker-app-postgres` (+ `redis` cache) | PostgreSQL 16, Redis 7 | fastapi only |

In front of them sits **nginx** (`prod-docker-app-nginx`), the only container
that publishes ports (80/443). `pgadmin` is an admin tool bound to
`127.0.0.1:5050` (SSH tunnel access only).

```
Internet
   |  :80 (redirect) / :443
   v
+------------------------- Hetzner VPS (ufw: 22, 80, 443) --------------------------+
|  nginx  (conf.d/: one file per site)                                              |
|    bhabotos.com       -> static site   (/opt/bhabotos-site/current)  [pre-existing] |
|    n8n.bhabotos.com   -> n8n container                              [pre-existing] |
|    api.bhabotos.com   -> /      frontend:8080                                      |
|                          /api/  fastapi:8000  (prefix stripped)                    |
|                                    |                                               |
|                                    v                                               |
|                          postgres:5432 (volume pgdata)     redis:6379              |
|  all on the internal Docker network  prod-docker-app_backend  (no published ports) |
+-----------------------------------------------------------------------------------+
```

The server is shared: nginx also fronts `bhabotos.com` and `n8n.bhabotos.com`,
and `n8n` (a separate compose project) and `chromadb` run alongside. That is why
deploys never restart nginx or the database unless you ask (`--all`).

## Request flow

1. Browser requests `https://api.bhabotos.com/` -> nginx serves the UI from the `frontend` container.
2. The UI calls `/api/items` (same origin: no CORS, no hard-coded host).
3. nginx rewrites `/api/items` -> `/items` and proxies to `fastapi:8000`.
4. FastAPI reads Redis first (`X-Cache: HIT/MISS`), falls back to Postgres, and invalidates the cache key on update/delete.

Upstreams are resolved by Docker DNS **per request** (`resolver 127.0.0.11` +
variable `proxy_pass`, see `nginx/snippets/app_locations.conf`). Recreating
`fastapi` during a deploy therefore never leaves nginx pointing at a dead IP.

## CI/CD flow

```
git push
   |
GitHub ---- Actions (ubuntu-latest) ----------------------------------------------
   |   1 test            pytest, shellcheck, compose config validation
   |   2 docker-validate build both images, start the full stack, curl smoke test
   |   3 publish         push  ghcr.io/<owner>/prod-docker-app-{fastapi,frontend}:sha-<7>
   |
   +--- 4 deploy  runs-on: [self-hosted, linux, x64, hetzner] ----------------------
             |   (main only; waits for approval on the `production` environment,
             |    then goes to the runner that long-polls GitHub)
             v
   Hetzner VPS: runner service, user "deploy"
             |   docker login (job token) -> ./scripts/deploy.sh
             v
   validate .env -> git ff -> pull images -> swap fastapi+frontend -> health gate
        -> nginx -t && reload -> end-to-end check -> record previous
        \-> on ANY failure: print logs, restore previous images + git rev
```

Nothing is built on the server: the exact image that passed CI is the one deployed.

## Design decisions

| Decision | Why |
|---|---|
| Immutable `sha-xxxxxxx` image tags | rollback = redeploy an older tag; `:latest` is never deployed |
| Deploy touches only `fastapi` + `frontend` | postgres/redis/nginx/n8n keep running; API interruption is one container swap (~1s of 502s measured locally) |
| Directory mount `nginx/conf.d/` | a git pull replaces files (new inode); a single-file bind mount would go stale |
| One generated file per new domain (`*.generated.conf`) | adding `api.bhabotos.com` never edits the live `bhabotos.com` / `n8n` server blocks |
| Two-phase HTTPS bootstrap | nginx refuses to load a `ssl_certificate` that doesn't exist yet - and a failed nginx would take every site down |
| Self-hosted runner instead of SSH deploy | no SSH private key or host stored in GitHub; the runner dials OUT to GitHub, no inbound port needed |
| Log rotation (10 MB x 3) on every container **except postgres** | logs can't fill the 38 GB disk; postgres is excluded so its definition is unchanged and the shared DB is never restarted by a deploy (see DEPLOYMENT.md) |

## Known limitations

- **Single server, single API replica**: a deploy has a ~1s window of 502s; true zero-downtime needs two API replicas (blue/green).
- **Rollback covers code, not data**: database changes are not reverted (see DEPLOYMENT.md).
- `nginx/conf.d/n8n.bhabotos.com.conf` resolves `n8n` at nginx startup; if the n8n container is missing when nginx restarts, nginx fails to boot for all sites.
- The API's tables are created with `create_all()` at startup; there are no migrations yet.
