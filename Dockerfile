# =============================================================================
# Stage 1: Builder — Install dependencies in an isolated environment
# =============================================================================
FROM python:3.11-slim AS builder

# Set build-time environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only requirements first for Docker layer caching
COPY requirements.txt .

# Install Python dependencies into venv
RUN pip install --upgrade pip && \
    pip install -r requirements.txt


# =============================================================================
# Stage 2: Runtime — Lean production image
# =============================================================================
FROM python:3.11-slim AS runtime

# Labels for image metadata (OCI standard)
LABEL org.opencontainers.image.title="CHB Portal Backend"
LABEL org.opencontainers.image.description="Production FastAPI backend for the Clock Hour Basis Portal"
LABEL org.opencontainers.image.version="1.0.0"

# Runtime environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    # Application defaults (override via .env or Docker env)
    ENV=production \
    DEBUG=False

# Install only runtime system dependencies (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --no-create-home --shell /bin/false appuser

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Copy application source code
COPY --chown=appuser:appgroup . .

# Create uploads directory and set correct permissions
RUN mkdir -p /app/uploads && \
    chown -R appuser:appgroup /app/uploads && \
    chmod 755 /app/uploads

# Switch to non-root user
USER appuser

# Expose application port
EXPOSE 8000

# Health check — hits the root endpoint every 30s
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Production entrypoint:
# - 1 worker per CPU core (adjust via WORKERS env var)
# - Uvicorn with production settings
CMD ["sh", "-c", "uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers ${WORKERS:-4} \
    --loop uvloop \
    --http httptools \
    --proxy-headers \
    --forwarded-allow-ips='*' \
    --access-log \
    --log-level ${LOG_LEVEL:-info}"]
