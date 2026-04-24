#!/usr/bin/env bash
# vm_bootstrap.sh
# Run this ON your class VM (as user `ubuntu`) to set up the Artemis Launch API.
#
# Usage (on the VM, after SSHing via bastion):
#   curl -fsSL https://raw.githubusercontent.com/willsuan/launch-analysis-api/main/scripts/vm_bootstrap.sh | bash
#
# Or clone first, then run:
#   git clone https://github.com/willsuan/launch-analysis-api.git
#   cd launch-analysis-api
#   bash scripts/vm_bootstrap.sh

set -euo pipefail

REPO_URL="https://github.com/willsuan/launch-analysis-api.git"
REPO_DIR="$HOME/launch-analysis-api"

log() { printf '\n\033[1;34m[bootstrap]\033[0m %s\n' "$*"; }
warn() { printf '\n\033[1;33m[bootstrap]\033[0m %s\n' "$*"; }

# --- 1. System deps ---
log "Updating apt and installing base packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    git python3 python3-venv python3-pip \
    curl jq make \
    ca-certificates gnupg lsb-release

# --- 2. Docker (Ubuntu 24.04) ---
if ! command -v docker >/dev/null 2>&1; then
    log "Installing Docker..."
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
    warn "You were added to the 'docker' group. Log out and back in for that to take effect,"
    warn "or prefix docker/compose commands with 'sudo' for now."
else
    log "Docker already installed: $(docker --version)"
fi

# --- 3. kubectl (optional, needed later for cluster deploy) ---
if ! command -v kubectl >/dev/null 2>&1; then
    log "Installing kubectl..."
    KUBECTL_VERSION="$(curl -L -s https://dl.k8s.io/release/stable.txt)"
    curl -fsSLo /tmp/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl"
    sudo install -m 0755 /tmp/kubectl /usr/local/bin/kubectl
    rm /tmp/kubectl
fi

# --- 4. Clone or update repo ---
if [[ -d "$REPO_DIR/.git" ]]; then
    log "Repo already cloned at $REPO_DIR — pulling latest."
    git -C "$REPO_DIR" pull --ff-only
else
    log "Cloning repo into $REPO_DIR..."
    git clone "$REPO_URL" "$REPO_DIR"
fi
cd "$REPO_DIR"

# --- 5. Python venv + deps ---
log "Setting up Python venv..."
if [[ ! -d .venv ]]; then
    python3 -m venv .venv
fi
# shellcheck source=/dev/null
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements.txt fakeredis

# --- 6. Run the test suite ---
log "Running test suite..."
PYTHONPATH=. pytest test/ -q || {
    warn "Tests failed. Check output above."
    exit 1
}

# --- 7. Summary ---
cat <<EOF

\033[1;32m✔ Bootstrap complete.\033[0m

Next steps on this VM:

  cd $REPO_DIR

  # One-time: fetch the full ~7,800 launches from the LL2 API into data/launches.json
  make ingest     # (~several minutes; rate-limited)

  # Bring up the full stack (Redis + API + Worker) locally on the VM
  sudo docker compose up -d --build     # or just 'docker compose' if you've re-logged in

  # Smoke test
  curl http://localhost:5000/help
  curl -X POST http://localhost:5000/data
  curl http://localhost:5000/launches | jq length

  # Submit a job
  curl -X POST http://localhost:5000/jobs \\
    -H 'Content-Type: application/json' \\
    -d '{"plot_type":"frequency_by_provider"}'

  # Once the cluster is ready:
  #   1. edit kubernetes/{test,prod}/*.yml — replace REPLACE_ME and ingress host
  #   2. make k8s-test-apply

EOF
