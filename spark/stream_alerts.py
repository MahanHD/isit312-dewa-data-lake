"""Live stream demo: watches stream/incoming for new reading files and flags spikes within seconds.

Uses the same spike rule as anomalies.py, with each meter's threshold taken from its history in cleaned/readings
(a stream joined to batch data). Alerts are printed and appended to stream/alerts as Parquet.

Run (terminal 1):  docker compose exec spark spark-submit spark/stream_alerts.py
Feed it (terminal 2):  docker compose exec namenode bash /workspace/spark/stream_replay.sh
Start the replay once it prints "thresholds ready" (about a minute on the full data). Stops on Ctrl+C, or after
STREAM_SECONDS seconds if set; shutting down takes about 30 seconds. Needs cleaned/readings (run clean_readings.py first).
"""
import os

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import StringType, StructField, StructType

BASE = os.environ.get("DEWA_BASE", "/dewa")
INCOMING = f"{BASE}/stream/incoming"
ALERTS = f"{BASE}/stream/alerts"
CHECKPOINT = f"{BASE}/stream/_checkpoint"
RUN_SECONDS = int(os.environ.get("STREAM_SECONDS", "0"))   # 0 = run until stopped

SPIKE_FACTOR = 1.5      # same rule as anomalies.py
SPIKE_MIN_KWH = 2.0

spark = SparkSession.builder.appName("stream_alerts").getOrCreate()
spark.conf.set("spark.sql.session.timeZone", "UTC")
spark.sparkContext.setLogLevel("WARN")

# The file source fails on a missing folder, so create it before the replay script has written anything
jvm = spark.sparkContext._jvm
fs = jvm.org.apache.hadoop.fs.FileSystem.get(spark.sparkContext._jsc.hadoopConfiguration())
fs.mkdirs(jvm.org.apache.hadoop.fs.Path(INCOMING))

# Per-meter threshold from history, computed once at start (percentile_approx through expr: Spark 3.0-safe)
thresholds = (
    spark.read.parquet(f"{BASE}/cleaned/readings")
    .groupBy("meter_id").agg(F.expr("percentile_approx(kwh, 0.999)").alias("p999"))
    .cache()
)
print(f"thresholds ready for {thresholds.count()} meters; watching {INCOMING}", flush=True)

# Incoming files have the raw columns (Shared rules 2); a streaming source needs the schema up front
raw_schema = StructType([StructField(c, StringType()) for c in ["LCLid", "stdorToU", "DateTime", "KWH/hh (per half hour) "]])
kwh = F.trim(F.col("KWH/hh (per half hour) "))
readings = (
    spark.readStream.schema(raw_schema).option("header", True).option("maxFilesPerTrigger", 1).csv(INCOMING)
    .select(
        F.trim("LCLid").alias("meter_id"),
        F.to_timestamp(F.substring("DateTime", 1, 19)).alias("reading_ts"),
        F.when(kwh.rlike(r"^-?[0-9]+(\.[0-9]+)?$"), kwh.cast("double")).alias("kwh"),
    )
    .where("kwh is not null and kwh >= 0")
)


def handle(batch, batch_id):
    """Runs once per new file: flag spikes, print them, append them to stream/alerts."""
    if batch.rdd.isEmpty():
        return
    batch = batch.cache()
    alerts = (
        batch.join(thresholds, "meter_id")
        .where((F.col("kwh") > SPIKE_FACTOR * F.col("p999")) & (F.col("kwh") >= SPIKE_MIN_KWH))
        .select("meter_id", "reading_ts", "kwh", F.col("p999").alias("threshold"),
                F.current_timestamp().alias("detected_at"))
    )
    found = alerts.collect()
    if found:
        spark.createDataFrame(found, alerts.schema).coalesce(1).write.mode("append").parquet(ALERTS)   # one small file per batch, not one per core
    day = batch.agg(F.min("reading_ts")).first()[0]
    print(f"batch {batch_id}: {batch.count()} readings for {day:%Y-%m-%d}, {len(found)} alert(s)", flush=True)
    for a in found:
        print(f"  ALERT {a.meter_id} {a.reading_ts:%Y-%m-%d %H:%M} {a.kwh:.3f} kWh (threshold {a.threshold:.3f})", flush=True)
    batch.unpersist()


query = (
    readings.writeStream.foreachBatch(handle)
    .option("checkpointLocation", CHECKPOINT)
    .trigger(processingTime="5 seconds")
    .start()
)
if RUN_SECONDS:
    query.awaitTermination(RUN_SECONDS)
    query.stop()
else:
    query.awaitTermination()
spark.stop()
