# Phase 4 — Read-only authenticated staging API scrape preflight

**Tooling only.** This preflight does not deploy infrastructure, configure
Prometheus, execute failure drills or demonstrate production readiness.

After obtaining the staging owner's approval, deploy the reviewed API image with
`LOGSIGHT_API_AUTH_MODE=token`, the matching Secret-backed bearer token,
a verified HTTPS endpoint and network-policy access. Export the same token
**locally and securely** as `LOGSIGHT_STAGING_SCRAPE_TOKEN`; never put it in a
CLI argument, commit, issue, or test evidence.

Run:

```bash
python -m logsight.staging_scrape_preflight --base-url https://staging.example.invalid
```

The command performs only GET requests to `/health`, `/ready`, and
`/metrics`, verifying that health/readiness succeed, unauthorized metric
access gets HTTP 401, and an authorized metric response includes the
readiness success counter. It exits 0 on all checks passing, 1 for an unmet
check, and 2 for invalid input or network errors. It prints Boolean outcomes,
not tokens or metric values. A HTTP endpoint is allowed **only** for explicit
localhost/loopback development fixtures; non-loopback targets require HTTPS.

**Limitations:** Passing this check proves neither Prometheus target discovery
nor scraping by an operator, encryption at every hop, Alertmanager routing,
external SLIs, Kafka-to-ClickHouse durability, or backup/restore. Capture
external scrape target state, `up` series, receiver delivery and human
acknowledgment with approved evidence links before Phase 4 sign-off.
