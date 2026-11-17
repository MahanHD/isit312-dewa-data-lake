#!/usr/bin/env bash
# Builds data/sample/readings_sample.csv: every row of 5 households (3 Std, 2 ToU), read straight from the zip,
# lines kept exactly as in the source. Run after download.sh. Needs python3.
set -euo pipefail
cd "$(dirname "$0")"
python3 -I - <<'PY'
import zipfile, io

# meter -> (file number it is in, expected row count); counts checked against the full dataset
SAMPLE = {
    "MAC000016": (0, 19524),    # Std
    "MAC000356": (10, 16552),   # Std
    "MAC000432": (12, 16407),   # Std
    "MAC000898": (139, 16981),  # ToU
    "MAC000932": (140, 16358),  # ToU
}

z = zipfile.ZipFile("download/lcl_partitioned.zip")
counts = dict.fromkeys(SAMPLE, 0)
with open("sample/readings_sample.csv", "w", newline="") as out:
    for n in sorted({f for f, _ in SAMPLE.values()}):
        with z.open(f"Small LCL Data/LCL-June2015v2_{n}.csv") as f:
            lines = io.TextIOWrapper(f, encoding="utf-8", newline="")
            header = next(lines)
            if out.tell() == 0:
                out.write(header)
            for line in lines:
                meter = line.split(",", 1)[0]
                if meter in counts:
                    out.write(line)
                    counts[meter] += 1

for meter, (_, expected) in SAMPLE.items():
    assert counts[meter] == expected, f"{meter}: got {counts[meter]} rows, expected {expected}"
print(f"wrote {sum(counts.values())} rows for {len(SAMPLE)} complete households -> data/sample/readings_sample.csv")
PY
ls -lh sample/readings_sample.csv
