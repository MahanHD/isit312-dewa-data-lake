"""Exercise the Shared rules 8 customer CSV contract against both input modes."""

import csv
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from data.generate_customers import generate


ROOT = Path(__file__).resolve().parents[1]
READINGS_HEADER = b"LCLid,stdorToU,DateTime,KWH/hh (per half hour) \r\n"
CUSTOMER_HEADER = ["meter_id", "customer_id", "area", "property_type", "household_size"]


class CustomerGeneration(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.sample = self.directory / "readings.csv"
        self.archive = self.directory / "readings.zip"
        self.output = self.directory / "customers.csv"

    def assert_customer_file(self, path, expected_meters):
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            self.assertEqual(reader.fieldnames, CUSTOMER_HEADER)
            rows = list(reader)

        self.assertCountEqual([row["meter_id"] for row in rows], expected_meters)
        customer_ids = {row["customer_id"] for row in rows}
        self.assertEqual(len(customer_ids), len(rows))
        self.assertTrue(all(customer_ids))
        for row in rows:
            self.assertNotIn(None, row)
            self.assertIn(row["area"], {"Al Barsha", "Deira", "Dubai Marina", "Jumeirah"})
            self.assertIn(row["property_type"], {"apartment", "villa"})
            self.assertIn(row["household_size"], {"1", "2", "3", "4", "5", "6"})
        return {row["meter_id"]: row for row in rows}

    def test_sample_cli_matches_checked_in_readings_and_is_repeatable(self):
        source = ROOT / "data/sample/readings_sample.csv"
        original = source.read_bytes()
        with source.open(encoding="utf-8-sig", newline="") as stream:
            expected_meters = {row["LCLid"].strip() for row in csv.DictReader(stream)}

        repeat = self.directory / "repeat.csv"
        for output in (self.output, repeat):
            subprocess.run(
                [sys.executable, "-B", "data/generate_customers.py", "--source", "sample", "--output", str(output)],
                cwd=ROOT, check=True, capture_output=True,
            )
        self.assert_customer_file(self.output, expected_meters)
        self.assertEqual(repeat.read_bytes(), self.output.read_bytes())
        self.assertEqual(source.read_bytes(), original)

    def test_full_zip_deduplicates_and_matches_sample_attributes(self):
        std = b"MAC000002,Std,2013-01-01 00:00:00,0.3\r\n"
        tou = b"MAC000003,ToU,2013-01-01 00:00:00,0.2\r\n"
        extra = b"MAC000001,Std,2013-01-01 00:00:00,0.5\r\n"
        self.sample.write_bytes(READINGS_HEADER + tou + std + tou)
        with ZipFile(self.archive, "w") as archive:
            for index in range(168):
                rows = extra + std + tou if index == 0 else std
                archive.writestr(f"readings/part-{index:03}.csv", READINGS_HEADER + rows)
            archive.writestr("__MACOSX/ignored.csv", b"not readings")
        original_zip = self.archive.read_bytes()

        full_output = self.directory / "full.csv"
        with redirect_stdout(StringIO()):
            generate("sample", self.archive, self.sample, self.output)
            counts = generate("full", self.archive, self.directory / "missing-sample.csv", full_output)
        sample_customers = self.assert_customer_file(self.output, {"MAC000002", "MAC000003"})
        full_customers = self.assert_customer_file(full_output, {"MAC000001", "MAC000002", "MAC000003"})
        for meter, customer in sample_customers.items():
            self.assertEqual(full_customers[meter], customer)
        self.assertEqual(counts, {"Std": 2, "ToU": 1})
        self.assertEqual(self.archive.read_bytes(), original_zip)

    def test_invalid_readings_preserve_existing_output(self):
        self.output.write_bytes(b"existing customers")
        cases = (
            (b"", "empty CSV"),
            (b"meter,tariff,other\n", "unexpected first two columns"),
            (READINGS_HEADER, "No meters found"),
            (READINGS_HEADER + b"MAC000001,Std\n", "malformed CSV row"),
            (READINGS_HEADER + b",Std,other\n", "empty meter ID"),
            (READINGS_HEADER + b"MAC000001,bad,other\n", "unknown tariff"),
            (READINGS_HEADER + b"MAC000001,Std,other\nMAC000001,ToU,other\n", "conflicting tariffs"),
        )
        for contents, error in cases:
            with self.subTest(error=error):
                self.sample.write_bytes(contents)
                with redirect_stdout(StringIO()), self.assertRaisesRegex(ValueError, error):
                    generate("sample", self.archive, self.sample, self.output)
                self.assertEqual(self.sample.read_bytes(), contents)
                self.assertEqual(self.output.read_bytes(), b"existing customers")

    def test_full_archive_requires_all_partitions(self):
        with ZipFile(self.archive, "w") as archive:
            archive.writestr("readings.csv", READINGS_HEADER + b"MAC000001,Std,other\n")
        with self.assertRaisesRegex(ValueError, "Expected 168 CSV files .* found 1"):
            generate("full", self.archive, self.sample, self.output)
        self.assertFalse(self.output.exists())

    def test_failed_publish_preserves_output_and_removes_staging_file(self):
        self.sample.write_bytes(READINGS_HEADER + b"MAC000001,Std,other\n")
        self.output.write_bytes(b"existing customers")
        with patch("data.generate_customers.os.replace", side_effect=OSError("publish failed")):
            with redirect_stdout(StringIO()), self.assertRaisesRegex(OSError, "publish failed"):
                generate("sample", self.archive, self.sample, self.output)
        self.assertEqual(self.output.read_bytes(), b"existing customers")
        self.assertEqual(set(self.directory.iterdir()), {self.output, self.sample})
