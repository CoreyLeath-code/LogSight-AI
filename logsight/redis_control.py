"""Optional Redis-backed deduplication and rate-limit admission controls."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from .enterprise import EnrichedLog

_ADMIT_SCRIPT = """
if redis.call("GET", KEYS[1]) then
  return {0, "duplicate"}
end
local count = redis.call("INCR", KEYS[2])
if count == 1 then
  redis.call("EXPIRE", KEYS[2], ARGV[2])
end
if count > tonumber(ARGV[1]) then
  return {0, "rate_limited"}
end
redis.call("SET", KEYS[1], "1", "EX", ARGV[3])
return {1, "accepted"}
"""


class AsyncRedisClient(Protocol):
    """Small async Redis contract needed by the admission controller."""

    async def eval(
        self, script: str, numkeys: int, *keys_and_args: str | int
    ) -> Sequence[Any]:
        """Execute a Lua script and return its result tuple."""


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    """Result of one atomic deduplication and rate-limit attempt."""

    accepted: bool
    reason: str


class RedisAdmissionController:
    """Perform deduplication and per-scope rate limiting in one Redis script."""

    def __init__(
        self,
        client: AsyncRedisClient,
        *,
        rate_limit: int = 120,
        rate_window_seconds: int = 60,
        dedup_ttl_seconds: int = 300,
        key_prefix: str = "logsight",
    ) -> None:
        if min(rate_limit, rate_window_seconds, dedup_ttl_seconds) < 1:
            raise ValueError("Redis admission limits must be positive")
        if not key_prefix:
            raise ValueError("key_prefix must not be empty")
        self.client = client
        self.rate_limit = rate_limit
        self.rate_window_seconds = rate_window_seconds
        self.dedup_ttl_seconds = dedup_ttl_seconds
        self.key_prefix = key_prefix

    async def admit(self, event: EnrichedLog, scope: str) -> AdmissionDecision:
        """Atomically reject duplicate events or exhausted scoped budgets."""

        if not event.fingerprint:
            raise ValueError("event fingerprint is required for Redis admission")
        if not scope:
            raise ValueError("scope is required for Redis admission")
        dedup_key = f"{self.key_prefix}:dedup:{event.fingerprint}"
        rate_key = f"{self.key_prefix}:rate:{scope}"
        response = await self.client.eval(
            _ADMIT_SCRIPT,
            2,
            dedup_key,
            rate_key,
            self.rate_limit,
            self.rate_window_seconds,
            self.dedup_ttl_seconds,
        )
        if len(response) != 2:
            raise RuntimeError("Redis admission script returned an invalid response")
        accepted, reason = response
        if not isinstance(reason, str) or reason not in {
            "accepted",
            "duplicate",
            "rate_limited",
        }:
            raise RuntimeError("Redis admission script returned an unknown reason")
        return AdmissionDecision(accepted=bool(accepted), reason=reason)


def build_redis_controller() -> RedisAdmissionController | None:
    """Build controls only when a deployment explicitly configures Redis."""

    url = os.getenv("LOGSIGHT_REDIS_URL")
    if not url:
        return None
    try:
        from redis.asyncio import Redis
    except ImportError as exc:
        raise RuntimeError("Install the redis extra to enable Redis admission controls") from exc
    client = Redis.from_url(url, decode_responses=True)
    return RedisAdmissionController(
        client,
        rate_limit=int(os.getenv("LOGSIGHT_RATE_LIMIT", "120")),
        rate_window_seconds=int(os.getenv("LOGSIGHT_RATE_WINDOW_SECONDS", "60")),
        dedup_ttl_seconds=int(os.getenv("LOGSIGHT_DEDUP_TTL_SECONDS", "300")),
        key_prefix=os.getenv("LOGSIGHT_REDIS_KEY_PREFIX", "logsight"),
    )
