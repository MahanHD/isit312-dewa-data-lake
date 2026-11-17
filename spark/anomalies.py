"""Flags unusual readings in cleaned/readings and writes curated/anomalies (rules in spark/README.md).

Run:  docker compose exec spark spark-submit spark/anomalies.py
"""
import os

from pyspark.sql import SparkSession, Window, functions as F

BASE = os.environ.get("DEWA_BASE", "/dewa")
INPUT = f"{BASE}/cleaned/readings"
OUTPUT = f"{BASE}/curated/anomalies"

SPIKE_FACTOR = 1.5      # spike: this many times the meter's own 99.9th percentile...
SPIKE_MIN_KWH = 2.0     # ...and at least this much in one half hour (keeps small meters from flagging noise)
ZERO_RUN = 48           # zero_run: at least this many readings in a row of exactly 0 kWh (48 = one day)

spark = SparkSession.builder.appName("anomalies").getOrCreate()
spark.conf.set("spark.sql.session.timeZone", "UTC")

readings = spark.read.parquet(INPUT)

# spike: a half hour well above even this meter's highest normal readings
# (percentile_approx through expr because F.percentile_approx doesn't exist in Spark 3.0)
stats = readings.groupBy("meter_id").agg(F.expr("percentile_approx(kwh, 0.999)").alias("p999"))
spikes = (
    readings.join(stats, "meter_id")   # no F.broadcast hint: Spark broadcasts the small table itself, and the hint hung Spark 4.2.1 on small inputs
    .where((F.col("kwh") > SPIKE_FACTOR * F.col("p999")) & (F.col("kwh") >= SPIKE_MIN_KWH))
    .select(
        "meter_id", "reading_ts", "kwh",
        F.lit("spike").alias("anomaly_type"),
        F.format_string("%.3f kWh vs the meter's 99.9th percentile of %.3f", "kwh", "p999").alias("details"),
    )
)

# zero_run: a meter reporting 0 kWh for a day or more (possible meter fault or empty home).
# Each non-zero reading starts a new group, so a run of zeros shares the group of the reading before it.
by_time = Window.partitionBy("meter_id").orderBy("reading_ts")
zeros = (
    readings.withColumn("grp", F.sum(F.when(F.col("kwh") != 0, 1).otherwise(0)).over(by_time))
    .where(F.col("kwh") == 0)
    .groupBy("meter_id", "grp")
    .agg(F.count("*").alias("n"), F.min("reading_ts").alias("start"), F.max("reading_ts").alias("end"))
    .where(F.col("n") >= ZERO_RUN)
    .select(
        "meter_id",
        F.col("start").alias("reading_ts"),
        F.lit(0.0).alias("kwh"),
        F.lit("zero_run").alias("anomaly_type"),
        F.concat(F.col("n").cast("string"), F.lit(" readings of 0 kWh until "),
                 F.date_format("end", "yyyy-MM-dd HH:mm:ss")).alias("details"),
    )
)

anomalies = spikes.unionByName(zeros).withColumn("reading_month", F.date_format("reading_ts", "yyyy-MM"))
anomalies.write.mode("overwrite").partitionBy("reading_month").parquet(OUTPUT)

result = spark.read.parquet(OUTPUT)
for row in result.groupBy("anomaly_type").agg(F.count("*").alias("events"), F.countDistinct("meter_id").alias("meters")).collect():
    print(f"{row.anomaly_type}: {row.events} events on {row.meters} meters")
spark.stop()
