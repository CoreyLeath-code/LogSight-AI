"""Explicitly approved synthetic Alertmanager staging delivery drill.

Dry-run by default. Does not claim receiver delivery or operator acknowledgment.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPSHandler, Request, build_opener

from scripts.staging_prometheus_target import _NoRedirect, validate_prometheus_url

_DRILL_ID = re.compile(r"^[a-z0-9][a-z0-9-]{5,39}$")
_TICKET = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{3,79}$")
_ALERT = "LogSightStagingSyntheticDeliveryDrill"


def make_drill(drill_id: str, approval_ticket: str, now: datetime) -> dict[str, Any]:
    """Create a synthetic, bounded-lifetime alert with no sensitive payload."""
    if not _DRILL_ID.fullmatch(drill_id):
        raise ValueError("drill_id must be 6-40 lowercase characters, digits or dashes")
    if not _TICKET.fullmatch(approval_ticket):
        raise ValueError("approval_ticket must be a simple change-control identifier")
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise ValueError("drill timestamp must be UTC")
    start = now.isoformat().replace("+00:00", "Z")
    end = (now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    return {
        "labels": {
            "alertname": _ALERT,
            "severity": "info",
            "environment": "staging",
            "logsight_drill_id": drill_id,
        },
        "annotations": {
            "summary": "Authorized synthetic LogSight staging notification delivery test",
        },
        "startsAt": start,
        "endsAt": end,
    }


def check_staging_endpoint(base_url: str) -> str:
    """Require an obvious staging hostname (or explicit loopback test fixture)."""
    base = validate_prometheus_url(base_url)
    parsed = urlsplit(base)
    host = parsed.hostname or ""
    if host not in {"localhost", "127.0.0.1", "::1"} and not (
        "staging" in host.lower() or "stage" in host.lower()
    ):
        raise ValueError("Alertmanager URL hostname must explicitly identify staging")
    return base


def submit_drill(
    base_url: str,
    token: str,
    drill: dict[str, Any],
    approval_ticket: str,
    approved_ticket_from_env: str,
    execute: bool,
    confirmation: str,
) -> dict[str, Any]:
    """Only send after opt-in plus matching approval; never follow redirects."""
    base = check_staging_endpoint(base_url)
    if not execute:
        return {
            "status": "dry_run",
            "alert_name": _ALERT,
            "drill_id": drill["labels"]["logsight_drill_id"],
            "receiver_delivery_verified": False,
            "operator_acknowledgment_verified": False,
        }
    if confirmation != "SEND_SYNTHETIC_STAGING_ALERT":
        raise ValueError("explicit confirmation phrase is required")
    if not approved_ticket_from_env or approved_ticket_from_env != approval_ticket:
        raise ValueError("matching approval ticket must be present in environment")
    if not token:
        raise ValueError("ALERTMANAGER_STAGING_TOKEN must be set for execution")
    request = Request(
        base + "/api/v2/alerts",
        data=json.dumps([drill], separators=(",", ":")).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    opener = build_opener(_NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(request, timeout=8) as response:
            if response.status not in {200, 202}:
                raise ValueError("Alertmanager did not accept synthetic drill")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ValueError("Alertmanager staging drill submission failed") from exc
    return {
        "status": "submitted_not_delivered",
        "alert_name": _ALERT,
        "drill_id": drill["labels"]["logsight_drill_id"],
        "receiver_delivery_verified": False,
        "operator_acknowledgment_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Approval-gated synthetic staging alert drill")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--drill-id", required=True)
    parser.add_argument("--approval-ticket", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    try:
        drill = make_drill(args.drill_id, args.approval_ticket, datetime.now(timezone.utc))
        result = submit_drill(
            args.base_url,
            os.environ.get("ALERTMANAGER_STAGING_TOKEN", ""),
            drill,
            args.approval_ticket,
            os.environ.get("LOGSIGHT_STAGING_DRILL_APPROVAL_TICKET", ""),
            args.execute,
            args.confirm,
        )
    except ValueError as exc:
        parser.exit(2, f"staging drill rejected: {exc}\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
