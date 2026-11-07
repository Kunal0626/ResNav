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

# Run as a non-root user, and give it ownership of the writable data directory.
RUN useradd --create-home --shell /usr/sbin/nologin resnav \
    && mkdir -p /data \
    && chown -R resnav:resnav /app /data
USER resnav

ENV DATABASE_PATH=/data/resource_navigator.db \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/api/health" || exit 1

CMD ["sh", "-c", "gunicorn --config gunicorn.conf.py wsgi:app"]
