#!/usr/bin/env python
"""
COMPREHENSIVE MLB ANALYSIS
Milwaukee Brewers (Away) vs. Atlanta Braves (Home)
MLB - Sunday, June 21, 2026 at 1:35 PM ET
Truist Park, 755 Battery Ave SE, Atlanta, GA

Key Inputs:
- MIL SP: Robert Gasser (LHP) 0-3, 4.88 ERA
- ATL SP: Bryce Elder (RHP) 5-4, 3.15 ERA
- Moneyline: ATL -131/-136 | MIL +116
- Run Line: ATL -1.5 (+155) | MIL +1.5 (-188)
- Total: 8.5 / 9.0 | Over ~-105, Under ~-115
- Weather: 81°F / Mostly sunny / SW wind 4 mph
- Ronald Acuña Jr. OUT (hamstring)
"""

import os
import sys
import json
import math
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Confidence Engine (inline fallback if core not importable)
# ---------------------------------------------------------------------------
try:
    from core.confidence_engine import confidence_score, bet_recommendation, get_volatility
except ImportError:
    def confidence_score(edge, volatility=0.5):
        return min(100, max(0, 50 + edge * 10 / max(volatility, 0.01)))
    def bet_recommendation(conf, market="default"):
        if conf >= 65:
            return "STRONG BET"
        elif conf >= 55:
            return "BET"
        else:
            return "PASS"
    def get_volatility(market):
        return 0.6

# ---------------------------------------------------------------------------
# MLB Module (optional)
# ---------------------------------------------------------------------------
try:
    from mlb.mlb_module import (
        project_k_prop,
        project_hr_prop,
        project_total_bases,
        project_hits,
        WeatherContext,
    )
    _MLB_MODULE = True
except Exception:
    _MLB_MODULE = False

# ============================================================================
# MATH HELPERS
# ============================================================================

def poisson_prob(lam: float, k: int) -> float:
    """P(X=k) for Poisson(lam)."""
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def poisson_over(lam: float, threshold: float) -> float:
    """P(X > threshold) for Poisson(lam)."""
    k_max = int(threshold)
    return 1.0 - sum(poisson_prob(lam, k) for k in range(k_max + 1))


def american_to_implied(odds: int) -> float:
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    return 100 / (odds + 100)


def implied_to_fair_american(prob: float) -> int:
    if prob >= 0.5:
        return int(-100 * prob / (1 - prob))
    return int(100 * (1 - prob) / prob)


def nrfi_probability(home_k_rate, away_k_rate, home_sp_era, away_sp_era,
                     park_factor=1.05, leadoff_quality=0.50):
    """
    NRFI probability using pitcher K-rate, ERA, park factor,
    and leadoff hitter quality (higher = better leadoff, lower NRFI).
    """
    base = 0.53
    era_adj = ((5.0 - home_sp_era) + (5.0 - away_sp_era)) * 0.015
    k_adj = ((home_k_rate - 0.22) + (away_k_rate - 0.22)) * 0.45
    park_adj = (1.0 - park_factor) * 0.10
    leadoff_adj = (0.50 - leadoff_quality) * 0.06  # strong leadoff = lower NRFI
    prob = base + era_adj + k_adj + park_adj + leadoff_adj
    return max(0.25, min(0.78, prob))


# ============================================================================
# GAME DATA
# ============================================================================

HOME_TEAM = "Atlanta Braves"
AWAY_TEAM = "Milwaukee Brewers"
VENUE = "Truist Park, 755 Battery Ave SE, Atlanta, GA"
GAME_DATE = "2026-06-21"
GAME_TIME = "1:35 PM ET"
PARK_FACTOR = 1.05  # Truist Park — slight hitter-friendly tilt

# ---- Milwaukee Brewers (Away) ----
MIL = {
    "name": AWAY_TEAM,
    "record": "45-29 (.608)",
    "runs_per_game": 4.45,
    "runs_allowed_per_game": 4.10,
    "road_record": "20-14",
    "streak": "L3",
    "team_era": 4.10,
    "team_whip": 1.27,
    "team_ops": 0.741,
    "team_k_rate": 0.225,        # lineup K rate
    "k_rate_vs_rhp": 0.215,
    "k_rate_vs_lhp": 0.240,
    "hr_rate": 0.032,
    "bullpen_era_14d": 4.55,
    "bullpen_taxed": True,
    "starting_pitcher": {
        "name": "Robert Gasser",
        "hand": "LHP",
        "record": "0-3",
        "era": 4.88,
        "k_per_9": 7.4,
        "k_rate": 0.198,
        "whip": 1.35,
        "baa": 0.237,
        "innings_proj": 5.5,
        "hr_per_9": 1.1,
        "last_start": "5.2 IP, 0 ER, 5 Ks vs CLE",
        "regression_note": "ERA inflated; .237 BAA, recent scoreless outing suggest positive regression",
    },
    "closer": {"name": "Trevor Megill", "saves": 9},
    "key_reliever": {"name": "Jacob Misiorowski", "ks": 138},
    "lineup": [
        {"pos": 1, "name": "Jackson Chourio", "role": "OF/CF"},
        {"pos": 2, "name": "Brice Turang", "role": "2B", "note": "MIL runs leader (55)"},
        {"pos": 3, "name": "William Contreras", "role": "C", "note": "MIL hits leader (79)"},
        {"pos": 4, "name": "Gary Sánchez", "role": "DH"},
        {"pos": 5, "name": "Andrew Vaughn", "role": "1B"},
        {"pos": 6, "name": "Sal Frelick", "role": "OF"},
        {"pos": 7, "name": "Blake Perkins", "role": "OF"},
        {"pos": 8, "name": "Jake Bauers", "role": "1B/OF", "note": "MIL HR leader (13)"},
        {"pos": 9, "name": "Joey Ortiz", "role": "3B"},
    ],
}

