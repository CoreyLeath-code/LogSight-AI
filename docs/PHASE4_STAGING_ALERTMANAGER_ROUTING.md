# Phase 4 — Staging Alertmanager active-alert routing observation

**This is an opt-in read-only check. It does not create an alert, inspect
production, send notifications, prove receiver delivery, or record human
acknowledgment.** The operator must run it only after approved synthetic
staging alert injection or an already-observed isolated staging alert.

The named alert and receiver must be approved by the environment owner.
Set `ALERTMANAGER_STAGING_TOKEN` using an approved secret manager. Do not put
tokens in source, CLI arguments, CI logs, evidence records or issues.

```bash
python scripts/staging_alertmanager_routing.py \
  --base-url https://alertmanager-staging.example.invalid \
  --alert APPROVED_STAGING_ALERT \
  --receiver APPROVED_STAGING_RECEIVER
```

The tool performs a single authenticated GET against `/api/v2/alerts`,
requires HTTPS outside explicit loopback development, rejects redirects,
and checks that exactly one selected alert has status `active` and has the
expected receiver assigned. It prints only sanitized assessment booleans and
the operator-provided identifiers, not the payload, annotations, URLs,
credentials, or extra labels. Exit 0 means the submitted API response met
the gate, 1 means inactive/unrouted, 2 means invalid input or inaccessible
API.

**Receiver assignment is not notification delivery.** Confirm the actual
page/ticket/message receipt and human acknowledgment with independent
receiver-side evidence and the existing `PHASE4_ALERT_DELIVERY_EVIDENCE.md`
runbook and evaluator. Also verify Prometheus rule evaluation and scrape
health separately. None of this can be checked in CI without an authorized
running staging environment.
