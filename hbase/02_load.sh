#!/usr/bin/env bash
# Run inside HBase container, or directly on the course VM.
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
base="${DEWA_BASE:-/dewa}"
[[ "$base" =~ ^/[a-zA-Z0-9_/-]+$ && "$base" != / ]] || { echo 'Invalid DEWA_BASE' >&2; exit 2; }
# FsShell uses the HBase Hadoop classpath; no separate hdfs executable needed.
hbase org.apache.hadoop.fs.FsShell -test -e "$base/curated/meter_status"
# Preflight all Spark part files before changing HBase. ImportTsv itself accepts
# missing trailing fields, so enforce this project's complete six-field contract.
hbase org.apache.hadoop.fs.FsShell -cat "$base/curated/meter_status/part-*" | awk -F, '
  NF != 6 || $1 == "" || $1 == "meter_id" || $2 == "" || $3 == "" ||
  ($4 != "OK" && $4 != "ALERT") || /["\r]/ ||
  ($4 == "OK" && ($5 != "" || $6 != "")) ||
  ($4 == "ALERT" && ($5 == "" || $6 == "")) {
    printf "Invalid meter_status record at input line %d\n", NR > "/dev/stderr"
    invalid = 1
  }
  END {
    if (NR == 0) { print "Empty meter_status export" > "/dev/stderr"; invalid = 1 }
    exit invalid
  }'
hbase shell -n "$repo_dir/hbase/01_create_table.rb"
# Standalone Docker stack has no YARN. Local MapReduce still reads HDFS.
# Reject malformed rows instead of silently dropping them. Empty fields are
# written so a new OK snapshot can clear an older alert's type/timestamp.
exec hbase org.apache.hadoop.hbase.mapreduce.ImportTsv \
  -Dmapreduce.framework.name=local \
  -Dimporttsv.separator=, \
  -Dimporttsv.columns=HBASE_ROW_KEY,r:ts,r:kwh,a:status,a:type,a:ts \
  -Dimporttsv.skip.bad.lines=false \
  -Dimporttsv.skip.empty.columns=false \
  dewa_meter_status "$base/curated/meter_status/part-*"