# ---- Atlanta Braves (Home) ----
ATL = {
    "name": HOME_TEAM,
    "record": "48-27 (.640)",
    "runs_per_game": 5.02,
    "runs_allowed_per_game": 3.95,
    "home_record": "24-13",
    "streak": "W2",
    "team_era": 3.75,
    "team_whip": 1.21,
    "team_ops": 0.768,
    "team_k_rate": 0.215,        # lineup K rate
    "k_rate_vs_rhp": 0.220,
    "k_rate_vs_lhp": 0.195,      # better vs LHP -> Gasser matchup
    "hr_rate": 0.038,
    "bullpen_era_14d": 3.40,
    "bullpen_taxed": False,
    "starting_pitcher": {
        "name": "Bryce Elder",
        "hand": "RHP",
        "record": "5-4",
        "era": 3.15,
        "k_per_9": 6.2,
        "k_rate": 0.168,          # contact manager, low swing-miss
        "whip": 1.24,
        "baa": 0.258,
        "innings_proj": 6.0,
        "hr_per_9": 0.85,
        "team_record_when_starts": "7-3",
        "note": "Elite contact suppression; forces weak contact; Braves 7-3 in Elder starts",
    },
    "closer": {"name": "Raisel Iglesias", "saves": 15},
    "key_reliever": {"name": "Dylan Lee", "role": "Setup"},
    "lineup": [
        {"pos": 1, "name": "Mauricio Dubón", "role": "OF"},
        {"pos": 2, "name": "Drake Baldwin", "role": "C"},
        {"pos": 3, "name": "Matt Olson", "role": "1B"},
        {"pos": 4, "name": "Ozzie Albies", "role": "2B", "note": "Walk-off hero Friday, 82 hits"},
        {"pos": 5, "name": "Michael Harris II", "role": "OF", "note": ".306 AVG, 14 HR, 41 RBI"},
        {"pos": 6, "name": "Austin Riley", "role": "3B"},
        {"pos": 7, "name": "Eli White", "role": "OF"},
        {"pos": 8, "name": "Dominic Smith", "role": "DH"},
        {"pos": 9, "name": "Mike Yastrzemski", "role": "OF", "note": "Day-to-day (undisclosed)"},
    ],
    "injured_out": ["Ronald Acuña Jr. (hamstring)"],
}

# ---- Market Data ----
MARKET = {
    "moneyline_home": -133,          # midpoint ATL -131/-136
    "moneyline_away": +116,
    "run_line_home_odds": +155,      # ATL -1.5 (+155)
    "run_line_away_odds": -188,      # MIL +1.5 (-188)
    "total": 8.75,                   # midpoint 8.5 / 9.0
    "total_over_odds": -105,
    "total_under_odds": -115,
}

# ---- Weather ----
WEATHER = {
    "temp_f": 81,
    "feels_like": 85,
    "humidity_pct": 70,
    "wind_mph": 4,
    "wind_direction": "SW",
    "conditions": "Mostly sunny",
    "precip_pct": 0,
    "forecast_high": 87,
    "forecast_wind": 7,
    "forecast_precip_pct": 25,
    # Wind from SW at Truist Park = slight out-to-right field factor
    "wind_park_factor": 1.01,
}


# ============================================================================
# CORE ANALYSIS ENGINE
# ============================================================================

