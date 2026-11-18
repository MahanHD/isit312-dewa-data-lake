#!/usr/bin/env bash
# Plays the sample back as live meter data: one file per day of readings into stream/incoming, every few seconds.
# Run inside the namenode container while spark/stream_alerts.py is running:
#   docker compose exec namenode bash /workspace/spark/stream_replay.sh [FROM_DATE] [SECONDS] [DAYS]
# Defaults start on 2013-04-01 (a spike follows within a few days) and send 7 days, 5 seconds apart.
set -euo pipefail
FROM=${1:-2013-04-01}
EVERY=${2:-5}
DAYS=${3:-7}
BASE=${DEWA_BASE:-/dewa}
SAMPLE="$(dirname "$0")/../data/sample/readings_sample.csv"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

# Split the sample into one CSV per day (header kept in each file), for days from FROM onwards
python3 -I - "$SAMPLE" "$WORK" "$FROM" "$DAYS" <<'PY'
import sys, collections
sample, work, start, days = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
by_day = collections.defaultdict(list)
with open(sample, newline="") as f:
    header = next(f)
    for line in f:
        day = line.split(",", 3)[2][:10]
        if day >= start:
            by_day[day].append(line)
for day in sorted(by_day)[:days]:
    with open(f"{work}/readings_{day}.csv", "w", newline="") as out:
        out.write(header)
        out.writelines(by_day[day])
PY

hdfs dfs -mkdir -p "$BASE/stream/incoming" "$BASE/stream/_staging"
for f in "$WORK"/readings_*.csv; do
  # put to staging, then move: the stream must only ever see complete files
  hdfs dfs -put -f "$f" "$BASE/stream/_staging/" && hdfs dfs -mv "$BASE/stream/_staging/$(basename "$f")" "$BASE/stream/incoming/"
  echo "sent $(basename "$f") ($(($(wc -l < "$f") - 1)) readings)"
  sleep "$EVERY"
done
