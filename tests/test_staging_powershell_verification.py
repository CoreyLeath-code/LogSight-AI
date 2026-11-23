"""Static local-staging verifier checks; never use Windows or Kubernetes in CI."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/verify_local_staging.ps1"


def test_verifier_is_pinned_to_named_local_cluster() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert "kind get clusters" in script
    assert "logsight-staging-alerts" in script
    assert "kind-$cluster" in script
    assert "logsight-staging" in script
    assert "--context $context -n $namespace" in script
    assert "No alternate context will be inspected" in script


def test_verifier_only_reads_deployments_services_and_local_receipt() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert "@('get', 'deployment', $name)" in script
    assert "@('get', 'service', $name)" in script
    assert "'ClusterIP'" in script
    assert "'http://127.0.0.1:8080/receipts'" in script
    assert "external_delivery_verified = $false" in script
    assert "human_acknowledgment_verified = $false" in script
    for mutating_command in ("kubectl apply", "kubectl delete", "kubectl patch", "kind create"):
        assert mutating_command not in script


def test_receipt_check_requires_explicit_synthetic_id() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert "ValidatePattern('^[a-z0-9][a-z0-9-]{5,39}$')" in script
    assert "if ($DrillId)" in script
    assert "$_.drill_id -eq $DrillId" in script
    assert "exit 1" in script
