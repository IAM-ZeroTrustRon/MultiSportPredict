#!/usr/bin/env bash
# Daily real-data ingestion for every sport.
# Windows users: prefer refresh_all.bat -- it is what the scheduled task runs.
set -uo pipefail
cd "$(dirname "$0")"

PY="venv/Scripts/python.exe"
[ -x "$PY" ] || PY="python"

echo "=== STARTING DAILY REAL-DATA INGESTION ==="
"$PY" ingest_all_sports.py "$@"
RC=$?
echo "=== DONE (exit $RC: 0=all OK, 1=some failed, 2=all failed) ==="
exit $RC
