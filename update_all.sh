#!/usr/bin/env bash
# update_all.sh - one command: back up the record, refresh every store, grade
# everything that can be graded, print the record.
#
# Run from Git Bash:   bash update_all.sh
# Full log is written to logs/update_YYYY-MM-DD.log
#
# Order matters:
#   1. back up multisport_history.db (grading writes to it)
#   2. ingest every sport (ingest_all.sh - never touches the database)
#   3. regrade already-settled rows with the current grading rules
#   4. settle new results: MLB, NFL, NCAAF, tennis, soccer (120-day lookback)
#   5. report + list what is still unsettled
# KBO and basketball have no auto-grader; they stay pending until settled
# with --manual.
set -u
cd "$(dirname "$0")" || exit 1
PY="venv/Scripts/python.exe"
[ -x "$PY" ] || PY="python"
TODAY=$(date +%Y-%m-%d)
mkdir -p logs backups
LOG="logs/update_${TODAY}.log"

{
echo "update_all.sh   $TODAY"

echo; echo "== 1/5  Backup =="
cp multisport_history.db "backups/multisport_history.${TODAY}.db" \
  && echo "  saved backups/multisport_history.${TODAY}.db" \
  || { echo "  [STOPPED] backup failed - nothing graded"; exit 1; }

echo; echo "== 2/5  Ingest every sport =="
bash ingest_all.sh

echo; echo "== 3/5  Regrade settled rows (current rules) =="
"$PY" grade_predictions.py --regrade || echo "  [FAILED] regrade"

echo; echo "== 4/5  Settle new results =="
"$PY" grade_predictions.py --auto --days 120 || echo "  [FAILED] auto-grade"

echo; echo "== 5/5  Record + still pending =="
"$PY" grade_predictions.py --report
"$PY" grade_predictions.py --pending --days 120
} 2>&1 | tee "$LOG"

echo
echo "Log saved: $LOG"
