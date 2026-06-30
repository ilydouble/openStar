# syntax=docker/dockerfile:1.7

# ─────────────────────────────────────────────────
# Stage 1: builder
# ─────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifests first so source-only changes reuse dependency layers.
COPY pyproject.toml requirements.txt ./

# Runtime dependencies depend only on requirements.txt. Keep this before
# copying source so normal code changes can reuse the expensive dependency layer.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install/deps -r requirements.txt

# Install build tooling after runtime dependencies so dependency resolution
# cannot remove packages that Hatch needs from the global build environment.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install hatch

COPY src/ ./src/

# Build wheel
RUN hatch build -t wheel
RUN pip install --prefix=/install/app --no-cache-dir --no-deps dist/*.whl

# ─────────────────────────────────────────────────
# Stage 2: runtime
# ─────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Non-root user for security
RUN groupadd -r icore && useradd -r -g icore -m -d /app icore

WORKDIR /app

# Runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash curl ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency and application installs as separate cacheable layers.
COPY --from=builder /install/deps /usr/local
COPY --from=builder /install/app /usr/local

# Alembic migration files are runtime artifacts for database upgrades.
COPY alembic.ini ./alembic.ini
COPY alembic/ ./alembic/

# Agent tool workspace
RUN mkdir -p /tmp/icore-agent-workspace && chown icore:icore /tmp/icore-agent-workspace

USER icore

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f "http://localhost:${API_PORT:-11001}/health" || exit 1

EXPOSE 11001

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    API_HOST=0.0.0.0 \
    API_PORT=11001

CMD ["sh", "-c", "alembic upgrade head && uvicorn icore_agent.main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-11001}"]
