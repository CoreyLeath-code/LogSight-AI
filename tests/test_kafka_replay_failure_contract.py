"""Unit fault injection for a DB success followed by a failed Kafka offset commit."""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from collections import namedtuple
from datetime import datetime, timezone
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from logsight.enterprise import enrich
from logsight.kafka_clickhouse_worker import persist_message
from logsight.parser import parse_line


def test_failed_offset_commit_replays_same_event_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tp = namedtuple("TopicPartition", ["topic", "partition"])
    module = ModuleType("aiokafka")
    module.TopicPartition = tp  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "aiokafka", module)

    class Consumer:
        def __init__(self) -> None:
            self.fail_once = True
            self.acknowledged: list[dict[Any, int]] = []

        async def commit(self, offsets: dict[Any, int]) -> None:
            if self.fail_once:
                self.fail_once = False
                raise ConnectionError("Kafka offset commit failed")
            self.acknowledged.append(offsets)

    class RecordingStore:
        def __init__(self) -> None:
            self.inserted_ids: list[str] = []

        def insert_event_deduplicated(self, event: dict[str, Any]) -> None:
            self.inserted_ids.append(event["event_id"])

    event = enrich(parse_line("ERROR replay test"))
    event.event_id = str(uuid.uuid4())
    event.timestamp = datetime.now(timezone.utc).isoformat()
    record = SimpleNamespace(
        value=json.dumps(event.to_dict()).encode(), topic="logs", partition=2, offset=10
    )

    async def scenario() -> None:
        consumer = Consumer()
        store = RecordingStore()
        with pytest.raises(ConnectionError, match="offset commit failed"):
            await persist_message(record, consumer, store)  # type: ignore[arg-type]
        assert consumer.acknowledged == []
        await persist_message(record, consumer, store)  # type: ignore[arg-type]
        assert consumer.acknowledged == [{tp("logs", 2): 11}]
        assert store.inserted_ids == [event.event_id, event.event_id]

    asyncio.run(scenario())
