# MultiSportPredict — State of Czech Liga Pro Engine

## 1. Engine Status & Operational Scope
- **Sport**: Table Tennis (Exclusively Czech Liga Pro).
- **Prohibited & Filtered Out**: Russian Liga Pro, Setka Cup, Czech TT Cup, TT Elite, WTT, and deceptive aliases.
- **Match Format**: Best-of-5 games (target 3 games won), 11 points per game (win by 2, deuce continuation to arbitrary depths).

## 2. Mathematical Framework
- **Scoring Engine**: Absorbing Markov chain point-state model (`models/table_tennis_scoring.py`).
  - Terminal boundaries: 11-0 through 11-9, 12-10, and deuce continuation ($P = p^2 / (p^2 + (1-p)^2)$).
  - Explicit joint distributions across Match Winner, Total Games, Game Handicap (-1.5 Games), and Total Points.
  - Distinct units enforced: Game Handicap vs Point Handicap.
  - Live conditioning: Preserves already completed games and points played in the active game.
- **Auxiliary Poisson Diagnostic**: Numerically stable implementation of Section 4 experimental Poisson function (`models/table_tennis_poisson.py`) used strictly as an auxiliary diagnostic tool; unconstrained Poisson is explicitly not used for legal terminal game scoring.
- **Top-Down & Hybrid Predictor**:
  - Proportional margin removal for same-book price pairs.
  - Hybrid calibration logit combining reference market, independent strength differential, shrunk residual H2H, rest, and workload.
  - Standalone bottom-up fallback when reference quotes are absent.
- **Odds & Alert Engine**:
  - Exact EV: $p \cdot d - 1$ for moneyline; push-aware EV for integer totals.
  - Staleness threshold and score-quote synchronization gates.

## 3. Test Coverage Summary
- **Tests Executed**: 24 tests across 7 test cases in `tests/test_table_tennis_comprehensive.py`.
- **Pass Rate**: 100% (24 passed, 0 failed, 0 errors).
- **Tested Modules**: Scoring rules, absorbing Markov chain deuce transitions, reversal symmetry, match probability resolution, live in-play conditioning, Poisson tail bounding, league scope validation, canonical player naming (Sr/Jr), H2H shrinkage, workload extraction, proportional de-vigging, EV calculation, and duplicate/correction reconciliation.
