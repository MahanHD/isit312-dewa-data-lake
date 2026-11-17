"""Cleans the extra sources into cleaned/tariffs, cleaned/weather, cleaned/bank_holidays and cleaned/customers.

Columns follow Shared rules 8. Each output is unpartitioned Parquet, overwritten on every run. A source whose raw
folder is still empty is skipped with a message, so the others can be built before data prep has finished.

Run:  docker compose exec spark spark-submit spark/clean_sources.py
"""
import os

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.utils import AnalysisException

BASE = os.environ.get("DEWA_BASE", "/dewa")
TS = "yyyy-MM-dd HH:mm:ss"

spark = SparkSession.builder.appName("clean_sources").getOrCreate()
spark.conf.set("spark.sql.session.timeZone", "UTC")   # timestamps stay London wall-clock time, as in the source


def read(fmt, path, **options):
    """Returns the DataFrame, or None when the raw folder has no files yet."""
    try:
        return spark.read.options(**options).format(fmt).load(path)
    except AnalysisException as e:
        if "Path does not exist" in str(e) or "Unable to infer schema" in str(e):
            print(f"skip {path}: no files yet")
            return None
        raise


def save(df, name):
    df.write.mode("overwrite").parquet(f"{BASE}/cleaned/{name}")
    print(f"{name}: {spark.read.parquet(f'{BASE}/cleaned/{name}').count()} rows")


# tariffs: data prep's tariffs.csv (half hours of 2013, see Shared rules 8)
tariffs = read("csv", f"{BASE}/raw/tariffs/tariffs.csv", header=True)
if tariffs is not None:
    save(tariffs.select(
        F.to_timestamp("tariff_datetime", TS).alias("tariff_ts"),
        F.trim("tariff_band").alias("price_band"),
        F.col("tou_price_pence_per_kwh").cast("double").alias("price_p_per_kwh"),
    ), "tariffs")

# weather: one Open-Meteo JSON object holding parallel hourly arrays; zip them into one row per hour
weather = read("json", f"{BASE}/raw/weather", multiLine=True)
if weather is not None:
    hours = weather.select(F.explode(F.arrays_zip("hourly.time", "hourly.temperature_2m", "hourly.precipitation")).alias("h"))
    save(hours.select(
        F.to_timestamp(F.col("h.time"), "yyyy-MM-dd'T'HH:mm").alias("weather_ts"),
        F.col("h.temperature_2m").cast("double").alias("temperature_c"),
        F.col("h.precipitation").cast("double").alias("precipitation_mm"),
    ), "weather")

# bank_holidays: one JSON array per year; keep holidays that apply in England (London)
holidays = read("json", f"{BASE}/raw/bank_holidays", multiLine=True)
if holidays is not None:
    england = F.col("global") | F.coalesce(F.array_contains("counties", "GB-ENG"), F.lit(False))
    save(holidays.where(england).select(
        F.to_date("date").alias("holiday_date"),
        F.col("name"),
    ).dropDuplicates(["holiday_date"]), "bank_holidays")

# customers: data prep's generated records, already in the cleaned columns
customers = read("csv", f"{BASE}/raw/customers/customers.csv", header=True)
if customers is not None:
    save(customers.select(
        F.trim("meter_id").alias("meter_id"),
        F.trim("customer_id").alias("customer_id"),
        F.trim("area").alias("area"),
        F.trim("property_type").alias("property_type"),
        F.col("household_size").cast("int").alias("household_size"),
    ), "customers")

spark.stop()
