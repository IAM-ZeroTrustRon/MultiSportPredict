#!/usr/bin/env python
"""
Unified CLI for MultiSportPredict
==================================
Predict matches across multiple sports with a single command.

Supported Sports:
    - basketball (FIBA/European, KBL)
    - soccer (xG-based, Anytime Goalscorer props)
    - baseball/mlb (MLB: NRFI, Ks, HRs via pybaseball)
    - kbo (Korean Baseball Organization)

Usage:
    python predict_match.py <sport> <home_team> <away_team> [league]
    python predict_match.py mlb "NYY" "BOS" --markets nrfi strikeouts
    python predict_match.py soccer "Astana" "Irtysh Pavlador" --anytime-scorer

Examples:
    python predict_match.py basketball "Real Madrid" "FC Barcelona"
    python predict_match.py soccer "Liverpool" "Aston Villa"
    python predict_match.py mlb "Yankees" "Red Sox"
    python predict_match.py kbo "Doosan Bears" "LG Twins"
    python predict_match.py soccer "Bayern Munich" "Dortmund" Bundesliga
"""

import sys
import json
import math
import os
import argparse
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# CORE IMPORTS
# ---------------------------------------------------------------------------
try:
    from core.confidence_engine import confidence_score, bet_recommendation
except ImportError:
    def confidence_score(edge, volatility=0.5):
        return min(100, max(0, 50 + edge * 10 / volatility))
    def bet_recommendation(conf, market="default"):
        return "BET" if conf > 60 else "PASS"

try:
    from core import init_db
    init_db()
except Exception:
    pass

# ---------------------------------------------------------------------------
# ODDS API CLIENT (The Odds API via requests.get)
# ---------------------------------------------------------------------------

class OddsAPIClient:
    """
    Client for The Odds API (https://the-odds-api.com/).
    Reads ODDS_API_KEY from environment. Falls back gracefully if unavailable.
    """
    BASE_URL = "https://api.the-odds-api.com/v4"

    # Sport key mapping for The Odds API
    SPORT_KEYS: Dict[str, str] = {
        "soccer": "soccer_epl",
        "football": "soccer_epl",
        "bundesliga": "soccer_germany_bundesliga",
        "la liga": "soccer_spain_la_liga",
        "serie a": "soccer_italy_serie_a",
        "ligue 1": "soccer_france_ligue_one",
        "champions league": "soccer_uefa_champs_league",
        "kazakhstan": "soccer_kazakhstan_premier_league",
        "npl": "soccer_australia_npl",
        "mlb": "baseball_mlb",
        "kbo": "baseball_kbo",
        "basketball": "basketball_nba",
        "euroleague": "basketball_euroleague",
        "kbl": "basketball_kbl",
    }

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.getenv("ODDS_API_KEY", "")
        self._available = bool(self.api_key)

    def available(self) -> bool:
        return self._available

    def fetch_events(self, sport_key: str) -> List[Dict]:
        """Fetch upcoming events for a sport from The Odds API."""
        if not self._available:
            return []
        try:
            import requests
            url = f"{self.BASE_URL}/sports/{sport_key}/events"
            params = {"apiKey": self.api_key, "dateFormat": "iso"}
            r = requests.get(url, params=params, timeout=(10, 30))
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"    [OddsAPI] Error fetching events: {e}")
            return []

    def fetch_odds(self, event_id: str, markets: str = "h2h") -> Dict:
        """Fetch odds for a specific event."""
        if not self._available:
            return {}
        try:
            import requests
            url = f"{self.BASE_URL}/events/{event_id}"
            params = {"apiKey": self.api_key, "markets": markets, "dateFormat": "iso"}
            r = requests.get(url, params=params, timeout=(10, 30))
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"    [OddsAPI] Error fetching odds: {e}")
            return {}

    def resolve_event_id(self, home_team: str, away_team: str,
                         sport_key: str) -> Optional[str]:
        """
        Resolve (home, away) to an event ID via The Odds API.
        Case-insensitive substring matching.
        """
        events = self.fetch_events(sport_key)
        home_l = home_team.lower()
        away_l = away_team.lower()
        for ev in events:
            home_api = ev.get("home_team", "").lower()
            away_api = ev.get("away_team", "").lower()
            if (home_l in home_api or home_api in home_l) and \
               (away_l in away_api or away_api in away_l):
                return ev.get("id")
        return None


