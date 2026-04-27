"""Redis connection factories.

Four logical databases on one Redis server. Splitting them like this means
flushing the queue (e.g. to recover from a stuck worker) doesn't blow away
completed result images.
"""
import os
import redis

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

RAW_DB = 0      # launch records (JSON strings keyed by launch id)
QUEUE_DB = 1    # job queue LIST
JOBS_DB = 2     # job metadata (status, params, timestamps)
RESULTS_DB = 3  # PNG bytes keyed by job id

QUEUE_KEY = "job_queue"


def get_raw_client() -> redis.Redis:
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=RAW_DB, decode_responses=True)


def get_queue_client() -> redis.Redis:
    # Queue holds job IDs as strings, so decode is fine.
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=QUEUE_DB, decode_responses=True)


def get_jobs_client() -> redis.Redis:
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=JOBS_DB, decode_responses=True)


def get_results_client() -> redis.Redis:
    # Results are raw PNG bytes. decode_responses must be False or redis-py
    # will try to interpret the binary as utf-8 and corrupt it.
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=RESULTS_DB, decode_responses=False)
