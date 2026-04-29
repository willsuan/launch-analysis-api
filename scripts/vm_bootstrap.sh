#!/usr/bin/env bash
# Bootstrap the launch-analysis-api project on a fresh class VM.
# Pipe-into-bash safe; idempotent on re-run.
#
#   curl -fsSL https://raw.githubusercontent.com/willsuan/launch-analysis-api/main/scripts/vm_bootstrap.sh | bash
#
# or:
#   git clone https://github.com/willsuan/launch-analysis-api.git
#   cd launch-analysis-api
#   bash scripts/vm_bootstrap.sh

set -euo pipefail

REPO_URL="https://github.com/willsuan/launch-analysis-api.git"
REPO_DIR="$HOME/launch-analysis-api"

log()  { printf '\n\033[1;34m[bootstrap]\033[0m %s\n' "$*"; }
warn() { printf '\n\033[1;33m[bootstrap]\033[0m %s\n' "$*"; }

log "apt update + base packages"
sudo apt-get update -qq
sudo apt-get install -y -qq \
    git python3 python3-venv python3-pip \
    curl jq make \
    ca-certificates gnupg lsb-release

if ! command -v docker >/dev/null 2>&1; then
    log "installing docker"
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
        sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
        sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
    sudo apt-get update -qq
    sudo apt-get install -y -qq \
        docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin
    sudo usermod -aG docker "$USER" || true
    warn "added you to the docker group. log out + back in for it to take effect, or use sudo for now."
else
    log "docker already there: $(docker --version)"
fi

if ! command -v kubectl >/dev/null 2>&1; then
    log "installing kubectl"
    KUBECTL_VERSION="$(curl -L -s https://dl.k8s.io/release/stable.txt)"
    curl -fsSLo /tmp/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl"
    sudo install -m 0755 /tmp/kubectl /usr/local/bin/kubectl
    rm /tmp/kubectl
fi

if [[ -d "$REPO_DIR/.git" ]]; then
    log "repo already at $REPO_DIR, pulling"
    git -C "$REPO_DIR" pull --ff-only
else
    log "cloning into $REPO_DIR"
    git clone "$REPO_URL" "$REPO_DIR"
fi
cd "$REPO_DIR"

log "python venv + deps"
if [[ ! -d .venv ]]; then
    python3 -m venv .venv
fi
# shellcheck source=/dev/null
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements.txt fakeredis

log "pytest"
PYTHONPATH=. pytest test/ -q || {
    warn "tests failed, see output above"
    exit 1
}

cat <<EOF

bootstrap done. next steps:

  cd $REPO_DIR

  # One-time. LL2 caps anonymous at 15 req/hr so this takes ~5 hours of
  # wall clock. Runs in tmux with auto-restart and resumes if interrupted.
  bash scripts/auto_ingest.sh
  bash scripts/auto_ingest.sh status
  bash scripts/auto_ingest.sh logs

  # Local stack
  sudo docker compose up -d --build

  curl http://localhost:5000/help
  curl -X POST http://localhost:5000/data
  curl http://localhost:5000/launches | jq length

  curl -X POST http://localhost:5000/jobs \\
    -H 'Content-Type: application/json' \\
    -d '{"plot_type":"frequency_by_provider"}'

  # Cluster (after copying ~/.kube from the bastion)
  bash scripts/k8s_deploy.sh test
EOF
