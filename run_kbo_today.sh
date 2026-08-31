#!/usr/bin/env bash
# run_kbo_today.sh - refresh KBO data, run the full slate, push to the bot app
#
#   ./run_kbo_today.sh              scrape, run all 5, push to the app server
#   ./run_kbo_today.sh --review     scrape and run, push NOTHING
#   ./run_kbo_today.sh --no-scrape  skip the refresh, just run and push
#
# WHERE IT GOES
#   The app server (your bot channel), regardless of what .env says. The
#   destination is set for this run only -- nothing on disk changes, and your
#   webhook servers are not touched. To send the same slate to the webhooks
#   instead:  DEST=webhooks ./run_kbo_today.sh
#
# THE MATCHUPS ARE HARDCODED AND THAT IS DELIBERATE
#   Home team FIRST. The mykbostats feed prints "away @ home", so these are
#   already flipped -- getting that backwards applies home advantage to the
#   wrong club, which has happened here before and grades as a correct-looking
#   prediction built on a wrong number.
#
#   EDIT THE LIST BELOW EACH DAY. Nothing in this project checks a matchup
#   against a real schedule yet, so a stale list produces confident predictions
#   for games nobody is playing. That has also happened here. The script prints
#   the card before running so you can see it.
#
#   Today's source: https://mykbostats.com/games

set -u
cd "$(dirname "$0")" || exit 1

PY="venv/Scripts/python.exe"
if [ ! -x "$PY" ]; then
  echo "No interpreter at $PY (in $(pwd))." >&2
  echo "Refusing to fall back to system Python -- it has none of the packages." >&2
  exit 1
fi

# --- today's card: HOME vs AWAY ---------------------------------------------
MATCHES=(
  "Samsung Lions vs KT Wiz"
  "Lotte Giants vs LG Twins"
  "Hanwha Eagles vs NC Dinos"
  "KIA Tigers vs SSG Landers"
  "Doosan Bears vs Kiwoom Heroes"
)

DEST="${DEST:-bot}"
SCRAPE=1
PUSH=1
for arg in "$@"; do
  case "$arg" in
    --review)    PUSH=0 ;;
    --no-scrape) SCRAPE=0 ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

echo "=============================================================="
echo "KBO  -  ${#MATCHES[@]} games   destination: $([ "$PUSH" = 1 ] && echo "$DEST" || echo "none (--review)")"
echo "=============================================================="
for m in "${MATCHES[@]}"; do echo "  $m"; done
echo "  (home team first -- check that against mykbostats.com/games)"
echo

if [ "$SCRAPE" = 1 ]; then
  echo "--- refreshing KBO team stats -------------------------------"
  if ! "$PY" ingest_all_sports.py --only kbo; then
    echo
    echo "The KBO refresh failed. Nothing was run." >&2
    echo "The store still holds whatever it had before -- run with" >&2
    echo "--no-scrape if you want to predict from that anyway." >&2
    exit 1
  fi
  echo
fi

echo "--- data guard ----------------------------------------------"
"$PY" data_guard.py --sport baseball || true
echo

ARGS=(run_mlb.py --league KBO)
for m in "${MATCHES[@]}"; do ARGS+=(--match "$m"); done
[ "$PUSH" = 1 ] || ARGS+=(--no-discord)

if [ "$PUSH" = 1 ]; then
  DISCORD_PUSH_TARGET="$DEST" "$PY" "${ARGS[@]}"
else
  "$PY" "${ARGS[@]}"
fi

echo
echo "=============================================================="
if [ "$PUSH" = 1 ]; then
  echo "Pushed to: $DEST"
  echo "Nothing on disk changed -- .env is untouched."
else
  echo "Nothing was pushed. To send it:  ./run_kbo_today.sh --no-scrape"
fi
echo
echo "Four of five games carried a rainout warning today. A rained-out"
echo "game stays ungraded -- that is correct, not a failure."
echo
echo "Grade them tomorrow:"
echo "    $PY grade_predictions.py --auto --report"
echo "=============================================================="
