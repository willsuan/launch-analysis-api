"""Redis connection helpers. Four logical databases on the same Redis server."""
import os
import redis

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

# DB 0 = raw launch data, DB 1 = hot queue, DB 2 = jobs metadata, DB 3 = results (images)
RAW_DB = 0
QUEUE_DB = 1
JOBS_DB = 2
RESULTS_DB = 3


def get_raw_client() -> redis.Redis:
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=RAW_DB, decode_responses=True)


def get_queue_client() -> redis.Redis:
    """Queue stores job IDs as strings — decode enabled."""
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=QUEUE_DB, decode_responses=True)


def get_jobs_client() -> redis.Redis:
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=JOBS_DB, decode_responses=True)


def get_results_client() -> redis.Redis:
    """Results store raw PNG bytes — do NOT decode responses."""
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=RESULTS_DB, decode_responses=False)


QUEUE_KEY = "job_queue"
