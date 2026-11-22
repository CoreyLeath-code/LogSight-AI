"""Pod snapshot tests use fake kubectl responses and no cluster connectivity."""

from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest

from scripts import staging_pod_image_snapshot as snapshot

IMAGE = "registry.example/logsight-ai@sha256:" + "a" * 64


def pod(name: str = "logsight-123") -> dict[str, object]:
    return {
        "metadata": {"name": name},
        "spec": {"containers": [{"name": "logsight-api", "image": IMAGE}]},
        "status": {
            "phase": "Running",
            "containerStatuses": [
                {
                    "name": "logsight-api",
                    "ready": True,
                    "imageID": "containerd://sha256:" + "b" * 64,
                }
            ],
        },
    }


def test_valid_pod_observations_remain_evidence_only() -> None:
    result = snapshot.inspect_pods({"items": [pod()]}, IMAGE, "logsight-api", 1)
    assert result["status"] == "pass"
    assert result["image_id_digest_equivalence_verified"] is False
    assert result["pods"][0]["runtime_image_id"].startswith("containerd://")


@pytest.mark.parametrize("broken", ["empty", "not_ready", "tag", "phase"])
def test_pods_fail_on_unready_or_incorrect_images(broken: str) -> None:
    item = pod()
    if broken == "empty":
        collection = {"items": []}
    else:
        if broken == "not_ready":
            item["status"]["containerStatuses"][0]["ready"] = False
        if broken == "tag":
            item["spec"]["containers"][0]["image"] = "logsight:latest"
        if broken == "phase":
            item["status"]["phase"] = "Pending"
        collection = {"items": [item]}
    assert snapshot.inspect_pods(collection, IMAGE, "logsight-api", 1)["status"] == "fail"


@pytest.mark.parametrize("broken", ["image_id", "container", "status", "count"])
def test_invalid_pod_evidence_is_rejected(broken: str) -> None:
    item = pod()
    count = 1
    if broken == "image_id":
        item["status"]["containerStatuses"][0]["imageID"] = ""
    if broken == "container":
        item["spec"]["containers"] = []
    if broken == "status":
        item["status"]["containerStatuses"] = []
    if broken == "count":
        count = 0
    with pytest.raises(ValueError):
        snapshot.inspect_pods({"items": [item]}, IMAGE, "logsight-api", count)


def test_read_only_queries_use_explicit_staging_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []
    deployment = {
        "spec": {"selector": {"matchLabels": {"app": "logsight", "tier": "api"}}}
    }

    def fake_run(args: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append(args)
        payload = deployment if "deployment" in args else {"items": [pod()]}
        return SimpleNamespace(stdout=json.dumps(payload))

    monkeypatch.setattr(snapshot.subprocess, "run", fake_run)
    result = snapshot.read_pod_snapshot(
        "cluster-staging", "logsight", "logsight-ai", "logsight-api", IMAGE, 1
    )
    assert result["status"] == "pass"
    assert len(calls) == 2
    assert all("get" in args and "--context" in args for args in calls)
    assert "app=logsight,tier=api" in calls[-1]
    assert not any("delete" in args or "patch" in args for args in calls)


def test_rejects_unsafe_selector(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(stdout=json.dumps({
            "spec": {"selector": {"matchExpressions": [{"key": "x"}]}}
        }))

    monkeypatch.setattr(snapshot.subprocess, "run", fake_run)
    with pytest.raises(ValueError, match="matchLabels"):
        snapshot.read_pod_snapshot(
            "cluster-staging", "logsight", "logsight-ai", "logsight-api", IMAGE, 1
        )


def test_kubectl_failure_redacts_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*args: object, **kwargs: object) -> None:
        raise subprocess.CalledProcessError(1, "kubectl", stderr="private auth header")

    monkeypatch.setattr(snapshot.subprocess, "run", blocked)
    with pytest.raises(ValueError, match="RBAC") as error:
        snapshot.read_pod_snapshot(
            "cluster-staging", "logsight", "logsight-ai", "logsight-api", IMAGE, 1
        )
    assert "private auth header" not in str(error.value)
