"""Exercise the Bash entry point with recording Compose clients and no services."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
JOBS = ['clean_readings', 'clean_sources', 'aggregates', 'anomalies', 'meter_status']
BATCH = [f'-T spark spark-submit /workspace/spark/{job}.py' for job in JOBS] + [
    'hive bash /workspace/hive/run.sh hive/01_create_tables.hql',
    'hive bash /workspace/hive/run.sh hive/03_refresh_partitions.hql',
    'hive bash /workspace/hive/run.sh hive/02_reports.hql',
    '-T hbase bash /workspace/hbase/02_load.sh',
]
LOADER = '-T namenode bash /workspace/data/load_hdfs.sh'
SAMPLE = '/dewa/raw/readings/readings_sample.csv'


class Pipeline(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        shutil.copy(ROOT / 'run_pipeline.sh', self.root)
        (self.root / 'spark').mkdir()
        for job in JOBS:
            (self.root / 'spark' / f'{job}.py').touch()
        for name in ('docker', 'podman'):
            client = self.root / name
            client.write_text('''#!/bin/sh
[ "$1" = compose ] || exit 90
if [ "$2" = version ]; then [ "${0##*/}" != "$UNAVAILABLE" ]; exit $?; fi
[ "$2" = exec ] || exit 91
shift 2
echo "${0##*/} ${COMPOSE_PROJECT_NAME:-default} $*" >> "$LOG"
[ "$*" != "$FAIL" ] || exit 17
if [ "$5" = -ls ]; then printf '%s\\n' "$FILES"; fi
if [ "$5 $6" = "-test -f" ]; then [ "$SAMPLE_TYPE" != directory ]; fi
''')
            client.chmod(0o755)
        self.log = self.root / 'calls'

    def invoke(self, *args, **env):
        self.log.write_text('')
        return subprocess.run([self.root / 'run_pipeline.sh', *args], capture_output=True, text=True,
                              env=dict(PATH=f"{self.root}:{os.defpath}", LOG=str(self.log), **env))

    def calls(self):
        return self.log.read_text().splitlines()

    def test_preloaded_order_on_podman(self):
        result = self.invoke('--skip-load', COMPOSE_PROJECT_NAME='lake')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), ['podman lake ' + step for step in BATCH])

    def test_explicit_load_with_docker_fallback(self):
        result = self.invoke('--load', UNAVAILABLE='podman')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls()[2:], ['docker default ' + step for step in [LOADER, *BATCH]])

    def test_first_failure_preserves_status_and_stops(self):
        for step in [LOADER, *BATCH]:
            with self.subTest(step=step):
                result = self.invoke('--load', COMPOSE_ENGINE='docker', FAIL=step)
                self.assertEqual(result.returncode, 17)
                self.assertEqual(self.calls()[-1], 'docker default ' + step)
                self.assertIn(step, result.stderr)

    def test_sample_uses_configured_project_and_uploads_once_when_empty(self):
        self.assertIn('name: dewa', (ROOT / 'compose.yaml').read_text().splitlines())
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        # The client records "default" when the runner leaves project selection to Compose.
        self.assertTrue(all(call.startswith('podman default ') for call in self.calls()))
        self.assertEqual([call for call in self.calls() if ' -put ' in call], [
            f'podman default -T namenode hdfs dfs -put /workspace/data/sample/readings_sample.csv {SAMPLE}'])

    def test_sample_reuses_a_populated_readings_directory(self):
        full = '/dewa/raw/readings/full.csv'
        for files in [full, SAMPLE, full + '\n' + SAMPLE]:
            with self.subTest(files=files):
                result = self.invoke('--sample', FILES=files)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('Reusing existing readings', result.stdout)
                self.assertNotIn(' -put ', self.log.read_text())
                self.assertNotIn(LOADER, self.log.read_text())
                self.assertEqual(f' -test -f {SAMPLE}' in self.log.read_text(), SAMPLE in files.splitlines())
                self.assertEqual(self.calls()[-len(BATCH):], ['podman default ' + step for step in BATCH])

    def test_load_matches_whole_lines_even_with_broken_grep(self):
        grep = self.root / 'grep'
        grep.write_text('#!/bin/sh\nexit 2\n')
        grep.chmod(0o755)
        similar = [SAMPLE + '.bak', '/archive' + SAMPLE]
        for paths, expected in [(similar, 0), ([similar[0], SAMPLE, similar[1]], 1)]:
            with self.subTest(paths=paths):
                result = self.invoke('--load', FILES='\n'.join(paths))
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertEqual('podman default ' + LOADER in self.calls(), expected == 0)

    def test_directory_named_like_sample_stops_before_spark(self):
        for files in [SAMPLE, SAMPLE + '\n/dewa/raw/readings/full.csv']:
            with self.subTest(files=files):
                result = self.invoke('--sample', FILES=files, SAMPLE_TYPE='directory')
                self.assertEqual(result.returncode, 1)
                self.assertIn('regular file', result.stderr)
                self.assertEqual(self.calls()[-1], f'podman default -T namenode hdfs dfs -test -f {SAMPLE}')

    def test_failed_listing_stops_both_load_modes(self):
        listing = '-T namenode hdfs dfs -ls -C /dewa/raw/readings'
        for mode in ('--sample', '--load'):
            with self.subTest(mode=mode):
                self.assertEqual(self.invoke(mode, FAIL=listing).returncode, 17)
                self.assertTrue(self.calls()[-1].endswith(listing))

    def test_missing_job_stops_before_loading(self):
        (self.root / 'spark/aggregates.py').unlink()
        result = self.invoke('--load')
        self.assertEqual(result.returncode, 3)
        self.assertIn('spark/aggregates.py', result.stderr)
        self.assertEqual(self.calls(), [])

    def test_usage_and_unavailable_explicit_provider(self):
        for args in [('--unknown',), ('--skip-load', '--load')]:
            self.assertEqual(self.invoke(*args).returncode, 2)
        self.assertEqual(self.invoke('--help').returncode, 0)
        self.assertEqual(self.invoke(COMPOSE_ENGINE='invalid').returncode, 2)
        self.assertEqual(self.invoke(COMPOSE_ENGINE='podman', UNAVAILABLE='podman').returncode, 1)
        self.assertEqual(self.calls(), [])
