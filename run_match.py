#!/usr/bin/env python
"""
Universal Match Analysis Runner
==============================
Run any sport match through a single CLI entry point.
Includes Live Web Scraping Hooks and SQLite Backtesting Database.

Usage:
    python run_match.py --sport baseball --home "Yankees" --away "Red Sox" --store-to-db
    python run_match.py --sport soccer --home "Switzerland" --away "Bosnia" --market-total 2.5 --store-to-db
"""

import argparse
import sys
import logging
import math
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
import pandas as pd
import numpy as np

# ============================================================================
# LOGGING
# ============================================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# SQLITE DATABASE MANAGER
# ============================================================================
class PredictionDatabase:
    """Manages the local SQLite database for storing and backtesting predictions."""
    def __init__(self, db_path: str = "predictions.db"):
        self.db_path = Path(db_path)
        self._create_tables()

    def _create_tables(self):
        """Creates the prediction tracking table if it does not exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS match_predictions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT,
                        sport TEXT,
                        home_team TEXT,
                        away_team TEXT,
                        league TEXT,
                        market_line REAL,
                        market_total REAL,
                        primary_recommendation TEXT,
                        confidence_score REAL,
                        projected_score_home REAL,
                        projected_score_away REAL,
                        raw_json_output TEXT
                    )
                ''')
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")

    def save_prediction(self, sport: str, home: str, away: str,
                        m_line: float, m_total: float, result: Dict[str, Any],
                        league: str = ""):
        """Extracts top-level metrics from the result dictionary and stores them."""
        try:
            # Parse recommendation and confidence dynamically based on sport output structure
            rec = "PASS"
            conf = 0.0
            proj_home = 0.0
            proj_away = 0.0

            if sport == "baseball":
                rec = result.get("game", {}).get("confidence", {}).get("side", {}).get("recommendation", "PASS")
                conf = result.get("game", {}).get("confidence", {}).get("side", {}).get("score", 0.0)
                proj_home = result.get("game", {}).get("projected_home_runs", 0.0)
                proj_away = result.get("game", {}).get("projected_away_runs", 0.0)
            elif sport == "soccer":
                rec = result.get("predictions", {}).get("side", {}).get("recommendation", "PASS")
                conf = result.get("predictions", {}).get("side", {}).get("confidence", 0.0)
                proj_home = result.get("game", {}).get("projected_home_goals", 0.0)
                proj_away = result.get("game", {}).get("projected_away_goals", 0.0)
                # Fall back to lam values if game dict not present
                if not proj_home and "home_lam" in result:
                    proj_home = result["home_lam"]
                if not proj_away and "away_lam" in result:
                    proj_away = result["away_lam"]
            elif sport == "basketball":
                rec = result.get("full_game", {}).get("lean", "PASS")
                conf = result.get("full_game", {}).get("probability", 0.0) * 100
                proj_home = 0.0
                proj_away = 0.0
            elif sport == "tennis":
                rec = result.get("pre_match_edge", "Neutral")
                conf = abs(result.get("pA_dr", 1.0) - result.get("pB_dr", 1.0)) * 100
                proj_home = 0.0
                proj_away = 0.0

            # Convert full dict to JSON string for deep backtesting later
            raw_json = json.dumps(result, default=str)
            timestamp = datetime.now().isoformat()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO match_predictions
                    (timestamp, sport, home_team, away_team, league,
                     market_line, market_total,
                     primary_recommendation, confidence_score,
                     projected_score_home, projected_score_away,
                     raw_json_output)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (timestamp, sport, home, away, league,
                      m_line, m_total, rec, conf,
                      proj_home, proj_away, raw_json))
                conn.commit()
            logger.info(f"Prediction saved to database ({self.db_path})")
        except Exception as e:
            logger.error(f"Failed to save prediction to DB: {e}")


# ============================================================================
# LIVE WEB SCRAPER HOOKS
# ============================================================================
class LiveDataScraper:
    """
    Attempts to scrape real-time data using community libraries.
    Gracefully returns None if libraries are missing, triggering the model's fallback data.
    """

    @staticmethod
    def get_mlb_stats(home_team: str, away_team: str) -> Optional[Dict[str, Any]]:
        """Attempts to use pybaseball to get real run environments and pitching stats."""
        try:
            import pybaseball as pyb
            pyb.cache.enable()
            logger.info("Pybaseball detected. Attempting to fetch live MLB stats...")

            current_year = datetime.now().year

            # Fetch team batting stats for the current season
            batting = pyb.batting_stats(current_year, qual=100)
            if batting.empty:
                return None

            # Helper to get team stats from batting dataframe
            def _team_runs(team_abbr):
                team_data = batting[batting["Team"] == team_abbr.upper()]
                if team_data.empty:
                    # Try alternate abbreviation
                    for col in ["Team", "team", "TEAM"]:
                        if col in team_data.columns:
                            team_data = batting[batting[col] == team_abbr.upper()]
                            break
                if not team_data.empty:
                    row = team_data.iloc[0]
                    g = float(row.get("G", row.get("g", 162)))
                    r = float(row.get("R", row.get("r", 700)))
                    games_played = max(g, 1)
                    return round(r / games_played, 2)
                return None

            home_runs = _team_runs(home_team)
            away_runs = _team_runs(away_team)

            if home_runs is None:
                home_runs = 4.5
            if away_runs is None:
                away_runs = 4.2

            # Fetch pitching stats
            try:
                pitching = pyb.pitching_stats(current_year, qual=10)
                if not pitching.empty:
                    def _team_era(team_abbr):
                        team_data = pitching[pitching["Team"] == team_abbr.upper()]
                        if not team_data.empty:
                            row = team_data.iloc[0]
                            return float(row.get("ERA", 4.0))
                        return None
                    home_era = _team_era(home_team) or 3.8
                    away_era = _team_era(away_team) or 4.2
                else:
                    home_era = 3.8
                    away_era = 4.2
            except Exception:
                home_era = 3.8
                away_era = 4.2

            logger.info(f"Scraped MLB: {home_team} ({home_runs} R/G, {home_era} ERA) vs {away_team} ({away_runs} R/G, {away_era} ERA)")
            return {
                "home_runs_per_game": home_runs,
                "away_runs_per_game": away_runs,
                "home_era": home_era,
                "away_era": away_era,
                "source": "pybaseball"
            }
        except ImportError:
            logger.warning("pybaseball not installed. Run 'pip install pybaseball' for live MLB data. Using baselines.")
            return None
        except Exception as e:
            logger.warning(f"MLB live scrape failed: {e}. Falling back to baseline data.")
            return None

    @staticmethod
    def get_soccer_xg_stats(home_team: str, away_team: str, league: str = "ENG-Premier League") -> Optional[Dict[str, Any]]:
        """Attempts to use soccerdata to pull FBRef xG metrics."""
        try:
            import soccerdata as sd
            logger.info("soccerdata detected. Attempting to fetch live FBRef xG stats...")

            current_year = datetime.now().year
            # Map common league names to FBRef league codes
            league_map = {
                "premier league": "ENG-Premier League",
                "epl": "ENG-Premier League",
                "la liga": "ESP-La Liga",
                "bundesliga": "GER-Bundesliga",
                "serie a": "ITA-Serie A",
                "ligue 1": "FRA-Ligue 1",
                "eredivisie": "NED-Eredivisie",
                "primeira liga": "POR-Primeira Liga",
            }
            league_code = league_map.get(league.lower().strip(), league)

            fbref = sd.FBref(leagues=league_code, seasons=current_year)
            schedule = fbref.read_schedule()

            if schedule.empty:
                logger.warning(f"No schedule data for {league_code}")
                return None

            # Get team stats
            try:
                team_stats = fbref.read_team_season_stats(stat_type="standard")
                if team_stats.empty:
                    return None
            except Exception:
                return None

            # Extract xG for the specific teams
            def _team_xg(team_name, stats_df):
                """Find xG for a team in the stats dataframe, fuzzy matching."""
                name_lower = team_name.lower()
                # Try exact match first
                if team_name in stats_df.index:
                    row = stats_df.loc[team_name]
                    xg = float(row.get("xG", row.get("xg", 1.35)))
                    xga = float(row.get("xGA", row.get("xga", 1.25)))
                    return xg, xga
                # Try partial match
                for idx in stats_df.index:
                    if name_lower in idx.lower() or idx.lower() in name_lower:
                        row = stats_df.loc[idx]
                        xg = float(row.get("xG", row.get("xg", 1.35)))
                        xga = float(row.get("xGA", row.get("xga", 1.25)))
                        return xg, xga
                return None, None

            home_xg, home_xga = _team_xg(home_team, team_stats)
            away_xg, away_xga = _team_xg(away_team, team_stats)

            if home_xg is None:
                home_xg = 1.35
            if home_xga is None:
                home_xga = 1.25
            if away_xg is None:
                away_xg = 1.30
            if away_xga is None:
                away_xga = 1.35

            logger.info(f"Scraped xG: {home_team} (xG={home_xg:.2f}, xGA={home_xga:.2f}) vs {away_team} (xG={away_xg:.2f}, xGA={away_xga:.2f})")
            return {
                "home_xg": home_xg,
                "home_xga": home_xga,
                "away_xg": away_xg,
                "away_xga": away_xga,
                "source": "soccerdata/fbref"
            }
        except ImportError:
            logger.warning("soccerdata not installed. Run 'pip install soccerdata' for live xG. Using baselines.")
            return None
        except Exception as e:
            logger.warning(f"Soccer live scrape failed: {e}. Falling back to baseline data.")
            return None

    @staticmethod
    def get_tennis_stats(player_a: str, player_b: str, surface: str = "Hard_Outdoor") -> Optional[Dict[str, Any]]:
        """Attempts to scrape tennis stats from public sources."""
        # Try TennisAbstract-style scraping
        try:
            import requests
            from bs4 import BeautifulSoup

            # Try ATP/WTA official site match stats
            # This is a placeholder for a real scraping endpoint
            # In production, you'd use something like:
            # https://www.atptour.com/en/players/player-stats
            logger.info("Attempting tennis stats scrape...")

            # For now, demonstrate the hook pattern
            # Real implementation would scrape:
            # - First serve percentage from last 10 matches
            # - Minutes played in last 48 hours
            # - Head-to-head records on this surface

            # Return None to indicate no real data available yet,
            # forcing fallback to hardcoded values
            return None
        except ImportError:
            logger.warning("Requests/BeautifulSoup not available for tennis scraping.")
            return None
        except Exception as e:
            logger.warning(f"Tennis scrape failed: {e}")
            return None


# ============================================================================
# SHARED UTILITY FUNCTIONS
# ============================================================================
def sigmoid(x: float) -> float:
    x = max(-500, min(500, x))
    return 1 / (1 + math.exp(-x))

def clamp(x: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, x))

def color_score(x: Any) -> float:
    return {"green": 1.0, "yellow": 0.0, "red": -1.0}.get(str(x).strip().lower(), 0.0)

def poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 0.0 if k > 0 else 1.0
    if k < 0:
        return 0.0
    try:
        log_pmf = -lam + k * math.log(lam) - math.lgamma(k + 1)
        return math.exp(log_pmf)
    except (ValueError, OverflowError):
        return 0.0

def poisson_over_prob(lam: float, line: float) -> float:
    n = int(math.floor(line))
    frac = line - n
    if abs(frac) < 1e-9:
        return 1 - sum(poisson_pmf(k, lam) for k in range(0, n + 1))
    else:
        threshold = math.floor(line)
        return 1 - sum(poisson_pmf(k, lam) for k in range(0, threshold + 1))

def poisson_at_least_one(lam: float) -> float:
    return 1 - math.exp(-lam)

def confidence_score(edge: float, volatility: float = 0.50, market_alignment: float = 0.0) -> float:
    raw = abs(edge) / max(volatility * 2, 0.01)
    confidence = min(100, max(0, 50 + raw * 25 + market_alignment * 10))
    return round(confidence, 1)

def bet_recommendation(confidence: float) -> str:
    if confidence >= 75:
        return "STRONG BET"
    elif confidence >= 60:
        return "BET"
    elif confidence >= 45:
        return "LEAN"
    else:
        return "PASS"


# ============================================================================
# SPORT PREDICTOR BASE CLASS
# ============================================================================
class SportPredictorBase(ABC):
    def __init__(self, name: str = None):
        self.name = name or self.__class__.__name__

    @abstractmethod
    def load_data(self, *args, **kwargs) -> Any:
        pass

    @abstractmethod
    def feature_engineering(self, data: Any, *args, **kwargs) -> Any:
        pass

    @abstractmethod
    def predict(self, features: Any, *args, **kwargs) -> Dict[str, Any]:
        pass

    def run_pipeline(self, *args, **kwargs) -> Dict[str, Any]:
        data = self.load_data(*args, **kwargs)
        features = self.feature_engineering(data, *args, **kwargs)
        predictions = self.predict(features, *args, **kwargs)
        predictions['metadata'] = {
            'predictor': self.name,
            'timestamp': datetime.now().isoformat()
        }
        return predictions

# endregion


# region Tennis Predictor
# ============================================================================
# TENNIS PREDICTOR
# ============================================================================
class TennisPredictor(SportPredictorBase):
    """
    Comprehensive Tennis Handicapping Model.
    Evaluates pre-match Dominance Ratios, Fatigue Deltas, and Environmental multipliers.
    """
    def __init__(self, surface="Hard_Outdoor", altitude=0):
        super().__init__()
        self.surface = surface
        self.altitude = altitude

    def load_data(self, *args, **kwargs):
        # Accept both home_team/away_team and player_a/player_b naming
        player_a = kwargs.get('player_a') or kwargs.get('home_team') or (args[0] if args else 'PlayerA')
        player_b = kwargs.get('player_b') or kwargs.get('away_team') or (args[1] if len(args) > 1 else 'PlayerB')
        logger.info(f"Loading data for {player_a} vs {player_b} on {self.surface}...")

        # Attempt live scrape
        live_data = LiveDataScraper.get_tennis_stats(player_a, player_b, self.surface)

        # Fallback to baseline if scrape unavailable
        if live_data is not None:
            logger.info("Using scraped tennis data.")
            return pd.DataFrame({
                "player_a_name": [player_a], "player_b_name": [player_b],
                "surface": [self.surface], "altitude_meters": [self.altitude],
                "player_a_1st_serve_in": [live_data.get("pA_1st_serve_in", 55)],
                "player_a_sv_pts": [live_data.get("pA_sv_pts", 80)],
                "player_a_1st_won": [live_data.get("pA_1st_won", 44)],
                "player_a_2nd_won": [live_data.get("pA_2nd_won", 13)],
                "player_a_ret_pts_won": [live_data.get("pA_ret_pts_won", 28)],
                "player_a_minutes_last_48h": [live_data.get("pA_minutes_last_48h", 80)],
                "player_a_current_elo": [live_data.get("pA_elo", 1900)],
                "player_b_sv_pts": [live_data.get("pB_sv_pts", 75)],
                "player_b_1st_won": [live_data.get("pB_1st_won", 35)],
                "player_b_2nd_won": [live_data.get("pB_2nd_won", 15)],
                "player_b_ret_pts_won": [live_data.get("pB_ret_pts_won", 22)],
                "player_b_minutes_last_48h": [live_data.get("pB_minutes_last_48h", 60)],
                "player_b_current_elo": [live_data.get("pB_elo", 1820)],
            })

        logger.info("Using baseline tennis data (no live scrape available).")
        return pd.DataFrame({
            "player_a_name": [player_a], "player_b_name": [player_b],
            "surface": [self.surface], "altitude_meters": [self.altitude],
            "player_a_1st_serve_in": [55], "player_a_sv_pts": [80],
            "player_a_1st_won": [44], "player_a_2nd_won": [13],
            "player_a_ret_pts_won": [28],
            "player_a_minutes_last_48h": [140], "player_a_current_elo": [1950],
            "player_b_sv_pts": [75], "player_b_1st_won": [35],
            "player_b_2nd_won": [15], "player_b_ret_pts_won": [22],
            "player_b_minutes_last_48h": [60], "player_b_current_elo": [1820],
        })

    def feature_engineering(self, df, **kwargs):
        # Serving Efficiencies
        df["pA_total_serve_won_pct"] = (df["player_a_1st_won"] + df["player_a_2nd_won"]) / df["player_a_sv_pts"]
        df["pB_total_serve_won_pct"] = (df["player_b_1st_won"] + df["player_b_2nd_won"]) / df["player_b_sv_pts"]

        # Returning Efficiencies
        df["pA_return_won_pct"] = df["player_a_ret_pts_won"] / df["player_b_sv_pts"]
        df["pB_return_won_pct"] = df["player_b_ret_pts_won"] / df["player_a_sv_pts"]

        # Dominance Ratio (DR)
        df["pA_dominance_ratio"] = df["pA_return_won_pct"] / (1 - df["pA_total_serve_won_pct"])
        df["pB_dominance_ratio"] = df["pB_return_won_pct"] / (1 - df["pB_total_serve_won_pct"])

        # Fatigue
        df["net_fatigue_minutes"] = df["player_a_minutes_last_48h"] - df["player_b_minutes_last_48h"]
        return df

    def predict(self, features, market_line=0.0, **kwargs):
        row = features.iloc[0]
        player_a, player_b = row['player_a_name'], row['player_b_name']
        dr_diff = row["pA_dominance_ratio"] - row["pB_dominance_ratio"]
        fatigue = row["net_fatigue_minutes"]

        pre_match_edge = "Neutral"
        if dr_diff > 0.15 and fatigue <= 30:
            pre_match_edge = f"Strong Edge: {player_a}"
        elif dr_diff < -0.15 and fatigue >= -30:
            pre_match_edge = f"Strong Edge: {player_b}"
        elif dr_diff > 0.10 and fatigue > 60:
            pre_match_edge = f"DANGER: {player_a} fatigued (+{fatigue}m)"

        print(f"\n*** TENNIS PRE-MATCH VERDICT: {pre_match_edge} ***")
        return {
            "sport": "tennis",
            "pre_match_edge": pre_match_edge,
            "pA_dr": float(row['pA_dominance_ratio']),
            "pB_dr": float(row['pB_dominance_ratio']),
            "net_fatigue_minutes": int(fatigue),
        }

# endregion


# region Basketball Predictor
# ============================================================================
# BASKETBALL PREDICTOR
# ============================================================================
class BasketballPredictor(SportPredictorBase):
    def __init__(self, league="EuroLeague"):
        super().__init__()
        self.league = league

    def load_data(self, home_team, away_team, **kwargs):
        # Generates fallback FIBA stats
        return {
            "home_ortg": kwargs.get('home_ortg', 110.0),
            "home_drtg": kwargs.get('home_drtg', 105.0),
            "home_pace": kwargs.get('home_pace', 72.0),
            "away_ortg": kwargs.get('away_ortg', 108.0),
            "away_drtg": kwargs.get('away_drtg', 107.0),
            "away_pace": kwargs.get('away_pace', 70.0),
        }

    def feature_engineering(self, data, **kwargs):
        data['home_net'] = data['home_ortg'] - data['home_drtg']
        data['away_net'] = data['away_ortg'] - data['away_drtg']
        return data

    def predict(self, features, market_line=0.0, **kwargs):
        edge = features['home_net'] - features['away_net']
        prob = clamp(sigmoid((edge - 4.0) / 2.5))

        total_pace = (features['home_pace'] + features['away_pace']) / 2
        proj_home = 75 + (edge * 1.8) + (total_pace * 0.1)
        proj_away = 73 - (edge * 0.9) + (total_pace * 0.1)

        lean = "Strong Lean" if prob > 0.63 else "Pass"

        print(f"\nProjected Basketball Score: {proj_home:.1f} - {proj_away:.1f}")
        return {
            "sport": "basketball",
            "league": self.league,
            "full_game": {
                "model_edge": round(float(edge), 2),
                "probability": round(float(prob), 4),
                "lean": lean,
                "projected_home_score": round(float(proj_home), 1),
                "projected_away_score": round(float(proj_away), 1),
                "projected_total": round(float(proj_home + proj_away), 1),
            }
        }

# endregion


# region Baseball Predictor
# ============================================================================
# BASEBALL PREDICTOR (WITH SCRAPER HOOK)
# ============================================================================
@dataclass
class PitcherMetrics:
    era: float
    k_per_9: float
    bb_per_9: float


class BaseballPredictor(SportPredictorBase):
    def load_data(self, home_team, away_team, **kwargs) -> Dict[str, Any]:
        # 1. Attempt Live Scrape
        live_data = LiveDataScraper.get_mlb_stats(home_team, away_team)

        # 2. Fallback to Baseline if Scrape failed
        if live_data is None:
            logger.info("Using baseline MLB data...")
            return {
                "home_runs": kwargs.get('home_runs', 4.5),
                "away_runs": kwargs.get('away_runs', 4.2),
                "home_era": kwargs.get('home_era', 3.8),
                "away_era": kwargs.get('away_era', 4.2),
                "home_pitcher": PitcherMetrics(
                    kwargs.get('home_pitcher_era', 3.0),
                    kwargs.get('home_k9', 9.0),
                    kwargs.get('home_bb9', 2.0)
                ),
                "away_pitcher": PitcherMetrics(
                    kwargs.get('away_pitcher_era', 3.5),
                    kwargs.get('away_k9', 8.5),
                    kwargs.get('away_bb9', 2.8)
                ),
                "data_source": "baseline"
            }
        else:
            # Inject Scraped Data
            return {
                "home_runs": live_data["home_runs_per_game"],
                "away_runs": live_data["away_runs_per_game"],
                "home_era": live_data["home_era"],
                "away_era": live_data["away_era"],
                "home_pitcher": PitcherMetrics(
                    float(live_data.get("home_era", 3.8)),
                    kwargs.get('home_k9', 9.0),
                    kwargs.get('home_bb9', 2.0)
                ),
                "away_pitcher": PitcherMetrics(
                    float(live_data.get("away_era", 4.2)),
                    kwargs.get('away_k9', 8.5),
                    kwargs.get('away_bb9', 2.8)
                ),
                "data_source": live_data.get("source", "pybaseball")
            }

    def feature_engineering(self, data, **kwargs):
        home_pitcher = data["home_pitcher"]
        away_pitcher = data["away_pitcher"]

        pitcher_adv = (away_pitcher.era - home_pitcher.era) * 0.5
        data["home_run_projection"] = data["home_runs"] + pitcher_adv
        data["away_run_projection"] = data["away_runs"] - pitcher_adv
        return data

    def predict(self, features, market_line=0.0, **kwargs):
        home_runs = float(features["home_run_projection"])
        away_runs = float(features["away_run_projection"])

        home_win_prob = clamp(sigmoid((home_runs - away_runs) / 2.0 + 0.1))
        proj_total = home_runs + away_runs

        total_edge = proj_total - 8.5
        total_conf = confidence_score(total_edge, volatility=0.65)
        side_conf = confidence_score(abs(home_runs - away_runs), volatility=0.55)

        print(f"\nProjected Baseball Score: {home_runs:.2f} - {away_runs:.2f} (data: {features.get('data_source', 'baseline')})")
        return {
            "sport": "baseball",
            "league": "MLB",
            "game": {
                "projected_home_runs": round(home_runs, 2),
                "projected_away_runs": round(away_runs, 2),
                "projected_total_runs": round(proj_total, 2),
                "home_win_probability": round(home_win_prob, 4),
                "confidence": {
                    "total": {
                        "score": total_conf,
                        "recommendation": bet_recommendation(total_conf)
                    },
                    "side": {
                        "score": side_conf,
                        "recommendation": bet_recommendation(side_conf)
                    }
                }
            },
            "data_source": features.get("data_source", "baseline")
        }

# endregion


# region Soccer Predictor
# ============================================================================
# SOCCER PREDICTOR (WITH SCRAPER HOOK)
# ============================================================================
class SoccerPredictor(SportPredictorBase):
    def load_data(self, home_team, away_team, **kwargs):
        league = kwargs.get('league', 'Premier League')

        # 1. Attempt Live Scrape
        live_data = LiveDataScraper.get_soccer_xg_stats(home_team, away_team, league)

        # 2. Fallback to Baseline if Scrape failed
        if live_data is None:
            logger.info("Using baseline Soccer data...")
            return {
                'home_xg': kwargs.get('home_xg', 1.35),
                'home_xga': kwargs.get('home_xga', 1.25),
                'away_xg': kwargs.get('away_xg', 1.30),
                'away_xga': kwargs.get('away_xga', 1.35),
                'home_sot': kwargs.get('home_sot', 3.8),
                'away_sot': kwargs.get('away_sot', 4.2),
                'data_source': 'baseline'
            }
        else:
            return {
                'home_xg': live_data["home_xg"],
                'home_xga': live_data["home_xga"],
                'away_xg': live_data["away_xg"],
                'away_xga': live_data["away_xga"],
                'home_sot': kwargs.get('home_sot', 3.8),
                'away_sot': kwargs.get('away_sot', 4.2),
                'data_source': live_data.get("source", "soccerdata/fbref")
            }

    def feature_engineering(self, data, **kwargs):
        data['home_lam'] = max(0.20, 0.55 * data['home_xg'] + 0.30 * data['away_xga'] + 0.15 * data['home_sot'])
        data['away_lam'] = max(0.20, 0.55 * data['away_xg'] + 0.30 * data['home_xga'] + 0.15 * data['away_sot'])
        return data

    def predict(self, features, market_line=0.0, market_total=2.5, **kwargs):
        home_lam = float(features['home_lam'])
        away_lam = float(features['away_lam'])
        total_lam = home_lam + away_lam

        home_win_prob = home_lam / (home_lam + away_lam) * 0.85 + 0.10
        away_raw = away_lam / (home_lam + away_lam) * 0.05 + 0.05
        draw_prob = 1 - home_win_prob - away_raw
        away_win_prob = 1 - home_win_prob - draw_prob

        btts_prob = clamp(0.55 * (poisson_at_least_one(home_lam) * poisson_at_least_one(away_lam)))

        side_edge = (home_lam - away_lam) - market_line
        total_edge = total_lam - market_total

        side_conf = confidence_score(side_edge, volatility=0.50)
        total_conf = confidence_score(total_edge, volatility=0.55)

        p_over_15 = poisson_over_prob(total_lam, 1.5)
        p_over_25 = poisson_over_prob(total_lam, 2.5)
        p_over_35 = poisson_over_prob(total_lam, 3.5)

        print(f"\nProjected Soccer Goals: {home_lam:.2f} - {away_lam:.2f} (data: {features.get('data_source', 'baseline')})")
        return {
            "sport": "soccer",
            "game": {
                "projected_home_goals": round(home_lam, 2),
                "projected_away_goals": round(away_lam, 2),
                "projected_total_goals": round(total_lam, 2),
                "home_win_prob": round(home_win_prob, 3),
                "draw_prob": round(draw_prob, 3),
                "away_win_prob": round(away_win_prob, 3),
            },
            "predictions": {
                "side": {
                    "edge": round(side_edge, 3),
                    "confidence": side_conf,
                    "recommendation": bet_recommendation(side_conf)
                },
                "total": {
                    "edge": round(total_edge, 3),
                    "confidence": total_conf,
                    "recommendation": bet_recommendation(total_conf)
                },
                "btts": {
                    "probability": round(btts_prob, 3)
                }
            },
            "goals_analysis": {
                "over_15_prob": round(p_over_15, 3),
                "over_25_prob": round(p_over_25, 3),
                "over_35_prob": round(p_over_35, 3),
            },
            "data_source": features.get("data_source", "baseline")
        }

# endregion


# region CLI & Main Entry Point
# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Universal Match Analysis Runner with Scraper & DB"
    )
    parser.add_argument("--sport", required=True,
                        choices=["soccer", "basketball", "baseball", "tennis"])
    parser.add_argument("--home", required=True, help="Home team/player")
    parser.add_argument("--away", required=True, help="Away team/player")
    parser.add_argument("--league", default="", help="League name (e.g. 'Premier League', 'EuroLeague')")
    parser.add_argument("--market-line", default=0.0, type=float)
    parser.add_argument("--market-total", default=0.0, type=float)
    parser.add_argument("--store-to-db", action="store_true",
                        help="Store result to SQLite database")

    # Allows passing infinite dynamic kwargs (like --surface "Clay" --altitude 600)
    args, unknown = parser.parse_known_args()

    # Dynamic kwargs parsing
    kwargs = {}
    i = 0
    while i < len(unknown):
        if unknown[i].startswith("--"):
            key = unknown[i].lstrip("-").replace("-", "_")
            if i + 1 < len(unknown) and not unknown[i + 1].startswith("--"):
                try:
                    kwargs[key] = float(unknown[i + 1]) if '.' in unknown[i + 1] else int(unknown[i + 1])
                except ValueError:
                    kwargs[key] = unknown[i + 1]
                i += 2
            else:
                kwargs[key] = True
                i += 1
        else:
            i += 1

    # Pass league through kwargs if provided
    if args.league:
        kwargs['league'] = args.league

    # Initialize correct predictor
    if args.sport == "soccer":
        predictor = SoccerPredictor()
    elif args.sport == "basketball":
        predictor = BasketballPredictor(league=args.league or "EuroLeague")
    elif args.sport == "baseball":
        predictor = BaseballPredictor()
    elif args.sport == "tennis":
        predictor = TennisPredictor(**kwargs)

    # print(f"\n{'='*60}")
    # print(f"{args.sport.upper()} MATCH: {args.home} vs {args.away}")
    # print('='*60)

    # Run Pipeline - map generic args to sport-specific parameter names
    result = predictor.run_pipeline(
        home_team=args.home,
        away_team=args.away,
        player_a=args.home,
        player_b=args.away,
        market_line=args.market_line,
        market_total=args.market_total,
        **kwargs
    )

    # Print data source if available
    if "data_source" in result:
        print(f"  Data Source: {result['data_source']}")

    # Store to SQLite Database if flag is passed
    if args.store_to_db:
        db = PredictionDatabase()
        db.save_prediction(
            sport=args.sport,
            home=args.home,
            away=args.away,
            m_line=args.market_line,
            m_total=args.market_total,
            result=result,
            league=args.league
        )
        print(f"  Prediction saved to predictions.db")

    print("\n=== ANALYSIS COMPLETE ===")
    return result

# endregion


if __name__ == "__main__":
    main()