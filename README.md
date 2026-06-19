# MultiSportPredict

A comprehensive machine learning platform for predicting outcomes across multiple sports worldwide. Features live web scraping hooks, SQLite backtesting, and a daily slate runner for batch processing.

## Overview

MultiSportPredict provides multi-sport prediction capabilities with sabermetric data, Poisson modeling, sharp consensus integration, and park factor adjustments:

- **⚾ KBO (Korean Baseball Organization)**: Game predictions (totals, moneyline, run line), player props, sharp consensus
- **🏀 Basketball**: EuroLeague/NBA/Taiwan P. League+ - full game, spread, totals, moneyline, Q1 projections, player props
- **⚽ Soccer**: Match outcome (1X2), goals over/under, BTTS, corner totals, xG-based Poisson modeling
- **🇺🇸 MLB**: NRFI/YRFI, strikeout props, home run props, full game predictions with Statcast data
- **🎾 Tennis**: Dominance Ratio analysis, fatigue delta tracking, live betting triggers

## Quick Start

### Installation

```bash
pip install -r MultiSportPredict/requirements.txt
```

### Unified CLI

Predict any sport with a single command:

```bash
# Universal Runner (all sports)
python run_match.py --sport baseball --home "NYY" --away "BOS" --store-to-db
python run_match.py --sport soccer --home "Liverpool" --away "Aston Villa" --market-total 2.5
python run_match.py --sport basketball --home "Real Madrid" --away "FC Barcelona" --league "EuroLeague"
python run_match.py --sport tennis --home "Djokovic" --away "Alcaraz" --surface "Grass"

# Legacy Unified CLI
python predict_match.py kbo "Doosan Bears" "LG Twins"
python predict_match.py soccer "Liverpool" "Aston Villa"
python predict_match.py mlb "NYY" "BOS"
```

### Batch Slate Processing

Process multiple matchups at once by creating a CSV and running:

```bash
python run_slate.py                              # Uses input/slate.csv
python run_slate.py --input my_matches.csv       # Custom CSV
python run_slate.py --store-to-db                # Save all to SQLite
```

Example CSV format (`input/slate.csv`):
```csv
sport,home_team,away_team,league,market_line,market_total
soccer,Liverpool,Aston Villa,EPL,0.25,2.5
mlb,NYY,BOS,MLB,0.0,8.5
tennis,Djokovic,Alcaraz,Grass,0.0,0.0
```

Output is a sorted Markdown report by **Highest Confidence Score**.

### Run Pre-built Analysis Scripts

```bash
# KBO June 16, 2026 - NC Dinos @ Hanwha Eagles + SSG Landers @ Lotte Giants
python run_kbo_june16_matches.py

# Taiwan P. League+ - Fubon Braves vs Taoyuan Pilots
python run_taiwan_basketball_analysis.py

# Estonian Meistriliiga - FC Kuressaare vs Trans Narva
python run_kuressaare_narva_soccer.py
```

## Project Structure

```
MultiSportPredict/
├── basketball/              # Basketball prediction module
│   ├── __init__.py
│   └── basketball_predict_game.py
├── core/                    # Shared core engine
│   ├── confidence_engine.py # Confidence scoring & bet recommendations
│   ├── historical_storage.py# SQLite prediction storage
│   └── schemas.py           # Data schemas
├── features/                # Feature engineering
│   ├── kbo_features.py
│   ├── soccer_features.py
│   └── basketball_features.py
├── ingest/                  # Data ingestion & odds fetching
│   ├── odds_client.py
│   ├── schedule_ingest.py
│   └── dispatcher.py
├── mlb/                     # MLB prediction module
│   ├── mlb_module.py        # Core MLB functionality
│   ├── mlb_prop_edges.py    # Prop edge calculation
│   └── README.md
├── models/                  # Sport-specific models
│   ├── kbo_model.py         # KBO Random Forest model
│   ├── soccer_predictor.py  # xG + Poisson soccer model
│   ├── basketball_predictor.py # FIBA basketball model
│   ├── baseball_predictor.py   # MLB/KBO baseball model
│   └── auto_dispatcher.py   # Automated prediction dispatcher
├── output/                  # Prediction results
│   ├── kbo/                 # KBO analysis output JSONs
│   ├── basketball/          # Basketball analysis output JSONs
│   ├── soccer/              # Soccer analysis output JSONs
│   ├── baseball/            # Baseball/MLB analysis output JSONs
│   └── mlb/                 # MLB-specific analysis output JSONs
├── data/
│   ├── mlb/
│   │   ├── raw/             # Raw Statcast data
│   │   ├── features/        # Engineered features
│   │   └── models/          # Trained models
│   └── processed/           # Processed feature CSVs
├── run_kbo_june13_with_analysis.py
├── run_kbo_june16_matches.py       # KBO June 16 doubleheader
├── run_taiwan_basketball_analysis.py # Taiwan P. League+
├── run_kuressaare_narva_soccer.py   # Estonian Meistriliiga
├── MultiSportModel.py       # Core European basketball/corner modeling engine
├── predict_match.py         # Unified CLI
├── requirements.txt
└── README.md
```

