"""Entrypoint for the batch-scoring worker process.

Usage (from backend/, separate process from uvicorn):
    python -m app.workers.run_worker

Uses SimpleWorker, not the default Worker: RQ's default worker forks a
child process per job (os.fork()) for isolation, which doesn't exist on
Windows. SimpleWorker runs jobs in-process instead -- the documented
cross-platform fallback. Trade-off: a crashing job takes the worker process
down with it (no fork boundary), so a supervisor that restarts the worker
matters more here than it would on Linux.

Also overrides death_penalty_class: RQ's default enforces job_timeout via
SIGALRM, which doesn't exist on Windows either. TimerDeathPenalty is RQ's
thread-based, signal-free alternative.
"""
from rq import SimpleWorker
from rq.timeouts import TimerDeathPenalty

from app.workers.queue import batch_queue, redis_conn

if __name__ == "__main__":
    worker = SimpleWorker([batch_queue], connection=redis_conn)
    worker.death_penalty_class = TimerDeathPenalty
    worker.work()
