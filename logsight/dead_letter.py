"""Fail-closed poison-record quarantine for the experimental Kafka sink.

This envelope retains the ORIGINAL bytes for operator-controlled replay.
It must be treated as sensitive and used only with a restricted DLQ topic.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import secrets
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


def inspect_quarantine(envelope: bytes) -> dict[str, Any]:
    """Verify an offline DLQ envelope without returning the raw payload.

    The returned metadata is safe to log only after an operator reviews source
    topic labels. No publishing, replay, or payload disclosure is performed.
    """
    if len(envelope) > 2 * 1024 * 1024:
        raise ValueError("DLQ envelope is too large")
    try:
        record = json.loads(envelope)
        if not isinstance(record, dict) or record.get("schema_version") != 1:
            raise ValueError("Unsupported DLQ envelope version")
        if record.get("reason") != "invalid_event_schema":
            raise ValueError("Unexpected quarantine reason")
        source = record["source"]
        if not isinstance(source, dict):
            raise ValueError("Invalid DLQ source")
        topic, partition, offset = source["topic"], source["partition"], source["offset"]
        if (
            not isinstance(topic, str)
            or not topic
            or type(partition) is not int
            or partition < 0
            or type(offset) is not int
            or offset < 0
        ):
            raise ValueError("Invalid DLQ source coordinates")
        digest = record["sha256"]
        data = record["payload_base64"]
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("Invalid DLQ checksum")
        if not isinstance(data, str):
            raise ValueError("Invalid DLQ payload encoding")
        payload = base64.b64decode(data, validate=True)
        if len(payload) > 1024 * 1024:
            raise ValueError("DLQ payload exceeds limit")
        if not secrets.compare_digest(hashlib.sha256(payload).hexdigest(), digest):
            raise ValueError("DLQ payload checksum mismatch")
    except (KeyError, TypeError, json.JSONDecodeError, binascii.Error, UnicodeEncodeError) as exc:
        raise ValueError("Invalid DLQ envelope") from exc
    return {
        "schema_version": 1,
        "reason": "invalid_event_schema",
        "source": {"topic": topic, "partition": partition, "offset": offset},
        "sha256": digest,
        "payload_bytes": len(payload),
        "verified": True,
    }
