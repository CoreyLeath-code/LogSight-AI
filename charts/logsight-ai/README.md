# LogSight-AI Helm chart

This chart deploys the LogSight API as a hardened Kubernetes workload. It expects
the image to contain the `api` extra and leaves Redis, OTLP, and distributed
inference services as deployment-owned dependencies.

## Install

```bash
helm upgrade --install logsight-ai ./charts/logsight-ai \
  --namespace logsight --create-namespace \
  --set image.repository=registry.example/logsight-ai \
  --set image.tag=IMMUTABLE_DIGEST_OR_TAG
```

## Production configuration

The chart defaults to two replicas, an HPA, a PDB, non-root/read-only container
security, a dedicated service account without a token, and a restrictive
NetworkPolicy. The default NetworkPolicy permits only ingress from the
`ingress-nginx` namespace and DNS egress. Add explicit `networkPolicy.extraEgress`
rules before configuring Redis, OTLP, Kafka, ClickHouse, or Qdrant endpoints.

Pass credentials through `extraEnvFrom` references to externally managed Secrets;
do not place connection credentials in values files. Use immutable image tags or
digests, tune resource requests from measured workload behavior, and test
autoscaling/disruption behavior in a non-production namespace before promotion.

## Optional authenticated Prometheus metrics scraping (Phase 4)

Set `serviceMonitor.enabled=true` **only** in a cluster with the Prometheus
Operator's ServiceMonitor CRD. Configure
`serviceMonitor.bearerTokenSecret.name` to reference an externally managed
Secret in the same namespace as the ServiceMonitor (default key: `token`).
The token must match `LOGSIGHT_API_TOKEN` used by the API in
`LOGSIGHT_API_AUTH_MODE=token`. Do not put the token itself in chart values,
ConfigMaps, annotations, GitHub Actions logs, or source control. Mount or
reference the API token through an externally managed secret using `extraEnv`.

**This is an opt-in manifest, not a deployed monitor.** `/metrics` is still
served on the API HTTP port. Provide TLS at an approved ingress or authenticated
service-mesh boundary: the example uses HTTP within the cluster and must not
be presented as end-to-end secure transport. Review network policy explicitly:
the chart's default ingress is restricted to `ingress-nginx`, so a Prometheus
pod cannot scrape the workload until an authorized monitoring namespace and
pod selector are added to `networkPolicy.ingress`. Verify that the collector
is allowed, that the metrics bearer token is rotated and never logged, and
that the operator selects this ServiceMonitor. Run a staging scrape, alert
routing and acknowledgment drill before claiming operational monitoring.
