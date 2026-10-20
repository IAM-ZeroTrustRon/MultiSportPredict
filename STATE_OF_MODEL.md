## Current workflow and record — October 19, 2026

The supported entrypoint is msp.py (see COMMANDS.md). Refresh, run/slate, immutable saved review, explicit delivery, grading and period/all-time records share the canonical database. The local hourly automation now grades all sports and sends no Discord messages; it never deletes records.

Verified result recovery added 31 grades. An integrity-checked backup and exact deletion manifest preceded removal of 47 unresolved historical ordinary rows and 18 table-tennis runs. Two active selections and two excluded reruns for tonight's in-progress SF–Washington event were preserved. A new reporting period begins 2026-10-20; historical settled records remain queryable.

Retained historical model record: 181W–195L–3P, 48.14% excluding pushes. Recorded-price subset: 112W–124L–2P, +20.2397 simulated units, +8.50% simulated ROI on 238 one-unit stakes including pushes. Another 141 historical grades lack confirmed recorded-price settlement. These are model records, not confirmed wagers; unresolved deletions introduce selection bias. See docs/PERFORMANCE_2026-10-19.md rather than presenting these as audited profitability.

MLB player imports share one official MLB Stats API + Baseball Savant schema (649 pitchers, 532 hitters; ambiguous Max Muncy names omitted). France soccer recovered 36 teams with bounded transient retries. Other refresh stages completed. Public table-tennis collection currently reports no readable recent-results page; no complete point-score coverage is claimed.

Review findings and remaining model/security/testing limitations: docs/REPOSITORY_REVIEW_2026-10-19.md. README now describes value handicapping, pricing discrepancies and estimated EV. The update includes curated screenshots under docs/evidence; publication details are in the repository commit history. Earlier notes below describe historical snapshots.

## Table-tennis paste and manual grading repair — 2026-10-11

MyStake clipboard parsing no longer requires the omitted Table Tennis navigation
label when the explicit Czechia/Czech Liga Pro header is present. Full-name tokens
identify participants independently of exact line positions; reordered names and
accents remain supported without fuzzy substitution of different players. Odds
pairing, competition, format, start and price-freshness checks remain enforced.
`run_table_tennis.py` loads optional `current_match_config.json` for the simple
no-argument paste workflow and emits a standalone `RUN_ID=tt_...` after saving.
`grade_table_tennis.py` adds --pending, confirmed --run-id/--scores/--source-url
registration and --import-file. It retains the saved provider IDs, validates legal
points before event updates, backs up SQLite, and grades immutable forecasts.
At diagnosis, all 11 saved runs had scheduled MyStake events; the 3 finished
public events were different IDs, explaining zero grades. No finals were invented.
Regression: tests/test_table_tennis_paste_grading.py, including no-argument CLI,
price mapping, invalid finals, original identity and idempotent grading.

Full sports audit - 2026-10-11

Tennis ESPN result insertion was unreachable beneath the unresolved-name continue; corrected and regression-tested. Final full regrade: 295 graded decisions, including 27 tennis (22 newly settled). All-sport ingestion/audit logs: output/full_audit_20261011/. Public table tennis results unavailable on retry; 10 runs and 80 research selections remain unresolved. Table tennis hourly collection/training/grading heartbeat is active; saved research selections remain separate from placed bets.

Google Docs table-tennis guide — 2026-10-10

Indexed operating guide: https://docs.google.com/document/d/1GFDeYLVTDHfpc4v5dgBB3f7gLOoCBm5mA1fJvG-yBtE/edit
TABLE_TENNIS_COMMANDS.md is its local content copy. Discord Model Notes section removed; terminal observations/warnings and the brief price/model basis remain. Reference lines have no assumed sportsbook price or EV. Manual final-result preparation validates actual complete game scores and retains the exact stored event/player IDs before canonical import/grading; it requires the operator to verify fixture identity from a real source. No Discord sent and no final result was invented/imported.