# ---------------------------------------------------------------------------
# PYBASEBALL INTEGRATION (MLB advanced stats)
# ---------------------------------------------------------------------------

try:
    import pybaseball as pyb
    _PYBASEBALL_AVAILABLE = True
except ImportError:
    _PYBASEBALL_AVAILABLE = False
    print("[WARNING] pybaseball not installed. MLB advanced stats unavailable.")
    print("  Install: pip install pybaseball")


def get_mlb_team_stats(team_abbr: str) -> Dict[str, Any]:
    """
    Fetch MLB team stats via pybaseball.

    Args:
        team_abbr: 3-letter team abbreviation (e.g. "NYY", "BOS")

    Returns:
        Dict with team statistics
    """
    if not _PYBASEBALL_AVAILABLE:
        return _fallback_mlb_stats(team_abbr)

    result = {
        "team": team_abbr,
        "runs_per_game": 4.5,
        "runs_allowed": 4.0,
        "era": 4.00,
        "whip": 1.25,
        "obp": 0.320,
        "slg": 0.400,
        "k_rate": 0.22,
        "hr_rate": 0.03,
        "bb_rate": 0.08,
        "source": "pybaseball_pending",
    }

    try:
        from pybaseball import batting_stats, pitching_stats

        # Fetch batting stats
        try:
            batting = batting_stats(2025, qual=100)
            team_bat = batting[batting["Team"] == team_abbr]
            if not team_bat.empty:
                tb = team_bat.iloc[0]
                result = {
                    "team": team_abbr,
                    "runs_per_game": float(tb.get("R", 4.5) / max(tb.get("G", 162), 1) * 9),
                    "obp": float(tb.get("OBP", 0.320)),
                    "slg": float(tb.get("SLG", 0.400)),
                    "k_rate": float(tb.get("SO", 1400) / max(tb.get("PA", 6200), 1)),
                    "hr_rate": float(tb.get("HR", 200) / max(tb.get("AB", 5400), 1)),
                    "bb_rate": float(tb.get("BB", 550) / max(tb.get("PA", 6200), 1)),
                    "source": "pybaseball",
                }
        except Exception as e:
            print(f"    [pybaseball] Batting stats error: {e}")

        # Fetch pitching stats
        try:
            pitching = pitching_stats(2025, qual=10)
            team_pitch = pitching[pitching["Team"] == team_abbr]
            if not team_pitch.empty:
                tp = team_pitch.iloc[0]
                result["runs_allowed"] = float(tp.get("R", 650) / max(tp.get("G", 162), 1) * 9)
                result["era"] = float(tp.get("ERA", 4.00))
                result["whip"] = float(tp.get("WHIP", 1.25))
        except Exception as e:
            print(f"    [pybaseball] Pitching stats error: {e}")

        if result.get("source") == "pybaseball_pending":
            result["source"] = "pybaseball"
        return result
    except Exception as e:
        print(f"    [pybaseball] Error: {e}")
        return _fallback_mlb_stats(team_abbr)


def _fallback_mlb_stats(team_abbr: str) -> Dict[str, Any]:
    """Fallback stats when pybaseball is unavailable."""
    return {
        "team": team_abbr,
        "runs_per_game": 4.5,
        "runs_allowed": 4.0,
        "era": 4.00,
        "whip": 1.25,
        "obp": 0.320,
        "slg": 0.400,
        "k_rate": 0.22,
        "hr_rate": 0.03,
        "bb_rate": 0.08,
        "source": "fallback",
    }


# ---------------------------------------------------------------------------
# EVENT ID RESOLVER (unified resolver for all sports)
# ---------------------------------------------------------------------------

