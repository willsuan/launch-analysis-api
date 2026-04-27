"""Worker loop. BLPOP a job, render a matplotlib chart, write the PNG back into Redis."""
import io
import json
import os
import sys
from collections import Counter, defaultdict

# Force the non-interactive backend before pyplot is imported. Without this
# matplotlib will try to open a Tk window inside the container and crash.
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.jobs import (
    get_job,
    pop_next_job,
    store_result,
    update_job_status,
)
from src.redis_client import get_raw_client


def _iter_launches():
    client = get_raw_client()
    for key in client.scan_iter("*"):
        raw = client.get(key)
        if raw:
            yield json.loads(raw)


def _year(launch: dict) -> int | None:
    net = launch.get("net") or ""
    try:
        return int(net[:4])
    except (ValueError, TypeError):
        return None


def plot_success_rate_over_time(start_year: int | None, end_year: int | None) -> bytes:
    """Stacked bar of successes vs. failures by year."""
    per_year_success = Counter()
    per_year_failure = Counter()
    for launch in _iter_launches():
        yr = _year(launch)
        if yr is None:
            continue
        if start_year and yr < start_year:
            continue
        if end_year and yr > end_year:
            continue
        status_name = ((launch.get("status") or {}).get("name") or "").lower()
        if "success" in status_name and "partial" not in status_name:
            per_year_success[yr] += 1
        elif "failure" in status_name:
            per_year_failure[yr] += 1
    years = sorted(set(per_year_success) | set(per_year_failure))
    if not years:
        raise ValueError("No launches matched the year filter")

    successes = [per_year_success[y] for y in years]
    failures = [per_year_failure[y] for y in years]

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(years, successes, label="Success", color="tab:green")
    ax.bar(years, failures, bottom=successes, label="Failure", color="tab:red")
    ax.set_xlabel("Year")
    ax.set_ylabel("Launches")
    ax.set_title("Launch Success vs. Failure Over Time")
    ax.legend()
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def plot_frequency_by_provider(top_n: int = 15) -> bytes:
    counts = Counter()
    for launch in _iter_launches():
        prov = (launch.get("launch_service_provider") or {}).get("name")
        if prov:
            counts[prov] += 1
    if not counts:
        raise ValueError("No provider data found in launches")
    top = counts.most_common(top_n)
    names = [t[0] for t in top][::-1]
    values = [t[1] for t in top][::-1]

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(names, values, color="tab:blue")
    ax.set_xlabel("Number of launches")
    ax.set_title(f"Top {top_n} Launch Providers by Number of Launches")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def plot_outcomes_pie(provider: str | None, rocket_family: str | None) -> bytes:
    counts = Counter()
    for launch in _iter_launches():
        if provider:
            p = ((launch.get("launch_service_provider") or {}).get("name") or "")
            if provider.lower() not in p.lower():
                continue
        if rocket_family:
            f = (((launch.get("rocket") or {}).get("configuration") or {}).get("family") or "")
            if rocket_family.lower() not in f.lower():
                continue
        status = ((launch.get("status") or {}).get("name") or "Unknown")
        counts[status] += 1
    if not counts:
        raise ValueError("No launches matched the provider/rocket_family filter")

    # most_common ordering keeps legend entries in the same order as slices.
    items = counts.most_common()
    labels = [s for s, _ in items]
    values = [c for _, c in items]
    total = sum(values)

    # Inline percent on small slices stacks unreadably, so suppress below 4%.
    def autopct_only_large(pct: float) -> str:
        return f"{pct:.1f}%" if pct >= 4.0 else ""

    fig, ax = plt.subplots(figsize=(9, 7))
    wedges, _, _ = ax.pie(
        values,
        autopct=autopct_only_large,
        startangle=90,
        pctdistance=0.7,
        textprops={"fontsize": 10, "color": "white", "fontweight": "bold"},
    )

    legend_labels = [
        f"{label} ({count:,}, {100 * count / total:.1f}%)"
        for label, count in items
    ]
    ax.legend(
        wedges,
        legend_labels,
        title="Outcome",
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        frameon=False,
    )

    filter_desc = provider or rocket_family or "All launches"
    ax.set_title(f"Launch Outcomes: {filter_desc}  (n={total:,})")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


PLOT_DISPATCH = {
    "success_rate_over_time": lambda job: plot_success_rate_over_time(job.start_year, job.end_year),
    "frequency_by_provider": lambda job: plot_frequency_by_provider(),
    "outcomes_pie": lambda job: plot_outcomes_pie(job.provider, job.rocket_family),
}


def process_one_job(job_id: str) -> None:
    job = get_job(job_id)
    if job is None:
        print(f"Job {job_id} not found", flush=True)
        return
    update_job_status(job_id, "in_progress")
    print(f"Processing job {job_id}: {job.plot_type}", flush=True)

    try:
        handler = PLOT_DISPATCH.get(job.plot_type)
        if handler is None:
            raise ValueError(f"Unknown plot_type: {job.plot_type}")
        image_bytes = handler(job)
        store_result(job_id, image_bytes)
        update_job_status(job_id, "complete")
        print(f"Completed job {job_id}", flush=True)
    except Exception as e:
        print(f"Job {job_id} failed: {e}", flush=True)
        update_job_status(job_id, "failed", error=str(e))


def main() -> None:
    print("Worker started. Waiting for jobs...", flush=True)
    while True:
        job_id = pop_next_job(timeout=5)
        if job_id is None:
            continue
        process_one_job(job_id)


if __name__ == "__main__":
    main()
