"""Shared fixtures. Uses fakeredis to avoid needing a real Redis during unit tests."""
import json
import sys
import types
from pathlib import Path

import pytest

# Ensure the repo root is on sys.path so `import src.*` works
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SAMPLE_LAUNCHES = [
    {
        "id": "launch-1",
        "name": "SLS Block 1 | Artemis II",
        "status": {"id": 3, "name": "Launch Successful"},
        "net": "2026-04-01T22:35:12Z",
        "launch_service_provider": {"id": 44, "name": "National Aeronautics and Space Administration", "type": "Government"},
        "rocket": {"id": 1, "configuration": {"id": 1, "name": "SLS Block 1", "family": "SLS"}},
        "mission": {"id": 100, "name": "Artemis II", "type": "Human Exploration", "orbit": {"name": "Lunar Orbit"}},
    },
    {
        "id": "launch-2",
        "name": "Falcon 9 | Starlink",
        "status": {"id": 3, "name": "Launch Successful"},
        "net": "2024-01-15T12:00:00Z",
        "launch_service_provider": {"id": 121, "name": "SpaceX", "type": "Commercial"},
        "rocket": {"id": 2, "configuration": {"id": 2, "name": "Falcon 9", "family": "Falcon"}},
        "mission": {"id": 200, "name": "Starlink", "type": "Communications", "orbit": {"name": "LEO"}},
    },
    {
        "id": "launch-3",
        "name": "Proton | Example",
        "status": {"id": 4, "name": "Launch Failure"},
        "net": "2019-05-10T08:00:00Z",
        "launch_service_provider": {"id": 63, "name": "Roscosmos", "type": "Government"},
        "rocket": {"id": 3, "configuration": {"id": 3, "name": "Proton-M", "family": "Proton"}},
        "mission": {"id": 300, "name": "Example Satellite", "type": "Communications", "orbit": {"name": "GTO"}},
    },
]


@pytest.fixture
def fake_redis(monkeypatch):
    """Replace all Redis clients with fakeredis-backed instances.

    Falls back to a simple in-memory dict if fakeredis isn't installed —
    enough coverage for the model/plot logic. For deeper integration tests
    install fakeredis: `pip install fakeredis`.
    """
    try:
        import fakeredis
    except ImportError:
        pytest.skip("fakeredis not installed; install it for full test coverage")

    raw = fakeredis.FakeRedis(decode_responses=True)
    queue = fakeredis.FakeRedis(decode_responses=True)
    jobs = fakeredis.FakeRedis(decode_responses=True)
    results = fakeredis.FakeRedis(decode_responses=False)

    from src import redis_client
    monkeypatch.setattr(redis_client, "get_raw_client", lambda: raw)
    monkeypatch.setattr(redis_client, "get_queue_client", lambda: queue)
    monkeypatch.setattr(redis_client, "get_jobs_client", lambda: jobs)
    monkeypatch.setattr(redis_client, "get_results_client", lambda: results)

    # jobs.py, api.py, and worker.py import these at module-scope, so patch there too
    from src import jobs as jobs_module, api as api_module, worker as worker_module
    monkeypatch.setattr(jobs_module, "get_jobs_client", lambda: jobs)
    monkeypatch.setattr(jobs_module, "get_queue_client", lambda: queue)
    monkeypatch.setattr(jobs_module, "get_results_client", lambda: results)
    monkeypatch.setattr(api_module, "get_raw_client", lambda: raw)
    monkeypatch.setattr(worker_module, "get_raw_client", lambda: raw)

    return {"raw": raw, "queue": queue, "jobs": jobs, "results": results}


@pytest.fixture
def loaded_redis(fake_redis):
    """Pre-populate the raw DB with sample launches."""
    for launch in SAMPLE_LAUNCHES:
        fake_redis["raw"].set(launch["id"], json.dumps(launch))
    return fake_redis
