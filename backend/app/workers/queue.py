"""RQ (Redis Queue) setup for async batch scoring jobs (blueprint's
"Background Worker (Celery/RQ)" component). A CSV upload enqueues a job here
and returns immediately; a separate `rq worker` process (started with
`python -m app.workers.run_worker`) picks it up and does the actual scoring,
so the API process never blocks on a large batch.
"""
import redis
from rq import Queue

from app.core.config import get_settings

settings = get_settings()

redis_conn = redis.from_url(settings.redis_url)
batch_queue = Queue("batch_scoring", connection=redis_conn)
