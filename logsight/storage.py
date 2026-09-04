"""HTTP storage adapters for ClickHouse and Qdrant.

The adapters intentionally use small JSON/HTTP contracts so the core package
stays dependency-light. Production deployments can swap them for native SDKs.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any


class ClickHouseStore:
    def __init__(self, base_url: str = "http://localhost:8123", database: str = "logsight") -> None:
        self.base_url = base_url.rstrip("/")
        self.database = database

    def execute(self, query: str, data: str | None = None) -> bytes:
        params = urllib.parse.urlencode({"database": self.database, "query": query})
        request = urllib.request.Request(
            f"{self.base_url}/?{params}",
            data=data.encode() if data is not None else None,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310
            return response.read()

    def insert_events(self, events: list[dict[str, Any]]) -> None:
        if not events:
            return
        payload = "\n".join(json.dumps(event, separators=(",", ":")) for event in events)
        self.execute("INSERT INTO logsight.events FORMAT JSONEachRow", payload)


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
            return json.loads(response.read().decode())
