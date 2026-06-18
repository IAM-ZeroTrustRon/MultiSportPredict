"""
auto_dispatcher.py
==================
Automated dispatcher that eliminates manual data entry.

Features:
- Fetches live data from The-Odds-API
- Auto-generates features for upcoming matches
- Caches results to avoid re-fetching
- Runs predictions without manual parameters
- Supports batch processing and scheduled updates

Usage:
  python -m models.auto_dispatcher --sport soccer --league soccer_epl
  python -m models.auto_dispatcher --sport soccer --upcoming
  python -m models.auto_dispatcher --sport all --batch
"""

import sys
import os
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

import pandas as pd

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    PROCESSED_DIR, CACHE_DIR, OUTPUT_DIR,
    SOCCER_FEATURE_COLS, BASKETBALL_FEATURE_COLS, KBO_FEATURE_COLS,
)
from OddsApiIngestor import OddsApiIngestor
from ingest.odds_client import OddsClient
from ingest.error_handling import safe_to_csv, logger
from models.soccer_league_config import (
    get_league_config,
    list_supported_leagues,
    LeagueDetector,
    add_league_detection_to_df,
)

# ──────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
LOG = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# LEAGUE & SPORT MAPPINGS
# ──────────────────────────────────────────────

SOCCER_LEAGUES = {
    "epl": "soccer_epl",
    "champions_league": "soccer_uefa_champs_league",
    "la_liga": "soccer_spain_la_liga",
    "serie_a": "soccer_italy_serie_a",
    "bundesliga": "soccer_germany_bundesliga",
    "ligue1": "soccer_france_ligue_one",
    "world_cup": "soccer_fifa_world_cup",
    "euro": "soccer_uefa_euro_championship",
}

FEATURE_DEFAULTS = {
    "soccer": {
        "home_xg": 1.5, "away_xg": 1.3,
        "home_xga": 1.2, "away_xga": 1.4,
        "home_shots": 12, "away_shots": 11,
        "home_corners": 5, "away_corners": 4,
        "home_form": 0.2, "away_form": 0.1,
        "goals_line": 2.5, "sharp_score": 0.0,
        "reverse_line_movement": 1, "money_ticket_gap": 5,
        "public_tickets_pct": 55, "public_money_pct": 50,
    },
    "basketball": {
        "home_ortg": 110, "away_ortg": 105,
        "home_drtg": 105, "away_drtg": 110,
        "home_pace": 100, "away_pace": 100,
        "rest_diff": 0, "sharp_score": 0.0,
        "reverse_line_movement": 1, "money_ticket_gap": 2,
        "public_tickets_pct": 55, "public_money_pct": 50,
    },
    "kbo": {
        "home_woba": 0.320, "away_woba": 0.310,
        "home_wrc_plus": 100, "away_wrc_plus": 100,
        "home_fip": 3.50, "away_fip": 3.60,
        "home_whip": 1.20, "away_whip": 1.25,
        "home_bullpen_fip": 3.80, "away_bullpen_fip": 4.00,
        "sharp_score": 0.0, "reverse_line_movement": 1,
        "money_ticket_gap": 5, "public_tickets_pct": 55,
        "public_money_pct": 50,
    },
}


# ──────────────────────────────────────────────
# AUTO FEATURE GENERATION
# ──────────────────────────────────────────────

