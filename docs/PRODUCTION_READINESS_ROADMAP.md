# Production-readiness roadmap

## Current status

LogSight-AI has a strong engineering baseline: dependency-light local analysis,
optional enterprise adapters, CI quality/security controls, a hardened container,
a Helm chart, and versioned quality benchmarks. It is **not yet approved for an
internet-facing, multi-tenant, or consequential production deployment**.

This roadmap is a promotion contract, not a list of features. An item is complete
only when its code, configuration, automated tests, operational evidence, and
owner approval are linked from a reviewed pull request or release record.

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
