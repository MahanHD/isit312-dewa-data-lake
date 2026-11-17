"""Template for a Spark job. Copy it, rename it (e.g. spark/clean_readings.py), then change the middle part.

Run:  docker compose exec spark spark-submit spark/<job>.py
Follows the README's Shared rules: HDFS paths under DEWA_BASE, UTC session time zone, Spark 3.0.3-safe functions,
Parquet output partitioned by reading_month.
"""
import os

from pyspark.sql import SparkSession, functions as F

BASE = os.environ.get("DEWA_BASE", "/dewa")
INPUT = f"{BASE}/raw/readings"
OUTPUT = f"{BASE}/tmp/template_output"   # change to your zone/table, e.g. f"{BASE}/curated/hourly_usage"

spark = SparkSession.builder.appName("template").getOrCreate()
spark.conf.set("spark.sql.session.timeZone", "UTC")   # timestamps stay London wall-clock time, exactly as in the source

raw = spark.read.option("header", True).csv(INPUT)    # every column is a string here

# --- your job starts here: this example maps raw columns to the cleaned schema ---
kwh = F.trim(F.col("KWH/hh (per half hour) "))
df = raw.select(
    F.trim("LCLid").alias("meter_id"),
    F.col("stdorToU").alias("tariff_type"),
    F.to_timestamp(F.substring("DateTime", 1, 19)).alias("reading_ts"),
    F.when(kwh.rlike(r"^-?[0-9]+(\.[0-9]+)?$"), kwh.cast("double")).alias("kwh"),   # "Null" -> null, no try_cast
).withColumn("reading_month", F.date_format("reading_ts", "yyyy-MM"))
# --- your job ends here ---

df.write.mode("overwrite").partitionBy("reading_month").parquet(OUTPUT)
print(f"wrote {spark.read.parquet(OUTPUT).count()} rows to {OUTPUT}")
spark.stop()
