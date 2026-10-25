# MultiSportPredict takeover audit — October 24, 2026

## Outcome and scope

Preserved Freebuff's uncommitted NHL, readiness, staking and report work, plus five
already-staged archive renames. Verified the local implementation and cached NHL
artifact. Repaired three reproduced correctness/workflow defects. Created the
comprehensive shared handoff and separate Gemini/Claude entry prompts.

No commits/pushes, Discord sends, new live picks, ledger grading/deletion, source
refresh, retraining or Google Drive/Notebook edits were performed. All production
tables compare exactly equal to the SQLite-consistent pre-repair backup. Tests
rewrote legacy sample output artifacts, as the existing suite normally does.

## Repairs

1. `core/market_handicapper.py`: power de-vig now brackets underround exponents
   below one and expands beyond ten for extreme overrounds. Input/convergence
   validation replaces silent incorrect fair probabilities. Reproduced old output
   for +120/+120: 0.454545 + 0.454545. Correct result: approximately 0.5 + 0.5.
2. `msp_workflow.py`: automatic --odds no longer collides with manual --moneyline,
   --spread or --total in basketball/NCAAF routing. Automatic runs request it once.
3. `grade_predictions.py`: shared recorded-price settlement validation applies to
   weighted and flat records. Weighted report separates missing stakes from
   invalid/assumed-price settlement exclusions, and retains pre-filter deduplication.
4. `tests/test_takeover_repairs.py`: 28 failure-oriented cases cover these repairs.
5. `COMMANDS.md`, `STATE_OF_MODEL.md`, `INDEX.md`: current routing and takeover notes.
   Existing dated handoffs received pointers; their historical content was retained.

Alternative considered: reject underround markets outright, keep direct-runner
workarounds, and leave weighted reporting separate. The selected repairs solve the
underlying math/routing/provenance problems in existing shared code without forking
an engine, loosening guards or fabricating historical data.

## Verification

| Check | Result |
|---|---|
| Baseline complete suite | 246 passed; 14 warnings; 9 subtests |
| Focused score/workflow/report/NHL regressions | 103 passed |
| Final complete suite | 274 passed; 14 warnings; 9 subtests |
| Compile all four new/edited Python files | Passed |
| git diff --check | Passed; existing CRLF conversion notices only |
| SQLite quick_check | OK |
| Compare every production table against backup | All identical |
| NHL cached schema/version/history hash | Matched |
| Real cached NHL forecast, no network/store | Correctly projection-only for unconfirmed goalies |

The warnings are legacy boolean-return tests, not new failures; those tests can
mask caught errors. Passing tests are not proof of accuracy, profitability, external
source availability or absence of malicious code. This was a targeted takeover
review, not an exhaustive repository/dependency/security audit.

## Key audit findings and corrected claims

- NHL implementation exists and has verified source/join/schema/settlement gates.
  4,136 cached fixtures / 2,968 finals / 2,959 advanced joins; 537 holdout games.
  Goal deviance 1.062471 vs 1.100603 baseline; winner Brier 0.237525 vs 0.248821.
  A prior claim that every metric improved over the previous fit was inaccurate:
  previous goal deviance 1.0605 was slightly better than 1.0625.
- Cached upcoming Chicago–Florida forecast (Oct 25) has sufficient game counts,
  but no confirmed starting goalies. It correctly exposes no EV/stake. This did
  not validate current external prices or automatically confirm either goalie.
- Optional goalie file checks user-entered identity/source/timestamps; no independent
  roster/starter verification or goalie-strength model is implemented.
- One original forward NHL event has a score; that is not enough for accuracy claims.
- All 889 prediction rows currently have NULL stake_size. The screenshot's weighted
  performance was a test example, not live Kelly results.
- Tennis calls shared moneyline pricing but does not persist stakes via its main
  storage path. Soccer, MLB and standalone basketball also lack full integration.
- Current all-time recorded-price subset: 243 selections, 114W/127L/2P,
  +18.2858 simulated flat units, +7.5250% ROI; 141 unknown-price settlements excluded.
  Ordinary selected settled count: 384 (183W/198L/3P). These are ledger records,
  not confirmed wagers; historical cleanup causes selection bias.
- Pending active ordinary selections: 29; pending TT runs: 18; TT grades: zero.
  Raw NULL-result counts include excluded rows and are not the actionable backlog.
- Current local HEAD: 18a5cab3ec8bcbc960e5467785d2bd068f8a15c5. Earlier chat SHAs
  differ. Remote alignment was not asserted and no changes were committed.

## Open work, intentionally not claimed complete

Soccer fixture date/orientation/accent/unknown-league fixes; consistent priced BTTS;
Belgium/Sweden/Norway/Estonia integration; actual tennis missing-odds diagnosis;
remaining staking persistence and portfolio exposure; independent goalie verification
and validated goalie features; period-specific NBA models; table-tennis source/ID
coverage; old boolean-return tests; synthetic soccer shots-prop training; stale
architecture documents and unsafe cleanup keep-set. See the shared handoff for
file-level detail and ordered next steps. No old deletion authorization was reused.

## Evidence and recovery

`output/takeover_audit/20261025T035246Z/` contains:
- `history_before.sqlite`
- `before/` exact prior file copies
- `working_tree_before.txt`
- `audit_snapshot.json` (including pending IDs and NHL metadata)
- `verification.json`

This folder is local/ignored. Preserve it separately when migrating computers.
Restore individual pre-repair files selectively; do not discard unrelated changes
or replace a later live database with an older snapshot casually.

## Handoffs

- `docs/AI_HANDOFF.md`: comprehensive authoritative shared state and limitations.
- `docs/GEMINI_START_HERE.md`: Gemini prompt; attach shared handoff in Notebook.
- `docs/CLAUDE_START_HERE.md`: Claude prompt; same shared source of truth.

These local documents do not auto-sync external chats or Google Drive. An agent
without file access must receive attachments and must not claim local inspection.
