"""Fetches the full launch dataset from the Launch Library 2 API and caches it to disk.

The LL2 public API is rate-limited (~15 req/hour unauthenticated), so we
ingest once into a local JSON file and then load that into Redis on demand.
"""
import json
import os
import sys
import time
from pathlib import Path

import requests

LL2_BASE = "https://ll.thespacedevs.com/2.2.0/launch/"
DATA_FILE = Path(os.environ.get("DATA_FILE", "/data/launches.json"))
PAGE_LIMIT = 100  # max the API allows


def fetch_all_launches(sleep_between: float = 2.0) -> list[dict]:
    """Walk the paginated API and return every launch record."""
    results = []
    url = f"{LL2_BASE}?mode=normal&limit={PAGE_LIMIT}"
    page = 1
    while url:
        print(f"Fetching page {page}: {url}", flush=True)
        resp = requests.get(url, timeout=30)
        if resp.status_code == 429:
            print("Rate limited. Sleeping 60s...", flush=True)
            time.sleep(60)
            continue
        resp.raise_for_status()
        payload = resp.json()
        results.extend(payload.get("results", []))
        url = payload.get("next")
        page += 1
        time.sleep(sleep_between)
    return results


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
    save_to_disk(launches)
    print(f"Done. Total records: {len(launches)}")
