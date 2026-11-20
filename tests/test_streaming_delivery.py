"""Kafka adapter delivery-contract tests without a running broker."""

from __future__ import annotations

import asyncio
import sys
from types import ModuleType
from typing import Any

import pytest

from logsight.enterprise import enrich
from logsight.parser import parse_line
from logsight.streaming import KafkaStream


def test_invalid_kafka_configuration() -> None:
    with pytest.raises(ValueError, match="bootstrap"):
        KafkaStream("", "events")
    with pytest.raises(ValueError, match="bootstrap"):
        KafkaStream("localhost:9092", "")
    with pytest.raises(ValueError, match="publish_timeout"):
        KafkaStream("localhost:9092", "events", publish_timeout_seconds=0)


def test_idempotent_acknowledged_publish(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[dict[str, Any]] = []
    publishes: list[tuple[str, bytes]] = []

    class FakeProducer:
        def __init__(self, **kwargs: Any) -> None:
            created.append(kwargs)

        async def start(self) -> None:
            return None

        async def send_and_wait(self, topic: str, payload: bytes) -> None:
            publishes.append((topic, payload))

        async def stop(self) -> None:
            return None

    module = ModuleType("aiokafka")
    module.AIOKafkaProducer = FakeProducer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "aiokafka", module)

    async def scenario() -> None:
        stream = KafkaStream("localhost:9092", "logs")
        with pytest.raises(RuntimeError, match="start"):
            await stream.publish(enrich(parse_line("INFO started")))
        await stream.start()
        await stream.publish(enrich(parse_line("INFO started")))
        await stream.stop()
        assert stream._producer is None

    asyncio.run(scenario())
    assert created == [
        {
            "bootstrap_servers": "localhost:9092",
            "acks": "all",
            "enable_idempotence": True,
        }
    ]
    assert publishes[0][0] == "logs"
    assert b"started" in publishes[0][1]


def test_publish_timeout_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeProducer:
        async def send_and_wait(self, topic: str, payload: bytes) -> None:
            await asyncio.sleep(1)

    async def scenario() -> None:
        stream = KafkaStream("localhost:9092", "logs", publish_timeout_seconds=0.001)
        stream._producer = FakeProducer()
        with pytest.raises(TimeoutError, match="acknowledgement timed out"):
            await stream.publish(enrich(parse_line("ERROR timeout")))

    asyncio.run(scenario())
