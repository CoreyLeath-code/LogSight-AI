# Deployment Guide

## Supported artifact

The supported artifact is the CLI container built by `Dockerfile`. Build and validate it with:

```bash
docker build --tag logsight-ai:local .
docker run --rm logsight-ai:local health
```

Mount logs read-only and invoke `analyze`:

```bash
docker run --rm -v "$PWD/logs:/logs:ro" logsight-ai:local analyze /logs/application.log
```

The process runs as an unprivileged user and does not require secrets or network access. Set CPU/memory limits in the target scheduler based on benchmark results. Logs may contain credentials or personal data; restrict access and retention accordingly.

## Production checklist

- CI, dependency, CodeQL, and secret scans are green.
- Image is built from the reviewed commit, scanned, signed, and stored immutably.
- Health command succeeds under configured resource limits.
- Log mounts are read-only; egress is denied unless explicitly required.
- Operational dashboards alert on failure rate, duration, memory, and disk pressure.
- Previous image digest is retained and rollback is rehearsed.

`app.py`, `demo.app.py`, and `agents/` are demonstrations, not supported deployment services.
