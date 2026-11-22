"""Check report calculations on deterministic SQLite fixtures, not Hive runtime.

The report SELECTs use SQL supported by both engines, except the ROLLUP in report 10.
HOUR, FLOOR and DATE_FORMAT are supplied explicitly.
These tests cannot establish Hive/Parquet compatibility or partition pruning.
"""
from datetime import date
import math
from pathlib import Path
import sqlite3
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_queries(month='2013-01'):
    text = (ROOT / 'hive/02_reports.hql').read_text()
    sql = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('--'))
    return [q.strip().replace('${hivevar:report_month}', month)
            for q in sql.split(';') if q.strip()]


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
        self.queries = load_queries()
        self.assertEqual(len(self.queries), 13)

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
        for query in self.queries[:6]:
            self.assertEqual(self.db.execute(query.replace('2013-01', '2014-01')).fetchall(), [])


class ExtraTableReports(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.execute("ATTACH DATABASE ':memory:' AS dewa")
        self.db.create_function('FLOOR', 1, math.floor)
        self.db.create_function('DATE_FORMAT', 2, lambda value, fmt: date.fromisoformat(value).strftime('%a'))
        self.db.executescript('''
          CREATE TABLE dewa.readings(meter_id, tariff_type, reading_ts, kwh, reading_month);
          CREATE TABLE dewa.tariffs(tariff_ts, price_band, price_p_per_kwh);
          CREATE TABLE dewa.hourly_usage(meter_id, hour_ts, kwh, readings, reading_month);
          CREATE TABLE dewa.weather(weather_ts, temperature_c, precipitation_mm);
          CREATE TABLE dewa.daily_usage(meter_id, reading_date, kwh_total, peak_kwh, peak_ts, readings, reading_month);
          CREATE TABLE dewa.bank_holidays(holiday_date, name);
          CREATE TABLE dewa.customers(meter_id, customer_id, area, property_type, household_size);
          INSERT INTO dewa.readings VALUES
            ('T1','ToU','2013-03-01 00:00:00',1.0,'2013-03'),
            ('T1','ToU','2013-03-01 00:30:00',2.0,'2013-03'),
            ('T1','ToU','2013-03-01 01:00:00',4.0,'2013-03'),
            ('S1','Std','2013-03-01 00:00:00',5.0,'2013-03'),
            ('T1','ToU','2013-04-01 00:00:00',9.0,'2013-04');
          INSERT INTO dewa.tariffs VALUES
            ('2013-03-01 00:00:00','Low',3.99),
            ('2013-03-01 00:30:00','High',67.2),
            ('2013-03-01 01:00:00','High',67.2),
            ('2013-04-01 00:00:00','Normal',11.76);
          INSERT INTO dewa.hourly_usage VALUES
            ('M1','2013-01-01 00:00:00',1.0,2,'2013-01'),
            ('M1','2013-01-01 01:00:00',3.0,2,'2013-01'),
            ('M1','2013-01-01 02:00:00',0.5,2,'2013-01'),
            ('M1','2012-12-31 23:00:00',100.0,2,'2012-12');
          INSERT INTO dewa.weather VALUES
            ('2013-01-01 00:00:00',3.5,0.0),
            ('2013-01-01 01:00:00',2.1,0.0),
            ('2013-01-01 02:00:00',-0.5,0.0),
            ('2012-12-31 23:00:00',2.0,0.0);
          INSERT INTO dewa.daily_usage VALUES
            ('A','2013-01-01',10.0,1.0,'2013-01-01 18:00:00',48,'2013-01'),
            ('A','2013-01-05',8.0,1.0,'2013-01-05 18:00:00',48,'2013-01'),
            ('A','2013-01-07',6.0,1.0,'2013-01-07 18:00:00',48,'2013-01'),
            ('B','2013-01-07',4.0,1.0,'2013-01-07 18:00:00',48,'2013-01'),
            ('C','2013-01-07',2.0,1.0,'2013-01-07 18:00:00',48,'2013-01'),
            ('C','2013-01-08',3.0,1.0,'2013-01-08 08:00:00',20,'2013-01'),
            ('A','2013-02-04',12.0,1.0,'2013-02-04 18:00:00',48,'2013-02'),
            ('B','2013-02-04',2.0,1.0,'2013-02-04 18:00:00',48,'2013-02');
          INSERT INTO dewa.bank_holidays VALUES ('2013-01-01',"New Year's Day");
          INSERT INTO dewa.customers VALUES
            ('A','CUS-A','Deira','apartment',3),
            ('B','CUS-B','Deira','villa',5),
            ('C','CUS-C','Jumeirah','apartment',2);
        ''')

    def rows(self, number, month='2013-01'):
        return self.db.execute(load_queries(month)[number - 1]).fetchall()

    def test_tariff_cost_per_band_for_tou_only(self):
        self.assertEqual(self.rows(7, '2013-03'), [('High', 2, 6.0, 4.03, 0.85), ('Low', 1, 1.0, 0.04, 0.14)])

    def test_kwh_by_temperature_band(self):
        self.assertEqual(self.rows(8), [(-2, 0.5, 1), (2, 2.0, 2)])

    def test_holidays_weekends_and_weekdays(self):
        self.assertEqual(self.rows(9), [('bank holiday', 10.0, 1), ('weekend', 8.0, 1), ('weekday', 5.2, 5)])

    def test_rank_top_meters_per_month(self):
        self.assertEqual(self.rows(11), [('2013-01', 1, 'A', 24.0), ('2013-01', 2, 'C', 5.0), ('2013-01', 3, 'B', 4.0),
                                         ('2013-02', 1, 'A', 12.0), ('2013-02', 2, 'B', 2.0)])

    def test_lag_change_from_previous_month(self):
        self.assertEqual(self.rows(12, '2013-02'), [('B', '2013-02', 2.0, 4.0, -2.0, -50.0),
                                                    ('A', '2013-02', 12.0, 24.0, -12.0, -50.0)])

    def test_share_of_area(self):
        self.assertEqual(self.rows(13), [('Deira', 'A', 24.0, 28.0, 85.7), ('Deira', 'B', 4.0, 28.0, 14.3),
                                         ('Jumeirah', 'C', 5.0, 5.0, 100.0)])


if __name__ == '__main__':
    unittest.main()
