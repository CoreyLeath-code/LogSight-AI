"""Memory-only test sink for synthetic local kind Alertmanager notifications.

Never deploy to production. No real page, durable storage or human ack.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from typing import Any

ALERT_NAME = "LogSightStagingSyntheticDeliveryDrill"
MAX_BODY = 65536
MAX_RECEIPTS = 100
_receipts: list[dict[str, str]] = []
_lock = Lock()


def sanitized_receipts(payload: Any, received_at: str) -> list[dict[str, str]]:
    """Keep only whitelisted synthetic drill identifiers and receive times."""
    if not isinstance(payload, dict) or payload.get("status") != "firing":
        raise ValueError("only firing Alertmanager notifications are accepted")
    alerts = payload.get("alerts")
    if not isinstance(alerts, list) or not alerts:
        raise ValueError("at least one alert is required")
    result: list[dict[str, str]] = []
    for alert in alerts:
        if not isinstance(alert, dict) or not isinstance(alert.get("labels"), dict):
            raise ValueError("invalid alert")
        labels = alert["labels"]
        drill_id = labels.get("logsight_drill_id")
        if (
            labels.get("alertname") != ALERT_NAME
            or labels.get("environment") != "staging"
            or alert.get("status") != "firing"
            or not isinstance(drill_id, str)
            or not (6 <= len(drill_id) <= 40)
            or any(
                character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in drill_id
            )
        ):
            raise ValueError("non-synthetic alert rejected")
        result.append({"drill_id": drill_id, "received_at_utc": received_at})
    return result


class Receiver(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        """Never log request URLs, bodies or network identities."""

    def _respond(self, code: int, value: dict[str, Any]) -> None:
        body = json.dumps(value, sort_keys=True).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._respond(200, {"status": "ok"})
        elif self.path == "/receipts":
            with _lock:
                recent = list(_receipts)
            self._respond(200, {"receipts": recent, "human_acknowledged": False})
        else:
            self._respond(404, {"status": "not_found"})

    def do_POST(self) -> None:
        if self.path != "/alertmanager":
            self._respond(404, {"status": "not_found"})
            return
        length = self.headers.get("Content-Length", "")
        if not length.isdecimal() or not (0 < int(length) <= MAX_BODY):
            self._respond(413, {"status": "invalid_size"})
            return
        try:
            payload = json.loads(self.rfile.read(int(length)))
            timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            entries = sanitized_receipts(payload, timestamp)
        except (ValueError, UnicodeDecodeError):
            self._respond(400, {"status": "invalid_synthetic_notification"})
            return
        with _lock:
            _receipts.extend(entries)
            del _receipts[:-MAX_RECEIPTS]
        self._respond(200, {"status": "received"})


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8080), Receiver)
    server.serve_forever()


if __name__ == "__main__":
    main()
