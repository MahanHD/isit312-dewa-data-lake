# DEWA Smart Meter Data Lake (ISIT312 group project)

ISIT312 Big Data Management, Autumn 2026, University of Wollongong in Dubai.

We design a data lake for **DEWA (Dubai Electricity and Water Authority)** smart meter data and build a working
version of it. DEWA does not publish per-meter readings, so we use a real public dataset as a stand-in:

> **SmartMeter Energy Consumption Data in London Households** (London Datastore, UK Power Networks).
> 5,567 homes, half-hourly electricity readings, Nov 2011 - Feb 2014, ~167M rows, 8.5 GB of CSV in 168 files.
> CC BY 4.0. https://data.london.gov.uk/dataset/smartmeter-energy-consumption-data-in-london-households-vqm0d

```
source files --> HDFS data lake --------------------------------> Spark ----------------> Hive (reporting)
                 raw (as downloaded) -> cleaned -> curated        cleaning, hourly/daily   HBase (latest reading
                                                                  totals, peaks, anomalies  + alert per meter)
```

Extra sources: tariffs (Excel, same London Datastore page), London weather (JSON), UK bank holidays (JSON),
generated customer records.

## Repo layout and parts

```
compose.yaml    the whole stack in containers (+ docker/ for its config and the HBase image)
architecture/   diagrams and design notes                  Architecture + DEWA research
docs/           report notes, references, meeting notes    Architecture + DEWA research
data/           download, sample and HDFS load scripts     Data prep
spark/          Spark jobs                                 Spark
hive/           .hql files + run.sh                        Hive + HBase
hbase/          HBase table and load scripts               Hive + HBase
screenshots/    evidence for the report, one folder per part
```

Each part writes its own report section and slides; the sections are merged into one report at the end.
Screenshots are named `screenshots/<part>/NN-what-it-shows.png`.

## Environment

We use current releases in containers (the course VM is for labs only), so everyone has the same setup on
Windows, macOS or Linux.

| Tool | Version | Notes |
|---|---|---|
| Hadoop HDFS | 3.4.3 | official `apache/hadoop` image |
| Hive | 4.2.1 | HiveServer2, Tez, Derby metastore; official `apache/hive` image |
| HBase | 2.6.7 | standalone, tables stored in HDFS; built from `docker/hbase/` |
| Spark | 4.2.1 | PySpark (Python 3.10), local mode; official `apache/spark` image |

### Setup

1. Install Docker Desktop (or Docker / Podman on Linux) and give it at least **6 GB of RAM**.
2. Clone the repo and, from its folder:

   ```bash
   docker compose up -d     # first run downloads ~5 GB of images; Hive takes ~1 minute to start
   docker compose ps        # all five services should be "Up"
   ```

3. Web UIs: HDFS http://localhost:9870, Hive http://localhost:10002, HBase http://localhost:16010,
   Spark http://localhost:4040 (while a job runs).

- The repo is mounted at `/workspace` in every container: edit on your machine, run inside the containers.
- `docker compose stop` / `down` keep all data. `docker compose down -v` **deletes HDFS, Hive and HBase data**.
- Hive's `beeline` needs a terminal, so don't use `docker compose exec -T` with Hive.
- Only one machine runs the full dataset (~10 GB extra disk). Everyone else works with `data/sample/`.
- Apple Silicon: the Hadoop image is amd64-only and runs under emulation (not yet tested on a Mac).

## Shared rules

Everyone follows these from day one. To change one, say so in the group chat first, then update this README in the
same commit as the code.

### 1. HDFS paths

Base folder **`/dewa`** (`$DEWA_BASE` in scripts, `${hivevar:base}` in Hive). Use plain paths like
`/dewa/cleaned/readings`, never `hdfs://namenode:8020/...`.

