# Repository review — October 19, 2026

Reviewed the local checkout against fetched `origin/main` at `08c06ce`. This report describes changes prepared against that baseline, including existing local changes. Publication details are recorded in the repository commit history. The Python inventory contains 441 tracked paths; the targeted AST scan excluded archived and output copies, found no parse errors in scanned files, and identified the serialized-model and shell-execution candidates below. This is a targeted engineering review, not a penetration test or certification that malicious code is absent. Dependencies and complete Git history were not independently audited.

## Improvements implemented

- **One supported workflow:** `msp.py` delegates to sport-specific engines, accepts mixed JSON slates, verifies that a forecast was saved, records immutable run snapshots, and separates delivery from generation. Sending a saved result preserves the complete forecast and never reruns the model.
- **Fixture integrity:** NFL uses Eastern dates and unique event identity, rejects previous-season fallback and started/completed fixtures, and repairs historical dates only against a unique compatible schedule event. Soccer's explicit date reaches its fixture check and stored result. Dated single-game baseball runs retain their date instead of switching to a slate.
- **Grading:** KBO uses a completed-score adapter and the actual `start` date parameter on its source's game index. A verified tied NFL two-way moneyline pushes. A soccer draw continues through the full settlement return contract. Resolved records preserve recorded prices where available.
- **Source recovery:** MLB player ingestion now uses official MLB season statistics plus measured Baseball Savant wOBA, joined by player ID. Both importers share the same output schema. Fractional innings derive from outs, and ambiguous player names are omitted with a coverage note. The October load produced 649 pitchers and 532 hitters; the name `Max Muncy` was excluded because the current consumer resolves names rather than IDs.
- **Soccer reliability:** temporary transport and server failures have bounded retries; HTTP 403 is not retried as an access workaround. France recovered 36 teams. Existing goal-derived xG estimates retain their Tier 2 label.
- **Recoverable cleanup:** integrity-checked SQLite backups and an exact deleted-record manifest precede deletion. Settled records and active/future events are protected. The new reporting period starts October 20; settled history remains queryable.
- **Legacy repair:** the team-stats helper no longer contains an accidentally copied CLI dispatch block referencing undefined `args` during basketball lookup.
- **Documentation:** root command guides, the separate engine compatibility guide, Google Drive guides and README now lead with the same supported interface. The README describes value handicapping and explicitly limits performance claims.

## Remaining priorities

### P1 — A clean historical record is not a complete prospective record

The cleanup removed unresolved outcomes. Therefore the retained record has missing-outcome/selection bias even though removed rows were backed up. [The performance disclosure](PERFORMANCE_2026-10-19.md) makes that limitation explicit. Keep future issued recommendations immutable, archive exclusions with reasons, capture original prices and track closing prices before treating a result as evidence of a durable edge. A delivery receipt is not a placed wager.

### P1 — Legacy/advanced simulations still use assumptions

[predict_mlb_advanced.py](../predict_mlb_advanced.py) retains fixed plate-appearance and bullpen assumptions and default inputs. [kbo_scraper.py](../kbo_scraper.py) can substitute league-average statistics after a fetch fails. These paths do not support a blanket repository-wide claim that every output is fully sourced or independently calibrated. The new README removes that claim. Next work should distinguish declared simulation assumptions from unavailable required inputs and add scenario/holdout evidence before pricing those outputs as betting edges.

### P1 — Some older tests can conceal failures

Examples in [test_modular_system.py](../tests/test_modular_system.py) and [test_soccer_resolver.py](../tests/test_soccer_resolver.py) return booleans; some catch exceptions and return `False`. Pytest warns instead of treating a returned `False` as a failed assertion. The current suite's 14 warnings must not be described as a warning-free or exhaustive validation of every model. Replace return-based checks and swallowed failures with real assertions and explicit expected exceptions.

### P2 — Serialized models require a trust boundary

`pickle.load` remains in [base_predictor.py](../base_predictor.py), [mlb_module.py](../mlb/mlb_module.py) and [soccer_shots_prop_model.py](../models/soccer_shots_prop_model.py). Loading an attacker-controlled pickle can execute code. These calls alone are not evidence of a backdoor. Restrict model provenance/paths, verify trusted artifacts and consider a safer format appropriate to the model. The current review did not verify an externally exploitable upload path.

### P2 — A legacy scraper builds a shell command

[kbo_scraper.py](../kbo_scraper.py) calls `subprocess.run(cmd, shell=True)` with interpolated arguments. Shell metacharacters in untrusted values could change command execution. Replace it with an argument list and `shell=False`; retire the wrapper if the shared workflow fully supersedes its use. The new workflow itself invokes children with argument lists and rejects forwarded delivery/guard-bypass flags.

### P2 — Table-tennis result coverage is incomplete

The current public browser collector reports **no readable Czech Liga Pro recent-results page**. It does not establish complete point-score history or an identity bridge between MyStake and public provider events. The hourly grader retries available sources; it cannot promise every market will settle without verified point data. Do not infer point totals or merge similarly named players to clear a backlog.

### P2 — Market/fixture coverage remains uneven

Challenger research can fail player identification; international basketball metrics do not provide the same verified schedules and prices as score-based leagues. Guard and source coverage should be audited per route. The shared CLI intentionally does not advertise a universal guard or universal price feed. Football-data files now expose some match xG columns; adopting measured xG would require separate coverage/provenance validation rather than relabeling goal-derived values.

### P3 — Reproducibility and repository packaging

Dependencies are broad minimum versions rather than a tested lockfile. Runtime artifacts, archived runners and duplicate engine copies make the tree harder to navigate. Current workflow logs/backups are now ignored; already tracked historical artifacts remain. Next cleanup should inventory actual callers, retain compatibility entrypoints, and remove dead copies only after ownership and tests are clear. Add a deliberate license file before repeating the old README's unsupported MIT license claim.

## Validation evidence

- Full test suite: **173 passed**, with **14 existing warnings** and **9 subtests passed**. Delivery tests use mocks; no Discord messages were sent.
- Verified KBO final: KIA 5–LG 1 on October 17, parsed from the dated source scoreboard; the stored OVER 9.5 selection lost.
- NFL recovery added 30 verified grades and the KBO final added one. The supplied Machac–Muller winner claim conflicted with source evidence and was not imported as a win.
- MLB official-source load and France recovery succeeded. Other completed refresh stages include tennis, NFL schedule/stats, NCAAF results/model history, NBA/WNBA/NCAAB/NCAAW schedules, KBL/NZNBL/BBL and EuroLeague. Public table-tennis refresh failed visibly.
- Historical cleanup: 47 unresolved ordinary rows and 18 table-tennis runs removed after verified backup. Two active ordinary selections plus two excluded reruns for tonight's in-progress NFL fixture were retained.
- SQLite integrity checked after cleanup. Saved historical and fresh-period figures are in [the fixed performance snapshot](PERFORMANCE_2026-10-19.md).

## Design choice

A shared orchestration layer was chosen over merging every sport into a single prediction engine. It removes command friction while preserving the models' different inputs, pricing rules and validation requirements.
