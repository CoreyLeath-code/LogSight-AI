"""Offline tests mock kubectl: no actual cluster access in CI."""

from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest

from scripts import staging_cluster_snapshot as snapshot


IMAGE = "registry.example/logsight-ai@sha256:" + "a" * 64


def deployment() -> dict[str, object]:
    return {
        "metadata": {"name": "logsight-ai", "generation": 3},
        "spec": {
            "replicas": 2,
            "template": {"spec": {"containers": [{"name": "logsight", "image": IMAGE}]}},
        },
        "status": {"readyReplicas": 2, "updatedReplicas": 2, "observedGeneration": 3},
    }


@pytest.mark.parametrize(
    ("context", "namespace"),
    [
        ("production-us-east", "logsight"),
        ("prod", "staging"),
        ("staging", "live-namespace"),
        ("cluster", "logsight"),
        ("staging;rm", "logsight"),
    ],
)
def test_rejects_invalid_or_nonstaging_scopes(context: str, namespace: str) -> None:
    with pytest.raises(ValueError):
        snapshot.validate_scope(context, namespace, "logsight-ai")


def test_valid_staging_scope() -> None:
    snapshot.validate_scope("test-staging", "logsight", "logsight-ai")


def test_digest_pinning_and_rollout_pass() -> None:
    assert snapshot.summarize_deployment(deployment(), IMAGE)["status"] == "pass"


@pytest.mark.parametrize("condition", ["tag", "ready", "stale", "image"])
def test_incomplete_rollout_fails(condition: str) -> None:
    doc = deployment()
    if condition == "tag":
        doc["spec"]["template"]["spec"]["containers"][0]["image"] = "logsight:latest"
    if condition == "ready":
        doc["status"]["readyReplicas"] = 1
    if condition == "stale":
        doc["status"]["observedGeneration"] = 2
    if condition == "image":
        doc["spec"]["template"]["spec"]["containers"][0]["image"] = (
            "registry.example/logsight-ai@sha256:" + "b" * 64
        )
    assert snapshot.summarize_deployment(doc, IMAGE)["status"] == "fail"


def test_rejects_bad_expected_image() -> None:
    with pytest.raises(ValueError):
        snapshot.summarize_deployment(deployment(), "logsight:latest")


def test_reads_explicit_cluster_with_only_get(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append(args)
        return SimpleNamespace(stdout=json.dumps(deployment()))

    monkeypatch.setattr(snapshot.subprocess, "run", fake_run)
    report = snapshot.read_snapshot("my-staging", "logsight", "logsight-ai", IMAGE)
    assert report["status"] == "pass"
    assert calls[0][:5] == [
        "kubectl",
        "--context",
        "my-staging",
        "--namespace",
        "logsight",
    ]
    assert "get" in calls[0]
    assert not any(value in calls[0] for value in ("apply", "patch", "delete"))


def test_kubectl_failure_does_not_expose_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(*args: object, **kwargs: object) -> None:
        raise subprocess.CalledProcessError(1, "kubectl", stderr="secret text")

    monkeypatch.setattr(snapshot.subprocess, "run", denied)
    with pytest.raises(ValueError, match="confirm staging RBAC") as error:
        snapshot.read_snapshot("my-staging", "logsight", "logsight-ai", IMAGE)
    assert "secret text" not in str(error.value)


def test_malformed_kubectl_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        snapshot.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout="{")
    )
    with pytest.raises(ValueError, match="invalid JSON"):
        snapshot.read_snapshot("my-staging", "logsight", "logsight-ai", IMAGE)
