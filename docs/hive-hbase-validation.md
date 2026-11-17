# Validation status

## Automated checks

- `python -m unittest discover -s tests -v`: 17 tests pass. Ten check the scripts with fake clients (argument
  forwarding, month/base validation, OK and ALERT rows, malformed export rejection, failure propagation). Seven run
  the six report SELECTs on SQLite fixtures (calculation check only, not Hive execution).
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

Reports 1-5 returned no rows because the curated tables had no data yet.

## Still to do

1. Add `dewa.tariffs`, `dewa.weather`, `dewa.bank_holidays`, `dewa.customers` once their columns are agreed.
2. Re-run on the real Spark output (cleaned and curated tables, `meter_status`) and on the full data.
3. Save screenshots in `screenshots/hive/` and `screenshots/hbase/`.
