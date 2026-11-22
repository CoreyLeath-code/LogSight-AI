# Phase 4 — Read-only staging Pod image and readiness observation

**No staging cluster was connected, altered, or queried by adding this tool.**
This is a separate observation stage after
`PHASE4_STAGING_CLUSTER_SNAPSHOT.md` and requires authorized read-only RBAC
on an explicitly identified isolated staging Kubernetes context.

Example (the image is a placeholder, not a validated registry artifact):

```bash
python scripts/staging_pod_image_snapshot.py \
  --context YOUR_STAGING_CONTEXT \
  --namespace logsight-staging \
  --deployment logsight-ai \
  --container logsight-api \
  --expected-image registry.example/logsight-ai@sha256:YOUR_VERIFIED_64_HEX_DIGEST \
  --minimum-ready 2 \
  --output /secure/path/pod-snapshot.json
```

The operator must set `--minimum-ready` based on the approved staging
replica plan, not this example. Only two read operations occur:
`kubectl get deployment` to find the controller's simple matchLabels, then
`kubectl get pods --selector ...` to capture selected Pods. The tool records
Pod names, phase, target container's specified image and runtime imageID,
and readiness. It never retrieves Secrets, environment variables or logs.
Missing imageIDs, ambiguous selector expressions and missing container statuses
cause a fail-closed error. Any unready or unexpectedly tagged selected Pod
fails the acceptance check, even during a rolling update.

**Important boundary:** Kubernetes runtime `imageID` may identify the
container image configuration digest rather than the registry manifest digest.
For that reason, imageID presence is recorded as evidence, but digest
**equivalence is intentionally not asserted** by this tool. The deployment
owner must independently reconcile manifest and runtime references with
the registry and the node runtime. A label selector can also include unrelated
Pods; check their ownership, timestamps and selected scope independently.

A pass does not mean a real staging run occurred, that the registry image was
verified, that authenticated Prometheus scraping works, or that alert,
recovery, disruption and soak drills are complete. These require separate
source evidence and independent approval.
