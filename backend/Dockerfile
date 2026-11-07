# ── Build a slim runtime image ────────────────────────────────────────────────
# Dependencies install in their own layer so code changes do not re-run pip.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production

WORKDIR /app

# scikit-learn needs a C++ runtime; build tools are not kept in the final image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user. There is no writable data directory to own now --
# the SQLite file it used to need is gone, which is one fewer volume to get
# wrong on a deploy.
RUN useradd --create-home --shell /usr/sbin/nologin resnav \
    && chown -R resnav:resnav /app
USER resnav

# No DATABASE_PATH any more: the database is a server, reached over the
# network, and its address arrives through DRA_MYSQL_* at run time.
ENV PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/api/health" || exit 1

CMD ["sh", "-c", "gunicorn --config gunicorn.conf.py wsgi:app"]
