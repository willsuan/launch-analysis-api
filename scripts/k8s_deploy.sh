#!/usr/bin/env bash
# Build the image, push to Docker Hub, apply k8s manifests, copy in the
# dataset, and load Redis. Run from the repo root on the class VM.
#
#   bash scripts/k8s_deploy.sh test
#   bash scripts/k8s_deploy.sh prod
#   bash scripts/k8s_deploy.sh test --skip-build   # image already pushed

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

if [[ "$SKIP_BUILD" -eq 0 ]]; then
    if ! docker info >/dev/null 2>&1; then
        SUDO="sudo "
    else
        SUDO=""
    fi
    if ! ${SUDO}docker info 2>/dev/null | grep -q "Username:"; then
        bold "-> docker login"
        ${SUDO}docker login -u "$DOCKER_USER"
    fi
    bold "-> docker build $IMAGE"
    ${SUDO}docker build -t "$IMAGE" .
    bold "-> docker push $IMAGE"
    ${SUDO}docker push "$IMAGE"
fi

bold "-> kubectl apply -f kubernetes/$ENV/"
kubectl apply -f "kubernetes/$ENV/"

bold "-> waiting for pods to become Ready (up to 5 min)..."
kubectl wait --for=condition=Ready pod -l app=$NAMESPACE_PREFIX-redis  --timeout=300s
kubectl wait --for=condition=Ready pod -l app=$NAMESPACE_PREFIX-api    --timeout=300s
kubectl wait --for=condition=Ready pod -l app=$NAMESPACE_PREFIX-worker --timeout=300s

API_POD=$(kubectl get pods -l app=$NAMESPACE_PREFIX-api -o jsonpath='{.items[0].metadata.name}')
bold "-> kubectl cp $DATA_FILE $API_POD:/data/launches.json"
kubectl cp "$DATA_FILE" "$API_POD:/data/launches.json"

bold "-> POST /data inside the API pod to load Redis"
kubectl exec "$API_POD" -- python -c "import urllib.request,json; r=urllib.request.urlopen(urllib.request.Request('http://localhost:5000/data', method='POST')); print(r.read().decode())"

NODE_PORT=$(kubectl get svc $NAMESPACE_PREFIX-api-nodeport -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || echo "")

green "Deployed."
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
bold "=== Smoke test ==="
sleep 3  # ingress takes a few seconds to wire up
if curl -fs -m 10 "http://$INGRESS_HOST/help" | python3 -m json.tool | head -15; then
    green "Public endpoint responding."
else
    warn "Ingress not yet reachable. Give it 30s and try:"
    echo "  curl http://$INGRESS_HOST/help"
fi
