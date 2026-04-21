# ─────────────────────────────────────────────────
# Stage 1: builder
# ─────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

# Install hatch for build
RUN pip install --no-cache-dir hatch

# Copy project metadata first (layer cache)
COPY pyproject.toml ./
COPY src/ ./src/

# Build wheel
RUN hatch build -t wheel
RUN pip install --no-cache-dir dist/*.whl

# ─────────────────────────────────────────────────
# Stage 2: runtime
# ─────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Non-root user for security
RUN groupadd -r icore && useradd -r -g icore -m -d /app icore

WORKDIR /app

# Runtime system deps (bash required by sequential agent)
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash curl git \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Sequential agent workspace
RUN mkdir -p /tmp/icore-seq-workspace && chown icore:icore /tmp/icore-seq-workspace

USER icore

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

EXPOSE 8080

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

CMD ["uvicorn", "icore_agent.main:app", "--host", "0.0.0.0", "--port", "8080"]
