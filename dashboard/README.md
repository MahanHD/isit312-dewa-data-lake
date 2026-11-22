# Demo dashboard (Zeppelin)

Zeppelin notebook that runs the reports in `hive/02_reports.hql` on Hive and shows them as tables and charts.
It is a separate Compose profile, so `docker compose up -d` does not start it.

```bash
docker compose --profile dashboard up -d zeppelin     # or: podman compose --profile dashboard up -d zeppelin
```

Wait about a minute, then open http://localhost:8080 and the **DEWA dashboard** note. Pick a month in the box at the
top (default `2013-01`) and click **Run all** (the play button at the top of the note).

```bash
docker compose stop zeppelin                          # frees the memory again after the demo
```

- First start downloads the Hive JDBC driver (about 45 MB). It needs internet once per new container.
- The notebook is rebuilt from `hive/02_reports.hql` every time Zeppelin starts, so new reports show up after a
  restart. Changes made in the Zeppelin page are not saved back to the repo.
- The driver is version 4.0.1, not 4.2.1: Zeppelin runs on Java 11 and the 4.2.x driver needs Java 21. Older drivers
  can talk to a newer HiveServer2, but check this first if the connection fails.
- Hive and the tables need to be up first (`hive/01_create_tables.hql`, `hive/03_refresh_partitions.hql`).
- Zeppelin and its interpreter are capped at 512 MB of Java heap each.
- If a report shows "interpreter not found" or a connection error, check `docker compose logs zeppelin` for the
  line `jdbc interpreter now points at Hive`.
