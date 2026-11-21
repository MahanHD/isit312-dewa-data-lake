"""Summarize cleaned half-hour readings for the Hive usage reports.

Run: docker compose exec spark spark-submit spark/aggregates.py
"""
import os

from pyspark.sql import SparkSession, functions as F

BASE = os.environ.get("DEWA_BASE", "/dewa")
INPUT = f"{BASE}/cleaned/readings"
HOURLY_OUTPUT = f"{BASE}/curated/hourly_usage"
DAILY_OUTPUT = f"{BASE}/curated/daily_usage"

spark = SparkSession.builder.appName("usage-aggregates").getOrCreate()
spark.conf.set("spark.sql.session.timeZone", "UTC")

readings = spark.read.parquet(INPUT).select("meter_id", "reading_ts", "kwh")

hourly = (
    readings.withColumn("hour_ts", F.date_trunc("hour", "reading_ts"))
    .groupBy("meter_id", "hour_ts")
    .agg(F.sum("kwh").alias("kwh"), F.count("*").cast("int").alias("readings"))
    .withColumn("reading_month", F.date_format("hour_ts", "yyyy-MM"))
)

# Struct ordering picks the largest kWh and then the earliest timestamp on ties.
peak = F.min(F.struct((-F.col("kwh")).alias("negative_kwh"), F.col("reading_ts")))
daily = (
    readings.withColumn("reading_date", F.to_date("reading_ts"))
    .groupBy("meter_id", "reading_date")
    .agg(
        F.sum("kwh").alias("kwh_total"),
        peak.alias("peak"),
        F.count("*").cast("int").alias("readings"),
    )
    .select(
        "meter_id",
        "reading_date",
        "kwh_total",
        (-F.col("peak.negative_kwh")).alias("peak_kwh"),
        F.col("peak.reading_ts").alias("peak_ts"),
        "readings",
        F.date_format("reading_date", "yyyy-MM").alias("reading_month"),
    )
)

hourly.write.mode("overwrite").partitionBy("reading_month").parquet(HOURLY_OUTPUT)
daily.write.mode("overwrite").partitionBy("reading_month").parquet(DAILY_OUTPUT)

print(f"Wrote hourly usage to {HOURLY_OUTPUT} and daily usage to {DAILY_OUTPUT}")
spark.stop()
