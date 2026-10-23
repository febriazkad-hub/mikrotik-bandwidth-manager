# ==========================================
# MikroTik Bandwidth Manager - Multi-Stage Dockerfile
# Optimized for minimal footprint (<55MB) and non-root security
# ==========================================

FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final Runtime Stage
FROM python:3.11-slim AS runner

LABEL org.opencontainers.image.title="MikroTik Bandwidth Manager"
LABEL org.opencontainers.image.description="Automated QoS Bandwidth Limiter, Telemetry & Diagnostics for MikroTik RouterOS"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Install curl for healthcheck & create unprivileged app user
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -u 10001 -m -s /bin/sh appuser \
    && mkdir -p /app/data && chown -R appuser:appuser /app

# Copy python dependencies from builder
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

# Copy application source & static assets
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser data/ ./data/
COPY --chown=appuser:appuser static/ ./static/

USER appuser

EXPOSE 5678

VOLUME ["/app/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5678/api/health || exit 1

CMD ["python", "-m", "app.main"]
