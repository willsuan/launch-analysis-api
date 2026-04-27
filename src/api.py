"""HTTP layer. CRUD on launch data, plus job submission and result retrieval."""
import json
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Response

from src import ingest
from src.jobs import (
    get_job,
    get_result,
    list_jobs,
    submit_job,
)
from src.models import Job, JobRequest, Launch
from src.redis_client import get_raw_client

app = FastAPI(
    title="Artemis II Launch Data Analysis API",
    description="REST API for exploring and analyzing space launch data with a focus on the Artemis program.",
    version="0.1.0",
)


@app.get("/help")
def help_routes() -> dict:
    """Describes all available routes."""
    return {
        "routes": {
            "GET /help": "Describes all available routes",
            "POST /data": "Loads the launch dataset from disk into Redis",
            "GET /data": "Returns all launch records",
            "DELETE /data": "Deletes all launch data from Redis",
            "GET /launches": "Returns launches. Query params: status, provider, start_date, end_date",
            "GET /launches/{id}": "Returns a specific launch by ID",
            "GET /missions": "Returns all missions",
            "GET /agencies": "Returns all launch providers",
            "GET /agencies/{id}/launches": "Returns all launches for a specific agency ID",
            "POST /jobs": "Submits a new analysis job",
            "GET /jobs": "Returns all jobs and their statuses",
            "GET /jobs/{id}": "Returns status and info for a specific job",
            "GET /results/{id}": "Retrieves the resulting image from a completed job",
        }
    }


@app.post("/data")
def load_data() -> dict:
    """Bulk-load data/launches.json into the raw-data Redis db."""
    try:
        launches = ingest.load_from_disk()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    client = get_raw_client()
    client.flushdb()
    pipe = client.pipeline()
    for launch in launches:
        pipe.set(launch["id"], json.dumps(launch))
    pipe.execute()
    return {"loaded": len(launches)}


@app.get("/data")
def get_all_data() -> list[dict]:
    """Dump every record. Big response (~30MB) for the full dataset."""
    client = get_raw_client()
    out = []
    for key in client.scan_iter("*"):
        raw = client.get(key)
        if raw:
            out.append(json.loads(raw))
    return out


@app.delete("/data")
def delete_data() -> dict:
    client = get_raw_client()
    client.flushdb()
    return {"deleted": True}


def _iter_launches():
    client = get_raw_client()
    for key in client.scan_iter("*"):
        raw = client.get(key)
        if raw:
            yield json.loads(raw)


@app.get("/launches")
def get_launches(
    status: Optional[str] = Query(None, description="Filter by launch status name (e.g., 'Launch Successful')"),
    provider: Optional[str] = Query(None, description="Filter by launch provider name"),
    start_date: Optional[str] = Query(None, description="ISO date lower bound for net field"),
    end_date: Optional[str] = Query(None, description="ISO date upper bound for net field"),
) -> list[dict]:
    out = []
    for launch in _iter_launches():
        if status:
            st = (launch.get("status") or {}).get("name", "")
            if status.lower() not in st.lower():
                continue
        if provider:
            prov = (launch.get("launch_service_provider") or {}).get("name", "")
            if provider.lower() not in prov.lower():
                continue
        if start_date:
            net = launch.get("net") or ""
            if net < start_date:
                continue
        if end_date:
            net = launch.get("net") or ""
            if net > end_date:
                continue
        out.append(launch)
    return out


@app.get("/launches/{launch_id}")
def get_launch(launch_id: str) -> dict:
    client = get_raw_client()
    raw = client.get(launch_id)
    if raw is None:
        raise HTTPException(status_code=404, detail=f"No launch with id {launch_id}")
    return json.loads(raw)


@app.get("/missions")
def get_missions() -> list[dict]:
    seen = {}
    for launch in _iter_launches():
        m = launch.get("mission")
        if m and m.get("id") is not None:
            seen[m["id"]] = m
    return list(seen.values())


@app.get("/agencies")
def get_agencies() -> list[dict]:
    seen = {}
    for launch in _iter_launches():
        a = launch.get("launch_service_provider")
        if a and a.get("id") is not None:
            seen[a["id"]] = a
    return list(seen.values())


@app.get("/agencies/{agency_id}/launches")
def get_agency_launches(agency_id: int) -> list[dict]:
    out = []
    for launch in _iter_launches():
        a = launch.get("launch_service_provider") or {}
        if a.get("id") == agency_id:
            out.append(launch)
    return out


@app.post("/jobs")
def create_job(req: JobRequest) -> Job:
    return submit_job(req)


@app.get("/jobs")
def get_all_jobs() -> list[Job]:
    return list_jobs()


@app.get("/jobs/{job_id}")
def get_single_job(job_id: str) -> Job:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No job with id {job_id}")
    return job


@app.get("/results/{job_id}")
def get_job_result(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No job with id {job_id}")
    if job.status != "complete":
        raise HTTPException(status_code=409, detail=f"Job {job_id} status is '{job.status}', not 'complete'")
    img = get_result(job_id)
    if img is None:
        raise HTTPException(status_code=404, detail=f"No result image for job {job_id}")
    return Response(content=img, media_type="image/png")
