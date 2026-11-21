"""Negative semantic tests for chart monitoring wiring, using fake manifests."""

from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.validate_monitoring_manifests import check_monitoring_contract


def manifests() -> list[dict[str, object]]:
    return [
        {
            "kind": "Service",
            "metadata": {"labels": {"app": "logsight"}},
            "spec": {"selector": {"app": "logsight"}, "ports": [{"name": "http", "port": 8000}]},
        },
        {
            "kind": "Deployment",
            "spec": {
                "template": {
                    "metadata": {"labels": {"app": "logsight"}},
                    "spec": {
                        "containers": [
                            {
                                "env": [
                                    {"name": "LOGSIGHT_API_AUTH_MODE", "value": "token"},
                                    {
                                        "name": "LOGSIGHT_API_TOKEN",
                                        "valueFrom": {
                                            "secretKeyRef": {"name": "scrape", "key": "token"}
                                        },
                                    },
                                ]
                            }
                        ]
                    },
                }
            },
        },
        {
            "kind": "ServiceMonitor",
            "spec": {
                "selector": {"matchLabels": {"app": "logsight"}},
                "endpoints": [
                    {
                        "port": "http",
                        "path": "/metrics",
                        "authorization": {
                            "credentials": {"name": "scrape", "key": "token"}
                        },
                    }
                ],
            },
        },
        {
            "kind": "NetworkPolicy",
            "spec": {
                "podSelector": {"matchLabels": {"app": "logsight"}},
                "ingress": [
                    {
                        "ports": [{"protocol": "TCP", "port": 8000}],
                        "from": [
                            {
                                "namespaceSelector": {"matchLabels": {"name": "monitoring"}},
                                "podSelector": {"matchLabels": {"app": "prometheus"}},
                            }
                        ],
                    }
                ],
            },
        },
    ]


def test_valid_monitoring_contract() -> None:
    check_monitoring_contract(manifests())


@pytest.mark.parametrize("broken", ["service", "auth", "secret", "monitor", "network"])
def test_monitoring_contract_rejects_inconsistent_resources(broken: str) -> None:
    docs = deepcopy(manifests())
    if broken == "service":
        docs[0]["spec"]["selector"] = {"app": "other"}
    elif broken == "auth":
        docs[1]["spec"]["template"]["spec"]["containers"][0]["env"][0]["value"] = "disabled"
    elif broken == "secret":
        docs[2]["spec"]["endpoints"][0]["authorization"]["credentials"]["key"] = "wrong"
    elif broken == "monitor":
        docs[2]["spec"]["endpoints"][0]["path"] = "/not-metrics"
    elif broken == "network":
        docs[3]["spec"]["ingress"][0]["from"][0]["podSelector"] = {}
    with pytest.raises(ValueError):
        check_monitoring_contract(docs)
