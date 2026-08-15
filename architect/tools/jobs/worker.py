"""RQ worker entry — run: python worker.py"""
from __future__ import annotations

import os

import redis
from rq import Worker

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
QUEUES = [q.strip() for q in os.environ.get("RQ_QUEUES", "default,ingest,memory,learn,security").split(",") if q.strip()]


def main() -> None:
    conn = redis.Redis.from_url(REDIS_URL)
    Worker(QUEUES, connection=conn).work(with_scheduler=False)


if __name__ == "__main__":
    main()
