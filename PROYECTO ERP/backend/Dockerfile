# syntax=docker/dockerfile:1.7
# Backend Flask + SocketIO (gevent) + Postgres - production image
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps: build tools (gevent, psycopg), libpq client, curl para healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps - aprovechamos cache de Docker copiando solo pyproject.toml primero
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install -e ".[exports,analytics,ocr]"

# Copy application code
COPY app ./app
COPY migrations ./migrations
COPY wsgi.py ./

# Crear directorios para certs AFIP y uploads OCR (montables como volumes en prod)
RUN mkdir -p /app/instance/afip_certs /app/instance/ocr_uploads

# Production gunicorn con gevent worker (necesario para Flask-SocketIO)
ENV PORT=8080
EXPOSE 8080

# Healthcheck contra el endpoint /healthz que ya existe en app/__init__.py
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:${PORT}/healthz || exit 1

# Aplica migraciones Alembic y arranca gunicorn
# - 1 worker gevent: SocketIO requiere sticky connections; horizontal scaling = mas instancias, no mas workers
# - timeout 120: requests lentas (export Excel, OCR) no deben matarse
CMD ["sh", "-c", "flask db upgrade && gunicorn --bind 0.0.0.0:${PORT} --worker-class gevent --workers 1 --timeout 120 --access-logfile - --error-logfile - wsgi:app"]
