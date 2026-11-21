"""Offline staging alert-delivery evidence gate; performs no network actions."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must have UTC offset")
    return parsed


def assess_alert_delivery(record: dict[str, Any]) -> dict[str, Any]:
    """Validate a declared alert acknowledgment drill, not its authenticity."""
    if not isinstance(record, dict):
        raise ValueError("alert evidence must be an object")
    for field in (
        "environment",
        "operator",
        "reviewer",
        "approval_ticket",
        "git_revision",
        "image_digest",
        "alert_name",
        "receiver_reference",
    ):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} is required")
    if record["environment"].strip().lower() in {"prod", "production"}:
        raise ValueError("production alert drills are not accepted")
    for field in ("source_observed", "alert_fired", "receiver_delivered", "operator_acknowledged"):
        if record.get(field) is not True:
            raise ValueError(f"{field} must be explicitly true")
    limit = record.get("approved_max_ack_seconds")
    if type(limit) is not int or limit < 1:
        raise ValueError("approved_max_ack_seconds must be a positive integer")
    links = record.get("evidence_links")
    if (
        not isinstance(links, list)
        or not links
        or any(not isinstance(link, str) or not link.startswith("https://") for link in links)
    ):
        raise ValueError("evidence_links must be HTTPS references")
    start = _utc(record.get("signal_at_utc"), "signal_at_utc")
    fired = _utc(record.get("fired_at_utc"), "fired_at_utc")
    delivered = _utc(record.get("delivered_at_utc"), "delivered_at_utc")
    acknowledged = _utc(record.get("acknowledged_at_utc"), "acknowledged_at_utc")
    if not start <= fired <= delivered <= acknowledged:
        raise ValueError("signal, firing, delivery and acknowledgment must be ordered")
    elapsed = (acknowledged - start).total_seconds()
    return {
        "status": "pass" if elapsed <= limit else "fail",
        "signal_to_ack_seconds": elapsed,
        "meets_approved_ack_window": elapsed <= limit,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a staging alert-drill evidence record")
    parser.add_argument("record", type=Path)
    args = parser.parse_args()
    try:
        result = assess_alert_delivery(json.loads(args.record.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"invalid alert evidence: {exc}\n")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
