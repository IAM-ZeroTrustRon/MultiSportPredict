# Full basketball and soccer package — implementation handoff

User-approved scope: implement the complete package below. Automatic odds are the default; manual inputs are optional overrides or an explicitly identified fallback. No further scope approval is needed. This document is an implementation plan, not a claim that these features already work.

## Required output

Basketball, every supported league including NBA, WNBA, NCAAB, NCAAW, EuroLeague, KBL, NZ NBL and German BBL:

| Period | Required markets |
|---|---|
| 1Q | Moneyline, spread, game total, home team total, away team total |
| 1H | Moneyline, spread, game total, home team total, away team total |
| FG | Moneyline, spread, game total, home team total, away team total |
| Players | Points, rebounds and assists; all evaluated priced candidates saved, significant candidates highlighted |

Soccer, including senior women's fixtures with separate team identities:

| Period | Required markets |
|---|---|
| 1H | Home/draw/away moneyline, Asian handicap, match goals, home goals, away goals |
| FG | Home/draw/away moneyline, Asian handicap, match goals, home goals, away goals |
| Corners | Match total, both team totals and corner handicap; 1H and FG supported when supplied by a source |
| Players | Anytime goalscorer for eligible roster players, including starter/substitute uncertainty |

Include every fetched alternative line for these markets. A market family must always appear in the report: a priced assessment, an explicitly labeled unpriced projection, or an exact missing-input request. Never omit a family silently. No fabricated prices, players, injuries, historical stats or EV. A missing-data row satisfies visibility only; it does not establish working prediction support.

## Current code entry points verified

- `run_basketball.py` delegates NBA/WNBA/college and some fixture runs to `run_ncaaf.main("basketball")`; other named international matches go through `euroleague_engine.run_cli`. Both paths need integration.
- `run_ncaaf.py` currently exposes manually priced moneyline/spread/total flags and optional `--odds`; the change must isolate basketball behavior so NCAAF is preserved.
- `score_odds.py` supplies score-runner odds; `live_odds.py` supplies the universal soccer runner and soccer batch. Use one normalization contract rather than conflicting provider routes.
- `models/score_ratings.py`, `models/basketball_predictor.py` and `euroleague_engine.py` contain scoring/segment models. `models/props_engine.py` contains legacy prop generation: audit and replace any invented line or roster fallback before integration.
- `models/soccer_predictor.py`, `extra_markets.py`, `universal_runner.py` and `run_soccer_batch.py` contain current soccer projections and display paths. Goal-derived xG proxies must remain labeled. The synthetic soccer shots artifact is not a validated anytime-scorer model.

## Implementation order and files

