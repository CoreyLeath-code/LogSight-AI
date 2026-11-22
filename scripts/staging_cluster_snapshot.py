"""Read-only Kubernetes staging Deployment snapshot with explicit context selection.

Only GET operations are issued; no credentials, pod logs or Secret values are saved.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

_SAFE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")
_DIGEST = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")


def validate_scope(context: str, namespace: str, deployment: str) -> None:
    """Require named isolated staging scope; never silently select current context."""
    for name, value in (
        ("context", context),
        ("namespace", namespace),
        ("deployment", deployment),
    ):
        if not _SAFE.fullmatch(value):
            raise ValueError(f"{name} must be a simple explicit identifier")
    lowered = f"{context} {namespace}".lower()
    if "staging" not in lowered and "stage" not in lowered:
        raise ValueError("context or namespace must explicitly identify staging")
    if any(word in lowered for word in ("production", "prod", "live")):
        raise ValueError("production-like scope is not allowed")


def summarize_deployment(document: dict[str, Any], expected_image: str) -> dict[str, Any]:
    """Cross-check the actual Deployment template and rollout status."""
    if not _DIGEST.fullmatch(expected_image):
        raise ValueError("expected_image must be a complete digest-pinned OCI reference")
    metadata = document.get("metadata", {})
    spec = document.get("spec", {})
    status = document.get("status", {})
    containers = spec.get("template", {}).get("spec", {}).get("containers", [])
    images = [container.get("image") for container in containers]
    if not images or any(not isinstance(value, str) for value in images):
        raise ValueError("Deployment has no usable container image references")
    desired = spec.get("replicas", 1)
    ready = status.get("readyReplicas", 0)
    updated = status.get("updatedReplicas", 0)
    observed = status.get("observedGeneration", -1)
    generation = metadata.get("generation", 0)
    if any(
        type(value) is not int or value < 0
        for value in (desired, ready, updated, observed, generation)
    ):
        raise ValueError("invalid Deployment status counts")
    pinned = expected_image in images and all(_DIGEST.fullmatch(value) for value in images)
    healthy = (
        desired > 0 and ready == desired and updated == desired and observed >= generation
    )
    return {
        "deployment": metadata.get("name"),
        "expected_image": expected_image,
        "template_images": images,
        "desired_replicas": desired,
        "ready_replicas": ready,
        "updated_replicas": updated,
        "rollout_observed": observed >= generation,
        "digest_pinned": pinned,
        "status": "pass" if pinned and healthy else "fail",
    }


def read_snapshot(
    context: str, namespace: str, deployment: str, expected_image: str
) -> dict[str, Any]:
    validate_scope(context, namespace, deployment)
    args = [
        "kubectl",
        "--context",
        context,
        "--namespace",
        namespace,
        "--request-timeout=10s",
        "get",
        "deployment",
        deployment,
        "-o",
        "json",
    ]
    try:
        result = subprocess.run(  # noqa: S603
            args,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError("kubectl read failed; confirm staging RBAC and context") from exc
    try:
        document = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("kubectl returned invalid JSON") from exc
    if not isinstance(document, dict):
        raise ValueError("kubectl returned a non-object response")
    report = summarize_deployment(document, expected_image)
    report["context"] = context
    report["namespace"] = namespace
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only staging Deployment inspection")
    parser.add_argument("--context", required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--deployment", required=True)
    parser.add_argument("--expected-image", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = read_snapshot(
            args.context, args.namespace, args.deployment, args.expected_image
        )
    except ValueError as exc:
        parser.exit(2, f"staging snapshot rejected: {exc}\n")
    contents = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(contents, encoding="utf-8")
    else:
        print(contents, end="")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
