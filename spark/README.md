# Spark jobs

Start each job from `_template.py`. Paths, schemas and the rules every job follows are in the main README
(Shared rules 1-5). Run a job with:

```bash
docker compose exec spark spark-submit spark/<job>.py
```

## Job order

| # | Job | Reads | Writes |
|---|---|---|---|
| 1 | `clean_readings.py` | `raw/readings` | `cleaned/readings` |
| 2 | `clean_sources.py` | `raw/tariffs`, `raw/weather`, `raw/bank_holidays`, `raw/customers` | `cleaned/<source>` |
| 3 | `aggregates.py` | `cleaned/readings` | `curated/hourly_usage`, `curated/daily_usage` |
| 4 | `anomalies.py` | `cleaned/readings`, `curated/daily_usage` | `curated/anomalies` |
| 5 | `meter_status.py` | `cleaned/readings`, `curated/anomalies` | `curated/meter_status` (CSV, for HBase) |
| - | `stream_*.py` | a folder of replayed readings | live demo only, not part of the batch run |

Each job overwrites its own output, so a job can be re-run on its own once the jobs before it have run.
Test on the sample first (main README, How to run step 1), then on the full data.

## Anomaly rules

TODO: agree on the rules, then list each one here with its `anomaly_type` value, the condition, and why it matters
for DEWA. `meter_status.py` sets `alert_status = ALERT` for a meter whose latest anomaly is recent.

| `anomaly_type` | Condition | Why |
|---|---|---|
| TODO | TODO | TODO |
