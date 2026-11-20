-- Run manually against existing NON-REPLICATED MergeTree deployments.
-- This enables only bounded insert-block deduplication, not unique event IDs.
-- Validate engine and version before applying; test on a staging database first.
ALTER TABLE logsight.events MODIFY SETTING non_replicated_deduplication_window = 10000;
