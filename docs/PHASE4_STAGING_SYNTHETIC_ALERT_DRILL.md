# Phase 4 — Approved synthetic alert-delivery staging drill

**Status: execution tool only; no real staging alert has been sent by this
repository change.** This is a controlled notification test, not a substitute
for independently observing Prometheus rule evaluation and real failure signals.

## Preconditions

- Obtain explicit written approval from the staging owner and the recipient of
  the staging notification, with an approval ticket, operator, separate
  reviewer, rollback contact, defined window and expected receiver.
- Verify Alertmanager in the **isolated staging environment** has a narrowly
  routed receiver for `LogSightStagingSyntheticDeliveryDrill`, and that it
  points only to a test/on-call-approved sink. Never reuse production paging
  routes; confirm routing rules yourself before execution.
- Use a TLS-verified staging API and approved bearer credentials. Set
  `ALERTMANAGER_STAGING_TOKEN` securely in the operator's environment; never
  put tokens in CLI arguments, PR comments, CI logs or evidence documents.

## Default: preview without sending

```bash
python scripts/staging_synthetic_alert_drill.py \
  --base-url https://alertmanager-staging.example.invalid \
  --drill-id staging-drill-unique-123 \
  --approval-ticket CHANGE-1234
```

The default dry run performs no network request. The caller supplies a
non-sensitive, unique staging drill ID. A synthetic `info` alert with
`environment=staging` and a five-minute expiration is generated; no customer
data or real incident details are included.

## Explicit operator execution

Only after reviewing the receiving channel, set
`LOGSIGHT_STAGING_DRILL_APPROVAL_TICKET` to the matching approved ticket
and run the same command with both `--execute` and
`--confirm SEND_SYNTHETIC_STAGING_ALERT`. This **POSTs one synthetic alert**
to `/api/v2/alerts`. The API response only establishes request acceptance,
**not** delivery, alert rule evaluation or acknowledgment. Treat the
`submitted_not_delivered` output accordingly.

The owner then independently confirms the Alertmanager active routing
observation, actual receipt in the authorized receiver, on-call acknowledgment
and their UTC timestamps and evidence references. Use
`PHASE4_ALERT_DELIVERY_EVIDENCE.md` and
`python -m logsight.alert_evidence /secure/path/staging-alert.json` to check
the separately reviewed record against the pre-approved acknowledgment limit.

**Important:** A direct Alertmanager POST bypasses Prometheus rule evaluation
and does not exercise scrape-failure detection. A separate synthetic-source
failure scenario must exercise the real alert rule and ingestion path. If the
recipient does not receive the alert, follow the staging incident runbook and
stop rather than repeating pages. No production readiness or human sign-off
is implied by this tool or its unit tests.
