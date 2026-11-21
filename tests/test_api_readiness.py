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


@pytest.mark.parametrize("mode", ["ok", "false", "error", "timeout"])
def test_configured_redis_admission_affects_readiness_not_liveness(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    import asyncio
    from types import SimpleNamespace

    class FakeRedisClient:
        async def ping(self) -> bool:
            if mode == "false":
                return False
            if mode == "error":
                raise ConnectionError("do not leak host details")
            if mode == "timeout":
                await asyncio.sleep(0.1)
            return True

    monkeypatch.setenv("LOGSIGHT_API_KAFKA_ENABLED", "false")
    monkeypatch.setenv("LOGSIGHT_API_AUTH_MODE", "disabled")
    monkeypatch.setenv("LOGSIGHT_REDIS_READINESS_TIMEOUT_SECONDS", "0.001")
    monkeypatch.setattr(api, "_admission_controller", SimpleNamespace(client=FakeRedisClient()))
    with TestClient(api.create_app()) as client:
        assert client.get("/health").status_code == 200
        response = client.get("/ready")
        if mode == "ok":
            assert response.status_code == 200
        else:
            assert response.status_code == 503
            assert response.json()["detail"] == "Redis admission not ready"
            assert "do not leak" not in response.text


@pytest.mark.parametrize("value", ["invalid", "-1", "0", "6"])
def test_redis_readiness_timeout_rejects_invalid_configuration(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("LOGSIGHT_API_KAFKA_ENABLED", "false")
    monkeypatch.setenv("LOGSIGHT_REDIS_READINESS_TIMEOUT_SECONDS", value)
    with pytest.raises(RuntimeError, match="Redis readiness timeout"):
        api.create_app()


def test_readiness_metrics_are_bounded_and_auth_protected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    class Client:
        healthy = True

        async def ping(self) -> bool:
            return self.healthy

    redis = Client()
    monkeypatch.setenv("LOGSIGHT_API_KAFKA_ENABLED", "false")
    monkeypatch.setenv("LOGSIGHT_API_AUTH_MODE", "token")
    monkeypatch.setenv("LOGSIGHT_API_TOKEN", "s" * 48)
    monkeypatch.setattr(api, "_admission_controller", SimpleNamespace(client=redis))
    keys = (
        "logsight_readiness_success_total",
        "logsight_readiness_redis_failure_total",
    )
    before = {key: api._metrics[key] for key in keys}
    with TestClient(api.create_app()) as client:
        assert client.get("/metrics").status_code == 401
        assert client.get("/ready").status_code == 200
        redis.healthy = False
        assert client.get("/ready").status_code == 503
        metrics = client.get(
            "/metrics", headers={"Authorization": "Bearer " + "s" * 48}
        )
        assert metrics.status_code == 200
        for key in keys:
            assert key + " " in metrics.text
        assert "Redis admission not ready" not in metrics.text
    assert api._metrics[keys[0]] == before[keys[0]] + 1
    assert api._metrics[keys[1]] == before[keys[1]] + 1
