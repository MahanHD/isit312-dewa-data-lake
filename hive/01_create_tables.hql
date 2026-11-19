-- Hive owns metadata; Spark owns files. Compatible with Hive 2.1.1+.
CREATE DATABASE IF NOT EXISTS dewa;
CREATE EXTERNAL TABLE IF NOT EXISTS dewa.raw_readings (
  meter_id STRING, tariff_type STRING, reading_ts STRING, kwh STRING
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar'=',', 'quoteChar'='"')
STORED AS TEXTFILE
LOCATION '${hivevar:base}/raw/readings'
TBLPROPERTIES ('skip.header.line.count'='1');

CREATE EXTERNAL TABLE IF NOT EXISTS dewa.readings (
  meter_id STRING, tariff_type STRING, reading_ts TIMESTAMP, kwh DOUBLE
)
PARTITIONED BY (reading_month STRING)
STORED AS PARQUET LOCATION '${hivevar:base}/cleaned/readings';

CREATE EXTERNAL TABLE IF NOT EXISTS dewa.hourly_usage (
  meter_id STRING, hour_ts TIMESTAMP, kwh DOUBLE, readings INT
)
PARTITIONED BY (reading_month STRING)
STORED AS PARQUET LOCATION '${hivevar:base}/curated/hourly_usage';

CREATE EXTERNAL TABLE IF NOT EXISTS dewa.daily_usage (
  meter_id STRING, reading_date DATE, kwh_total DOUBLE,
  peak_kwh DOUBLE, peak_ts TIMESTAMP, readings INT
)
PARTITIONED BY (reading_month STRING)
STORED AS PARQUET LOCATION '${hivevar:base}/curated/daily_usage';

CREATE EXTERNAL TABLE IF NOT EXISTS dewa.anomalies (
  meter_id STRING, reading_ts TIMESTAMP, kwh DOUBLE,
  anomaly_type STRING, details STRING
)
PARTITIONED BY (reading_month STRING)
STORED AS PARQUET LOCATION '${hivevar:base}/curated/anomalies';

-- Extra tables from Shared rules 8. clean_sources.py writes these.
-- Not partitioned so they don't need MSCK REPAIR.
CREATE EXTERNAL TABLE IF NOT EXISTS dewa.tariffs (
  tariff_ts TIMESTAMP, price_band STRING, price_p_per_kwh DOUBLE
)
STORED AS PARQUET LOCATION '${hivevar:base}/cleaned/tariffs';

CREATE EXTERNAL TABLE IF NOT EXISTS dewa.weather (
  weather_ts TIMESTAMP, temperature_c DOUBLE, precipitation_mm DOUBLE
)
STORED AS PARQUET LOCATION '${hivevar:base}/cleaned/weather';

CREATE EXTERNAL TABLE IF NOT EXISTS dewa.bank_holidays (
  holiday_date DATE, name STRING
)
STORED AS PARQUET LOCATION '${hivevar:base}/cleaned/bank_holidays';

CREATE EXTERNAL TABLE IF NOT EXISTS dewa.customers (
  meter_id STRING, customer_id STRING, area STRING,
  property_type STRING, household_size INT
)
STORED AS PARQUET LOCATION '${hivevar:base}/cleaned/customers';