| Zone | Path | Contents | Format |
|---|---|---|---|
| raw | `/dewa/raw/readings/` | the 168 original CSV files, unchanged | CSV with header |
| raw | `/dewa/raw/tariffs/` | `Tariffs.xlsx` + `tariffs.csv` (converted) | XLSX, CSV |
| raw | `/dewa/raw/weather/` | `weather_london.json` (hourly temperature, precipitation) | JSON |
| raw | `/dewa/raw/bank_holidays/` | `bank_holidays_YYYY.json`, 2011-2014 | JSON |
| raw | `/dewa/raw/customers/` | generated customer records | CSV with header |
| cleaned | `/dewa/cleaned/readings/reading_month=YYYY-MM/` | cleaned readings | Parquet |
| cleaned | `/dewa/cleaned/<source>/` | tariffs, weather, bank_holidays, customers | Parquet |
| curated | `/dewa/curated/<table>/reading_month=YYYY-MM/` | `hourly_usage`, `daily_usage`, `anomalies` | Parquet |
| curated | `/dewa/curated/meter_status/` | latest reading + alert per meter, for HBase | CSV, no header |

- **raw is never changed.** Only data prep writes there, and only by adding files.
- Only Spark jobs write to cleaned and curated; re-running a job overwrites its own output folder.
- Readings tables are partitioned **by month** (`reading_month=2013-01`, string). Daily would mean ~830 folders of
  small files, which HDFS and Hive handle badly.

### 2. Raw readings columns

| Column | Example | Notes |
|---|---|---|
| `LCLid` | `MAC000002` | meter / household id |
| `stdorToU` | `Std` or `ToU` | flat-rate or time-of-use tariff |
| `DateTime` | `2012-10-12 00:30:00.0000000` | half-hour timestamp, London local time |
| `KWH/hh (per half hour) ` | ` 0.263 ` | kWh; has spaces and `Null` values. The header ends with a space |

Lines end in `\r\n`.

### 3. Cleaned readings schema

| Column | Type | Rule |
|---|---|---|
| `meter_id` | STRING | `LCLid`, trimmed |
| `tariff_type` | STRING | `stdorToU` |
| `reading_ts` | TIMESTAMP | first 19 characters of `DateTime` |
| `kwh` | DOUBLE | trimmed, cast only if numeric (see Spark rules); null or negative rows dropped |
| `reading_month` | STRING | `YYYY-MM` from `reading_ts`, partition column |

Duplicate `(meter_id, reading_ts)` rows are dropped. All names are lower case with underscores, used exactly as
written in Spark, Hive and HBase.

### 4. Curated tables

| Table | Columns |
|---|---|
| `hourly_usage` | `meter_id STRING, hour_ts TIMESTAMP, kwh DOUBLE, readings INT` |
| `daily_usage` | `meter_id STRING, reading_date DATE, kwh_total DOUBLE, peak_kwh DOUBLE, peak_ts TIMESTAMP, readings INT` |
| `anomalies` | `meter_id STRING, reading_ts TIMESTAMP, kwh DOUBLE, anomaly_type STRING, details STRING` |
| `meter_status` | `meter_id, last_reading_ts, last_kwh, alert_status, alert_type, alert_ts` (CSV, this order) |

`readings` = number of half-hour readings in the total (48 for a full day), so gaps show. `alert_status` is `OK`
or `ALERT`. The anomaly rules go in `spark/README.md`; the column names stay fixed.

### 5. Spark

- PySpark scripts in `spark/`. They read and write HDFS paths only; no `saveAsTable`. Hive owns the tables, Spark
  owns the files.
- Code must also run on Spark 3.0.3 (the VM). So no `try_cast`; check values before casting, because Spark 4 fails
  the job on a bad cast:

  ```python
  v = F.trim(F.col("KWH/hh (per half hour) "))
  kwh = F.when(v.rlike(r"^-?[0-9]+(\.[0-9]+)?$"), v.cast("double"))   # "Null" -> null
  ```
- Start every job with `spark.conf.set("spark.sql.session.timeZone", "UTC")` so timestamps stay exactly as in the
  source (London wall-clock time).

### 6. Hive

