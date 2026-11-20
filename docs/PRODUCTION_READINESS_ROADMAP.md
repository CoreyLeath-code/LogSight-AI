# Production-readiness roadmap

## Current status

LogSight-AI has a strong engineering baseline: dependency-light local analysis,
optional enterprise adapters, CI quality/security controls, a hardened container,
a Helm chart, and versioned quality benchmarks. It is **not yet approved for an
internet-facing, multi-tenant, or consequential production deployment**.

This roadmap is a promotion contract, not a list of features. An item is complete
only when its code, configuration, automated tests, operational evidence, and
owner approval are linked from a reviewed pull request or release record.

## Verified implementation milestones (not phase approvals)

The following items were merged into `main` after repository CI validation.
These checkmarks cover the named code/test milestone only. None of Phases 0–6
has yet met its full deployment-specific exit criteria.

- [x] **Phase 1 — API authentication foundation:** optional bearer-token guard,
  startup checks, and negative authentication tests
  ([PR #55](https://github.com/CoreyLeath-code/LogSight-AI/pull/55)).
- [x] **Phase 1 — bounded request bodies:** ingestion size caps and streamed
  request tests ([PR #57](https://github.com/CoreyLeath-code/LogSight-AI/pull/57)).
- [x] **Phase 2 — targeted API redaction:** selected credentials/emails redacted
  ahead of parsing, local caching and responses
  ([PR #56](https://github.com/CoreyLeath-code/LogSight-AI/pull/56)).
- [x] **Phase 3 — Kafka producer contract:** broker acknowledgement,
  idempotent producer configuration and publish timeouts
  ([PR #59](https://github.com/CoreyLeath-code/LogSight-AI/pull/59)).
- [x] **Phase 3 — experimental API producer path:** optional Kafka publish
  before success response, with negative delivery tests
  ([PR #60](https://github.com/CoreyLeath-code/LogSight-AI/pull/60)).
- [x] **Phase 3 — experimental ClickHouse sink:** offset commit after successful
  insert, schema tests and storage-failure handling
  ([PR #61](https://github.com/CoreyLeath-code/LogSight-AI/pull/61)).

**Not yet complete:** none of these milestones proves end-to-end exactly-once
delivery, multi-tenant security, approved privacy controls or staging durability.
The phase-level checkboxes below remain unchecked until the documented exit
evidence is available.

## Scope and non-goals

The supported production target is an authenticated service that ingests
authorized log events, applies explicit redaction and retention controls,
durably stores normalized data, produces observable anomaly signals, and can be
rolled back safely.

The following do not count as evidence of production readiness on their own:

- a green unit-test suite;
- a local Docker Compose demonstration;
- an adapter class that is not wired into the service path;
- an unreviewed model, corpus, runbook, or external endpoint;
- a dashboard without a documented alert and response owner.

## Phase 0 — Ownership, policy, and release boundary

- [ ] Name accountable owners for service operation, security response, data
  governance, and release approval.
- [ ] Define supported deployment topology, tenants, regions, data classes, and
  excluded use cases.
- [ ] Establish SLOs for ingestion availability, accepted-event latency, durable
  delivery, error rate, and alert-quality review.
- [ ] Define severity levels, on-call coverage, incident communications, and
  escalation paths.
- [ ] Publish a release policy requiring an immutable artifact, change review,
  rollback target, and approval evidence.
- [ ] Validate the documented rollback procedure in a non-production
  environment.

**Exit evidence:** reviewed operational policy, named owners, versioned SLO/alert
definitions, an exercised rollback record, and a release checklist signed by the
accountable owner.

## Incremental implementation evidence (2026-11-19)

A candidate PR adds an opt-in bearer-token check to the FastAPI gateway, protecting
all routes except `/health`. It rejects invalid token-mode configuration at
application creation, uses a constant-time comparison, and adds negative auth
regression tests. This is **not a completed Phase 1 checkbox**: deployment
integration, tenant-scoped identity/authorization, secrets management, TLS,
request size/concurrency limits, access audits, and security review remain open.

For the optional gateway, `LOGSIGHT_API_AUTH_MODE=token` requires a
`LOGSIGHT_API_TOKEN` of at least 32 characters. Use a randomly generated
secret from a deployment secret manager, transmit it only over TLS, and set
`Authorization: Bearer <token>` on protected requests. The default mode
`disabled` preserves local development behavior and **must not be used for a
publicly reachable deployment**. `/health` remains a public liveness probe;
metrics and recent-event endpoints are guarded in token mode.

### Additional API request admission control (candidate PR)

A bounded ASGI request-body guard now checks declared and streamed payload
sizes before validation, parsing, or inference for ingestion routes. The
configured cap defaults to 1 MiB and tests cover oversized JSON, streamed
requests, and successful small requests. This is partial Phase 1 evidence;
concurrency/timeouts, tenant-aware quotas, identity and authorization,
external ingress policy, and deployment load evidence remain outstanding.

### Scoped Redis admission-key hardening (PR #58)

Redis deduplication includes the same hashed admission scope as its per-scope
rate-limit key. Equal event fingerprints from unrelated service scopes no longer
share a deduplication key. Regression tests verify scope separation and stable
same-scope keys.

**Boundary:** the scope still comes from a caller-supplied service field;
this does not provide trusted workload identity or tenant authorization.
The Phase 1 exit criteria remain open.

## Phase 1 — API trust boundary

- [ ] Require workload identity at the ingress boundary (for example OIDC,
  mTLS, or deployment-approved API keys).
- [ ] Enforce authorization by tenant/service and least-privilege endpoint
  scopes; do not rely on network location as the only control.
- [ ] Protect ingestion, recent-event retrieval, metrics, and administrative
  endpoints according to their intended audience.
- [ ] Add request-size, per-tenant rate, concurrency, and timeout limits before
  expensive parsing or inference.
- [ ] Emit tamper-resistant access/audit events without exposing raw sensitive
  log content.
- [ ] Add API integration and negative authorization tests.

**Exit evidence:** threat model, authenticated end-to-end tests, authorization
matrix, rate-limit/load results, and security review sign-off.

### Initial API redaction implementation (candidate PR)

The optional API ingestion path now applies a deterministic, dependency-free
text-redaction pass before parsing and enrichment. Regression tests cover
common credential assignments, bearer credentials, email addresses, and
exclusion of representative sensitive strings from API responses and the
process-local recent-event cache.

**Not a complete data-governance control:** pattern matching is incomplete and
cannot discover arbitrary personal or regulated information. It does not
address already-stored records, external adapters, parser use outside the API,
retention/deletion, tenant boundaries, audit trails, or deployment-specific
classification policy. Review these limits before handling real log data.

## Phase 2 — Data governance and privacy

- [ ] Define the log schema, classification policy, approved attributes, and
  tenant boundary.
- [ ] Redact/tokenize configured secrets and personal data before storage,
  export, indexing, or response serialization.
- [ ] Enforce configurable retention, deletion, legal-hold, and access-audit
  requirements.
- [ ] Encrypt traffic and stored data using deployment-managed keys; document
  rotation and recovery.
- [ ] Keep credentials in a managed secrets system and prove they are absent
  from images, values files, benchmark data, and telemetry.
- [ ] Validate redaction and retention behavior with representative,
  de-identified fixtures.

**Exit evidence:** data-flow diagram, approved data classification, redaction
tests, retention/deletion test evidence, and secrets/key-management runbook.

### Kafka producer delivery contract (candidate PR)

The optional `KafkaStream` adapter now requests broker acknowledgements from
all in-sync replicas and enables producer idempotence. Client publish waits
are bounded and acknowledgement timeout raises an explicit exception;
unit tests verify these settings without claiming a live-broker recovery drill.

**Still missing:** the FastAPI gateway does not yet route accepted events
through Kafka; TLS/SASL, ACLs, partitioning, retries and downstream ClickHouse
consumer ownership require explicit deployment design and integration evidence.
A publish timeout is an indeterminate outcome and is **not** proof of rejection
by the broker. Producer idempotence alone does not make the end-to-end pipeline
exactly-once.

### Experimental API-to-Kafka acknowledgement path (candidate PR)

When explicitly enabled, the FastAPI gateway starts a Kafka producer during
application lifespan, publishes the redacted event before returning an API
success, and maps unconfirmed broker acknowledgements to HTTP 503 without
adding the event to local metrics or recent-event cache. Unit tests use a
fake producer to verify success and failure cases. Default local behavior
remains unchanged.

**This does not close Phase 3:** the broker must still be configured with
authenticated transport, ACLs, replication and retention; there is no
durable ClickHouse consumer, idempotency/replay contract, staging drill,
or tenant-safe recent-event store. Retrying after HTTP 503 can duplicate
a broker-accepted event. Batch ingestion can partially succeed before a
failure. Redis admission mode is blocked in experimental Kafka mode until
the pre-ack deduplication ordering is corrected.

### Experimental Kafka-to-ClickHouse sink (candidate PR)

The reference worker consumes the broker topic with auto-commit disabled,
validates and re-redacts the event schema, inserts a matching row into the
existing ClickHouse table, then commits the consumer offset only after the
storage call succeeds. Unit tests exercise valid/invalid event envelopes,
storage failures, and no-offset-commit behavior for poison records.

This is *at-least-once* processing groundwork, not an end-to-end durability
guarantee. ClickHouse insert success followed by offset-commit failure can
duplicate records. Malformed events stop progress until explicitly resolved.
A production promotion still requires reviewed stable event identifiers,
database idempotency, DLQ/replay policy, TLS/ACLs, authenticated dependencies,
rebalances and partition recovery, load tests, live dependency integration,
backup/restore, and owner approval.

## Phase 3 — Durable ingestion and storage

- [ ] Route accepted events through a durable, authenticated Kafka/Redpanda
  topic with explicit partitioning, retention, ACLs, and consumer ownership.
- [ ] Wire the service path to durable ClickHouse storage and only use Qdrant
  for explicitly approved vector data.
- [ ] Add schema versioning, migrations, compatibility tests, idempotency keys,
  retry/backoff policy, and a dead-letter/replay workflow.
- [ ] Replace process-local recent-event state with shared, bounded, tenant-safe
  state or an explicitly scoped query model.
- [ ] Define backpressure behavior and preserve accepted-event ordering and
  delivery semantics in API responses and runbooks.
- [ ] Test broker, storage, and worker unavailability, recovery, duplicate
  delivery, and replay.

**Exit evidence:** end-to-end integration tests against deployment-like
dependencies, durable-delivery dashboards, documented recovery procedure, and a
successful replay drill.

## Phase 4 — Availability, resilience, and observability

- [ ] Implement dependency-aware readiness and startup probes; distinguish
  liveness from readiness.
- [ ] Define degraded-mode behavior for Redis, Kafka, storage, model workers,
  and telemetry exporters.
- [ ] Export authenticated production metrics for request rate, latency,
  saturation, queue lag, error classes, retry/dead-letter volume, and
  dependency health.
- [ ] Export OpenTelemetry to an authenticated, retained backend; remove debug
  exporters from production configuration.
- [ ] Create dashboards and alerts aligned with SLOs, with runbooks and owners.
- [ ] Test horizontal scaling, pod disruption, node loss, dependency partitions,
  restart recovery, and capacity exhaustion.
- [ ] Establish backup, restore, and disaster-recovery objectives for every
  persistent dependency.

**Exit evidence:** staging soak/load test, alert test record, failure-injection
results, tested backup restore, and capacity plan for the approved workload.

## Phase 5 — Supply chain and deployment controls

- [ ] Lock direct and transitive runtime dependencies; automate reviewed update
  and vulnerability remediation policy.
- [ ] Build reproducible images from pinned base-image digests and publish
  immutable image digests.
- [ ] Generate SBOM and provenance, scan the final image, sign release
  artifacts, and verify signatures during deployment.
- [ ] Make Helm accept and require digest-pinned images; validate manifests,
  policy controls, and secrets references in CI.
- [ ] Separate environment configuration from source, with protected production
  promotion and approval gates.
- [ ] Verify least-privilege cloud/Kubernetes identities, NetworkPolicies,
  ingress TLS, and egress allowlists in the target environment.

**Exit evidence:** signed immutable release, SBOM/provenance attached to the
release, deployment-policy test, and successful deployment from the approved
artifact digest.

## Phase 6 — Detection quality and human operation

- [ ] Expand the labeled corpus with reviewed, de-identified representative
  workloads and a documented sampling/labeling process.
- [ ] Track precision, recall, incident recall, alert burden, and drift by
  service and corpus version.
- [ ] Set human-approved promotion thresholds; make benchmark gates enforce the
  release policy without presenting scores as universal safety guarantees.
- [ ] Version models, feature contracts, thresholds, runbooks, and investigator
  source revisions.
- [ ] Require human review for high-impact recommendations; prohibit automatic
  remediation until separately designed, tested, and approved.
- [ ] Establish a false-positive/false-negative feedback loop and periodic
  quality review.

**Exit evidence:** reviewed evaluation report, threshold approval, corpus/model
provenance, and an alert-quality review record.

## Production launch gate

The service may be labeled production-ready only after every applicable phase has
exit evidence, all deployment-specific dependencies are configured, and the
accountable release owner records approval for a named artifact digest and
environment.

Before each production release, confirm:

1. required CI, security, image, Helm, and integration checks passed for the
   exact release commit;
2. the deployed image digest, configuration revision, model/corpus revisions,
   and rollback digest are recorded;
3. SLO dashboards and alerts are live and tested;
4. backup/restore, incident response, and rollback drills are current;
5. no critical or high-severity security, privacy, reliability, or quality
   exception remains unaccepted by the accountable owner.

## First implementation milestone

Start with **secure, durable ingestion**:

1. authenticated and authorized API access;
2. pre-storage redaction and data-policy enforcement;
3. Kafka-backed durable acceptance plus ClickHouse persistence;
4. dependency-aware readiness, backpressure, and failure-mode tests.

That milestone removes the highest-risk gaps while creating the foundation for
reliable operations, quality evaluation, and controlled production promotion.
