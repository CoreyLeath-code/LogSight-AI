# Stage 1: build
FROM python:3.11-slim AS builder

WORKDIR /app
RUN pip install --upgrade pip build
COPY pyproject.toml requirements.txt README.md ./
COPY logsight/ logsight/
RUN python -m build --wheel --outdir /dist

# Stage 2: runtime
FROM python:3.11-slim AS runtime

ARG INSTALL_EXTRAS=""
LABEL maintainer="CoreyLeath-code" \
      description="LogSight-AI: production log analysis and observability" \
      version="0.2.0"

RUN useradd --create-home --shell /bin/bash logsight
WORKDIR /app
COPY --from=builder /dist/*.whl /tmp/
RUN WHEEL=$(ls /tmp/*.whl) && if [ -n "$INSTALL_EXTRAS" ]; then pip install --no-cache-dir "$WHEEL[$INSTALL_EXTRAS]"; else pip install --no-cache-dir "$WHEEL"; fi && rm /tmp/*.whl

USER logsight
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 CMD ["logsight", "health"]
ENTRYPOINT ["logsight"]
CMD ["--help"]