- Database **`dewa`**. All tables `EXTERNAL`, `LOCATION '${hivevar:base}/...'`. HiveQL must also work on Hive 2.1.1.
- After Spark writes new data: `MSCK REPAIR TABLE dewa.<table>;`

| Table | Location |
|---|---|
| `dewa.raw_readings` | `raw/readings` (all STRING, `skip.header.line.count`=1) |
| `dewa.readings` | `cleaned/readings` |
| `dewa.hourly_usage`, `dewa.daily_usage`, `dewa.anomalies` | `curated/<table>` |
| `dewa.tariffs`, `dewa.weather`, `dewa.bank_holidays`, `dewa.customers` | `cleaned/<name>` |

### 7. HBase

- Table **`dewa_meter_status`**, row key `meter_id`.
- Family `r` (latest reading): `r:ts`, `r:kwh`. Family `a` (alert): `a:status`, `a:type`, `a:ts`.
- Values are strings; timestamps as `yyyy-MM-dd HH:mm:ss`. Loaded from `/dewa/curated/meter_status/`.

## How to run

From the repo folder, with the stack up.

```bash
# 0. Get the data (data prep, full run only; Git Bash on Windows)
bash data/download.sh          # into data/download/ (git-ignored), ~760 MB
bash data/make_sample.sh       # rebuilds data/sample/readings_sample.csv (3 households, already in git)

# 1. Load into HDFS raw (streams the CSVs out of the zip; re-running skips loaded files)
docker compose exec namenode bash /workspace/data/load_hdfs.sh
#    ...or just the sample:
docker compose exec namenode hdfs dfs -mkdir -p /dewa/raw/readings
docker compose exec namenode hdfs dfs -put /workspace/data/sample/readings_sample.csv /dewa/raw/readings/

# 2. Spark (job order in spark/README.md)
docker compose exec spark spark-submit spark/<job>.py

# 3. Hive
docker compose exec hive bash /workspace/hive/run.sh hive/01_create_tables.hql
docker compose exec hive bash /workspace/hive/run.sh hive/02_reports.hql
docker compose exec hive beeline -u jdbc:hive2://localhost:10000        # interactive

# 4. HBase
docker compose exec hbase hbase shell
docker compose exec hbase hbase org.apache.hadoop.hbase.mapreduce.ImportTsv \
  -Dimporttsv.separator=, -Dimporttsv.columns=HBASE_ROW_KEY,r:ts,r:kwh,a:status,a:type,a:ts \
  dewa_meter_status /dewa/curated/meter_status
```

**On the course VM** (fallback if Docker won't run on your laptop; not yet tested end to end): run the same
commands without `docker compose exec <service>` and with relative paths, e.g. `bash data/load_hdfs.sh`,
`spark-submit spark/<job>.py`. For Hive use `hive --hivevar base=/dewa -f hive/<file>.hql`. PySpark 3.0.3 needs
Python 3.8 or older.

## Open tasks

| Task | Part | Output |
|---|---|---|
| Customer record generator (one row per `meter_id`) | Data prep | `data/generate_customers.py` -> `data/download/customers.csv` |
| Tariffs XLSX -> CSV | Data prep | `data/download/tariffs.csv` |
| Cleaning, aggregates, peaks, anomalies, meter_status export | Spark | `spark/*.py` + `spark/README.md` |
| Simulated live stream (Structured Streaming reading a folder) | Spark | `spark/stream_*.py` |
| Create tables, reporting queries | Hive + HBase | `hive/01_create_tables.hql`, `hive/02_reports.hql` |
| HBase table and load | Hive + HBase | `hbase/` |

## Git rules

- Never commit the full dataset, zips or large files; check `git status` before committing.
- One branch per part (`spark/...`, `hive/...`), pull request, one reviewer from your part.
- No passwords, tokens or personal details.

## Data licence

Readings and tariffs: UK Power Networks, London Datastore, CC BY 4.0. Weather: Open-Meteo, CC BY 4.0. Bank holidays:
Nager.Date. The differences between the London data and DEWA's (country, climate, tariffs, scale) are covered as
limitations in the report.
