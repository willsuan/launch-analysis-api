"""Tests for plot generators. Each test verifies we return non-empty PNG bytes."""
import pytest

from src import worker


PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_plot_success_rate_over_time(loaded_redis):
    img = worker.plot_success_rate_over_time(start_year=None, end_year=None)
    assert img.startswith(PNG_MAGIC)
    assert len(img) > 100


def test_plot_frequency_by_provider(loaded_redis):
    img = worker.plot_frequency_by_provider(top_n=5)
    assert img.startswith(PNG_MAGIC)


def test_plot_outcomes_pie_all(loaded_redis):
    img = worker.plot_outcomes_pie(provider=None, rocket_family=None)
    assert img.startswith(PNG_MAGIC)


def test_plot_outcomes_pie_filtered(loaded_redis):
    img = worker.plot_outcomes_pie(provider="SpaceX", rocket_family=None)
    assert img.startswith(PNG_MAGIC)


def test_plot_outcomes_pie_no_match_raises(loaded_redis):
    with pytest.raises(ValueError):
        worker.plot_outcomes_pie(provider="NonexistentProvider", rocket_family=None)


def test_process_one_job_end_to_end(loaded_redis):
    from src.jobs import submit_job, get_job, get_result
    from src.models import JobRequest

    job = submit_job(JobRequest(plot_type="frequency_by_provider"))
    worker.process_one_job(job.id)

    updated = get_job(job.id)
    assert updated.status == "complete"
    img = get_result(job.id)
    assert img is not None and img.startswith(PNG_MAGIC)


def test_process_one_job_unknown_plot_type_fails(loaded_redis):
    from src.jobs import submit_job, get_job
    from src.models import JobRequest

    job = submit_job(JobRequest(plot_type="bogus_plot"))
    worker.process_one_job(job.id)
    updated = get_job(job.id)
    assert updated.status == "failed"
    assert "Unknown plot_type" in (updated.error or "")
