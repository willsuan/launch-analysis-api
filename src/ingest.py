"""Pulls the LL2 launch dataset down to disk.

LL2's anonymous limit is around 15 requests per hour and the full crawl is
~78 pages, so a naive run will burn all night repeating the same retry. The
fix is three things:

  1. After every page that succeeds, write the cumulative result to
     data/launches.json. If anything kills the process, no work is lost.
  2. Persist the URL of the next page in data/.ingest_progress. A subsequent
     run reads it and picks up from there.
  3. On 429, back off 60s, then 5m, then 20m. Polling every minute just
     sits in the rate window forever.
"""
import json
import os
import time
from pathlib import Path

import requests

LL2_BASE = "https://ll.thespacedevs.com/2.2.0/launch/"
DATA_FILE = Path(os.environ.get("DATA_FILE", "/data/launches.json"))
PROGRESS_FILE = DATA_FILE.parent / ".ingest_progress"
PAGE_LIMIT = 100


def _load_state() -> tuple[list[dict], str | None]:
    """Read what we have on disk. Returns (existing launches, next URL to fetch)."""
    launches: list[dict] = []
    next_url: str | None = None

    if DATA_FILE.exists():
        try:
            with open(DATA_FILE) as f:
                launches = json.load(f)
        except (json.JSONDecodeError, OSError):
            launches = []

    if PROGRESS_FILE.exists():
        try:
            next_url = PROGRESS_FILE.read_text().strip() or None
        except OSError:
            next_url = None
    else:
        # No progress file means a fresh run; start from page 1.
        next_url = f"{LL2_BASE}?mode=normal&limit={PAGE_LIMIT}"

    if next_url == "DONE":
        next_url = None

    return launches, next_url


def _save_state(launches: list[dict], next_url: str | None) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Write to a sibling tmp file and rename so a crash mid-write can't leave
    # us with a half-written launches.json.
    tmp = DATA_FILE.with_suffix(DATA_FILE.suffix + ".tmp")
    with open(tmp, "w") as f:
        json.dump(launches, f)
    tmp.replace(DATA_FILE)
    PROGRESS_FILE.write_text(next_url if next_url else "DONE")


def fetch_all_launches(sleep_between: float = 5.0) -> list[dict]:
    """Walk LL2's paginated launch endpoint until exhausted, resuming if needed."""
    launches, url = _load_state()
    seen_ids = {l.get("id") for l in launches if l.get("id")}

    if url is None:
        print(f"Already complete. {len(launches)} launches in {DATA_FILE}", flush=True)
        return launches

    if launches:
        print(f"Resuming with {len(launches)} launches already on disk.", flush=True)

    # Step ladder: first 429 sleeps a minute, then 5, then 20.
    backoff_steps = [60, 300, 1200]
    backoff_idx = 0
    page = 1
    while url:
        print(f"Fetching page {page}: {url}", flush=True)
        try:
            resp = requests.get(url, timeout=30)
        except requests.RequestException as e:
            print(f"Network error: {e}. Backing off 60s.", flush=True)
            time.sleep(60)
            continue

        if resp.status_code == 429:
            wait = backoff_steps[min(backoff_idx, len(backoff_steps) - 1)]
            backoff_idx += 1
            print(f"Rate limited. Sleeping {wait}s before retry...", flush=True)
            time.sleep(wait)
            continue

        if resp.status_code >= 500:
            print(f"Server error {resp.status_code}. Sleeping 60s.", flush=True)
            time.sleep(60)
            continue

        resp.raise_for_status()
        backoff_idx = 0  # any successful fetch resets the ladder

        payload = resp.json()
        new_count = 0
        for launch in payload.get("results", []):
            lid = launch.get("id")
            if lid and lid not in seen_ids:
                launches.append(launch)
                seen_ids.add(lid)
                new_count += 1

        url = payload.get("next")
        page += 1

        _save_state(launches, url)
        print(f"  +{new_count} launches (total: {len(launches)})", flush=True)

        if url:
            time.sleep(sleep_between)

    _save_state(launches, None)  # writes "DONE" so next run is a no-op
    return launches


def save_to_disk(launches: list[dict], path: Path = DATA_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(launches, f)
    print(f"Wrote {len(launches)} launches to {path}", flush=True)


def load_from_disk(path: Path = DATA_FILE) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"No local dataset at {path}. Run `python -m src.ingest` to fetch it."
        )
    with open(path) as f:
        return json.load(f)


if __name__ == "__main__":
    launches = fetch_all_launches()
    print(f"Done. Total records: {len(launches)}")
