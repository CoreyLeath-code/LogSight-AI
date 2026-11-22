# Phase 4 — Read-only Prometheus target verification in staging

**No Prometheus server or staging cluster was contacted in repository CI.**
This is an opt-in, operator-run observation step after the Deployment and
Pod snapshots in the Phase 4 staging runbooks.

Use a named, authorized isolated staging environment. Verify that the
monitoring operator approved the exact **job** and **instance** labels, and
that the API endpoint is served over verified HTTPS (loopback HTTP is
supported only for local developer fixtures).

Set `PROMETHEUS_STAGING_TOKEN` securely through the operator's approved
secret manager; do not pass it as a CLI argument, save it in source control
or include it in evidence. With access to the monitoring API, run:

```bash
python scripts/staging_prometheus_target.py \
  --base-url https://prometheus-staging.example.invalid \
  --job APPROVED_STAGING_JOB \
  --instance APPROVED_STAGING_INSTANCE
```

The command reads only `/api/v1/targets?state=active` and rejects
cross-origin redirects. It checks a single exact active target by job and
instance labels, whether it scrapes `/metrics`, whether `lastScrape` is
present and whether the target health is `up` with no lastError.
Only sanitized Boolean conclusions and the explicitly provided labels
are printed. The response body, tokens, target-discovery metadata and
error details are never dumped.

Exit 0 means the observed target reported healthy; exit 1 means its last
scrape was unhealthy; exit 2 means scope, access or target data was invalid.
Store only approved summaries and evidence URLs. A successful scrape is
**not** proof of independent application availability, authentication
configuration, correct telemetry semantics, alert delivery or recovery.
Confirm those separately with the staging preflight and approved human
alert drill.
