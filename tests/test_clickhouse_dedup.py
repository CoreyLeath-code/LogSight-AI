"""Unit contract for ClickHouse bounded insert deduplication tokens."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from logsight.storage import ClickHouseStore


def test_same_event_id_has_same_insert_token_on_retry() -> None:
    queries: list[tuple[str, str | None]] = []

    class RecordingStore(ClickHouseStore):
        def execute(self, query: str, data: str | None = None) -> bytes:
            queries.append((query, data))
            return b""

    store = RecordingStore()
    event: dict[str, Any] = {
        "event_id": "b0b0c11b-0fc2-49ef-b8ee-a017a334da12",
        "message": "test",
    }
    store.insert_event_deduplicated(event)
    store.insert_event_deduplicated(event)
    assert len(queries) == 2
    assert queries[0] == queries[1]
    assert "insert_deduplicate=1" in queries[0][0]
    expected_token = "insert_deduplication_token='" + event["event_id"] + "'"
    assert expected_token in queries[0][0]


def test_distinct_ids_produce_distinct_tokens() -> None:
    queries: list[str] = []

    class RecordingStore(ClickHouseStore):
        def execute(self, query: str, data: str | None = None) -> bytes:
            queries.append(query)
            return b""

    store = RecordingStore()
    for _ in range(2):
        store.insert_event_deduplicated({"event_id": str(uuid.uuid4())})
    assert queries[0] != queries[1]


@pytest.mark.parametrize(
    "event_id",
    [None, "", "not-a-uuid", "A" * 100, "B0B0C11B-0FC2-49EF-B8EE-A017A334DA12"],
)
def test_invalid_ids_cannot_be_injected_into_insert_query(event_id: Any) -> None:
    class RecordingStore(ClickHouseStore):
        def execute(self, query: str, data: str | None = None) -> bytes:
            raise AssertionError("invalid ID must not reach database")

    with pytest.raises(ValueError):
        RecordingStore().insert_event_deduplicated({"event_id": event_id})


def test_failed_insert_propagates_to_worker_without_acknowledging() -> None:
    class FailingStore(ClickHouseStore):
        def execute(self, query: str, data: str | None = None) -> bytes:
            raise ConnectionError("ClickHouse unavailable")

    with pytest.raises(ConnectionError):
        FailingStore().insert_event_deduplicated(
            {"event_id": "b0b0c11b-0fc2-49ef-b8ee-a017a334da12"}
        )
