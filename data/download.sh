#!/usr/bin/env bash
# Downloads every source file into data/download/ (git-ignored). Run on your own machine (Linux, macOS, or Git Bash on
# Windows). Safe to re-run: skips files already there. The readings zip stays zipped; load_hdfs.sh streams from it.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p download && cd download

LDS=https://data.london.gov.uk/download/vqm0d
get() { [ -s "$2" ] && echo "have $2" || { echo "get  $2"; curl -fL --retry 3 -o "$2.part" "$1" && mv "$2.part" "$2"; }; }

# Readings: same data as LCL-FullData.zip, split into 168 CSVs of 1M rows (~760 MB zipped, ~10 GB unzipped)
get "$LDS/04feba67-f1a3-4563-98d0-f3071e3d56d1/Partitioned%20LCL%20Data.zip" lcl_partitioned.zip
get "$LDS/14855047-44c2-4856-8a48-e5649200e6ce/Tariffs.xlsx" Tariffs.xlsx

# London hourly weather for the dataset period (Open-Meteo archive, free, no key)
get "https://archive-api.open-meteo.com/v1/archive?latitude=51.5072&longitude=-0.1276&start_date=2011-11-01&end_date=2014-02-28&hourly=temperature_2m,precipitation&timezone=Europe%2FLondon" weather_london.json

# UK bank holidays per year (gov.uk's own JSON only goes back a few years)
for y in 2011 2012 2013 2014; do get "https://date.nager.at/api/v3/PublicHolidays/$y/GB" "bank_holidays_$y.json"; done

ls -lh
