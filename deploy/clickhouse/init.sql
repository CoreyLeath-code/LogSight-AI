CREATE DATABASE IF NOT EXISTS logsight;

CREATE TABLE IF NOT EXISTS logsight.events
(
    timestamp DateTime64(3, 'UTC'),
    level LowCardinality(String),
    service LowCardinality(String),
    source LowCardinality(String),
    host LowCardinality(String),
    message String,
    raw String,
    trace_id Nullable(String),
    span_id Nullable(String),
    template Nullable(String),
    fingerprint String,
    attributes String
)
ENGINE = MergeTree
PARTITION BY toDate(timestamp)
ORDER BY (service, timestamp, fingerprint)
TTL toDateTime(timestamp) + INTERVAL 30 DAY;
