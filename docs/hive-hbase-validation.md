# Validation status

## Automated checks

- `python -m unittest discover -s tests -v`: all tests pass. For Hive and HBase, `tests/test_hive_hbase_scripts.py`
  checks the scripts with fake clients (argument forwarding, month/base validation, OK and ALERT rows, malformed
  export rejection, failure propagation) and `tests/test_hive_reports.py` runs the report SELECTs on SQLite fixtures
  (calculation check only, not Hive execution).
- `bash -n hive/run.sh hbase/02_load.sh`, `docker compose config --quiet`.

HBase 2.6.7 source review: ImportTsv keeps a trailing empty field and writes empty values when
`skip.empty.columns=false`, but it accepts missing trailing columns, hence the stricter six-field preflight.

## Live run on the team stack (18 Nov 2026)

Run on the Docker stack (HDFS 3.4.3, Hive 4.2.1, HBase 2.6.7, Spark 4.2.1) with the repository sample, in a
separate base folder (`DEWA_BASE=/dewa_check`) and Spark output built from the sample.

| Check | Result |
|---|---|
| `hive/01_create_tables.hql` | five tables created |
| `dewa.raw_readings` | sample rows read correctly, header skipped |
| `hive/03_refresh_partitions.hql` | month partitions found for `dewa.readings` |
| `dewa.readings` | Spark Parquet read, timestamps unchanged |
| `hive/02_reports.hql 2013-01` | all six queries run; report 6 matches Spark (6,677 rows, 5 meters, 1134.1 kWh) |
| `hbase/02_load.sh` | 5 rows imported, 0 bad lines |
| ALERT -> OK reload | `a:type` and `a:ts` cleared |
| Malformed row (ALERT without type) | rejected by preflight, nothing written |
| `hbase/03_verify.rb` | runs |

At this point the curated tables were still empty and only the first five tables and six reports existed. The full
run below covers the rest.

## Full data run (Nov 2026)

`run_pipeline.sh` on the full data (the Compose stack on Podman, one laptop), checked again on 24 Nov 2026.

| Check | Result |
|---|---|
| `hive/01_create_tables.hql` | nine tables created, all with data |
| `dewa.readings` | 167,811,461 rows |
| `dewa.hourly_usage`, `dewa.daily_usage` | 83,925,571 and 3,510,403 rows; `readings` adds up to 167,811,461 in both |
| Daily totals against cleaned readings, 2013-01 | 8,184,185 readings and 2,155,819.36 kWh in both |
| `dewa.anomalies` | 2,841 spikes on 1,322 meters, 1,907 zero runs on 232 meters |
| `dewa.tariffs`, `weather`, `bank_holidays`, `customers` | 17,520, 20,424, 32 and 5,566 rows, no NULL prices, temperatures, names or areas |
| `hive/02_reports.hql 2013-01` | all 13 reports run, also from the Zeppelin dashboard |
| `hbase/02_load.sh` | 5,561 rows imported, 0 bad lines; 85 `ALERT`, 5,476 `OK` |
| Slow first start (NameNode delayed 75 s, empty volumes, sample) | HBase waits, pipeline exits 0, 5 rows imported |
