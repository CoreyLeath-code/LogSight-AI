# Phase 4 — Staging rollout and monitoring evidence

**Status: evidence contract only. No staging cluster was contacted or deployed
by this change.** Use an authorized, isolated environment and a reviewed,
digest-pinned artifact; follow the approval and rollback procedures in
`PHASE4_STAGING_FAILURE_RECOVERY_DRILL.md`.

## Operator evidence checklist

1. Obtain change approval, choose a named operator and **different** reviewer,
   record the staging namespace, Helm release, reviewed values revision, Git
   commit SHA, rollback digest, and deployment window.
2. Verify the image digest from the reviewed container registry artifact. Set
   `image.requireDigest=true` and pin `image.digest`; record the resulting
   **full** `repository@sha256:...` reference. Do not use a mutable tag.
3. With explicit staging access, collect Deployment rollout status and pod
   status from Kubernetes. Compare desired, ready, and updated replica counts,
   and confirm the actual running image digest equals the intended digest.
4. Execute the read-only authenticated scrape preflight described in
   `PHASE4_STAGING_SCRAPE_PREFLIGHT.md`. Independently verify the Prometheus
   target and `up` series from the monitoring operator's environment.
5. Store sanitized, access-controlled evidence links (no tokens, logs with
   customer events, raw payloads or credentials). Record UTC rollout times.
   Have a reviewer inspect original cluster, registry and monitoring records.

Build a restricted JSON record with these keys: `environment`, `namespace`,
`operator`, `reviewer`, `approval_ticket`, `helm_release`,
`values_revision`, `git_revision`, `expected_image`, `observed_image`,
`desired_replicas`, `ready_replicas`, `updated_replicas`,
`rollout_completed`, `authenticated_scrape_observed`,
`rollout_started_at_utc`, `rollout_finished_at_utc`, and `evidence_links`
(a nonempty list of HTTPS references). The image values are full identical
`repository@sha256:...` references, not only hashes.

Run `python scripts/validate_staging_deployment_evidence.py /secure/path/rollout.json`.
Exit 0 means the **submitted record** declares a completed healthy rollout
with matching digests and an observed authenticated scrape; exit 1 means replica
targets were missed; exit 2 means incomplete or invalid data.

The validator **does not verify** the source of those declarations, authenticate
evidence URLs, inspect Kubernetes itself, prove that Prometheus scraped the
target, deliver an alert, or approve any deployment. Human source review and
real staging tests remain mandatory. Backup/restore, disruption and soak-test
acceptance use their separate Phase 4 gates.
