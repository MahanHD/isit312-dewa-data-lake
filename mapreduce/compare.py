"""Checks that mapreduce/run_hourly.sh and mapreduce/spark_hourly.py produced the same rows."""
import os

from pyspark.sql import SparkSession, functions as F

BASE = os.environ.get("DEWA_BASE", "/dewa")
spark = SparkSession.builder.appName("compare_hourly").getOrCreate()


def load(path):
    # 3 decimals: the two tools add in a different order, which changes the last float digits
    return spark.read.csv(path, sep="\t").toDF("meter_id", "hour_ts", "kwh", "readings").selectExpr(
        "meter_id", "hour_ts", "round(cast(kwh as double), 3) kwh", "cast(readings as int) readings")


mr, sp = load(f"{BASE}/tmp/mr_hourly"), load(f"{BASE}/tmp/spark_hourly")
for name, df in (("mapreduce", mr), ("spark", sp)):
    r = df.agg(F.count("*"), F.round(F.sum("kwh"), 3), F.sum("readings")).first()
    print(f"{name}: rows={r[0]} kwh={r[1]} readings={r[2]}")
diff = mr.exceptAll(sp).count() + sp.exceptAll(mr).count()
print(f"rows only in one side: {diff}")
spark.stop()
