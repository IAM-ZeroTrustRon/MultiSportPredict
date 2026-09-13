#!/usr/bin/env python3
"""
MultiSportEngine — Production Orchestration Pipeline
=====================================================
Single-file consolidated prediction engine for soccer, basketball, baseball,
and tennis. Integrates xG/Poisson models, ELO-based tennis, live odds
ingestion, and Discord telemetry.

Usage:
    python multi_sport_engine.py soccer "Atletico Ottawa" "Cavalry FC" "CPL" --push-discord
    python multi_sport_engine.py basketball "Real Madrid" "FC Barcelona" "EuroLeague" --push-discord
    python multi_sport_engine.py mlb "NYY" "BOS" --markets nrfi strikeouts --push-discord
    python multi_sport_engine.py tennis "Djokovic" "Alcaraz" "Wimbledon" --push-discord
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ============================================================================
# SECTION 1 — MATH UTILITIES
# ============================================================================

def sigmoid(x: float) -> float:
    x = max(-500, min(500, x))
    return 1 / (1 + math.exp(-x))

def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))

def to_num(v: Any, default: float = 0.0) -> float:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return default
    try:
        if isinstance(v, str):
            v = v.strip().replace(",", "")
            if v == "":
                return default
        return float(v)
    except (ValueError, TypeError):
        return default

def poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 0.0 if k > 0 else 1.0
    if k < 0:
        return 0.0
    try:
        return math.exp(-lam + k * math.log(lam) - math.lgamma(k + 1))
    except (ValueError, OverflowError):
        return 0.0

def poisson_over_prob(lam: float, line: float) -> float:
    n = int(math.floor(line))
    if abs(line - n) < 1e-9:
        return 1 - sum(poisson_pmf(k, lam) for k in range(0, n + 1))
    return 1 - sum(poisson_pmf(k, lam) for k in range(0, n + 1))

def poisson_at_least_one(lam: float) -> float:
    return 1 - math.exp(-lam)

def confidence_score(edge: float, volatility: float = 0.5) -> float:
    return min(100, max(0, 50 + edge * 10 / volatility))

def bet_recommendation(conf: float) -> str:
    if conf >= 75:
        return "STRONG BET"
    elif conf >= 60:
        return "BET"
    elif conf >= 50:
        return "LEAN"
    return "PASS"

# ============================================================================
# SECTION 2 — ODDS API CLIENT
# ============================================================================

class OddsAPIClient:
    """Ingests real-time odds via The Odds API (best-effort, never blocks pipeline)."""
    BASE_URL = "https://api.the-odds-api.com/v4"
    SPORT_KEYS: Dict[str, str] = {
        "soccer": "soccer_epl", "premier league": "soccer_epl", "epl": "soccer_epl",
        "bundesliga": "soccer_germany_bundesliga", "la liga": "soccer_spain_la_liga",
        "serie a": "soccer_italy_serie_a", "ligue 1": "soccer_france_ligue_one",
        "champions league": "soccer_uefa_champs_league", "kazakhstan": "soccer_kazakhstan_premier_league",
        "mlb": "baseball_mlb", "kbo": "baseball_kbo",
        "basketball": "basketball_nba", "euroleague": "basketball_euroleague",
        "nba": "basketball_nba", "kbl": "basketball_kbl",
        "tennis": "tennis_atp_wimbledon", "atp": "tennis_atp_wimbledon",
        "wta": "tennis_wta_wimbledon",
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ODDS_API_KEY", "04d2ee61b50ba34a748e5d12c3b5a1cb")
        self.available = bool(self.api_key)

    def fetch_odds(self, sport: str, market: str = "h2h") -> List[Dict]:
        if not self.available:
            return []
        sport_key = self.SPORT_KEYS.get(sport.lower(), sport)
        try:
            import requests
            url = f"{self.BASE_URL}/sports/{sport_key}/odds"
            params = {"apiKey": self.api_key, "regions": "us", "markets": market, "oddsFormat": "american"}
            r = requests.get(url, params=params, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"    [OddsAPI] Skipped (not available for this league): {e}")
            return []

# ============================================================================
# SECTION 3 — SOCCER PREDICTOR
# ============================================================================

# Team-specific xG + shot metrics for dynamic predictions.
# Values are league-agnostic placeholders; replace/tune as your data pipeline improves.
# Unknown teams get name-derived differentiation so different matchups produce unique outputs.
SOCCER_TEAM_STATS: Dict[str, Dict[str, float]] = {
    # Known team stats
    "VPS": {"xg_for": 1.85, "xg_against": 1.10, "sot": 5.2, "tempo": 0.40},
    "SJK": {"xg_for": 1.50, "xg_against": 1.30, "sot": 4.1, "tempo": 0.20},
    # World Cup 2026 Quarterfinalists
    "Norway": {"xg_for": 1.95, "xg_against": 1.20, "sot": 5.1, "tempo": 0.35},
    "England": {"xg_for": 2.10, "xg_against": 0.95, "sot": 5.8, "tempo": 0.45},
    "Argentina": {"xg_for": 2.25, "xg_against": 0.80, "sot": 6.2, "tempo": 0.50},
    "Switzerland": {"xg_for": 1.30, "xg_against": 1.10, "sot": 3.9, "tempo": 0.15},
    # Common European teams
    "Liverpool": {"xg_for": 2.05, "xg_against": 0.90, "sot": 5.5, "tempo": 0.50},
    "Manchester City": {"xg_for": 2.20, "xg_against": 0.85, "sot": 6.0, "tempo": 0.55},
    "Arsenal": {"xg_for": 1.90, "xg_against": 0.95, "sot": 5.2, "tempo": 0.45},
    "Chelsea": {"xg_for": 1.80, "xg_against": 1.10, "sot": 4.8, "tempo": 0.40},
    "Manchester United": {"xg_for": 1.65, "xg_against": 1.20, "sot": 4.5, "tempo": 0.35},
    "Tottenham": {"xg_for": 1.75, "xg_against": 1.15, "sot": 4.7, "tempo": 0.40},
    "Aston Villa": {"xg_for": 1.60, "xg_against": 1.25, "sot": 4.3, "tempo": 0.35},
    "Newcastle": {"xg_for": 1.70, "xg_against": 1.10, "sot": 4.6, "tempo": 0.38},
    "Bayern Munich": {"xg_for": 2.30, "xg_against": 0.80, "sot": 6.5, "tempo": 0.55},
    "Borussia Dortmund": {"xg_for": 1.85, "xg_against": 1.05, "sot": 5.0, "tempo": 0.45},
    "Barcelona": {"xg_for": 2.10, "xg_against": 0.95, "sot": 5.8, "tempo": 0.50},
    "Real Madrid": {"xg_for": 2.00, "xg_against": 0.90, "sot": 5.5, "tempo": 0.48},
    "Atletico Madrid": {"xg_for": 1.55, "xg_against": 1.00, "sot": 4.2, "tempo": 0.30},
    "Paris Saint-Germain": {"xg_for": 2.15, "xg_against": 0.85, "sot": 5.7, "tempo": 0.50},
    "Inter Milan": {"xg_for": 1.80, "xg_against": 1.00, "sot": 4.8, "tempo": 0.40},
    "AC Milan": {"xg_for": 1.70, "xg_against": 1.10, "sot": 4.5, "tempo": 0.38},
    "Juventus": {"xg_for": 1.60, "xg_against": 1.00, "sot": 4.3, "tempo": 0.35},
    "Ajax": {"xg_for": 1.95, "xg_against": 1.10, "sot": 5.2, "tempo": 0.45},
    # Swedish clubs
    "FBK Karlstad": {"xg_for": 1.65, "xg_against": 1.25, "sot": 4.8, "tempo": 0.30},
    "IF Karlstad": {"xg_for": 1.45, "xg_against": 1.40, "sot": 4.0, "tempo": 0.10},
    # Finnish clubs
    "FC Haka": {"xg_for": 1.75, "xg_against": 1.15, "sot": 5.2, "tempo": 0.40},
    "JaPS": {"xg_for": 1.30, "xg_against": 1.55, "sot": 3.5, "tempo": -0.10},
    "KaPa": {"xg_for": 1.40, "xg_against": 1.50, "sot": 3.8, "tempo": 0.00},
    "KTP Kotka": {"xg_for": 1.60, "xg_against": 1.30, "sot": 4.5, "tempo": 0.20},
}

def _soccer_team_stats(team_name: str) -> Dict[str, float]:
    """Best-effort lookup for team metrics with name-derived fallback."""
    SOCCER_DEFAULT = {"xg_for": 1.40, "xg_against": 1.40, "sot": 4.0, "tempo": 0.20}

    if not team_name:
        return dict(SOCCER_DEFAULT)

    key = team_name.strip()

    # Exact match first
    if key in SOCCER_TEAM_STATS:
        return SOCCER_TEAM_STATS[key]

    # Case-insensitive / partial match fallback
    key_l = key.lower()
    for known, stats in SOCCER_TEAM_STATS.items():
        known_l = known.lower()
        if known_l == key_l or known_l in key_l or key_l in known_l:
            return stats

    # --- DIFFERENTIATION FIX: Derive unique stats from team name hash ---
    # Uses Python's hash() to generate a deterministic seed from the team name,
    # then produces unique but realistic xG values so different teams get different predictions.
    name_hash = sum(ord(c) * (i + 1) for i, c in enumerate(key_l)) % 1000
    seed = name_hash / 1000.0  # value in [0.0, 1.0)

    # Generate differentiated stats within realistic ranges:
    # xG for: 0.80 - 2.20 range
    # xG against: 0.80 - 1.80 range
    # SOT: 2.5 - 6.5 range
    # Tempo: -0.10 - 0.60 range
    derived = {
        "xg_for": round(0.80 + seed * 1.40, 2),
        "xg_against": round(1.80 - seed * 1.00, 2),  # inversely correlated with xG for
        "sot": round(2.50 + seed * 4.00, 1),
        "tempo": round(-0.10 + seed * 0.70, 2),
    }
    return derived

LEAGUE_CONFIGS: Dict[str, Dict] = {

    "Premier League":     {"goal_variance": 1.10, "avg_goals": 2.85, "home_adv": 0.35, "draw_rate": 0.25},
    "La Liga":            {"goal_variance": 1.05, "avg_goals": 2.65, "home_adv": 0.40, "draw_rate": 0.27},
    "Bundesliga":         {"goal_variance": 1.15, "avg_goals": 3.10, "home_adv": 0.30, "draw_rate": 0.23},
    "Serie A":            {"goal_variance": 1.00, "avg_goals": 2.55, "home_adv": 0.38, "draw_rate": 0.28},
    "Ligue 1":            {"goal_variance": 1.08, "avg_goals": 2.60, "home_adv": 0.35, "draw_rate": 0.26},
    "World Cup":          {"goal_variance": 1.00, "avg_goals": 2.50, "home_adv": 0.20, "draw_rate": 0.30},
    "Canadian Premier League": {"goal_variance": 1.00, "avg_goals": 2.60, "home_adv": 0.30, "draw_rate": 0.27},
    "default":            {"goal_variance": 1.00, "avg_goals": 2.70, "home_adv": 0.35, "draw_rate": 0.26},
}

def get_league_config(league: str) -> Dict:
    return LEAGUE_CONFIGS.get(league, LEAGUE_CONFIGS["default"])

def estimate_team_goals(xg_for: float, sot: float, tempo: float, home: int,
                        miss_att: int, miss_cre: int,
                        opp_xg_against: float, opp_miss_cb: int, opp_miss_gk: int) -> float:
    lam = 0.55 * xg_for + 0.30 * opp_xg_against + 0.15 * sot
    lam += 0.10 * tempo + 0.10 * home
    lam += -0.15 * miss_att - 0.10 * miss_cre
    lam += 0.12 * (opp_miss_cb + opp_miss_gk)
    return max(0.20, lam)

def estimate_btts_prob(home_lam: float, away_lam: float,
                       home_btts: float, away_btts: float) -> float:
    p_home = poisson_at_least_one(max(0.25, home_lam))
    p_away = poisson_at_least_one(max(0.25, away_lam))
    structural = sigmoid((home_btts + away_btts) / 2.0)
    return clamp(0.45 * structural + 0.55 * (p_home * p_away))

def predict_soccer(home: str, away: str, league: str = "default",
                   market_total: float = 2.5, **kwargs) -> Dict[str, Any]:
    """Full soccer match prediction using Bivariate Poisson / xG model."""
    cfg = get_league_config(league)

    # Fill in xG + shot metrics from team lookup unless explicitly overridden via kwargs.
    h_team = _soccer_team_stats(home)
    a_team = _soccer_team_stats(away)

    h_xgf    = kwargs.get("home_xg_for", h_team["xg_for"])
    h_xga    = kwargs.get("home_xg_against", h_team["xg_against"])
    h_sot    = kwargs.get("home_sot", h_team["sot"])
    h_tempo  = kwargs.get("home_tempo", h_team["tempo"])
    h_miss_a = kwargs.get("home_missing_attacker", 0)
    h_miss_c = kwargs.get("home_missing_creator", 0)
    h_miss_d = kwargs.get("home_missing_cb", 0)
    h_miss_g = kwargs.get("home_missing_gk", 0)
    h_goals  = kwargs.get("home_goals_for", 1.7)
    h_clean  = kwargs.get("home_clean_sheets", 4)

    a_xgf    = kwargs.get("away_xg_for", a_team["xg_for"])
    a_xga    = kwargs.get("away_xg_against", a_team["xg_against"])
    a_sot    = kwargs.get("away_sot", a_team["sot"])
    a_tempo  = kwargs.get("away_tempo", a_team["tempo"])
    a_miss_a = kwargs.get("away_missing_attacker", 0)
    a_miss_c = kwargs.get("away_missing_creator", 0)
    a_miss_d = kwargs.get("away_missing_cb", 0)
    a_miss_g = kwargs.get("away_missing_gk", 0)
    a_goals  = kwargs.get("away_goals_for", 1.4)
    a_clean  = kwargs.get("away_clean_sheets", 3)


    home_lam = estimate_team_goals(h_xgf, h_sot, h_tempo, 1, h_miss_a, h_miss_c,
                                   a_xga, a_miss_d, a_miss_g) * cfg["goal_variance"]
    away_lam = estimate_team_goals(a_xgf, a_sot, a_tempo, 0, a_miss_a, a_miss_c,
                                   h_xga, h_miss_d, h_miss_g) * cfg["goal_variance"]
    home_lam *= (1 + cfg["home_adv"] * 0.1)
    total_lam = home_lam + away_lam

    max_g = 5
    home_win = draw = away_win = 0.0
    for i in range(max_g + 1):
        for j in range(max_g + 1):
            p = poisson_pmf(i, home_lam) * poisson_pmf(j, away_lam)
            if i > j:
                home_win += p
            elif i == j:
                draw += p
            else:
                away_win += p
    total_p = home_win + draw + away_win
    if total_p > 0:
        home_win /= total_p
        draw /= total_p
        away_win /= total_p

    h_btts = (h_xgf - 1.20) * 1.05 + (h_xga - 1.25) * 0.95 + (h_goals - 1.2) * 0.10 - 0.35 * h_miss_a + 0.28 * (h_miss_d + h_miss_g) - 0.20 * h_clean / 10.0
    a_btts = (a_xgf - 1.20) * 1.05 + (a_xga - 1.25) * 0.95 + (a_goals - 1.2) * 0.10 - 0.35 * a_miss_a + 0.28 * (a_miss_d + a_miss_g) - 0.20 * a_clean / 10.0
    btts_prob = estimate_btts_prob(home_lam, away_lam, h_btts, a_btts)

    over_15 = poisson_over_prob(total_lam, 1.5)
    over_25 = poisson_over_prob(total_lam, 2.5)
    over_35 = poisson_over_prob(total_lam, 3.5)

    corner_total = 9.2 + 0.75 * ((h_sot - 4) * 0.18 + 0.30 + (a_sot - 4) * 0.18)
    corner_total = max(4.0, min(16.0, corner_total))

    total_edge = total_lam - market_total
    conf = confidence_score(total_edge, volatility=0.55)
    rec = bet_recommendation(conf)

    # Determine the actual bet pick — pick strongest signal only
    candidates = []
    if conf >= 50 and total_edge != 0:
        if total_edge > 0:
            candidates.append((abs(total_edge), f"OVER {market_total} Goals"))
        else:
            candidates.append((abs(total_edge), f"UNDER {market_total} Goals"))
    if btts_prob > 0.55 and conf >= 50:
        candidates.append((btts_prob, f"BTTS YES ({btts_prob*100:.0f}%)"))
    if home_win > 0.50:
        candidates.append((home_win, f"{home} WIN ({home_win*100:.0f}%)"))
    elif away_win > 0.50:
        candidates.append((away_win, f"{away} WIN ({away_win*100:.0f}%)"))

    bet_pick = max(candidates, key=lambda x: x[0])[1] if candidates else None

    return {
        "sport": "soccer",
        "league": league,
        "home": home,
        "away": away,
        "projected": {
            "home_goals": round(home_lam, 2),
            "away_goals": round(away_lam, 2),
            "total_goals": round(total_lam, 2),
        },
        "outcome": {
            "home_win": round(home_win, 3),
            "draw": round(draw, 3),
            "away_win": round(away_win, 3),
        },
        "goals_analysis": {
            "over_15": round(over_15, 3),
            "over_25": round(over_25, 3),
            "over_35": round(over_35, 3),
        },
        "btts_probability": round(btts_prob, 3),
        "corner_projection": round(corner_total, 1),
        "edge": round(total_edge, 3),
        "confidence": round(conf, 1),
        "recommendation": rec,
        "bet_pick": bet_pick,
    }

# ============================================================================
# SECTION 4 — BASKETBALL PREDICTOR
# ============================================================================

def predict_basketball(home: str, away: str, league: str = "EuroLeague",
                       market_line: float = 0.0) -> Dict[str, Any]:
    """Basketball prediction using baseline scoring rates."""
    baselines = {
        "EuroLeague": (82, 78), "NBA": (115, 112), "KBL": (80, 77),
        "Liga ACB": (80, 77), "FIBA": (78, 75),
    }
    home_base, away_base = baselines.get(league, (80, 77))

    home_score = home_base + 3 + (market_line * 0.5)
    away_score = away_base - (market_line * 0.5)
    total = home_score + away_score

    point_diff = home_score - away_score
    win_prob = 1 / (1 + math.exp(-point_diff / 12))
    win_prob = clamp(win_prob)

    edge = point_diff - market_line
    conf = confidence_score(edge, volatility=6.0)
    rec = bet_recommendation(conf)

    return {
        "sport": "basketball",
        "league": league,
        "home": home,
        "away": away,
        "projected": {
            "home_score": round(home_score, 1),
            "away_score": round(away_score, 1),
            "total": round(total, 1),
        },
        "outcome": {
            "home_win": round(win_prob, 3),
            "away_win": round(1 - win_prob, 3),
        },
        "edge": round(edge, 1),
        "confidence": round(conf, 1),
        "recommendation": rec,
    }

# ============================================================================
# SECTION 5 — BASEBALL PREDICTOR (MLB / KBO)
# ============================================================================

TEAM_STATS: Dict[str, Dict] = {}

def _team_stats(abbr: str) -> Dict:
    if abbr not in TEAM_STATS:
        TEAM_STATS[abbr] = {
            "runs_per_game": 4.55, "era": 4.05, "whip": 1.23,
            "obp": 0.320, "slg": 0.400, "k_rate": 0.22, "hr_rate": 0.032,
        }
    return TEAM_STATS[abbr]

def predict_baseball(home: str, away: str, league: str = "MLB",
                     markets: Optional[List[str]] = None) -> Dict[str, Any]:
    """Baseball prediction with prop markets (NRFI, Ks, HRs)."""
    markets = markets or ["nrfi", "strikeouts", "home_runs"]
    hs = _team_stats(home)
    as_ = _team_stats(away)

    proj_home = hs["runs_per_game"] + (as_["era"] - 4.0) * 0.3
    proj_away = as_["runs_per_game"] + (hs["era"] - 4.0) * 0.3
    total = proj_home + proj_away

    result: Dict[str, Any] = {
        "sport": "baseball",
        "league": league.upper(),
        "home": home,
        "away": away,
        "projected": {
            "home_runs": round(proj_home, 2),
            "away_runs": round(proj_away, 2),
            "total": round(total, 2),
        },
        "props": {},
    }

    for m in markets:
        m = m.lower().replace("mlb_", "").replace("kbo_", "")
        if m in ("nrfi", "yrfi"):
            base = 0.53 if league.upper() == "MLB" else 0.47
            era_adj = ((5.0 - hs["era"]) + (5.0 - as_["era"])) * 0.015
            k_adj = ((hs["k_rate"] - 0.22) + (as_["k_rate"] - 0.22)) * 0.5
            prob = clamp(base + era_adj + k_adj, 0.30, 0.75)
            result["props"]["nrfi"] = {
                "probability": round(prob, 3),
                "lean": "NRFI" if prob > 0.53 else "YRFI",
            }
        elif m in ("ks", "strikeouts", "k"):
            result["props"]["strikeouts"] = {
                "home_projected": round(hs["k_rate"] * 38 * 0.5, 1),
                "away_projected": round(as_["k_rate"] * 38 * 0.5, 1),
            }
        elif m in ("hrs", "home_runs", "hr"):
            result["props"]["home_runs"] = {
                "home_projected": round(hs["hr_rate"] * 38 * 0.5, 1),
                "away_projected": round(as_["hr_rate"] * 38 * 0.5, 1),
            }

    edge = total - 8.5
    conf = confidence_score(abs(edge) * 25 / 1.3, volatility=0.6)
    rec = bet_recommendation(conf)

    # --- ADD THIS BLOCK TO FIX THE OUTPUT ---
    if conf >= 50 and edge != 0:
        result["bet_pick"] = f"OVER 8.5 Runs" if edge > 0 else f"UNDER 8.5 Runs"
    else:
        result["bet_pick"] = "PASS"
    # ----------------------------------------

    result["edge"] = round(edge, 2)
    result["confidence"] = round(conf, 1)
    result["recommendation"] = rec
    return result


# ============================================================================
# SECTION 6 — TENNIS PREDICTOR (ELO-based, generic for any matchup)
# ============================================================================

# Baseline ELO ratings for well-known players (default 1500 for unknown)
PLAYER_ELO: Dict[str, int] = {
    # ATP Top (approx grass/hard court ratings as of mid-2026)
    "djokovic": 2100, "alcaraz": 2080, "sinner": 2060, "alcaraz": 2080,
    "medvedev": 1980, "tsitsipas": 1940, "rublev": 1900, "ruud": 1860,
    "hurkacz": 1840, "fritz": 1820, "zverev": 1880, "auger-aliassime": 1800,
    "rune": 1850, "shelton": 1780, "tiafoe": 1750, "paul": 1770,
    "etcheverry": 1720, "dimitrov": 1760, "berrettini": 1790, "bublik": 1700,
    "khachanov": 1780, "de minaur": 1810, "musetti": 1740, "struff": 1680,
    "mochizuki": 1620, "quinn": 1600, "jodar": 1660, "carreno busta": 1720,
    "carreno": 1720,
    # WTA Top
    "swiatek": 2000, "sabalenka": 1950, "gauff": 1900, "rybakina": 1880,
    "pegula": 1820, "jabeur": 1800, "sakkari": 1780, "kvitova": 1760,
    "kostyuk": 1640, "noskova": 1660,
}

TENNIS_TOURNAMENT_CONFIGS: Dict[str, Dict] = {
    "wimbledon":     {"surface": "grass", "best_of": 5, "games_baseline": 42, "games_line": 38.5},
    "french open":   {"surface": "clay",  "best_of": 5, "games_baseline": 40, "games_line": 37.5},
    "us open":       {"surface": "hard",  "best_of": 5, "games_baseline": 41, "games_line": 38.5},
    "australian open": {"surface": "hard", "best_of": 5, "games_baseline": 41, "games_line": 38.5},
    "atp finals":    {"surface": "hard",  "best_of": 3, "games_baseline": 25, "games_line": 22.5},
    "default":       {"surface": "hard",  "best_of": 3, "games_baseline": 24, "games_line": 22.5},
}

def get_tournament_config(tournament: str) -> Dict:
    return TENNIS_TOURNAMENT_CONFIGS.get(tournament.lower(), TENNIS_TOURNAMENT_CONFIGS["default"])

def _name_to_elo_key(name: str) -> str:
    """Normalize player name to lookup key."""
    key = name.strip().lower()
    for known_key in PLAYER_ELO:
        if known_key in key or key in known_key:
            return known_key
    return key

def predict_tennis(home: str, away: str, tournament: str = "",
                   **kwargs) -> Dict[str, Any]:
    """Generic tennis match prediction using ELO-based win probability."""
    tcfg = get_tournament_config(tournament)

    # Get ELO ratings (from lookup or default 1500)
    h_key = _name_to_elo_key(home)
    a_key = _name_to_elo_key(away)
    h_elo = kwargs.get("home_elo", PLAYER_ELO.get(h_key, 1500))
    a_elo = kwargs.get("away_elo", PLAYER_ELO.get(a_key, 1500))

    # Win probability via ELO formula
    expected_h = 1 / (1 + 10 ** ((a_elo - h_elo) / 400))
    home_win_prob = clamp(expected_h + 0.02)  # slight nominal home/name bias
    away_win_prob = 1 - home_win_prob

    # Edge vs 50% market baseline
    edge = (home_win_prob - 0.5) * 100
    conf = confidence_score(edge, volatility=8.0)
    rec = bet_recommendation(conf)

    # First-set probability (correlated with win prob, regressed toward 0.5)
    first_set_prob = clamp(0.50 + (home_win_prob - 0.50) * 0.65)

    # Total games projection
    closeness = 1.0 - abs(home_win_prob - 0.5) * 2.0
    games_line = tcfg["games_line"]
    games_over_prob = clamp(0.40 + closeness * 0.30)
    games_rec = "OVER" if games_over_prob >= 0.53 else "UNDER"

    return {
        "sport": "tennis",
        "league": tournament or "ATP",
        "home": home,
        "away": away,
        "projected": {
            "home_elo": h_elo,
            "away_elo": a_elo,
            "elo_diff": h_elo - a_elo,
            "surface": tcfg["surface"],
        },
        "outcome": {
            "home_win": round(home_win_prob, 3),
            "away_win": round(away_win_prob, 3),
        },
        "first_set": {
            "home_first_set_prob": round(first_set_prob, 3),
            "recommendation": f"{home} to win first set" if first_set_prob > 0.55 else f"{away} to win first set" if first_set_prob < 0.45 else "Lean toward first-set markets",
        },
        "total_games": {
            "line": games_line,
            "over_prob": round(games_over_prob, 3),
            "recommendation": f"{games_rec} {games_line} games",
        },
        "elo_confidence": round(abs(h_elo - a_elo) / 400 * 100, 1),
        "edge": round(edge, 1),
        "confidence": round(conf, 1),
        "recommendation": rec,
    }

# ============================================================================
# SECTION 7 — DISCORD TELEMETRY
# ============================================================================

SPORT_EMOJIS = {"soccer": "⚽", "basketball": "🏀", "baseball": "⚾", "mlb": "⚾", "kbo": "⚾", "tennis": "🎾"}

def _tennis_wimbledon_2026_deep_dive_fields(home: str, away: str, tournament: str) -> Optional[List[Dict[str, str]]]:
    """Return Wimbledon 2026 WTA Final deep-dive fields for the specific matchup (if matched)."""
    h = (home or "").strip().lower()
    a = (away or "").strip().lower()
    t = (tournament or "").strip().lower()

    if "wimbledon" not in t:
        return None

    matchup_1 = h == "karolina muchova" and a == "linda noskova"
    matchup_2 = h == "linda noskova" and a == "karolina muchova"
    if not (matchup_1 or matchup_2):
        return None

    return [
        {"name": "🏆 Event", "value": "**2026 Wimbledon Women’s Final**\nFirst all-Czech women’s singles final in Wimbledon history", "inline": False},
        {"name": "👤 Muchova Profile", "value": "Age 29 • Seed #10 • World No. 9\nReached French Open final (2023)", "inline": False},
        {"name": "👤 Noskova Profile", "value": "Age 21 • Seed #9 • World No. 12\nFirst Grand Slam final", "inline": False},
        {"name": "🆚 H2H + Grass Form", "value": "Muchova leads **1-0**\nH2H win: US Open 2025 (Aug 30) — 3 sets, **31 games**\nGrass this season: **Both 11-1**\nWarm-up: Muchova (Bad Homburg), Noskova (Berlin)", "inline": False},
        {"name": "📈 Momentum", "value": "Muchova: **10-match win streak**\nNoskova: **9 wins in last 10**\nDoubles together @ 2024 Paris Olympics — finished 4th", "inline": False},
        {"name": "🧠 Sharp Bettor Angles", "value": "• Muchova slight favorite (bookies): **1.8 vs 2.1**\n• Noskova serve: **6.4 aces** vs Muchova **4.8**; doubles: **4 vs 1.6**\n• Return edge: Muchova **33%** return games won vs Noskova **31%** (grass)\n• H2H was long (**31 games**) → look at **Total Games / Over** markets\n• Pressure: Noskova 1st GS final, Muchova 2nd", "inline": False},
    ]


def push_to_discord(sport: str, home: str, away: str,
                    projection: Dict[str, Any],
                    webhook_url: Optional[str] = None) -> bool:
    """Push a rich embed prediction card to Discord."""
    url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
    if not url:
        print("    [Discord] No webhook URL configured. Skipping.")
        return False

    emoji = SPORT_EMOJIS.get(sport.lower(), "🎲")
    rec = projection.get("recommendation", "PASS")
    conf = projection.get("confidence", 0)
    edge = projection.get("edge", 0)
    bet_pick = projection.get("bet_pick", None)

    fields = [
        {"name": "Pick", "value": f"**{bet_pick or rec}**", "inline": False},
        {"name": "Confidence", "value": f"{conf:.1f}%", "inline": True},
        {"name": "Edge", "value": f"{edge:+.2f}", "inline": True},
    ]

    if sport == "soccer":
        p = projection.get("projected", {})
        o = projection.get("outcome", {})
        fields.append({"name": "Projected Score", "value": f"{home} {p.get('home_goals', '?')} -- {away} {p.get('away_goals', '?')}", "inline": False})
        fields.append({"name": "Match Outcome", "value": f"H: {o.get('home_win', 0)*100:.1f}% | D: {o.get('draw', 0)*100:.1f}% | A: {o.get('away_win', 0)*100:.1f}%", "inline": False})
        fields.append({"name": "BTTS", "value": f"{projection.get('btts_probability', 0)*100:.1f}%", "inline": True})
        fields.append({"name": "Corners", "value": f"{projection.get('corner_projection', 0)}", "inline": True})
    elif sport == "basketball":
        p = projection.get("projected", {})
        o = projection.get("outcome", {})
        fields.append({"name": "Projected Score", "value": f"{home} {p.get('home_score', '?')} -- {away} {p.get('away_score', '?')}", "inline": False})
        fields.append({"name": "Win Prob", "value": f"{home}: {o.get('home_win', 0)*100:.1f}% | {away}: {o.get('away_win', 0)*100:.1f}%", "inline": False})
    elif sport == "baseball":
        p = projection.get("projected", {})
        fields.append({"name": "Projected Score", "value": f"{home} {p.get('home_runs', '?')} -- {away} {p.get('away_runs', '?')}", "inline": False})
        props = projection.get("props", {})
        for k, v in props.items():
            if isinstance(v, dict):
                vals = " | ".join(f"{kk}: {vv}" for kk, vv in v.items())
                fields.append({"name": f"{k.upper()}", "value": vals, "inline": False})
    elif sport == "tennis":
        p = projection.get("projected", {})
        o = projection.get("outcome", {})
        fs = projection.get("first_set", {})
        tg = projection.get("total_games", {})
        fields.append({"name": "ELO", "value": f"{home}: {p.get('home_elo', '?')} | {away}: {p.get('away_elo', '?')}", "inline": True})
        fields.append({"name": "Surface", "value": p.get('surface', '?'), "inline": True})
        fields.append({"name": "Win Prob", "value": f"{home}: {o.get('home_win', 0)*100:.1f}% | {away}: {o.get('away_win', 0)*100:.1f}%", "inline": False})
        fields.append({"name": "First Set", "value": fs.get('recommendation', '?'), "inline": False})
        fields.append({"name": "Total Games", "value": tg.get('recommendation', '?'), "inline": False})

        deep_dive = _tennis_wimbledon_2026_deep_dive_fields(home, away, projection.get("league", ""))
        if deep_dive:
            fields.extend(deep_dive)

    color_map = {"STRONG BET": 3066993, "BET": 10181046, "LEAN": 16776960, "PASS": 15158332}
    color = color_map.get(rec, 9807270)

    payload = {
        "embeds": [{
            "title": f"{emoji} {home.upper()} vs {away.upper()}",
            "description": f"**{sport.title()}** -- {projection.get('league', '')}",
            "color": color,
            "fields": fields,
            "timestamp": datetime.now().isoformat() + "Z",
            "footer": {"text": "MultiSportPredict Engine"},
        }]
    }

    try:
        import requests
        r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
        if r.status_code in (200, 204):
            print(f"    [Discord] OK - Prediction pushed for {home} vs {away}")
            return True
        print(f"    [Discord] WARN - HTTP {r.status_code}: {r.text[:200]}")
        return False
    except Exception as e:
        print(f"    [Discord] FAILED: {e}")
        return False

# ============================================================================
# SECTION 8 — CLI ORCHESTRATOR
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="MultiSportEngine -- Predict matches across soccer, basketball, baseball, and tennis."
    )
    parser.add_argument("sport", nargs="?", help="Sport: soccer, basketball, mlb, kbo, tennis")
    parser.add_argument("home", nargs="?", help="Home team/player")
    parser.add_argument("away", nargs="?", help="Away team/player")
    parser.add_argument("league", nargs="?", default="", help="League/tournament name")
    parser.add_argument("--markets", "-m", nargs="+", help="Baseball prop markets (nrfi strikeouts home_runs)")
    parser.add_argument("--market-line", type=float, default=0.0, help="Spread/handicap line")
    parser.add_argument("--market-total", type=float, default=2.5, help="Over/under total line")
    parser.add_argument("--push-discord", action="store_true", help="Push results to Discord")
    parser.add_argument("--save", action="store_true", help="Save results to JSON file")

    args = parser.parse_args()

    if not args.sport or not args.home or not args.away:
        parser.print_help()
        print("\nExamples:")
        print('  python multi_sport_engine.py soccer "Atletico Ottawa" "Cavalry FC" "CPL" --push-discord')
        print('  python multi_sport_engine.py basketball "Real Madrid" "FC Barcelona" "EuroLeague" --push-discord')
        print('  python multi_sport_engine.py mlb "NYY" "BOS" --markets nrfi strikeouts --push-discord')
        print('  python multi_sport_engine.py tennis "Djokovic" "Alcaraz" "Wimbledon" --push-discord')
        sys.exit(1)

    sport = args.sport.lower()
    home = args.home
    away = args.away
    league = args.league or "default"

    print(f"\n{'='*60}")
    print(f"[{sport.upper()}] {home} vs {away}")
    if league and league != "default":
        print(f"   League: {league}")
    print(f"{'='*60}\n")

    result: Dict[str, Any] = {}

    if sport in ("soccer", "football"):
        result = predict_soccer(home, away, league, market_total=args.market_total)
    elif sport in ("basketball", "nba", "euroleague", "kbl"):
        result = predict_basketball(home, away, league, market_line=args.market_line)
    elif sport in ("mlb", "baseball", "kbo"):
        league_code = "KBO" if sport == "kbo" else (league or "MLB")
        result = predict_baseball(home, away, league_code, markets=args.markets)
    elif sport in ("tennis", "atp", "wta"):
        result = predict_tennis(home, away, league)
    else:
        print(f"[ERROR] Unknown sport: {sport}")
        print("   Supported: soccer, basketball, mlb, kbo, tennis")
        sys.exit(1)

    # Print summary
    p = result.get("projected", {})
    o = result.get("outcome", {})

    if sport in ("soccer", "football"):
        print(f"   Projected: {home} {p.get('home_goals', '?')} -- {away} {p.get('away_goals', '?')}")
        print(f"   Win Prob:  H {o.get('home_win', 0)*100:.1f}% | D {o.get('draw', 0)*100:.1f}% | A {o.get('away_win', 0)*100:.1f}%")
        print(f"   BTTS:      {result.get('btts_probability', 0)*100:.1f}%")
        print(f"   Corners:   {result.get('corner_projection', 0)}")
    elif sport in ("basketball", "nba", "euroleague", "kbl"):
        print(f"   Projected: {home} {p.get('home_score', '?')} -- {away} {p.get('away_score', '?')}")
        print(f"   Win Prob:  {home} {o.get('home_win', 0)*100:.1f}% | {away} {o.get('away_win', 0)*100:.1f}%")
    elif sport in ("mlb", "baseball", "kbo"):
        print(f"   Projected: {home} {p.get('home_runs', '?')} -- {away} {p.get('away_runs', '?')}")
        for k, v in result.get("props", {}).items():
            if isinstance(v, dict):
                print(f"   {k.upper()}: {v}")
    elif sport in ("tennis", "atp", "wta"):
        fs = result.get("first_set", {})
        tg = result.get("total_games", {})
        print(f"   ELO:       {home} {p.get('home_elo', '?')} | {away} {p.get('away_elo', '?')} (diff: {p.get('elo_diff', 0):+d})")
        print(f"   Surface:   {p.get('surface', '?')}")
        print(f"   Win Prob:  {home} {o.get('home_win', 0)*100:.1f}% | {away} {o.get('away_win', 0)*100:.1f}%")
        print(f"   First Set: {fs.get('recommendation', '?')}")
        print(f"   Games:     {tg.get('recommendation', '?')}")

    print(f"   Pick:      {result.get('bet_pick') or result.get('recommendation', 'PASS')}")
    print(f"   Edge:      {result.get('edge', 0):+.2f}")
    print(f"   Confidence: {result.get('confidence', 0):.1f}%")
    print(f"   Rec:       {result.get('recommendation', 'PASS')}")

    if args.save:
        out_dir = Path(f"output/{sport}")
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{home.replace(' ', '_')}_vs_{away.replace(' ', '_')}.json"
        with open(path, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n   [SAVED] to: {path}")

    if args.push_discord:
        print(f"\n   [DISCORD] Pushing to Discord...")
        push_to_discord(sport, home, away, result)

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()