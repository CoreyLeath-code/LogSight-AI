"""Streaming ingestion adapters with an optional Kafka/Redpanda backend."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterable
from typing import Any

from .enterprise import EnrichedLog
from .kafka_security import kafka_security_settings


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

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        *,
        publish_timeout_seconds: float = 10.0,
    ) -> None:
        if not bootstrap_servers.strip() or not topic.strip():
            raise ValueError("Kafka bootstrap servers and topic must be provided")
        if not 0 < publish_timeout_seconds <= 300:
            raise ValueError("publish_timeout_seconds must be between 0 and 300")
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.publish_timeout_seconds = publish_timeout_seconds
        self._producer: Any = None

    async def start(self) -> None:
        try:
            from aiokafka import AIOKafkaProducer
        except ImportError as exc:
            raise RuntimeError("Install the 'kafka' extra to use KafkaStream") from exc
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            acks="all",
            enable_idempotence=True,
            **kafka_security_settings(),
        )
        await self._producer.start()

    async def publish(self, event: EnrichedLog) -> None:
        if self._producer is None:
            raise RuntimeError("KafkaStream.start() must be called before publish()")
        # A timeout is an indeterminate outcome: broker acceptance may have
        # succeeded. Callers must not assume that retrying is exactly-once.
        try:
            await asyncio.wait_for(
                self._producer.send_and_wait(self.topic, event.to_json().encode("utf-8")),
                timeout=self.publish_timeout_seconds,
            )
        except TimeoutError as exc:
            raise TimeoutError("Kafka publish acknowledgement timed out") from exc

    def is_ready(self) -> bool:
        """Report whether the configured Kafka producer is initialized locally.

        Does not prove broker reachability following startup.
        """
        return self._producer is not None

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
