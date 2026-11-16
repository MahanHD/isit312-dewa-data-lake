"""CLI contract checks with fake clients; these do not replace live integration."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ScriptContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.log = self.directory / 'calls.jsonl'
        client = f'''#!{sys.executable}
import json, os, sys
with open(os.environ['CALL_LOG'], 'a') as out:
    out.write(json.dumps(sys.argv[1:]) + '\\n')
if os.environ.get('FAIL_COMMAND') in sys.argv[1:]:
    sys.exit(17)
if len(sys.argv) > 2 and sys.argv[2] == '-cat':
    print(os.environ.get('STATUS_ROWS', ''), end='')
'''
        for name in ('hbase', 'beeline'):
            path = self.directory / name
            path.write_text(client)
            path.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.directory) + ':' + os.environ['PATH'],
                        CALL_LOG=str(self.log), DEWA_BASE='/dewa')

    def run_script(self, script, *args):
        return subprocess.run(['bash', str(ROOT / script), *args], env=self.env,
                              cwd=self.directory, text=True, capture_output=True)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_hive_month_and_base_reach_client(self):
        result = self.run_script('hive/run.sh', 'hive/02_reports.hql', '2013-02')
        self.assertEqual(result.returncode, 0, result.stderr)
        args = self.calls()[0]
        self.assertIn('report_month=2013-02', args)
        self.assertIn('base=/dewa', args)
        self.assertIn('--force=false', args)

    def test_hive_rejects_invalid_month_before_client(self):
        result = self.run_script('hive/run.sh', 'hive/02_reports.hql', '2013-13')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_base_rejects_hql_injection(self):
        self.env['DEWA_BASE'] = "/dewa'; DROP DATABASE dewa; --"
        for script in ('hive/run.sh', 'hbase/02_load.sh'):
            args = ('hive/01_create_tables.hql',) if script.startswith('hive/') else ()
            self.assertNotEqual(self.run_script(script, *args).returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_complete_ok_and_alert_rows_import_with_empty_cells(self):
        self.env['STATUS_ROWS'] = ('MAC000002,2013-01-01 00:00:00,0.5,OK,,\n'
                                   'MAC000003,2013-01-01 00:00:00,8.0,ALERT,HIGH,2013-01-01 00:00:00\n')
        result = self.run_script('hbase/02_load.sh')
        self.assertEqual(result.returncode, 0, result.stderr)
        args = self.calls()[-1]
        self.assertIn('org.apache.hadoop.hbase.mapreduce.ImportTsv', args)
        self.assertIn('-Dmapreduce.framework.name=local', args)
        self.assertIn('-Dimporttsv.skip.empty.columns=false', args)
        self.assertIn('-Dimporttsv.skip.bad.lines=false', args)
        self.assertEqual(args[-1], '/dewa/curated/meter_status/part-*')
        self.assertEqual(args[-1], self.calls()[1][-1])

    def test_missing_hdfs_input_stops_before_table_creation(self):
        self.env['FAIL_COMMAND'] = '-test'
        result = self.run_script('hbase/02_load.sh')
        self.assertEqual(result.returncode, 17)
        self.assertEqual(len(self.calls()), 1)

    def test_failed_preflight_read_stops_before_table_creation(self):
        self.env['FAIL_COMMAND'] = '-cat'
        self.assertNotEqual(self.run_script('hbase/02_load.sh').returncode, 0)
        self.assertEqual(len(self.calls()), 2)

    def test_table_creation_failure_stops_before_import(self):
        self.env['STATUS_ROWS'] = 'MAC000002,2013-01-01 00:00:00,0.5,OK,,\n'
        self.env['FAIL_COMMAND'] = 'shell'
        self.assertEqual(self.run_script('hbase/02_load.sh').returncode, 17)
        self.assertFalse(any('org.apache.hadoop.hbase.mapreduce.ImportTsv' in call for call in self.calls()))

    def test_import_failure_reaches_caller(self):
        self.env['STATUS_ROWS'] = 'MAC000002,2013-01-01 00:00:00,0.5,OK,,\n'
        self.env['FAIL_COMMAND'] = 'org.apache.hadoop.hbase.mapreduce.ImportTsv'
        self.assertEqual(self.run_script('hbase/02_load.sh').returncode, 17)

    def test_beeline_failure_reaches_caller(self):
        self.env['FAIL_COMMAND'] = '--force=false'
        self.assertEqual(self.run_script('hive/run.sh', 'hive/01_create_tables.hql').returncode, 17)

    def test_invalid_rows_never_create_or_import(self):
        for row in ('', 'meter_id,last_reading_ts,last_kwh,alert_status,alert_type,alert_ts\n',
                    'MAC000002,2013-01-01 00:00:00,0.5,OK\n',
                    'MAC000002,2013-01-01 00:00:00,0.5,OK,"",""\n',
                    'MAC000002,2013-01-01 00:00:00,0.5,OK,HIGH,old\n',
                    'MAC000002,2013-01-01 00:00:00,0.5,ALERT,,\n'):
            with self.subTest(row=row):
                if self.log.exists():
                    self.log.unlink()
                self.env['STATUS_ROWS'] = row
                self.assertNotEqual(self.run_script('hbase/02_load.sh').returncode, 0)
                self.assertTrue(all(call[0] == 'org.apache.hadoop.fs.FsShell' for call in self.calls()))


if __name__ == '__main__':
    unittest.main()
