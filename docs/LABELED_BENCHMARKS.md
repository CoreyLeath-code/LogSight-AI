# Labeled benchmark corpus

The versioned corpus at `benchmarks/corpus/v1/events.jsonl` measures the deterministic baseline detector against reviewed, synthetic labels. It contains no customer, credential, or production log data.

## Record contract

Each non-empty JSONL record requires:

```json
{
  "id": "db-001",
  "level": "ERROR",
  "message": "database connection pool timeout during checkout",
  "is_anomaly": true,
  "incident_id": "database-timeout"
}
```

Anomalous records must have an `incident_id`; normal records use `null`. The manifest records the corpus schema, version, data classification, label meaning, and record count. Corpus changes need review, a version increment, and re-baselined results.

## Measurements

`logsight benchmark` invokes the repository's deterministic anomaly detector and reports:

- entry-level precision, recall, and F1;
- incident recall: the share of labeled incident groups with at least one alert;
- total alerts;
- alerts per 1,000 events;
- false alerts per 1,000 events;
- alerts per true incident.

An alert-volume metric is not an availability or customer-impact metric. It quantifies detector output for this fixed corpus only. The corpus is a regression signal, not a claim that the detector is calibrated for every production workload.

## Run and gate

```bash
logsight benchmark
logsight benchmark \
  --min-precision 0.95 \
  --min-recall 0.90 \
  --max-alerts-per-1000-events 250
```

Gates are intentionally supplied by the deployment or release process: the project does not hard-code a universal production threshold. A failed gate returns a non-zero exit code after printing measured values.

Before promotion, use a representative, approved, de-identified corpus with an immutable version; evaluate both false-negative risk and alert fatigue; record the corpus version, detector threshold, and metrics with the release; and obtain human approval for any change to the label taxonomy or gate.