@dataclass
class EventIDResolver:
    """
    Resolves a (home_team, away_team) pair to the correct API event ID.
    Uses The Odds API as primary source, with local cache fallback.
    """
    odds_client: Any = field(default_factory=OddsAPIClient)
    _cache: Dict[str, str] = field(default_factory=dict)

    # KBO Team name normalization
    KBO_TEAMS: Dict[str, str] = field(default_factory=lambda: {
        "doosan bears": "Doosan Bears", "doosan": "Doosan Bears",
        "lg twins": "LG Twins", "lg": "LG Twins",
        "kiwoom heroes": "Kiwoom Heroes", "kiwoom": "Kiwoom Heroes",
        "kt wiz": "KT Wiz", "kt": "KT Wiz",
        "ssg landers": "SSG Landers", "ssg": "SSG Landers",
        "lotte giants": "Lotte Giants", "lotte": "Lotte Giants",
        "samsung lions": "Samsung Lions", "samsung": "Samsung Lions",
        "nc dinos": "NC Dinos", "nc": "NC Dinos",
        "kia tigers": "KIA Tigers", "kia": "KIA Tigers",
        "hanwha eagles": "Hanwha Eagles", "hanwha": "Hanwha Eagles",
        "두산 베어스": "Doosan Bears", "키움 히어로즈": "Kiwoom Heroes",
        "기아 타이거즈": "KIA Tigers", "한화 이글스": "Hanwha Eagles",
    })

    # Euro Basketball aliases
    EURO_TEAMS: Dict[str, str] = field(default_factory=lambda: {
        "olympiacos": "Olympiacos", "panathinaikos": "Panathinaikos",
        "real madrid": "Real Madrid", "fc barcelona": "FC Barcelona",
        "anadolu efes": "Anadolu Efes", "fenerbahce": "Fenerbahce",
        "cska moscow": "CSKA Moscow", "barca": "FC Barcelona",
    })

    def normalize_team(self, team: str, sport: str = "") -> str:
        """Normalize team name based on sport."""
        t = team.strip().lower()
        if sport == "kbo":
            return self.KBO_TEAMS.get(t, team)
        return self.EURO_TEAMS.get(t, team)

    def resolve(self, home: str, away: str, sport: str = "soccer",
                league: str = "") -> Optional[str]:
        """Resolve event ID. Returns None if not found."""
        cache_key = f"{home.lower()}|{away.lower()}|{sport}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        sport_key = OddsAPIClient.SPORT_KEYS.get(
            league.lower(), OddsAPIClient.SPORT_KEYS.get(sport.lower(), "")
        )
        if not sport_key or not self.odds_client.available():
            return None

        event_id = self.odds_client.resolve_event_id(home, away, sport_key)
        if event_id:
            self._cache[cache_key] = event_id
        return event_id


# ---------------------------------------------------------------------------
# SPORT ROUTING DICTIONARY
# ---------------------------------------------------------------------------

