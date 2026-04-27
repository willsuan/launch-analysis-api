#!/usr/bin/env bash
# k8s_deploy.sh — full Kubernetes deployment in one shot.
#
# Steps it performs:
#   1. docker login (only if needed)
#   2. docker build & push willsuan/artemis-launch-api:<env>
#   3. kubectl apply -f kubernetes/<env>/
#   4. wait for the API pod to become Ready
#   5. kubectl cp data/launches.json into the API pod
#   6. curl POST /data inside the API pod to load Redis
#   7. print the public URL and run a smoke test
#
# Usage (run from the VM, inside ~/launch-analysis-api):
#   bash scripts/k8s_deploy.sh test     # default
#   bash scripts/k8s_deploy.sh prod
#   bash scripts/k8s_deploy.sh test --skip-build   # if image already pushed

set -euo pipefail

ENV="${1:-test}"
SKIP_BUILD=0
if [[ "${2:-}" == "--skip-build" ]]; then SKIP_BUILD=1; fi

if [[ "$ENV" != "test" && "$ENV" != "prod" ]]; then
    echo "Usage: $0 {test|prod} [--skip-build]"
    exit 1
fi

DOCKER_USER="willsuan"
IMAGE="$DOCKER_USER/artemis-launch-api:$ENV"
NAMESPACE_PREFIX="artemis-$ENV"
INGRESS_HOST=$(grep -h '^[[:space:]]*- host:' "kubernetes/$ENV/app-$ENV-ingress-api.yml" | sed 's/.*"\(.*\)".*/\1/')
DATA_FILE="data/launches.json"

bold()  { printf '\033[1m%s\033[0m\n' "$*"; }
green() { printf '\033[1;32m%s\033[0m\n' "$*"; }
blue()  { printf '\033[1;34m%s\033[0m\n' "$*"; }
warn()  { printf '\033[1;33m%s\033[0m\n' "$*"; }

# --------- 0. Sanity ---------
if ! command -v kubectl >/dev/null 2>&1; then
    warn "kubectl not found. Are you on the class VM?"
    exit 1
fi
if [[ ! -f "$DATA_FILE" ]]; then
    warn "$DATA_FILE missing. Run 'bash scripts/auto_ingest.sh' first."
    exit 1
fi

bold "=== Deploying to $ENV ==="
echo "  Image:        $IMAGE"
echo "  Ingress host: $INGRESS_HOST"
echo "  Data file:    $DATA_FILE ($(wc -c < "$DATA_FILE") bytes)"
echo

# --------- 1. Build & push ---------
if [[ "$SKIP_BUILD" -eq 0 ]]; then
    if ! docker info >/dev/null 2>&1; then
        SUDO="sudo "
    else
        SUDO=""
    fi
    if ! ${SUDO}docker info 2>/dev/null | grep -q "Username:"; then
        bold "→ docker login required"
        ${SUDO}docker login -u "$DOCKER_USER"
    fi
    bold "→ docker build $IMAGE"
    ${SUDO}docker build -t "$IMAGE" .
    bold "→ docker push $IMAGE"
    ${SUDO}docker push "$IMAGE"
fi

# --------- 2. Apply manifests ---------
bold "→ kubectl apply -f kubernetes/$ENV/"
kubectl apply -f "kubernetes/$ENV/"

# --------- 3. Wait for pods ---------
bold "→ Waiting for pods to become Ready (up to 5 minutes)..."
kubectl wait --for=condition=Ready pod -l app=$NAMESPACE_PREFIX-redis  --timeout=300s
kubectl wait --for=condition=Ready pod -l app=$NAMESPACE_PREFIX-api    --timeout=300s
kubectl wait --for=condition=Ready pod -l app=$NAMESPACE_PREFIX-worker --timeout=300s

# --------- 4. Copy data file ---------
API_POD=$(kubectl get pods -l app=$NAMESPACE_PREFIX-api -o jsonpath='{.items[0].metadata.name}')
bold "→ kubectl cp $DATA_FILE $API_POD:/data/launches.json"
kubectl cp "$DATA_FILE" "$API_POD:/data/launches.json"

# --------- 5. Load Redis ---------
bold "→ POST /data inside the API pod to load Redis"
kubectl exec "$API_POD" -- python -c "import urllib.request,json; r=urllib.request.urlopen(urllib.request.Request('http://localhost:5000/data', method='POST')); print(r.read().decode())"

# --------- 6. Public smoke test ---------
NODE_PORT=$(kubectl get svc $NAMESPACE_PREFIX-api-nodeport -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || echo "")

green "✔ Deployed."
echo
bold "=== Connection details ==="
echo "  Pods:"
kubectl get pods -l "app in ($NAMESPACE_PREFIX-api,$NAMESPACE_PREFIX-redis,$NAMESPACE_PREFIX-worker)" 2>/dev/null \
  | sed 's/^/    /'
echo
echo "  Public URL (Ingress):"
echo "    http://$INGRESS_HOST/help"
echo "    http://$INGRESS_HOST/launches?provider=SpaceX"
if [[ -n "$NODE_PORT" ]]; then
    echo
    echo "  NodePort fallback (from class network):"
    echo "    curl coe332.tacc.cloud:$NODE_PORT/help"
fi
echo
bold "=== Smoke test (via ingress) ==="
sleep 3  # ingress takes a few seconds to wire up
if curl -fs -m 10 "http://$INGRESS_HOST/help" | python3 -m json.tool | head -15; then
    green "✔ Public endpoint responding."
else
    warn "Ingress not yet reachable — give it 30s and retry:"
    echo "  curl http://$INGRESS_HOST/help"
fi
