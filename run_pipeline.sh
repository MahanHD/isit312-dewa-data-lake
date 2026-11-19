#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

usage() { echo "Usage: ./run_pipeline.sh [--sample | --skip-load | --load]"; }
if (( $# > 1 )); then usage >&2; exit 2; fi
mode=${1---sample}
case "$mode" in
  --sample) export COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-dewa-sample} ;;
  --skip-load|--load) ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac

engines=(podman docker)
case "${COMPOSE_ENGINE:-}" in
  docker|podman) engines=("$COMPOSE_ENGINE") ;;
  '') ;;
  *) echo "COMPOSE_ENGINE must be podman or docker." >&2; exit 2 ;;
esac
jobs=(clean_readings clean_sources aggregates anomalies meter_status)
for job in "${jobs[@]}"; do
  [[ -r spark/$job.py ]] || { echo "Missing spark/$job.py. Batch stopped before loading or running jobs." >&2; exit 3; }
done

for engine in "${engines[@]}"; do
  if "$engine" compose version >/dev/null 2>&1; then break; fi
  engine=
done
[[ -n $engine ]] || { echo "A working Podman Compose or Docker Compose command is required." >&2; exit 1; }

run() {
  echo "+ $engine compose exec $*" >&2
  "$engine" compose exec "$@"
}
readings=/dewa/raw/readings
if [[ $mode != --skip-load ]]; then
  dfs() { run -T namenode hdfs dfs "$@"; }
  dfs -mkdir -p "$readings"
  files=$(dfs -ls -C "$readings")
  sample=$readings/readings_sample.csv
  if [[ $mode == --sample ]]; then
    case "$files" in
      '') dfs -put /workspace/data/sample/readings_sample.csv "$sample" ;;
      "$sample")
        dfs -test -f "$sample" || {
          status=$?
          echo "Cannot verify $sample is a regular file. Check the sample project." >&2
          exit "$status"
        }
        echo "Reusing $sample" ;;
      *) echo "Sample needs its own readings directory. Check the Compose project." >&2; exit 1 ;;
    esac
  else
    # Pad the listing with newlines so the path must match one complete entry.
    if [[ $'\n'"$files"$'\n' == *$'\n'"$sample"$'\n'* ]]; then
      echo "Sample readings present. Select the full-data project before loading." >&2; exit 1
    fi
    run -T namenode bash /workspace/data/load_hdfs.sh
  fi
fi

for job in "${jobs[@]}"; do run -T spark spark-submit "/workspace/spark/$job.py"; done
# Beeline needs a terminal. Keep the default Compose TTY for all three Hive calls.
for hql in 01_create_tables 03_refresh_partitions 02_reports; do
  run hive bash /workspace/hive/run.sh "hive/$hql.hql"
done
run -T hbase bash /workspace/hbase/02_load.sh
