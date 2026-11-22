#!/usr/bin/env bash
set -euo pipefail

CLUSTER="logsight-staging-alerts"
CONTEXT="kind-${CLUSTER}"
NAMESPACE="logsight-staging"

if [[ "${1:-}" != "--execute" || "$#" != 1 ]]; then
  echo "PLAN ONLY: creates a new local kind cluster '${CLUSTER}' with a test-only Alertmanager and in-memory webhook receiver."
  echo "Requires local Docker, kind, kubectl. No production notifications or cloud Kubernetes access."
  echo "Run explicitly with: bash scripts/bootstrap_local_staging_alerts.sh --execute"
  exit 0
fi

for command in docker kind kubectl; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Missing required executable: $command" >&2
    exit 2
  fi
done
if ! docker info >/dev/null 2>&1; then
  echo "Local Docker daemon is not available" >&2
  exit 2
fi
if kind get clusters | grep -Fxq "$CLUSTER"; then
  echo "Refusing to change an existing kind cluster: $CLUSTER" >&2
  exit 2
fi
if [[ ! -f deploy/staging/kind-config.yaml || ! -f deploy/staging/kind-alerts.yaml ]]; then
  echo "Run from the repository root" >&2
  exit 2
fi

kind create cluster --name "$CLUSTER" --config deploy/staging/kind-config.yaml
kubectl --context "$CONTEXT" apply -f deploy/staging/kind-alerts.yaml
kubectl --context "$CONTEXT" -n "$NAMESPACE" create configmap staging-receiver-code \
  --from-file=staging_test_receiver.py=scripts/staging_test_receiver.py \
  --dry-run=client -o yaml | kubectl --context "$CONTEXT" -n "$NAMESPACE" apply -f -
kubectl --context "$CONTEXT" -n "$NAMESPACE" rollout status deployment/staging-receiver --timeout=180s
kubectl --context "$CONTEXT" -n "$NAMESPACE" rollout status deployment/staging-alertmanager --timeout=180s

echo "Local kind staging infrastructure is ready for operator verification."
echo "Run two separate port-forwards bound to localhost:"
echo "kubectl --context $CONTEXT -n $NAMESPACE port-forward --address 127.0.0.1 svc/staging-alertmanager 9093:9093"
echo "kubectl --context $CONTEXT -n $NAMESPACE port-forward --address 127.0.0.1 svc/staging-receiver 8080:8080"
echo "No synthetic alert was submitted and no human acknowledgment was recorded."
