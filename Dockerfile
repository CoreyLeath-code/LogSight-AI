# â”€â”€ Stage 1: build â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build tools
RUN pip install --upgrade pip build

# Copy project files required for the build
COPY pyproject.toml requirements.txt ./
COPY logsight/ logsight/

# Build the wheel
RUN python -m build --wheel --outdir /dist

# â”€â”€ Stage 2: runtime â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
FROM python:3.11-slim AS runtime

LABEL maintainer="Trojan3877" \
      description="LogSight-AI: AI-powered log analysis and anomaly detection" \
      version="0.1.0"

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash logsight

WORKDIR /app

# Install the built wheel from the builder stage
COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# Drop privileges
USER logsight

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 CMD ["logsight", "health"]

ENTRYPOINT ["logsight"]
CMD ["--help"]