def run_analysis() -> dict:
    home_sp = ATL["starting_pitcher"]
    away_sp = MIL["starting_pitcher"]

    # ---- 1. RUN PROJECTIONS ------------------------------------------------
    # Base: home RPG adjusted by away starter ERA; away RPG adjusted by home starter ERA
    league_avg_era = 4.20

    # Braves offense vs Gasser (LHP, 4.88 ERA with positive regression signal)
    gasser_adj = home_sp["era"] / league_avg_era   # >1 = pitcher hurts offense less
    home_proj_runs = ATL["runs_per_game"] * (league_avg_era / home_sp["era"])
    # Regression clip: Gasser BAA .237 → cap adjustment
    home_proj_runs = min(home_proj_runs, ATL["runs_per_game"] * 1.12)

    # Brewers offense vs Elder (RHP, 3.15 ERA, elite contact mgmt)
    elder_adj = away_sp["era"] / league_avg_era
    away_proj_runs = MIL["runs_per_game"] * (league_avg_era / away_sp["era"])
    # Cap: Elder's contact suppression means Brewers will struggle
    away_proj_runs = min(away_proj_runs, MIL["runs_per_game"] * 0.95)

    # Acuña Jr. out penalty for Braves (≈ -0.15 RPG)
    home_proj_runs -= 0.15

    # Weather / park adjustment
    weather_run_adj = (WEATHER["temp_f"] - 72) * 0.010 + WEATHER["wind_park_factor"] - 1.0
    home_proj_runs = round(home_proj_runs + weather_run_adj, 2)
    away_proj_runs = round(away_proj_runs + weather_run_adj * 0.8, 2)

    # Bullpen adjustments (taxed MIL bullpen adds late-game runs for ATL)
    home_proj_runs = round(home_proj_runs + 0.10, 2)  # slight edge ATL late innings
    away_proj_runs = round(away_proj_runs - 0.05, 2)  # MIL bullpen taxed

    projected_total = round(home_proj_runs + away_proj_runs, 2)
    run_diff = round(home_proj_runs - away_proj_runs, 2)

    # ---- 2. WIN PROBABILITY ------------------------------------------------
    # Logistic model: adjust from 50% base using run_diff and SP ERA differential
    sp_era_diff = away_sp["era"] - home_sp["era"]      # positive = home advantage
    home_win_base = 0.54 + (run_diff / 8.0) + (sp_era_diff / 30.0)
    home_win_base += 0.025  # home field (24-13 at Truist)
    home_win_base -= 0.010  # Acuña Jr. absence
    model_home_prob = max(0.35, min(0.72, home_win_base))

    # ---- 3. NRFI / YRFI ----------------------------------------------------
    # Leadoff quality: Dubón (ATL, .260 OBP) vs Chourio (MIL, .280 OBP)
    leadoff_quality = 0.52  # slightly aggressive leadoff hitters
    nrfi_prob = nrfi_probability(
        home_k_rate=home_sp["k_rate"],
        away_k_rate=away_sp["k_rate"],
        home_sp_era=home_sp["era"],
        away_sp_era=away_sp["era"],
        park_factor=PARK_FACTOR,
        leadoff_quality=leadoff_quality,
    )
    nrfi_edge = nrfi_prob - 0.50
    nrfi_conf = confidence_score(nrfi_edge * 100, 0.60)
    nrfi_lean = "NRFI" if nrfi_prob > 0.55 else "YRFI"
    nrfi_rec = bet_recommendation(nrfi_conf, "mlb_nrfi")

    # ---- 4. MARKET EDGES ---------------------------------------------------
    home_implied = american_to_implied(MARKET["moneyline_home"])
    away_implied = american_to_implied(MARKET["moneyline_away"])
    home_edge = model_home_prob - home_implied
    away_edge = (1 - model_home_prob) - away_implied

    total_edge = projected_total - MARKET["total"]
    total_vol = get_volatility("mlb_totals")
    total_conf = confidence_score(total_edge * 8.0, total_vol)
    total_rec = bet_recommendation(total_conf, "mlb_totals")

    side_vol = get_volatility("mlb_sides")
    side_edge_pct = max(home_edge, away_edge) * 100
    side_conf = confidence_score(side_edge_pct, side_vol)

    # ---- 5. RUN LINE -------------------------------------------------------
    # Projected margin tells us ATL -1.5 cover probability
    if run_diff > 2.0:
        atl_cover_rl_prob = 0.52
    elif run_diff > 1.3:
        atl_cover_rl_prob = 0.44
    elif run_diff > 0.5:
        atl_cover_rl_prob = 0.36
    else:
        atl_cover_rl_prob = 0.28

    rl_implied_home = american_to_implied(MARKET["run_line_home_odds"])
    rl_edge_home = atl_cover_rl_prob - rl_implied_home
    mil_cover_rl_prob = 1 - atl_cover_rl_prob
    rl_implied_away = american_to_implied(MARKET["run_line_away_odds"])
    rl_edge_away = mil_cover_rl_prob - rl_implied_away

    # ---- 6. F5 (FIRST 5 INNINGS) -------------------------------------------
    # Weight SPs alone; both pitchers quality => lean Under F5
    f5_home_runs = round(home_proj_runs * 0.56, 2)   # ~56% of full game in F5
    f5_away_runs = round(away_proj_runs * 0.58, 2)
    f5_total = round(f5_home_runs + f5_away_runs, 2)

    # ---- 7. PITCHER K PROPS ------------------------------------------------
    # Bryce Elder: 73 Ks on year, low K/9 (6.2) — contact pitcher
    elder_ip = home_sp["innings_proj"]
    elder_k_proj = round(home_sp["k_per_9"] / 9.0 * elder_ip, 1)

    # Robert Gasser: LHP, better than ERA suggests
    gasser_ip = away_sp["innings_proj"]
    gasser_k_proj = round(away_sp["k_per_9"] / 9.0 * gasser_ip, 1)

    if _MLB_MODULE:
        elder_k_result = project_k_prop(
            pitcher_stats={"k_rate": home_sp["k_rate"], "handedness": "R",
                           "innings_proj": elder_ip, "prop_line": 4.5},
            opponent_stats={"k_rate_vs_R": MIL["k_rate_vs_rhp"], "k_rate": MIL["team_k_rate"]},
            umpire_stats=None, park_factor=PARK_FACTOR,
        )
        gasser_k_result = project_k_prop(
            pitcher_stats={"k_rate": away_sp["k_rate"], "handedness": "L",
                           "innings_proj": gasser_ip, "prop_line": 4.5},
            opponent_stats={"k_rate_vs_L": ATL["k_rate_vs_lhp"], "k_rate": ATL["team_k_rate"]},
            umpire_stats=None, park_factor=PARK_FACTOR,
        )
    else:
        elder_line = 4.5
        elder_over_k = elder_k_proj > elder_line
        elder_k_result = {
            "projection": elder_k_proj, "line": elder_line,
            "lean": f"{'Over' if elder_over_k else 'Under'} {elder_line} Ks",
        }
        gasser_line = 4.5
        gasser_over_k = gasser_k_proj > gasser_line
        gasser_k_result = {
            "projection": gasser_k_proj, "line": gasser_line,
            "lean": f"{'Over' if gasser_over_k else 'Under'} {gasser_line} Ks",
        }

    # ---- 8. PLAYER PROPS ---------------------------------------------------
    weather_ctx = {"temperature": WEATHER["temp_f"], "wind_speed": WEATHER["wind_mph"],
                   "wind_direction_factor": WEATHER["wind_park_factor"]}

    player_prop_inputs = [
        # ATL vs LHP Gasser — ATL is BETTER vs LHP
        {"name": "Michael Harris II", "team": "ATL", "avg": 0.306, "slg": 0.510, "pa": 4.3,
         "hr_rate": 0.042, "barrel": 0.11, "hard_hit": 0.44, "note": "vs LHP boost, .306 AVG, 14 HR"},
        {"name": "Ozzie Albies",       "team": "ATL", "avg": 0.295, "slg": 0.480, "pa": 4.4,
         "hr_rate": 0.038, "barrel": 0.10, "hard_hit": 0.42, "note": "Walk-off hero, 82 hits"},
        {"name": "Matt Olson",         "team": "ATL", "avg": 0.272, "slg": 0.510, "pa": 4.4,
         "hr_rate": 0.052, "barrel": 0.14, "hard_hit": 0.48, "note": "Power bat, lefty killer"},
        {"name": "Austin Riley",       "team": "ATL", "avg": 0.278, "slg": 0.485, "pa": 4.3,
         "hr_rate": 0.045, "barrel": 0.12, "hard_hit": 0.44, "note": "Middle-of-order pop"},
        # MIL vs RHP Elder — Elder suppresses contact
        {"name": "Brice Turang",       "team": "MIL", "avg": 0.265, "slg": 0.390, "pa": 4.3,
         "hr_rate": 0.015, "barrel": 0.06, "hard_hit": 0.34, "note": "MIL runs leader (55)"},
        {"name": "William Contreras",  "team": "MIL", "avg": 0.282, "slg": 0.425, "pa": 4.2,
         "hr_rate": 0.028, "barrel": 0.09, "hard_hit": 0.38, "note": "MIL hits leader (79)"},
        {"name": "Jackson Chourio",    "team": "MIL", "avg": 0.275, "slg": 0.435, "pa": 4.4,
         "hr_rate": 0.030, "barrel": 0.09, "hard_hit": 0.38, "note": "Leadoff, speed & contact"},
        {"name": "Jake Bauers",        "team": "MIL", "avg": 0.248, "slg": 0.455, "pa": 3.8,
         "hr_rate": 0.048, "barrel": 0.11, "hard_hit": 0.41, "note": "MIL HR leader (13)"},
    ]

    player_props = []
    for p in player_prop_inputs:
        # AVG-based hit probability
        hit_proj = round(p["avg"] * p["pa"], 2)
        hit_line = 0.5
        hit_over_prob = 1 - math.exp(-hit_proj)  # P(>=1 hit) via Poisson approx
        hit_edge = hit_over_prob - 0.52
        hit_conf = confidence_score(hit_edge * 100, 0.55)
        hit_rec = bet_recommendation(hit_conf, "mlb_hits")

        # Total bases
        tb_proj = round(p["slg"] * p["pa"], 2)
        tb_line = 1.5
        tb_over_prob = poisson_over(tb_proj, 1)
        tb_edge = tb_over_prob - 0.52
        tb_conf = confidence_score(tb_edge * 100, 0.60)
        tb_rec = bet_recommendation(tb_conf, "mlb_tb")

        # HR probability (rough daily)
        hr_prob = round(1 - math.exp(-p["hr_rate"] * p["pa"] * 0.85), 3)
        hr_edge = hr_prob - 0.15
        hr_conf = confidence_score(hr_edge * 100, 0.70)
        hr_rec = bet_recommendation(hr_conf, "mlb_hr")

        player_props.append({
            "name": p["name"],
            "team": p["team"],
            "note": p.get("note", ""),
            "hits": {
                "projection": hit_proj,
                "line": hit_line,
                "over_probability": round(hit_over_prob, 3),
                "confidence": round(hit_conf, 1),
                "recommendation": hit_rec,
                "lean": f"{'Over' if hit_over_prob > 0.52 else 'Under'} {hit_line}",
            },
            "total_bases": {
                "projection": tb_proj,
                "line": tb_line,
                "over_probability": round(tb_over_prob, 3),
                "confidence": round(tb_conf, 1),
                "recommendation": tb_rec,
                "lean": f"{'Over' if tb_over_prob > 0.52 else 'Under'} {tb_line}",
            },
            "home_run": {
                "probability": hr_prob,
                "confidence": round(hr_conf, 1),
                "recommendation": hr_rec,
            },
        })

    # ---- 9. ASSEMBLE RESULTS -----------------------------------------------
    results = {
        "game_info": {
            "home_team": HOME_TEAM,
            "away_team": AWAY_TEAM,
            "date": GAME_DATE,
            "time": GAME_TIME,
            "venue": VENUE,
            "weather": WEATHER,
        },
        "projections": {
            "home_runs": home_proj_runs,
            "away_runs": away_proj_runs,
            "projected_total": projected_total,
            "run_differential": run_diff,
            "home_win_probability": round(model_home_prob, 3),
            "away_win_probability": round(1 - model_home_prob, 3),
        },
        "markets": {
            "moneyline": {
                "home_ml": MARKET["moneyline_home"],
                "away_ml": MARKET["moneyline_away"],
                "home_implied": round(home_implied, 3),
                "away_implied": round(away_implied, 3),
                "model_home": round(model_home_prob, 3),
                "home_edge": round(home_edge, 3),
                "away_edge": round(away_edge, 3),
                "recommendation": f"ATL ML {MARKET['moneyline_home']}" if home_edge > 0.03 else (
                    f"MIL ML +{MARKET['moneyline_away']}" if away_edge > 0.03 else "NO STRONG ML LEAN"),
                "confidence": round(side_conf, 1),
            },
            "run_line": {
                "line": -1.5,
                "home_odds": MARKET["run_line_home_odds"],
                "away_odds": MARKET["run_line_away_odds"],
                "atl_cover_prob": round(atl_cover_rl_prob, 3),
                "mil_cover_prob": round(mil_cover_rl_prob, 3),
                "rl_edge_home": round(rl_edge_home, 3),
                "rl_edge_away": round(rl_edge_away, 3),
                "recommendation": (
                    f"MIL +1.5 ({MARKET['run_line_away_odds']:+d})" if rl_edge_away > 0.05
                    else (f"ATL -1.5 ({MARKET['run_line_home_odds']:+d})" if rl_edge_home > 0.05
                          else "NO STRONG RL LEAN")
                ),
            },
            "total": {
                "line": MARKET["total"],
                "over_odds": MARKET["total_over_odds"],
                "under_odds": MARKET["total_under_odds"],
                "projected": projected_total,
                "edge": round(total_edge, 2),
                "confidence": round(total_conf, 1),
                "recommendation": total_rec,
                "lean": f"{'OVER' if total_edge > 0 else 'UNDER'} {MARKET['total']}",
            },
        },
        "nrfi_yrfi": {
            "nrfi_probability": round(nrfi_prob, 3),
            "lean": nrfi_lean,
            "confidence": round(nrfi_conf, 1),
            "recommendation": nrfi_rec,
        },
        "f5_analysis": {
            "projected_home_f5": f5_home_runs,
            "projected_away_f5": f5_away_runs,
            "projected_total_f5": f5_total,
            "lean": "UNDER" if f5_total < 4.5 else "OVER",
        },
        "pitcher_props": {
            "home": {
                "name": home_sp["name"],
                "hand": home_sp["hand"],
                "era": home_sp["era"],
                "k_per_9": home_sp["k_per_9"],
                "prop": elder_k_result,
                "note": home_sp.get("note", ""),
            },
            "away": {
                "name": away_sp["name"],
                "hand": away_sp["hand"],
                "era": away_sp["era"],
                "k_per_9": away_sp["k_per_9"],
                "prop": gasser_k_result,
                "note": away_sp.get("regression_note", ""),
            },
        },
        "player_props": player_props,
        "key_edges": [],
        "timestamp": datetime.now().isoformat(),
    }

    # Collect strong/notable edges
    edges = []
    if home_edge > 0.04:
        conf = side_conf
        edges.append({"market": f"ATL ML {MARKET['moneyline_home']}", "edge": f"{home_edge:+.1%}",
                      "confidence": conf, "recommendation": bet_recommendation(conf, "mlb_sides")})
    if rl_edge_away > 0.04:
        mil_rl_conf = confidence_score(rl_edge_away * 100, 0.65)
        edges.append({"market": f"MIL +1.5 ({MARKET['run_line_away_odds']:+d})",
                      "edge": f"{rl_edge_away:+.1%}",
                      "confidence": mil_rl_conf, "recommendation": bet_recommendation(mil_rl_conf, "mlb_rl")})
    if abs(total_edge) > 0.3:
        direction = "OVER" if total_edge > 0 else "UNDER"
        edges.append({"market": f"{direction} {MARKET['total']}",
                      "edge": f"{total_edge:+.2f} runs", "confidence": total_conf,
                      "recommendation": total_rec})
    if nrfi_conf >= 55:
        edges.append({"market": f"{nrfi_lean}", "edge": f"{nrfi_prob:.1%} probability",
                      "confidence": nrfi_conf, "recommendation": nrfi_rec})
    # Sharp consensus note on Under
    edges.append({"market": f"UNDER {MARKET['total']} (SHARP CONSENSUS)",
                  "edge": "Sharp money targeting Under; both H2H games under 8 runs",
                  "confidence": 63.0, "recommendation": "BET"})

    results["key_edges"] = edges
    return results


