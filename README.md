# Artemis II Launch Data Analysis with a Distributed API System

A REST API for exploring and analyzing space launch data, with a focus on the Artemis program. Built with FastAPI, Redis, and a worker-based architecture for asynchronous plot generation. Deployable locally with Docker Compose and to Kubernetes.

**Authors:** Dilynn Derden and Will Suan
**Course:** COE 332 — Software Engineering and Design

---

## Project Overview

This system allows users to:

- Load the full Launch Library 2 (LL2) dataset into Redis
- Browse launches, missions, and agencies through REST-style collection endpoints
- Filter launches by status, provider, and date range
- Submit analysis jobs that workers process asynchronously
- Retrieve generated plots (as PNG images) from completed jobs

**Three analyses are supported:**

1. Launch success vs. failure rates over time
2. Launch frequency by provider
3. Launch outcomes pie chart for a given provider or rocket family

## Architecture

```
┌─────────┐       POST /jobs       ┌────────────────┐
│  User   │ ─────────────────────▶ │   FastAPI API  │
│  (curl) │                        │   (src/api.py) │
└─────────┘                        └───────┬────────┘
      ▲                                    │
      │ GET /results/<id>                  │  push job ID
      │                                    ▼
      │                           ┌────────────────┐
      │                           │     Redis      │
      │                           │  0: raw data   │
      │                           │  1: job queue  │
      │                           │  2: jobs meta  │
      │                           │  3: results    │
      │                           └───────┬────────┘
      │                                   │  BLPOP job ID
      │                                   ▼
      │                           ┌────────────────┐
      └───────────────────────────│    Worker      │
         completed PNG            │ (src/worker.py)│
                                  └────────────────┘
```

## Data Source

[Launch Library 2 API](https://ll.thespacedevs.com/2.2.0/launch/) — a public dataset of ~7,800 historical and upcoming space launches. We ingest the full dataset once into `data/launches.json` (to avoid hitting the rate limit on each deploy), then load it into Redis on demand via `POST /data`.

## Repository Layout

```
artemis-launch-api/
├── data/                        # local cache of ingested launch data
├── diagram.png                  # software architecture diagram
├── docker-compose.yml
├── Dockerfile
├── kubernetes/
│   ├── prod/                    # production K8s manifests
│   └── test/                    # test K8s manifests
├── Makefile
├── README.md
├── requirements.txt
├── src/
│   ├── api.py                   # FastAPI app
│   ├── ingest.py                # fetch LL2 API → local JSON
│   ├── jobs.py                  # job helpers (Redis-backed)
│   ├── models.py                # pydantic models
│   ├── redis_client.py          # redis db factories
│   └── worker.py                # plot generation worker loop
└── test/
    ├── conftest.py              # fakeredis fixtures + sample data
    ├── test_api.py
    ├── test_jobs.py
    └── test_worker.py
```

---

## Setup & Testing on a Local Linux VM

### 1. Clone and install

```bash
git clone <your-repo-url>
cd artemis-launch-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt fakeredis
```

### 2. Fetch the dataset (one time)

```bash
make ingest
```

This walks the paginated LL2 API and writes `data/launches.json`. It takes several minutes and is rate-limited — you only need to do it once.

### 3. Run the test suite

```bash
make test
```

Tests use `fakeredis` so they don't need a running Redis server.

### 4. Run the stack locally with Docker Compose

```bash
make compose-up
```

This brings up Redis, the API (on port 5000), and a worker. In another shell:

```bash
# Load the dataset into Redis
curl -X POST http://localhost:5000/data

# Browse launches
curl http://localhost:5000/launches | jq '.[0]'

# Filter
curl 'http://localhost:5000/launches?provider=SpaceX&status=success' | jq length

# Submit a job
curl -X POST http://localhost:5000/jobs \
  -H 'Content-Type: application/json' \
  -d '{"plot_type": "success_rate_over_time"}'

# Check job status
curl http://localhost:5000/jobs/<job-id>

# Download the result image
curl http://localhost:5000/results/<job-id> -o plot.png
```

### 5. Tear down

```bash
make compose-down
```

---

## Deployment & Testing on the Kubernetes Cluster

### 1. Build and push the image

```bash
make build IMAGE=yourdockerhub/artemis-launch-api TAG=test
make push  IMAGE=yourdockerhub/artemis-launch-api TAG=test
```

Replace the `REPLACE_ME/...` placeholder in `kubernetes/{test,prod}/*deployment*` with your image.

### 2. Apply manifests

```bash
# Test environment
make k8s-test-apply

# Production
make k8s-prod-apply
```

This creates a Redis Deployment + PVC + Service, the API Deployment + ClusterIP Service + NodePort + Ingress, and the Worker Deployment.

### 3. Load data into the cluster

Copy `data/launches.json` into the running API pod (it reads from `/data/launches.json`):

```bash
kubectl cp data/launches.json $(kubectl get pod -l app=artemis-test-api -o name | cut -d/ -f2):/data/launches.json
curl -X POST https://artemis-test.coe332.tacc.cloud/data
```

Update the ingress `host:` field to match your class cluster's domain before applying.

### 4. Public-URL usage

Once the ingress is wired up, all endpoints are reachable at the public hostname, e.g.:

```bash
curl https://artemis-test.coe332.tacc.cloud/help
curl https://artemis-test.coe332.tacc.cloud/launches?provider=NASA
```

### 5. Backup & Restore

Redis is configured with `--save 60 1 --appendonly yes`, so:

- **RDB snapshots** (`dump.rdb`) are written every 60 seconds if at least one key changed.
- **AOF** (`appendonly.aof`) records every write operation.
- Both files live on the `artemis-{env}-redis-pvc` PersistentVolumeClaim so they survive pod restarts.

To restore from a snapshot, copy the `dump.rdb` file onto the Redis PVC mount point (`/data` inside the pod) and restart the Redis deployment — Redis loads it automatically at startup.

---

## API Endpoints

| Method | Path                           | Description |
|--------|--------------------------------|-------------|
| GET    | `/help`                        | List all routes |
| POST   | `/data`                        | Load dataset from disk into Redis |
| GET    | `/data`                        | Return all raw launch records |
| DELETE | `/data`                        | Clear raw data DB |
| GET    | `/launches`                    | All launches (filters: `status`, `provider`, `start_date`, `end_date`) |
| GET    | `/launches/{id}`               | Single launch |
| GET    | `/missions`                    | All missions (deduped) |
| GET    | `/agencies`                    | All launch providers (deduped) |
| GET    | `/agencies/{id}/launches`      | All launches for an agency |
| POST   | `/jobs`                        | Submit an analysis job |
| GET    | `/jobs`                        | All jobs |
| GET    | `/jobs/{id}`                   | Single job metadata |
| GET    | `/results/{id}`                | PNG image for a completed job |

### Example: Submitting a job

```bash
curl -X POST http://localhost:5000/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "plot_type": "outcomes_pie",
    "provider": "SpaceX"
  }'
```

Supported `plot_type` values:
- `success_rate_over_time` — optional `start_year`, `end_year`
- `frequency_by_provider`
- `outcomes_pie` — optional `provider` or `rocket_family`

## Citations

- Launch Library 2 API by The Space Devs: https://ll.thespacedevs.com/
- FastAPI: https://fastapi.tiangolo.com/
- Redis: https://redis.io/
- Kubernetes: https://kubernetes.io/
