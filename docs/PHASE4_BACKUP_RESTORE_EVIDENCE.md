# Phase 4 — Backup/restore evidence and RPO/RTO gate

> **Not execution evidence.** This repository does not provision backups, restore
> storage, operate ClickHouse/Kafka/Redis, or claim a successful staging restore.
> This optional offline gate checks the completeness and arithmetic of an
> **operator-supplied** evidence record; it does not verify its authenticity.

## Backup and recovery inventory

Before a real staging drill, the responsible infrastructure owner must record
and approve, for **each** persistent dependency:

| Dependency | What needs separate coverage | Verification ownership |
|---|---|---|
| ClickHouse | schema/migrations, backup set, encryption and restore, row counts and representative stable event IDs | storage operator |
| Kafka | topic configurations, ACLs, replication/retention, recoverable event offsets and producer/consumer position | Kafka operator |
| Redis admission | whether ephemeral keys can be rebuilt; if persistence is required, snapshot/AOF strategy, key TTL and consistency | Redis operator |
| Celery result backend | task retry/reconciliation, pending/acked task state and result retention where enabled | worker operator |
| Model artifacts and configuration | approved version, digest and a rollback path independent of transient caches | release owner |

A single passing ClickHouse restore does **not** prove Kafka replay safety,
cross-system consistency, tenant isolation, or operational availability.

## Approved staging execution

1. Use an isolated staging environment, non-sensitive synthetic events,
   authorized backup target and a named operator/reviewer. Document permission,
   rollback target and pre-agreed RPO/RTO objectives.
2. Create a verified staging backup using the deployment-owned vendor procedure.
   Preserve metadata and integrity checksums in an access-controlled record.
3. Introduce an approved staging-only restoration scenario and record
   `started_at_utc` (incident start), `last_recoverable_at_utc` (the latest
   recoverable data timestamp) and `restored_at_utc` (full service recovery).
   Verify restored schema, row/event counts, representative synthetic IDs and
   ability to ingest a new synthetic record. Reconcile Kafka offsets and DLQ.
4. Sign off data-integrity verification and recovered service behavior only
   after evidence review. Do not upload raw event data, database credentials,
   bearer tokens or unredacted service logs into source control.
5. Save the evidence record outside this repository in a restricted storage
   system; include links to approvals, restore logs and checksums. Reference it
   by HTTPS link, not pasted credentials.

## Offline validation

Run `python -m logsight.recovery_evidence /secure/path/staging-drill.json`.
The command exits 0 when a structurally complete record reports both objectives
met, 1 when measured objectives are exceeded, and 2 for incomplete/invalid
records. It prints **only** the dependency, measured elapsed seconds, and
pass/fail indicators, not the full record. Require a human reviewer to verify
the evidence links, backup correctness, UTC timestamps, actual outage and
signature; this tool cannot prove those claims.

Example *schema only* (replace all placeholders after an actual approved
drill; never commit a filled production record):

```json
{
  "environment": "isolated-staging",
  "operator": "OPERATOR-ID",
  "reviewer": "REVIEWER-ID",
  "approval_ticket": "CHANGE-ID",
  "image_digest": "sha256:APPROVED-IMMUTABLE-DIGEST",
  "git_revision": "GIT-SHA",
  "dependency": "clickhouse",
  "backup_reference": "BACKUP-ID",
  "restore_reference": "RESTORE-ID",
  "started_at_utc": "2026-11-20T12:00:00Z",
  "last_recoverable_at_utc": "2026-11-20T11:59:00Z",
  "restored_at_utc": "2026-11-20T12:04:00Z",
  "rpo_objective_seconds": 120,
  "rto_objective_seconds": 300,
  "data_integrity_verified": true,
  "service_recovered": true,
  "evidence_links": ["https://example.invalid/RESTRICTED-EVIDENCE-LINK"]
}
```

Values are illustrative, not approved service SLOs. The evaluator only
compares submitted UTC timestamps and declared goals; a synthetic record can
pass **unit tests** and still provide zero operational evidence. Real Phase 4
approval requires independently reviewed drills for applicable dependencies,
backup retention and deletion policy, restore testing, alert delivery, replica
failure exercises and accountable sign-off.
