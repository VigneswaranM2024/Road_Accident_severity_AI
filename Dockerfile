# Build Stage
FROM python:3.10-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-prod.txt .
# Build wheels for dependencies
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements-prod.txt

# Final Stage
FROM python:3.10-slim

WORKDIR /app

# Install runtime dependencies and create non-root user
RUN apt-get update && apt-get install -y \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system appuser && adduser --system --group appuser

COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements-prod.txt .

# Install pre-built wheels
RUN pip install --no-cache /wheels/*

# Copy application files with appropriate ownership
COPY --chown=appuser:appuser . .

# Ensure necessary directories are writable by the non-root user
RUN mkdir -p data model \
    && chown -R appuser:appuser data model \
    && chmod -R 755 data model

# Switch to non-root user
USER appuser

EXPOSE 5000

# Docker Healthcheck using native Python (no need for curl)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/')" || exit 1

# Start gunicorn with eventlet for SocketIO
CMD ["gunicorn", "-k", "eventlet", "-w", "1", "-b", "0.0.0.0:5000", "app:app"]
