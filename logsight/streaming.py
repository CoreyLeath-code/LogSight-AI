"""Streaming ingestion adapters with an optional Kafka/Redpanda backend."""

from __future__ import annotations

import asyncio
import os
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
        self._ready = False
        self._metadata_ready = True  # Metadata monitoring is opt-in.
        self._monitor_task: asyncio.Task[None] | None = None
        raw_interval = os.getenv("LOGSIGHT_KAFKA_MONITOR_INTERVAL_SECONDS", "0")
        try:
            self.monitor_interval_seconds = float(raw_interval)
        except ValueError as exc:
            raise ValueError("Invalid Kafka monitor interval") from exc
        if self.monitor_interval_seconds != 0 and not 5 <= self.monitor_interval_seconds <= 300:
            raise ValueError("Kafka monitor interval must be zero or between 5 and 300 seconds")
        self.monitor_timeout_seconds = min(self.publish_timeout_seconds, 5.0)

    async def start(self) -> None:
        try:
            from aiokafka import AIOKafkaProducer
        except ImportError as exc:
            raise RuntimeError("Install the 'kafka' extra to use KafkaStream") from exc
        producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            acks="all",
            enable_idempotence=True,
            **kafka_security_settings(),
        )
        self._ready = False
        self._metadata_ready = True  # Remain compatible until first scheduled probe.
        try:
            await producer.start()
        except BaseException:
            self._producer = None
            raise
        self._producer = producer
        self._ready = True
        if self.monitor_interval_seconds:
            self._monitor_task = asyncio.create_task(self._monitor_metadata())

    async def _probe_metadata(self) -> None:
        """Force a live metadata request; never accept cached partition state."""
        producer = self._producer
        if producer is None:
            self._metadata_ready = False
            return
        try:
            metadata = await asyncio.wait_for(
                producer.client.fetch_all_metadata(),
                timeout=self.monitor_timeout_seconds,
            )
            partitions = metadata.partitions_for_topic(self.topic)
            if not partitions:
                raise RuntimeError("Kafka topic has no available partitions")
        except Exception:
            self._metadata_ready = False
        else:
            # Never clear a failed-publish signal using metadata alone.
            self._metadata_ready = True

    async def _monitor_metadata(self) -> None:
        while True:
            await asyncio.sleep(self.monitor_interval_seconds)
            await self._probe_metadata()

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
            self._ready = False
            raise TimeoutError("Kafka publish acknowledgement timed out") from exc
        except BaseException:
            # Fail closed on broker errors and cancellation. A confirmed
            # subsequent acknowledgement can restore local readiness.
            self._ready = False
            raise
        else:
            self._ready = True

    def is_ready(self) -> bool:
        """Reflect local startup and the latest completed broker send outcome.

        This is NOT continuous broker reachability or a delivery SLA check.
        """
        # A stopped/crashed monitor must never leave a stale healthy probe.
        # Deliberately fail closed rather than silently restarting a task here.
        monitor_running = not self.monitor_interval_seconds or (
            self._monitor_task is not None and not self._monitor_task.done()
        )
        return (
            self._producer is not None and self._ready and self._metadata_ready and monitor_running
        )

    async def stop(self) -> None:
        self._ready = False
        self._metadata_ready = False
        monitor = self._monitor_task
        self._monitor_task = None
        if monitor is not None:
            monitor.cancel()
            try:
                await monitor
            except asyncio.CancelledError:
                pass
        producer = self._producer
        self._producer = None
        if producer is not None:
            await producer.stop()


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
