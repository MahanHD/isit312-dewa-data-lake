#!/usr/bin/env python3
"""Convert the original London Tariffs.xlsx into an HDFS-ready CSV.

Runs with Python's standard library (no Excel/pandas dependency).
Source: UK Power Networks / London Datastore; rates are pence per kWh.
Output timestamps retain source local wall-clock time (not time-zone converted).
"""

import argparse
import csv
from datetime import datetime, timedelta
import os
from pathlib import Path
import re
import tempfile
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
MAIN_NS = NS["x"]
DATE_1899 = datetime(1899, 12, 30)
DATE_1904 = datetime(1904, 1, 1)
RATES = {"high": "67.20", "normal": "11.76", "low": "3.99"}
STD_RATE = "14.228"
HEADER = ["tariff_datetime", "tariff_band", "tou_price_pence_per_kwh", "std_price_pence_per_kwh"]


def xlsx_rows(path: Path):
    """Read simple worksheet cells directly from XLSX XML, including shared strings."""
    with ZipFile(path) as z:
        members = z.namelist()
        if "xl/workbook.xml" not in members:
            raise ValueError("Not a valid XLSX workbook")
        workbook = ET.fromstring(z.read("xl/workbook.xml"))
        props = workbook.find("x:workbookPr", NS)
        date1904 = props is not None and props.get("date1904") in ("1", "true")
        shared = []
        if "xl/sharedStrings.xml" in members:
            strings = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in strings.findall("x:si", NS):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{MAIN_NS}}}t")))
        sheets = sorted((n for n in members if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)),
                        key=lambda x: int(re.search(r"sheet(\d+)", x).group(1)))
        if not sheets:
            raise ValueError("No worksheet XML found in XLSX")
        for sheet in sheets:
            xml = ET.fromstring(z.read(sheet))
            for row in xml.findall(".//x:sheetData/x:row", NS):
                values = {}
                for cell in row.findall("x:c", NS):
                    ref = cell.get("r", "")
                    match = re.match(r"[A-Z]+", ref)
                    if not match:
                        continue
                    column = 0
                    for char in match.group():
                        column = column * 26 + ord(char) - ord("A") + 1
                    v = cell.find("x:v", NS)
                    if cell.get("t") == "s" and v is not None:
                        value = shared[int(v.text)]
                    elif cell.get("t") == "inlineStr":
                        is_node = cell.find("x:is", NS)
                        value = "".join(t.text or "" for t in is_node.iter(f"{{{MAIN_NS}}}t")) if is_node is not None else ""
                    else:
                        value = v.text if v is not None else ""
                    values[column - 1] = value
                if values:
                    yield sheet, int(row.get("r", "0")), values, date1904


def parse_time(raw: str, date1904: bool) -> datetime:
    val = str(raw).strip()
    if not val:
        raise ValueError("blank tariff timestamp")
    # Excel date/time serials (including fractional half-hours).
    if re.fullmatch(r"\d+(\.\d+)?", val):
        base = DATE_1904 if date1904 else DATE_1899
        return base + timedelta(seconds=round(float(val) * 86400))
    try:
        return datetime.fromisoformat(val.replace("Z", ""))
    except ValueError:
        pass
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized timestamp: {raw!r}")


def convert(input_path: Path, output: Path, allow_partial: bool = False) -> list:
    if not input_path.is_file():
        raise FileNotFoundError(f"Missing {input_path}; run bash data/download.sh first.")
    found_header = False
    rows = []
    date_col = band_col = None
    active_sheet = None
    for sheet, rownum, values, date1904 in xlsx_rows(input_path):
        if active_sheet is not None and sheet != active_sheet:
            break
        if not found_header:
            normalized = {str(v).strip().casefold().replace(" ", ""): key for key, v in values.items()}
            # Official workbook: TariffDateTime and Tariff.  Be strict if these are absent.
            if "tariffdatetime" in normalized and "tariff" in normalized:
                date_col, band_col = normalized["tariffdatetime"], normalized["tariff"]
                active_sheet, found_header = sheet, True
            continue
        if not values.get(date_col) and not values.get(band_col):
            continue
        if not values.get(date_col) or not values.get(band_col):
            raise ValueError(f"{sheet} row {rownum}: missing timestamp or tariff")
        dt = parse_time(values[date_col], date1904)
        band = str(values[band_col]).strip().casefold()
        if band not in RATES:
            raise ValueError(f"{sheet} row {rownum}: unsupported tariff band {values[band_col]!r}")
        rows.append((dt, band))

    if not found_header:
        raise ValueError("Cannot locate 'TariffDateTime' and 'Tariff' columns in Tariffs.xlsx")
    rows.sort()
    stamps = [dt for dt, _ in rows]
    if len(stamps) != len(set(stamps)):
        raise ValueError("Duplicate tariff timestamps; cannot safely join to meter readings")
    if not allow_partial:
        if len(rows) != 365 * 48:
            raise ValueError(f"Expected 17,520 half-hour tariff rows for 2013, found {len(rows)}")
        expected = datetime(2013, 1, 1)
        for i, stamp in enumerate(stamps):
            if stamp != expected + timedelta(minutes=30 * i):
                raise ValueError(f"Timestamp gap/offset at row {i + 1}: got {stamp}, expected {expected + timedelta(minutes=30 * i)}")
    if not rows:
        raise ValueError("No tariff rows found")

    output.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="tariffs-", suffix=".csv.tmp", dir=str(output.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(HEADER)
            for dt, band in rows:
                writer.writerow([dt.strftime("%Y-%m-%d %H:%M:%S"), band.title(), RATES[band], STD_RATE])
        os.replace(tmp, output)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    print(f"Created {output}: {len(rows):,} tariff intervals; {rows[0][0]} to {rows[-1][0]}")
    return rows


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=ROOT / "download" / "Tariffs.xlsx")
    p.add_argument("--output", type=Path, default=ROOT / "download" / "tariffs.csv")
    p.add_argument("--allow-partial", action="store_true", help="development fixture only; skip full-year validation")
    a = p.parse_args()
    convert(a.input, a.output, allow_partial=a.allow_partial)


if __name__ == "__main__":
    main()