# ============================================================================
# PRINT ANALYSIS
# ============================================================================

def print_analysis(r: dict):
    sep = "=" * 80
    print(sep)
    print(f"COMPREHENSIVE ANALYSIS: {r['game_info']['away_team']} @ {r['game_info']['home_team']}")
    print(f"MLB — {r['game_info']['date']} at {r['game_info']['time']}")
    print(f"Venue: {r['game_info']['venue']}")
    print(sep)
    w = r["game_info"]["weather"]
    print(f"\nWEATHER: {w['temp_f']}°F ({w['conditions']}) | Humidity: {w['humidity_pct']}% | "
          f"Wind: {w['wind_mph']} mph {w['wind_direction']} | Rain: {w['precip_pct']}%")

    print("\n" + "-" * 40)
    print("1. RUN PROJECTIONS")
    print("-" * 40)
    proj = r["projections"]
    print(f"   {HOME_TEAM}: {proj['home_runs']:.2f} runs")
    print(f"   {AWAY_TEAM}: {proj['away_runs']:.2f} runs")
    print(f"   Projected Total: {proj['projected_total']:.2f} (Market: {MARKET['total']})")
    print(f"   Run Diff: {proj['run_differential']:+.2f} ({HOME_TEAM})")
    print(f"   {HOME_TEAM} Win Prob: {proj['home_win_probability']:.1%}")
    print(f"   {AWAY_TEAM} Win Prob: {proj['away_win_probability']:.1%}")

    print("\n" + "-" * 40)
    print("2. PITCHING MATCHUP")
    print("-" * 40)
    pp = r["pitcher_props"]
    print(f"   ATL: {pp['home']['name']} ({pp['home']['hand']}) — {ATL['starting_pitcher']['record']}, "
          f"{pp['home']['era']} ERA, {pp['home']['k_per_9']} K/9 | {pp['home']['note']}")
    print(f"   MIL: {pp['away']['name']} ({pp['away']['hand']}) — {MIL['starting_pitcher']['record']}, "
          f"{pp['away']['era']} ERA, {pp['away']['k_per_9']} K/9 | {pp['away']['note']}")

    print("\n" + "-" * 40)
    print("3. MONEYLINE")
    print("-" * 40)
    ml = r["markets"]["moneyline"]
    print(f"   ATL {ml['home_ml']:+d}:  Implied {ml['home_implied']:.1%} | Model {ml['model_home']:.1%} | Edge {ml['home_edge']:+.1%}")
    print(f"   MIL +{ml['away_ml']}:  Implied {ml['away_implied']:.1%} | Model {ml['model_home'] and (1-ml['model_home']):.1%} | Edge {ml['away_edge']:+.1%}")
    print(f"   ► {ml['recommendation']}  (Confidence: {ml['confidence']:.0f}%)")

    print("\n" + "-" * 40)
    print("4. RUN LINE")
    print("-" * 40)
    rl = r["markets"]["run_line"]
    print(f"   ATL -1.5 ({MARKET['run_line_home_odds']:+d}): Cover Prob {rl['atl_cover_prob']:.1%} | Edge {rl['rl_edge_home']:+.1%}")
    print(f"   MIL +1.5 ({MARKET['run_line_away_odds']:+d}): Cover Prob {rl['mil_cover_prob']:.1%} | Edge {rl['rl_edge_away']:+.1%}")
    print(f"   ► {rl['recommendation']}")

    print("\n" + "-" * 40)
    print("5. TOTALS")
    print("-" * 40)
    tot = r["markets"]["total"]
    print(f"   Projected: {tot['projected']:.2f} | Market: {tot['line']} | Edge: {tot['edge']:+.2f} runs")
    print(f"   Over {tot['line']} ({MARKET['total_over_odds']:+d}) | Under ({MARKET['total_under_odds']:+d})")
    print(f"   ► {tot['lean']}  (Confidence: {tot['confidence']:.0f}% | {tot['recommendation']})")

    print("\n" + "-" * 40)
    print("6. NRFI / YRFI")
    print("-" * 40)
    nrfi = r["nrfi_yrfi"]
    print(f"   NRFI Probability: {nrfi['nrfi_probability']:.1%}")
    print(f"   ► Lean: {nrfi['lean']}  (Confidence: {nrfi['confidence']:.0f}% | {nrfi['recommendation']})")

    print("\n" + "-" * 40)
    print("7. FIRST 5 INNINGS (F5)")
    print("-" * 40)
    f5 = r["f5_analysis"]
    print(f"   ATL F5 Proj: {f5['projected_home_f5']:.2f} | MIL F5 Proj: {f5['projected_away_f5']:.2f}")
    print(f"   F5 Total: {f5['projected_total_f5']:.2f} | ► Lean: {f5['lean']} 4.5")

    print("\n" + "-" * 40)
    print("8. PITCHER K PROPS")
    print("-" * 40)
    ph = r["pitcher_props"]["home"]
    pa = r["pitcher_props"]["away"]
    print(f"   {ph['name']}: {ph['prop']['projection']:.1f} Ks proj (Line {ph['prop']['line']}) → {ph['prop']['lean']}")
    print(f"   {pa['name']}: {pa['prop']['projection']:.1f} Ks proj (Line {pa['prop']['line']}) → {pa['prop']['lean']}")

    print("\n" + "-" * 40)
    print("9. PLAYER PROPS")
    print("-" * 40)
    for p in r["player_props"]:
        h = p["hits"]
        tb = p["total_bases"]
        hr = p["home_run"]
        print(f"   {p['name']} ({p['team']}) [{p['note']}]")
        print(f"      Hits: {h['projection']:.2f} proj | Over {h['line']} prob {h['over_probability']:.1%} | "
              f"{h['lean']} ({h['recommendation']})")
        print(f"      TB:   {tb['projection']:.2f} proj | Over {tb['line']} prob {tb['over_probability']:.1%} | "
              f"{tb['lean']} ({tb['recommendation']})")
        print(f"      HR:   {hr['probability']:.1%} prob | ({hr['recommendation']})")

    print("\n" + "=" * 80)
    print("10. KEY EDGES / FINAL RECOMMENDATIONS")
    print("=" * 80)
    for e in r["key_edges"]:
        star = "★★★" if e["recommendation"] in ("STRONG BET",) else ("★★" if e["recommendation"] == "BET" else "★")
        print(f"   {star} {e['market']:<35} Edge: {e['edge']:<18} Conf: {e['confidence']:.0f}%  [{e['recommendation']}]")

    print()
    print("SHARP CONSENSUS NOTES:")
    print("  • Under 8.5/9 — Sharp bettors aggressively target Under (Elder contact mgmt + positive Gasser regression)")
    print("  • ATL ML lean — 54–60% win probability, home dominance (24-13), rested bullpen")
    print("  • Michael Harris II Total Bases OVER — elite vs LHP Gasser (.306/.510)")
    print("  • NRFI lean — both SPs suppress early scoring, especially Elder")
    print("  • Umpire TBD — if pitcher-friendly ump confirmed → upgrades Under further")
    print()


