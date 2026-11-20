"""Fail-closed poison-record quarantine for the experimental Kafka sink.

This envelope retains the ORIGINAL bytes for operator-controlled replay.
It must be treated as sensitive and used only with a restricted DLQ topic.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any


def quarantine_envelope(payload: bytes, *, topic: str, partition: int, offset: int) -> bytes:
    """Capture a bounded broker record without exposing its body in diagnostics."""
    if len(payload) > 1024 * 1024:
        raise ValueError("Poison record exceeds the quarantine limit")
    if not topic or partition < 0 or offset < 0:
        raise ValueError("Source coordinates must be valid")
    record: dict[str, Any] = {
        "schema_version": 1,
        "reason": "invalid_event_schema",
        "source": {"topic": topic, "partition": partition, "offset": offset},
        "sha256": hashlib.sha256(payload).hexdigest(),
        "payload_base64": base64.b64encode(payload).decode("ascii"),
    }
    return json.dumps(record, separators=(",", ":"), sort_keys=True).encode("utf-8")