## KBO Module (Korean Baseball Organization)

The KBO module provides comprehensive baseball predictions for the Korean Baseball Organization.

### Features

- **Sabermetric Team Profiles**: Detailed stats for all 10 KBO teams including wOBA, wRC+, FIP, WHIP, SwStr%, O-Swing%
- **Park Factor Adjustments**: Venue-specific HR, runs, hits, and strikeout factors
- **Poisson Totals Modeling**: Run distribution probabilities for over/under markets
- **Win Probability**: Team strength-based moneyline projections
- **Strikeout Props**: Pitcher K projections based on K/9 and park factors
- **Sharp Consensus**: Market sentiment and sharp money indicators

### KBO Teams Supported

| Team | Abbreviation | Home Venue |
|------|-------------|------------|
| Doosan Bears | DOO | Jamsil Baseball Stadium |
| LG Twins | LG | Jamsil Baseball Stadium |
| Kiwoom Heroes | KIW | Gocheok Sky Dome |
| KT Wiz | KT | Suwon KT Wiz Park |
| SSG Landers | SSG | Incheon SSG Landers Field |
| Lotte Giants | LOT | Sajik Baseball Stadium |
| Samsung Lions | SAM | Samsung Lions Park |
| NC Dinos | NC | Changwon NC Park |
| KIA Tigers | KIA | KIA Champions Field |
| Hanwha Eagles | HAN | Hanwha Life Eagles Park |

### Run KBO Analysis

```bash
# June 16, 2026 doubleheader
python run_kbo_june16_matches.py
# Analyzes: NC Dinos @ Hanwha Eagles + SSG Landers @ Lotte Giants

# June 13, 2026 analysis
python run_kbo_june13_with_analysis.py
# Analyzes: Hanwha Eagles @ Kiwoom Heroes + Doosan Bears @ KIA Tigers
```

## Taiwan P. League+ Basketball Module

Basketball predictions for Taiwan's top professional league.

### Features

- **Advanced Metrics**: ORTG, DRTG, net rating, pace, 3PT%, rebounding
- **Efficiency Gap Analysis**: Team strength differentials
- **Spread Projections**: Model-based point spread with cover probability
- **Totals Analysis**: Normal distribution-based over/under probabilities
- **Win Probability**: Net rating gap + home court advantage modeling
- **Player Props**: Star player points, team 3PT made projections
- **Sharp Consensus**: Market sentiment integration

### Run Taiwan Basketball Analysis

```bash
python run_taiwan_basketball_analysis.py
# Analyzes: Fubon Braves vs Taoyuan Pilots (P. League+)
```

## Soccer Module (xG-Based Poisson Modeling)

Provides soccer predictions using expected goals (xG) metrics and Poisson distribution modeling.

### Features

- **xG-Based Goal Projections**: Expected goals for/against with injury adjustments
- **Poisson Outcome Probabilities**: Full match outcome (1X2) via bivariate Poisson
- **Goals Over/Under**: Over 1.5, 2.5, 3.5, 4.5 probabilities
- **BTTS (Both Teams To Score)**: Structural + Poisson hybrid calculation
- **Corner Projections**: Shot volume, tempo, and width-based corner estimation
- **Injury Impact**: Missing attacker/creator/CB/GK adjustments
- **League Configs**: Per-league goal variance, home advantage, draw rate tuning

### Supported Leagues

- English Premier League, La Liga, Bundesliga, Serie A, Ligue 1
- UEFA Champions League / Europa League
- Estonian Meistriliiga, Kazakhstan Premier League
- Australian NPL, and more (auto-detected or configurable)

### Run Soccer Analysis

```bash
python run_kuressaare_narva_soccer.py
# Analyzes: FC Kuressaare vs Trans Narva (Estonian Meistriliiga)
```

## MLB Module

The MLB module provides comprehensive baseball predictions using Statcast data.

### Features

- **Data Ingestion**: Automatic Statcast data pulling via pybaseball
- **Feature Engineering**: Pitcher, hitter, umpire, and game-level features
- **Full Game Model**: Random Forest for total runs and run differential
- **NRFI/YRFI**: No Run/Ye Run First Inning probability calculations
- **Strikeout Props**: Pitcher K projections with umpire adjustments
- **Home Run Props**: Barrel rate, hard hit%, weather, park factor integration
- **Prop Edges**: Automated edge calculation for MLB prop markets

### MLB Workflow