SPORT_CATEGORIES: Dict[str, list] = {
    "mlb":       ["mlb_game", "mlb_prop", "mlb_nrfi", "mlb_ks", "mlb_hrs"],
    "baseball":  ["mlb_game", "mlb_prop", "mlb_nrfi", "mlb_ks", "mlb_hrs"],
    "kbo":       ["kbo_game", "kbo_prop"],
    "basketball":           ["game", "1h", "q1", "prop"],
    "kbl":                  ["game", "1h", "q1", "prop"],
    "euroleague":           ["game", "1h", "q1", "prop"],
    "eurocup":              ["game", "1h", "q1", "prop"],
    "liga acb":             ["game", "1h", "q1", "prop"],
    "acb":                  ["game", "1h", "q1", "prop"],
    "euro basketball":      ["game", "1h", "q1", "prop"],
    "european basketball":  ["game", "1h", "q1", "prop"],
    "eurobasket":           ["game", "1h", "q1", "prop"],
    "soccer":    ["soccer_ml", "soccer_goals", "soccer_team_totals",
                  "soccer_corners", "soccer_btts", "soccer_anytime_scorer"],
    "football":  ["soccer_ml", "soccer_goals", "soccer_team_totals",
                  "soccer_corners", "soccer_btts", "soccer_anytime_scorer"],
    "premier league": ["soccer_ml", "soccer_goals", "soccer_team_totals",
                       "soccer_corners", "soccer_btts", "soccer_anytime_scorer"],
    "epl":      ["soccer_ml", "soccer_goals", "soccer_team_totals",
                 "soccer_corners", "soccer_btts", "soccer_anytime_scorer"],
    "bundesliga":   ["soccer_ml", "soccer_goals", "soccer_team_totals",
                     "soccer_corners", "soccer_btts", "soccer_anytime_scorer"],
    "la liga":      ["soccer_ml", "soccer_goals", "soccer_team_totals",
                     "soccer_corners", "soccer_btts", "soccer_anytime_scorer"],
    "serie a":      ["soccer_ml", "soccer_goals", "soccer_team_totals",
                     "soccer_corners", "soccer_btts", "soccer_anytime_scorer"],
    "ligue 1":      ["soccer_ml", "soccer_goals", "soccer_team_totals",
                     "soccer_corners", "soccer_btts", "soccer_anytime_scorer"],
    "champions league": ["soccer_ml", "soccer_goals", "soccer_team_totals",
                         "soccer_corners", "soccer_btts", "soccer_anytime_scorer"],
    "europa league":  ["soccer_ml", "soccer_goals", "soccer_team_totals",
                       "soccer_corners", "soccer_btts", "soccer_anytime_scorer"],
    "kazakhstan":     ["soccer_ml", "soccer_goals", "soccer_team_totals",
                       "soccer_corners", "soccer_btts"],
    "npl":            ["soccer_ml", "soccer_goals", "soccer_btts"],
}

# ---------------------------------------------------------------------------
# LOW-LIQUIDITY SOCCER LEAGUES (no props)
# ---------------------------------------------------------------------------
LOW_LIQUIDITY_LEAGUES = {
    "kazakhstan", "npl", "belarus", "mongolia", "laos", "brunei",
    "tajikistan", "turkmenistan", "kyrgyzstan", "fiji", "samoa",
    "vanuatu", "papua new guinea", "solomon islands",
}


# ============================================================================
# SOCCER: ANYTIME GOALSCORER WITH LOW-LIQUIDITY HANDLING
# ============================================================================

def run_soccer_anytime_scorer(home_team: str, away_team: str,
                              league: str = "", market_line: float = 2.5,
                              market_total: float = 2.5,
                              anytime_scorer_player: str = "") -> Dict[str, Any]:
    """
    Soccer Anytime Goalscorer analysis with low-liquidity league error handling.

    Low-liquidity leagues (NPL, Kazakhstan, etc.) may not have player prop lines.
    This function gracefully degrades to total/btts analysis when props are unavailable.
    """
    league_lower = league.lower() if league else ""
    is_low_liquidity = league_lower in LOW_LIQUIDITY_LEAGUES

    print(f"\n=== SOCCER (Anytime Goalscorer): {home_team} vs {away_team} ===")
    if is_low_liquidity:
        print(f"    [WARNING] Low-liquidity league detected: '{league}'")
        print(f"    Anytime Goalscorer props likely UNAVAILABLE for this league.")
        print(f"    Falling back to ML/Total/BTTS analysis.\n")

    # Try to import and run soccer predictor
    try:
        from models.soccer_predictor import SoccerPredictor
        predictor = SoccerPredictor(league=league or "Premier League")
        result = predictor.predict(
            features=None, model=None,
            home_team=home_team, away_team=away_team,
            market_line=market_line, market_total=market_total,
        )
        game = result.get("game", {})
        print(f"    Projected Score: {home_team} {game.get('projected_home_goals', 0):.2f} "
              f"- {away_team} {game.get('projected_away_goals', 0):.2f}")
        print(f"    Total Goals: {game.get('projected_total_goals', 0):.2f}")

        # Anytime Goalscorer (if not low-liquidity and player provided)
        if anytime_scorer_player and not is_low_liquidity:
            # TODO: Wire up The Odds API for player props
            # Example:
            #   event_id = resolver.resolve(home_team, away_team, "soccer")
            #   if event_id:
            #       odds = odds_client.fetch_odds(event_id, markets="player_goals_anytime")
            #       player_line = extract_player_line(odds, anytime_scorer_player)
            print(f"    Anytime Goalscorer: {anytime_scorer_player}")
            print(f"    [TODO] Wire up The Odds API for player props market")
        elif is_low_liquidity:
            print(f"    [SKIP] Anytime Goalscorer not available for {league}")

        return result
    except ImportError:
        print(f"    [ERROR] Soccer predictor not available.")
        return {}


