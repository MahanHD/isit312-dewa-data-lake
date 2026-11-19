"""Check permissions and atomic publication of the converted tariff CSV."""

from contextlib import redirect_stdout
from io import StringIO
import os
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from data.convert_tariffs import convert


class TariffPublication(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.workbook = self.directory / "Tariffs.xlsx"
        self.output = self.directory / "tariffs.csv"

    def write_workbook(self, band):
        namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        with ZipFile(self.workbook, "w") as workbook:
            workbook.writestr("xl/workbook.xml", f'<workbook xmlns="{namespace}"/>')
            workbook.writestr("xl/worksheets/sheet1.xml", f'''
                <worksheet xmlns="{namespace}"><sheetData>
                  <row r="1">
                    <c r="A1" t="inlineStr"><is><t>TariffDateTime</t></is></c>
                    <c r="B1" t="inlineStr"><is><t>Tariff</t></is></c>
                  </row>
                  <row r="2">
                    <c r="A2" t="inlineStr"><is><t>2013-01-01 00:00:00</t></is></c>
                    <c r="B2" t="inlineStr"><is><t>{band}</t></is></c>
                  </row>
                </sheetData></worksheet>
            ''')

    @unittest.skipUnless(os.name == "posix", "requires POSIX file modes")
    def test_published_tariff_csv_has_mode_0644(self):
        self.write_workbook("High")
        with redirect_stdout(StringIO()):
            convert(self.workbook, self.output, allow_partial=True)
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o644)

    def test_failed_publish_preserves_output_and_removes_staging_file(self):
        self.write_workbook("High")
        with redirect_stdout(StringIO()):
            convert(self.workbook, self.output, allow_partial=True)
        original = self.output.read_bytes()
        original_mode = stat.S_IMODE(self.output.stat().st_mode)
        self.write_workbook("Low")
        for operation in ("chmod", "replace"):
            with self.subTest(operation=operation), redirect_stdout(StringIO()):
                with patch(f"data.convert_tariffs.os.{operation}", side_effect=OSError("publish failed")):
                    with self.assertRaisesRegex(OSError, "publish failed"):
                        convert(self.workbook, self.output, allow_partial=True)
                self.assertEqual(self.output.read_bytes(), original)
                self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), original_mode)
                self.assertEqual(set(self.directory.iterdir()), {self.output, self.workbook})
