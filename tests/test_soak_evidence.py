"""Offline acceptance tests use synthetic records, not a running cluster."""

from __future__ import annotations

import pytest

from logsight.soak_evidence import assess_soak_evidence


def sample() -> dict[str, object]:
    return {
        "environment": "isolated-staging",
        "operator": "operator",
        "reviewer": "reviewer",
        "approval_ticket": "CHANGE-123",
        "git_revision": "a" * 40,
        "image_digest": "sha256:" + "a" * 64,
        "load_profile_reference": "synthetic-load-profile",
        "requests_total": 1000,
        "requests_successful": 995,
        "requests_failed": 5,
        "duration_seconds": 3600,
        "p95_latency_ms": 120,
        "approved_min_success_ratio": 0.99,
        "approved_max_p95_latency_ms": 250,
        "approved_min_duration_seconds": 1800,
        "dependency_recovery_verified": True,
        "evidence_links": ["https://example.invalid/restricted-evidence"],
    }


def test_synthetic_soak_passes() -> None:
    report = assess_soak_evidence(sample())
    assert report["status"] == "pass"
    assert report["success_ratio"] == 0.995


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("requests_successful", 900),
        ("p95_latency_ms", 300),
        ("duration_seconds", 300),
    ],
)
def test_soak_objective_failure(field: str, value: object) -> None:
    record = sample()
    if field == "requests_successful":
        record["requests_failed"] = 100
    record[field] = value
    assert assess_soak_evidence(record)["status"] == "fail"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("environment", "production"),
        ("duration_seconds", 0),
        ("requests_total", 0),
        ("requests_total", True),
        ("dependency_recovery_verified", False),
        ("evidence_links", []),
        ("evidence_links", ["http://insecure.example"]),
        ("approved_min_success_ratio", 1.2),
        ("reviewer", ""),
    ],
)
def test_incomplete_or_unsafe_soak_evidence_rejected(field: str, value: object) -> None:
    record = sample()
    record[field] = value
    with pytest.raises(ValueError):
        assess_soak_evidence(record)


def test_counter_mismatch_rejected() -> None:
    record = sample()
    record["requests_failed"] = 4
    with pytest.raises(ValueError, match="counts must equal"):
        assess_soak_evidence(record)
