"""API readiness transitions after actual Kafka publish acknowledgements."""

from __future__ import annotations

import sys
from types import ModuleType

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from logsight import api


def test_api_readiness_degrades_after_failed_broker_ack_and_recovers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Producer:
        failing = True

        async def start(self) -> None:
            return None

        async def stop(self) -> None:
            return None

        async def send_and_wait(self, topic: str, payload: bytes) -> None:
            if self.failing:
                raise ConnectionError("synthetic unavailable broker")

    producer = Producer()
    fake = ModuleType("aiokafka")
    fake.AIOKafkaProducer = lambda **kwargs: producer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "aiokafka", fake)
    monkeypatch.setenv("LOGSIGHT_API_KAFKA_ENABLED", "true")
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "broker:9092")
    monkeypatch.setenv("LOGSIGHT_KAFKA_TOPIC", "logs")
    monkeypatch.setenv("LOGSIGHT_API_AUTH_MODE", "disabled")
    monkeypatch.setattr(api, "_admission_controller", None)
    monkeypatch.setattr(api, "_inference_dispatcher", None)
    api._recent.clear()

    with TestClient(api.create_app()) as client:
        assert client.get("/ready").status_code == 200
        assert client.post("/v1/logs", json={"line": "ERROR synthetic"}).status_code == 503
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 503
        producer.failing = False
        assert client.post("/v1/logs", json={"line": "INFO recovered"}).status_code == 200
        assert client.get("/ready").status_code == 200

    api._recent.clear()
