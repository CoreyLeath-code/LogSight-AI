-- Apply to existing ClickHouse deployments before starting the new consumer.
-- This additive migration preserves old rows but cannot deduplicate history.
ALTER TABLE logsight.events ADD COLUMN IF NOT EXISTS event_id String DEFAULT '';