```python
from mlb import (
    ingest_recent,
    engineer_pitcher_features,
    engineer_hitter_features,
    engineer_umpire_features,
    engineer_team_game_features,
    predict_match,
)

# Step 1: Ingest recent data
df = ingest_recent(days_back=3)

# Step 2: Build features
engineer_pitcher_features(df)
engineer_hitter_features(df)
engineer_umpire_features(df)
engineer_team_game_features(df)

# Step 3: Predict a matchup
result = predict_match("NYY", "BOS")
print(result)
```

See `mlb/README.md` for detailed documentation.

## Confidence Engine

All predictions use the core `confidence_score()` and `bet_recommendation()` functions from `core/confidence_engine.py`:

- **Edge Calculation**: Model value minus market value
- **Volatility Tuning**: Sport-specific volatility parameters (baseball: 0.65, basketball: 0.35-0.40, soccer: 0.45-0.55)
- **Sharp/Market Alignment**: Consensus data integration
- **Recommendations**: STRONG BET (>75), BET (60-75), PASS (<60)

## Historical Storage & Analysis

All predictions are automatically stored in a SQLite database (`multisport_history.db`) for tracking and analysis.

### Querying Historical Predictions

```python
from core import get_predictions, get_prediction_summary, export_predictions_to_json

# Get all basketball predictions
bball_preds = get_predictions(sport="basketball")

# Get predictions for a specific team
team_preds = get_predictions(home_team="FC Barcelona")

# Get predictions by date range
recent_preds = get_predictions(
    start_date="2026-06-01",
    end_date="2026-06-30"
)

# Get summary statistics
summary = get_prediction_summary()
print(f"Total predictions: {summary['total_predictions']}")
print(f"Average confidence: {summary['avg_confidence']}%")

# Export to JSON
export_predictions_to_json("output/all_predictions.json")
```

### Database Schema

The predictions table includes:
- `id`: Unique identifier
- `sport`: Sport type (basketball, soccer, mlb, kbo)
- `home_team`, `away_team`: Team names
- `market_type`: Type of market (spread, total, moneyline, props)
- `model_value`: Model's projected value
- `market_value`: Market line/value
- `edge`: Difference between model and market
- `confidence`: Confidence score (0-100)
- `recommendation`: Bet recommendation (STRONG BET, BET, PASS)
- `timestamp`: When the prediction was made
- `raw_json`: Full prediction result
- `result_outcome`: Actual outcome (win, loss, push)
- `profit_loss`: P&L tracking

## Auto-Dispatcher

The `models/auto_dispatcher.py` provides automated prediction dispatching:

- Auto-creates missing CSV files
- Fetches live odds (if ODDS_API_KEY configured)
- Caches results for performance
- Falls back to sensible defaults when data unavailable
- Supports batch prediction across all sports

```bash
# Predict all upcoming matches across all sports
python predict_match.py --batch

# Predict upcoming matches for a specific sport
python predict_match.py --upcoming --league epl
```

## Recent Updates (June 2026)

| Date | Update | Details |
|------|--------|---------|
| Jun 16 | KBO Doubleheader | NC Dinos @ Hanwha Eagles + SSG Landers @ Lotte Giants |
| Jun 16 | Taiwan PLG | Fubon Braves vs Taoyuan Pilots basketball analysis |
| Jun 16 | Estonian Soccer | FC Kuressaare vs Trans Narva xG-based analysis |
| Jun 15 | MLB June 15 | Comprehensive MLB analysis with NRFI props |
| Jun 15 | KBO June 13 | Hanwha @ Kiwoom + Doosan @ KIA analysis scripts |
| Jun 15 | Model Updates | MultiSportModel, OddsApiIngestor, auto_dispatcher improvements |
| Jun 15 | MLB Prop Edges | New `mlb/mlb_prop_edges.py` module for prop edge calculation |
| Jun 15 | Cleanup | Removed deprecated `predict.py`, `models/basketball_predict.py`, `models/soccer_predict.py` |

## Requirements

- Python 3.8+
- pandas
- numpy
- scikit-learn
- requests
- matplotlib
- pybaseball (for MLB)

## 2026 Season Notes

### MLB
The 2026 MLB season features the new Automated Ball-Strike (ABS) Challenge System, resulting in:
- Tighter strike zone (53.5% at top, 27% at bottom)
- Average of 9.4 runs per game
- Specific umpire tendencies affecting Over/Under trends

### KBO
- Higher scoring environment (~10.2 runs/game vs MLB's ~8.8)
- Foreign player restrictions (3-player limit with significant impact)
- Unique park factors (Gocheok Sky Dome suppresses HRs)
- Contact-focused league (lowest SwStr% in professional baseball)

### Taiwan P. League+
- 40-minute FIBA rules format
- Fubon Braves are back-to-back defending champions
- Moderate scoring environment (~170-175 total points per game)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License