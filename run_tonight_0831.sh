#!/usr/bin/env bash
# run_tonight_0831.sh - Mon 31 Aug 2026: four MLB games + one US Open R1 match
#
#   ./run_tonight_0831.sh           predict everything, push NOTHING
#   ./run_tonight_0831.sh --push    send it all to the webhook servers
#
# Destination is set for this run only. .env is not touched.
# To send to the bot app instead:  DEST=bot ./run_tonight_0831.sh --push
#
# FIXTURES VERIFIED 2026-08-31 16:47 ET
#   All four MLB games appear on statsapi.mlb.com for 2026-08-31, and in every
#   case the team you listed first is the AWAY team. run_mlb.py reads home/away
#   from the schedule feed rather than the order typed, so it will correct
#   itself and print what it used -- but the list below is already right.
#
#   Borges v Tien is US Open Round 1, confirmed on the order of play.
#
# "FLORIDA MARLINS" IS NOW THE MIAMI MARLINS
#   Renamed in 2012. The store and the MLB feed both use Miami, and the fuzzy
#   name matcher does not bridge those two words, so the old name would have
#   failed to resolve rather than quietly matching something else.
#
# ODDS
#   MLB totals come live from The Odds API via --odds (spends a little of your
#   monthly quota). Without it every total is a hardcoded 8.5 placeholder and
#   the "edge" is the gap between the model and a number nobody offered.
#   Tennis prices are the opening line, decimal 2.36 / 1.58 converted:
#       Borges +136   Tien -172   (de-vigs to 105.7%, a believable margin)

set -u
cd "$(dirname "$0")" || exit 1

PY="venv/Scripts/python.exe"
if [ ! -x "$PY" ]; then
  echo "No interpreter at $PY (in $(pwd))." >&2
  echo "Refusing to fall back to system Python -- it has none of the packages." >&2
  exit 1
fi

DEST="${DEST:-webhooks}"
PUSH=0
[ "${1:-}" = "--push" ] && PUSH=1

echo "=============================================================="
echo "TONIGHT  -  4 MLB + 1 tennis"
echo "  destination: $([ "$PUSH" = 1 ] && echo "$DEST" || echo "none (review only)")"
echo "=============================================================="

# ---------------------------------------------------------------- MLB
MLB=(run_mlb.py --league MLB --odds
     --match "Atlanta Braves vs San Francisco Giants"
     --match "Cincinnati Reds vs San Diego Padres"
     --match "Boston Red Sox vs Seattle Mariners"
     --match "Washington Nationals vs Miami Marlins")

echo
echo "--- MLB ------------------------------------------------------"
if [ "$PUSH" = 1 ]; then
  DISCORD_PUSH_TARGET="$DEST" "$PY" "${MLB[@]}"
else
  "$PY" "${MLB[@]}" --no-discord
fi

# ---------------------------------------------------------------- TENNIS
echo
echo "--- TENNIS ---------------------------------------------------"
"$PY" run_tennis.py --tournament "US Open" --round R1 --surface hard \
  --match "Nuno Borges vs Learner Tien" --p1-ml 136 --p2-ml -172

if [ "$PUSH" = 1 ]; then
  echo
  echo "--- pushing tennis -------------------------------------------"
  DISCORD_PUSH_TARGET="$DEST" "$PY" run_tennis.py --push 1
fi

echo
echo "=============================================================="
if [ "$PUSH" = 1 ]; then
  echo "Pushed to: $DEST   (.env untouched)"
else
  echo "Nothing was pushed. Reviewed and stored only."
  echo "To send it:   ./run_tonight_0831.sh --push"
fi
echo
echo "Grade them tomorrow:"
echo "    $PY grade_predictions.py --auto --report"
echo "=============================================================="
