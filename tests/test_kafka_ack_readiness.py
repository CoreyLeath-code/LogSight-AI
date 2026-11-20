"""Kafka readiness follows confirmed delivery outcomes, not producer presence alone."""

from __future__ import annotations

import asyncio
import sys
from types import ModuleType
from typing import Any

import pytest

from logsight.enterprise import enrich
from logsight.parser import parse_line
from logsight.streaming import KafkaStream


@pytest.mark.parametrize("failure", ["timeout", "connection", "cancel"])
def test_publish_failure_degrades_until_confirmed_recovery(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    class Producer:
        fail_mode = failure

        async def start(self) -> None:
            return None

        async def stop(self) -> None:
            return None

        async def send_and_wait(self, topic: str, payload: bytes) -> None:
            if self.fail_mode == "timeout":
                await asyncio.sleep(1)
            if self.fail_mode == "connection":
                raise ConnectionError("broker unavailable")
            if self.fail_mode == "cancel":
                raise asyncio.CancelledError

    fake = ModuleType("aiokafka")
    producer = Producer()
    fake.AIOKafkaProducer = lambda **kwargs: producer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "aiokafka", fake)

    async def scenario() -> None:
        stream = KafkaStream("broker:9092", "logs", publish_timeout_seconds=0.001)
        assert not stream.is_ready()
        await stream.start()
        assert stream.is_ready()
        event = enrich(parse_line("INFO test"))
        expected = (
            TimeoutError
            if failure == "timeout"
            else asyncio.CancelledError
            if failure == "cancel"
            else ConnectionError
        )
        with pytest.raises(expected):
            await stream.publish(event)
        assert not stream.is_ready()
        producer.fail_mode = ""
        await stream.publish(event)
        assert stream.is_ready()
        await stream.stop()
        assert not stream.is_ready()

    asyncio.run(scenario())


def test_failed_start_never_marks_producer_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    class Producer:
        async def start(self) -> None:
            raise ConnectionError("broker unavailable")

    fake = ModuleType("aiokafka")
    fake.AIOKafkaProducer = lambda **kwargs: Producer()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "aiokafka", fake)

    async def scenario() -> None:
        stream = KafkaStream("broker:9092", "logs")
        with pytest.raises(ConnectionError):
            await stream.start()
        assert not stream.is_ready()
        assert stream._producer is None

    asyncio.run(scenario())
