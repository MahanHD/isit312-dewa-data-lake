#!/usr/bin/env bash
# Hourly kWh per meter as a Hadoop streaming job (local mode, as there is no YARN in the stack).
# Containers: docker compose exec namenode bash /workspace/mapreduce/run_hourly.sh [INPUT]
set -euo pipefail
cd "$(dirname "$0")"
BASE=${DEWA_BASE:-/dewa}
INPUT=${1:-$BASE/raw/readings}
OUT=$BASE/tmp/mr_hourly
export HADOOP_HEAPSIZE_MAX=4g
hdfs dfs -rm -r -f -skipTrash "$OUT" >/dev/null
start=$(date +%s)
# key = meter_id + hour_ts; the combiner output is read with the reduce key setting, so set both.
# 8 map and 8 reduce tasks in parallel, so local mode uses the same machine as fairly as Spark's local[*]
hadoop jar /opt/hadoop/share/hadoop/tools/lib/hadoop-streaming-*.jar \
  -D mapreduce.job.name=mr_hourly -D mapreduce.job.reduces=8 \
  -D mapreduce.local.map.tasks.maximum=8 -D mapreduce.local.reduce.tasks.maximum=8 \
  -D stream.num.map.output.key.fields=2 -D stream.num.reduce.output.key.fields=2 \
  -files hourly_mapper.py,hourly_reducer.py \
  -mapper "python3 hourly_mapper.py" -combiner "python3 hourly_reducer.py" -reducer "python3 hourly_reducer.py" \
  -input "$INPUT" -output "$OUT"
echo "mr_hourly: $(( $(date +%s) - start )) s"
