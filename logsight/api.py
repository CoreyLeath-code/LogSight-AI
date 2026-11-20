"""Optional FastAPI gateway for live ingestion and analysis."""

from __future__ import annotations

import asyncio
import os
import secrets
import uuid
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any

from .distributed import CeleryInferenceDispatcher, build_celery_dispatcher
from .enterprise import EnrichedLog, enrich, score_event
from .observability import configure_tracing, correlate_with_active_span, span
from .parser import parse_line
from .redaction import redact_log_line
from .redis_control import RedisAdmissionController, build_redis_controller
from .request_limits import IngestionBodyLimit
from .streaming import KafkaStream
from .templates import TemplateParser, build_template_parser

try:
    from fastapi import FastAPI, HTTPException, Request, Response
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover - base installation does not need the API
    FastAPI = None  # type: ignore[assignment,misc]
    HTTPException = RuntimeError  # type: ignore[misc,assignment]
    Response = object  # type: ignore[assignment,misc]
    Request = object  # type: ignore[assignment,misc]
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
_template_parser: TemplateParser = build_template_parser()
_admission_controller: RedisAdmissionController | None = build_redis_controller()
_inference_dispatcher: CeleryInferenceDispatcher | None = build_celery_dispatcher()


async def _process(
    item: LogPayload, *, kafka_stream: KafkaStream | None = None, event_id: str | None = None
) -> tuple[EnrichedLog, Any, str | None]:
    with span("logsight.ingest", service=item.service, source=item.source) as _:
        event = correlate_with_active_span(
            enrich(
                parse_line(redact_log_line(item.line)),
                service=item.service,
                source=item.source,
                host=item.host,
            )
        )
        if event_id is not None:
            event.event_id = event_id
        if _admission_controller is not None:
            decision = await _admission_controller.admit(event, item.service)
            if not decision.accepted:
                status_code = 409 if decision.reason == "duplicate" else 429
                raise HTTPException(status_code=status_code, detail=decision.reason)
        event.template = _template_parser.parse(event.message)
        if kafka_stream is not None:
            try:
                await kafka_stream.publish(event)
            except Exception as exc:
                # A timeout can mean the broker accepted the event; retries
                # require downstream deduplication. Never expose raw logs.
                raise HTTPException(
                    status_code=503,
                    detail="Broker acknowledgement not confirmed; retry may duplicate event",
                ) from exc
        _recent.append(event)
        result = score_event(event, list(_recent))
        _metrics["logsight_ingested_total"] += 1
        if result.score >= 0.5:
            _metrics["logsight_anomalies_total"] += 1
        task_id = (
            await asyncio.to_thread(_inference_dispatcher.submit_embeddings, [event])
            if _inference_dispatcher is not None
            else None
        )
        return event, result, task_id


