FROM python:3.11-slim

LABEL maintainer="Antigravity Ecosystem"
LABEL description="MikroTik Smart Bandwidth Manager (Web GUI & Telegram Bot)"

WORKDIR /app

# Install curl for healthcheck & clean apt cache
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app/ ./app/
COPY static/ ./static/
COPY config.json .

# Create persistent data volume directory
RUN mkdir -p /app/data

EXPOSE 5678

VOLUME ["/app/data"]

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:5678/api/health || exit 1

CMD ["python", "-m", "app.main"]