# ============================================================================
# MLB: NRFI (No Run First Inning) / STRIKEOUTS / HOME RUNS
# ============================================================================

def run_mlb_prop_market(home_team: str, away_team: str,
                        markets: List[str] = None) -> Dict[str, Any]:
    """
    Run MLB prop market predictions: NRFI, Strikeouts, Home Runs.

    Uses pybaseball for advanced stats and The Odds API for live lines.

    Markets:
        - nrfi: No Run First Inning probability
        - strikeouts: Team/pitcher K props
        - home_runs: Team/pitcher HR props
    """
    markets = markets or ["mlb_game"]
    print(f"\n=== MLB PROP MARKETS: {home_team} vs {away_team} ===\n")

    # Fetch team stats via pybaseball
    home_stats = get_mlb_team_stats(home_team)
    away_stats = get_mlb_team_stats(away_team)
    print(f"    Home Stats Source: {home_stats.get('source', 'unknown')}")
    print(f"    Away Stats Source: {away_stats.get('source', 'unknown')}")

    result = {"home_team": home_team, "away_team": away_team, "markets": {}}

    for market in markets:
        ml = market.lower().replace("mlb_", "").strip()
        if ml in ("nrfi", "yrfi"):
            result["markets"]["nrfi"] = _compute_nrfi(home_stats, away_stats)
        elif ml in ("ks", "strikeouts", "k"):
            result["markets"]["strikeouts"] = _compute_strikeouts(home_stats, away_stats)
        elif ml in ("hrs", "home_runs", "hr"):
            result["markets"]["home_runs"] = _compute_home_runs(home_stats, away_stats)

    # Also run full game prediction
    try:
        from models.baseball_predictor import BaseballPredictor
        predictor = BaseballPredictor()
        data = predictor.load_data(league="MLB", home_team=home_team, away_team=away_team)
        features = predictor.feature_engineering(data)
        game_result = predictor.predict(features, None, home_team, away_team, "MLB")
        result["game"] = game_result.get("game", {})

        game = result["game"]
        print(f"    Projected Total: {game.get('projected_total_runs', 0):.2f}")
        print(f"    Home Win Prob: {game.get('home_win_probability', 0):.1%}")
    except Exception as e:
        print(f"    [ERROR] MLB game prediction failed: {e}")

    return result


def _compute_nrfi(home_stats: Dict, away_stats: Dict) -> Dict[str, Any]:
    """Compute No Run First Inning probability."""
    # NRFI depends on: starting pitcher K rate, BB rate, opponent contact quality
    home_era = home_stats.get("era", 4.0)
    away_era = away_stats.get("era", 4.2)
    home_k_rate = home_stats.get("k_rate", 0.22)
    away_k_rate = away_stats.get("k_rate", 0.21)

    # Base NRFI probability: ~53% for league average
    base_nrfi = 0.53
    era_adj = ((5.0 - home_era) + (5.0 - away_era)) * 0.015
    k_adj = ((home_k_rate - 0.22) + (away_k_rate - 0.22)) * 0.5

    nrfi_prob = base_nrfi + era_adj + k_adj
    nrfi_prob = max(0.30, min(0.75, nrfi_prob))

    edge = nrfi_prob - 0.50
    conf = confidence_score(edge * 100, volatility=0.60)
    lean = "NRFI" if nrfi_prob > 0.55 else "YRFI"
    rec = bet_recommendation(conf, "mlb_nrfi")

    print(f"    NRFI Probability: {nrfi_prob:.1%} | Lean: {lean} | Conf: {conf:.1f}%")

    return {
        "probability": round(nrfi_prob, 4),
        "lean": lean,
        "confidence": round(conf, 1),
        "recommendation": rec,
    }


