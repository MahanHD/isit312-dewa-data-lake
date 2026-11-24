# Latest meter status in HBase

```bash
docker compose exec hbase bash /workspace/hbase/02_load.sh
docker compose exec hbase hbase shell -n /workspace/hbase/03_verify.rb
```

On the course VM run the same commands without the Docker prefix and use local
paths. The loader uses local MapReduce because this stack has no YARN service.
It uses HBase's FsShell class to check the HDFS source path and preflight Spark
part-* files before creating the table. Preflight requires six fields, nonempty
key/reading values, OK or ALERT status, and no quotes or carriage returns. OK rows
must have empty alert type/time; ALERT rows must supply both. The import uses the same part-* glob as preflight, so unrelated visible files
are not accidentally imported. Timestamp and numeric
semantics remain the Spark producer's responsibility. Creating the table is idempotent; an existing table is described, not reset.

Input is Spark's **headerless**, six-field, comma-separated meter_status export:

```
meter_id,last_reading_ts,last_kwh,alert_status,alert_type,alert_ts
```

The line above describes field order; it must NOT appear as a header in input.
Every record must have all six positions, including trailing delimiters for empty
alert fields. Timestamps use yyyy-MM-dd HH:mm:ss. Values are strings. ImportTsv
is a delimiter parser, not an RFC CSV parser: no quoting, embedded commas or
newlines are allowed in fields. Spark must export empty fields as empty text,
not quoted empty strings. In Spark CSV export, explicitly set
`.option("emptyValue", "").option("nullValue", "")`; Spark's default serialization
of empty strings can otherwise produce quoted empty fields that preflight rejects. It must emit exactly one row per meter. Validate these
conditions upstream; ImportTsv's bad-line check validates structure, not timestamp
formats or status semantics. Hadoop ignores Spark's _SUCCESS and hidden files.

Mapping: meter_id -> row key; r:ts/r:kwh -> latest reading;
a:status/a:type/a:ts -> current alert. Empty columns are written, clearing previous
alert text when a meter becomes OK. Keep this behaviour when changing imports.
A reimport updates existing keys and retains one visible cell version; it does
not remove meters missing from the next snapshot. This is an upsert view, not
an atomic snapshot replacement. Failed imports can partially update rows. Do not
load an older export over newer data: ingestion time determines cell versions,
not the event timestamp stored as text. Concurrent imports are unsupported.

The ALERT scan is a demonstration and scans rows; the primary efficient access
pattern is `get` by meter ID. It is not a secondary index or a streaming pipeline.
The sample verification ID may need changing. The checks done, including that an
ALERT -> OK update clears a:type and a:ts, are in `docs/hive-hbase-validation.md`.
