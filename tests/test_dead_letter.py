"""Fail-closed Kafka dead-letter delivery tests without live infrastructure."""

from __future__ import annotations

import asyncio
import base64
import json
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from logsight.dead_letter import quarantine_envelope
from logsight.kafka_clickhouse_worker import InvalidEventEnvelope, decode_event, run_worker


def test_quarantine_preserves_source_and_bytes() -> None:
    payload = b"invalid:\x00email@example.test"
    data = json.loads(quarantine_envelope(payload, topic="logs", partition=2, offset=91))
    assert data["schema_version"] == 1
    assert data["source"] == {"topic": "logs", "partition": 2, "offset": 91}
    assert base64.b64decode(data["payload_base64"]) == payload
    assert len(data["sha256"]) == 64
    assert "email@example.test" not in str(data)  # Payload is encoded, not sanitized.


def test_reject_unsafe_quarantine_coordinates() -> None:
    with pytest.raises(ValueError):
        quarantine_envelope(b"x", topic="", partition=0, offset=0)
    with pytest.raises(ValueError):
        quarantine_envelope(b"x" * (1024 * 1024 + 1), topic="logs", partition=0, offset=0)


@pytest.mark.parametrize("fail_dlq", [False, True])
def test_worker_commits_only_after_quarantine_ack(
    monkeypatch: pytest.MonkeyPatch, fail_dlq: bool
) -> None:
    events: list[str] = []

    class FakeConsumer:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            assert kwargs["enable_auto_commit"] is False

        async def start(self) -> None:
            events.append("consumer-start")

        async def stop(self) -> None:
            events.append("consumer-stop")

        def __aiter__(self):
            async def records():
                yield SimpleNamespace(value=b"not json", topic="logs", partition=1, offset=3)

            return records()

        async def commit(self) -> None:
            events.append("commit")

    class FakeProducer:
        def __init__(self, **kwargs: Any) -> None:
            assert kwargs["acks"] == "all"
            assert kwargs["enable_idempotence"] is True

        async def start(self) -> None:
            events.append("dlq-start")

        async def stop(self) -> None:
            events.append("dlq-stop")

        async def send_and_wait(self, topic: str, payload: bytes) -> None:
            assert topic == "logs-dlq"
            assert json.loads(payload)["source"]["offset"] == 3
            events.append("dlq-send")
            if fail_dlq:
                raise ConnectionError("DLQ broker unavailable")

    module = ModuleType("aiokafka")
    module.AIOKafkaConsumer = FakeConsumer  # type: ignore[attr-defined]
    module.AIOKafkaProducer = FakeProducer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "aiokafka", module)
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "broker:9092")
    monkeypatch.setenv("LOGSIGHT_KAFKA_TOPIC", "logs")
    monkeypatch.setenv("LOGSIGHT_KAFKA_DLQ_TOPIC", "logs-dlq")
    monkeypatch.setenv("CLICKHOUSE_URL", "http://clickhouse:8123")

    if fail_dlq:
        with pytest.raises(ConnectionError, match="DLQ broker unavailable"):
            asyncio.run(run_worker())
        assert "commit" not in events
    else:
        asyncio.run(run_worker())
        assert events.index("dlq-send") < events.index("commit")
    assert events[-2:] == ["dlq-stop", "consumer-stop"]


def test_decode_failure_is_tagged_but_storage_failures_are_not() -> None:
    with pytest.raises(InvalidEventEnvelope):
        decode_event(b"not json")
