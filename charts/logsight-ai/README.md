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
When enabled, the chart explicitly sets `LOGSIGHT_API_AUTH_MODE=token`
and injects `LOGSIGHT_API_TOKEN` using the **same external Secret/key**
referenced by the ServiceMonitor, preventing an unauthenticated metrics
endpoint due to missing manual API configuration. Do not separately set these
environment variables through `env` or `extraEnv`; Helm rejects duplicates.
The application also rejects tokens shorter than 32 characters at startup.
Ensure the Secret already exists in the chart's namespace, is accessible to
both the API pod and Prometheus Operator, and is rotated by the deployment
owner. Never put the token value in chart values, ConfigMaps, annotations,
GitHub Actions logs or source control.

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

## Opt-in restricted monitoring NetworkPolicy ingress

The chart's default ingress still excludes monitoring collectors. Once an
operator has approved namespace/pod labels, set
`networkPolicy.monitoringIngress.enabled=true` and configure
`networkPolicy.monitoringIngress.namespaceLabels` and
`networkPolicy.monitoringIngress.podLabels` to select **only** the
authorized Prometheus collector pods in their approved namespace.
This feature is disabled by default and requires both the NetworkPolicy
and ServiceMonitor to be enabled. Missing selectors cause Helm rendering
to fail instead of allowing unrestricted ingress.

Example values (illustrative labels, not a verified cluster):

```yaml
serviceMonitor:
  enabled: true
  bearerTokenSecret:
    name: externally-managed-scrape-token
    key: token
networkPolicy:
  enabled: true
  monitoringIngress:
    enabled: true
    namespaceLabels:
      kubernetes.io/metadata.name: monitoring
    podLabels:
      app: prometheus
```

These label names and values must be verified against actual staging
resources. NetworkPolicy permits TCP on the API service port, not just
`/metrics`; application bearer-token auth must remain enabled and the
network/mesh must enforce the approved TLS transport. This does not create
a Prometheus instance, Secret, receiver, or a successful staging scrape.

## Immutable staging image pinning

For approved staging and release validation, set `image.requireDigest=true`
and provide `image.digest` as `sha256:` followed by **64 lowercase
hexadecimal characters** from a verified OCI registry artifact. The chart
renders `repository@sha256:…` and ignores `image.tag` when a valid digest
is supplied. Without a digest, default development installs retain their
tag-based behavior; **do not use a mutable tag as staging promotion evidence**.

Example values (a placeholder digest is **not** a real published artifact):

```yaml
image:
  repository: registry.example/logsight-ai
  digest: "sha256:REPLACE_WITH_64_LOWERCASE_HEX_CHARACTERS"
  requireDigest: true
```

Obtain the digest from the actual reviewed and scanned registry artifact;
record image source, Git SHA, signatures where supported and rollback digest
in the restricted staging deployment record. A render-only digest check does
not verify artifact provenance, a real registry, vulnerability posture, or
successful deployment. The default Helm install example above is for
development and should not be copied as a staging promotion record.
