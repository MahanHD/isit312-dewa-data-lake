# Hive + HBase completion audit

Verdict: core implementation present; not fully integrated or submission-ready.
Audit sources: repository README/shared rules and main at 2bc2346, the supplied
ISIT312 Autumn 2026 specification PDF, and the leader's pasted messages. The Drive
plan document was not available in this audit; its individual deadlines cannot be
verified. The messages and PDF are project context, not authorization to contact
the leader, alter shared contracts, or publish to main.

| Requirement | Status | Evidence / remaining work |
|---|---|---|
| Work on a branch | Done | hive/hive-hbase-implementation; main unchanged |
| Use agreed names, paths and types | Core done | Five specified Hive tables; agreed HBase table/key/families |
| Hive external tables, monthly partitions, repair | Implemented, runtime pending | 01_create_tables.hql and 03_refresh_partitions.hql |
| Historical reporting queries | Implemented; fixture checks pass | Six SELECTs with explicit month predicates; real Hive run pending |
| Four auxiliary Hive tables | Blocked by shared contracts | README names tariffs/weather/bank_holidays/customers but gives no column schemas; Spark main has no jobs yet |
| HBase create, load and get/alert demonstration | Implemented, runtime pending | Idempotent creation, preflight, local MR import, verification commands |
| Newer Docker stack | Configuration validates; startup blocked here | Both full and reduced stack pulls failed due Docker storage exhaustion |
| Test using small repository sample | Partially pending | Sample is present; no running HDFS/Hive or actual Spark outputs to test end to end |
| Test on your laptop / Mac compatibility | Unverified | A Codex machine cannot establish laptop compatibility |
| Preserve compatibility with Hive 2.1.1 fallback | Design target; unverified | No course VM available; static review is not runtime proof |
| Save screenshots as work progresses | Pending | No successful live run to capture; guides specify screenshots/hive and screenshots/hbase |
| Write own report section and slides | Draft material only | Report notes and slide outline exist; final narrative and finished deck still needed |
| PR with reviewer from your part | Pending | Branch published; no PR/reviewer assigned |
| Data prep customer generation/tariff conversion | Other part | Not assigned to Hive + HBase in the README/leader text |
| Actual group-plan deadlines | Unknown | Separate Drive plan not read |

## Test results and fix

17 automated tests pass: 10 mocked-client/script checks and 7 report-calculation
checks in SQLite fixtures. Shell syntax, Compose configuration and diff whitespace
checks pass. These do not verify HiveQL execution, Parquet mapping, HDFS permissions,
HBase cell state, or full-stack compatibility. See hive-hbase-validation.md.

The audit fixed an input-selection mismatch: validation read only Spark part-*
files but import formerly read the complete directory. Both now use the same glob.

## Concrete handoff dependencies

1. Obtain printSchema() output for the four cleaned reference sources from the
   Spark/data teammates, agree the join keys, then add external table definitions.
2. Obtain actual cleaned/curated Spark output, including the six-field headerless
   status export. For OK rows, agree empty alert fields; Spark should explicitly
   export emptyValue/nullValue as empty text to avoid quoted CSV empty values.
3. On a working Docker machine, create the tables, repair populated partitions,
   run all six reports for a month present in the sample, and reconcile totals.
4. Load HBase, inspect an actual meter and alerts, then reload a controlled OK
   update to demonstrate old alert fields clear. Record inputs and real outputs.
5. Save screenshots, complete your report section/deck, and request the required
   teammate review on a branch PR. Consult the Drive plan for the actual deadline.

The PDF additionally asks for empirical tool evaluation and company/stakeholder
feedback. Tool timing/results must come from real runs; company feedback is a
group-level dependency and must not be invented. Full dataset performance claims
cannot be supported solely by the three-household sample.