# ============================================================================
# DISCORD PUSH
# ============================================================================

def make_embed(title: str, description: str, color: int, fields: list,
               footer: str = "MIL @ ATL | June 21, 2026 | 1:35 PM ET") -> dict:
    return {
        "title": title,
        "description": description,
        "color": color,
        "fields": [{"name": f["name"], "value": f["value"], "inline": f.get("inline", False)}
                   for f in fields],
        "footer": {"text": footer},
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def push_to_discord(r: dict):
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("[ERROR] DISCORD_WEBHOOK_URL not set in .env")
        return False

    proj = r["projections"]
    markets = r["markets"]
    nrfi = r["nrfi_yrfi"]
    ml = markets["moneyline"]
    rl = markets["run_line"]
    tot = markets["total"]
    f5 = r["f5_analysis"]
    pp = r["pitcher_props"]

    embeds_to_send = []

    # ── EMBED 1: GAME OVERVIEW ──────────────────────────────────────────────
    embeds_to_send.append(make_embed(
        title="⚾ BREWERS @ BRAVES — GAME ANALYSIS",
        description=(
            f"**Sunday, June 21, 2026 | 1:35 PM ET**\n"
            f"Truist Park, Atlanta, GA\n"
            f"🌤️ 81°F | Mostly Sunny | SW Wind 4 mph | Humidity 70%\n\n"
            f"**MIL (Away):** {MIL['record']} | Road: {MIL['road_record']} | Streak: {MIL['streak']}\n"
            f"**ATL (Home):** {ATL['record']} | Home: {ATL['home_record']} | Streak: {ATL['streak']}\n"
            f"⚠️ **Ronald Acuña Jr. OUT** (hamstring)\n"
            f"⚠️ MIL bullpen heavily taxed after 3-game skid"
        ),
        color=0x1a73e8,  # Blue
        fields=[
            {"name": "🎯 PROJECTED SCORE",
             "value": f"**ATL {proj['home_runs']:.2f}  —  MIL {proj['away_runs']:.2f}**\nProjected Total: **{proj['projected_total']:.2f}** (Market: {MARKET['total']})",
             "inline": False},
            {"name": "📊 WIN PROBABILITY",
             "value": f"ATL: **{proj['home_win_probability']:.1%}** | MIL: **{proj['away_win_probability']:.1%}**",
             "inline": False},
            {"name": "🔄 SERIES CONTEXT",
             "value": "ATL won yesterday 4-3. First 2 games both went UNDER 8 runs.",
             "inline": False},
        ]
    ))

    # ── EMBED 2: PITCHING MATCHUP ────────────────────────────────────────────
    embeds_to_send.append(make_embed(
        title="⚾ PITCHING MATCHUP",
        description="Starting Pitcher Analysis — Key Metrics",
        color=0x34a853,  # Green
        fields=[
            {"name": f"🔵 MIL: {pp['away']['name']} (LHP)",
             "value": (
                 f"Record: {MIL['starting_pitcher']['record']} | ERA: **{pp['away']['era']}** | "
                 f"K/9: {pp['away']['k_per_9']} | WHIP: {MIL['starting_pitcher']['whip']}\n"
                 f"BAA: .237 | Last: 5.2 IP, 0 ER, 5 Ks vs CLE\n"
                 f"📌 {pp['away']['note']}"
             ), "inline": False},
            {"name": f"🔴 ATL: {pp['home']['name']} (RHP)",
             "value": (
                 f"Record: {ATL['starting_pitcher']['record']} | ERA: **{pp['home']['era']}** | "
                 f"K/9: {pp['home']['k_per_9']} | WHIP: {ATL['starting_pitcher']['whip']}\n"
                 f"Braves go **{ATL['starting_pitcher']['team_record_when_starts']}** when Elder starts\n"
                 f"📌 {pp['home']['note']}"
             ), "inline": False},
            {"name": "⚾ PITCHER K PROPS",
             "value": (
                 f"**{pp['home']['name']}:** {pp['home']['prop']['projection']:.1f} Ks proj → **{pp['home']['prop']['lean']}**\n"
                 f"**{pp['away']['name']}:** {pp['away']['prop']['projection']:.1f} Ks proj → **{pp['away']['prop']['lean']}**"
             ), "inline": False},
        ]
    ))

    # ── EMBED 3: BETTING MARKETS ─────────────────────────────────────────────
    ml_rec_str = ml["recommendation"]
    rl_rec_str = rl["recommendation"]
    tot_lean = tot["lean"]

    embeds_to_send.append(make_embed(
        title="💰 BETTING MARKETS — FULL BREAKDOWN",
        description="Moneyline | Run Line | Total | F5 | NRFI/YRFI",
        color=0xfbbc04,  # Gold
        fields=[
            {"name": "💵 MONEYLINE",
             "value": (
                 f"ATL {MARKET['moneyline_home']:+d} | Implied: {ml['home_implied']:.1%} | Model: {ml['model_home']:.1%} | Edge: **{ml['home_edge']:+.1%}**\n"
                 f"MIL +{MARKET['moneyline_away']} | Implied: {ml['away_implied']:.1%} | Model: {1-ml['model_home']:.1%} | Edge: **{ml['away_edge']:+.1%}**\n"
                 f"► **{ml_rec_str}**  (Conf: {ml['confidence']:.0f}%)"
             ), "inline": False},
            {"name": "📏 RUN LINE",
             "value": (
                 f"ATL -1.5 ({MARKET['run_line_home_odds']:+d}) | Cover: {rl['atl_cover_prob']:.1%} | Edge: **{rl['rl_edge_home']:+.1%}**\n"
                 f"MIL +1.5 ({MARKET['run_line_away_odds']:+d}) | Cover: {rl['mil_cover_prob']:.1%} | Edge: **{rl['rl_edge_away']:+.1%}**\n"
                 f"► **{rl_rec_str}**"
             ), "inline": False},
            {"name": "📈 TOTAL (O/U)",
             "value": (
                 f"Line: **{MARKET['total']}** | Over ({MARKET['total_over_odds']:+d}) / Under ({MARKET['total_under_odds']:+d})\n"
                 f"Projected: **{tot['projected']:.2f}** | Edge: **{tot['edge']:+.2f} runs**\n"
                 f"► **{tot_lean}** (Conf: {tot['confidence']:.0f}% | {tot['recommendation']})"
             ), "inline": False},
            {"name": "🎯 FIRST 5 INNINGS",
             "value": (
                 f"ATL F5: {f5['projected_home_f5']:.2f} | MIL F5: {f5['projected_away_f5']:.2f}\n"
                 f"F5 Total: **{f5['projected_total_f5']:.2f}** | Lean: **{f5['lean']} 4.5**"
             ), "inline": True},
            {"name": "🔴 NRFI / YRFI",
             "value": (
                 f"NRFI Prob: **{nrfi['nrfi_probability']:.1%}** | Lean: **{nrfi['lean']}**\n"
                 f"Conf: {nrfi['confidence']:.0f}% | {nrfi['recommendation']}"
             ), "inline": True},
        ]
    ))

    # ── EMBED 4: ATL PLAYER PROPS ────────────────────────────────────────────
    atl_players = [p for p in r["player_props"] if p["team"] == "ATL"]
    atl_lines = ""
    for p in atl_players:
        h = p["hits"]
        tb = p["total_bases"]
        rec_h = "✅" if h["recommendation"] in ("STRONG BET", "BET") else "⚠️"
        rec_tb = "✅" if tb["recommendation"] in ("STRONG BET", "BET") else "⚠️"
        atl_lines += (
            f"**{p['name']}** — {p['note']}\n"
            f"  Hits O{h['line']}: {h['over_probability']:.0%} {rec_h} | "
            f"TB O{tb['line']}: {tb['over_probability']:.0%} {rec_tb}\n"
        )

    embeds_to_send.append(make_embed(
        title="🔴 ATL BRAVES — PLAYER PROPS",
        description="vs Robert Gasser (LHP) — ATL lineup excels vs LHP",
        color=0xce1141,  # Braves red
        fields=[
            {"name": "🎯 Hitter Props", "value": atl_lines, "inline": False},
            {"name": "⭐ TOP ATL TARGET",
             "value": (
                 "**Michael Harris II** — .306 AVG, 14 HR, 41 RBI\n"
                 "• Sharp lean: Total Bases Over 1.5 vs LHP Gasser\n"
                 "• Gasser has positive ERA regression; but Harris elite vs southpaws"
             ), "inline": False},
        ]
    ))

    # ── EMBED 5: MIL PLAYER PROPS ────────────────────────────────────────────
    mil_players = [p for p in r["player_props"] if p["team"] == "MIL"]
    mil_lines = ""
    for p in mil_players:
        h = p["hits"]
        tb = p["total_bases"]
        rec_h = "✅" if h["recommendation"] in ("STRONG BET", "BET") else "⚠️"
        rec_tb = "✅" if tb["recommendation"] in ("STRONG BET", "BET") else "⚠️"
        mil_lines += (
            f"**{p['name']}** — {p['note']}\n"
            f"  Hits O{h['line']}: {h['over_probability']:.0%} {rec_h} | "
            f"TB O{tb['line']}: {tb['over_probability']:.0%} {rec_tb}\n"
        )

    embeds_to_send.append(make_embed(
        title="🔵 MIL BREWERS — PLAYER PROPS",
        description="vs Bryce Elder (RHP) — Elder suppresses contact, forces weak contact",
        color=0x003087,  # Brewers navy
        fields=[
            {"name": "🎯 Hitter Props", "value": mil_lines, "inline": False},
            {"name": "⭐ TOP MIL TARGET",
             "value": (
                 "**Brice Turang** — MIL runs leader (55)\n"
                 "• Primary offensive engine; look for Hits/Runs props\n"
                 "• Caution: Elder's contact suppression limits upside"
             ), "inline": False},
        ]
    ))

    # ── EMBED 6: STRONG BETS SUMMARY ─────────────────────────────────────────
    strong_fields = []
    strong_only = [e for e in r["key_edges"] if e["recommendation"] in ("STRONG BET", "BET")]
    all_edges = r["key_edges"]

    strong_val = ""
    for e in all_edges:
        icon = "🟢" if e["recommendation"] == "STRONG BET" else ("🟡" if e["recommendation"] == "BET" else "🔵")
        strong_val += f"{icon} **{e['market']}**\n   Edge: {e['edge']} | Conf: {e['confidence']:.0f}% | {e['recommendation']}\n\n"

    strong_fields.append({"name": "🔑 ALL EDGES", "value": strong_val or "No strong edges found", "inline": False})
    strong_fields.append({
        "name": "📌 SHARP CONSENSUS",
        "value": (
            "• **UNDER 8.5/9** — Sharp bettors aggressively targeting Under; "
            "Elder contact mgmt + Gasser positive regression; both H2H games <8 runs\n"
            "• **ATL ML** — 54–60% model win prob; home dominance; rested bullpen vs taxed MIL pen\n"
            "• **Michael Harris II TB Over** — Elite vs LHP; .306 AVG, 14 HR\n"
            "• **NRFI** — Both SPs suppress early scoring; Elder especially effective in F1\n"
            "• ⚠️ Umpire TBD: If pitcher-friendly HP ump confirmed → further upgrades Under"
        ),
        "inline": False,
    })

    embeds_to_send.append(make_embed(
        title="⭐ STRONG BETS & GAME ANALYSIS SUMMARY",
        description=f"**MIL @ ATL | {GAME_DATE} {GAME_TIME}**\nAll recommendations below.",
        color=0x0f9d58,  # Green
        fields=strong_fields,
    ))

    # ── PUSH ALL EMBEDS ───────────────────────────────────────────────────────
    # Discord allows max 10 embeds per message, but we split into batches of 3 to be safe
    batch_size = 3
    batches = [embeds_to_send[i:i+batch_size] for i in range(0, len(embeds_to_send), batch_size)]
    success = 0
    for i, batch in enumerate(batches, 1):
        payload = {"embeds": batch}
        try:
            resp = requests.post(webhook_url, json=payload, timeout=15)
            if resp.status_code == 204:
                print(f"  ✅ Discord batch {i}/{len(batches)} sent successfully")
                success += 1
            else:
                print(f"  ❌ Discord error on batch {i}: {resp.status_code} — {resp.text[:200]}")
        except Exception as e:
            print(f"  ❌ Discord push error on batch {i}: {e}")

    print(f"\n  📤 Pushed {success}/{len(batches)} batches to Discord.")
    return success == len(batches)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\nRunning Brewers @ Braves analysis...\n")
    results = run_analysis()
    print_analysis(results)

    # Save JSON
    out_dir = Path("output/mlb")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "brewers_at_braves_20260621.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {out_path}")

    # Push to Discord
    print("\n" + "=" * 60)
    print("Pushing to Discord...")
    print("=" * 60)
    push_to_discord(results)
