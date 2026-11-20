"""API readiness is separate from liveness and does not leak application tokens."""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from logsight import api


def test_local_mode_readiness_and_liveness(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGSIGHT_API_KAFKA_ENABLED", "false")
    monkeypatch.setenv("LOGSIGHT_API_AUTH_MODE", "disabled")
    with TestClient(api.create_app()) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert client.get("/ready").json()["status"] == "ready"


def test_readiness_is_public_but_operational_routes_remain_protected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOGSIGHT_API_KAFKA_ENABLED", "false")
    monkeypatch.setenv("LOGSIGHT_API_AUTH_MODE", "token")
    monkeypatch.setenv("LOGSIGHT_API_TOKEN", "r" * 48)
    with TestClient(api.create_app()) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 200
        assert client.get("/metrics").status_code == 401


def test_kafka_readiness_degrades_without_masking_liveness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeKafka:
        def __init__(self, bootstrap_servers: str, topic: str) -> None:
            self.ready = False

        async def start(self) -> None:
            self.ready = True

        async def stop(self) -> None:
            self.ready = False

        def is_ready(self) -> bool:
            return self.ready

    monkeypatch.setenv("LOGSIGHT_API_KAFKA_ENABLED", "true")
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "broker:9092")
    monkeypatch.setenv("LOGSIGHT_KAFKA_TOPIC", "logs")
    monkeypatch.setenv("LOGSIGHT_API_AUTH_MODE", "disabled")
    monkeypatch.setattr(api, "KafkaStream", FakeKafka)
    monkeypatch.setattr(api, "_admission_controller", None)
    with TestClient(api.create_app()) as client:
        assert client.get("/ready").status_code == 200
        producer: Any = client.app.state.kafka_stream
        producer.ready = False
        assert client.get("/health").status_code == 200
        result = client.get("/ready")
        assert result.status_code == 503
        assert "producer not ready" in result.json()["detail"]
