"""Offline semantic checks for opt-in Helm monitoring resources.

This checks rendered manifest consistency, not live scrape behavior.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


def _labels_match(selector: dict[str, str], labels: dict[str, str]) -> bool:
    return bool(selector) and all(labels.get(key) == value for key, value in selector.items())


def check_monitoring_contract(documents: list[dict[str, Any]]) -> None:
    """Fail closed when monitoring targets, credentials or ingress disagree."""
    by_kind = {doc.get("kind"): doc for doc in documents if isinstance(doc, dict)}
    required = {"Service", "Deployment", "ServiceMonitor", "NetworkPolicy"}
    if not required.issubset(by_kind):
        raise ValueError("missing required monitoring resources")
    service = by_kind["Service"]
    deployment = by_kind["Deployment"]
    monitor = by_kind["ServiceMonitor"]
    policy = by_kind["NetworkPolicy"]

    service_selector = service["spec"]["selector"]
    pod_labels = deployment["spec"]["template"]["metadata"]["labels"]
    if not _labels_match(service_selector, pod_labels):
        raise ValueError("Service selector does not match API pod labels")
    monitor_selector = monitor["spec"]["selector"]["matchLabels"]
    service_labels = service["metadata"]["labels"]
    if not _labels_match(monitor_selector, service_labels):
        raise ValueError("ServiceMonitor selector does not match Service labels")

    endpoints = monitor["spec"]["endpoints"]
    if len(endpoints) != 1:
        raise ValueError("expected one monitored API endpoint")
    endpoint = endpoints[0]
    ports = service["spec"]["ports"]
    if not any(port.get("name") == endpoint.get("port") for port in ports):
        raise ValueError("monitor endpoint does not match a named Service port")
    if endpoint.get("path") != "/metrics":
        raise ValueError("monitor must use the guarded /metrics path")

    container = deployment["spec"]["template"]["spec"]["containers"][0]
    environment = {item["name"]: item for item in container["env"]}
    auth = environment.get("LOGSIGHT_API_AUTH_MODE", {})
    if auth.get("value") != "token":
        raise ValueError("monitor-enabled API must require bearer auth")
    token = environment.get("LOGSIGHT_API_TOKEN", {})
    selector = token.get("valueFrom", {}).get("secretKeyRef", {})
    credential = endpoint.get("authorization", {}).get("credentials", {})
    if (
        not selector.get("name")
        or not selector.get("key")
        or selector.get("name") != credential.get("name")
        or selector.get("key") != credential.get("key")
    ):
        raise ValueError("API and ServiceMonitor must reference the same Secret key")
    if not _labels_match(policy["spec"]["podSelector"]["matchLabels"], pod_labels):
        raise ValueError("NetworkPolicy does not select monitored API pods")

    target_port = next(port["port"] for port in ports if port.get("name") == endpoint["port"])
    monitoring_rules = [
        rule
        for rule in policy["spec"].get("ingress", [])
        if any(
            entry.get("protocol") == "TCP" and entry.get("port") == target_port
            for entry in rule.get("ports", [])
        )
        and any(
            peer.get("namespaceSelector", {}).get("matchLabels")
            and peer.get("podSelector", {}).get("matchLabels")
            for peer in rule.get("from", [])
        )
    ]
    if not monitoring_rules:
        raise ValueError("no namespace- and pod-restricted monitoring ingress rule")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check rendered Helm monitoring contract")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        documents = list(yaml.safe_load_all(args.manifest.read_text(encoding="utf-8")))
        check_monitoring_contract(documents)
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        parser.exit(2, f"invalid monitoring manifest contract: {exc}\n")
    print("monitoring manifest contract: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
