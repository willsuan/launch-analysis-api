"""Unit tests for the FastAPI application."""
from fastapi.testclient import TestClient

from src.api import app


def test_help_endpoint_lists_routes():
    client = TestClient(app)
    r = client.get("/help")
    assert r.status_code == 200
    body = r.json()
    assert "routes" in body
    assert "GET /help" in body["routes"]
    assert "POST /jobs" in body["routes"]


def test_get_launches_returns_all_when_no_filter(loaded_redis):
    client = TestClient(app)
    r = client.get("/launches")
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_get_launches_filters_by_status(loaded_redis):
    client = TestClient(app)
    r = client.get("/launches?status=Failure")
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["id"] == "launch-3"


def test_get_launches_filters_by_provider(loaded_redis):
    client = TestClient(app)
    r = client.get("/launches?provider=SpaceX")
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["id"] == "launch-2"


def test_get_launches_date_range(loaded_redis):
    client = TestClient(app)
    r = client.get("/launches?start_date=2023-01-01&end_date=2025-12-31")
    assert r.status_code == 200
    ids = [l["id"] for l in r.json()]
    assert ids == ["launch-2"]


def test_get_single_launch(loaded_redis):
    client = TestClient(app)
    r = client.get("/launches/launch-1")
    assert r.status_code == 200
    assert r.json()["name"] == "SLS Block 1 | Artemis II"


def test_get_single_launch_not_found(loaded_redis):
    client = TestClient(app)
    r = client.get("/launches/does-not-exist")
    assert r.status_code == 404


def test_agencies_returns_unique(loaded_redis):
    client = TestClient(app)
    r = client.get("/agencies")
    assert r.status_code == 200
    names = {a["name"] for a in r.json()}
    assert names == {"National Aeronautics and Space Administration", "SpaceX", "Roscosmos"}


def test_agency_launches(loaded_redis):
    client = TestClient(app)
    r = client.get("/agencies/121/launches")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_delete_data_clears_db(loaded_redis):
    client = TestClient(app)
    r = client.delete("/data")
    assert r.status_code == 200
    r2 = client.get("/launches")
    assert r2.json() == []
