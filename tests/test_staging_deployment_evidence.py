"""Synthetic rollout evidence does not represent a real staging deployment."""

from __future__ import annotations

import pytest

from scripts.validate_staging_deployment_evidence import assess_staging_deployment


def sample() -> dict[str, object]:
    image = "registry.example/logsight-ai@sha256:" + "a" * 64
    return {
        "environment": "isolated-staging",
        "namespace": "logsight-staging",
        "operator": "engineer-a",
        "reviewer": "engineer-b",
        "approval_ticket": "STAGING-123",
        "helm_release": "logsight-ai",
        "values_revision": "approved-values-commit",
        "git_revision": "b" * 40,
        "expected_image": image,
        "observed_image": image,
        "desired_replicas": 2,
        "ready_replicas": 2,
        "updated_replicas": 2,
        "rollout_completed": True,
        "authenticated_scrape_observed": True,
        "rollout_started_at_utc": "2026-11-22T16:00:00Z",
        "rollout_finished_at_utc": "2026-11-22T16:03:00Z",
        "evidence_links": ["https://example.invalid/restricted-rollout-evidence"],
    }


def test_synthetic_staging_record_passes() -> None:
    assert assess_staging_deployment(sample())["status"] == "pass"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("environment", "production"),
        ("operator", "engineer-b"),
        ("git_revision", "short"),
        ("expected_image", "registry.example/logsight-ai:latest"),
        ("observed_image", "registry.example/logsight-ai@sha256:" + "c" * 64),
        ("desired_replicas", 0),
        ("desired_replicas", True),
        ("ready_replicas", -1),
        ("updated_replicas", "2"),
        ("rollout_completed", False),
        ("authenticated_scrape_observed", False),
        ("rollout_finished_at_utc", "2026-11-22T15:00:00Z"),
        ("rollout_finished_at_utc", "2026-11-22T17:00:00+01:00"),
        ("evidence_links", ["http://example.invalid/evidence"]),
        ("reviewer", ""),
    ],
)
def test_invalid_deployment_record_rejected(field: str, value: object) -> None:
    record = sample()
    record[field] = value
    with pytest.raises(ValueError):
        assess_staging_deployment(record)


def test_incomplete_rollout_fails_objective() -> None:
    record = sample()
    record["ready_replicas"] = 1
    assert assess_staging_deployment(record)["status"] == "fail"
    record = sample()
    record["updated_replicas"] = 1
    assert assess_staging_deployment(record)["status"] == "fail"


def test_missing_evidence_field_rejected() -> None:
    record = sample()
    del record["approval_ticket"]
    with pytest.raises(ValueError, match="approval_ticket"):
        assess_staging_deployment(record)
