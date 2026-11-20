"""HTTP retry identity contract: identity propagation, not deduplication."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from logsight import api


def test_retry_identity_is_reused_without_suppressing_duplicate_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeKafka:
        events: list[Any] = []

        def __init__(self, bootstrap_servers: str, topic: str) -> None:
            self.events = []

        async def start(self) -> None:
            return None

        async def stop(self) -> None:
            return None

        async def publish(self, event: Any) -> None:
            self.events.append(event)

    monkeypatch.setenv("LOGSIGHT_API_KAFKA_ENABLED", "true")
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "broker:9092")
    monkeypatch.setenv("LOGSIGHT_KAFKA_TOPIC", "logsight-events")
    monkeypatch.setenv("LOGSIGHT_API_AUTH_MODE", "disabled")
    monkeypatch.setattr(api, "KafkaStream", FakeKafka)
    monkeypatch.setattr(api, "_admission_controller", None)
    monkeypatch.setattr(api, "_inference_dispatcher", None)
    api._recent.clear()

    key = str(uuid.uuid4())
    with TestClient(api.create_app()) as client:
        headers = {"Idempotency-Key": key}
        first = client.post("/v1/logs", json={"line": "INFO accepted"}, headers=headers)
        second = client.post("/v1/logs", json={"line": "INFO accepted"}, headers=headers)
        assert first.status_code == second.status_code == 200
        assert first.json()["event"]["event_id"] == key
        assert second.json()["event"]["event_id"] == key
        stream = client.app.state.kafka_stream
        assert [event.event_id for event in stream.events] == [key, key]

        ordinary = client.post("/v1/logs", json={"line": "INFO accepted"})
        assert ordinary.status_code == 200
        assert ordinary.json()["event"]["event_id"] != key
    api._recent.clear()


@pytest.mark.parametrize("key", ["", "not-a-uuid", "A" * 100, str(uuid.uuid1())])
def test_invalid_retry_identity_fails_before_ingestion(
    key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOGSIGHT_API_KAFKA_ENABLED", "false")
    monkeypatch.setenv("LOGSIGHT_API_AUTH_MODE", "disabled")
    monkeypatch.setattr(api, "_admission_controller", None)
    monkeypatch.setattr(api, "_inference_dispatcher", None)
    api._recent.clear()
    with TestClient(api.create_app()) as client:
        response = client.post(
            "/v1/logs", json={"line": "INFO rejected"}, headers={"Idempotency-Key": key}
        )
        assert response.status_code == 400
        assert client.get("/v1/logs/recent").json()["count"] == 0
    api._recent.clear()


def test_batch_has_independent_event_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGSIGHT_API_KAFKA_ENABLED", "false")
    monkeypatch.setenv("LOGSIGHT_API_AUTH_MODE", "disabled")
    monkeypatch.setattr(api, "_admission_controller", None)
    monkeypatch.setattr(api, "_inference_dispatcher", None)
    api._recent.clear()
    with TestClient(api.create_app()) as client:
        response = client.post(
            "/v1/logs/batch", json={"logs": [{"line": "INFO one"}, {"line": "INFO two"}]}
        )
        assert response.status_code == 200
        results = response.json()["results"]
        assert len({result["event"]["event_id"] for result in results}) == 2
    api._recent.clear()
