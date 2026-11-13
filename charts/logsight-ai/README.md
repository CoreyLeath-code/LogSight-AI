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
