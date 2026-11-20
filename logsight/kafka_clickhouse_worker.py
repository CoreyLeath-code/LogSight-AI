"""Experimental Kafka-to-ClickHouse at-least-once sink.

A single worker commits offsets only after ClickHouse accepts the insert.
Malformed records stop processing without committing; a DLQ and poison-record
policy must be approved before deploying this outside a controlled staging lab.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any

from .redaction import redact_log_line
from .storage import ClickHouseStore

_FIELDS = ("level", "service", "source", "host", "message", "raw", "fingerprint")
_OPTIONAL_FIELDS = ("trace_id", "span_id", "template")


def decode_event(payload: bytes) -> dict[str, Any]:
    """Validate a bounded event envelope and map to the existing table contract."""
    if len(payload) > 1024 * 1024:
        raise ValueError("Kafka event exceeds the 1 MiB worker limit")
    try:
        value = json.loads(payload)
        if not isinstance(value, dict):
            raise ValueError("Kafka event must be an object")
        for key in _FIELDS:
            if not isinstance(value.get(key), str):
                raise ValueError("Kafka event missing a required string field")
        for key in _OPTIONAL_FIELDS:
            if value.get(key) is not None and not isinstance(value[key], str):
                raise ValueError("Kafka event has an invalid optional field")
        attributes = value.get("attributes", {})
        if not isinstance(attributes, dict) or not all(
            isinstance(key, str) and isinstance(item, str)
            for key, item in attributes.items()
        ):
            raise ValueError("Kafka event attributes must be a string map")
        raw_timestamp = value["timestamp"]
        if not isinstance(raw_timestamp, str):
            raise ValueError("Kafka event timestamp must be text")
        timestamp = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError("Kafka event timestamp requires timezone")
    except (KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("Invalid Kafka event schema") from exc

    normalized: dict[str, Any] = {
        key: redact_log_line(value[key]) for key in _FIELDS
    }
    normalized["timestamp"] = timestamp.astimezone(timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S.%f"
    )[:-3]
    for key in _OPTIONAL_FIELDS:
        normalized[key] = (
            redact_log_line(value[key]) if value.get(key) is not None else None
        )
    normalized["attributes"] = json.dumps(
        {key: redact_log_line(item) for key, item in attributes.items()},
        separators=(",", ":"),
        sort_keys=True,
    )
    return normalized


async def persist_message(
    payload: bytes, consumer: Any, store: ClickHouseStore
) -> None:
    """Commit the consumer offset only after a successful storage response."""
    event = decode_event(payload)
    await asyncio.to_thread(store.insert_events, [event])
    await consumer.commit()


async def run_worker() -> None:
    """Run a single-member consumer against explicitly configured dependencies."""
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "")
    topic = os.environ.get("LOGSIGHT_KAFKA_TOPIC", "")
    group = os.environ.get("LOGSIGHT_KAFKA_CONSUMER_GROUP", "logsight-clickhouse-v1")
    url = os.environ.get("CLICKHOUSE_URL", "")
    if not all((bootstrap, topic, group, url)):
        raise RuntimeError("Kafka bootstrap, topic, consumer group and ClickHouse URL required")

    try:
        from aiokafka import AIOKafkaConsumer
    except ImportError as exc:
        raise RuntimeError("Install the kafka extra to run the ClickHouse sink") from exc

    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=bootstrap,
        group_id=group,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        max_poll_records=1,
    )
    store = ClickHouseStore(base_url=url)
    await consumer.start()
    try:
        async for message in consumer:
            await persist_message(message.value, consumer, store)
    finally:
        await consumer.stop()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
