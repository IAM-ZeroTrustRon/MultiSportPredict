Current local implementation — 2026-10-10: Gemini's ZIP was audited and kept separate. A replacement Czech-only engine is now installed in `table_tennis/`, with `ingest_table_tennis.py`, `train_table_tennis.py`, `run_table_tennis.py` and `grade_table_tennis.py`. The original proposed architecture below is historical; actual commands and limitations are in `README_CZECH_LIGA_PRO.md` and `COMMANDS.md`. Collection still needs a supported provider token; no example data was imported for training.

# Czech Liga Pro: live data, top-down pricing, H2H and prediction engine

Research date: October 9, 2026. Workspace: `C:\MultiSportPredict`.

## Objective and boundaries

Build a Czech Liga Pro TABLE TENNIS engine only. Train, calibrate, predict and grade exclusively verified Czech Liga Pro events. Do not import Russian Liga Pro, Setka Cup, Czech TT Cup, TT Elite or WTT results. Repeated matches between the same players require event IDs and scheduled times, not name-only matching.

The desired strategy is top-down market pricing combined with H2H trends and independently measured player strength/form/workload. The deliverable is a names-only prediction run with automatic data/quotes, a readable complete market report and a separate saved-run Discord push. This document is a researched implementation handoff. No live collector, authenticated feed, alert service or production prediction engine has been installed or tested here.

## 1. Recommended collection methods and researched source candidates

Choose providers by recorded evidence, not marketing claims. Prefer an authenticated documented feed for production; use browser discovery to understand a named site's permitted responses when a documented feed is unavailable. A stream transports updates quickly but cannot undo upstream delay.

| Candidate | Evidence checked | Recommended role | What remains unverified |
|---|---|---|---|
| Odds-API.io + its OddsHub product | An indexed Czech Liga Pro historical event lists three books, a completed 3–1 result and prices. Vendor documents REST snapshots and WebSocket odds integration. | First odds-stream trial candidate; compare books and archive quotes. | Account-level Czech coverage today, live markets, underlying update delay, point scores/server identity and historical depth. |
| BetsAPI | Published authenticated REST documentation with rate-limit headers. A Czech league page candidate exists at `/l/22742/Czech-Liga-Pro`, but this research fetch returned 403. | Trial for fixtures, completed game scores and H2H history; possibly live state/odds depending on package. | League ID/country validation through actual account response, point-by-point/server fields, licensed books, timestamps and historical access. Do not treat 22742 as a verified production ID. |
| Stake Czech Liga Pro page | Primary sportsbook page lists the league, prices and suspended selections. The retrieved live-looking content was dated October 6, not the research date. | Named-site comparison/discovery candidate if this is the user's book; useful for checking market semantics. | Authenticated October 9 payload, permission/terms, response schema, score-to-quote synchronization and stable automation access. The cached page is not live evidence. |
| ParlayAPI | Vendor changelog advertises table-tennis/Bovada coverage including Czech Liga Pro and a REST odds endpoint. | Secondary odds candidate to trial. | Current Czech event coverage, score granularity, latency and bookmaker independence; changelog claims are not a measured guarantee. |
| tabletennis-api.com | Coverage page advertises Czech Liga Pro; API documentation explicitly calls hosts, paths, protocol and examples placeholders. | Do NOT use as an implementation-ready adapter. | Production specification, sample payload, authentication and all coverage. |

