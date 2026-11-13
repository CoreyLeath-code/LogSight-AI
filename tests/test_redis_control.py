"""Contract tests for Redis admission controls."""

from __future__ import annotations

import asyncio
import sys
from types import ModuleType

import pytest

from logsight.enterprise import enrich
from logsight.parser import parse_line
from logsight.redis_control import RedisAdmissionController, build_redis_controller


class FakeRedis:
    def __init__(self, response: list[int | str]) -> None:
        self.response = response
        self.calls: list[tuple[object, ...]] = []

    async def eval(self, *args: object) -> list[int | str]:
        self.calls.append(args)
        return self.response


def event(message: str):
    return enrich(parse_line(message), service="payments")


def test_admission_uses_atomic_script_and_hashed_scope() -> None:
    client = FakeRedis([1, "accepted"])
    controller = RedisAdmissionController(
        client, rate_limit=5, rate_window_seconds=30, dedup_ttl_seconds=90
    )

    decision = asyncio.run(controller.admit(event("ERROR request 42 failed"), "payments/api"))

    assert decision.accepted is True
    assert decision.reason == "accepted"
    script, key_count, dedup_key, rate_key, *args = client.calls[0]
    assert "redis.call" in str(script)
    assert key_count == 2
    assert str(dedup_key).startswith("logsight:dedup:")
    assert str(rate_key).startswith("logsight:rate:")
    assert "payments/api" not in str(rate_key)
    assert args == [5, 30, 90]


def test_admission_preserves_duplicate_and_rate_limited_outcomes() -> None:
    duplicate = RedisAdmissionController(FakeRedis([0, "duplicate"]))
    rate_limited = RedisAdmissionController(FakeRedis([0, "rate_limited"]))

    duplicate_result = asyncio.run(duplicate.admit(event("INFO same log"), "payments"))
    rate_result = asyncio.run(rate_limited.admit(event("INFO another log"), "payments"))

    assert duplicate_result.accepted is False
    assert duplicate_result.reason == "duplicate"
    assert rate_result.accepted is False
    assert rate_result.reason == "rate_limited"


def test_admission_rejects_invalid_configuration_and_responses() -> None:
    with pytest.raises(ValueError, match="positive"):
        RedisAdmissionController(FakeRedis([1, "accepted"]), rate_limit=0)
    with pytest.raises(ValueError, match="must not be empty"):
        RedisAdmissionController(FakeRedis([1, "accepted"]), key_prefix="")

    missing_fingerprint = event("INFO accepted")
    missing_fingerprint.fingerprint = None
    with pytest.raises(ValueError, match="fingerprint"):
        asyncio.run(RedisAdmissionController(FakeRedis([1, "accepted"])).admit(missing_fingerprint, "x"))
    with pytest.raises(ValueError, match="scope"):
        asyncio.run(RedisAdmissionController(FakeRedis([1, "accepted"])).admit(event("INFO accepted"), ""))

    invalid_length = RedisAdmissionController(FakeRedis([1]))
    with pytest.raises(RuntimeError, match="invalid response"):
        asyncio.run(invalid_length.admit(event("INFO accepted"), "payments"))
    invalid_value = RedisAdmissionController(FakeRedis([2, "accepted"]))
    with pytest.raises(RuntimeError, match="invalid response"):
        asyncio.run(invalid_value.admit(event("INFO accepted"), "payments"))


def test_redis_controller_is_optional_without_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOGSIGHT_REDIS_URL", raising=False)

    assert build_redis_controller() is None


def test_redis_controller_builds_from_explicit_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    created: dict[str, object] = {}

    class FakeRedisFactory:
        @staticmethod
        def from_url(url: str, *, decode_responses: bool) -> FakeRedis:
            created["url"] = url
            created["decode_responses"] = decode_responses
            return FakeRedis([1, "accepted"])

    redis_module = ModuleType("redis")
    redis_module.__path__ = []  # type: ignore[attr-defined]
    asyncio_module = ModuleType("redis.asyncio")
    asyncio_module.Redis = FakeRedisFactory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "redis", redis_module)
    monkeypatch.setitem(sys.modules, "redis.asyncio", asyncio_module)
    monkeypatch.setenv("LOGSIGHT_REDIS_URL", "redis://cache:6379/2")
    monkeypatch.setenv("LOGSIGHT_RATE_LIMIT", "9")
    monkeypatch.setenv("LOGSIGHT_RATE_WINDOW_SECONDS", "45")
    monkeypatch.setenv("LOGSIGHT_DEDUP_TTL_SECONDS", "180")
    monkeypatch.setenv("LOGSIGHT_REDIS_KEY_PREFIX", "tenant")

    controller = build_redis_controller()

    assert controller is not None
    assert controller.rate_limit == 9
    assert controller.rate_window_seconds == 45
    assert controller.dedup_ttl_seconds == 180
    assert controller.key_prefix == "tenant"
    assert created == {"url": "redis://cache:6379/2", "decode_responses": True}
