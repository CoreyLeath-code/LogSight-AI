# Phase 4 — Windows PowerShell local kind bootstrap

From a clean LogSight-AI checkout on Windows, with **Docker Desktop in
Linux containers mode**, kind and kubectl installed:

```powershell
cd $HOME\LogSight-AI-staging
.\scripts\bootstrap_local_staging_alerts.ps1
```

This only displays the plan and makes **no Kubernetes or Docker changes**.

Verify the required executables and Docker engine:

```powershell
docker info
kind version
kubectl version --client
```

With the operator's explicit authorization for a **local isolated cluster**,
run:

```powershell
.\scripts\bootstrap_local_staging_alerts.ps1 -Execute
kubectl --context kind-logsight-staging-alerts -n logsight-staging get pods
```

The script refuses to modify an already-existing kind cluster and uses only
`--context kind-logsight-staging-alerts` after creating the dedicated local
cluster. No external notification or human acknowledgment is produced.
No Bash/WSL is required. The existing Bash script is retained for Linux/macOS
and `.gitattributes` keeps Bash script checkouts in LF format.

For local port-forwarding, verification, opt-in synthetic alert rehearsal and
cleanup, follow [PHASE4_LOCAL_KIND_STAGING.md](PHASE4_LOCAL_KIND_STAGING.md).
The staging Alertmanager is an **unauthenticated localhost-only fixture**,
not a hardened remote cluster; this bootstrap does not verify actual
end-to-end production alerts, Prometheus rules, delivery, or operator sign-off.
Issue #103 remains open until that evidence exists.
