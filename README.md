# DEWA Smart Meter Data Lake (ISIT312 group project)

ISIT312 Big Data Management, Autumn 2026, University of Wollongong in Dubai. We design a data lake for **DEWA (Dubai
Electricity and Water Authority)** smart meter data and build a working version of it on Hadoop, Spark, Hive and HBase.

## Start here

1. Set up the stack once (see [Setup](#setup)), then find your part below.
2. Work on your own branch, never directly on `main` (see [Git in 5 commands](#git-in-5-commands)).
3. Read the [Shared rules](#shared-rules) before writing code. Paths, column names and table names are fixed there.

| Part | Read | Make | Branch | Done when |
|---|---|---|---|---|
| Architecture + DEWA research | [About the project](#about-the-project), Shared rules 1 | diagrams in `architecture/` (`.drawio` + `.png`), notes in `docs/` | `architecture/<topic>` | the diagrams show every zone, tool and data flow in this README, and the notes cover DEWA's current setup and why we chose (or didn't choose) each tool |
| Data prep | Shared rules 1, 2, 8, How to run 0-1 | `data/generate_customers.py`, `data/convert_tariffs.py` | `data/<topic>` | the scripts write `customers.csv` and `tariffs.csv` into `data/download/`, and `load_hdfs.sh` puts them in `/dewa/raw/` |
| Spark | Shared rules 1-5, 8, [`spark/README.md`](spark/README.md) | `spark/*.py`, copied from `spark/_template.py` | `spark/<topic>` | each job runs on the sample and the full data, and its output matches the paths and schemas in Shared rules 1, 3 and 4 |
| Hive + HBase | Shared rules 1, 3, 4, 6-8 | `hive/01_create_tables.hql`, `hive/02_reports.hql`, `hive/03_refresh_partitions.hql`, `hbase/01_create_table.rb`, `hbase/02_load.sh` | `hive/<topic>`, `hbase/<topic>` | the Hive tables read the Spark output, the report queries return results, and `get 'dewa_meter_status', 'MAC000016'` returns a row |

Data prep commits the **scripts only**. The files they produce stay in `data/download/`, which git ignores.

### Open tasks

| Task | Part | Output |
|---|---|---|
| Customer record generator (one row per `meter_id`) | Data prep | `data/generate_customers.py` (writes `data/download/customers.csv`) |
| Tariffs XLSX -> CSV | Data prep | `data/convert_tariffs.py` (writes `data/download/tariffs.csv`) |
| Cleaning, aggregates, peaks, anomalies, meter_status export | Spark | `spark/*.py` (order and anomaly rules in `spark/README.md`) |
| Simulated live stream (Structured Streaming reading a folder) | Spark | `spark/stream_*.py` |
| Create tables, reporting queries | Hive + HBase | `hive/01_create_tables.hql`, `hive/02_reports.hql` |
| HBase table and load | Hive + HBase | `hbase/01_create_table.rb`, `hbase/02_load.sh` |

### Git in 5 commands

```bash
git switch -c spark/clean-readings              # 1. new branch from an up-to-date main (git switch main && git pull first)
git add spark/clean_readings.py                 # 2. stage your files (check `git status` first)
git commit -m "Add readings cleaning job"       # 3. commit with a short message
git push -u origin spark/clean-readings         # 4. push the branch to GitHub
# 5. open the link git prints (or GitHub > "Compare & pull request"), create the pull request, ask someone from your part to review
```

## About the project

DEWA does not publish per-meter readings, so we use a real public dataset as a stand-in:

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

```
compose.yaml    the whole stack in containers (+ docker/ for its config and the HBase image)
architecture/   diagrams and design notes                  Architecture + DEWA research
docs/           report notes, references, meeting notes    Architecture + DEWA research
data/           download, sample and HDFS load scripts     Data prep
spark/          Spark jobs + template                      Spark
hive/           .hql files + run.sh                        Hive + HBase
hbase/          HBase table and load scripts               Hive + HBase
screenshots/    evidence for the report, one folder per part
```

Each part writes its own report section and slides; the sections are merged into one report at the end.
Screenshots are named `screenshots/<part>/NN-what-it-shows.png`.

## Setup

We use current releases in containers (the course VM is for labs only): Hadoop HDFS 3.4.3, Hive 4.2.1,
HBase 2.6.7, Spark 4.2.1 (PySpark).

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
- Only one machine runs the full dataset (~10 GB extra disk). Everyone else works with `data/sample/`.

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

### 8. Extra sources

Data prep writes the raw files. Spark (`clean_sources.py`) writes each to `cleaned/<name>` as unpartitioned Parquet,
and Hive reads it as `dewa.<name>`.

| Table | Columns | Rule | Joins readings on |
|---|---|---|---|
| `tariffs` | `tariff_ts TIMESTAMP, price_band STRING, price_p_per_kwh DOUBLE` | half hours of 2013 from `Tariffs.xlsx`; `price_band` is `High` (67.20p), `Normal` (11.76p) or `Low` (3.99p) | `reading_ts = tariff_ts`, ToU meters only (Std meters pay a flat 14.228p) |
| `weather` | `weather_ts TIMESTAMP, temperature_c DOUBLE, precipitation_mm DOUBLE` | hourly, London local time | the hour of `reading_ts` |
| `bank_holidays` | `holiday_date DATE, name STRING` | England only: entries with `global` true or `GB-ENG` in `counties` | the date of `reading_ts` |
| `customers` | `meter_id STRING, customer_id STRING, area STRING, property_type STRING, household_size INT` | generated, one row per meter in the readings; `area` is a Dubai community (e.g. `Al Barsha`), `property_type` is `apartment` or `villa`; no names or contact details | `meter_id` |

Raw files from data prep: `raw/tariffs/tariffs.csv` with header `TariffDateTime,Tariff` (`TariffDateTime` converted
from Excel serial numbers to `yyyy-MM-dd HH:mm:ss`), and `raw/customers/customers.csv` with the `customers` columns
above as its header.

## How to run

From the repo folder, with the stack up.

```bash
# 0. Get the data (data prep, full run only; Git Bash on Windows)
bash data/download.sh          # into data/download/ (git-ignored), ~760 MB
bash data/make_sample.sh       # rebuilds data/sample/readings_sample.csv (5 households, already in git)

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

# 4. HBase (loading meter_status: see Details)
docker compose exec hbase hbase shell
```

**On the course VM** (fallback if Docker won't run on your laptop; not yet tested end to end): run the same
commands without `docker compose exec <service>` and with relative paths, e.g. `bash data/load_hdfs.sh`,
`spark-submit spark/<job>.py`. For Hive use `hive --hivevar base=/dewa -f hive/<file>.hql`. PySpark 3.0.3 needs
Python 3.8 or older.

## Git rules

- Never commit the full dataset, zips or large files; check `git status` before committing.
- One branch per part, pull request, one reviewer from your part.
- No passwords, tokens or personal details.

## Details

| Tool | Version | Container |
|---|---|---|
| Hadoop HDFS | 3.4.3 (Java 11) | `namenode`, `datanode`; official `apache/hadoop` image, one datanode, replication 1 |
| Hive | 4.2.1 (Java 21) | `hive`; official `apache/hive` image: HiveServer2 with Tez in local mode and an embedded Derby metastore |
| HBase | 2.6.7 (Java 17) | `hbase`; built from `docker/hbase/`, standalone (master, region server and ZooKeeper in one process), tables stored in HDFS under `/hbase` |
| Spark | 4.2.1 (Java 21, Python 3.10) | `spark`; official `apache/spark` image, local mode, settings in `docker/conf/spark-defaults.conf` |

- **Loading HBase** from Spark's CSV uses HBase's `ImportTsv` tool:

  ```bash
  docker compose exec hbase hbase org.apache.hadoop.hbase.mapreduce.ImportTsv \
    -Dimporttsv.separator=, -Dimporttsv.columns=HBASE_ROW_KEY,r:ts,r:kwh,a:status,a:type,a:ts \
    dewa_meter_status /dewa/curated/meter_status
  ```
- **beeline** in Hive 4.2.1 needs a terminal and hangs on `-f` inside containers, so `hive/run.sh` passes the file
  through `-e`. Don't use `docker compose exec -T` with Hive.
- **Apple Silicon**: Hive, Spark and HBase images run natively; the Hadoop image is amd64-only and runs under
  Docker Desktop's emulation (not yet tested on a Mac).
- **Sample**: `data/sample/readings_sample.csv` holds every row of 5 households (3 `Std`, 2 `ToU`), 85,822 rows,
  in the original format.

## Data licence

Readings and tariffs: UK Power Networks, London Datastore, CC BY 4.0. Weather: Open-Meteo, CC BY 4.0. Bank holidays:
Nager.Date. The differences between the London data and DEWA's (country, climate, tariffs, scale) are covered as
limitations in the report.
