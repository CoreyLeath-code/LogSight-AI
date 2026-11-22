# Phase 4 — Opt-in local kind staging alert rehearsal

**Status: local infrastructure definition, not an executed deployment.** This
creates a brand-new, isolated Kubernetes-in-Docker (kind) cluster, named
`logsight-staging-alerts`, with test-only Alertmanager and an in-memory
webhook receiver. It is not a production-equivalent environment and does
**not** deploy the LogSight API, Prometheus, persistent dependencies or
external notification integrations. Docker, kind and kubectl are required.

## Plan and bootstrap

From the repository root, inspect the Kubernetes manifests before execution:

```bash
bash scripts/bootstrap_local_staging_alerts.sh
bash scripts/bootstrap_local_staging_alerts.sh --execute
```

The first invocation is a **no-mutation preview**. The second creates a
new local cluster; it refuses to modify one already bearing the same name.
Resources are in namespace `logsight-staging`, and the two Services are
ClusterIP only. No NodePort, Ingress, cloud credentials, production
receiver or external notification endpoint is configured.

Once deployments are ready, open two **separate** terminal sessions:

```bash
kubectl --context kind-logsight-staging-alerts -n logsight-staging port-forward --address 127.0.0.1 svc/staging-alertmanager 9093:9093
kubectl --context kind-logsight-staging-alerts -n logsight-staging port-forward --address 127.0.0.1 svc/staging-receiver 8080:8080
```

These local HTTP ports are **unauthenticated developer fixtures**.
Alertmanager does not enforce the supplied bearer token itself. The existing
drill script can talk to HTTP loopback, but a dummy token is **not** proof
of API authentication. Do not expose the port-forward beyond localhost, share
it publicly or use it to test protected production API access.

Inspect the test receiver at `http://127.0.0.1:8080/receipts`.
It stores only synthetic drill IDs and receive timestamps in memory and
always reports `human_acknowledged=false`. Receipts disappear when its Pod
restarts. It never pages a real human.

## Rehearsal

After the owner approves a **local-only dry-run rehearsal**, use the command
in `docs/PHASE4_STAGING_SYNTHETIC_ALERT_DRILL.md`, substituting
`--base-url http://127.0.0.1:9093`. The default command does not send.
The explicit `--execute --confirm SEND_SYNTHETIC_STAGING_ALERT` option
requires `LOGSIGHT_STAGING_DRILL_APPROVAL_TICKET` and
`ALERTMANAGER_STAGING_TOKEN` environment variables. In this **local
fixture only**, Alertmanager ignores the bearer value; that does not meet
the authentication requirement of a real staging deployment.

The drill's matching alert routes solely to
`staging-test-webhook`; unmatched alerts go to a no-op receiver. After
an authorized test, check the receiver's local `/receipts` endpoint for
the exact synthetic ID and UTC receive time. API acceptance and webhook
receipt demonstrate a **local synthetic route only**. They do not validate
Prometheus rule evaluation, real on-call delivery, human acknowledgment,
external availability, TLS, high availability, image provenance or disaster
recovery. **Issue #103 remains pending** until a separately approved, actual
staging notification is independently reviewed.

## Cleanup

```bash
kind delete cluster --name logsight-staging-alerts
```

The images use version tags suitable for a local rehearsal; before
deploying in a shared/remote staging environment, pin verified OCI digests,
enforce TLS/RBAC/network policies and obtain authorized receiver consent.
