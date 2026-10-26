# Handoff — tracked odds snapshots and closing-line value

Last updated: 2026-10-26. Owner of this note: whoever next touches the odds/CLV
path. Read this before changing a guard or "fixing" a refusal.

## What exists

A forecast stores the exact price pair it was priced with, immutably, so that a
later pre-kickoff capture of the same market can be compared to it. Nothing in
this path re-prices a fixture, rewrites a stored quote, or invents a close.

```
run_nhl.py / run_ncaaf.py / euroleague_engine.py
        └── capture_prediction_odds()  ──┐
closing_collector.py ────────────────────┤──> save_odds_snapshot()  ->  odds_snapshots (append-only)
                                         │                                   │
                                         └── refused[] -> output/odds_closing/<LEAGUE>_<UTC>.json
                                                                             │
                                                              clv.py ────────┘
```

| File | Role |
|---|---|
| `core/historical_storage.py` | `odds_snapshots` table, `save_odds_snapshot`, `capture_prediction_odds`, `get_odds_snapshots` |
| `closing_collector.py` | Pre-match capture for tracked predictions only; refuses rather than guesses |
| `clv.py` | Exact-line CLV (price and power-de-vigged probability), separate from line movement |
| `run_nhl.py`, `run_ncaaf.py`, `euroleague_engine.py` | Archive the prices each stored forecast used |
| `score_odds.py`, `live_odds.py` | Provider fetch; `for_fixture` attaches event ID and settlement scope; optional quota capture |
| `tests/test_odds_snapshots.py`, `tests/test_task2_safety.py` | The contract, stated as tests |

## Data model

`odds_snapshots` is append-only by trigger: `odds_snapshots_append_only_update`
and `odds_snapshots_append_only_delete` raise on any UPDATE/DELETE. A stored
quote can only be superseded by a new row.

Identity that must match before two rows may be compared (`clv.py`): event ID,
league, home/away orientation, bookmaker, settlement scope, market, line and
period. Different bookmakers, scopes or periods are never paired.

`snapshot_id` is a hash of the observation, so a repeated capture of the same
bookmaker publication is idempotent; prediction rows are additionally scoped by
`payload.run_id`, so two runs' prices are distinct observations.

## Guards (do not weaken)

| Guard | Where | Behaviour |
|---|---|---|
| No verified kickoff | storage | refused |
| Observed at/after kickoff | storage | refused as in-play |
| Bookmaker quote at/after kickoff | storage + collector | refused |
| Quote older than 5 min | collector | refused as stale |
| Quote in the future | collector + storage | refused |
| Lone price (no two-sided pair) | collector | refused, never priced by assumption |
| Official fixture not `FUT`/`PRE`/scheduled | collector | refused |
| Official kickoff differs from the tracked kickoff | collector | refused, reschedule review |
| Team orientation mismatch | collector | refused |
| Provider kickoff EARLIER than the league's | collector | **always** refused |
| Provider kickoff later than the league's by > 15 min | collector | refused for review |
| Provider marks event in-play/completed | collector | refused |
| Tracked bookmaker missing | collector | refused, no substitution |

### The kickoff tolerance, and why it exists

The Odds API mirrors the league schedule. Measured live on 2026-10-26 for NHL
game `2026020184` (official `02:00:00Z`), the provider reported `commence_time`
`02:10:00Z`: **exactly +600 s**. The same mismatch had refused the previous
night's game. Strict equality therefore blocked every closing capture.

The policy now: a late mirror is tolerated up to `KICKOFF_TOLERANCE_MINUTES = 15`
because the league time stays the **earlier**, hence binding, deadline. The
storage deadline is `min(official, provider)`, so the tolerated case still stores
the league kickoff and still refuses anything at or after it. An earlier provider
time is never tolerated — that would mean the provider already treats the event
as in-play.

