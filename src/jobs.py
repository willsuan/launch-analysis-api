"""Job helpers. Thin wrappers around Redis to keep api.py and worker.py clean."""
import json
import uuid
from datetime import datetime, timezone

from src.redis_client import get_jobs_client, get_queue_client, get_results_client, QUEUE_KEY
from src.models import Job, JobRequest


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def submit_job(req: JobRequest) -> Job:
    """Create a new job, store it, and push its ID onto the queue."""
    job_id = str(uuid.uuid4())
    job = Job(
        id=job_id,
        status="queued",
        plot_type=req.plot_type,
        provider=req.provider,
        rocket_family=req.rocket_family,
        start_year=req.start_year,
        end_year=req.end_year,
        submitted_at=_now_iso(),
    )
    jobs_client = get_jobs_client()
    jobs_client.set(job_id, job.model_dump_json())

    queue_client = get_queue_client()
    queue_client.rpush(QUEUE_KEY, job_id)

    return job


def get_job(job_id: str) -> Job | None:
    raw = get_jobs_client().get(job_id)
    if raw is None:
        return None
    return Job.model_validate_json(raw)


def list_jobs() -> list[Job]:
    client = get_jobs_client()
    jobs = []
    for key in client.scan_iter("*"):
        raw = client.get(key)
        if raw:
            jobs.append(Job.model_validate_json(raw))
    return jobs


def update_job_status(
    job_id: str,
    status: str,
    error: str | None = None,
) -> None:
    job = get_job(job_id)
    if job is None:
        return
    job.status = status
    if status in ("complete", "failed"):
        job.completed_at = _now_iso()
    if error is not None:
        job.error = error
    get_jobs_client().set(job_id, job.model_dump_json())


def pop_next_job(timeout: int = 0) -> str | None:
    """Blocking pop. Returns a job ID or None on timeout."""
    client = get_queue_client()
    result = client.blpop(QUEUE_KEY, timeout=timeout)
    if result is None:
        return None
    _, job_id = result
    return job_id


def store_result(job_id: str, image_bytes: bytes) -> None:
    get_results_client().set(job_id, image_bytes)


def get_result(job_id: str) -> bytes | None:
    return get_results_client().get(job_id)
