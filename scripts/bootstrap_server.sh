#!/bin/bash
# One-time setup for a FRESH Ubuntu VPS (22.04/24.04) ONLY. Do NOT run this on a
# server that already hosts other services: it force-enables ufw with a fixed
# rule set and clones into /opt/prod-docker-app. Run as a sudo-capable
# user over SSH:
#   scp scripts/bootstrap_server.sh youruser@your-server-ip:~
#   ssh youruser@your-server-ip
#   chmod +x bootstrap_server.sh && ./bootstrap_server.sh <git-repo-url>
#
# What this does:
#   1. Updates the system, enables unattended security upgrades
#   2. Installs Docker Engine + Compose plugin from Docker's official apt repo
#   3. Adds the current user to the docker group (no sudo needed for docker)
#   4. Configures ufw (firewall): allow SSH/80/443 only, deny everything else
#   5. Installs fail2ban to slow down SSH brute-force attempts
#   6. Clones the project into /opt/prod-docker-app
set -euo pipefail

REPO_URL="${1:?Usage: bootstrap_server.sh <git-repo-url>}"
PROJECT_DIR="/opt/prod-docker-app"

echo "==> Updating system packages"
sudo apt-get update
sudo apt-get upgrade -y

echo "==> Enabling unattended security upgrades"
sudo apt-get install -y unattended-upgrades
sudo dpkg-reconfigure -f noninteractive unattended-upgrades

echo "==> Installing Docker Engine + Compose plugin (official apt repo)"
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "==> Adding $USER to the docker group"
sudo usermod -aG docker "$USER"

echo "==> Configuring firewall (ufw)"
sudo apt-get install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

echo "==> Installing fail2ban"
sudo apt-get install -y fail2ban
sudo systemctl enable --now fail2ban

echo "==> Cloning project into $PROJECT_DIR"
sudo mkdir -p "$PROJECT_DIR"
sudo chown "$USER":"$USER" "$PROJECT_DIR"
git clone "$REPO_URL" "$PROJECT_DIR"

echo
echo "==================================================================="
echo "Bootstrap complete. IMPORTANT — log out and back in (or run"
echo "'newgrp docker') for the docker group membership to take effect."
echo
echo "Next steps (see DEPLOYMENT.md):"
echo "  1. cd $PROJECT_DIR"
echo "  2. cp .env.prod.example .env   (fill in real secrets + DOMAIN_NAME)"
echo "  3. Point your domain's DNS A record at this server's IP"
echo "  4. ./scripts/init_ssl.sh <domain> <email>"
echo "  5. Add SERVER_HOST / SERVER_USER / SERVER_SSH_KEY as GitHub repo"
echo "     secrets so the CD workflow can deploy here automatically"
echo "==================================================================="
