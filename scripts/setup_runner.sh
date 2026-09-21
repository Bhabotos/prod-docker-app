#!/usr/bin/env bash
# Installs the GitHub Actions self-hosted runner ON THIS SERVER as a systemd
# service running as the current (non-root) user.
#
#   1. GitHub -> repo -> Settings -> Actions -> Runners -> New self-hosted runner
#      (or: gh api -X POST repos/OWNER/REPO/actions/runners/registration-token --jq .token)
#      Copy the registration token. It expires after 1 hour and is single-use.
#   2. On the server, as the deploy user:
#        RUNNER_TOKEN=<token> ./scripts/setup_runner.sh
#
# Labels: self-hosted, Linux, X64 (automatic) + hetzner (added here). The
# workflow selects it with:  runs-on: [self-hosted, linux, x64, hetzner]
set -Eeuo pipefail
# Self-contained on purpose (no lib.sh): it must be runnable BEFORE the server
# checkout is updated, e.g. copied out with `git show origin/main:scripts/setup_runner.sh`.
log()  { printf '==> %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

REPO="${RUNNER_REPO:-Bhabotos/prod-docker-app}"
RUNNER_NAME="${RUNNER_NAME:-hetzner-vps}"
RUNNER_DIR="${RUNNER_DIR:-$HOME/actions-runner}"
: "${RUNNER_TOKEN:?Set RUNNER_TOKEN to the registration token (see header)}"

[ "$(id -u)" -ne 0 ] || die "run as the deploy user, NOT root - the runner executes workflow code"
id -nG | tr ' ' '\n' | grep -qx docker || die "$USER must be in the docker group"
[ ! -e "$RUNNER_DIR/.runner" ] || die "a runner is already configured in $RUNNER_DIR"

log "Looking up the latest runner release"
release=$(curl -fsS https://api.github.com/repos/actions/runner/releases/latest)
read -r url digest < <(python3 -c '
import json, sys
r = json.load(sys.stdin)
a = next(x for x in r["assets"] if x["name"].endswith("linux-x64-" + r["tag_name"].lstrip("v") + ".tar.gz"))
print(a["browser_download_url"], a.get("digest", ""))
' <<<"$release")
[ -n "$url" ] || die "could not find a linux-x64 runner asset"

mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"
log "Downloading $url"
curl -fsSL -o runner.tar.gz "$url"

if [ -n "$digest" ]; then
  log "Verifying SHA-256 against the release metadata"
  echo "${digest#sha256:}  runner.tar.gz" | sha256sum -c -
else
  warn "release exposes no digest - verify runner.tar.gz manually before continuing"
  read -r -p "Type 'yes' to continue anyway: " ok
  [ "$ok" = yes ] || die "aborted"
fi

tar xzf runner.tar.gz
rm runner.tar.gz

log "Registering the runner with $REPO"
./config.sh --unattended --url "https://github.com/$REPO" --token "$RUNNER_TOKEN" \
  --name "$RUNNER_NAME" --labels hetzner --work _work

log "Installing and starting the systemd service (needs sudo)"
sudo ./svc.sh install "$USER"
sudo ./svc.sh start
sudo ./svc.sh status | head -n 5
log "Done. It should show as Idle at: https://github.com/$REPO/settings/actions/runners"
