# Czech Liga Pro Table Tennis Prediction Engine

Built for integration into `C:\MultiSportPredict`.

## Overview
This package implements a dedicated prediction engine and odds alerting service exclusively for **Czech Liga Pro Table Tennis**. It strictly enforces Czech Liga Pro boundaries, rejecting all other leagues (Russian Liga Pro, Setka Cup, Czech TT Cup, TT Elite, WTT).

## Package Contents
```text
.
├── table_tennis/
│   ├── __init__.py
│   ├── provider_discovery.py       # Strict league boundary enforcement & provider manifest
│   ├── sources.py                  # Provider adapters (Odds-API.io, BetsAPI) & Playwright observer
│   └── alerts.py                   # EV math, quote freshness check & Discord embed builder
├── models/
│   ├── __init__.py
│   ├── table_tennis_scoring.py     # Rule-faithful absorbing Markov point-state model (11-pt, deuce)
│   ├── table_tennis_poisson.py     # Section 4 auxiliary count distribution utility & diagnostics
│   ├── table_tennis_features.py    # Chronological H2H shrinkage, residuals & workload tracking
│   └── table_tennis_predictor.py   # Proportional de-vigging, hybrid calibration & bottom-up fallback
├── ingest_table_tennis.py          # Scope verification, idempotent dedup & correction versioning
├── run_table_tennis.py             # CLI runner, multi-family market report & Discord push
├── data/
│   └── czech_liga_pro_samples/     # Real captured match and odds payloads from Oct 8-9, 2026
├── tests/
│   ├── __init__.py
│   └── test_table_tennis_comprehensive.py # Section 8 acceptance tests (24 passed)
├── COMMANDS.md                     # Copy-pasteable Git Bash commands
└── STATE_OF_MODEL.md               # Model specification & tested coverage report
```

## Quick Start (Git Bash in C:\MultiSportPredict)
```bash
# 1. Run full test suite
venv/Scripts/python.exe -m unittest -v tests.test_table_tennis_comprehensive

# 2. Run a pre-match prediction
venv/Scripts/python.exe run_table_tennis.py --match "Havrda Leos vs Kulhanek Pavel" --event-id "cz_tt_37257_01" --home-rating 428 --away-rating 476 --odds 2.15 1.65

# 3. Run live in-play conditioning
venv/Scripts/python.exe run_table_tennis.py --match "Havrda Leos vs Kulhanek Pavel" --event-id "cz_tt_37257_01" --home-rating 428 --away-rating 476 --live --live-games 1 0 --live-points 8 5

# 4. Generate Discord embed from saved run
venv/Scripts/python.exe run_table_tennis.py --push "cz_tt_37257_01" --odds 2.15 1.65
```