1. **Define a shared contract** in new `market_contract.py` and `market_registry.py`. Enumerate sport, period, family, participant and settlement rules. Normalize every quote with event ID, bookmaker, decimal price, line, selection, timestamp, source, regulation/overtime rule and status. Separate projection, priced evaluation and missing-input records. Store player IDs, gender and competition; do not match women's teams to men's records.
2. **Fetch all event markets automatically** in new `market_sources.py`; adapt `live_odds.py` and `score_odds.py` to it. Discover the actual event, fetch its available market catalog when supported, and request extended markets from the event endpoint. Batch compatible requests; cache by event/book/market, not merely league/day. Preserve provider response and quote time. Manual overrides apply only to matching event/period/family/participant/line; remaining markets still fetch automatically. Never combine opposing prices from different books into a paired de-vig calculation. Fallback adapters must declare real coverage and source provenance, not pretend another API's URL/schema is compatible.
3. **Refresh measured inputs** through `ingest_basketball_espn.py`, `ingest_basketball_official.py` and new `ingest_market_features.py`. Save regulation quarter/half scores, period possessions when available, box-score minutes/points/rebounds/assists, roster/injury updates and fixture start time. For soccer save half scores, measured match/team corners, player minutes, goals, penalties and measured xG when available. Preserve competition, season and senior men's/women's identity. Missing fields remain missing. Source URLs and retrieval times travel with every sample.
4. **Implement basketball periods** in new `models/basketball_period_markets.py`, integrating the existing score/EuroLeague models. Estimate Q1/H1 from actual league/team period history with shrinkage, sample counts and residual uncertainty. Model home and away scoring jointly so moneyline, margin, game total and team totals agree. Handle discrete tied periods according to the quoted book's two-way/draw-refund or three-way rules. FG overtime inclusion is explicit. League-specific duration and college halves are respected; do not fabricate a college Q1 settlement period. For leagues without quarters, display Q1 as structurally inapplicable and offer first-half markets.
5. **Implement basketball player props** in new `models/basketball_player_markets.py`. Project minutes with starter, injury, rotation and recent workload evidence; estimate opponent/pace-adjusted per-minute production. Fit and check a suitable count/overdispersed distribution using real game logs. Handle DNP/void rules and player ID ambiguity. Assess points, rebounds and assists for every eligible player with a fetched line. Significance uses configurable EV, uncertainty and minimum data criteria verified by chronological validation; it is not an arbitrary fixed probability threshold. Save all candidates and correlations, highlight qualifying ones. Unsupported player input produces a precise request rather than a fictional projection.
6. **Implement soccer periods/corners/scorers** in new `models/soccer_period_markets.py`, `models/soccer_corner_markets.py` and `models/soccer_scorer_markets.py`. Derive H1/FG score distributions from measured period history with opponent adjustment and shrinkage; label any prior. Calculate three-way results, goals totals/team totals and Asian handicaps from those distributions. Fit corner counts from measured corners, checking overdispersion and home/away dependence. Build scorer intensity from measured goal/xG production, expected minutes, penalty role and team goal projection. Integrate over start/minutes scenarios and enforce team-level scoring coherence. Estimate scoring probability from the intensity distribution rather than assuming certain 90-minute participation. Observe book-specific own-goal, substitution, extra-time and DNP settlement rules.
7. **Price and rank markets** in new `market_evaluation.py`. Calculate net return per unit stake with full/half wins, losses and refunds. Quarter handicaps/totals split the stake correctly. Calculate fair odds and proportional de-vig only with complete compatible opposing outcomes; label the method. No quote means no EV or value recommendation. Show uncertainty, sample size, freshness and calibration status beside recommendations. Correlated alternatives are flagged and do not become independent parlay legs. Missing data for one family must not crash otherwise valid markets.
8. **Wire both runners and output**: update `run_basketball.py`, basketball branch of `run_ncaaf.py`, `euroleague_engine.py`, `universal_runner.py` and `run_soccer_batch.py`. Add a direct soccer names runner `run_soccer_full.py`. Auto-fetch by default; retain explicit `--no-odds`, `--refresh`, `--markets-file`, `--no-store` and immutable saved-run `--push RUN_ID`. Follow existing storage schema after checking compatibility and backing up the DB; preserve separate market rows and selections for grading. Centralize readable rendering in new `full_market_report.py`: period table, significant props, then exact missing inputs. Save full JSON plus Markdown. Discord pushes the saved run and full report, not a recomputation or truncated single-moneyline card.
9. **Document and validate**: update `COMMANDS.md`, `STATE_OF_MODEL.md`, `INDEX.md` and applicable handoff docs. Preserve existing unrelated modifications and CRLF; back up touched files. Add targeted tests for source parsing, settlement, period/prop modeling, runner integration, storage and Discord artifact replay. Compile edited Python and run relevant existing regressions before live smoke checks.

## Provider integration reference

Verified documented Odds API keys to map (validate actual event/book availability rather than assume universal coverage):

