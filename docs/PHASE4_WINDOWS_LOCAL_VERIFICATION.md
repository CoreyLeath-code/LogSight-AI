# Phase 4 — Windows local staging verification

After running the opt-in bootstrap described in
[PHASE4_WINDOWS_KIND_BOOTSTRAP.md](PHASE4_WINDOWS_KIND_BOOTSTRAP.md),
check the newly created local kind cluster **without mutating resources**:

```powershell
.\scripts\verify_local_staging.ps1
```

This script refuses to inspect another Kubernetes context, requires the named
local kind cluster `logsight-staging-alerts`, and uses read-only `kubectl
get` requests for two Deployments and two internal Services in
`logsight-staging`. It checks each Deployment has exactly one desired, ready
and updated replica and a fully observed generation, and that the Services
remain ClusterIP. It does **not** launch the cluster, validate the images'
registry digests, send an alert, or verify external delivery.

To inspect a previously sent approved synthetic drill, first start the
test receiver port-forward in a separate PowerShell session:

```powershell
kubectl --context kind-logsight-staging-alerts -n logsight-staging port-forward --address 127.0.0.1 svc/staging-receiver 8080:8080
```

Then in the repository root run:

```powershell
.\scripts\verify_local_staging.ps1 -DrillId staging-drill-unique-123
```

The script reports whether that exact synthetic ID is present in the
in-memory localhost receiver and returns nonzero if the deployment checks
or requested receipt check fail. A receipt is **not** a human acknowledgment,
real paging receipt, or proof that Prometheus evaluated a rule. There is no
automatic alert injection or recipient contact. Retain the restricted evidence
of any separately approved real staging test for [Issue #103](https://github.com/CoreyLeath-code/LogSight-AI/issues/103).
