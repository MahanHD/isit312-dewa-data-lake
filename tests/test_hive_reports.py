"""Check report calculations on deterministic SQLite fixtures, not Hive runtime.

The report SELECTs use SQL supported by both engines; HOUR is supplied explicitly.
These tests cannot establish Hive/Parquet compatibility or partition pruning.
"""
from pathlib import Path
import sqlite3
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReportCalculations(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.execute("ATTACH DATABASE ':memory:' AS dewa")
        self.db.create_function('HOUR', 1, lambda value: int(value[11:13]))
        self.db.executescript('''
          CREATE TABLE dewa.readings(meter_id, tariff_type, reading_ts, kwh, reading_month);
          CREATE TABLE dewa.daily_usage(meter_id, reading_date, kwh_total, peak_kwh, peak_ts, readings, reading_month);
          CREATE TABLE dewa.hourly_usage(meter_id, hour_ts, kwh, readings, reading_month);
          CREATE TABLE dewa.anomalies(meter_id, reading_ts, kwh, anomaly_type, details, reading_month);
          INSERT INTO dewa.readings VALUES
            ('M1','Std','2013-01-01 00:00:00',0.5,'2013-01'),
            ('M1','Std','2013-01-01 00:30:00',1.5,'2013-01'),
            ('M1','Std','2013-01-01 01:00:00',2.0,'2013-01'),
            ('M2','Std','2013-01-01 00:00:00',3.0,'2013-01'),
            ('OUTSIDE','Std','2013-02-01 00:00:00',999.0,'2013-02');
          INSERT INTO dewa.daily_usage VALUES
            ('M1','2013-01-01',4.0,2.0,'2013-01-01 01:00:00',3,'2013-01'),
            ('M2','2013-01-01',3.0,3.0,'2013-01-01 00:00:00',1,'2013-01'),
            ('OUTSIDE','2013-02-01',999.0,999.0,'2013-02-01 00:00:00',1,'2013-02');
          INSERT INTO dewa.hourly_usage VALUES
            ('M1','2013-01-01 00:00:00',2.0,2,'2013-01'),
            ('M1','2013-01-01 01:00:00',2.0,1,'2013-01'),
            ('M2','2013-01-01 00:00:00',3.0,1,'2013-01'),
            ('OUTSIDE','2013-02-01 00:00:00',999.0,1,'2013-02');
          INSERT INTO dewa.anomalies VALUES
            ('M1','2013-01-01 00:30:00',1.5,'HIGH','test','2013-01'),
            ('M1','2013-01-01 01:00:00',2.0,'HIGH','test','2013-01'),
            ('M2','2013-01-01 00:00:00',3.0,'HIGH','test','2013-01'),
            ('OUTSIDE','2013-02-01 00:00:00',999.0,'OUTSIDE','test','2013-02');
        ''')
        text = (ROOT / 'hive/02_reports.hql').read_text()
        sql = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('--'))
        self.queries = [q.strip().replace('${hivevar:report_month}', '2013-01')
                        for q in sql.split(';') if q.strip()]
        self.assertEqual(len(self.queries), 6)

    def rows(self, number):
        return self.db.execute(self.queries[number - 1]).fetchall()

    def test_monthly_totals_and_coverage(self):
        self.assertEqual(self.rows(1), [('M1', '2013-01', 4.0, 1, 3), ('M2', '2013-01', 3.0, 1, 1)])

    def test_peak_order_and_month_filter(self):
        self.assertEqual([row[0] for row in self.rows(2)], ['M2', 'M1'])
        self.assertEqual([row[2] for row in self.rows(2)], [3.0, 2.0])

    def test_hourly_sum_mean_and_coverage(self):
        self.assertEqual(self.rows(3), [(0, 5.0, 2.5, 2, 3), (1, 2.0, 2.0, 1, 1)])

    def test_anomaly_events_and_distinct_meters(self):
        self.assertEqual(self.rows(4), [('HIGH', 3, 2)])

    def test_low_coverage_days(self):
        self.assertEqual([(row[0], row[2]) for row in self.rows(5)], [('M1', 3), ('M2', 1)])

    def test_cleaned_daily_reconciliation(self):
        cleaned = self.rows(6)
        self.assertEqual(cleaned, [('2013-01', 4, 2, 7.0)])
        self.assertAlmostEqual(cleaned[0][3], sum(row[2] for row in self.rows(1)))

    def test_empty_month_returns_no_rows(self):
        for query in self.queries:
            self.assertEqual(self.db.execute(query.replace('2013-01', '2014-01')).fetchall(), [])


if __name__ == '__main__':
    unittest.main()
