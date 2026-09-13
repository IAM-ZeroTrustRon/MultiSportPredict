# TODO - MultiSportPredict Improvements

## Completed
- (none yet)

## In Progress
- [ ] Step 1: Refactor MLB-only prop runner into generic baseball prop runner supporting KBO
  - [ ] Update NRFI base probability for KBO to ~0.47
  - [ ] Update run_baseball_game to run prop markets for KBO when --markets is provided

- [ ] Step 3: Fix broken Euro basketball CLI argument pipeline
  - [ ] Add argparse flags: --market-line, --current-line, --open-line to predict_match.py
  - [ ] Pass these values into run_basketball_game()

## Next
- [ ] Step 2: Dynamic KBO team stats integration (Odds API or fallback to existing KBO model)
- [ ] Step 4: Automate Euro basketball odds fetching and pass live lines into BasketballPredictor
- [ ] Step 5: Complete soccer player props TODO (anytime goalscorer) via Odds API
- [ ] Step 6: Remove hardcoded Discord market totals (soccer) and use dynamic args
- [ ] Step 7: Expand low-liquidity league handling to avoid skipping prop targets