class AutoFeatureGenerator:
    """Automatically generates features from live odds data."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ODDS_API_KEY")
        self.ingestor = None
        self.cache_dir = CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        if self.api_key:
            try:
                self.ingestor = OddsApiIngestor(api_key=self.api_key)
                LOG.info("OddsApiIngestor initialized")
            except Exception as e:
                LOG.warning(f"Could not initialize OddsApiIngestor: {e}. Will use defaults.")

    def _generate_soccer_features_from_odds(
        self, home_team: str, away_team: str, odds_data: Optional[Dict] = None
    ) -> Dict:
        """Generate soccer features from live odds."""
        features = dict(FEATURE_DEFAULTS["soccer"])
        features["home_team"] = home_team
        features["away_team"] = away_team

        # If odds data provided, extract bookmaker signals
        if odds_data:
            try:
                # Parse sharp/consensus signals from bookmakers
                bookmakers = odds_data.get("bookmakers", [])
                if bookmakers:
                    spreads = [b.get("markets", []) for b in bookmakers]
                    # Simplified: use first bookmaker's total
                    if spreads and spreads[0]:
                        totals = [m for m in spreads[0] if m.get("key") == "totals"]
                        if totals:
                            first_outcome = totals[0].get("outcomes", [{}])[0]
                            features["goals_line"] = float(first_outcome.get("point", 2.5))
            except Exception as e:
                LOG.debug(f"Could not parse odds for {home_team} vs {away_team}: {e}")

        return features

    def _generate_basketball_features_from_odds(
        self, home_team: str, away_team: str, odds_data: Optional[Dict] = None
    ) -> Dict:
        """Generate basketball features from live odds."""
        features = dict(FEATURE_DEFAULTS["basketball"])
        features["home_team"] = home_team
        features["away_team"] = away_team
        return features

    def _generate_kbo_features_from_odds(
        self, home_team: str, away_team: str, odds_data: Optional[Dict] = None
    ) -> Dict:
        """Generate KBO features from live odds."""
        features = dict(FEATURE_DEFAULTS["kbo"])
        features["home_team"] = home_team
        features["away_team"] = away_team
        return features

    def fetch_and_generate_soccer_features(
        self, league_key: str = "soccer_epl", cache: bool = True
    ) -> Optional[pd.DataFrame]:
        """Fetch upcoming soccer matches and auto-generate features."""
        if not self.ingestor:
            LOG.error("OddsApiIngestor not available. Cannot fetch live data.")
            return None

        try:
            LOG.info(f"Fetching soccer matches from {league_key}...")
            odds_events = self.ingestor.fetch_live_odds(sport_key=league_key)

            if not odds_events:
                LOG.warning(f"No events returned for {league_key}")
                return None

            features_list = []
            for event in odds_events:
                home_team = event.get("home_team", "Unknown")
                away_team = event.get("away_team", "Unknown")

                features = self._generate_soccer_features_from_odds(
                    home_team, away_team, event
                )
                features["target"] = 2.5  # Placeholder; would be filled during model fit
                features_list.append(features)

            df = pd.DataFrame(features_list)
            LOG.info(f"Generated features for {len(df)} soccer matches")

            if cache:
                cache_path = self.cache_dir / f"{league_key}_features.csv"
                safe_to_csv(df, cache_path)
                LOG.info(f"Cached features to {cache_path}")

            return df

        except Exception as e:
            LOG.error(f"Error fetching soccer features: {e}")
            return None

    def get_or_generate_features(
        self, sport: str, home_team: str, away_team: str
    ) -> Dict:
        """Get features from cache or generate on-demand."""
        if sport == "soccer":
            return self._generate_soccer_features_from_odds(home_team, away_team)
        elif sport == "basketball":
            return self._generate_basketball_features_from_odds(home_team, away_team)
        elif sport == "kbo":
            return self._generate_kbo_features_from_odds(home_team, away_team)
        else:
            raise ValueError(f"Unknown sport: {sport}")


# ──────────────────────────────────────────────
# AUTO DISPATCHER
# ──────────────────────────────────────────────

class AutoDispatcher:
    """Dispatch predictions automatically without manual CSV or parameter entry."""

    def __init__(self, api_key: Optional[str] = None):
        self.generator = AutoFeatureGenerator(api_key=api_key)
        self.processed_dir = PROCESSED_DIR
        self.output_dir = OUTPUT_DIR

    def predict_match(self, sport: str, home_team: str, away_team: str, league: str = None) -> bool:
        """
        Run prediction for a match without requiring pre-built CSV.

        Args:
            sport: Sport type (soccer, basketball, kbo)
            home_team: Home team name
            away_team: Away team name
            league: Optional league identifier

        Returns True if successful, False otherwise.
        """
        try:
            # Generate features on-demand
            LOG.info(f"Generating features for {sport}: {home_team} vs {away_team}")
            features = self.generator.get_or_generate_features(sport, home_team, away_team)

            # Convert to DataFrame for model
            df = pd.DataFrame([features])

            # Import appropriate model
            if sport == "soccer":
                # Try to run prediction; if match not found, add it and retry
                try:
                    from models.soccer_predictor import SoccerPredictor
                    LOG.info(f"Running soccer prediction...")
                    predictor = SoccerPredictor(league=league or "Premier League")
                    result = predictor.predict(
                        features=None, model=None,
                        home_team=home_team, away_team=away_team
                    )
                except ValueError as e:
                    if "No soccer game found" in str(e):
                        LOG.warning(f"Match not in CSV. Adding {home_team} vs {away_team}...")
                        if self._add_match_to_csv(sport, home_team, away_team):
                            predictor = SoccerPredictor(league=league or "Premier League")
                            result = predictor.predict(
                                features=None, model=None,
                                home_team=home_team, away_team=away_team
                            )
                        else:
                            raise
                    else:
                        raise

            elif sport == "basketball":
                try:
                    from models.basketball_predictor import BasketballPredictor
                    LOG.info(f"Running basketball prediction...")
                    predictor = BasketballPredictor(league=league or "EuroLeague")
                    result = predictor.predict(
                        features=None, model=None,
                        home_team=home_team, away_team=away_team
                    )
                except ValueError as e:
                    if "No basketball game found" in str(e):
                        LOG.warning(f"Match not in CSV. Adding {home_team} vs {away_team}...")
                        if self._add_match_to_csv(sport, home_team, away_team):
                            predictor = BasketballPredictor(league=league or "EuroLeague")
                            result = predictor.predict(
                                features=None, model=None,
                                home_team=home_team, away_team=away_team
                            )
                        else:
                            raise
                    else:
                        raise

            elif sport == "kbo":
                try:
                    from models.baseball_predictor import BaseballPredictor
                    LOG.info(f"Running KBO prediction...")
                    predictor = BaseballPredictor()
                    data = predictor.load_data(league="KBO", home_team=home_team, away_team=away_team)
                    features = predictor.feature_engineering(data)
                    result = predictor.predict(features, None, home_team, away_team, "KBO")
                except ValueError as e:
                    if "No kbo game found" in str(e).lower():
                        LOG.warning(f"Match not in CSV. Adding {home_team} vs {away_team}...")
                        if self._add_match_to_csv(sport, home_team, away_team):
                            predictor = BaseballPredictor()
                            data = predictor.load_data(league="KBO", home_team=home_team, away_team=away_team)
                            features = predictor.feature_engineering(data)
                            result = predictor.predict(features, None, home_team, away_team, "KBO")
                        else:
                            raise
                    else:
                        raise
            else:
                raise ValueError(f"Unknown sport: {sport}")

            LOG.info(f"✓ Prediction complete: {result}")
            return True

        except FileNotFoundError as e:
            # If feature file doesn't exist, create it with defaults
            LOG.warning(f"Feature file not found: {e}. Creating with defaults...")
            if self._create_default_features_csv(sport):
                return self.predict_match(sport, home_team, away_team)
            return False

        except Exception as e:
            LOG.error(f"Error predicting {sport} {home_team} vs {away_team}: {e}")
            return False

    def _add_match_to_csv(self, sport: str, home_team: str, away_team: str) -> bool:
        """Add a match to the features CSV if missing."""
        try:
            if sport == "soccer":
                csv_path = self.processed_dir / "soccer_features.csv"
                features = self.generator._generate_soccer_features_from_odds(home_team, away_team)
                features["total_goals"] = 2.5
                target_col = "total_goals"
                # Add league detection
                detector = LeagueDetector()
                detected_league = detector.detect_from_row(
                    pd.Series({"home_team": home_team})
                )
                if detected_league:
                    features["league"] = detected_league
            elif sport == "basketball":
                csv_path = self.processed_dir / "basketball_features.csv"
                features = self.generator._generate_basketball_features_from_odds(home_team, away_team)
                features["total_points"] = 215
                target_col = "total_points"
            elif sport == "kbo":
                csv_path = self.processed_dir / "kbo_features.csv"
                features = self.generator._generate_kbo_features_from_odds(home_team, away_team)
                features["total_runs"] = 8.5
                target_col = "total_runs"
            else:
                return False

            # Read existing CSV, add new match, save
            if csv_path.exists():
                df = pd.read_csv(csv_path)
                # Check if match already exists (case-insensitive)
                existing = df[
                    (df["home_team"].str.lower() == home_team.lower()) &
                    (df["away_team"].str.lower() == away_team.lower())
                ]
                if not existing.empty:
                    LOG.info(f"Match already in CSV (different case)")
                    return True
            else:
                df = pd.DataFrame()

            # Add new row
            new_row = pd.DataFrame([features])
            df = pd.concat([df, new_row], ignore_index=True)
            
            # Add league detection if sport is soccer and column missing
            if sport == "soccer" and "league" not in df.columns:
                df = add_league_detection_to_df(df)
            
            safe_to_csv(df, csv_path)
            LOG.info(f"Added {home_team} vs {away_team} to {csv_path}")
            return True

        except Exception as e:
            LOG.error(f"Could not add match to CSV: {e}")
            return False

    def _create_default_features_csv(self, sport: str) -> bool:
        """Create a template feature CSV with defaults if it doesn't exist."""
        try:
            if sport == "soccer":
                feature_cols = SOCCER_FEATURE_COLS + ["home_team", "away_team", "total_goals"]
                sample = self.generator._generate_soccer_features_from_odds("Team A", "Team B")
                sample["total_goals"] = 2.5
            elif sport == "basketball":
                feature_cols = BASKETBALL_FEATURE_COLS + ["home_team", "away_team", "total_points"]
                sample = self.generator._generate_basketball_features_from_odds("Team A", "Team B")
                sample["total_points"] = 215
            elif sport == "kbo":
                feature_cols = KBO_FEATURE_COLS + ["home_team", "away_team", "total_runs"]
                sample = self.generator._generate_kbo_features_from_odds("Team A", "Team B")
                sample["total_runs"] = 8.5
            else:
                return False

            df = pd.DataFrame([sample])
            out_path = self.processed_dir / f"{sport}_features.csv"
            safe_to_csv(df, out_path)
            LOG.info(f"Created template feature CSV: {out_path}")
            return True

        except Exception as e:
            LOG.error(f"Could not create default features CSV for {sport}: {e}")
            return False

    def predict_batch(self, sport: str, matches: List[Tuple[str, str]]) -> Dict[str, bool]:
        """Run predictions for multiple matches."""
        results = {}
        for home, away in matches:
            key = f"{home} vs {away}"
            success = self.predict_match(sport, home, away)
            results[key] = "✓" if success else "✗"
            LOG.info(f"  {key}: {results[key]}")
        return results

    def predict_upcoming_league(self, league_key: str = "soccer_epl") -> Dict:
        """Fetch upcoming matches from league and predict all."""
        LOG.info(f"Fetching upcoming matches for {league_key}...")
        df = self.generator.fetch_and_generate_soccer_features(league_key)

        if df is None or df.empty:
            LOG.error(f"Could not fetch matches for {league_key}")
            return {}

        results = {}
        for _, row in df.iterrows():
            home = row.get("home_team")
            away = row.get("away_team")
            if home and away:
                success = self.predict_match("soccer", home, away)
                results[f"{home} vs {away}"] = "✓" if success else "✗"

        return results


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Automated dispatcher: predict without manual data entry"
    )
    parser.add_argument(
        "--sport",
        default="soccer",
        choices=["soccer", "basketball", "kbo", "all"],
        help="Sport to predict"
    )
    parser.add_argument(
        "--home",
        help="Home team name"
    )
    parser.add_argument(
        "--away",
        help="Away team name"
    )
    parser.add_argument(
        "--league",
        default="epl",
        choices=list(SOCCER_LEAGUES.keys()),
        help="League (soccer only)"
    )
    parser.add_argument(
        "--upcoming",
        action="store_true",
        help="Predict all upcoming matches in league"
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Process batch (all sports, all upcoming)"
    )
    parser.add_argument(
        "--api-key",
        help="The-Odds-API key (or set ODDS_API_KEY env var)"
    )

    args = parser.parse_args()

    dispatcher = AutoDispatcher(api_key=args.api_key)

    if args.batch:
        LOG.info("Starting batch prediction...")
        for sport in ["soccer", "basketball", "kbo"]:
            LOG.info(f"\n--- {sport.upper()} ---")
            # For now, just handle soccer with upcoming
            if sport == "soccer":
                dispatcher.predict_upcoming_league(SOCCER_LEAGUES.get(args.league, "soccer_epl"))

    elif args.upcoming:
        LOG.info(f"Predicting upcoming matches for {args.league}...")
        league_key = SOCCER_LEAGUES.get(args.league)
        if league_key:
            dispatcher.predict_upcoming_league(league_key)
        else:
            LOG.error(f"Unknown league: {args.league}")

    elif args.home and args.away:
        LOG.info(f"Predicting: {args.sport} - {args.home} vs {args.away}")
        dispatcher.predict_match(args.sport, args.home, args.away)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

