#!/usr/bin/env bash
# Runs a .hql file through beeline. Usage (from the repo folder): docker compose exec hive bash /workspace/hive/run.sh hive/<file>.hql
# shortcut: Hive 4.2.1's beeline hangs on -f inside containers (terminal library bug), so the file goes through -e instead
set -euo pipefail
cd /workspace
exec beeline -u jdbc:hive2://localhost:10000 --silent=true --showHeader=true --hivevar base="${DEWA_BASE:-/dewa}" -e "$(cat "$1")"
