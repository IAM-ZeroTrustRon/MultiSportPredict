# Edit plan — Debug missing soccer markets

## Information Gathered
- `predict_match.py` routes soccer to `run_soccer_game()` → `models/soccer_predictor.SoccerPredictor.predict()`.
- `SoccerPredictor.predict()` currently returns only:
  - `game` projected goals + win/draw probabilities
  - `predictions.side` (moneyline-style “side”)
  - `predictions.total` (over/under only using a single `market_total` input)
  - `predictions.btts` and goal/corner analyses
- `predict_match.py` does **not** fetch odds markets from TheOddsAPI for soccer in the soccer path.
- The Odds API client + event resolver exist in `predict_match.py`, so we can fetch markets for the resolved event and parse them.

## Plan
### File: `predict_match.py`
1. Add helper functions to:
   - call `OddsAPIClient.fetch_odds(event_id, markets=...)`
   - parse soccer event odds for:
     - Moneyline (H/D/A)
     - Double chance (1X, X2)
     - Team totals (Over/Under for each team; if the API returns asian/OU formats)
     - 1H totals (Over/Under first half; if available)
     - BTTS and match totals (over/under)
     - Corners totals (over/under; if available)
2. Normalize parsed odds into `soccer_result['market_odds']` (raw + normalized) and recommendations/edges into `soccer_result['predictions']` if needed.
3. Ensure parsing is robust: if a market is missing from the Odds API response, include the key with `None` and a `missing_reason`.
4. Update `_push_soccer_result_to_discord()` to pull values from the new normalized keys when present (while preserving existing fields).

## Dependent Files to be edited
- `models/soccer_predictor.py` only if we must adjust the output schema expectations (likely not required; we can layer odds on top).

## Followup Steps
- Run a smoke test: `python predict_match.py soccer Liverpool "Aston Villa" "Premier League"`.
- Verify output JSON contains:
  - `market_odds.moneyline`, `market_odds.double_chance`, `market_odds.team_totals`, `market_odds.first_half_totals`, `market_odds.total`, `market_odds.btts`, `market_odds.corners`.
- If Discord push used, verify no KeyErrors and message includes the new info.

<ask_followup_question>
Implementation approved—proceed to coding in `predict_match.py` only.
</ask_followup_question>

