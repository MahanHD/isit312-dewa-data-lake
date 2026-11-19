# Run the DEWA batch

Use a terminal in this checkout with the intended Compose stack already running and the checkout mounted at `/workspace`. Run the bundled readings sample first in its own project:

```bash
./run_pipeline.sh
```

The default project for `--sample` is `dewa-sample`. The runner uploads the sample into an empty raw readings folder or reuses the existing sample filename. For an existing stack, use the same project and Compose settings used to start it. For example:

```bash
COMPOSE_ENGINE=podman COMPOSE_PROJECT_NAME=dewa ./run_pipeline.sh --skip-load
```

`--skip-load` processes the current HDFS inputs directly. `--load` delegates to the append-only loader for prepared full inputs in `data/download/`. That loader can return zero after an intermediate ZIP member upload fails. Verify ingestion separately before relying on a new full load. Both options default to the stack's configured project.

The runner tries Podman Compose, then Docker Compose, or uses the explicitly selected engine. Check the target before running: Spark rewrites its cleaned and curated outputs and HBase updates meter rows.

The five Spark jobs run in the order in `spark/README.md`. Missing `spark/aggregates.py` stops the batch with exit 3 before any service call. Extra sources are cleaned when present. Existing raw customers must already have the five-column schema in Shared rules 8; coordinate any old-file cutover separately.

Hive creates the external tables, repairs the four monthly partitioned tables, and prints the six reports for the wrapper's default month (2013-01). Keep the terminal attached for Beeline and screenshots. HBase then validates and imports the meter-status CSV. Each command is printed before execution; a failed stage returns its exit code and stops the batch.
