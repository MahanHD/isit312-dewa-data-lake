"""Latest reading and alert per meter, written as headerless CSV in curated/meter_status for hbase/02_load.sh.

Run after anomalies.py:  docker compose exec spark spark-submit spark/meter_status.py
"""
import os

from pyspark.sql import SparkSession, functions as F

BASE = os.environ.get("DEWA_BASE", "/dewa")
OUTPUT = f"{BASE}/curated/meter_status"
ALERT_DAYS = 7          # an anomaly within this many days before the meter's last reading makes it ALERT
TS = "yyyy-MM-dd HH:mm:ss"

spark = SparkSession.builder.appName("meter_status").getOrCreate()
spark.conf.set("spark.sql.session.timeZone", "UTC")

readings = spark.read.parquet(f"{BASE}/cleaned/readings")
anomalies = spark.read.parquet(f"{BASE}/curated/anomalies")

# max of a struct picks the row with the latest timestamp, keeping its other fields
last = readings.groupBy("meter_id").agg(F.max(F.struct("reading_ts", "kwh")).alias("l"))
last_alert = anomalies.groupBy("meter_id").agg(F.max(F.struct("reading_ts", "anomaly_type")).alias("a"))

status = last.join(last_alert, "meter_id", "left")
# The data is historical, so "recent" is measured from each meter's last reading, not from today
recent = F.col("a.reading_ts") >= F.col("l.reading_ts") - F.expr(f"INTERVAL {ALERT_DAYS} DAYS")
recent = F.coalesce(recent, F.lit(False))

out = status.select(
    "meter_id",
    F.date_format("l.reading_ts", TS).alias("last_reading_ts"),
    F.format_string("%.3f", "l.kwh").alias("last_kwh"),
    F.when(recent, "ALERT").otherwise("OK").alias("alert_status"),
    F.when(recent, F.col("a.anomaly_type")).alias("alert_type"),            # null when OK -> empty field
    F.when(recent, F.date_format("a.reading_ts", TS)).alias("alert_ts"),
)

# hbase/02_load.sh needs plain, unquoted fields: nulls and empty strings written as nothing
(out.coalesce(1).write.mode("overwrite")
    .option("emptyValue", "").option("nullValue", "")
    .csv(OUTPUT))

counts = spark.read.csv(OUTPUT).groupBy("_c3").count().collect()
print("meter_status:", ", ".join(f"{r['_c3']}={r['count']}" for r in counts))
spark.stop()
