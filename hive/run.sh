#!/usr/bin/env bash
# Docker: docker compose exec hive bash /workspace/hive/run.sh hive/01_create_tables.hql
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
if [[ $# -lt 1 || $# -gt 2 || ! -f "$1" ]]; then
  echo "Usage: bash hive/run.sh FILE.hql [YYYY-MM]" >&2
  exit 2
fi
report_month="${2:-2013-01}"
base="${DEWA_BASE:-/dewa}"
[[ "$report_month" =~ ^[0-9]{4}-(0[1-9]|1[0-2])$ ]] || { echo 'Invalid month' >&2; exit 2; }
[[ "$base" =~ ^/[a-zA-Z0-9_/-]+$ && "$base" != / ]] || { echo 'Invalid DEWA_BASE' >&2; exit 2; }
# -e avoids the repository's documented Beeline -f terminal issue.
exec beeline -u "${HIVE_JDBC_URL:-jdbc:hive2://localhost:10000}" \
  --force=false --silent=true --showHeader=true \
  --hivevar base="$base" --hivevar report_month="$report_month" -e "$(cat "$1")"
