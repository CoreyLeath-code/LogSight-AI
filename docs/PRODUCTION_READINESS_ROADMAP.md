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
- [x] **Phase 4 — Redis admission readiness foundation:** bounded Redis
  connectivity checks in `/ready` with negative-path tests
  ([PR #78](https://github.com/CoreyLeath-code/LogSight-AI/pull/78)).
- [x] **Phase 4 — readiness outcome counters:** low-cardinality per-process
  readiness outcomes and guarded metrics endpoint regression tests
  ([PR #79](https://github.com/CoreyLeath-code/LogSight-AI/pull/79)).
- [x] **Phase 4 — inference enqueue failure semantics:** sanitized enqueue
  errors and explicit ambiguous-delivery response; worker heartbeat
  monitoring remains outstanding
  ([PR #81](https://github.com/CoreyLeath-code/LogSight-AI/pull/81)).
- [x] **Phase 4 — ClickHouse failure signals:** separate fixed operator signals
  for ClickHouse insert and Kafka offset commit failures, with secret-safety tests
  ([PR #82](https://github.com/CoreyLeath-code/LogSight-AI/pull/82)).
- [x] **Phase 4 — sample readiness alert rules:** static Prometheus rule
  examples and incident-response runbook, not deployed or alert-delivery proof
  ([PR #83](https://github.com/CoreyLeath-code/LogSight-AI/pull/83)).
- [x] **Phase 4 — opt-in authenticated ServiceMonitor plumbing:** secret
  reference, Helm render checks and deployment caveats; live staging scrape
  remains unverified ([PR #85](https://github.com/CoreyLeath-code/LogSight-AI/pull/85)).
- [x] **Phase 4 — HA configuration test foundation:** HPA/PDB and probes
  regression tests with an unexecuted staging disruption plan
  ([PR #86](https://github.com/CoreyLeath-code/LogSight-AI/pull/86)).
- [x] **Phase 4 — recovery evidence validator foundation:** offline RPO/RTO
  evaluator and negative tests; live restores and human evidence review remain open
  ([PR #89](https://github.com/CoreyLeath-code/LogSight-AI/pull/89)).
- [x] **Phase 4 — soak acceptance validator foundation:** offline success-rate,
  latency and duration gate; staging load tests remain unexecuted
  ([PR #88](https://github.com/CoreyLeath-code/LogSight-AI/pull/88)).
- [x] **Phase 4 — alert delivery evidence validator:** offline
  acknowledgment deadline validation and negative tests, not a live drill
  ([PR #90](https://github.com/CoreyLeath-code/LogSight-AI/pull/90)).
- [x] **Phase 4 — missing-scrape alert example:** explicit down-target and
  absent-series alerts plus static tests; real scrape and receiver remain unverified
  ([PR #91](https://github.com/CoreyLeath-code/LogSight-AI/pull/91)).
- [ ] **Phase 4 — staging authenticated scrape preflight (PR pending):**
  read-only protected metrics smoke checks and negative tests; actual
  authorized staging deployment and observations remain open.
- [x] **Phase 4 — failed monitor supervision:** readiness fails closed after
  the Kafka metadata monitoring task exits unexpectedly
  ([PR #76](https://github.com/CoreyLeath-code/LogSight-AI/pull/76)).
- [x] **Phase 4 — isolated failure-recovery drill procedure:** staging
  scenarios, approval gates and evidence record created; drills unexecuted
  ([PR #77](https://github.com/CoreyLeath-code/LogSight-AI/pull/77)).
- [x] **Phase 4 — independent readiness signals:** metadata reachability
  cannot erase a failed broker publish; confirmed write and metadata status
  are checked separately ([PR #75](https://github.com/CoreyLeath-code/LogSight-AI/pull/75)).
- [x] **Phase 4 — optional Kafka idle connectivity foundation:** bounded
  metadata probes, failure/recovery tests and shutdown cleanup; not a write SLA
  ([PR #74](https://github.com/CoreyLeath-code/LogSight-AI/pull/74)).
- [x] **Phase 4 — local producer readiness foundation:** independent
  liveness and Kafka producer lifecycle readiness, Helm probe and tests
  ([PR #72](https://github.com/CoreyLeath-code/LogSight-AI/pull/72)).
- [x] **Phase 3 — ClickHouse HTTPS client foundation:** verified TLS,
  optional CA and header-based credentials for the experimental consumer
  ([PR #71](https://github.com/CoreyLeath-code/LogSight-AI/pull/71)).
- [x] **Phase 3 — Kafka transport security foundation:** TLS context,
  SASL_SSL configuration and rejection of plaintext credential transport
  ([PR #70](https://github.com/CoreyLeath-code/LogSight-AI/pull/70)).
- [x] **Phase 3 — opt-in recovery-test harness:** replay and injected
  storage/offset failure tests with a disposable infrastructure runbook;
  live execution evidence is still pending
  ([PR #69](https://github.com/CoreyLeath-code/LogSight-AI/pull/69)).
- [x] **Phase 3 — bounded ClickHouse retry deduplication:** stable per-event
  insert tokens and opt-in SQL migration; not a uniqueness guarantee
  ([PR #68](https://github.com/CoreyLeath-code/LogSight-AI/pull/68)).
- [x] **Phase 3 — partition-scoped offsets:** commit only the successfully
  processed source partition's next offset, including the DLQ path
  ([PR #67](https://github.com/CoreyLeath-code/LogSight-AI/pull/67)).
- [x] **Phase 3 — offline DLQ verification foundation:** metadata-only
  source/checksum verification without publishing or replaying payloads
  ([PR #66](https://github.com/CoreyLeath-code/LogSight-AI/pull/66)).
- [x] **Phase 3 — malformed-event quarantine foundation:** optional restricted
  Kafka DLQ with source-offset commit gated on DLQ acknowledgement
  ([PR #65](https://github.com/CoreyLeath-code/LogSight-AI/pull/65)).
- [x] **Phase 3 — client retry identity foundation:** validated optional
  UUIDv4 header carried through the experimental event pipeline; duplicate
  writes remain possible ([PR #64](https://github.com/CoreyLeath-code/LogSight-AI/pull/64)).
- [x] **Phase 3 — stable event identity:** UUID propagation through Kafka,
  ClickHouse schema migration and replay ID tests
  ([PR #63](https://github.com/CoreyLeath-code/LogSight-AI/pull/63)).
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

### Stable event identifiers (candidate PR)

New enriched events are assigned UUID identifiers, serialized into the Kafka
envelope, validated by the ClickHouse worker, and persisted in an additive
ClickHouse column. Replays of the same broker record carry the same identifier.
New databases include the column and existing installations require an explicit
additive SQL migration.

This is traceability groundwork, **not duplicate prevention**: the current
MergeTree table can store multiple rows with the same UUID, and an HTTP retry
creates a new identifier. A reviewed idempotency-key contract, database
deduplication strategy, replay tests, and actual broker/storage recovery evidence
are required before the Phase 3 exit gate can close.

### HTTP retry identity propagation (candidate PR)

An optional canonical UUIDv4 `Idempotency-Key` header on the single-log API
endpoint replaces that generated event's identifier. The same header on a
later client retry produces the same UUID, so the broker record and stored row
can be correlated after ambiguous acknowledgements. Validation rejects
invalid/noncanonical keys; default calls and batch elements still receive
independent UUIDs.

**Not completed:** this does not guarantee a single Kafka publish or
ClickHouse row. It does not bind a key to a tenant, immutable payload,
retention period, response cache, or transactional batch. Durable deduplication
and tenant-scoped authorization must be implemented and reviewed before
calling this an idempotency mechanism.

### Experimental malformed-record quarantine (candidate PR)

An optional `LOGSIGHT_KAFKA_DLQ_TOPIC` routes invalid message envelopes to a
separate Kafka topic; it commits the source offset **only after** the DLQ publish
is acknowledged by the broker. Unconfigured/failed DLQ delivery blocks offset
progress. Storage failures remain fatal and uncommitted rather than being
misclassified as poison records. Tests cover quarantine acknowledgement order,
missing DLQ acknowledgement, and validation errors.

**Remaining production gates:** DLQ carries original bytes and must have
restricted ACLs, authenticated/encrypted transport, retention/deletion, audited
access, and a reviewed sanitization process. It currently has no authorized
replay CLI, deduplication guarantee, poison-event repair protocol, retry budget,
or live-broker recovery proof. Never enable this for untrusted workloads without
an approved data governance design.

### Offline DLQ envelope verification (candidate PR)

An offline operator utility validates existing restricted dead-letter
envelopes, original-byte checksum, source coordinates, and input size without
printing or republishing the payload. Tests reject mutated checksums,
encodings, versions and coordinates, and check that metadata-only reports do
not expose representative secrets. This is an incremental prerequisite to a
controlled replay runbook.

**Not completed:** no automatic replay, tenant authorization, repair approval,
data-retention enforcement, payload sanitization guarantee, durable deduplication,
live-broker integration, or operational recovery drill is implemented.

### Partition-scoped consumer offsets (candidate PR)

The ClickHouse worker now uses explicit Kafka `TopicPartition` offset maps
rather than `commit()` without arguments, which may advance the positions
of multiple assigned partitions. After an acknowledged ClickHouse write or
dead-letter publish, only the corresponding source record's next offset is
committed. Regression tests cover separate partitions, a storage outage,
and the DLQ acknowledgement path.

**Not phase completion:** inserts can still be duplicated if a broker offset
commit fails after a successful ClickHouse write. Real rebalance, concurrent
worker, retention, replay, and broker failure tests remain required.

### Bounded ClickHouse insert deduplication (candidate PR)

The consumer uses each event's canonical UUID as a deterministic
ClickHouse insert-deduplication token for its single-row INSERT. Initial
non-replicated MergeTree DDL configures
`non_replicated_deduplication_window=10000`; an explicit migration is
provided for existing tables. Tests verify deterministic tokens, distinct
IDs, rejection of malformed IDs, and propagation of database failures.

**Limit:** deduplication is a finite block-history mechanism, not an
event_id uniqueness constraint or cross-cluster transaction. Live
integration testing and restart/rebalance fault injection are pending;
multi-tenant identity, retention and replay control are unresolved.

### Opt-in real-dependency recovery drill harness (candidate PR)

An explicit, opt-in integration test exercises a synthetic Kafka event
against a real Kafka broker and ClickHouse database. It injects a
storage failure before offset commit, retries the same record, then
replays it after successful persistence and verifies the expected row
count while the bounded ClickHouse dedup window applies. A unit test
simulates ClickHouse write success followed by Kafka offset-commit
failure and confirms replay preserves the event identifier.
[Runbook](KAFKA_CLICKHOUSE_RECOVERY_DRILL.md) documents isolated
configuration and evidence collection.

**Evidence gap:** the live integration test is skipped by ordinary CI.
The runbook and test are authored, not proof that a broker/database
drill ran successfully. Actual connection, restart, rebalance,
broker outage and authenticated deployment conditions remain
unverified and Phase 3 remains open.

### Kafka TLS/SASL client settings (candidate PR)

The API producer, worker consumer and restricted DLQ producer now share
validation for PLAINTEXT development mode, TLS certificate verification
(`SSL`), and `SASL_SSL` with PLAIN or SCRAM credentials. SASL over
unencrypted Kafka is prohibited, and inconsistent credential settings
fail before establishing a broker connection. Unit tests exercise validation
and the resulting verified TLS context.

**Not complete:** the local Compose broker remains plaintext; no broker
ACL, secret-store injection, broker identity provisioning, authenticated
live recovery test, mTLS client certificate policy, credential rotation,
or secured ClickHouse endpoint is certified. Phase 3 exit remains open.

### ClickHouse HTTPS client authentication foundation (candidate PR)

The ClickHouse HTTP adapter supports verified HTTPS, optional private CA,
username/password authentication via request headers, and strict URL
validation. Credential pairs on plaintext HTTP and URL-embedded credentials
are rejected. The experimental consumer accepts those values from
environment-based secret injection; tests inspect the TLS context and
credential placement without connecting to a real database.

**Open requirements:** deployed HTTPS endpoint, secret-manager injection,
least-privilege ClickHouse database permissions, credential rotation,
identity isolation, audit logging, approved retention, and a live
authenticated broker/database recovery test.

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

### API liveness/readiness separation (candidate PR)

The API exposes `/health` for independent process liveness and `/ready`
for local Kafka-producer lifecycle readiness when broker-acknowledged
ingestion is enabled. The Helm chart routes the readiness probe to
`/ready`. Tests check healthy/degraded readiness and that application
bearer tokens are still required for operational endpoints.

**Limit:** this is lifecycle-aware, not a continuous external dependency
health check. Kafka broker connectivity after startup, ClickHouse health,
Redis, inference workers, multi-pod probe behavior, and staging alerts
must still be tested. No Phase 4 production exit is claimed.

### Kafka acknowledgement-aware readiness (candidate PR)

The experimental API Kafka producer now records failed acknowledgements,
timeouts and cancelled publishes as not-ready. Subsequent successful
broker-acknowledged publishing can restore readiness. `/health` remains
a lightweight independent liveness probe while `/ready` reflects the
local producer state and observed delivery errors. Tests cover transitions
and actual FastAPI responses.

**Incomplete:** idle broker failures are not detected until a send, and
traffic removal can prevent a successful write from restoring readiness
without an operator action. There is no periodic bounded authenticated
health probe, deployment failure drill, or evidence of downstream durable
delivery. This does not close Phase 4.

### Optional bounded Kafka idle metadata checks (candidate PR)

An opt-in periodic task makes fresh metadata requests for the configured
topic, with a bounded timeout and no synthetic writes, so `/ready` can
degrade on idle broker outages and recover on subsequent successful
metadata reads. Tests cover transport failure, timeout, empty metadata,
interval validation and lifecycle cancellation.

**Exit gap:** this is a broker metadata probe, **not** a write-path,
replication, queue-lag, ClickHouse, or end-to-end durability guarantee.
An unavailable write path may coexist with responsive metadata. Live
authenticated Kafka failure/recovery drills, alerting, HA behavior,
controlled retry budgets, and real deployment evidence remain open.

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
