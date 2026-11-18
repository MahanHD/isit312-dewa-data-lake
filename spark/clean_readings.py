"""Cleans raw readings into cleaned/readings (Shared rules 2 and 3).

Reads  raw/readings (CSV with header), writes cleaned/readings as Parquet partitioned by reading_month.
Drops rows whose kwh is null (e.g. "Null") or negative, and duplicate (meter_id, reading_ts) rows.

Run:  docker compose exec spark spark-submit spark/clean_readings.py
"""
import os

from pyspark.sql import SparkSession, functions as F

BASE = os.environ.get("DEWA_BASE", "/dewa")
INPUT = os.environ.get("DEWA_INPUT", f"{BASE}/raw/readings")
OUTPUT = os.environ.get("DEWA_OUTPUT", f"{BASE}/cleaned/readings")

spark = SparkSession.builder.appName("clean_readings").getOrCreate()
spark.conf.set("spark.sql.session.timeZone", "UTC")   # timestamps stay London wall-clock time, exactly as in the source
# overwrite only the months this run writes would leave stale months behind; this job owns the whole folder
spark.conf.set("spark.sql.sources.partitionOverwriteMode", "static")

raw = spark.read.option("header", True).csv(INPUT)    # every column is a string here

v = F.trim(F.col("KWH/hh (per half hour) "))
df = (
    raw.select(
        F.trim("LCLid").alias("meter_id"),
        F.trim("stdorToU").alias("tariff_type"),
        F.to_timestamp(F.substring("DateTime", 1, 19)).alias("reading_ts"),
        F.when(v.rlike(r"^-?[0-9]+(\.[0-9]+)?$"), v.cast("double")).alias("kwh"),   # "Null" -> null, no try_cast
    )
    .filter(F.col("kwh").isNotNull() & (F.col("kwh") >= 0) & F.col("reading_ts").isNotNull())
    .dropDuplicates(["meter_id", "reading_ts"])
    .withColumn("reading_month", F.date_format("reading_ts", "yyyy-MM"))
)

df.write.mode("overwrite").partitionBy("reading_month").parquet(OUTPUT)
out = spark.read.parquet(OUTPUT)
print(f"wrote {out.count()} rows to {OUTPUT} ({raw.count()} raw rows)")
spark.stop()
