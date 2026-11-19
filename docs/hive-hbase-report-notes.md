# Hive and HBase report notes (draft, not execution evidence)

## Purpose and implementation

The DEWA-oriented prototype separates historical reporting from per-meter status
retrieval. Spark writes agreed Parquet files to HDFS. Hive external tables expose
cleaned readings and curated hourly, daily and anomaly datasets without copying
those files. Monthly partition predicates restrict the requested data range.
After Spark writes partitions, MSCK REPAIR registers them for Hive queries.

HBase stores one row per meter in dewa_meter_status. The r family contains the
latest reading timestamp and kWh; the a family contains alert status, type and
timestamp. A headerless Spark export is loaded using ImportTsv in local MapReduce
mode. This demonstrates batch refresh of a serving table, not real-time ingestion.

## Tool choices and evaluation to perform

Hive suits historical SQL aggregation. HBase suits keyed reads and updates; it
would require scans or extra indexes to answer fleet-wide analytical queries.
HDFS alone stores files but does not supply either SQL reporting or keyed updates.
A MapReduce batch import can refresh this demonstration, but job startup and batch
latency make it unsuitable as the proposed low-latency live alert ingestion path.
These are design arguments: substantiate empirical claims with measured runs.

Record the dataset scope, hardware, tool versions, cold/warm runs and timings.
Reconcile cleaned and daily kWh totals for the same month, inspect partition
pruning with EXPLAIN, compare an HBase get with a bounded demonstration scan, and
verify both ALERT and subsequent OK states. Include actual commands and screenshots.
Do not invent results, latency figures, stakeholder interviews or DEWA approval.

## Limitations and remaining dependencies

London household electricity data stands in for DEWA data; climate, tariffs,
customer population and operational scale differ. Local wall-clock timestamps
have DST ambiguity. Sample results cannot establish production performance.
The single-node Docker stack lacks production availability and security controls.
HBase refreshes are non-atomic upserts; absent keys persist and old exports must
not overwrite newer states. Company evaluation required by the specification remains
a group responsibility; disclose if no direct company feedback was obtained.

## Suggested slides

1. HDFS -> Spark -> Hive historical reporting / HBase meter-status retrieval.
2. External Parquet tables, monthly partitions, example report and real output.
3. HBase key and families, import, real get and ALERT -> OK demonstration.
4. Validation results, dataset limitations and remaining integration work.