def _compute_strikeouts(home_stats: Dict, away_stats: Dict) -> Dict[str, Any]:
    """Compute team strikeout projections."""
    home_k_rate = home_stats.get("k_rate", 0.22)
    away_k_rate = away_stats.get("k_rate", 0.21)
    # Approximate team Ks per game from K rate
    home_k_proj = home_k_rate * 38 * 0.5  # ~38 PA per game half
    away_k_proj = away_k_rate * 38 * 0.5

    # TODO: Wire up pybaseball.pitching_stats() for actual pitcher K projections
    # Example:
    #   from pybaseball import pitching_stats
    #   sp_stats = pitching_stats(2025, qual=0)
    #   home_sp_k9 = sp_stats[sp_stats["Team"] == home_abbr]["K/9"].median()
    #   away_sp_k9 = sp_stats[sp_stats["Team"] == away_abbr]["K/9"].median()

    print(f"    Home Team K Projection: {home_k_proj:.1f}")
    print(f"    Away Team K Projection: {away_k_proj:.1f}")

    return {
        "home_k_projected": round(home_k_proj, 1),
        "away_k_projected": round(away_k_proj, 1),
    }


def _compute_home_runs(home_stats: Dict, away_stats: Dict) -> Dict[str, Any]:
    """Compute team home run projections."""
    home_hr_rate = home_stats.get("hr_rate", 0.03)
    away_hr_rate = away_stats.get("hr_rate", 0.03)
    home_hr_proj = home_hr_rate * 38 * 0.5
    away_hr_proj = away_hr_rate * 38 * 0.5

    # TODO: Wire up pybaseball.batting_stats() for actual batter HR rates
    # Example:
    #   from pybaseball import batting_stats
    #   batters = batting_stats(2025, qual=100)
    #   team_batters = batters[batters["Team"] == home_abbr]
    #   home_hr_proj = team_batters["HR"].sum() / team_batters["G"].median()

    print(f"    Home Team HR Projection: {home_hr_proj:.1f}")
    print(f"    Away Team HR Projection: {away_hr_proj:.1f}")

    return {
        "home_hr_projected": round(home_hr_proj, 1),
        "away_hr_projected": round(away_hr_proj, 1),
    }


# ============================================================================
# SPORT-SPECIFIC RUNNERS
# ============================================================================