Sources: [OddsHub Czech event](https://www.oddshub.io/table-tennis/czech-republic-czech-liga-pro/73881106), [Odds-API.io integration](https://odds-api.io/blog/sportsbook-api-integration), [BetsAPI documentation](https://betsapi.com/docs/), [BetsAPI candidate league](https://betsapi.com/l/22742/Czech-Liga-Pro), [Stake league page](https://stake.com/sports/table-tennis/czech-republic/czech-liga-pro), [ParlayAPI changelog](https://parlay-api.com/changelog), [draft table-tennis API documentation](https://tabletennis-api.com/api-documentation/).

No authenticated subscriptions were tested, bought or recommended as definitively best. No organizer-owned results feed was verified. Vendor choice requires a coverage/latency trial before spending money or claiming automatic live recommendations.

### Transport hierarchy

1. Documented REST for event discovery, history, initial state and reconnect reconciliation; documented WebSocket/SSE for live updates where available.
2. Controlled polling of documented/public JSON responses, with session reuse, provider quotas, cache validators and backoff. HTTP is useful; BeautifulSoup is suitable for static pages, not streaming frames.
3. For a user-selected site, Playwright response/WebSocket observation inside an ordinary authorized browser session. Record sanitized payload shapes, IDs and timing. DOM extraction is a last resort for low-frequency display fields.
4. Do not invent hidden endpoints or replay a guessed WebSocket URL. Inspect the actual connection handshake, subscription frames, heartbeat and session requirements. Browser WebSockets use TLS normally; TLS encryption alone is not a reason to switch methods.

Playwright Python event hooks are `page.on("response", ...)` and `page.on("websocket", ...)`, followed by socket `framereceived`/`framesent` listeners. `route.on('response', ...)` is not the documented API. Register listeners before navigating. See [Playwright Python network documentation](https://playwright.dev/python/docs/network). A login script needs a named URL and user's authenticated session; credentials do not go in code, logs or the report. Do not route around CAPTCHA/access rejection. The first task is discovery, not automatic wagering.

### Feed evaluation protocol

- Capture real payloads for Czech Liga Pro fixtures, completed matches and at least two concurrently priced books if top-down comparison is intended.
- Verify player IDs, league/country mapping, repeated same-pair matches, best-of format, game scores, point scores, server, odds units, market suspension and retirement/void behavior.
- Record provider event time, quote update time, UTC receipt time and monotonic processing time. Distinguish interarrival interval from measured delivery lag; unknown provider timestamps cannot establish latency.
- Compare identical live score states across sources. Measure completeness, duplicates, corrections, missing game scores, stalls, reconnection recovery and observed stale quotes. Assess peak and quiet sessions.
- Live-point support requires actual point state, synchronized prices and observed update performance. If only game/match results exist, deliver pre-match/game-break analysis, not fictional point-live precision.
- Derive freshness budgets from measured feed behavior and match pace. Persist limits as configuration. No unverified fixed 30–45-second bookmaker lag or guaranteed millisecond advantage.

## 2. Review of the supplied proposals

| Supplied claim/code | Finding and correction |
|---|---|
| Top-down is arguably the most profitable method | Unverified. Evaluate a market-only baseline against independent and hybrid models on this league. |
| Pinnacle is the true probability anchor | Neither Czech Liga Pro coverage nor suitability was verified. A de-vigged reference is an estimate; select actually observed reference books and measure reliability. |
| Retail quotes lag 30–45 seconds; stale lines guarantee EV | Unsupported fixed delay and guarantee. Quotes may be suspended, rejected or based on a different score state. Measure synchronization and feasible execution. |
| DR above 1.10 identifies elite players | No Czech-specific validated threshold. DR needs real service/return labels and enough observations; absent fields remain unavailable. |
| Grip/rubber/handedness creates a fixed rating modifier | Direction and magnitude are not established. Use verified features and fit effects chronologically; no manually invented Elo bonus. |
| HTTP/BeautifulSoup are useless and instantly blocked | False generalization. Static parsing and REST/polling remain useful; provider behavior/rate limits determine access. |
| Mock WebSocket loop is production-ready | It yields invented packets, makes no connection and has no real state validation. The shown `wss://://...` URL is malformed. |
| Independent Poisson scores predict exact final games | Incorrect for stopped, win-by-two scoring. The grid allows unfinished, tied and impossible terminal scores. Normalizing a 0..15 grid hides deuce tail mass. |
| Totals helper puts equality in Over | Wrong for integer total lines with refund settlement. Equality must be a push where book rules specify it. |
| Live score automatically changes prediction | Supplied pipeline prints the score but does not condition its distribution on that score; lambdas come from mock packets. |
| Fair odds at probability 0/1 are +0 | Invalid representation. Return undefined/infinite fair odds and an explicit status. |

The first pasted example's dollar EV arithmetic is consistent with a $100 stake for ordinary valid American odds, but its probability estimates and arbitrary edge trigger are unvalidated. It does not implement a real top-down reference or calibrated H2H model. `base_k_factor` is unused; the tactical modifier's positive sign reduces A's probability. Neither pasted script is a production baseline.

## 3. Top-down + H2H design

For a two-outcome book with decimal prices `d_A`, `d_B`:

```text
q_A = 1 / d_A; q_B = 1 / d_B
p_market_A = q_A / (q_A + q_B)
```

This removes margin proportionally from a complete same-book pair. Other de-vig methods can be compared. Do not combine opposite sides from different books into a supposed single-book market. Do not select the target execution quote as the only independent reference. Multiple vendors copying the same source are not independent confirmations. Exchange commissions and quoted liquidity need explicit accounting.

### H2H features

- Match win fraction, games won/lost and point margin per game; dates and sample counts always shown.
- Recency-weighted meetings, same-session rematches, first-game result and point-total distribution.
- Shrink small H2H samples toward an independent strength-based prediction. For a candidate baseline `p_base`, weights `w_i`, and A outcomes `y_i`, use `(sum(w_i*y_i) + strength*p_base)/(sum(w_i)+strength)`. Tune prior strength using earlier data only.
- Distinguish weighted sample sum from independent information. Repeated meetings on one day are correlated; report distinct sessions/days and cluster validation accordingly.
- Prefer residual H2H features: actual outcomes minus the prior strength/market expectation available at each historical meeting. Do not count the same result as three independent signals through Elo, form and H2H.
- Rest and workload use completed earlier matches only: matches/games/points played, elapsed rest and session order. Timestamp corrections must not retroactively become known features in a backtest.

### Hybrid calibration

Fit, rather than assume, a model such as:

```text
logit(p_final) = intercept
              + beta_market * logit(p_reference)
              + beta_strength * strength_difference
              + beta_h2h * shrunk_h2h_residual
              + beta_rest * rest_difference
              + beta_load * workload_difference
```

Regularize and validate chronologically. In-play calibration must condition on game/point state and time-aligned reference quotes. Compare market-only, strength-only, H2H-only and hybrid ablations. If H2H does not improve held-out calibration, keep it as an observation panel rather than probability adjustment. Missing reference odds should produce a separately trained/validated bottom-up fallback, not silently fill the market feature with zero.

## 4. Poisson function — requested, but experimental

Include this numerically stable count-distribution utility. It exposes omitted tail mass and validates inputs. It is not an exact table-tennis final-score distribution.

```python
import math

def poisson_distribution(rate: float, tolerance: float = 1e-10,
                         max_count: int = 10000) -> dict:
    if not math.isfinite(rate) or rate < 0:
        raise ValueError("rate must be finite and nonnegative")
    if not math.isfinite(tolerance) or not 0 < tolerance < 1:
        raise ValueError("tolerance must be between zero and one")
    if isinstance(max_count, bool) or not isinstance(max_count, int) or max_count < 0:
        raise ValueError("max_count must be a nonnegative integer")
    probabilities = []
    mass = 0.0
    for count in range(max_count + 1):
        probability = (1.0 if count == 0 else 0.0) if rate == 0 else math.exp(
            count * math.log(rate) - rate - math.lgamma(count + 1)
        )
        probabilities.append(probability)
        mass = math.fsum(probabilities)
        if count >= rate and mass >= 1 - tolerance:
            return {"probabilities": probabilities,
                    "tail_mass": max(0.0, 1 - mass)}
    raise ValueError("Increase max_count; tail tolerance was not reached")
```

Use Poisson initially as an auxiliary count-model diagnostic (e.g. completed-game losing-point counts), compared with empirical and overdispersed alternatives. Even losing-point counts have rule-dependent support, so unrestricted Poisson is not sufficient for scoring markets. Fit any conditional/truncated count model with its appropriate likelihood, not by assuming the raw sample mean remains the fitted truncated rate. No fitted rates or example predictions are supplied here.

### Main scoring model

Use an absorbing point-state model or rule-faithful simulation, trained on Czech data:

- State: games won, current game score, game number, server/serve phase when known, and observed match format.
- A game ends on a legal terminal state: at least 11 points and a lead of at least two; stop immediately when reached. Handle deuce beyond 15, not a fixed cap normalized away.
- Serve sequence follows verified rules. If first server is unknown, integrate over that uncertainty; do not fabricate service labels. Adjust for any verified event-specific rule exceptions.
- With constant independent point probability `p` and no service effect, deuce win probability is `p**2 / (p**2 + (1-p)**2)`. This is a simplified baseline; service-specific transitions need their own state treatment.
- Live predictions start from the actual current game and match state, preserving points already played. Never restart the game at 0–0.
- Produce joint distributions for match winner, games played, game margin, points played and point margin. Sum actual played-game totals for match markets; do not add unplayed games.
- Integrate uncertainty over player strength, point rates and workload effects. Validate point-market performance separately from match moneyline.

Stake describes this league as best-of-five games, but event metadata must confirm the actual format. [Bookmaker league description](https://stake.com/sports/table-tennis/czech-republic/czech-liga-pro). General rules reference: [ITTF laws](https://documents.ittf.sport/sites/default/files/public/2022-02/ITTF_HB_2022_tc_v1_0.pdf).

## 5. Collection/state architecture

```text
Verified Czech league IDs + player/event mapping
  -> REST snapshot/history + live stream or measured polling
  -> raw timestamped archive
  -> validation, deduplication, corrections and state reconciliation
  -> features known at prediction time + synchronized quote pairs
  -> market-only baseline / H2H hybrid / scoring distributions
  -> settlement-aware pricing and uncertainty
  -> saved readable report + optional alert + saved-run Discord push
```

Persist UTC; display user time in America/New_York. Workload/session features use the verified event venue timezone, not assumed US days. Track scheduled time, actual start/end when known, receipt time and effective correction time separately.

Every normalized event needs: canonical/provider IDs, exact league ID/name, country, stable player IDs/names, start time, status, format, completed game scores, live game points if available, server if available, source time, receipt time and provenance. Every quote needs event/book/market/unit/period/selection/line/price/status/time/associated-score-state. A -1.5 spread must explicitly distinguish GAME handicap from POINT handicap; the numeric line alone is insufficient.

Duplicates are idempotent. A correction is retained as a new version, not silently overwritten. Reconnect loads a fresh snapshot before recomputing; suspended/removed quotes become unavailable. Do not keep obsolete prices alive by blindly merging update payloads.

## 6. EV, alerts and output

For no-push moneyline, `EV = p*d - 1`, where `d` is executable decimal odds. For refund/quarter markets compute expected winning stake times `(d-1)` minus expected losing stake. Calculate fair prices and confidence intervals from the actual outcome distribution. No price means projection only, no EV.

Each alert must include event/player IDs, exact market/unit/line, book, target price, reference time/state, model probability, estimated EV, uncertainty, freshness and sample counts. Deduplicate by event/market/selection/line and materially changed price. If score/quote is stale, suspended or mismatched: suppress betting alert and show a data-status message. User-authorized alert delivery is separate from automatic betting; this task does not authorize wagers.

Report required market families: match ML; individual-game winner; match/game POINT totals and POINT handicaps; match total GAMES and GAME handicaps; player point totals where quoted and modeled; exact game/match score distribution as research when valid. Always show unsupported families with exact missing inputs. Display top-down, bottom-up and hybrid probability separately, H2H observations with sample sizes, and the case against the recommendation.

## 7. Repository integration and implementation sequence

Before editing: inspect actual current code and all callers; preserve unrelated Cline/Codex modifications. Do not reuse ATP synthetic seeds or surface ratings. Existing `market_contract.py`, `market_evaluation.py`, `market_registry.py` and `core/market_handicapper.py` are integration candidates, not assumed correct for new table-tennis units/settlements. Review their behavior first.

1. Add `table_tennis/provider_discovery.py`: coverage probe and captured-sample manifest; exact Czech-only IDs.
2. Add `table_tennis/sources.py`: authenticated provider adapters and optional named-site Playwright discovery. Separate provider environment keys; never point the existing Odds API token at a different vendor.
3. Add `ingest_table_tennis.py`: history ingestion and live collector, league filtering, raw archive, canonical player mapping and correction history.
4. Add `models/table_tennis_features.py`, `models/table_tennis_predictor.py`, `models/table_tennis_scoring.py`: chronology-safe features, H2H shrinkage, calibrated hybrid and legal scoring.
5. Add `models/table_tennis_poisson.py`: the auxiliary utility above plus comparative diagnostics; clearly experimental, not the default exact-score engine.
6. Extend market registry/contract only as required for distinct game/point units and settlements. Add tests before routing into shared evaluation.
7. Add `run_table_tennis.py`: auto-fetch default, repeatable names, optional exact event ID, pre-match/live state, override file, saved-run review and Discord push. Reject ambiguous repeated fixtures.
8. Add optional `table_tennis/alerts.py`: synchronization/freshness checks, signal deduplication and user-enabled delivery. Build after successful capture/replay, not before verified data.
9. Add historical grader and chronological evaluation; use the project's canonical database if predictions are stored, with backup/migration tests. Separate raw archives are not a second prediction DB.
10. Update `COMMANDS.md`, `STATE_OF_MODEL.md`, `INDEX.md`, tests and handoff docs with actual tested commands. No live-price flag requirement; manual entries are fallback overrides only.

Proposed commands ONLY — not available yet:

```bash
cd /c/MultiSportPredict
venv/Scripts/python.exe ingest_table_tennis.py --stats
venv/Scripts/python.exe ingest_table_tennis.py --days 30 --no-quotes --auto-train
venv/Scripts/python.exe ingest_table_tennis.py --days 1 --watch --auto-train
venv/Scripts/python.exe run_table_tennis.py --match "First Player vs Second Player"
venv/Scripts/python.exe run_table_tennis.py --event-id "Event ID" --live
venv/Scripts/python.exe run_table_tennis.py --push "Saved Run ID"
```

## 8. Acceptance tests and evidence

- Coverage proof: authenticated real Czech event, both players, legal game scores and actual quote payload; every unavailable field explicitly recorded. Reject all other leagues, including deceptive Liga Pro aliases.
- Parser/replay tests: duplicate frames, reversed players, same names/Sr/Jr, same-day rematches, out-of-order events, corrected scores, suspended/deleted markets, malformed frames and reconnects.
- Scoring tests: terminal 11–0 and 11–9; nonterminal 10–10/11–10; terminal 12–10; deuce continuation beyond 15; settled current state; legal best-of termination. Independent Poisson final-score grid must not be used to pass these tests.
- Distribution tests: normalization plus explicitly bounded tail; score/player reversal symmetry; all probabilities in [0,1]; integer totals pushes; points versus games units; retirement/void rules; zero rates and invalid Poisson inputs.
- Chronological, session-clustered holdouts: market-only vs independent vs hybrid; H2H ablation; calibration/Brier/log loss, point-total interval coverage and bootstrap uncertainty. Include price availability and feasible delays; no closing-line look-ahead or random-row cross-validation leakage.
- Shadow collection/recommendations before betting use. Report observed update lag and quote rejection/staleness assumptions; profitability claims need out-of-sample evidence and execution costs.
- End-to-end snapshots: report, JSON, stored selection and Discord card refer to the same run/state. Push performs no recomputation. Missing family never disappears silently. No invented source data, fake demo players or secret logging.

## 9. What Gemini needs next

The exact sportsbook/site the user bets at; one chosen provider's working account access or documented permitted public feed; real sanitized Czech sample payloads covering fixtures, history, live state and prices. Do not ask the user to paste passwords/tokens into chat. Configure keys locally in `.env` or use a user-authenticated browser session. Build the source probe first, then select the working adapter; no source subscription has been selected or purchased.

Gemini instruction: implement this Czech-only plan within the already requested scope; do not expand leagues or unrelated engines. Correct the supplied mock/Poisson assumptions rather than preserve misleading production claims. Start with verified data and replay fixtures, then build the scoring/market/H2H pipeline, then alerts. Report exact supported markets and source gaps, with tests and copy-paste Git Bash commands. Do not claim scraping URLs, live latency or automated odds work until a real run proves them.
