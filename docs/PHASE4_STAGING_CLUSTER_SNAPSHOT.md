# Phase 4 — Read-only staging Kubernetes snapshot

This opt-in operator tool complements the offline staging deployment
evidence gate. **No staging environment is connected or inspected by CI.**

With an approved, isolated staging cluster, a **read-only Kubernetes RBAC**
identity and a verified image digest, run:

```bash
python scripts/staging_cluster_snapshot.py \
  --context YOUR_STAGING_CONTEXT \
  --namespace logsight-staging \
  --deployment logsight-ai \
  --expected-image registry.example/logsight-ai@sha256:YOUR_VERIFIED_64_HEX_DIGEST \
  --output /secure/path/staging-snapshot.json
```

The tool requires an explicit staging context or namespace and refuses
names containing production/prod/live. It runs **only** `kubectl get deployment
-o json`, with a finite timeout and no mutation. It checks that the Deployment
template has digest-pinned images, the approved image is present, desired and
ready/updated replicas agree, and the controller observed the latest generation.
The output contains no Pod environment, Secret contents, pod logs or user
events. Treat the snapshot as restricted deployment metadata.

For end-to-end staging verification, an operator must additionally inspect
the running pod imageIDs (including any registry normalization), confirm
actual ServiceMonitor target discovery and `up` in Prometheus, run the
authenticated API preflight, test receiver delivery, and compare to the
approved rollout and rollback records. This is a **read-only Deployment
template/status snapshot**, not proof that the running container image digest
matches its template or that the system is production ready.
