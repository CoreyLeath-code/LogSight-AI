"""Opt-in Kafka metadata polling tests without a real broker."""

from __future__ import annotations

import asyncio
import sys
from types import ModuleType
from typing import Any

import pytest

from logsight.streaming import KafkaStream


def test_monitor_interval_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    for value in ("invalid", "-1", "1", "301"):
        monkeypatch.setenv("LOGSIGHT_KAFKA_MONITOR_INTERVAL_SECONDS", value)
        with pytest.raises(ValueError):
            KafkaStream("broker:9092", "logs")
    monkeypatch.setenv("LOGSIGHT_KAFKA_MONITOR_INTERVAL_SECONDS", "0")
    assert KafkaStream("broker:9092", "logs").monitor_interval_seconds == 0


def test_live_metadata_probe_fails_closed_and_recovers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Metadata:
        def partitions_for_topic(self, topic: str) -> set[int]:
            assert topic == "logs"
            return {0}

    class Client:
        error = False
        calls = 0

        async def fetch_all_metadata(self) -> Metadata:
            self.calls += 1
            if self.error:
                raise ConnectionError("Kafka unavailable")
            return Metadata()

    class Producer:
        def __init__(self, **kwargs: Any) -> None:
            self.client = Client()

        async def start(self) -> None:
            return None

        async def stop(self) -> None:
            return None

    producer = Producer()
    module = ModuleType("aiokafka")
    module.AIOKafkaProducer = lambda **kwargs: producer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "aiokafka", module)
    monkeypatch.setenv("LOGSIGHT_KAFKA_MONITOR_INTERVAL_SECONDS", "5")

    async def scenario() -> None:
        stream = KafkaStream("broker:9092", "logs")
        await stream.start()
        assert stream.is_ready()
        producer.client.error = True
        await stream._probe_metadata()
        assert not stream.is_ready()
        producer.client.error = False
        await stream._probe_metadata()
        assert stream.is_ready()
        assert producer.client.calls == 2
        await stream.stop()
        assert stream._monitor_task is None
        assert not stream.is_ready()

    asyncio.run(asyncio.wait_for(scenario(), timeout=5))


def test_bounded_probe_timeout_and_empty_partition_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Metadata:
        def partitions_for_topic(self, topic: str) -> set[int]:
            return set()

    class Client:
        mode = "timeout"

        async def fetch_all_metadata(self) -> Metadata:
            if self.mode == "timeout":
                await asyncio.sleep(1)
            return Metadata()

    class Producer:
        def __init__(self) -> None:
            self.client = Client()

    async def scenario() -> None:
        stream = KafkaStream("broker:9092", "logs")
        stream._producer = Producer()
        stream.monitor_timeout_seconds = 0.001
        stream._ready = True
        await stream._probe_metadata()
        assert not stream.is_ready()
        stream._producer.client.mode = "empty"
        stream._ready = True
        await stream._probe_metadata()
        assert not stream.is_ready()

    asyncio.run(asyncio.wait_for(scenario(), timeout=5))


def test_periodic_monitor_invokes_probe_and_cancels_on_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Metadata:
        def partitions_for_topic(self, topic: str) -> set[int]:
            return {0}

    class Client:
        calls = 0

        async def fetch_all_metadata(self) -> Metadata:
            self.calls += 1
            return Metadata()

    class Producer:
        def __init__(self, **kwargs: Any) -> None:
            self.client = Client()

        async def start(self) -> None:
            return None

        async def stop(self) -> None:
            return None

    producer = Producer()
    module = ModuleType("aiokafka")
    module.AIOKafkaProducer = lambda **kwargs: producer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "aiokafka", module)
    monkeypatch.setenv("LOGSIGHT_KAFKA_MONITOR_INTERVAL_SECONDS", "5")

    async def scenario() -> None:
        stream = KafkaStream("broker:9092", "logs")
        stream.monitor_interval_seconds = 0.001
        await stream.start()
        await asyncio.sleep(0.02)
        assert producer.client.calls > 0
        await stream.stop()
        before = producer.client.calls
        await asyncio.sleep(0.005)
        assert producer.client.calls == before

    asyncio.run(asyncio.wait_for(scenario(), timeout=5))


def test_metadata_success_does_not_erase_failed_publish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Readiness must require both confirmed writes and broker metadata."""
    from logsight.enterprise import enrich
    from logsight.parser import parse_line

    class Metadata:
        def partitions_for_topic(self, topic: str) -> set[int]:
            return {0}

    class Client:
        failing = False

        async def fetch_all_metadata(self) -> Metadata:
            if self.failing:
                raise ConnectionError("metadata unreachable")
            return Metadata()

    class Producer:
        def __init__(self, **kwargs: Any) -> None:
            self.client = Client()
            self.fail_send = True

        async def start(self) -> None:
            return None

        async def stop(self) -> None:
            return None

        async def send_and_wait(self, topic: str, payload: bytes) -> None:
            if self.fail_send:
                raise ConnectionError("publish unavailable")

    producer = Producer()
    module = ModuleType("aiokafka")
    module.AIOKafkaProducer = lambda **kwargs: producer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "aiokafka", module)
    monkeypatch.setenv("LOGSIGHT_KAFKA_MONITOR_INTERVAL_SECONDS", "5")

    async def scenario() -> None:
        stream = KafkaStream("broker:9092", "logs")
        await stream.start()
        event = enrich(parse_line("INFO test"))
        await stream._probe_metadata()
        assert stream.is_ready()
        with pytest.raises(ConnectionError):
            await stream.publish(event)
        assert not stream.is_ready()
        await stream._probe_metadata()
        assert not stream.is_ready()  # Metadata cannot override failed write.

        producer.fail_send = False
        producer.client.failing = True
        await stream._probe_metadata()
        await stream.publish(event)
        assert not stream.is_ready()  # Write cannot override failed metadata.
        producer.client.failing = False
        await stream._probe_metadata()
        assert stream.is_ready()
        await stream.stop()
        assert not stream.is_ready()

    asyncio.run(asyncio.wait_for(scenario(), timeout=5))
