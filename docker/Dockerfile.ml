# ML / MLOps Production Dockerfile
# Supports: PyTorch, TensorFlow, scikit-learn, FastAPI model serving
# CUDA support: use nvidia/cuda base for GPU inference

# ─── Stage 1: Base with system deps ───────────────────────────────────
FROM python:3.11-slim AS base
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ─── Stage 2: Dependencies ────────────────────────────────────────────
FROM base AS deps
COPY requirements.txt requirements-inference.txt* ./
RUN pip install --user --no-cache-dir -r requirements.txt \
    && if [ -f requirements-inference.txt ]; then pip install --user -r requirements-inference.txt; fi

# ─── Stage 3: Production ──────────────────────────────────────────────
FROM base AS runner

ENV PATH="/home/mluser/.local/bin:$PATH" \
    PORT=8080 \
    MODEL_PATH=/app/models \
    LOG_LEVEL=info

# Security: non-root user
RUN groupadd --system --gid 1001 mlgroup \
    && useradd --system --uid 1001 --gid mlgroup mluser \
    && mkdir -p /app/models /app/artifacts /tmp/model-cache \
    && chown -R mluser:mlgroup /app /tmp/model-cache

COPY --from=deps --chown=mluser:mlgroup /root/.local /home/mluser/.local
COPY --chown=mluser:mlgroup . .

LABEL org.opencontainers.image.title="ML Model Service" \
      org.opencontainers.image.vendor="Your Org" \
      org.opencontainers.image.licenses="Apache-2.0"

USER mluser

EXPOSE 8080

VOLUME ["/app/models"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -sf http://localhost:8080/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--log-level", "info"]
