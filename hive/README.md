# Hive reporting

Run from the repository root with the stack running:

```bash
docker compose exec hive bash /workspace/hive/run.sh hive/01_create_tables.hql
# After the Spark teammate has produced cleaned/curated Parquet:
docker compose exec hive bash /workspace/hive/run.sh hive/03_refresh_partitions.hql
docker compose exec hive bash /workspace/hive/run.sh hive/02_reports.hql 2013-01
```

`./run_pipeline.sh` runs these three after the Spark jobs (see `docs/pipeline-runner.md`).

`hive/04_bucketed_daily.hql` is a standalone bucketing demo run separately from the normal batch pipeline.

Choose a month present in `SHOW PARTITIONS dewa.daily_usage;`. Empty results before
Spark runs are expected and do not prove that the integration works. Raw readings
can be queried immediately after loading the repository sample. The four raw CSV
columns are mapped positionally to readable aliases; values remain strings.
`skip.header.line.count=1` applies per input file. Do not put non-CSV files there.

On the VM use `hive --hivevar base=/dewa --hivevar report_month=2013-01 -f hive/02_reports.hql`
(and the analogous command for table creation and repair). With Beeline, run.sh
also works outside Docker; override HIVE_JDBC_URL if necessary.

All tables are external. This implementation never writes source files or drops
tables. IF NOT EXISTS is rerunnable but does not migrate existing schemas or
locations: inspect DESCRIBE FORMATTED before using an existing metastore. Changing
DEWA_BASE does not relocate already-created tables. MSCK discovers new partitions;
on Hive 2 it does not remove stale metastore partitions after Spark removes files.

## Extra tables

`dewa.tariffs`, `dewa.weather`, `dewa.bank_holidays` and `dewa.customers` use the
columns from Shared rules 8. They read the Parquet files that `spark/clean_sources.py`
writes to `cleaned/<name>`. They're not partitioned, so no MSCK REPAIR needed.
Hive matches Parquet columns by name, so a wrong column name gives NULLs, not an error.

## Evidence and interpretation

Capture real output under screenshots/hive/: table list and DESCRIBE FORMATTED,
raw sample rows, SHOW PARTITIONS, reports for a populated month, and EXPLAIN for a
month-filtered query. Compare report 6's cleaned kWh sum with report 1's monthly
sum (allow floating-point rounding). Record row counts, month, data scope and
execution time; the five-household sample does not establish full-scale performance.

Missing readings are coverage indicators, not confirmed meter failures. A day with
no records is absent from daily_usage and is not detected by report 5. London
wall-clock timestamps are preserved by the Spark contract; DST and partial first/
last days complicate a fixed 48-reading expectation. No report claims DEWA billing
accuracy, water consumption, or actual DEWA customer behaviour.
