# syntax=docker/dockerfile:1
#
# Fixes over the previous image:
#   * create_app() built every agent's model at startup, so without live API
#     keys the container exited with LLMNotConfigured before serving /health.
#     CI never saw it: the image was built there and never run. Models are now
#     built on first use and /ready reports what is missing.
#   * single stage: gcc, postgresql-client and pip's cache shipped in the
#     runtime image (1.37 GB); two stages now
#   * uid 1000; now a system user with uid 10001
#   * `uvicorn src.server.server:create_app` without --factory: uvicorn guessed
#     that it was a factory and warned on every start
#   * curl installed only for the HEALTHCHECK; the probe is Python now
#   * no .dockerignore, so `COPY . .` took .git, the local virtualenv and any
#     developer .env into a layer

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    # Production refuses to start while API_KEY is the placeholder.
    ENVIRONMENT=production \
    HOST=0.0.0.0 \
    PORT=8000 \
    LOG_LEVEL=info

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --create-home app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=app:app . .

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"]

# exec form: uvicorn is PID 1 and receives SIGTERM directly.
CMD ["uvicorn", "src.server.server:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--timeout-graceful-shutdown", "20", "--no-server-header"]
