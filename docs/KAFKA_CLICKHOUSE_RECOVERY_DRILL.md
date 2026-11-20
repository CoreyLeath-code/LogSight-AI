# Disposable Kafka + ClickHouse recovery drill

This is an **opt-in, destructive-to-test-data** integration check. Use only a
new local or isolated staging environment with **synthetic logs**, never a
production broker, tenant topic, or ClickHouse database. It is not part of
routine PR CI and does not by itself certify production durability.

## Preflight

1. Install Docker Compose, Python 3.11, and the repository's development
   dependencies including Kafka: `python -m pip install -e ".[dev,kafka]"`.
2. Start the dependencies from the repository root:
   `docker compose -f docker-compose.enterprise.yml up -d kafka clickhouse`.
3. Confirm ClickHouse initialized its schema (or apply the SQL below to an
   **empty disposable** ClickHouse instance):
   `docker compose -f docker-compose.enterprise.yml exec -T clickhouse clickhouse-client --multiquery < deploy/clickhouse/init.sql`.
   For an existing *isolated test* database with the old schema, apply
   `deploy/clickhouse/migrations/001_event_id.sql` and then
   `002_bounded_insert_dedup.sql` instead. Do not run migrations blindly
   against an actual deployment.
4. Create a **new empty topic** specifically for this test. For example:
   `docker compose -f docker-compose.enterprise.yml exec kafka rpk topic create logsight-recovery-probe`.
   The topic must have no consumer traffic and no previous messages. Verify
   the Redpanda advertised listeners permit access from the test host.

## Run

Set these environment variables in your shell or CI environment:

```bash
export LOGSIGHT_RUN_DURABILITY_INTEGRATION=1
export LOGSIGHT_INTEGRATION_KAFKA_BOOTSTRAP=localhost:9092
export LOGSIGHT_INTEGRATION_CLICKHOUSE_URL=http://localhost:8123
export LOGSIGHT_INTEGRATION_KAFKA_TOPIC=logsight-recovery-probe
pytest -q tests/test_kafka_clickhouse_live_recovery.py --no-cov
```

The test creates one synthetic event with a unique ID, verifies that a
simulated storage error leaves the source offset uncommitted, retries the
write, seeks back to the same Kafka record to model a post-write crash,
and checks the resulting ClickHouse row count is **one** within the
configured bounded deduplication window. This exercises the real Kafka
consumer and ClickHouse HTTP insert path but is **not** a full network
partition, process-kill, rebalance, or cluster-failover drill.

## Evidence and cleanup

Record the exact commit SHA, broker and ClickHouse versions, connection
configuration (excluding secrets), test output, event ID, resulting row
count, owner, and any anomalies in a dated staging evidence record.
Delete the disposable topic and test database/environment when done.
Never run the probe on a shared or sensitive dataset.

**Unverified until actually executed:** passing routine CI does not mean
this test ran or that real duplicate prevention was observed. In addition,
bounded MergeTree deduplication is not a permanent event-ID uniqueness
constraint, and ClickHouse versions/topologies may differ.
