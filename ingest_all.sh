#!/usr/bin/env bash
# ingest_all.sh - refresh every sport this project covers, up to today.
#
# Run from Git Bash:   bash ingest_all.sh > ingest_all.log 2>&1
#
# Safe to re-run. Every ingest merges or rewrites its own store; none of them
# touch multisport_history.db, so no prediction or graded result is at risk.
#
# Source notes, learned the hard way:
#   soccer-espn  is used, NOT the "soccer" adapter -- that one reads FBref,
#                which is Cloudflare-blocked from this machine.
#   ingest_tennis.py reads tennis-data.co.uk. The "tennis" adapter reads
#                Sackmann on GitHub, which returns 403 here.
set -u
cd "$(dirname "$0")" || exit 1

PY="venv/Scripts/python.exe"
[ -x "$PY" ] || PY="python"

fail=0
line() { printf '=%.0s' $(seq 1 72); echo; }
step() { echo; line; echo "  $*"; line; }
run()  { echo; echo "\$ $PY $*"; "$PY" "$@" || { echo "  [FAILED] $1 (exit $?)"; fail=$((fail+1)); }; }

TODAY=$(date +%Y-%m-%d)
echo "ingest_all.sh   $TODAY"

step "1/6  MLB team metrics + probable starters"
run ingest_all_sports.py --only mlb
run ingest_all_sports.py --only mlb-probables

step "2/6  KBO team metrics"
run ingest_all_sports.py --only kbo

step "3/6  Soccer (ESPN, every league in the table)"
run ingest_soccer_espn.py --all

step "4/6  Tennis (ATP + WTA, 2025-2026)"
run ingest_tennis.py --years 2025 2026 --tours atp wta

step "5/6  NFL schedule, results, first-half splits, team stats"
run ingest_nfl_schedule.py --season 2026
run ingest_nfl.py --season 2026

step "6/6  NCAAF results since the last pull"
# Rolling 3-day window ending today, so this stops going stale between runs.
ncaaf_dates=()
for d in 2 1 0; do
  ncaaf_dates+=("$(date -d "$d days ago" +%Y-%m-%d)")
done
run ingest_ncaaf.py --dates "${ncaaf_dates[@]}"

step "Freshness audit"
for s in baseball nfl soccer tennis basketball; do   # "baseball", not "mlb"
  echo; echo "--- $s ---"
  "$PY" data_guard.py --sport "$s" 2>&1 | tail -14
done

echo
line
if [ "$fail" -eq 0 ]; then
  echo "  Done. No step failed."
else
  echo "  Done, but $fail step(s) failed -- search this log for [FAILED]."
fi
line
