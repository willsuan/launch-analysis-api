"""Fetches the full launch dataset from the Launch Library 2 API and caches it to disk.

The LL2 public API is rate-limited (~15 req/hour unauthenticated). This module:

1. Saves progress incrementally to data/launches.json after every page so the
   work isn't lost when the network or the SSH session drops.
2. Persists the next URL in a tiny progress file (data/.ingest_progress) so
   subsequent runs resume where the last one left off.
3. Backs off exponentially on rate-limit responses (60s -> 5min -> 20min)
   instead of hammering the API every minute.
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
    """Return (existing_launches, next_url). If neither file exists, return ([], starting_url)."""
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
        # Fresh run
        next_url = f"{LL2_BASE}?mode=normal&limit={PAGE_LIMIT}"

    if next_url == "DONE":
        next_url = None

    return launches, next_url


def _save_state(launches: list[dict], next_url: str | None) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Atomic-ish: write to .tmp then rename
    tmp = DATA_FILE.with_suffix(DATA_FILE.suffix + ".tmp")
    with open(tmp, "w") as f:
        json.dump(launches, f)
    tmp.replace(DATA_FILE)
    PROGRESS_FILE.write_text(next_url if next_url else "DONE")


def fetch_all_launches(sleep_between: float = 5.0) -> list[dict]:
    """Walk the paginated API. Resumes from disk if a prior run was interrupted.

    Saves after every successful page so SSH disconnects don't kill progress.
    """
    launches, url = _load_state()
    seen_ids = {l.get("id") for l in launches if l.get("id")}

    if url is None:
        print(f"Already complete. {len(launches)} launches in {DATA_FILE}", flush=True)
        return launches

    if launches:
        print(f"Resuming with {len(launches)} launches already on disk.", flush=True)

    backoff_steps = [60, 300, 1200]  # 1m, 5m, 20m
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
        backoff_idx = 0  # reset after a success

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

        # Persist after every successful page
        _save_state(launches, url)
        print(f"  +{new_count} launches (total: {len(launches)})", flush=True)

        if url:
            time.sleep(sleep_between)

    # Mark complete
    _save_state(launches, None)
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
