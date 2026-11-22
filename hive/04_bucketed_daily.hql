-- Run after dewa.daily_usage has populated, registered monthly partitions.
-- Use an unused demo location on first run. Before a rerun, verify that the
-- existing demo table and its partitions still point to that location.
CREATE EXTERNAL TABLE IF NOT EXISTS dewa.daily_usage_bucketed (
  meter_id STRING, reading_date DATE, kwh_total DOUBLE,
  peak_kwh DOUBLE, peak_ts TIMESTAMP, readings INT
)
PARTITIONED BY (reading_month STRING)
CLUSTERED BY (meter_id) INTO 8 BUCKETS
STORED AS PARQUET LOCATION '${hivevar:base}/hive/daily_usage_bucketed';

-- Hive 2.1 needs nonstrict mode when every partition column is dynamic.
SET hive.exec.dynamic.partition.mode=nonstrict;
-- 28 months x 8 buckets is more than the default 100 dynamic partitions per node.
SET hive.exec.max.dynamic.partitions=1000;
SET hive.exec.max.dynamic.partitions.pernode=1000;
-- Only months present in the source are replaced in the demo table.
INSERT OVERWRITE TABLE dewa.daily_usage_bucketed PARTITION (reading_month)
SELECT meter_id, reading_date, kwh_total, peak_kwh, peak_ts, readings, reading_month
FROM dewa.daily_usage;

DESCRIBE FORMATTED dewa.daily_usage_bucketed;
SHOW PARTITIONS dewa.daily_usage_bucketed;

-- A positive balance means extra copies in the target, a negative one means missing copies.
WITH copies AS (
  SELECT s.*, -1 AS balance FROM dewa.daily_usage s
  UNION ALL
  SELECT b.*, 1 AS balance FROM dewa.daily_usage_bucketed b
)
SELECT meter_id, reading_date, kwh_total, peak_kwh, peak_ts, readings, reading_month,
       SUM(balance) AS extra_copies
FROM copies
GROUP BY meter_id, reading_date, kwh_total, peak_kwh, peak_ts, readings, reading_month
HAVING SUM(balance) <> 0;

-- Count rows in each populated physical file for the selected month.
SELECT INPUT__FILE__NAME AS bucket_file, COUNT(*) AS daily_rows
FROM dewa.daily_usage_bucketed
WHERE reading_month = '${hivevar:report_month}'
GROUP BY INPUT__FILE__NAME;

-- This meter occurs in the bundled January 2013 sample.
SELECT meter_id, reading_date, kwh_total, INPUT__FILE__NAME AS bucket_file
FROM dewa.daily_usage_bucketed
WHERE reading_month = '${hivevar:report_month}' AND meter_id = 'MAC000932'
ORDER BY reading_date;
