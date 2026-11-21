# Phase 4 — Staging alert delivery and acknowledgment evidence

**Status: offline evidence validator, not an executed drill.** Use only in an
approved, isolated staging environment; synthetic signals and an approved
notification sink must be configured by an operator.

Prerequisites: authenticated metrics scrape, verified Prometheus rule
evaluation, an Alertmanager receiver with a named on-call owner, independent
observation of the failure signal, UTC clocks, pre-approved acknowledgment
deadline and an authorized rollback path. A passing static rule check or
`ServiceMonitor` render **does not** prove these prerequisites.

Record the signal, alert firing, receiver delivery and human acknowledgment
timestamps as `signal_at_utc`, `fired_at_utc`, `delivered_at_utc` and
`acknowledged_at_utc`. Provide explicit `true` for `source_observed`,
`alert_fired`, `receiver_delivered`, and `operator_acknowledged`, plus
`approved_max_ack_seconds`. Include nonempty `environment`, `operator`,
`reviewer`, `approval_ticket`, `git_revision`, `image_digest`,
`alert_name`, `receiver_reference`, and at least one restricted HTTPS
`evidence_links` URL. Do not commit filled real-world records, endpoints,
credentials or alert payloads to this repository.

Run `python -m logsight.alert_evidence /secure/path/staging-alert.json`.
Exit 0 means the **submitted** record meets its declared acknowledgment
deadline, exit 1 means that deadline was exceeded, and exit 2 means the
evidence is missing or inconsistent. The output contains only a pass/fail
indicator and signal-to-acknowledgment interval.

This validator does not send notifications, authenticate evidence links,
prove availability SLIs, or verify operator identity. Independent reviewers
must inspect original Prometheus/Alertmanager events and acknowledge
that missing-target alerts, counter reset handling, authentication, and
recovery behavior have been demonstrated before any Phase 4 sign-off.
