"""HTTP storage adapters for ClickHouse and Qdrant.

The adapters intentionally use small JSON/HTTP contracts so the core package
stays dependency-light. Production deployments can swap them for native SDKs.
"""

from __future__ import annotations

import json
import ssl
import urllib.parse
import urllib.request
import uuid
from typing import Any, cast


class ClickHouseStore:
    def __init__(
        self,
        base_url: str = "http://localhost:8123",
        database: str = "logsight",
        *,
        username: str | None = None,
        password: str | None = None,
        ca_file: str | None = None,
    ) -> None:
        parsed = urllib.parse.urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError("ClickHouse URL must be an HTTP(S) origin without credentials")
        if not database or not database.replace("_", "").isalnum():
            raise ValueError("ClickHouse database name must be alphanumeric or underscores")
        if (username is None) != (password is None):
            raise ValueError("ClickHouse username and password must be configured together")
        if username is not None:
            if not username or not password or "\\r" in username or "\\n" in username:
                raise ValueError("Invalid ClickHouse authentication configuration")
            if parsed.scheme != "https":
                raise ValueError("ClickHouse credentials require HTTPS")
        if ca_file and parsed.scheme != "https":
            raise ValueError("ClickHouse custom CA requires HTTPS")
        self.base_url = base_url.rstrip("/")
        self.database = database
        self.username = username
        self.password = password
        try:
            self._ssl_context = (
                ssl.create_default_context(cafile=ca_file or None)
                if parsed.scheme == "https"
                else None
            )
        except (OSError, ssl.SSLError) as exc:
            raise ValueError("Invalid ClickHouse CA configuration") from exc

    def execute(self, query: str, data: str | None = None) -> bytes:
        params = urllib.parse.urlencode({"database": self.database, "query": query})
        headers = {"Content-Type": "application/json"}
        if self.username is not None:
            headers["X-ClickHouse-User"] = self.username
            headers["X-ClickHouse-Key"] = self.password or ""
        request = urllib.request.Request(
            f"{self.base_url}/?{params}",
            data=data.encode() if data is not None else None,
            headers=headers,
            method="POST",
        )
        if self._ssl_context is not None:
            response = urllib.request.urlopen(
                request, timeout=10, context=self._ssl_context
            )  # nosec B310
        else:
            response = urllib.request.urlopen(request, timeout=10)  # nosec B310
        with response as result:
            return cast(bytes, result.read())

    def insert_events(self, events: list[dict[str, Any]]) -> None:
        if not events:
            return
        payload = "\n".join(json.dumps(event, separators=(",", ":")) for event in events)
        self.execute("INSERT INTO logsight.events FORMAT JSONEachRow", payload)

    def insert_event_deduplicated(self, event: dict[str, Any]) -> None:
        """Insert a single event with a deterministic bounded block-dedup token.

        Requires a configured MergeTree deduplication window. This is not a
        unique constraint and does not guarantee exactly-once delivery.
        """
        raw_id = event.get("event_id")
        if not isinstance(raw_id, str):
            raise ValueError("event_id must be a canonical UUID")
        try:
            event_id = str(uuid.UUID(raw_id))
        except ValueError as exc:
            raise ValueError("event_id must be a canonical UUID") from exc
        if event_id != raw_id:
            raise ValueError("event_id must be a canonical UUID")
        payload = json.dumps(event, separators=(",", ":"))
        self.execute(
            "INSERT INTO logsight.events "
            "SETTINGS insert_deduplicate=1, "
            f"insert_deduplication_token='{event_id}' FORMAT JSONEachRow",
            payload,
        )


class QdrantStore:
    def __init__(
        self, base_url: str = "http://localhost:6333", collection: str = "logsight"
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.collection = collection

    def upsert(self, points: list[dict[str, Any]]) -> dict[str, Any]:
        url = f"{self.base_url}/collections/{urllib.parse.quote(self.collection, safe='')}/points"
        body = json.dumps({"points": points}).encode()
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310
            return cast(dict[str, Any], json.loads(response.read().decode()))
