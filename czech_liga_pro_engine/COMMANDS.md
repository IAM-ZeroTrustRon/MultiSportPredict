# MultiSportPredict — Table Tennis (Czech Liga Pro) Commands

## 1. NAMES-ONLY PREDICTION (Canonical Workflow)
Automatically resolves player ratings from `data/czech_liga_pro_ratings.json` and market quotes from `data/czech_liga_pro_samples/real_captured_odds_payloads.json`:
```bash
cd /c/MultiSportPredict
venv/Scripts/python.exe run_table_tennis.py --match "Havrda Leos vs Kulhanek Pavel"
```

## 2. PREDICTION WITH EXPLICIT EVENT ID & OPTIONAL OVERRIDES
Use when targeting a specific scheduled event ID, or providing manual stat overrides as fallback:
```bash
# Explicit event ID (auto-resolves from stores)
venv/Scripts/python.exe run_table_tennis.py --match "Havrda Leos vs Kulhanek Pavel" --event-id "cz_tt_37257_m01"

# Manual rating and decimal odds overrides (HOME AWAY)
venv/Scripts/python.exe run_table_tennis.py --match "Havrda Leos vs Kulhanek Pavel" --event-id "cz_tt_37257_m01" --home-rating 428 --away-rating 476 --odds 2.15 1.65
```

## 3. LIVE IN-PLAY STATE CONDITIONING
Conditions probabilities on active match state without restarting at 0–0:
```bash
# Player A leads 1-0 in games and 8-5 in Game 2
venv/Scripts/python.exe run_table_tennis.py --match "Havrda Leos vs Kulhanek Pavel" --event-id "cz_tt_37257_m01" --live --live-games 1 0 --live-points 8 5
```

## 4. SAVED-RUN DISCORD PUSH
Directly formats and pushes the previously evaluated run without recomputing or requiring manual odds re-entry:
```bash
# Push saved run directly by event/run ID
venv/Scripts/python.exe run_table_tennis.py --push "cz_tt_37257_m01"
```

## 5. TEST SUITE & VERIFICATION
Execute the full acceptance test suite:
```bash
venv/Scripts/python.exe -m unittest -v tests.test_table_tennis_comprehensive
```
