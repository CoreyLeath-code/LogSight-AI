# Phase 4 — Staging soak acceptance evidence

**Status: validation tool only. No load, failure injection, or monitoring drill
was executed by adding these files.**

Use isolated staging, synthetic traffic, a named operator and reviewer, and
pre-approved success-rate, p95 latency, and duration targets. Record external
measurements and source logs in access-controlled storage. Capture dependency
recovery and alert acknowledgments separately. Do not store credentials,
customer traffic, raw logs or private data in Git.

After an approved staging run, build a restricted JSON evidence record
containing: `environment`, `operator`, `reviewer`, `approval_ticket`,
`git_revision`, `image_digest`, `load_profile_reference`,
`requests_total`, `requests_successful`, `requests_failed`,
`duration_seconds`, `p95_latency_ms`,
`approved_min_success_ratio`, `approved_max_p95_latency_ms`,
`approved_min_duration_seconds`, `dependency_recovery_verified` and
`evidence_links` (HTTPS references).

Run `python -m logsight.soak_evidence /secure/path/staging-soak.json`.
Exit 0 means the submitted record met the **declared** thresholds, exit 1
means it did not, and exit 2 indicates incomplete/invalid data. Thresholds
are not hardcoded because they require accountable owner approval.

This evaluator checks consistency and basic acceptance arithmetic; it cannot
prove source authenticity, p95 calculation correctness, traffic
representativeness, independent alert delivery, sustained availability, or
that a real staging experiment happened. A reviewer must verify all evidence
and independently confirm the live SLI/alert and backup/restore records before
checking off Phase 4.
