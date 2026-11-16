# Validation status

Implemented on branch hive/hive-hbase-implementation.

Passed in the Codex workspace:

- `bash -n hive/run.sh hbase/02_load.sh`
- `git diff --check`
- `docker compose config --quiet`
- `python -m unittest discover -s tests -v`: 17 tests passed in the follow-up audit.
  Ten fake-client tests check argument forwarding, month/base validation, valid OK
  and ALERT rows, malformed export rejection, consistent validation/import paths,
  and propagation of HDFS, table-creation, import and Beeline failures.
  Seven SQLite fixture tests execute the six report SELECTs and check monthly
  totals/coverage, peak order, hourly sums/means, anomaly events/distinct meters,
  low-coverage days, cleaned/daily reconciliation, and an empty month. SQLite is
  only a calculation check; it is not Hive execution.

HBase 2.6.7 upstream source review confirmed that ImportTsv retains a trailing empty
field and TsvImporterMapper writes empty values when skip.empty.columns=false.
It also showed ImportTsv permits missing trailing columns, motivating the stricter
six-field preflight. Source references:

- https://github.com/apache/hbase/blob/rel/2.6.7/hbase-mapreduce/src/main/java/org/apache/hadoop/hbase/mapreduce/ImportTsv.java
- https://github.com/apache/hbase/blob/rel/2.6.7/hbase-mapreduce/src/main/java/org/apache/hadoop/hbase/mapreduce/TsvImporterMapper.java

Live execution was attempted with `docker compose up -d`. Image extraction failed
with `failed to register layer ... no space left on device` in the Docker daemon's
storage. A follow-up attempt with only namenode, datanode and hive also failed while
pulling image data with `write ... GetImageBlob...: no space left on device`.
No running services were available for a real Hive/HBase smoke test.
The static and fake-client checks do not establish HiveQL runtime compatibility,
HDFS permissions, client/server connectivity or successful data ingestion.
No runtime screenshots or benchmark results are supplied or claimed.

Before final submission, run the commands in hive/README.md and hbase/README.md on
a machine with the Docker stack working and actual Spark output. Check partition
registration, same-month total reconciliation, HBase get and ALERT -> OK updates.
Obtain auxiliary source schemas from the Spark teammate before adding those tables.
