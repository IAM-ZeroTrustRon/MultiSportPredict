#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# run_liga_mx.sh - refresh Liga MX data, then run matches and push to Discord
#
#   ./run_liga_mx.sh                                Club Leon vs Atlante
#   ./run_liga_mx.sh --match "Toluca vs Pachuca"
#   ./run_liga_mx.sh --match "Club Leon vs Atlante" --total 2.5 --line -0.5
#   ./run_liga_mx.sh --no-discord
#   ./run_liga_mx.sh --skip-ingest                  data is already fresh
#   ./run_liga_mx.sh --list-teams
#
# Anything not listed above is passed straight through to run_liga_mx.py.
# ---------------------------------------------------------------------------

cd "$(dirname "$0")" || exit 1

# Windows venv first, then anything on PATH.
PY=".venv/Scripts/python.exe"
[ -x "$PY" ] || PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
  echo "No Python found. Expected .venv/Scripts/python.exe in $(pwd)"
  exit 1
fi

SKIP_INGEST=0
ARGS=()
for arg in "$@"; do
  if [ "$arg" = "--skip-ingest" ]; then
    SKIP_INGEST=1
  else
    ARGS+=("$arg")
  fi
done

echo "==============================================================="
echo " Liga MX  -  $(date '+%Y-%m-%d %H:%M')"
echo " Python: $PY"
echo "==============================================================="

if [ "$SKIP_INGEST" -eq 0 ]; then
  echo
  echo "--- Step 1/2: refreshing Liga MX from football-data.co.uk ---"
  "$PY" ingest_soccer_fd.py --countries mexico
  RC=$?
  # Exit 1 means some country failed; with one country that is fatal, so stop
  # rather than predicting off whatever stale data happens to be on disk.
  if [ $RC -ne 0 ]; then
    echo
    echo "Ingestion failed (exit $RC). Not running predictions on stale data."
    echo "The raw download is in data/cache/probe/ if you want to look."
    exit $RC
  fi
else
  echo
  echo "--- Step 1/2: skipped (--skip-ingest) ---"
fi

echo
echo "--- Step 2/2: running matches ---"
"$PY" run_liga_mx.py "${ARGS[@]}"
RC=$?

echo
if [ $RC -eq 0 ]; then
  echo "Done. Grade it once the match is final:"
  echo "  $PY grade_predictions.py --pending"
else
  echo "run_liga_mx.py exited $RC"
fi
exit $RC
