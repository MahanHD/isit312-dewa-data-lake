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
| 4 | `anomalies.py` | `cleaned/readings` | `curated/anomalies` |
| 5 | `meter_status.py` | `cleaned/readings`, `curated/anomalies` | `curated/meter_status` (CSV, for HBase) |
| - | `stream_*.py` | a folder of replayed readings | live demo only, not part of the batch run |

Each job overwrites its own output, so a job can be re-run on its own once the jobs before it have run.
Test on the sample first (main README, How to run step 1), then on the full data.

## Anomaly rules

Both rules compare a meter with its own history, since households use very different amounts. Thresholds are
constants at the top of `anomalies.py`.

| `anomaly_type` | Condition | Why it matters for DEWA |
|---|---|---|
| `spike` | a half hour above 1.5 x the meter's own 99.9th percentile **and** at least 2 kWh | sudden heavy load: a faulty appliance, an overload risk, or a meter error worth checking |
| `zero_run` | at least 48 readings in a row (one day) of exactly 0 kWh; one event per run, at its first reading | a stuck or disconnected meter, or an empty property |

On the full data this gives about 2,850 spikes on about 1,320 meters (the percentile is approximate, so counts
shift slightly between runs) and 1,907 zero runs on 232 meters. The first spike rule
tried (mean + 4 standard deviations) flagged 959,727 half hours and put 54% of meters on ALERT, so it was dropped.

## meter_status export

`meter_status.py` writes one row per meter to `curated/meter_status`, in the order of Shared rules 4, as CSV with no
header. A meter is `ALERT` when its latest anomaly is within 7 days before its last reading (the data is historical,
so this is measured from the last reading, not from today); `alert_type` and `alert_ts` come from that anomaly and are
empty for `OK` meters. Timestamps are `yyyy-MM-dd HH:mm:ss` and kWh has 3 decimals. Empty fields must stay unquoted,
because `hbase/02_load.sh` rejects quotes. On the full data, about 85 of 5,561 meters are `ALERT`; on the sample, 3 of 5.
