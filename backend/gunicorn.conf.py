"""Gunicorn configuration for production."""

import multiprocessing
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# The old limit of two workers existed because SQLite serialises writes and
# more processes only contended over one file. MySQL has no such ceiling, so
# this now follows the usual (2 x cores) + 1 -- capped, because each worker
# holds its own connection and the server's max_connections is finite.
workers = int(os.environ.get("WEB_CONCURRENCY",
                             min(9, multiprocessing.cpu_count() * 2 + 1)))
threads = int(os.environ.get("WEB_THREADS", 4))
worker_class = "gthread"

# The AI endpoints run scikit-learn fits; the default 30s timeout is too tight.
timeout = int(os.environ.get("WEB_TIMEOUT", 90))
graceful_timeout = 30
keepalive = 5

# Recycle workers periodically so a slow leak cannot accumulate indefinitely.
max_requests = 1000
max_requests_jitter = 100

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info").lower()

# Fail fast at boot rather than on the first request.
preload_app = True
