#!/usr/bin/env python3
"""Generate synthetic customer records keyed by REAL London smart meter IDs.

Usage from the repo root:
    python data/generate_customers.py --source full
    python data/generate_customers.py --source sample   # development only

No external dependencies. Never modifies the original readings.
"""

import argparse
import csv
import os
from collections import Counter
from pathlib import Path
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
HEADER = ["customer_id", "meter_id", "tariff_type", "customer_name", "customer_segment", "is_synthetic"]


def add_reading(meters: dict[str, str], raw_meter: bytes, raw_tariff: bytes, source: str, row_number: int) -> None:
    meter = raw_meter.decode("utf-8-sig").strip()
    tariff = raw_tariff.decode("utf-8-sig").strip()
    if not meter:
        raise ValueError(f"{source}, row {row_number}: empty meter ID")
    if tariff not in ("Std", "ToU"):
        raise ValueError(f"{source}, row {row_number}: unknown tariff {tariff!r} for {meter}")
    previous = meters.setdefault(meter, tariff)
    if previous != tariff:
        raise ValueError(f"{source}, row {row_number}: {meter} has conflicting tariffs {previous} / {tariff}")


def consume_csv_lines(lines, meters: dict[str, str], source: str) -> int:
    header = next(lines, None)
    if header is None:
        raise ValueError(f"{source}: empty CSV")
    fields = header.decode("utf-8-sig").strip().split(",")
    if fields[:2] != ["LCLid", "stdorToU"]:
        raise ValueError(f"{source}: unexpected first two columns: {fields[:2]}")
    count = 0
    for count, line in enumerate(lines, start=1):
        # Only the first two source columns are needed; avoid loading ~167M rows.
        parts = line.split(b",", 2)
        if len(parts) < 3:
            raise ValueError(f"{source}, row {count + 1}: malformed CSV row")
        add_reading(meters, parts[0], parts[1], source, count + 1)
    return count


def generate(source: str, zip_path: Path, sample_path: Path, output: Path) -> Counter:
    meters: dict[str, str] = {}
    if source == "full":
        if not zip_path.is_file():
            raise FileNotFoundError(f"Full readings archive not found: {zip_path}. Run bash data/download.sh first.")
        with ZipFile(zip_path) as archive:
            csv_members = sorted(n for n in archive.namelist() if n.lower().endswith(".csv") and not n.startswith("__MACOSX/"))
            if len(csv_members) != 168:
                raise ValueError(f"Expected 168 CSV files in {zip_path.name}; found {len(csv_members)}")
            for i, name in enumerate(csv_members, 1):
                with archive.open(name) as lines:
                    count = consume_csv_lines(lines, meters, name)
                if not count:
                    raise ValueError(f"{name}: no readings")
                if i % 20 == 0 or i == len(csv_members):
                    print(f"Read {i}/{len(csv_members)} files; {len(meters)} distinct meters", flush=True)
    else:
        if not sample_path.is_file():
            raise FileNotFoundError(f"Sample CSV not found: {sample_path}")
        with sample_path.open("rb") as lines:
            consume_csv_lines(lines, meters, str(sample_path))
        print("SAMPLE MODE ONLY: this is not the full customer dataset.")

    if not meters:
        raise ValueError("No meters found in input data")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="customers-", suffix=".csv.tmp", dir=str(output.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(HEADER)
            for i, (meter, tariff) in enumerate(sorted(meters.items()), 1):
                cid = f"CUS{i:06d}"
                writer.writerow([cid, meter, tariff, f"Synthetic Customer {i:06d}", "Residential", "true"])
        os.replace(tmp, output)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    counts = Counter(meters.values())
    print(f"Created {output}: {len(meters)} customers; Std={counts['Std']}, ToU={counts['ToU']}")
    return counts


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", choices=["full", "sample"], default="full",
                   help="full uses 168 CSVs inside the original ZIP; sample uses the checked-in subset")
    p.add_argument("--zip", type=Path, default=ROOT / "download" / "lcl_partitioned.zip")
    p.add_argument("--sample", type=Path, default=ROOT / "sample" / "readings_sample.csv")
    p.add_argument("--output", type=Path, default=ROOT / "download" / "customers.csv")
    a = p.parse_args()
    generate(a.source, a.zip, a.sample, a.output)


if __name__ == "__main__":
    main()
