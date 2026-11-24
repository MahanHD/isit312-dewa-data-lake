# MapReduce vs Spark

The report argues MapReduce is too slow for this workload. This folder measures it: the same job (hourly kWh per
meter from `raw/readings`, dropping null and negative readings but keeping duplicates) written as a Hadoop streaming
job in Python, as in Lab 3, and in Spark.

| File | What it is |
|---|---|
| `hourly_mapper.py` | map: one raw reading to `meter_id, hour_ts, kwh, 1` |
| `hourly_reducer.py` | reduce, also used as the combiner: sums kWh and readings per meter and hour |
| `run_hourly.sh` | runs the streaming job, writes `tmp/mr_hourly` |
| `spark_hourly.py` | the same job in Spark, writes `tmp/spark_hourly` |
| `compare.py` | checks both outputs have the same rows |

```bash
docker compose exec namenode bash /workspace/mapreduce/run_hourly.sh
docker compose exec spark spark-submit --master 'local[8]' /workspace/mapreduce/spark_hourly.py
docker compose exec spark spark-submit /workspace/mapreduce/compare.py
```

## Result on the full data (167.9M readings, 8 GB)

| | MapReduce | Spark |
|---|---|---|
| Time | 231 s | 124 s |
| Hourly rows | 83,925,571 | 83,925,571 |
| Readings counted | 167,926,914 | 167,926,914 |

Same output, Spark 1.9x faster. Both ran on one machine with 8 parallel tasks (MapReduce in local mode, since the
stack has no YARN; Spark in `local[8]`). With all 16 threads Spark took 103 s. MapReduce writes map output to disk
and sorts it before every reduce, while Spark keeps the aggregation in memory, and the gap grows with jobs that
have more steps, such as cleaning, then totals, then anomalies.

A first run gave one extra row: an hour whose two readings were split across two input files came out as two rows.
The combiner's output is re-read with the reduce key setting, which defaults to one field, so after combining the
key was only `meter_id` and the two halves were no longer sorted next to each other.
`stream.num.reduce.output.key.fields=2` fixes it.

On 25 Nov the job ran out of memory, because in local mode the 8 reducers share one 4 GB heap and each one may fill
70% of it during the shuffle. `mapreduce.reduce.shuffle.input.buffer.percent=0.08` gives each its share. With that
setting a second run took 237 s in MapReduce and 94 s in Spark, again with the same output
(`screenshots/mapreduce/01-mapreduce-vs-spark.png`). Times vary between runs; the table above is the first run.
