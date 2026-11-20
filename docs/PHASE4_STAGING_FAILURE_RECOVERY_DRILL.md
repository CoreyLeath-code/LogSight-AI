# Phase 4 — Staging availability and failure-recovery drill

> **Status: procedure only, not execution evidence.** This runbook defines an
> operator-controlled staging drill. No broker outage, disruption, or restore is
> claimed to have been performed by creating or merging this document.

## Preconditions and safety

- Obtain approval from the staging owner and define a rollback window, on-call
  contact, affected cluster/namespace and maintenance notice.
- Use an isolated staging namespace and **synthetic, non-sensitive** events;
  never run fault injection against production or shared broker dependencies.
- Record immutable image digest, Git revision, Helm values revision, Kafka topic
  and consumer group identifiers, broker/ClickHouse endpoints and TLS policy.
- Confirm authorization for fault injection, Kubernetes changes, Kafka ACLs,
  topic deletion/recreation and storage operations. Do not publish raw secrets
  or captured event payloads into an evidence artifact.
- Ensure a known-good rollback release and sufficient spare capacity.
- Configure real authentication, broker and storage retention and dashboard
  access before validating production-like behavior.

## Baseline evidence (capture before disruption)

1. Record UTC timestamp, request volume, client retry/idempotency policy,
   configured monitor interval, selected Kafka topic and app pod count.
2. Capture authorized HTTP status for `GET /health` and `GET /ready`.
   Authentication is not required for these probe paths. Avoid logging tokens.
3. Record a *synthetic* event UUID, Kafka topic/partition/offset, producer
   acknowledgment outcome, and ClickHouse event row count at a fixed
   observation time. Record any delivery uncertainty separately.
4. Save dashboard/export evidence for ingress errors, queue lag, request
   latency, pod restarts, Kafka leader/ISR and ClickHouse insert failures,
   **where actual instrumentation exists**. Mark missing signals as gaps.

## Failure matrix

| Scenario | Operator-controlled action | Expected observation | Recovery evidence |
|---|---|---|---|
| Kafka broker metadata unavailable | Block staging API-to-broker network or stop an isolated staging broker within an approved test window | With monitoring enabled, `/ready` eventually returns 503; `/health` remains independent if API process is alive | Restore connectivity and record metadata recovery and broker-acknowledged publish |
| Kafka publish acknowledgment fails | Inject isolated broker failure or use a staging fault proxy | Publish fails/returns 503; subsequent successful metadata-only probe must **not** erase failed-publish readiness | A confirmed subsequent publish clears the publish-failure signal only if metadata status is also healthy |
| Background metadata monitor stops | Terminate/cancel monitoring task in a controlled test harness, **not** by modifying live production internals | `/ready` fails closed rather than returning stale success | Restart/redeploy within approved procedure; verify monitoring resumed before declaring readiness |
| ClickHouse insert unavailable | Block sink access to staging ClickHouse while holding Kafka messages | Consumer must not commit failed insert offset; DLQ must not receive storage errors as malformed events | Restore ClickHouse and validate replay/row counts; investigate duplicate-risk and bounded dedup window |
| Kafka consumer restart/rebalance | Restart one isolated staging consumer and cause a partition reassignment | No acknowledgments beyond successfully stored/quarantined records | Compare per-partition source offsets, storage IDs, and duplicates before/after |
| Pod disruption and rollout | Execute an approved staging rollout/disruption within capacity budget | Readiness removes unhealthy API pods from service; liveness does not depend on downstream metadata | Record rollout, ready replicas, request-error gap, and confirmed post-rollout publish |

## Execution protocol

1. Record **baseline**, execute only one approved fault at a time, and note UTC
   start/end timestamps and exact commands in an **access-controlled** evidence
   record. Do not paste credentials, sensitive headers or original log bodies.
2. Observe probes and broker/storage signals until either the scenario's
   pre-agreed recovery budget is met or the abort threshold is reached.
   **Do not invent numeric SLO thresholds**: link the owner-approved policy.
3. Validate application-visible outcomes, not only container health. When Kafka
   returns an ambiguous timeout, record the event as *indeterminate* and use its
   stable ID for deduplication analysis rather than assuming it was rejected.
4. Capture failures and rollback/recovery actions; stop immediately if the fault
   affects an unexpected namespace, customer, tenant or unrelated dependency.
5. Restore the staging baseline and reconcile Kafka source offsets, DLQ records
   and ClickHouse events. Annotate known bounded deduplication limitations.

## Evidence record template

- Date/time (UTC), operator, reviewer and change/approval ticket:
- Cluster/namespace and isolated service/broker/storage identifiers:
- Git commit, image digest, chart/config revision, model/corpus revision:
- Scenario and exact authorized fault-injection method:
- Expected outcome, actual timestamps and probe statuses:
- Request error count, observed latency and queue/consumer lag (or missing):
- Kafka acknowledgment, partition/offset, replay and duplicate counts:
- ClickHouse row count before/after; schema and deduplication window:
- SLO/abort threshold references and whether each was met:
- Rollback actions, restored baseline and lingering risks:
- Evidence links (access-controlled), reviewer signature, disposition:

## Promotion gate

A passing unit test or this runbook alone does **not** close Phase 4. Require
staging execution, objective SLO checks, alert delivery/acknowledgment evidence,
approved recovery budget, infrastructure owner review, backup/restore proof,
and explicit sign-off for a named image digest and environment. Unrun,
inconclusive, or partial scenarios remain open.
