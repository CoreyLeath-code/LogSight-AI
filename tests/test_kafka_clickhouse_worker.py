"""Failure and delivery contract tests for the experimental ClickHouse sink."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from collections import namedtuple
from types import ModuleType, SimpleNamespace
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
        "event_id": "b0b0c11b-0fc2-49ef-b8ee-a017a334da12",
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
        "timestamp",
        "level",
        "service",
        "source",
        "host",
        "message",
        "raw",
        "fingerprint",
        "event_id",
        "trace_id",
        "span_id",
        "template",
        "attributes",
    }
    assert row["timestamp"] == "2026-11-19 13:14:15.123"
    assert "secret123" not in row["raw"]
    assert "user@example.org" not in row["message"]
    assert "hidden" not in row["attributes"]
    assert row["trace_id"] is None
    assert row["event_id"] == "b0b0c11b-0fc2-49ef-b8ee-a017a334da12"


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
        encoded({key: value for key, value in sample_event().items() if key != "event_id"}),
        encoded({**sample_event(), "event_id": "not-a-uuid"}),
    ],
)
def test_invalid_envelopes_fail_closed(payload: bytes) -> None:
    with pytest.raises(ValueError):
        decode_event(payload)


def test_storage_failure_does_not_advance_consumer_offset(monkeypatch: pytest.MonkeyPatch) -> None:
    tp = namedtuple("TopicPartition", ["topic", "partition"])
    module = ModuleType("aiokafka")
    module.TopicPartition = tp  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "aiokafka", module)

    class Consumer:
        commits = 0

        async def commit(self, offsets: Any) -> None:
            assert offsets == {tp("logs", 2): 42}
            self.commits += 1

    class Store:
        def __init__(self, fail: bool) -> None:
            self.fail = fail
            self.events: list[dict[str, Any]] = []

        def insert_event_deduplicated(self, event: dict[str, Any]) -> None:
            if self.fail:
                raise ConnectionError("database unavailable")
            self.events.append(event)

    async def exercise() -> None:
        consumer = Consumer()
        message = SimpleNamespace(value=encoded(), topic="logs", partition=2, offset=41)
        store = Store(fail=True)
        with pytest.raises(ConnectionError):
            await persist_message(message, consumer, store)  # type: ignore[arg-type]
        assert consumer.commits == 0
        assert store.events == []

        store.fail = False
        await persist_message(message, consumer, store)  # type: ignore[arg-type]
        assert consumer.commits == 1
        assert len(store.events) == 1

    asyncio.run(exercise())


def test_poison_record_does_not_advance_offset() -> None:
    class Consumer:
        committed = False

        async def commit(self, offsets: Any) -> None:
            self.committed = True

    class Store:
        def insert_event_deduplicated(self, event: dict[str, Any]) -> None:
            raise AssertionError("poison event should not be persisted")

    async def exercise() -> None:
        consumer = Consumer()
        with pytest.raises(ValueError):
            await persist_message(
                SimpleNamespace(value=b"{}", topic="logs", partition=2, offset=41),
                consumer,
                Store(),  # type: ignore[arg-type]
            )
        assert consumer.committed is False

    asyncio.run(exercise())


def test_event_id_is_stable_for_replayed_broker_message() -> None:
    payload = encoded()
    first = decode_event(payload)
    replayed = decode_event(payload)
    assert first["event_id"] == replayed["event_id"]


def test_different_partition_offsets_never_advance_together(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tp = namedtuple("TopicPartition", ["topic", "partition"])
    module = ModuleType("aiokafka")
    module.TopicPartition = tp  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "aiokafka", module)

    class Consumer:
        def __init__(self) -> None:
            self.commits: list[dict[Any, int]] = []

        async def commit(self, offsets: dict[Any, int]) -> None:
            self.commits.append(offsets)

    class Store:
        def __init__(self) -> None:
            self.fail = False

        def insert_event_deduplicated(self, event: dict[str, Any]) -> None:
            if self.fail:
                raise OSError("ClickHouse temporarily unavailable")

    async def scenario() -> None:
        consumer = Consumer()
        store = Store()
        first = SimpleNamespace(value=encoded(), topic="logs", partition=0, offset=7)
        other = SimpleNamespace(value=encoded(), topic="logs", partition=1, offset=12)
        await persist_message(first, consumer, store)  # type: ignore[arg-type]
        store.fail = True
        with pytest.raises(OSError):
            await persist_message(other, consumer, store)  # type: ignore[arg-type]
        assert consumer.commits == [{tp("logs", 0): 8}]
        store.fail = False
        await persist_message(other, consumer, store)  # type: ignore[arg-type]
        assert consumer.commits == [{tp("logs", 0): 8}, {tp("logs", 1): 13}]

    asyncio.run(scenario())


def test_clickhouse_insert_failure_emits_sanitized_replay_signal(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    class Consumer:
        async def commit(self, offsets: Any) -> None:
            raise AssertionError("Offset must not commit when storage fails")

    class Store:
        def insert_event_deduplicated(self, event: dict[str, Any]) -> None:
            raise ConnectionError("password=EXTRA_SECRET_CREDENTIAL")

    async def scenario() -> None:
        message = SimpleNamespace(value=encoded(), topic="private-topic", partition=0, offset=7)
        with pytest.raises(ConnectionError):
            await persist_message(message, Consumer(), Store())  # type: ignore[arg-type]

    with caplog.at_level(logging.ERROR, logger="logsight.kafka_clickhouse_worker"):
        asyncio.run(scenario())
    assert "clickhouse_insert_failed offset_uncommitted" in caplog.text
    assert "EXTRA_SECRET_CREDENTIAL" not in caplog.text
    assert "private-topic" not in caplog.text


def test_offset_commit_failure_emits_ambiguous_replay_signal(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    tp = namedtuple("TopicPartition", ["topic", "partition"])
    module = ModuleType("aiokafka")
    module.TopicPartition = tp  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "aiokafka", module)

    class Consumer:
        async def commit(self, offsets: Any) -> None:
            raise ConnectionError("password=EXTRA_SECRET_CREDENTIAL")

    class Store:
        def __init__(self) -> None:
            self.inserted = 0

        def insert_event_deduplicated(self, event: dict[str, Any]) -> None:
            self.inserted += 1

    async def scenario() -> None:
        store = Store()
        message = SimpleNamespace(value=encoded(), topic="private-topic", partition=0, offset=7)
        with pytest.raises(ConnectionError):
            await persist_message(message, Consumer(), store)  # type: ignore[arg-type]
        assert store.inserted == 1

    with caplog.at_level(logging.ERROR, logger="logsight.kafka_clickhouse_worker"):
        asyncio.run(scenario())
    assert "kafka_offset_commit_failed insert_outcome_success_replay_possible" in caplog.text
    assert "EXTRA_SECRET_CREDENTIAL" not in caplog.text
    assert "private-topic" not in caplog.text
