# MultiSportPredict

A multi-sport prediction engine that ingests live sports data, models match outcomes, and
grades every forecast against real results. Built in Python with a hard rule: **the system
refuses to produce a number it cannot justify.**

Sports covered: soccer (Premier League, Championship, Eredivisie, Liga MX), baseball
(MLB, KBO), basketball (EuroLeague), tennis, with an NFL engine in progress.

---

## Security & Reliability Engineering

This project is as much an exercise in defensive engineering as in modelling. A prediction
system that silently degrades is worse than one that stops — a confident number built on
missing data is indistinguishable from a correct one until money is on it.

### Fail-closed data validation

`data_guard.py` blocks a run rather than degrading. It validates every record before use:

- **Staleness** — season and last-updated fields are checked against an expected window
- **Sample size** — teams below a per-sport minimum are refused, not averaged
- **Severity separation** — wrong-season data is an *error* (blocks); merely old data is a
  *warning* (informs). A guard that cries wolf gets ignored, which is worse than no guard.

Built after a season-sorting bug silently loaded 1999/2000 league data into a 2026 slate.
The ingest succeeded, the parse succeeded, the run reported success. The only symptom was a
defunct club appearing in a team list — caught by eye, not by code. That gap is now closed.

### Eliminating silent failure paths

Three separate bugs were found where a failed lookup fell through to a hardcoded default,
producing confident output from no data at all:

| Component | Failure | Fix |
|---|---|---|
| `SoccerPredictor` | missing stats → default xG for both teams | raise on lookup miss |
| `BaseballPredictor` | missing stats → league-average runs/ERA | pass real values, warn loudly on miss |
| `TennisElo` | no data file → frozen seed ratings | load real match history, report count |

Each produced *identical predictions across different matchups* — a failure mode that looks
like working software. The pattern is now treated as a class of bug, not three incidents.

### Secrets management

- API credentials live in `.env`, excluded via `.gitignore` and verified untracked
- No key, token, or webhook URL appears in source or in commit history
- Credentials are read at runtime, never logged or written to output files

### Least privilege access

Remote access is configured with a **dedicated non-administrator account**, not the primary
user. Filesystem permissions are scoped to the project directory only (`icacls`), so a
compromised remote credential cannot reach the rest of the host. SSH is bound to the local
network; no port is exposed to the internet.

### Data integrity

- **Atomic writes** — every store is written to a temp file and `os.replace`d, so an
  interrupted write cannot corrupt it
- **Corruption handling** — malformed JSON is quarantined with a timestamped copy rather
  than overwritten
- **Backups before mutation** — any script that edits existing source files writes a dated
  backup first
- **Merge, never clobber** — stores merge on write, so one league's ingest cannot delete
  another's data

### Network forensics

`diagnose_sources.py` distinguishes *legitimate site-side blocking* from *traffic
interception* — a distinction that matters before you conclude a source is unavailable:

- Proxy environment variables and system proxy configuration
- DNS resolution (detecting redirection to local or private addresses)
- **TLS certificate issuer inspection** — a non-public CA on a public host indicates
  interception by inspection middleware
- Multi-method fetch comparison (proxied vs. direct, varying client fingerprints)

Used to prove that four failing data sources were genuine CDN bot-protection (Cloudflare,
Akamai) rather than a compromised local environment.

### Respecting access controls

- `koreabaseball.com` is deliberately **not** scraped — its `robots.txt` disallows automated
  access, so an alternative source is used
- Rate limiting and on-disk response caching on every scraped host
- Data licence terms tracked in-source where they constrain use

### Provenance and auditability

Every stored record carries its `source`, `updated` timestamp, and a `data_tier` marking
whether a value is measured or derived. Every prediction is logged to SQLite and graded
against real outcomes, with wins settled at recorded market prices rather than assumed ones.

The system distinguishes what it *knows* from what it *inferred* — and says so in the output.

### Supply chain scepticism

AI-generated contributions to this codebase are reviewed before use. One submission was
rejected after inspection revealed hardcoded fabricated statistics labelled as live
"Tier 1" data from a named source. Verified against the real feed, its numbers were wrong
by up to a full run per game. **Provenance labels are checked, not trusted.**

---

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