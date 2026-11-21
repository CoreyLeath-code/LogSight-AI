"""Guardrails for the existing Helm HA defaults; not a live disruption test."""

from __future__ import annotations

from pathlib import Path

import yaml

CHART = Path(__file__).resolve().parents[1] / "charts" / "logsight-ai"


def test_default_ha_values_have_safe_minimum_capacity() -> None:
    values = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))
    autoscaling = values["autoscaling"]
    pdb = values["podDisruptionBudget"]
    assert autoscaling["enabled"] is True
    assert 2 <= autoscaling["minReplicas"] <= autoscaling["maxReplicas"]
    assert pdb["enabled"] is True
    assert 1 <= pdb["minAvailable"] < autoscaling["minReplicas"]
    assert values["probes"]["readiness"]["failureThreshold"] >= 1
    assert values["probes"]["liveness"]["failureThreshold"] >= 1


def test_hpa_pdb_and_probes_are_rendered_from_chart_configuration() -> None:
    hpa = (CHART / "templates" / "hpa.yaml").read_text(encoding="utf-8")
    pdb = (CHART / "templates" / "pdb.yaml").read_text(encoding="utf-8")
    deployment = (CHART / "templates" / "deployment.yaml").read_text(
        encoding="utf-8"
    )
    assert "kind: HorizontalPodAutoscaler" in hpa
    assert ".Values.autoscaling.minReplicas" in hpa
    assert "kind: PodDisruptionBudget" in pdb
    assert ".Values.podDisruptionBudget.minAvailable" in pdb
    assert "path: /ready" in deployment
    assert "path: /health" in deployment
