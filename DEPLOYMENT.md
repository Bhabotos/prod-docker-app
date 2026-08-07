# Deployment Guide

This project deploys as: GitHub Actions builds the FastAPI image and pushes
it to GitHub Container Registry (GHCR) on every push to `main`, then (once
configured) SSHes into your VPS and runs `scripts/deploy.sh`, which pulls
the new image and restarts the stack. Postgres, Redis, and Nginx run from
their official images directly — only the FastAPI image is built and
versioned by CI.

Until the server secrets below are added, CI still builds and pushes the
image on every push — deployment is just a no-op until you're ready.

## 1. Get a VPS

Any Ubuntu 22.04/24.04 server works (DigitalOcean Droplet, AWS EC2, Linode,
Hetzner, etc). You need:
- Its public IP address
- Root or sudo SSH access
- A domain name whose DNS A record you can point at that IP (required for
  Let's Encrypt — it validates ownership by reaching your server on port 80)

## 2. Bootstrap the server

From your local machine:

```bash
scp scripts/bootstrap_server.sh youruser@YOUR_SERVER_IP:~
ssh youruser@YOUR_SERVER_IP
chmod +x bootstrap_server.sh
./bootstrap_server.sh https://github.com/Bhabotos/prod-docker-app.git
```

This installs Docker, configures `ufw` (allows only SSH/80/443), installs
`fail2ban`, and clones the repo into `/opt/prod-docker-app`. Log out and
back in afterward so your docker group membership takes effect.

## 3. Configure environment variables

On the server:

```bash
cd /opt/prod-docker-app
cp .env.prod.example .env
nano .env   # fill in real passwords (openssl rand -base64 24), DOMAIN_NAME, LETSENCRYPT_EMAIL
```

`.env` lives only on the server and is never committed to git.

## 4. Point DNS at the server

Create an A record for your domain pointing at the server's IP. Wait for
it to propagate (`dig yourdomain.com` should return the server IP) before
continuing — Let's Encrypt needs to be able to reach the server at that
domain on port 80.

## 5. First deploy (build locally on the server, no CD yet)

```bash
cd /opt/prod-docker-app
export FASTAPI_IMAGE=prod-docker-app-fastapi:bootstrap
docker compose -f docker-compose.yml -f docker-compose.prod.yml build fastapi
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d postgres redis fastapi pgadmin
```

(Nginx isn't started yet — `init_ssl.sh` starts it as part of the SSL
bootstrap below.)

## 6. Get an SSL certificate

```bash
./scripts/init_ssl.sh yourdomain.com you@example.com
```

This starts nginx in HTTP-only mode, requests a cert from Let's Encrypt via
the ACME HTTP-01 challenge, then switches nginx to full HTTPS. Your site
should now be live at `https://yourdomain.com`.

Set up auto-renewal (Let's Encrypt certs expire every 90 days):

```bash
crontab -e
# add:
0 3 * * * cd /opt/prod-docker-app && ./scripts/renew_ssl.sh >> /var/log/ssl_renew.log 2>&1
```

## 7. Set up automatic deployment (CD)

By default, GHCR packages built from Actions are created **private**. After
your first CD run pushes an image, go to your GitHub profile → Packages →
`prod-docker-app-fastapi` → Package settings → change visibility to
**Public** (simplest option — the image contains no secrets, only app
code). Otherwise the server will need its own GHCR login, which means
managing another credential.

Generate a deploy-only SSH key pair (don't reuse your personal key):

```bash
ssh-keygen -t ed25519 -f ~/.ssh/prod_docker_app_deploy -N ""
ssh-copy-id -i ~/.ssh/prod_docker_app_deploy.pub youruser@YOUR_SERVER_IP
```

In your GitHub repo → Settings → Secrets and variables → Actions, add:

| Secret | Value |
|---|---|
| `SERVER_HOST` | Your server's IP or hostname |
| `SERVER_USER` | The SSH user (e.g. `youruser`) |
| `SERVER_SSH_KEY` | Contents of `~/.ssh/prod_docker_app_deploy` (the **private** key) |

From then on, every push to `main` that passes CI will automatically build,
push, and deploy — SSH in and run `git log` on the server, or just watch
`gh run list`, to confirm.

## 8. Backups

```bash
crontab -e
# add:
0 2 * * * cd /opt/prod-docker-app && ./scripts/backup.sh >> /var/log/db_backup.log 2>&1
```

Backs up Postgres daily to `backups/`, gzipped, pruned after 14 days. To
restore: `./scripts/restore.sh backups/appdb_20260101_020000.sql.gz`
(destructive — asks for confirmation).

**This only protects against database-level mistakes on this one server.**
For real disaster recovery (server destroyed, disk failure), also sync
`backups/` to off-server storage — S3, another host, whatever you use. That
step needs your own cloud credentials, so it's intentionally not automated
here.

## A note on `ufw` and Docker

Docker manipulates `iptables` directly and, by default, **published
container ports bypass `ufw` rules entirely** — a very common gotcha. This
project avoids it two ways: Postgres, Redis, and FastAPI publish no host
port at all (only reachable over the internal Docker network), and pgAdmin
binds to `127.0.0.1:5050` specifically (not `0.0.0.0`), so it's reachable
only from the server itself. To access pgAdmin remotely, use an SSH tunnel:

```bash
ssh -L 5050:localhost:5050 youruser@YOUR_SERVER_IP
# then open http://localhost:5050 on your own machine
```

## Rolling back

```bash
cd /opt/prod-docker-app
FASTAPI_IMAGE=ghcr.io/OWNER/prod-docker-app-fastapi:sha-<previous-good-sha> ./scripts/deploy.sh
```

Find previous tags under your GitHub repo → Packages, or `git log` to find
the commit whose short SHA matches a known-good `sha-xxxxxxx` image tag.

## Troubleshooting

- **`docker compose ps` shows a service unhealthy**: `docker compose logs <service>`
- **Deploy step fails on "Permission denied (publickey)"**: the public key
  wasn't added to the server user's `~/.ssh/authorized_keys`, or
  `SERVER_SSH_KEY` secret doesn't match the private key
- **Certbot fails the HTTP-01 challenge**: DNS hasn't propagated yet, or
  port 80 isn't reachable (check `ufw status`, check the domain resolves
  to this server with `dig yourdomain.com`)