def run_basketball_game(home_team: str, away_team: str, league: str = "EuroLeague",
                        market_line: float = 0.0, current_line: float = 0.0,
                        open_line: float = 0.0) -> Dict[str, Any]:
    """Run basketball prediction using the FIBA/European module."""
    print(f"\n{'='*60}")
    print(f"BASKETBALL ({league}) MATCHUP: {home_team} vs {away_team}")
    print('='*60 + '\n')
    try:
        from models.basketball_predictor import BasketballPredictor
        predictor = BasketballPredictor(league=league)
        result = predictor.predict(
            features=None, model=None,
            home_team=home_team, away_team=away_team,
            market_line=market_line,
            current_line=current_line or market_line,
            open_line=open_line or market_line,
        )
        full_game = result.get("full_game", {})
        print(f"Projected: {home_team} {full_game.get('projected_home_score', 0):.1f}"
              f" - {away_team} {full_game.get('projected_away_score', 0):.1f}")
        print(f"Win Prob: {home_team} {full_game.get('probability', 0):.1%}")
        print(f"Lean: {full_game.get('lean', 'N/A')}")

        out_dir = Path("output/basketball")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{home_team.replace(' ', '_')}_vs_{away_team.replace(' ', '_')}.json"
        with open(out_path, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nResults saved to: {out_path}")
        return result
    except ImportError as e:
        print(f"Error: Basketball module not available. {e}")
        return {}
    except Exception as e:
        print(f"Error: {e}")
        return {}


def run_soccer_game(home_team: str, away_team: str, league: str = "Premier League",
                    market_line: float = 0.0, market_total: float = 2.5,
                    anytime_scorer: str = "") -> Dict[str, Any]:
    """Run soccer prediction. Handles Anytime Goalscorer with low-liquidity check."""
    # Check if player prop requested
    if anytime_scorer:
        return run_soccer_anytime_scorer(
            home_team, away_team, league, market_line, market_total, anytime_scorer
        )

    print(f"\n{'='*60}")
    print(f"SOCCER ({league}) MATCHUP: {home_team} vs {away_team}")
    print('='*60 + '\n')
    try:
        from models.soccer_predictor import SoccerPredictor
        predictor = SoccerPredictor(league=league)
        result = predictor.predict(
            features=None, model=None,
            home_team=home_team, away_team=away_team,
            market_line=market_line, market_total=market_total,
        )
        game = result.get("game", {})
        print(f"Projected: {home_team} {game.get('projected_home_goals', 0):.2f}"
              f" - {away_team} {game.get('projected_away_goals', 0):.2f}")

        # Corner projection
        corner_proj = result.get("corner_projection")
        if corner_proj is not None:
            print(f"Corner Projection: {corner_proj:.1f}")
            corners_over_85 = result.get("corners_analysis", {}).get("over_85_prob")
            corners_over_95 = result.get("corners_analysis", {}).get("over_95_prob")
            corners_over_105 = result.get("corners_analysis", {}).get("over_105_prob")
            if corners_over_105 is not None:
                print(f"  Over 8.5: {corners_over_85:.1%} | Over 9.5: {corners_over_95:.1%} | Over 10.5: {corners_over_105:.1%}")

        # Handle Anytime Goalscorer (graceful degradation for low-liquidity)
        league_lower = league.lower() if league else ""
        if league_lower in LOW_LIQUIDITY_LEAGUES:
            print(f"    [INFO] Low-liquidity league: '{league}' — props unavailable")

        print(f"\nMatch Outcome:")
        print(f"  {home_team} Win: {game.get('home_win_prob', 0):.1%}")
        print(f"  Draw: {game.get('draw_prob', 0):.1%}")
        print(f"  {away_team} Win: {game.get('away_win_prob', 0):.1%}")

        out_dir = Path("output/soccer")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{home_team.replace(' ', '_')}_vs_{away_team.replace(' ', '_')}.json"
        with open(out_path, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nResults saved to: {out_path}")
        return result
    except ImportError as e:
        print(f"Error: Soccer module not available. {e}")
        return {}
    except Exception as e:
        print(f"Error: {e}")
        return {}


def run_baseball_game(home_team: str, away_team: str, league: str = "MLB",
                      markets: List[str] = None) -> Dict[str, Any]:
    """Run baseball prediction (MLB or KBO). Supports prop markets for MLB."""
    print(f"\n{'='*60}")
    print(f"BASEBALL ({league.upper()}) MATCHUP: {home_team} vs {away_team}")
    print('='*60 + '\n')

    if markets and league.upper() == "MLB":
        return run_mlb_prop_market(home_team, away_team, markets)

    try:
        from models.baseball_predictor import BaseballPredictor
        predictor = BaseballPredictor()
        data = predictor.load_data(league=league, home_team=home_team, away_team=away_team)
        features = predictor.feature_engineering(data)
        result = predictor.predict(features, None, home_team, away_team, league=league)

        game = result.get("game", {})
        print(f"Projected Total: {game.get('projected_total_runs', 0):.2f}")
        print(f"Run Diff: {game.get('projected_run_differential', 0):+.2f}")
        print(f"Win Prob: {home_team} {game.get('home_win_probability', 0):.1%}")

        out_dir = Path("output/baseball")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{home_team.replace(' ', '_')}_vs_{away_team.replace(' ', '_')}.json"
        with open(out_path, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nResults saved to: {out_path}")
        return result
    except ImportError as e:
        print(f"Error: Baseball module not available. {e}")
        return {}
    except Exception as e:
        print(f"Error: {e}")
        return {}


# ============================================================================
# MAIN CLI
# ============================================================================

def main():
    """Main entry point for the unified CLI"""
    parser = argparse.ArgumentParser(
        description="Predict matches across multiple sports with a single command."
    )
    parser.add_argument("sport", nargs="?", help="Sport (soccer, basketball, mlb, kbo)")
    parser.add_argument("home", nargs="?", help="Home team")
    parser.add_argument("away", nargs="?", help="Away team")
    parser.add_argument("league", nargs="?", help="League (e.g. Bundesliga, Kazakhstan)")
    parser.add_argument("--markets", "-m", nargs="+",
                        help="MLB prop markets (nrfi strikeouts home_runs)")
    parser.add_argument("--anytime-scorer", "-ags", type=str, default="",
                        help="Anytime Goalscorer player name (soccer)")
    parser.add_argument("--api-key", "-k",
                        help="The-Odds-API key (or set ODDS_API_KEY env var)")
    parser.add_argument("--batch", "-b", action="store_true",
                        help="Batch mode: predict all upcoming matches")
    parser.add_argument("--upcoming", "-u", action="store_true",
                        help="Predict all upcoming matches for the sport")

    args = parser.parse_args()

    if not args.sport or not args.home or not args.away:
        parser.print_help()
        print("\nExamples:")
        print("  python predict_match.py soccer \"Astana\" \"Irtysh Pavlador\" Kazakhstan")
        print("  python predict_match.py mlb \"NYY\" \"BOS\" --markets nrfi strikeouts")
        print("  python predict_match.py kbo \"Doosan Bears\" \"LG Twins\"")
        print("  python predict_match.py soccer \"Liverpool\" \"Aston Villa\" --anytime-scorer 'Salah'")
        sys.exit(1)

    sport = args.sport.lower()
    home = args.home
    away = args.away
    league = args.league or ""

    # Initialize Odds API client
    odds_client = OddsAPIClient(api_key=args.api_key or "")

    # Resolve sport categories
    categories = SPORT_CATEGORIES.get(sport, [])
    if not categories:
        print(f"\nError: Unknown sport '{sport}'")
        print("Accepted:", ", ".join(sorted(SPORT_CATEGORIES.keys())))
        sys.exit(1)

    # Determine canonical sport
    if "mlb_game" in categories or "kbo_game" in categories:
        canonical = "baseball"
    elif "game" in categories or "q1" in categories:
        canonical = "basketball"
    elif "soccer_ml" in categories:
        canonical = "soccer"
    else:
        canonical = sport

    print(f"[PREDICT] {sport.upper()} ({canonical}) - {home} vs {away}")
    if league:
        print(f"  League: {league}")
    print(f"  Markets: {categories}\n")

    # Resolve event ID via The Odds API
    if odds_client.available():
        resolver = EventIDResolver(odds_client=odds_client)
        event_id = resolver.resolve(home, away, canonical, league)
        if event_id:
            print(f"  [OddsAPI] Resolved Event ID: {event_id}")
        else:
            print(f"  [OddsAPI] No event found for this matchup")
    else:
        print(f"  [OddsAPI] Not configured (set ODDS_API_KEY env var)\n")

    # Route to appropriate handler
    if canonical == "basketball":
        run_basketball_game(home, away, league=league or "EuroLeague")
    elif canonical == "soccer":
        run_soccer_game(home, away, league=league,
                        anytime_scorer=args.anytime_scorer)
    elif canonical == "baseball":
        kbo_keywords = {"kbo", "doosan", "kiwoom", "kia tigers", "hanwha",
                        "ssg", "nc dinos", "samsung", "lotte", "kt wiz", "lg twins"}
        league_code = "KBO" if sport == "kbo" or home.lower() in kbo_keywords or away.lower() in kbo_keywords else (league or "MLB")
        run_baseball_game(home, away, league=league_code, markets=args.markets)
    else:
        print(f"\nError: Unsupported canonical sport '{canonical}'")
        sys.exit(1)


if __name__ == "__main__":
    main()