```python
BASKETBALL_KEYS = {
    "FG": ["h2h", "spreads", "totals", "team_totals"],
    "1H": ["h2h_h1", "h2h_3_way_h1", "spreads_h1", "totals_h1", "team_totals_h1"],
    "1Q": ["h2h_q1", "h2h_3_way_q1", "spreads_q1", "totals_q1", "team_totals_q1"],
    "players": ["player_points", "player_rebounds", "player_assists"],
}
SOCCER_KEYS = {
    "FG": ["h2h", "spreads", "totals", "team_totals"],
    "1H": ["h2h_h1", "h2h_3_way_h1", "spreads_h1", "totals_h1", "team_totals_h1"],
    "corners": ["alternate_totals_corners", "alternate_team_totals_corners", "alternate_spreads_corners"],
    "players": ["player_goal_scorer_anytime"],
}
```

Also request documented alternate spread/total/team-total keys per period. Soccer 1H result adapters must preserve the draw outcome rather than treat a two-outcome response as three-way. No invented corner-half API keys: map a verified alternate provider's period quotes or display the exact required missing quote.

Reference: [official market catalog](https://the-odds-api.com/sports-odds-data/betting-markets.html) and [official event endpoint documentation](https://the-odds-api.com/liveapi/guides/v4/). These describe API capabilities, not proof of every league's availability. API credentials remain in `.env`, never errors or reports.

## Required user experience after implementation — proposed commands, not working yet

```bash
cd /c/MultiSportPredict
venv/Scripts/python.exe run_basketball.py --league "League" --match "Home Team vs Away Team"
venv/Scripts/python.exe run_soccer_full.py --league "League" --match "Home Team vs Away Team"
```

The runner prints its saved run ID and exact command:

```bash
venv/Scripts/python.exe run_basketball.py --push "Run ID"
venv/Scripts/python.exe run_soccer_full.py --push "Run ID"
```

No required price flags. When input cannot be obtained automatically, print an actionable list, e.g. `NEEDED: Home Team 1H team-total line, Over price, Under price; accepted through --markets-file PATH`. Generate a JSON template containing only missing entries with null values and field labels; never populate assumed -110 prices. Distinguish source errors, unavailable quotes, structural inapplicability and missing model features.

## Acceptance gates — evidence required before claiming complete

1. Both basketball dispatch paths produce all 15 period market families plus points/rebounds/assists evaluations. Soccer produces all 10 goals/result families, corner families and eligible scorer evaluations. Every family has an explicit status.
2. Live supported-league smoke runs show actual quotes and timestamps for period/team/player markets without manual price flags. Coverage tests include NBA, a verified international basketball fixture and soccer. KBL/NZNBL/BBL adapter gaps are named individually; do not mark these leagues complete based only on a US league success.
3. Missing-price/model-feature and structurally unavailable-period cases render exact requests/statuses; no invented EV. An unavailable provider does not silently erase a required section or stop unrelated markets.
4. Reversed home/away, same-name players, women's/men's identity, duplicate fixtures, stale quotes, postponed events and begun matches have regression tests. Pre-match analysis does not silently become in-play.
5. Known-result tests cover integer/quarter line settlement, Asian DNB, tied Q1/H1, three-way soccer draws, overtime, player DNP and voids. Probability masses and team/game total coherence are checked.
6. Chronological holdouts report calibration/Brier or log loss for result/prop probabilities, interval coverage, sample sizes, and separate period performance. Record uncertainty; never assert accurate probabilities from one successful example.
7. Saved JSON, terminal, Markdown, database rows and Discord artifact reference the same inputs/quotes/run ID. Pushing a saved run performs zero odds refresh or model recomputation.
8. Relevant regressions pass; no secret logging; no synthetic historical stats disguised as measured input. Commands are tested rather than documented ahead of implementation.

Execution instruction for Claude Code/ChatGPT: implement this plan end to end using /godmode within the already approved scope. Prefer one shared market pipeline with adapters over another independent sport-specific runner implementation. Report completed, tested features and remaining source coverage precisely. Do not call the entire package complete while a requested league or market only has a missing-data placeholder.
