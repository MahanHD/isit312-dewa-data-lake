-- Set report_month through run.sh (default 2013-01). Explicit partition
-- predicates bound scans; use a month actually present in SHOW PARTITIONS.
-- 1. Monthly consumption and observed coverage, per meter.
SELECT meter_id, reading_month, SUM(kwh_total) AS monthly_kwh,
       COUNT(*) AS observed_days, SUM(readings) AS half_hour_readings
FROM dewa.daily_usage
WHERE reading_month = '${hivevar:report_month}'
GROUP BY meter_id, reading_month
ORDER BY monthly_kwh DESC, meter_id;

-- 2. Largest observed half-hour peaks (not hourly or instantaneous demand).
SELECT meter_id, reading_date, peak_kwh, peak_ts
FROM dewa.daily_usage
WHERE reading_month = '${hivevar:report_month}'
ORDER BY peak_kwh DESC, meter_id, reading_date LIMIT 20;

-- 3. Fleet consumption by hour of day. Counts expose unequal coverage.
SELECT HOUR(hour_ts) AS hour_of_day, SUM(kwh) AS total_kwh,
       AVG(kwh) AS mean_meter_hour_kwh, COUNT(*) AS observed_meter_hours,
       SUM(readings) AS half_hour_readings
FROM dewa.hourly_usage
WHERE reading_month = '${hivevar:report_month}'
GROUP BY HOUR(hour_ts) ORDER BY hour_of_day;

-- 4. Anomaly counts by rule; these are flags, not proven faults.
SELECT anomaly_type, COUNT(*) AS events, COUNT(DISTINCT meter_id) AS meters
FROM dewa.anomalies
WHERE reading_month = '${hivevar:report_month}'
GROUP BY anomaly_type ORDER BY events DESC, anomaly_type;

-- 5. Days with fewer than 48 observed readings. Boundary days and London DST
-- need interpretation; entirely absent days require a separate calendar join.
SELECT meter_id, reading_date, readings, kwh_total
FROM dewa.daily_usage
WHERE reading_month = '${hivevar:report_month}' AND readings < 48
ORDER BY reading_date, meter_id LIMIT 100;

-- 6. Cleaned monthly totals for reconciliation against daily aggregates.
SELECT reading_month, COUNT(*) AS cleaned_rows, COUNT(DISTINCT meter_id) AS meters,
       SUM(kwh) AS cleaned_kwh
FROM dewa.readings
WHERE reading_month = '${hivevar:report_month}' GROUP BY reading_month;
