#!/usr/bin/env bash
# Creates the lake folders and copies downloaded files into the raw zone. Raw files are never overwritten.
# Containers: docker compose exec namenode bash /workspace/data/load_hdfs.sh    VM: bash data/load_hdfs.sh
set -euo pipefail
cd "$(dirname "$0")/download"
BASE=${DEWA_BASE:-/dewa}

for d in raw/readings raw/tariffs raw/weather raw/bank_holidays raw/customers cleaned curated; do
  hdfs dfs -mkdir -p "$BASE/$d"
done

exists() { hdfs dfs -test -e "$1"; }
put() { exists "$2/$(basename "$1")" && echo "skip $1 (already in HDFS)" || hdfs dfs -put "$1" "$2/"; }

# Readings: stream each CSV out of the zip straight into HDFS, so the 10 GB never sits unzipped on local disk
python3 -I -c 'import zipfile; print("\n".join(i.filename for i in zipfile.ZipFile("lcl_partitioned.zip").infolist() if i.filename.endswith(".csv")))' |
while read -r member; do
  dest="$BASE/raw/readings/$(basename "$member" | tr ' ' '_')"
  if exists "$dest"; then echo "skip $member"; continue; fi
  echo "put  $member"
  python3 -I -c 'import sys, zipfile, shutil; shutil.copyfileobj(zipfile.ZipFile("lcl_partitioned.zip").open(sys.argv[1]), sys.stdout.buffer)' "$member" |
    # exit explicitly: a failure inside this piped loop would otherwise be skipped and the script would still succeed
    hdfs dfs -put - "$dest._COPYING_" && hdfs dfs -mv "$dest._COPYING_" "$dest" || exit 1
done

put Tariffs.xlsx "$BASE/raw/tariffs"
if [ -f tariffs.csv ]; then put tariffs.csv "$BASE/raw/tariffs"; fi
put weather_london.json "$BASE/raw/weather"
for f in bank_holidays_*.json; do put "$f" "$BASE/raw/bank_holidays"; done
if [ -f customers.csv ]; then put customers.csv "$BASE/raw/customers"; fi

hdfs dfs -du -h "$BASE/raw"
