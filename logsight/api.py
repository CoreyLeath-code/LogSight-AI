"""Optional FastAPI gateway for live ingestion and analysis."""

from __future__ import annotations

import os
from collections import deque
from dataclasses import asdict
from typing import Any

from .enterprise import EnrichedLog, enrich, extract_template, score_event
from .parser import parse_line

try:
    from fastapi import FastAPI, HTTPException, Response
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover - base installation does not need the API
    FastAPI = None  # type: ignore[assignment,misc]
    HTTPException = RuntimeError  # type: ignore[misc,assignment]
    Response = object  # type: ignore[assignment,misc]
    BaseModel = object  # type: ignore[assignment,misc]

    def Field(**_: Any) -> Any:  # type: ignore[misc]
        return None


class LogPayload(BaseModel):  # type: ignore[misc]
    line: str = Field(min_length=1)
    service: str = "unknown"
    source: str = "api"
    host: str = "unknown"


class BatchPayload(BaseModel):  # type: ignore[misc]
    logs: list[LogPayload] = Field(min_length=1, max_length=10_000)


_recent: deque[EnrichedLog] = deque(maxlen=int(os.getenv("LOGSIGHT_WINDOW", "500")))
_metrics = {"logsight_ingested_total": 0, "logsight_anomalies_total": 0}


def _process(item: LogPayload) -> tuple[EnrichedLog, Any]:
    event = enrich(parse_line(item.line), service=item.service, source=item.source, host=item.host)
    event.template = extract_template(event.message)
    _recent.append(event)
    result = score_event(event, list(_recent))
    _metrics["logsight_ingested_total"] += 1
    if result.score >= 0.5:
        _metrics["logsight_anomalies_total"] += 1
    return event, result


def create_app() -> Any:
    if FastAPI is None:
        raise RuntimeError("Install the 'api' extra to run the LogSight API")
    app = FastAPI(title="LogSight-AI Enterprise API", version="0.2.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "logsight-api"}

    @app.get("/metrics")
    async def metrics() -> Response:
        body = "\n".join(f"{name} {value}" for name, value in _metrics.items()) + "\n"
        return Response(content=body, media_type="text/plain; version=0.0.4")

    @app.post("/v1/logs")
    async def ingest(payload: LogPayload) -> dict[str, Any]:
        event, result = _process(payload)
        return {"event": event.to_dict(), "anomaly": asdict(result)}

    @app.post("/v1/logs/batch")
    async def ingest_batch(payload: BatchPayload) -> dict[str, Any]:
        results = []
        for item in payload.logs:
            event, result = _process(item)
            results.append({"event": event.to_dict(), "anomaly": asdict(result)})
        return {"count": len(results), "results": results}

    @app.get("/v1/logs/recent")
    async def recent(limit: int = 100) -> dict[str, Any]:
        if not 1 <= limit <= 500:
            raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
        return {"count": min(limit, len(_recent)), "events": [e.to_dict() for e in list(_recent)[-limit:]]}

    return app


app = create_app() if FastAPI is not None else None
