"""Contract tests for Redis admission controls."""

from __future__ import annotations

import asyncio

import pytest

from logsight.enterprise import enrich
from logsight.parser import parse_line
from logsight.redis_control import RedisAdmissionController


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

    controller = RedisAdmissionController(FakeRedis([2, "accepted"]))
    with pytest.raises(RuntimeError, match="invalid response"):
        asyncio.run(controller.admit(event("INFO accepted"), "payments"))
