#!/usr/bin/env bash
# ingest_football.sh - NFL Week 1 results + 2026 team stats, and every NCAAF
# result of the season so far.
#
# Run from Git Bash:   bash ingest_football.sh
#
# Safe to re-run. Both ingests merge on game id, so nothing already on disk is
# lost. NCAAF writes results only -- there is no college team-stats store in
# this project yet.
set -u
cd "$(dirname "$0")" || exit 1

PY="venv/Scripts/python.exe"
[ -x "$PY" ] || PY="python"

line() { printf '=%.0s' $(seq 1 70); echo; }
step() { line; echo "  $*"; line; }

fail=0
run() {
  echo
  echo "\$ $PY $*"
  "$PY" "$@" || { echo "  [FAILED] $1"; fail=$((fail+1)); }
}

step "1/3  NFL schedule + Week 1 results + first-half splits"
run ingest_nfl_schedule.py --season 2026

step "2/3  NFL 2026 team stats (keeps your 2025 records)"
run ingest_nfl.py --season 2026

step "3/3  NCAAF results, season to date"
for d in 2026-08-29 2026-08-30 2026-09-03 2026-09-04 2026-09-05 2026-09-06 \
         2026-09-10 2026-09-11 2026-09-12 2026-09-13; do
  echo
  echo "--- $d ---"
  "$PY" ingest_ncaaf.py --dates "$d" || echo "  [skip] $d returned nothing"
done

step "Freshness check"
run data_guard.py --sport nfl

echo
line
if [ "$fail" -eq 0 ]; then
  echo "  Done. No step failed."
else
  echo "  Done, but $fail step(s) failed -- read the output above."
fi
echo "  NCAAF wrote results only. There is no ncaaf_stats.json in this project."
line
