"""API broker-acknowledgement contract tests with a fake Kafka producer."""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from logsight import api


class FakeKafka:
    instances: list[FakeKafka] = []

    def __init__(self, bootstrap_servers: str, topic: str) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.events: list[Any] = []
        self.fail = False
        self.started = False
        self.stopped = False
        self.instances.append(self)

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def publish(self, event: Any) -> None:
        if self.fail:
            raise TimeoutError("ambiguous broker outcome")
        self.events.append(event)


@pytest.fixture
def kafka_config(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeKafka.instances.clear()
    monkeypatch.setenv("LOGSIGHT_API_KAFKA_ENABLED", "true")
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "broker:9092")
    monkeypatch.setenv("LOGSIGHT_KAFKA_TOPIC", "logsight-events")
    monkeypatch.setenv("LOGSIGHT_API_AUTH_MODE", "disabled")
    monkeypatch.setattr(api, "KafkaStream", FakeKafka)
    monkeypatch.setattr(api, "_admission_controller", None)
    monkeypatch.setattr(api, "_inference_dispatcher", None)
    api._recent.clear()
    yield
    api._recent.clear()


def test_api_rejects_invalid_kafka_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGSIGHT_API_KAFKA_ENABLED", "perhaps")
    with pytest.raises(RuntimeError, match="true or false"):
        api.create_app()


def test_api_rejects_unresolved_redis_dedup_ordering(kafka_config: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_admission_controller", object())
    with pytest.raises(RuntimeError, match="Redis admission"):
        api.create_app()


def test_successful_publish_precedes_api_acknowledgement(kafka_config: None) -> None:
    with TestClient(api.create_app()) as client:
        producer = FakeKafka.instances[-1]
        assert producer.started
        response = client.post("/v1/logs", json={"line": "ERROR password=secretvalue"})
        assert response.status_code == 200
        assert len(producer.events) == 1
        assert "secretvalue" not in producer.events[0].raw
        assert client.get("/v1/logs/recent").json()["count"] == 1
    assert producer.stopped


def test_failed_publish_does_not_record_locally(kafka_config: None) -> None:
    with TestClient(api.create_app()) as client:
        producer = FakeKafka.instances[-1]
        producer.fail = True
        response = client.post("/v1/logs", json={"line": "ERROR broker unavailable"})
        assert response.status_code == 503
        assert "retry may duplicate" in response.json()["detail"]
        assert client.get("/v1/logs/recent").json()["count"] == 0
    assert producer.stopped
