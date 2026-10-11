# Czech Liga Pro package review

Downloaded from the user's Google Drive link and extracted into `output/table_tennis_package_audit/gemini`. The original ZIP is retained beside this report. Production modules and shared command documentation were not replaced.

## Verdict

Do not deploy this archive as the finished automatic betting engine. Its supplied 24 unit tests pass (independently reproduced: 24 tests, 0.015 seconds), but important implementation requirements are absent. Eight independent acceptance probes fail; see `audit_results.json` and `audit_probes.py`. These probes check expected behavior, including two adapter implementation checks whose empty returns were also confirmed by reading the source.

## Confirmed problems

1. **Automatic feeds are stubs.** Both adapters in `table_tennis/sources.py` return empty fixtures/results even with a configured key. No HTTP request is implemented. The runner reads bundled JSON samples rather than current sportsbook prices. Providing credentials alone will not fix this.
2. **Scoring distribution is incorrect.** In `models/table_tennis_scoring.py`, the pre-deuce combinatorial coefficient must be `comb(10+k,k)`, not `comb(9+k,k)`. Deuce scores must progress 12-10, 13-11, 14-12; the code skips every other score. Renormalization hides missing probability. At point probability 0.5, 11-1 should have probability 0.002685546875; the package returns 0.003610552681. A legal 13-11 result has probability 0.0220246315, but the package assigns zero.
3. **Live expected points are incorrect.** At 11-10 with A point probability 0.6, expected remaining points are `1 + 0.4 * 2/(0.6²+0.4²)` = 2.538461538; the code returns 2.846153846. Match total expected points also counts an extra neutral game at a pre-match 0-0 state: the current game is already included in expected games but is added separately. Live point margins must preserve the observed completed and current point margin, rather than multiply all played points by the future point advantage.
4. **Quotes can be assigned to the wrong player or event.** Reversing names does not reverse prices. An explicit different event ID still resolves by names. There is no scheduled-time, finished-event or quote-age check in this resolution path. Same-day repeat matches require distinct verified event IDs.
5. **Unknown players silently receive rating 750.** Partial name matching also risks generation collisions. Report unavailable observations explicitly; any statistical prior must be labeled and must not produce an actionable recommendation without validated coverage.
6. **H2H and fatigue are not connected to real history.** The runner passes an empty history and empty workload records. The hybrid coefficients are hand-selected defaults, not a fitted or independently calibrated model. Do not call these probabilities calibrated or imply populated H2H analysis.
7. **Discord does not send.** `--push` prints embed JSON. It also substitutes odds 1.85 when missing and chooses the higher win-probability side rather than the best eligible EV. Integrate the repository's real Discord sender, using the immutable saved recommendations without invented prices.
8. **Required markets are incomplete.** Point totals and point handicaps have expected values but no outcome distributions, priced lines, push probabilities or EV. Game markets are hardcoded to a few lines. Bundled alternative quotes are stored but not evaluated. This is not a full market handicap.
9. **Live streaming is absent.** `--live` is declared but unused. Manual scores are not a live feed. Distinguish pre-match market anchors from in-play quotes to avoid conditioning an already live probability a second time.
10. **Storage and ingestion need hardening.** Event IDs can become filesystem paths; constrain them. Runs overwrite the same event file. Ingested events live only in memory; status/odds-only changes are ignored as duplicates. Missing IDs become string `None`, bypassing the intended check. Validate legal scores, odd best-of values, player identity, timestamps and state consistency.
11. **Provenance remains unverified.** Odds sample JSON lacks exact source URLs/raw captures. The supplied tournament URL could not be retrieved through the web tool in this review; that does not prove the records false, but does not verify them either. Keep bundled examples out of live execution. Browser capture code also needs credential redaction before archiving URLs and frames.
12. **The ZIP overwrites shared files if installed wholesale.** It includes `COMMANDS.md`, `STATE_OF_MODEL.md`, package initializers, and canned saved runs. Integrate individual files and merge documentation deliberately.

## Concrete handoff to Gemini

Repair the package against the original `CZECH_LIGA_PRO_GEMINI_HANDOFF.md` and the failures above. Preserve Czech Liga Pro only. Implement actual documented provider requests and durable history/quote ingestion first; verify league identity and availability with real captured responses. Never substitute archived sample quotes for current prices. Record source URL, provider event ID, event start, bookmaker, market, line, selection orientation and quote timestamp. Keep reference market and execution quote provenance explicit.

Correct the legal point-state model and add independent analytical fixtures for exact score probabilities, deuce tail accounting, pre-match expected match points and preservation of live played points. Build distributions for supported game/point totals and handicaps, including integer pushes, before producing EV. Document unavailable markets instead of fabricating prices. Estimate and validate model weights chronologically on real pre-event data; label the model experimental until that validation exists.

Use verified player IDs and exact event matching, reject ambiguity, enforce quote freshness and event status, persist ingestion across restarts, and create immutable unique run IDs. Wire the existing Discord sender and test it with a mocked transport before any real send. Merge only the new sport files into MultiSportPredict; do not replace shared initializers or documentation wholesale.

Acceptance evidence must include: recorded real adapter responses with secrets redacted; two same-day matches involving the same pair resolved separately; reversed selection checks for every market; restart/correction tests; stale quote suppression; complete priced-market settlement and EV checks; independent scoring oracles; and a names-only end-to-end test using a mocked provider plus a separate real provider smoke test. A passing suite of normalization assertions is insufficient.

## Reproduce locally in Git Bash

These commands operate only inside the audit extraction:

```bash
cd /c/MultiSportPredict/output/table_tennis_package_audit/gemini
/c/MultiSportPredict/venv/Scripts/python.exe -m unittest -v tests.test_table_tennis_comprehensive
cd /c/MultiSportPredict
venv/Scripts/python.exe output/table_tennis_package_audit/audit_probes.py
```

No betting prediction or Discord message was sent during this review.
