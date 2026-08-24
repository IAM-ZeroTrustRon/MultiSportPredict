# ═══════════════════════════════════════════════════════════════════════════
# DEPRECATED / ORPHANED — DO NOT EXTEND OR RELY ON THIS FILE
# ───────────────────────────────────────────────────────────────────────────
# Confirmed via repo-wide import grep (see ARCHITECTURE.md §2/§3): this file
# is NOT reachable from predict_match.py (the live entry point). It has zero
# effect on real predictions. Keep it only as reference until it is deleted.
# ═══════════════════════════════════════════════════════════════════════════

"""
Soccer League Configuration System
===================================
Universal configuration for all soccer leagues.
Auto-detects league from match data and applies league-specific tuning.

Features:
- League auto-detection from team names or league column
- League-specific model hyperparameters
- Feature normalization per league
- Automatic handling of new/unknown leagues with sensible defaults
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, List
import pandas as pd

# ──────────────────────────────────────────────
# LEAGUE DEFINITIONS
# ──────────────────────────────────────────────

@dataclass
class LeagueConfig:
    """Configuration for a specific soccer league."""
    
    name: str
    key: str  # e.g., "soccer_epl"
    region: str  # e.g., "England"
    
    # Model hyperparameters (tuned per league)
    model_n_estimators: int = 300
    model_max_depth: int = 10
    model_min_samples_split: int = 5
    model_random_state: int = 42
    
    # Feature scaling / normalization
    xg_scale: float = 1.0  # Scaling factor for xG values
    shots_scale: float = 1.0
    corners_scale: float = 1.0
    
    # Goals prediction thresholds
    goals_line_default: float = 2.5
    btts_xg_threshold: float = 0.8  # Minimum xG for BTTS prediction
    over_probability_threshold: float = 0.5
    
    # League characteristics
    avg_goals_per_match: float = 2.74
    high_scoring: bool = False  # True if league typically has 3+ goals/match
    defensive_focus: bool = False  # True if league emphasizes defense
    
    # Feature availability
    required_features: List[str] = None
    optional_features: List[str] = None
    
    def __post_init__(self):
        if self.required_features is None:
            self.required_features = [
                "home_xg", "away_xg", "home_xga", "away_xga",
                "home_shots", "away_shots",
                "home_corners", "away_corners",
                "home_form", "away_form",
            ]
        if self.optional_features is None:
            self.optional_features = [
                "sharp_score", "reverse_line_movement",
                "money_ticket_gap", "public_tickets_pct", "public_money_pct"
            ]


# ──────────────────────────────────────────────
# LEAGUE CONFIGURATIONS
# ──────────────────────────────────────────────

LEAGUE_CONFIGS: Dict[str, LeagueConfig] = {
    # Norway Division 1
    "soccer_norway_div1": LeagueConfig(
        name="Norway Division 1",
        key="soccer_norway_div1",
        region="Norway",
        model_n_estimators=300,
        model_max_depth=10,
        avg_goals_per_match=2.55,
        high_scoring=False,
        defensive_focus=False,
        btts_xg_threshold=0.80,
        goals_line_default=2.5,
    ),

    # Premier League (England)
    "soccer_epl": LeagueConfig(
        name="English Premier League",
        key="soccer_epl",
        region="England",
        model_n_estimators=400,  # More trees for complex league
        model_max_depth=12,
        avg_goals_per_match=2.82,
        high_scoring=True,
        btts_xg_threshold=0.75,
    ),
    
    # Champions League (Europe)
    "soccer_uefa_champs_league": LeagueConfig(
        name="UEFA Champions League",
        key="soccer_uefa_champs_league",
        region="Europe",
        model_n_estimators=350,
        model_max_depth=11,
        avg_goals_per_match=2.61,
        defensive_focus=True,
        btts_xg_threshold=0.85,  # Stricter BTTS in CL
    ),
    
    # La Liga (Spain)
    "soccer_spain_la_liga": LeagueConfig(
        name="La Liga",
        key="soccer_spain_la_liga",
        region="Spain",
        model_n_estimators=300,
        model_max_depth=10,
        avg_goals_per_match=2.65,
        xg_scale=1.05,  # Spanish teams create more xG
    ),
    
    # Serie A (Italy)
    "soccer_italy_serie_a": LeagueConfig(
        name="Serie A",
        key="soccer_italy_serie_a",
        region="Italy",
        model_n_estimators=280,
        model_max_depth=9,
        avg_goals_per_match=2.54,
        defensive_focus=True,
        btts_xg_threshold=0.90,  # Defensive league, harder to score
    ),
    
    # Bundesliga (Germany)
    "soccer_germany_bundesliga": LeagueConfig(
        name="Bundesliga",
        key="soccer_germany_bundesliga",
        region="Germany",
        model_n_estimators=320,
        model_max_depth=11,
        avg_goals_per_match=3.12,
        high_scoring=True,
        shots_scale=1.1,  # High-tempo league
    ),
    
    # Ligue 1 (France)
    "soccer_france_ligue_one": LeagueConfig(
        name="Ligue 1",
        key="soccer_france_ligue_one",
        region="France",
        model_n_estimators=300,
        model_max_depth=10,
        avg_goals_per_match=2.76,
    ),
    
    # World Cup
    "soccer_fifa_world_cup": LeagueConfig(
        name="FIFA World Cup",
        key="soccer_fifa_world_cup",
        region="International",
        model_n_estimators=250,  # Fewer samples, less historical data
        model_max_depth=8,
        avg_goals_per_match=2.72,
        defensive_focus=True,
        btts_xg_threshold=0.95,  # International matches more cautious
    ),
    
    # Euro (European Championship)
    "soccer_uefa_euro_championship": LeagueConfig(
        name="UEFA Euro",
        key="soccer_uefa_euro_championship",
        region="Europe",
        model_n_estimators=280,
        model_max_depth=9,
        avg_goals_per_match=2.34,
        defensive_focus=True,
        btts_xg_threshold=0.92,
    ),
    
    # Brazilian League
    "soccer_brazil_campeonato": LeagueConfig(
        name="Campeonato Brasileiro",
        key="soccer_brazil_campeonato",
        region="Brazil",
        model_n_estimators=320,
        model_max_depth=11,
        avg_goals_per_match=2.98,
        high_scoring=True,
    ),
}

# Default config for unknown leagues
DEFAULT_LEAGUE_CONFIG = LeagueConfig(
    name="Unknown League",
    key="unknown",
    region="Unknown",
    model_n_estimators=300,
    model_max_depth=10,
    avg_goals_per_match=2.75,
)


# ──────────────────────────────────────────────
# LEAGUE DETECTION & LOOKUP
# ──────────────────────────────────────────────

class LeagueDetector:
    """Auto-detects league from match data."""
    
    # Team name to league mapping (for teams that appear in multiple leagues)
    TEAM_LEAGUE_MAP: Dict[str, str] = {
        # EPL clubs
        "manchester united": "soccer_epl",
        "liverpool": "soccer_epl",
        "manchester city": "soccer_epl",
        "arsenal": "soccer_epl",
        "chelsea": "soccer_epl",
        "tottenham": "soccer_epl",
        "brighton": "soccer_epl",
        "aston villa": "soccer_epl",
        
        # La Liga clubs
        "real madrid": "soccer_spain_la_liga",
        "barcelona": "soccer_spain_la_liga",
        "atletico madrid": "soccer_spain_la_liga",
        
        # Serie A clubs
        "juventus": "soccer_italy_serie_a",
        "ac milan": "soccer_italy_serie_a",
        "inter milan": "soccer_italy_serie_a",
        
        # Bundesliga clubs
        "bayern munich": "soccer_germany_bundesliga",
        "borussia dortmund": "soccer_germany_bundesliga",
        
        # Ligue 1 clubs
        "psg": "soccer_france_ligue_one",
        "paris": "soccer_france_ligue_one",
    }
    
    @classmethod
    def detect_from_row(cls, row: pd.Series) -> Optional[str]:
        """Detect league from a single match row."""
        # Check if league column exists
        if "league" in row and pd.notna(row["league"]):
            league_val = str(row["league"]).lower()
            # Try exact match first
            for key in LEAGUE_CONFIGS.keys():
                if key.lower() in league_val or league_val in key.lower():
                    return key
        
        # Try team name detection
        if "home_team" in row and pd.notna(row["home_team"]):
            team_name = str(row["home_team"]).lower().strip()
            for known_team, league_key in cls.TEAM_LEAGUE_MAP.items():
                if known_team in team_name:
                    return league_key
        
        return None
    
    @classmethod
    def detect_from_df(cls, df: pd.DataFrame) -> Dict[int, str]:
        """Detect league for each row in DataFrame."""
        league_map = {}
        for idx, row in df.iterrows():
            detected = cls.detect_from_row(row)
            league_map[idx] = detected if detected else "unknown"
        return league_map


# ──────────────────────────────────────────────
# CONFIG LOOKUP & UTILITIES
# ──────────────────────────────────────────────

def get_league_config(league_key: str) -> LeagueConfig:
    """Get configuration for a league."""
    return LEAGUE_CONFIGS.get(league_key.lower(), DEFAULT_LEAGUE_CONFIG)


def get_league_config_for_match(home_team: str, away_team: str, 
                                league: Optional[str] = None) -> LeagueConfig:
    """Get league config for a match (with auto-detection)."""
    if league:
        return get_league_config(league)
    
    # Try to detect from team names
    row = pd.Series({"home_team": home_team, "league": league})
    detected = LeagueDetector.detect_from_row(row)
    if detected:
        return get_league_config(detected)
    
    return DEFAULT_LEAGUE_CONFIG


def list_supported_leagues() -> Dict[str, str]:
    """List all supported leagues."""
    return {key: config.name for key, config in LEAGUE_CONFIGS.items()}


def add_league_detection_to_df(df: pd.DataFrame) -> pd.DataFrame:
    """Add league column to DataFrame with auto-detection."""
    df_copy = df.copy()
    
    if "league" not in df_copy.columns:
        league_map = LeagueDetector.detect_from_df(df_copy)
        df_copy["league"] = df_copy.index.map(league_map)
    
    return df_copy


if __name__ == "__main__":
    # Example usage
    print("Supported Soccer Leagues:")
    for key, config in LEAGUE_CONFIGS.items():
        print(f"  {key:40} - {config.name:40} (avg goals: {config.avg_goals_per_match})")
    
    print("\nExample: Get EPL config")
    epl = get_league_config("soccer_epl")
    print(f"  Model trees: {epl.model_n_estimators}, max_depth: {epl.model_max_depth}")
    print(f"  Avg goals/match: {epl.avg_goals_per_match}")
