-- Run after each Spark batch. Discovery does not load or rewrite files.
MSCK REPAIR TABLE dewa.readings;
MSCK REPAIR TABLE dewa.hourly_usage;
MSCK REPAIR TABLE dewa.daily_usage;
MSCK REPAIR TABLE dewa.anomalies;