Safety direction, stated plainly: this change can never make a capture *later*
than the league's own kickoff. It removes refusals that were blocking safe
captures; it does not remove any refusal that protected against in-play rows.
An unexplained gap larger than 15 minutes is still a refusal, not an acceptance.

## Commands

```bash
# Archive the prices a forecast used (one paid league request).
venv/Scripts/python.exe -u run_nhl.py --date 2026-10-25 \
    --match "Vancouver Canucks vs Minnesota Wild" --odds

# Capture the last verified prematch reference inside the 30..1 minute window.
venv/Scripts/python.exe -u closing_collector.py --league NHL \
    --date 2026-10-25 --event-id <provider event id>

# Compare. Free; reads the database only.
venv/Scripts/python.exe -u clv.py --sport nhl --json
```

`--dry-run` prices nothing; `--events-file`/`--fixtures-file` replay a saved
provider payload with **no** API request. A league request bills multiple credits
(three markets × one region = 3 on this account); the report records
`x-requests-last/used/remaining`.

No scheduler exists. `docs/ODDS_CLV_SCHEDULER_PROPOSAL.md` describes a cadence
that is **not** installed and must not be installed without a review.

## Where evidence lives

| Path | Contents |
|---|---|
| `output/task2_live_test/` | First bounded live test, DB backups, focused test log |
| `output/task2_partA/` | Pre-run DB backup for the second live test |
| `output/odds_closing/*.json` | Every collector report, including refusals with kickoff deltas |
| `output/nhl/<game_id>.json` | The stored forecast for that game |

## Audit review status

Resolved and covered by tests:

- Append-only snapshot storage; no update or delete path exists.
- Storage-level pre-kickoff guard, checked again at the boundary so no caller can
  archive an in-play row.
- Prediction capture links `run_id` (workflow via `MSP_RUN_ID`, direct via
  `direct_<uuid>`) plus official fixture ID, period, selections, odds format.
- Collector gates locally on tracked predictions and on a fresh public fixture
  check **before** spending a paid request.
- Quota headers are reported from an allowlist; no URL or credential is copied.
- Refusals record `official_kickoff_utc`, `provider_kickoff_utc`,
  `provider_minus_official_seconds` from the already-paid response, so the size
  of a discrepancy never costs a second request.
- CLV refuses cross-book/cross-scope/cross-period/cross-event pairs and reports
  line movement separately from CLV.
- Legacy tests: 14 `PytestReturnNotNoneWarning`s converted to real assertions.

Verified live:

- Prediction capture: 6 real rows across two games (`2026020183`, `2026020184`),
  both `fanduel`, both prematch, prices and quote timestamps archived.
- Refusal diagnostics: measured `+600.0 s` on `2026020184` without an extra call.
- Quota arithmetic: `used` 388 → 394 across exactly two requests at 3 credits.

Open:

- **No closing row has ever been stored.** Closing capture, closing idempotence
  and in-play rejection at capture time are still covered only by mocked tests.
  The next eligible fixture inside the 30..1 minute window should be collected
  once with the tolerance in place; until then CLV remains unavailable, and
  "unavailable" is the correct output — never zero.
- Last night's (`2026020183`) exact provider delta is unrecoverable: that report
  predates the delta fields and `commence_time` was never persisted.
- Tooling: running the suite rewrites `output/test_results/*.json` and two
  `output/<sport>/*.json` fixtures, dirtying the tree. Cosmetic, unfixed.
- Soccer and MLB prediction snapshots are not wired; only predicates that already
  pass `capture_prediction_odds` are archived.

Out of scope by policy: scheduler/daemon, hand-editing or inserting snapshots,
fabricated opening quotes, model/Kelly/threshold changes, pushing to any remote.

## Language

A capture is a **LAST OBSERVED PREMATCH** reference, not a closing price. One run
cannot prove a market close. Reports carry
`reference_label = "Last observed eligible prematch quote; not guaranteed sportsbook close"`;
do not drop it when quoting a number.
