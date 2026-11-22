"""Offline synthetic receiver contract tests; no Kubernetes is accessed."""

from __future__ import annotations

import pytest

from scripts.staging_test_receiver import ALERT_NAME, sanitized_receipts


def notification() -> dict[str, object]:
    return {
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": ALERT_NAME,
                    "environment": "staging",
                    "logsight_drill_id": "staging-drill-abc123",
                },
            }
        ],
    }


def test_accepts_only_synthetic_firing_staging_alert() -> None:
    assert sanitized_receipts(notification(), "2026-11-22T00:00:00Z") == [
        {
            "drill_id": "staging-drill-abc123",
            "received_at_utc": "2026-11-22T00:00:00Z",
        }
    ]


@pytest.mark.parametrize("change", ["wrong_name", "wrong_environment", "resolved", "unsafe_id"])
def test_rejects_non_drill_notifications(change: str) -> None:
    payload = notification()
    alert = payload["alerts"][0]
    if change == "wrong_name":
        alert["labels"]["alertname"] = "ProductionOutage"
    if change == "wrong_environment":
        alert["labels"]["environment"] = "production"
    if change == "resolved":
        alert["status"] = "resolved"
    if change == "unsafe_id":
        alert["labels"]["logsight_drill_id"] = "../unsafe"
    with pytest.raises(ValueError):
        sanitized_receipts(payload, "2026-11-22T00:00:00Z")


def test_empty_notification_rejected() -> None:
    with pytest.raises(ValueError):
        sanitized_receipts({"status": "firing", "alerts": []}, "2026-11-22T00:00:00Z")
