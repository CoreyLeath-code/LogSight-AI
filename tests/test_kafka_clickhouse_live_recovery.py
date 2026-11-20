"""Opt-in real Kafka/ClickHouse replay-and-recovery integration test.

Requires disposable, locally controlled services. Not run in ordinary CI.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import pytest

from logsight.enterprise import enrich
from logsight.kafka_clickhouse_worker import persist_message
from logsight.parser import parse_line
from logsight.storage import ClickHouseStore


@pytest.mark.skipif(
    os.environ.get("LOGSIGHT_RUN_DURABILITY_INTEGRATION") != "1",
    reason="requires explicitly enabled disposable Kafka and ClickHouse services",
)
def test_real_kafka_clickhouse_redelivery_and_storage_recovery() -> None:
    aiokafka = pytest.importorskip("aiokafka")
    bootstrap = os.environ.get("LOGSIGHT_INTEGRATION_KAFKA_BOOTSTRAP", "")
    clickhouse = os.environ.get("LOGSIGHT_INTEGRATION_CLICKHOUSE_URL", "")
    topic = os.environ.get("LOGSIGHT_INTEGRATION_KAFKA_TOPIC", "")
    if not all((bootstrap, clickhouse, topic)):
        pytest.fail("Set the integration Kafka bootstrap, ClickHouse URL and test topic")

    class FailFirstInsert(ClickHouseStore):
        def __init__(self, base_url: str) -> None:
            super().__init__(base_url=base_url)
            self.fail_once = True

        def insert_event_deduplicated(self, event: dict[str, Any]) -> None:
            if self.fail_once:
                self.fail_once = False
                raise ConnectionError("Simulated ClickHouse unavailability")
            super().insert_event_deduplicated(event)

    async def scenario() -> None:
        # Unique consumer group prevents unrelated test runs from sharing offsets.
        producer = aiokafka.AIOKafkaProducer(
            bootstrap_servers=bootstrap, acks="all", enable_idempotence=True
        )
        consumer = aiokafka.AIOKafkaConsumer(
            topic,
            bootstrap_servers=bootstrap,
            group_id=f"logsight-durability-test-{uuid.uuid4()}",
            enable_auto_commit=False,
            auto_offset_reset="earliest",
        )
        store = FailFirstInsert(base_url=clickhouse)
        event = enrich(parse_line("ERROR integration replay test"))
        event.timestamp = datetime.now(timezone.utc).isoformat()
        target_id = event.event_id
        await producer.start()
        try:
            await consumer.start()
            try:
                # Ensure this partition is assigned and its starting position
                # is established before publishing the probe event.
                for _ in range(30):
                    if consumer.assignment():
                        break
                    await consumer.getmany(timeout_ms=500, max_records=1)
                if not consumer.assignment():
                    pytest.fail("Kafka consumer did not receive a partition")
                await producer.send_and_wait(topic, event.to_json().encode("utf-8"))
                # A dedicated test topic is required; it must not carry user logs.
                record: Any = await asyncio.wait_for(consumer.getone(), timeout=20)
                assert record.value == event.to_json().encode("utf-8")
                tp = aiokafka.TopicPartition(record.topic, record.partition)
                assert await consumer.committed(tp) is None

                with pytest.raises(ConnectionError, match="Simulated ClickHouse"):
                    await persist_message(record, consumer, store)
                assert await consumer.committed(tp) is None

                await persist_message(record, consumer, store)
                assert await consumer.committed(tp) == record.offset + 1

                # Mimic a crash after DB success but before committing: seek
                # to the previously handled record and process it once more.
                consumer.seek(tp, record.offset)
                again: Any = await asyncio.wait_for(consumer.getone(), timeout=20)
                assert again.value == record.value
                await persist_message(again, consumer, store)

                result = store.execute(
                    "SELECT count() FROM logsight.events "
                    f"WHERE event_id = '{target_id}' FORMAT TabSeparated"
                )
                assert int(result.decode().strip()) == 1, (
                    "Retry inserted a duplicate: verify ClickHouse engine, "
                    "deduplication window and migration"
                )
            finally:
                await consumer.stop()
        finally:
            await producer.stop()

    asyncio.run(scenario())
