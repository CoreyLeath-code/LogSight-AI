"""Offline verification of dead-letter envelopes without payload exposure."""

from __future__ import annotations

import base64
import json
from typing import Any

import pytest

from logsight.dead_letter import inspect_quarantine, quarantine_envelope


def sample() -> dict[str, Any]:
    payload = b"password=private-data contact=person@example.test"
    return json.loads(quarantine_envelope(payload, topic="logs", partition=2, offset=19))


def test_valid_envelope_inspection_never_returns_sensitive_bytes() -> None:
    original = sample()
    summary = inspect_quarantine(json.dumps(original).encode())
    assert summary["verified"] is True
    assert summary["source"] == {"topic": "logs", "partition": 2, "offset": 19}
    assert summary["payload_bytes"] > 0
    assert "payload_base64" not in summary
    assert "private-data" not in repr(summary)
    assert "person@example.test" not in repr(summary)


@pytest.mark.parametrize("change", ["checksum", "payload", "version", "offset", "topic"])
def test_tampered_envelopes_fail_closed(change: str) -> None:
    value = sample()
    if change == "checksum":
        value["sha256"] = "0" * 64
    elif change == "payload":
        value["payload_base64"] = base64.b64encode(b"changed").decode()
    elif change == "version":
        value["schema_version"] = 2
    elif change == "offset":
        value["source"]["offset"] = -1
    else:
        value["source"]["topic"] = ""
    with pytest.raises(ValueError):
        inspect_quarantine(json.dumps(value).encode())


def test_malformed_and_oversized_envelopes_fail_closed() -> None:
    with pytest.raises(ValueError):
        inspect_quarantine(b"not json")
    with pytest.raises(ValueError):
        inspect_quarantine(b"x" * (2 * 1024 * 1024 + 1))
    original = sample()
    original["payload_base64"] = "???"
    with pytest.raises(ValueError):
        inspect_quarantine(json.dumps(original).encode())
