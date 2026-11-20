"""The same hourly job as mapreduce/, in Spark, for the timing comparison. Reads raw/readings, writes tmp/spark_hourly."""
import os
import sys
import time

from pyspark.sql import SparkSession, functions as F

BASE = os.environ.get("DEWA_BASE", "/dewa")
INPUT = sys.argv[1:] or [f"{BASE}/raw/readings"]   # paths or folders

spark = SparkSession.builder.appName("spark_hourly").getOrCreate()
spark.conf.set("spark.sql.session.timeZone", "UTC")
start = time.time()
raw = spark.read.csv(INPUT, header=True)
v = F.trim(F.col("KWH/hh (per half hour) "))
hourly = (raw.select(F.trim("LCLid").alias("meter_id"),
                     F.concat(F.substring("DateTime", 1, 13), F.lit(":00:00")).alias("hour_ts"),
                     F.when(v.rlike(r"^-?[0-9]+(\.[0-9]+)?$"), v.cast("double")).alias("kwh"))
          .where("kwh >= 0")
          .groupBy("meter_id", "hour_ts").agg(F.sum("kwh").alias("kwh"), F.count("*").alias("readings")))
hourly.write.mode("overwrite").option("sep", "\t").csv(f"{BASE}/tmp/spark_hourly")
print(f"spark_hourly: {time.time() - start:.0f} s")
spark.stop()
