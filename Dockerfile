FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DATA_DIR=/app/data \
    DATABASE_PATH=/app/data/gst_intelligence.db \
    UPLOAD_DIR=/app/data/uploads \
    OUTPUT_DIR=/app/data/output \
    BACKUP_DIR=/app/data/backups \
    APP_ENV=production

WORKDIR /app

# Install security certificates and curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies from backend/requirements.txt
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root application user and data directories
RUN useradd -u 1000 -m -s /bin/bash appuser && \
    mkdir -p /app/data/uploads /app/data/output /app/data/backups && \
    chown -R appuser:appuser /app

# Copy backend application source code into /app
COPY backend/ .
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/health || exit 1

CMD ["sh", "-c", "exec gunicorn -w 2 --threads 4 -b 0.0.0.0:${PORT:-8000} --timeout 120 wsgi:application"]
