"""Read-only selected staging Pod image and readiness observations.

Observations are evidence, not proof of OCI manifest/config digest equivalence.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from scripts.staging_cluster_snapshot import validate_scope

_IMAGE = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
_LABEL = re.compile(r"^[A-Za-z0-9_.-]{1,63}$")


def inspect_pods(
    payload: dict[str, Any], expected_image: str, container_name: str, min_ready: int
) -> dict[str, Any]:
    """Assess only selected target containers; never inspect env or Pod logs."""
    if not _IMAGE.fullmatch(expected_image):
        raise ValueError("expected_image must be a digest-pinned OCI reference")
    if not _LABEL.fullmatch(container_name):
        raise ValueError("container_name must be a simple name")
    if type(min_ready) is not int or min_ready < 1:
        raise ValueError("min_ready must be a positive integer")
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("Pod response has no items list")

    observations: list[dict[str, Any]] = []
    for pod in items:
        if not isinstance(pod, dict):
            raise ValueError("invalid Pod item")
        metadata = pod.get("metadata", {})
        spec = pod.get("spec", {})
        status = pod.get("status", {})
        containers = [
            c for c in spec.get("containers", []) if c.get("name") == container_name
        ]
        if len(containers) != 1:
            raise ValueError("selected Pod missing a unique target container")
        statuses = [
            c for c in status.get("containerStatuses", []) if c.get("name") == container_name
        ]
        if len(statuses) != 1:
            raise ValueError("target container status missing")
        container = containers[0]
        container_status = statuses[0]
        image_id = container_status.get("imageID")
        if not isinstance(image_id, str) or not image_id.strip():
            raise ValueError("target container imageID missing")
        ready = container_status.get("ready") is True
        spec_image = container.get("image")
        observations.append(
            {
                "pod": metadata.get("name"),
                "phase": status.get("phase"),
                "specified_image": spec_image,
                "runtime_image_id": image_id,
                "ready": ready,
                "spec_matches_expected": spec_image == expected_image,
            }
        )
    ready_count = sum(
        row["ready"] and row["spec_matches_expected"] and row["phase"] == "Running"
        for row in observations
    )
    healthy = bool(observations) and ready_count >= min_ready and all(
        row["ready"] and row["spec_matches_expected"] and row["phase"] == "Running"
        for row in observations
    )
    return {
        "status": "pass" if healthy else "fail",
        "expected_image": expected_image,
        "target_container": container_name,
        "minimum_ready": min_ready,
        "observed_pod_count": len(observations),
        "matching_ready_pod_count": ready_count,
        "pods": observations,
        "image_id_digest_equivalence_verified": False,
    }


def read_pod_snapshot(
    context: str,
    namespace: str,
    deployment: str,
    container_name: str,
    expected_image: str,
    min_ready: int,
) -> dict[str, Any]:
    """Read Deployment selector then its selected Pod metadata and status."""
    validate_scope(context, namespace, deployment)
    if not _LABEL.fullmatch(container_name):
        raise ValueError("invalid container name")
    common = ["kubectl", "--context", context, "--namespace", namespace, "--request-timeout=10s"]

    def get_json(arguments: list[str]) -> dict[str, Any]:
        try:
            result = subprocess.run(  # noqa: S603
                [*common, "get", *arguments, "-o", "json"],
                capture_output=True,
                check=True,
                text=True,
                timeout=15,
            )
            data = json.loads(result.stdout)
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise ValueError("read-only kubectl query failed; check staging RBAC") from exc
        except json.JSONDecodeError as exc:
            raise ValueError("kubectl returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise ValueError("kubectl returned a non-object response")
        return data

    deploy = get_json(["deployment", deployment])
    selector = deploy.get("spec", {}).get("selector", {})
    match = selector.get("matchLabels")
    if (
        not isinstance(match, dict)
        or not match
        or any(
            not isinstance(key, str)
            or not isinstance(value, str)
            or not key
            or not value
            or "," in key
            or "," in value
            for key, value in match.items()
        )
        or selector.get("matchExpressions")
    ):
        raise ValueError("Deployment needs nonempty simple matchLabels with no expressions")
    label_selector = ",".join(f"{key}={value}" for key, value in sorted(match.items()))
    pods = get_json(["pods", "--selector", label_selector])
    result = inspect_pods(pods, expected_image, container_name, min_ready)
    result["context"] = context
    result["namespace"] = namespace
    result["deployment"] = deployment
    result["label_selector"] = label_selector
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only staging Pod image evidence")
    parser.add_argument("--context", required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--deployment", required=True)
    parser.add_argument("--container", required=True)
    parser.add_argument("--expected-image", required=True)
    parser.add_argument("--minimum-ready", type=int, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        record = read_pod_snapshot(
            args.context,
            args.namespace,
            args.deployment,
            args.container,
            args.expected_image,
            args.minimum_ready,
        )
    except ValueError as exc:
        parser.exit(2, f"staging Pod snapshot rejected: {exc}\n")
    output = json.dumps(record, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0 if record["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
