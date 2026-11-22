"""Static local kind safety checks; never creates Kubernetes resources."""

from __future__ import annotations

from pathlib import Path

import yaml

MANIFEST = Path(__file__).resolve().parents[1] / "deploy/staging/kind-alerts.yaml"


def documents() -> list[dict[str, object]]:
    return list(yaml.safe_load_all(MANIFEST.read_text(encoding="utf-8")))


def test_services_are_internal_only_and_staging_scoped() -> None:
    items = documents()
    services = [item for item in items if item["kind"] == "Service"]
    assert {item["metadata"]["name"] for item in services} == {
        "staging-alertmanager",
        "staging-receiver",
    }
    assert all(item["metadata"]["namespace"] == "logsight-staging" for item in services)
    assert all(item["spec"]["type"] == "ClusterIP" for item in services)
    assert not any("nodePort" in port for item in services for port in item["spec"]["ports"])
    assert not any(item["kind"] == "Ingress" for item in items)


def test_only_test_alert_routes_to_webhook() -> None:
    config = next(item for item in documents() if item["kind"] == "ConfigMap")["data"][
        "alertmanager.yml"
    ]
    parsed = yaml.safe_load(config)
    route = parsed["route"]
    assert route["receiver"] == "discard-unmatched"
    assert route["routes"][0]["matchers"] == [
        'alertname="LogSightStagingSyntheticDeliveryDrill"',
        'environment="staging"',
    ]
    receivers = {entry["name"]: entry for entry in parsed["receivers"]}
    assert not receivers["discard-unmatched"].get("webhook_configs")
    webhooks = receivers["staging-test-webhook"]["webhook_configs"]
    assert len(webhooks) == 1
    assert webhooks[0]["url"] == (
        "http://staging-receiver.logsight-staging.svc.cluster.local:8080/alertmanager"
    )


def test_deployments_have_no_api_token_or_external_receiver() -> None:
    items = [item for item in documents() if item["kind"] == "Deployment"]
    assert {item["metadata"]["name"] for item in items} == {
        "staging-alertmanager",
        "staging-receiver",
    }
    for deployment in items:
        spec = deployment["spec"]["template"]["spec"]
        assert spec["automountServiceAccountToken"] is False
        assert spec["securityContext"]["runAsNonRoot"] is True
        for container in spec["containers"]:
            assert container["securityContext"]["readOnlyRootFilesystem"] is True
            assert container["securityContext"]["allowPrivilegeEscalation"] is False
