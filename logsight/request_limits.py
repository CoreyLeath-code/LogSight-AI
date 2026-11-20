"""Bounded ASGI request-body buffering for log ingestion endpoints.

Reject oversized payloads before request validation or parsing, including
chunked transfers without Content-Length.
"""

from __future__ import annotations

from typing import Any, cast


class IngestionBodyLimit:
    def __init__(self, app: Any, *, max_body_bytes: int) -> None:
        if max_body_bytes <= 0:
            raise ValueError("max_body_bytes must be positive")
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or scope.get("path") not in {"/v1/logs", "/v1/logs/batch"}
        ):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        length = headers.get(b"content-length")
        if length is not None:
            try:
                declared_length = int(length)
            except ValueError:
                await self._reject(send, 400, b'{"detail":"Invalid Content-Length"}')
                return
            if declared_length < 0:
                await self._reject(send, 400, b'{"detail":"Invalid Content-Length"}')
                return
            if declared_length > self.max_body_bytes:
                await self._reject(send, 413, b'{"detail":"Request body too large"}')
                return

        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_body_bytes:
                await self._reject(send, 413, b'{"detail":"Request body too large"}')
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break

        body = b"".join(chunks)
        delivered = False

        async def replay() -> dict[str, Any]:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return cast(dict[str, Any], await receive())

        await self.app(scope, replay, send)

    @staticmethod
    async def _reject(send: Any, status: int, body: bytes) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"cache-control", b"no-store"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
