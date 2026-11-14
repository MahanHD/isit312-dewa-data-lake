#!/usr/bin/env bash
# Builds data/sample/readings_sample.csv: header + first N rows of the first readings file, read straight from the zip.
# Rows are grouped by household, so this is a few complete households. Run after download.sh. Needs python3.
set -euo pipefail
cd "$(dirname "$0")"
python3 -I - "${1:-60000}" <<'PY'
import sys, zipfile, io, itertools
n = int(sys.argv[1])
z = zipfile.ZipFile("download/lcl_partitioned.zip")
first = sorted((i for i in z.infolist() if i.filename.endswith(".csv")), key=lambda i: (len(i.filename), i.filename))[0]
with z.open(first) as f, open("sample/readings_sample.csv", "w", newline="") as out:
    lines = list(itertools.islice(io.TextIOWrapper(f, encoding="utf-8", newline=""), n + 1))
    out.writelines(lines)
ids = {l.split(",")[0] for l in lines[1:]}
print(f"{first.filename}: wrote {len(lines) - 1} rows, {len(ids)} households -> data/sample/readings_sample.csv")
PY
