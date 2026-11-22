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

-- 7. Cost per price band for ToU meters, against the flat Std price.
SELECT t.price_band, COUNT(*) AS half_hours, ROUND(SUM(r.kwh), 2) AS kwh,
       ROUND(SUM(r.kwh * t.price_p_per_kwh) / 100, 2) AS cost_gbp,
       ROUND(SUM(r.kwh * 14.228) / 100, 2) AS std_cost_gbp
FROM dewa.readings r
JOIN dewa.tariffs t ON r.reading_ts = t.tariff_ts
WHERE r.reading_month = '${hivevar:report_month}' AND r.tariff_type = 'ToU'
GROUP BY t.price_band
ORDER BY cost_gbp DESC;

-- 8. Average kWh per meter-hour by temperature (2 degree bands), same year as report_month.
SELECT FLOOR(w.temperature_c / 2) * 2 AS temp_from_c,
       ROUND(AVG(h.kwh), 3) AS avg_kwh, COUNT(*) AS meter_hours
FROM dewa.hourly_usage h
JOIN dewa.weather w ON h.hour_ts = w.weather_ts
WHERE SUBSTR(h.reading_month, 1, 4) = SUBSTR('${hivevar:report_month}', 1, 4)
GROUP BY FLOOR(w.temperature_c / 2) * 2
ORDER BY temp_from_c;

-- 9. Average daily kWh per meter on bank holidays, weekends and weekdays (full days only).
SELECT day_type, ROUND(AVG(kwh_total), 3) AS avg_daily_kwh, COUNT(*) AS meter_days
FROM (
  SELECT d.kwh_total,
         CASE WHEN b.holiday_date IS NOT NULL THEN 'bank holiday'
              WHEN DATE_FORMAT(d.reading_date, 'EEE') IN ('Sat', 'Sun') THEN 'weekend'
              ELSE 'weekday' END AS day_type
  FROM dewa.daily_usage d
  LEFT JOIN dewa.bank_holidays b ON d.reading_date = b.holiday_date
  WHERE d.readings >= 46
) by_day
GROUP BY day_type
ORDER BY avg_daily_kwh DESC;

-- 10. kWh by month, area and property type with subtotals (ROLLUP), same year as report_month.
SELECT d.reading_month, c.area, c.property_type,
       ROUND(SUM(d.kwh_total), 2) AS kwh, COUNT(*) AS meter_days
FROM dewa.daily_usage d
JOIN dewa.customers c ON d.meter_id = c.meter_id
WHERE SUBSTR(d.reading_month, 1, 4) = SUBSTR('${hivevar:report_month}', 1, 4)
GROUP BY d.reading_month, c.area, c.property_type WITH ROLLUP
ORDER BY reading_month, area, property_type;

-- 11. Top 10 meters per month (RANK), same year as report_month.
SELECT reading_month, meter_rank, meter_id, ROUND(monthly_kwh, 2) AS monthly_kwh
FROM (
  SELECT reading_month, meter_id, monthly_kwh,
         RANK() OVER (PARTITION BY reading_month ORDER BY monthly_kwh DESC) AS meter_rank
  FROM (
    SELECT reading_month, meter_id, SUM(kwh_total) AS monthly_kwh
    FROM dewa.daily_usage
    WHERE SUBSTR(reading_month, 1, 4) = SUBSTR('${hivevar:report_month}', 1, 4)
    GROUP BY reading_month, meter_id
  ) monthly
) ranked
WHERE meter_rank <= 10
ORDER BY reading_month, meter_rank, meter_id;

-- 12. Change from the previous month per meter (LAG), biggest increases in report_month.
SELECT meter_id, reading_month, ROUND(monthly_kwh, 2) AS monthly_kwh,
       ROUND(previous_kwh, 2) AS previous_kwh,
       ROUND(monthly_kwh - previous_kwh, 2) AS change_kwh,
       ROUND(100 * (monthly_kwh - previous_kwh) / previous_kwh, 1) AS change_pct
FROM (
  SELECT meter_id, reading_month, monthly_kwh,
         LAG(monthly_kwh) OVER (PARTITION BY meter_id ORDER BY reading_month) AS previous_kwh
  FROM (
    SELECT meter_id, reading_month, SUM(kwh_total) AS monthly_kwh
    FROM dewa.daily_usage
    GROUP BY meter_id, reading_month
  ) monthly
) changes
WHERE reading_month = '${hivevar:report_month}'
ORDER BY change_kwh DESC, meter_id LIMIT 20;

-- 13. Share of each meter in its area total for report_month (window SUM).
SELECT area, meter_id, ROUND(monthly_kwh, 2) AS monthly_kwh,
       ROUND(SUM(monthly_kwh) OVER (PARTITION BY area), 2) AS area_kwh,
       ROUND(100 * monthly_kwh / SUM(monthly_kwh) OVER (PARTITION BY area), 1) AS share_pct
FROM (
  SELECT c.area, d.meter_id, SUM(d.kwh_total) AS monthly_kwh
  FROM dewa.daily_usage d
  JOIN dewa.customers c ON d.meter_id = c.meter_id
  WHERE d.reading_month = '${hivevar:report_month}'
  GROUP BY c.area, d.meter_id
) monthly
ORDER BY area, share_pct DESC, meter_id;
