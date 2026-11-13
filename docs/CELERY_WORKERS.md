# Celery Distributed Inference Workers

## Contract

`logsight.distributed.CeleryInferenceDispatcher` submits bounded JSON-only
`logsight.embed_events` tasks. Each item contains the event fingerprint, message,
and optional trace/span IDs; it never sends raw log lines or arbitrary Python
objects through the broker. The worker validates task shape, batch size, and
message size before invoking the existing embedding worker.

The Celery configuration uses JSON serialization, one-task prefetching, late
acknowledgement, rejection after a lost worker, and soft/hard task limits. These
settings make retries explicit and prevent one worker from hoarding inference work.

## Reference stack

`docker-compose.enterprise.yml` defines an idle `logsight-worker` service that
uses Redis database 0 as the broker and database 1 as the result backend. It is
built with the `workers,ai` extras and starts with two worker processes.

API dispatch is deliberately disabled by default:

```bash
export LOGSIGHT_CELERY_DISPATCH_ENABLED=true
export LOGSIGHT_CELERY_BROKER_URL=redis://redis:6379/0
export LOGSIGHT_CELERY_RESULT_BACKEND=redis://redis:6379/1
export LOGSIGHT_EMBEDDING_MODEL=/models/approved-embedding-model
```

Enable dispatch only after a model artifact is provisioned and the worker image
has access to it. With dispatch enabled, accepted API events include
`inference_task_id`; inference remains asynchronous and does not alter the
request-time anomaly score.

## Production promotion

Use separate Redis users/databases, TLS, authentication, network policies, and
queue-depth/worker-health alerts. Set concurrency from measured model memory and
latency, retain task results only as long as needed, and use a deployment-owned
immutable model artifact. This implementation provides the Celery path; Ray
orchestrators can be added later behind the same bounded task envelope rather
than exposing runtime objects over the broker.
