"""Failure and delivery contract tests for the experimental ClickHouse sink."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from logsight.kafka_clickhouse_worker import decode_event, persist_message


def sample_event() -> dict[str, Any]:
    return {
        "timestamp": "2026-11-19T13:14:15.123456+00:00",
        "level": "ERROR",
        "service": "payments",
        "source": "api",
        "host": "worker-1",
        "message": "ERROR password=secret123 user=user@example.org",
        "raw": "ERROR password=secret123 user=user@example.org",
        "fingerprint": "abc123",
        "trace_id": None,
        "span_id": None,
        "template": "ERROR <*>",
        "attributes": {"note": "api_key=hidden"},
    }


def encoded(event: dict[str, Any] | None = None) -> bytes:
    return json.dumps(event if event is not None else sample_event()).encode()


def test_schema_matches_clickhouse_insert_contract_and_redacts() -> None:
    row = decode_event(encoded())
    assert set(row) == {
        "timestamp", "level", "service", "source", "host", "message",
        "raw", "fingerprint", "trace_id", "span_id", "template", "attributes",
    }
    assert row["timestamp"] == "2026-11-19 13:14:15.123"
    assert "secret123" not in row["raw"]
    assert "user@example.org" not in row["message"]
    assert "hidden" not in row["attributes"]
    assert row["trace_id"] is None


@pytest.mark.parametrize(
    "payload",
    [
        b"not json",
        b"[]",
        b"{}",
        b"x" * (1024 * 1024 + 1),
        encoded({**sample_event(), "timestamp": "not-a-timestamp"}),
        encoded({**sample_event(), "timestamp": "2026-11-19T13:14:15"}),
        encoded({**sample_event(), "attributes": {"size": 123}}),
        encoded({**sample_event(), "raw": None}),
    ],
)
def test_invalid_envelopes_fail_closed(payload: bytes) -> None:
    with pytest.raises(ValueError):
        decode_event(payload)


def test_storage_failure_does_not_advance_consumer_offset() -> None:
    class Consumer:
        commits = 0

        async def commit(self) -> None:
            self.commits += 1

    class Store:
        def __init__(self, fail: bool) -> None:
            self.fail = fail
            self.events: list[dict[str, Any]] = []

        def insert_events(self, events: list[dict[str, Any]]) -> None:
            if self.fail:
                raise ConnectionError("database unavailable")
            self.events.extend(events)

    async def exercise() -> None:
        consumer = Consumer()
        store = Store(fail=True)
        with pytest.raises(ConnectionError):
            await persist_message(encoded(), consumer, store)  # type: ignore[arg-type]
        assert consumer.commits == 0
        assert store.events == []

        store.fail = False
        await persist_message(encoded(), consumer, store)  # type: ignore[arg-type]
        assert consumer.commits == 1
        assert len(store.events) == 1

    asyncio.run(exercise())


def test_poison_record_does_not_advance_offset() -> None:
    class Consumer:
        committed = False

        async def commit(self) -> None:
            self.committed = True

    class Store:
        def insert_events(self, events: list[dict[str, Any]]) -> None:
            raise AssertionError("poison event should not be persisted")

    async def exercise() -> None:
        consumer = Consumer()
        with pytest.raises(ValueError):
            await persist_message(b"{}", consumer, Store())  # type: ignore[arg-type]
        assert consumer.committed is False

    asyncio.run(exercise())
