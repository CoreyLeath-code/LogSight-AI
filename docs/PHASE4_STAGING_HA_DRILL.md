# Phase 4 — Staging high-availability and disruption validation

> **Status: proposed test plan, not an executed staging drill.** Helm default
> configuration and its unit tests do not establish actual high availability.

## Preconditions

- Obtain environment-owner approval, approved rollback target, and a named
  incident observer. Use **isolated staging** with synthetic requests/logs.
- Pin a tested image digest, Helm values revision, node/pod topology and
  autoscaling resource metrics provider. Record the named Kafka/Redis/ClickHouse
  staging dependencies, their authorization boundaries, and agreed failure
  budgets without sharing credentials or original event content.
- Confirm readiness and liveness use `/ready` and `/health` respectively.
  Verify the cluster has the resources to schedule spare replicas and the PDB
  is admitted; an HPA minimum of two is not a guarantee of node diversity.
- Enable an authorized, independently observed traffic generator and an
  external success/latency measurement before injecting any failure.

## Required scenarios and observations

| Scenario | Isolation and safety | Evidence before promotion |
|---|---|---|
| Evict one API pod | Approved staging namespace; honor PDB | Eviction response, ready replica count, load generator error/latency intervals, recovery time |
| Rollout a new revision | Approved immutable image digest, rollback known | Availability throughout rollout, pod transitions, verified post-rollout acceptance |
| Lose a staging node | Dedicated isolated pool only | Replica rescheduling across nodes, service continuity, HPA/PDB state, load loss |
| Dependency partition | Authorized nonshared Kafka or Redis only | `/ready` degrades while `/health` remains process-local, rejected ingest behavior and recovery |
| Resource saturation | Bounded synthetic workload with abort budget | HPA scale signal, scale-up time, saturation/queue lag, request success and latency |
| Inference/ClickHouse failure | Isolated worker/store, preserve Kafka topic | At-least-once replay, offset safety and duplicate-risk reconciliation |

For each experiment record UTC start/end, authorized commands, expected versus
observed availability SLI, errors, alerts and acknowledgments, Kafka offsets,
ClickHouse event IDs/counts and the exact recovery/rollback. Stop immediately
when effects exceed the approved namespace or resource budget.

## Pass/fail record

- Owner/observer, staging namespace/cluster, approval ticket and UTC time:
- Exact Git revision, chart revision, image digest and values fingerprint:
- Scenario, authorized fault, baseline service SLI and approved thresholds:
- Load profile, observed errors/latency/recovery and HPA/PDB transitions:
- Kafka offsets, rejected or uncertain deliveries, dedup/replay analysis:
- Alert delivery, acknowledgment, rollback and post-failure verification:
- Evidence links, reviewer and explicit pass/fail/unknown decision:

The final Phase 4 gate also needs authenticated metrics collection, SLO alerts,
backup/restore evidence, representative soak/load testing and accountable
sign-off. Leave the phase-level checkbox open until each is verified.
