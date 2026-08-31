#!/usr/bin/env bash
# run_usopen_day1.sh - US Open 2026, Day 1 men's singles, with real prices
#
#   ./run_usopen_day1.sh          predict and review. Pushes nothing.
#   ./run_usopen_day1.sh --push 1 4 7
#
# ODDS ARE READ POSITIONALLY off the order-of-play screenshot: the player
# listed first takes the first price. Two of them read oddly against form
# (Merida Aguilar over Fucsovics, Samuel over Machac) -- both are in the
# skipped list below, so nothing here depends on them. Check the pairings
# against your book before backing anything: an edge measured against the
# wrong side of a price is worse than no edge.
#
# THREE MATCHES ARE MISSING ON PURPOSE
#   Daniel Merida Aguilar v Marton Fucsovics
#   Lloyd Harris v Jack Kennedy
#   Toby Samuel v Tomas Machac
# Merida Aguilar, Kennedy and Samuel have no tour-level matches in the store,
# so they have no Elo. The model would rate them at the starting constant and
# hand back a confident number about a player it has never seen. Left out.
#
# BEFORE THIS WILL RUN
#   ATP 2026 must be in the store. Check:
#       venv/Scripts/python.exe -c "import sys,json; sys.path.insert(0,'.'); \
#         import run_tennis as rt; \
#         print(rt.tour_lag(json.load(open('data/tennis/players.json')),'atp'), 'days')"
#   Under 45 is fine. 287 means the 2026 season did not download -- re-run
#   ingest_tennis.py until the ATP 2026 line reports a match count.

set -u
cd "$(dirname "$0")" || exit 1

PY="venv/Scripts/python.exe"
if [ ! -x "$PY" ]; then
  echo "No interpreter at $PY (in $(pwd))." >&2
  echo "Refusing to fall back to system Python -- it has none of the packages." >&2
  exit 1
fi

if [ "${1:-}" = "--push" ]; then
  shift
  exec "$PY" run_tennis.py --push "$@"
fi

"$PY" run_tennis.py \
  --tournament "US Open" --round R1 --surface hard \
  --match "Wu Y. vs Adam Walton"                 --p1-ml  100  --p2-ml -125 \
  --match "Kamil Majchrzak vs Hamad Medjedovic"  --p1-ml -125  --p2-ml  100 \
  --match "Sho Shimabukuro vs Arthur Rinderknech" --p1-ml 240  --p2-ml -303 \
  --match "Jiri Lehecka vs Pablo Carreno Busta"  --p1-ml -454  --p2-ml  333 \
  --match "Dino Prizmic vs Alexander Shevchenko" --p1-ml -303  --p2-ml  240 \
  --match "Luca van Assche vs Cameron Norrie"    --p1-ml  175  --p2-ml -227 \
  --match "Wong C. vs Tommy Paul"                --p1-ml  450  --p2-ml -714 \
  --match "Jaume Munar vs Terence Atmane"        --p1-ml  150  --p2-ml -188 \
  --match "Daniil Medvedev vs Hugo Gaston"       --p1-ml -1250 --p2-ml  700 \
  --match "Jaime Faria vs Jenson Brooksby"       --p1-ml  100  --p2-ml -125

echo
echo "Nothing was pushed. Review the EDGE column, then:"
echo "    ./run_usopen_day1.sh --push 1 4 7"
echo
echo "DISCORD_PUSH_TARGET is currently: ${DISCORD_PUSH_TARGET:-(from .env)}"
echo "Picks go to your webhooks. To send one run to the bot channel instead:"
echo "    DISCORD_PUSH_TARGET=bot ./run_usopen_day1.sh --push 1"
