# Phase 4 readiness alert response and evidence contract

**Status: example configuration, not an operated alert system.** The YAML at
`deploy/prometheus/logsight-readiness-alerts.yaml` is a candidate set of rules
for an explicitly configured Prometheus environment. It is not installed by
the Helm chart and no Alertmanager receiver is configured here.

## Prerequisites

1. Assign a named staging operator, on-call destination, alert owner, escalation
   rotation, and change-approval ticket before loading the rules.
2. Configure an authenticated, TLS-protected metrics scraping path appropriate
   to the deployment. The LogSight `/metrics` route is guarded by the
   application bearer token in token mode; do not disable authentication to
   make scraping easier, and **never** commit or paste the bearer token into
   scrape configs, alerts or test evidence.
3. Aggregate across expected API replicas, test counter reset behavior, and
   verify that metric/job labels are stable and free of tenants, topics, event
   content, addresses and credentials.
4. Define a separate signal for missing scrape targets: these example counters
   only increase when readiness requests occur. Quiet services, failed metrics
   collection and a complete process outage can therefore produce **no alert**
   from these rules. An externally observed readiness/availability SLI is
   required before an availability SLO can be asserted.
5. Review the alert evaluation interval, proposed five-minute `increase()`
   window, and two-minute `for` duration against owner-approved SLO/error
   budgets; these illustrative values are not an approved incident threshold.

## Triage and recovery

- **Kafka:** verify `/health` vs `/ready`, producer lifecycle, enabled
  metadata monitor, recent confirmed publishes, and broker-side authorization,
  topic availability, replication and partition health. A successful metadata
  probe alone does not clear a failed publish signal. On uncertain broker
  acknowledgment, preserve the event's stable UUID for replay/duplicate review.
- **Redis:** check connectivity and admission Lua script health, configured
  probe timeout, replication and latency. A successful PING proves neither
  admission-script correctness nor durability. Do not enable Kafka+Redis
  experimental modes together without resolving pre-ack deduplication order.
- **ClickHouse:** review the *fixed* worker signals
  `clickhouse_insert_failed offset_uncommitted` and
  `kafka_offset_commit_failed insert_outcome_success_replay_possible`.
  These are plain log messages, not Prometheus metrics and cannot be detected
  by the two readiness alert rules. Review the offset and bounded insert-token
  deduplication behavior before any replay.
- During recovery, use the approved staging fault/rollback plan in
  `docs/PHASE4_STAGING_FAILURE_RECOVERY_DRILL.md`; never inject faults into a
  shared or production environment without permission.

## Alert acceptance evidence

Capture UTC timestamps, immutable Git/image/chart revisions, metric source
authentication design, named owner, selected synthetic failure scenario,
Prometheus evaluation and firing evidence, Alertmanager delivery, on-call
acknowledgment time, recovery, counter resets, missing-target coverage and
post-incident review. Protect the evidence links and omit any raw events or
secrets. Until a real staged delivery/acknowledgment drill and owner approval
are linked, **Phase 4 monitoring and SLO alerting remain open**.
