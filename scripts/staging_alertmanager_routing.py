"""Read-only Alertmanager staging alert routing observation.

This does not send a test alert or prove delivery or human acknowledgment.
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, Request, build_opener

from scripts.staging_prometheus_target import _NoRedirect, validate_prometheus_url


def assess_alertmanager_routing(
    payload: list[dict[str, Any]], alert_name: str, receiver_name: str
) -> dict[str, Any]:
    """Check one exact active alert's configured receiver without leaking labels."""
    if not alert_name.strip() or not receiver_name.strip():
        raise ValueError("approved alert and receiver names are required")
    if not isinstance(payload, list):
        raise ValueError("Alertmanager response must be an array")
    matches = [
        alert
        for alert in payload
        if isinstance(alert, dict)
        and isinstance(alert.get("labels"), dict)
        and alert["labels"].get("alertname") == alert_name
    ]
    if len(matches) != 1:
        raise ValueError("expected exactly one matching staging alert")
    observed = matches[0]
    status = observed.get("status")
    receivers = observed.get("receivers")
    if not isinstance(status, dict) or not isinstance(receivers, list):
        raise ValueError("Alertmanager alert status or routing data is missing")
    if any(not isinstance(receiver, dict) for receiver in receivers):
        raise ValueError("Alertmanager returned malformed receivers")
    names = [receiver.get("name") for receiver in receivers]
    if any(not isinstance(name, str) for name in names):
        raise ValueError("Alertmanager receiver name missing")
    active = status.get("state") == "active"
    routed = receiver_name in names
    return {
        "status": "pass" if active and routed else "fail",
        "alert_name": alert_name,
        "expected_receiver": receiver_name,
        "alert_active": active,
        "receiver_assigned": routed,
        "receiver_delivery_verified": False,
        "human_acknowledgment_verified": False,
    }


def observe_alertmanager(
    base_url: str, token: str, alert_name: str, receiver_name: str
) -> dict[str, Any]:
    """Read /api/v2/alerts, requiring verified TLS for non-loopback access."""
    origin = validate_prometheus_url(base_url)
    if not token:
        raise ValueError("ALERTMANAGER_STAGING_TOKEN must be set")
    request = Request(
        origin + "/api/v2/alerts",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    opener = build_opener(_NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(request, timeout=8) as response:
            if response.status != 200:
                raise ValueError("Alertmanager API returned a non-success status")
            body = response.read(1024 * 1024 + 1)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise ValueError("Alertmanager read failed; verify staging access") from exc
    if len(body) > 1024 * 1024:
        raise ValueError("Alertmanager response exceeded size limit")
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("Alertmanager response is not valid JSON") from exc
    if not isinstance(payload, list):
        raise ValueError("Alertmanager response must be an array")
    return assess_alertmanager_routing(payload, alert_name, receiver_name)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only staging Alertmanager routing check")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--alert", required=True)
    parser.add_argument("--receiver", required=True)
    args = parser.parse_args()
    try:
        report = observe_alertmanager(
            args.base_url,
            os.environ.get("ALERTMANAGER_STAGING_TOKEN", ""),
            args.alert,
            args.receiver,
        )
    except ValueError as exc:
        parser.exit(2, f"staging Alertmanager check rejected: {exc}\n")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
