"""Streaming ingestion adapters with an optional Kafka/Redpanda backend."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterable
from typing import Any

from .enterprise import EnrichedLog


class InMemoryStream:
    """Bounded async stream used for local development and tests."""

    def __init__(self, maxsize: int = 10_000) -> None:
        self._queue: asyncio.Queue[EnrichedLog] = asyncio.Queue(maxsize=maxsize)

    async def publish(self, event: EnrichedLog) -> None:
        await self._queue.put(event)

    async def consume(self) -> AsyncIterator[EnrichedLog]:
        while True:
            yield await self._queue.get()
            self._queue.task_done()


class KafkaStream:
    """Kafka/Redpanda producer-consumer adapter.

    Requires the optional ``kafka`` extra (aiokafka). Keeping this adapter
    isolated prevents the base CLI from requiring a broker.
    """

    def __init__(self, bootstrap_servers: str, topic: str) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self._producer: Any = None

    async def start(self) -> None:
        try:
            from aiokafka import AIOKafkaProducer
        except ImportError as exc:
            raise RuntimeError("Install the 'kafka' extra to use KafkaStream") from exc
        self._producer = AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers)
        await self._producer.start()

    async def publish(self, event: EnrichedLog) -> None:
        if self._producer is None:
            raise RuntimeError("KafkaStream.start() must be called before publish()")
        await self._producer.send_and_wait(self.topic, event.to_json().encode("utf-8"))

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None


def batch(iterable: Iterable[EnrichedLog], size: int) -> Iterable[list[EnrichedLog]]:
    """Yield bounded batches for storage/inference workers."""
    current: list[EnrichedLog] = []
    for item in iterable:
        current.append(item)
        if len(current) >= size:
            yield current
            current = []
    if current:
        yield current
