"""Optional Celery distributed embedding worker with bounded task contracts."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from .embeddings import EmbeddedLog, build_embedding_worker
from .enterprise import EnrichedLog

_TASK_NAME = "logsight.embed_events"


@dataclass(frozen=True, slots=True)
class InferenceRequest:
    """JSON-safe, bounded event identity and text supplied to a worker."""

    fingerprint: str
    message: str
    trace_id: str | None = None
    span_id: str | None = None

    @classmethod
    def from_event(cls, event: EnrichedLog, *, max_message_chars: int) -> InferenceRequest:
        if not event.fingerprint:
            raise ValueError("distributed inference requires an event fingerprint")
        if not event.message or len(event.message) > max_message_chars:
            raise ValueError("event message must be non-empty and within the configured limit")
        return cls(
            fingerprint=event.fingerprint,
            message=event.message,
            trace_id=event.trace_id,
            span_id=event.span_id,
        )

    @classmethod
    def from_payload(
        cls, payload: dict[str, object], *, max_message_chars: int
    ) -> InferenceRequest:
        expected = {"fingerprint", "message", "trace_id", "span_id"}
        if set(payload) != expected:
            raise ValueError("distributed inference payload has an unexpected shape")
        fingerprint = payload["fingerprint"]
        message = payload["message"]
        trace_id = payload["trace_id"]
        span_id = payload["span_id"]
        if not isinstance(fingerprint, str) or not isinstance(message, str):
            raise ValueError("distributed inference payload requires string identity and message")
        if trace_id is not None and not isinstance(trace_id, str):
            raise ValueError("trace_id must be a string or null")
        if span_id is not None and not isinstance(span_id, str):
            raise ValueError("span_id must be a string or null")
        return cls(
            fingerprint=fingerprint,
            message=message,
            trace_id=trace_id,
            span_id=span_id,
        ).validated(max_message_chars=max_message_chars)

    def validated(self, *, max_message_chars: int) -> InferenceRequest:
        if not self.fingerprint:
            raise ValueError("distributed inference requires an event fingerprint")
        if not self.message or len(self.message) > max_message_chars:
            raise ValueError("event message must be non-empty and within the configured limit")
        return self

    def to_payload(self) -> dict[str, str | None]:
        return asdict(self)

    def to_event(self) -> EnrichedLog:
        return EnrichedLog(
            raw="",
            message=self.message,
            level="UNKNOWN",
            timestamp="",
            trace_id=self.trace_id,
            span_id=self.span_id,
            fingerprint=self.fingerprint,
        )


class TaskSender(Protocol):
    """Minimal Celery app contract used by the enqueue adapter."""

    def send_task(self, name: str, args: list[object], *, queue: str) -> Any:
        """Submit a named task."""


class CeleryInferenceDispatcher:
    """Serialize bounded embedding batches to a configured Celery queue."""

    def __init__(
        self,
        app: TaskSender,
        *,
        queue: str = "inference",
        max_batch_size: int = 64,
        max_message_chars: int = 16_000,
    ) -> None:
        if max_batch_size < 1 or max_message_chars < 1:
            raise ValueError("distributed worker limits must be positive")
        if not queue:
            raise ValueError("queue must not be empty")
        self.app = app
        self.queue = queue
        self.max_batch_size = max_batch_size
        self.max_message_chars = max_message_chars

    def submit_embeddings(self, events: Sequence[EnrichedLog]) -> str:
        """Queue one bounded JSON-only embedding task and return its task ID."""

        if not 1 <= len(events) <= self.max_batch_size:
            raise ValueError(f"batch size must be between 1 and {self.max_batch_size}")
        payload = [
            InferenceRequest.from_event(
                event, max_message_chars=self.max_message_chars
            ).to_payload()
            for event in events
        ]
        result = self.app.send_task(_TASK_NAME, [payload], queue=self.queue)
        task_id = getattr(result, "id", None)
        if not isinstance(task_id, str) or not task_id:
            raise RuntimeError("Celery did not return a task ID")
        return task_id


def _settings() -> tuple[str, str, int, int, int]:
    broker_url = os.getenv("LOGSIGHT_CELERY_BROKER_URL") or os.getenv("LOGSIGHT_REDIS_URL")
    if not broker_url:
        raise ValueError("LOGSIGHT_CELERY_BROKER_URL must be configured")
    result_backend = os.getenv("LOGSIGHT_CELERY_RESULT_BACKEND", broker_url)
    max_batch_size = int(os.getenv("LOGSIGHT_CELERY_MAX_BATCH_SIZE", "64"))
    max_message_chars = int(os.getenv("LOGSIGHT_CELERY_MAX_MESSAGE_CHARS", "16000"))
    task_time_limit = int(os.getenv("LOGSIGHT_CELERY_TASK_TIME_LIMIT_SECONDS", "120"))
    if min(max_batch_size, max_message_chars, task_time_limit) < 1:
        raise ValueError("Celery worker limits must be positive")
    return broker_url, result_backend, max_batch_size, max_message_chars, task_time_limit


def create_celery_app() -> Any:
    """Create the explicitly configured Celery app and register inference tasks."""

    broker_url, result_backend, max_batch_size, max_message_chars, task_time_limit = _settings()
    try:
        from celery import Celery
    except ImportError as exc:
        raise RuntimeError("Install the workers extra to enable Celery inference workers") from exc

    app = Celery("logsight", broker=broker_url, backend=result_backend)
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        task_default_queue="inference",
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_soft_time_limit=max(1, task_time_limit - 10),
        task_time_limit=task_time_limit,
        result_expires=3600,
    )

    @app.task(name=_TASK_NAME)
    def embed_events(payloads: list[dict[str, object]]) -> list[dict[str, object]]:
        if not 1 <= len(payloads) <= max_batch_size:
            raise ValueError(f"batch size must be between 1 and {max_batch_size}")
        requests = [
            InferenceRequest.from_payload(payload, max_message_chars=max_message_chars)
            for payload in payloads
        ]
        results: list[EmbeddedLog] = build_embedding_worker(max_batch_size=max_batch_size).embed(
            [request.to_event() for request in requests]
        )
        return [asdict(result) for result in results]

    return app


def build_celery_dispatcher() -> CeleryInferenceDispatcher | None:
    """Build an enqueue adapter only when API dispatch is explicitly enabled."""

    if os.getenv("LOGSIGHT_CELERY_DISPATCH_ENABLED") != "true":
        return None
    _, _, max_batch_size, max_message_chars, _ = _settings()
    return CeleryInferenceDispatcher(
        create_celery_app(),
        queue=os.getenv("LOGSIGHT_CELERY_QUEUE", "inference"),
        max_batch_size=max_batch_size,
        max_message_chars=max_message_chars,
    )


celery_app = create_celery_app() if os.getenv("LOGSIGHT_CELERY_ENABLED") == "true" else None
