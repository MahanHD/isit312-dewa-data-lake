import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "mapreduce"


def run(script, text):
    return subprocess.run([sys.executable, str(ROOT / script)], input=text, capture_output=True, text=True,
                          check=True).stdout


class HourlyJob(unittest.TestCase):
    def test_cleaning_and_sums_survive_the_combiner(self):
        raw = ("LCLid,stdorToU,DateTime,KWH/hh (per half hour) \r\n"
               "MAC000002,Std,2012-10-12 00:00:00.0000000, 0.1 \r\n"
               "MAC000002,Std,2012-10-12 00:30:00.0000000, 0.263 \r\n"
               "MAC000002,Std,2012-10-12 01:00:00.0000000,Null\r\n"
               "MAC000003,ToU,2012-10-12 00:00:00.0000000,-1\r\n")
        combined = run("hourly_reducer.py", "".join(sorted(run("hourly_mapper.py", raw).splitlines(True))))
        meter, hour, kwh, readings = run("hourly_reducer.py", combined).strip().split("\t")
        self.assertEqual((meter, hour, readings), ("MAC000002", "2012-10-12 00:00:00", "2"))
        self.assertAlmostEqual(float(kwh), 0.363)


if __name__ == "__main__":
    unittest.main()
