"""Enterprise observability primitives for LogSight-AI.

All integrations are optional. The existing local-first analyzer remains usable
without any infrastructure services installed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .parser import LogEntry


@dataclass(slots=True)
class EnrichedLog:
    """Normalized event suitable for streaming, storage, and correlation."""

    raw: str
    message: str
    level: str
    timestamp: str
    service: str = "unknown"
    source: str = "unknown"
    host: str = "unknown"
    trace_id: str | None = None
    span_id: str | None = None
    template: str | None = None
    fingerprint: str | None = None
    attributes: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"), sort_keys=True)


def enrich(
    entry: LogEntry,
    *,
    service: str = "unknown",
    source: str = "unknown",
    host: str = "unknown",
) -> EnrichedLog:
    """Convert the legacy parser record into a correlation-friendly event."""
    timestamp = entry.timestamp or datetime.now(timezone.utc)
    attributes = dict(entry.extra)
    trace_id = attributes.pop("trace_id", None) or attributes.pop("traceId", None)
    span_id = attributes.pop("span_id", None) or attributes.pop("spanId", None)
    fingerprint = hashlib.sha256(entry.message.encode("utf-8", "replace")).hexdigest()[:24]
    return EnrichedLog(
        raw=entry.raw,
        message=entry.message,
        level=entry.level.value,
        timestamp=timestamp.isoformat(),
        service=service,
        source=source,
        host=host,
        trace_id=trace_id,
        span_id=span_id,
        fingerprint=fingerprint,
        attributes=attributes,
    )


_TEMPLATE_TOKEN = re.compile(
    r"(?:\b\d+(?:\.\d+)?\b|\b[0-9a-fA-F]{8,}\b|\b\d{1,3}(?:\.\d{1,3}){3}\b)"
)


def extract_template(message: str) -> str:
    """Small dependency-free template extractor used as a safe baseline.

    Deployments can replace this implementation with Drain3 without changing
    the event contract.
    """
    return _TEMPLATE_TOKEN.sub("<*>", message)


def semantic_features(message: str) -> list[float]:
    """Return deterministic hashed n-gram features for lightweight detection.

    This is intentionally not presented as an embedding model. Sentence-
    Transformers/LogBERT can be plugged in behind the same interface later.
    """
    buckets = [0.0] * 32
    tokens = re.findall(r"\w+", message.lower())
    for token in tokens:
        digest = hashlib.sha256(token.encode()).digest()
        buckets[int.from_bytes(digest[:2], "big") % len(buckets)] += 1.0
    norm = sum(x * x for x in buckets) ** 0.5
    return [x / norm for x in buckets] if norm else buckets


@dataclass(slots=True)
class AnomalyScore:
    score: float
    reason: str
    detector: str
    fingerprint: str


def score_event(event: EnrichedLog, recent: list[EnrichedLog]) -> AnomalyScore:
    """Combine frequency and structural signals into a deterministic score."""
    template = event.template or extract_template(event.message)
    same = sum(
        1
        for item in recent
        if (item.template or extract_template(item.message)) == template
    )
    error_rate = sum(
        item.level in {"ERROR", "CRITICAL"} for item in recent
    ) / max(len(recent), 1)
    rarity = 1.0 / (same + 1)
    severity = 1.0 if event.level in {"ERROR", "CRITICAL"} else 0.0
    score = min(1.0, 0.45 * rarity + 0.35 * error_rate + 0.20 * severity)
    return AnomalyScore(
        score,
        f"template_frequency={same},window_error_rate={error_rate:.3f}",
        "hybrid",
        event.fingerprint or "",
    )


class WebhookNotifier:
    """Minimal outbound webhook notifier for Slack/PagerDuty/Discord adapters."""

    def __init__(self, url: str | None = None, timeout: float = 5.0) -> None:
        self.url = url or os.getenv("LOGSIGHT_WEBHOOK_URL")
        self.timeout = timeout

    def send(self, payload: dict[str, Any]) -> bool:
        if not self.url:
            return False
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # nosec B310
                return 200 <= response.status < 300
        except (OSError, ValueError):
            return False
