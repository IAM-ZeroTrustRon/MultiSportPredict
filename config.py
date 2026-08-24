"""
Centralized Configuration for MultiSportPredict
=================================================
Single source of truth for paths, API keys, feature columns,
and league-specific parameters across the entire pipeline.
Uses pathlib for OS-agnostic path resolution.
"""

from pathlib import Path
from typing import Dict, List

# ──────────────────────────────────────────────
# PROJECT ROOT & DATA DIRECTORIES
# ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache"

OUTPUT_DIR = PROJECT_ROOT / "output"
SHARP_OUTPUT_DIR = OUTPUT_DIR / "sharp"
BASKETBALL_OUTPUT_DIR = OUTPUT_DIR / "basketball"
SOCCER_OUTPUT_DIR = OUTPUT_DIR / "soccer"
LIVE_TRACKER_OUTPUT_DIR = OUTPUT_DIR / "live_tracker"
KBO_OUTPUT_DIR = OUTPUT_DIR / "kbo"
TENNIS_OUTPUT_DIR = OUTPUT_DIR / "tennis"

# Ensure all directories exist
for _dir in [
    RAW_DIR, PROCESSED_DIR, CACHE_DIR,
    OUTPUT_DIR, SHARP_OUTPUT_DIR,
    BASKETBALL_OUTPUT_DIR, SOCCER_OUTPUT_DIR, KBO_OUTPUT_DIR,
    TENNIS_OUTPUT_DIR, LIVE_TRACKER_OUTPUT_DIR,
]:
    _dir.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────
# API KEYS (set via env vars with sensible defaults)
# ──────────────────────────────────────────────
ODDS_API_KEY_ENV_VAR = "ODDS_API_KEY"
ODDS_API_BASE_URL_ENV_VAR = "ODDS_API_BASE_URL"
ODDS_API_DEFAULT_BASE_URL = "https://api.opticodds.com/api/v3"

# ──────────────────────────────────────────────
# FEATURE COLUMNS FOR EACH SPORT
# Used by model classes so feature definitions stay DRY.
# ──────────────────────────────────────────────

BASKETBALL_FEATURE_COLS: List[str] = [
    # Basketball efficiency metrics
    "home_ortg", "away_ortg",
    "home_drtg", "away_drtg",
    "home_pace", "away_pace",
    "rest_diff",
    # Sharp / consensus signals
    "sharp_score",
    "reverse_line_movement",
    "money_ticket_gap",
    "public_tickets_pct",
    "public_money_pct",
]

SOCCER_FEATURE_COLS: List[str] = [
    # xG-based team metrics
    "home_xg", "away_xg",
    "home_xga", "away_xga",
    # Shot volume
    "home_shots", "away_shots",
    "home_corners", "away_corners",
    # Form indicators
    "home_form", "away_form",
    # Sharp / consensus signals
    "sharp_score",
    "reverse_line_movement",
    "money_ticket_gap",
    "public_tickets_pct",
    "public_money_pct",
]

KBO_FEATURE_COLS: List[str] = [
    # Advanced hitting metrics
    "home_woba", "away_woba",
    "home_wrc_plus", "away_wrc_plus",
    # Pitching metrics
    "home_fip", "away_fip",
    "home_whip", "away_whip",
    "home_bullpen_fip", "away_bullpen_fip",
    # Sharp / consensus signals
    "sharp_score",
    "reverse_line_movement",
    "money_ticket_gap",
    "public_tickets_pct",
    "public_money_pct",
]

# ──────────────────────────────────────────────
# SPORT-SPECIFIC RAW / PROCESSED FILE PATHS
# ──────────────────────────────────────────────

BASKETBALL_RAW_CSV = RAW_DIR / "basketball_matches.csv"
BASKETBALL_FEATURES_CSV = PROCESSED_DIR / "basketball_features.csv"

SOCCER_RAW_CSV = RAW_DIR / "soccer_matches.csv"
SOCCER_FEATURES_CSV = PROCESSED_DIR / "soccer_features.csv"

KBO_RAW_CSV = RAW_DIR / "kbo_matches.csv"
KBO_FEATURES_CSV = PROCESSED_DIR / "kbo_features.csv"

UPCOMING_MATCHES_RAW_CSV = RAW_DIR / "upcoming_matches.csv"
UPCOMING_MATCHES_PROCESSED_CSV = PROCESSED_DIR / "upcoming_matches.csv"

SHARP_DAILY_ENRICHED_CSV = PROCESSED_DIR / "sharp_daily.csv"

# ──────────────────────────────────────────────
# MODEL TARGET COLUMNS
# ──────────────────────────────────────────────
BASKETBALL_TARGET_COL = "total_points"
SOCCER_TARGET_COL = "total_goals"
KBO_TARGET_COL = "total_runs"

# ──────────────────────────────────────────────
# MODEL HYPERPARAMETERS
# ──────────────────────────────────────────────
RF_N_ESTIMATORS = 300
RF_MAX_DEPTH = 10
RF_RANDOM_STATE = 42

# ──────────────────────────────────────────────
# LEAGUE-IDENTIFIER MAPS FOR ODDS API
# ──────────────────────────────────────────────
SPORT_LEAGUE_MAP: Dict[str, Dict[str, str]] = {
    "basketball": {
        "key": "basketball_euroleague",
        "label": "Basketball - EuroLeague",
    },
    "soccer": {
        "key": "soccer_epl",
        "label": "Soccer - Premier League",
    },
    "kbo": {
        "key": "baseball_kbo",
        "label": "Baseball - KBO",
    },
}

# ──────────────────────────────────────────────
# API-FOOTBALL LIVE TRACKER SETTINGS
# ──────────────────────────────────────────────
API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"
API_FOOTBALL_DEFAULT_POLL_INTERVAL_SECS = 60
API_FOOTBALL_DEFAULT_ROLLING_WINDOW_MINS = 15

# ──────────────────────────────────────────────
# CACHE / RETRY SETTINGS
# ──────────────────────────────────────────────
HTTP_TOTAL_RETRIES = 5
HTTP_BACKOFF_FACTOR = 0.75
HTTP_TIMEOUT_SECONDS = (10, 30)

# ──────────────────────────────────────────────
# CONVENIENCE FUNCTION
# ──────────────────────────────────────────────
def ensure_dirs():
    """Create all required data/output directories."""
    for _dir in [
        RAW_DIR, PROCESSED_DIR, CACHE_DIR,
        OUTPUT_DIR, SHARP_OUTPUT_DIR,
        BASKETBALL_OUTPUT_DIR, SOCCER_OUTPUT_DIR, KBO_OUTPUT_DIR,
        TENNIS_OUTPUT_DIR, LIVE_TRACKER_OUTPUT_DIR,
    ]:
        _dir.mkdir(parents=True, exist_ok=True)