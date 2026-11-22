# Run the DEWA batch

Use a terminal in this checkout with the `dewa` Compose stack running and the checkout mounted at `/workspace`. The default command uses `--sample`.

```bash
./run_pipeline.sh
```

`--sample` uploads the bundled readings only when `/dewa/raw/readings` is empty. On a populated stack it reports reuse and processes the readings already there, including full data. All modes use Compose's project selection. The repository's `compose.yaml` names the project `dewa`. If the stack was started with a project override, use the same setting for the runner.

```bash
COMPOSE_ENGINE=podman ./run_pipeline.sh --skip-load
```

`--skip-load` processes the current HDFS inputs directly. `--load` delegates to the append-only loader for prepared full inputs in `data/download/` and stops if the sample readings file is already present.

The runner tries Podman Compose, then Docker Compose, or uses the explicitly selected engine. Even when raw readings are reused, Spark rewrites its cleaned and curated outputs, Hive updates table and partition metadata, and HBase updates meter rows.

The five Spark jobs run in the order in `spark/README.md`. Missing `spark/aggregates.py` stops the batch with exit 3 before any service call. Extra sources are cleaned when present. Existing raw customers must already have the five-column schema in Shared rules 8; coordinate any old-file cutover separately.

Hive creates the external tables, repairs the four monthly partitioned tables, and prints the reports in `hive/02_reports.hql` for the wrapper's default month (2013-01). Keep the terminal attached for Beeline and screenshots. HBase then validates and imports the meter-status CSV. Each command is printed before execution; a failed stage returns its exit code and stops the batch.