def create_app() -> Any:
    if FastAPI is None:
        raise RuntimeError("Install the 'api' extra to run the LogSight API")
    if os.getenv("LOGSIGHT_OTEL_ENABLED", "").lower() == "true":
        configure_tracing("logsight-api")
    auth_mode = os.getenv("LOGSIGHT_API_AUTH_MODE", "disabled").strip().lower()
    if auth_mode not in {"disabled", "token"}:
        raise RuntimeError("LOGSIGHT_API_AUTH_MODE must be disabled or token")
    api_token = os.getenv("LOGSIGHT_API_TOKEN", "")
    if auth_mode == "token" and len(api_token) < 32:
        raise RuntimeError("LOGSIGHT_API_TOKEN must contain at least 32 characters in token mode")

    max_body_bytes_raw = os.getenv("LOGSIGHT_API_MAX_BODY_BYTES", "1048576")
    try:
        max_body_bytes = int(max_body_bytes_raw)
    except ValueError as exc:
        raise RuntimeError("LOGSIGHT_API_MAX_BODY_BYTES must be a positive integer") from exc
    if not 1 <= max_body_bytes <= 16 * 1024 * 1024:
        raise RuntimeError("LOGSIGHT_API_MAX_BODY_BYTES must be between 1 and 16777216")

    kafka_mode = os.getenv("LOGSIGHT_API_KAFKA_ENABLED", "false").strip().lower()
    if kafka_mode not in {"true", "false"}:
        raise RuntimeError("LOGSIGHT_API_KAFKA_ENABLED must be true or false")
    kafka_stream = (
        KafkaStream(
            os.getenv("KAFKA_BOOTSTRAP_SERVERS", ""),
            os.getenv("LOGSIGHT_KAFKA_TOPIC", ""),
        )
        if kafka_mode == "true"
        else None
    )
    # Redis dedup currently commits before a broker ack. Combining these modes
    # could reject retries after a failed or ambiguous broker send.
    if kafka_stream is not None and _admission_controller is not None:
        raise RuntimeError("Disable Redis admission while API Kafka mode is experimental")

    @asynccontextmanager
    async def lifespan(application: Any) -> AsyncIterator[None]:
        application.state.kafka_stream = kafka_stream
        if kafka_stream is not None:
            await kafka_stream.start()
        try:
            yield
        finally:
            if kafka_stream is not None:
                await kafka_stream.stop()

    app = FastAPI(title="LogSight-AI Enterprise API", version="0.2.0", lifespan=lifespan)
    app.add_middleware(IngestionBodyLimit, max_body_bytes=max_body_bytes)

    @app.middleware("http")
    async def require_api_token(request: Request, call_next: Any) -> Response:
        # Health and readiness probes must not require application bearer tokens.
        if auth_mode == "token" and request.url.path not in {"/health", "/ready"}:
            authorization = request.headers.get("authorization", "")
            scheme, separator, candidate = authorization.partition(" ")
            if (
                not separator
                or scheme.lower() != "bearer"
                or not secrets.compare_digest(candidate.encode(), api_token.encode())
            ):
                return Response(
                    content='{"detail":"Unauthorized"}',
                    status_code=401,
                    media_type="application/json",
                    headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
                )
        return await call_next(request)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "logsight-api"}

    @app.get("/metrics")
    async def metrics() -> Response:
        body = "\n".join(f"{name} {value}" for name, value in _metrics.items()) + "\n"
        return Response(content=body, media_type="text/plain; version=0.0.4")

    @app.post("/v1/logs")
    async def ingest(payload: LogPayload, request: Request) -> dict[str, Any]:
        # Optional request identity for retries; not a deduplication guarantee.
        key = request.headers.get("idempotency-key")
        event_id = None
        if key is not None:
            try:
                parsed_key = uuid.UUID(key)
            except (ValueError, AttributeError) as exc:
                raise HTTPException(
                    status_code=400, detail="Idempotency-Key must be a canonical UUIDv4"
                ) from exc
            if parsed_key.version != 4 or str(parsed_key) != key:
                raise HTTPException(
                    status_code=400, detail="Idempotency-Key must be a canonical UUIDv4"
                )
            event_id = key
        event, result, task_id = await _process(
            payload, kafka_stream=request.app.state.kafka_stream, event_id=event_id
        )
        response: dict[str, Any] = {"event": event.to_dict(), "anomaly": asdict(result)}
        if task_id is not None:
            response["inference_task_id"] = task_id
        return response

    @app.post("/v1/logs/batch")
    async def ingest_batch(payload: BatchPayload, request: Request) -> dict[str, Any]:
        results = []
        for item in payload.logs:
            event, result, task_id = await _process(
                item, kafka_stream=request.app.state.kafka_stream
            )
            response: dict[str, Any] = {"event": event.to_dict(), "anomaly": asdict(result)}
            if task_id is not None:
                response["inference_task_id"] = task_id
            results.append(response)
        return {"count": len(results), "results": results}

    @app.get("/v1/logs/recent")
    async def recent(limit: int = 100) -> dict[str, Any]:
        if not 1 <= limit <= 500:
            raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
        return {
            "count": min(limit, len(_recent)),
            "events": [e.to_dict() for e in list(_recent)[-limit:]],
        }

    return app


app = create_app() if FastAPI is not None else None
