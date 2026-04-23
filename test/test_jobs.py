"""Tests for the job submission / tracking helpers."""
from src.jobs import (
    get_job,
    list_jobs,
    pop_next_job,
    store_result,
    get_result,
    submit_job,
    update_job_status,
)
from src.models import JobRequest


def test_submit_job_creates_record_and_queues(fake_redis):
    req = JobRequest(plot_type="success_rate_over_time")
    job = submit_job(req)
    assert job.status == "queued"
    # stored in jobs db
    assert get_job(job.id) is not None
    # queued
    assert pop_next_job(timeout=1) == job.id


def test_update_job_status_sets_completed_at(fake_redis):
    job = submit_job(JobRequest(plot_type="frequency_by_provider"))
    update_job_status(job.id, "complete")
    updated = get_job(job.id)
    assert updated.status == "complete"
    assert updated.completed_at is not None


def test_list_jobs(fake_redis):
    submit_job(JobRequest(plot_type="success_rate_over_time"))
    submit_job(JobRequest(plot_type="frequency_by_provider"))
    jobs = list_jobs()
    assert len(jobs) == 2


def test_store_and_get_result(fake_redis):
    store_result("job-abc", b"\x89PNG\r\n...fake image bytes")
    assert get_result("job-abc") == b"\x89PNG\r\n...fake image bytes"
