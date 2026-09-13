# ═══════════════════════════════════════════════════════════════════════════
# DEPRECATED / ORPHANED — DO NOT EXTEND OR RELY ON THIS FILE
# ───────────────────────────────────────────────────────────────────────────
# Confirmed via repo-wide import grep (see ARCHITECTURE.md §2/§3): this file
# is NOT reachable from predict_match.py (the live entry point). It has zero
# effect on real predictions. Keep it only as reference until it is deleted.
# ═══════════════════════════════════════════════════════════════════════════

"""
MULTI-SPORT HANDICAPPING MODEL
==============================
Unified framework for analyzing and predicting outcomes across multiple sports.

Supported Sports:
- Basketball (Euroleague/NBA) - Full game, Q1, Player Props
- Soccer - Goals totals, Corner totals, BTTS

Features:
- CSV-based data input system
- Sport-specific analysis engines
- Unified output and logging
- Modular architecture for easy expansion
- European Basketball-specific templates

Author: Basketball Analytics Suite
Date: May 2026
"""

import math
import os
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict

# Try to import pandas, fall back to csv module if not available
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

# Import shared utilities to avoid duplication
from core.utils import (
    sigmoid, clamp, to_num, to_bool, color_score,
    poisson_pmf, poisson_over_prob, poisson_at_least_one
)


# ============================================================================
# CONFIGURATION
# ============================================================================

INPUT_CSV = "input/multisport_input.csv"
OUTPUT_CSV = "output/multisport_results.csv"
LOG_CSV = "output/model_log.csv"

# Record types supported
RECORD_TYPES = ["game", "q1", "prop", "soccer_goals", "soccer_corners", "soccer_btts"]

# Probability thresholds for recommendations
PROB_THRESHOLD_LEAN = 0.57
PROB_THRESHOLD_STRONG = 0.63
PROB_THRESHOLD_MODERATE = 0.57
PROB_THRESHOLD_SLIGHT = 0.53


# ============================================================================
# UTILITY FUNCTIONS (Shared across all sports)
# ============================================================================



def score_to_prob(score: float) -> float:
    """Convert raw score to win probability"""
    return clamp(sigmoid((score - 4.0) / 2.5))


# ============================================================================
# DATA CLASSES (European Basketball Template)
# ============================================================================

@dataclass
class GameContext:
    """Context information for a game"""
    game_id: str
    date: str
    league: str
    record_type: str
    home_team: str
    away_team: str
    market_line: float
    current_line: float
    open_line: float
    notes: Optional[str] = None


@dataclass
class TeamMetrics:
    """Team performance metrics"""
    ortg: float
    drtg: float
    baseline_net: float
    recent_net: float
    pace: float
    rest_days: int
    travel_km: float
    back_to_back: bool
    three_in_six: bool
    split_edge: float
    rotation_depth: int
    injury_status: str
    coach_stability: str
    motivation: str
    open_line: float
    current_line: float


@dataclass
class Q1Metrics:
    """First quarter specific metrics"""
    pts_for: float
    pts_against: float
    pace: float
    starting_five_net: float
    turnovers: float
    rebounds: float
    fg_pct: float
    three_pt_pct: float
    ft_rate: float
    home_edge: float
    coach_fast_start: str
    injury_status: str
    open_line: float
    current_line: float


@dataclass
class PlayerProp:
    """Player proposition bet metrics"""
    player_name: str
    team: str
    opponent: str
    prop_type: str
    prop_line: float
    player_avg: float
    minutes_proj: float
    usage_rate: float
    game_pace: float
    opp_def_rating: float
    opp_position_def_rating: float
    injury_boost: str
    blowout_risk: str
    role: str
    open_prop_line: float
    current_prop_line: float


# ============================================================================
# BASKETBALL ANALYSIS FUNCTIONS
# ============================================================================

def team_net_rating(ortg: float, drtg: float) -> float:
    """Calculate team net rating (ORTG - DRTG)"""
    return ortg - drtg


def efficiency_gap(home_ortg: float, home_drtg: float, away_ortg: float, away_drtg: float) -> float:
    """Calculate efficiency gap between home and away teams"""
    return team_net_rating(home_ortg, home_drtg) - team_net_rating(away_ortg, away_drtg)


def historical_efficiency_gap(current_gap: float, baseline_gap: float, recent_gap: float) -> float:
    """Blend current, baseline, and recent efficiency gaps"""
    return (current_gap - baseline_gap) * 0.6 + (recent_gap - baseline_gap) * 0.4


def pace_edge(home_pace: float, away_pace: float) -> float:
    """Calculate pace advantage/disadvantage"""
    return home_pace - away_pace


def rest_travel_score(rest_days: float, travel_km: float, back_to_back: bool, three_games_six_days: bool) -> float:
    """Score rest and travel factors"""
    score = 0
    score += 2 if rest_days >= 3 else 1 if rest_days == 2 else -1
    if travel_km >= 2000:
        score -= 2
    elif travel_km >= 1000:
        score -= 1
    if back_to_back:
        score -= 2
    if three_games_six_days:
        score -= 1
    return score


def home_away_score(home_split_edge: float, away_split_edge: float) -> float:
    """Calculate home/away split advantage"""
    return home_split_edge - away_split_edge


def context_score(rotation_depth, injury_status, coach_stability, motivation) -> float:
    """Score contextual factors (rotation, injuries, coaching, motivation)"""
    score = 0
    score += 2 if str(rotation_depth).strip().lower() == "green" else 0 if str(rotation_depth).strip().lower() == "yellow" else -2
    score += 2 if str(injury_status).strip().lower() == "green" else 0 if str(injury_status).strip().lower() == "yellow" else -2
    score += 1 if str(coach_stability).strip().lower() == "green" else 0 if str(coach_stability).strip().lower() == "yellow" else -1
    score += 1 if str(motivation).strip().lower() == "green" else 0 if str(motivation).strip().lower() == "yellow" else -1
    return score


def market_filter(open_line: float, current_line: float, model_edge: float) -> Tuple[int, str]:
    """Validate model edge against market movement"""
    if open_line is None or current_line is None:
        return 0, "Market filter skipped"
    movement = current_line - open_line
    score = 0
    if abs(model_edge - movement) <= 1.5:
        score += 2
    elif abs(model_edge - movement) <= 3.0:
        score += 1
    else:
        score -= 2
    if abs(current_line) >= 8.5:
        score -= 1
    return score, f"Open line: {open_line}, Current line: {current_line}, Movement: {movement}"


def project_basketball_q1(home: Dict, away: Dict) -> Dict:
    """
    Project first quarter outcomes for basketball games.
    
    Args:
        home: Dictionary containing home team metrics (ortg, drtg, pace, rotation_depth, etc.)
        away: Dictionary containing away team metrics (ortg, drtg, pace, rotation_depth, etc.)
    
    Returns:
        Dictionary with Q1 projections including points, spread, total, and probabilities
    """
    avg_q1_possessions = 20
    
    home_q1_efficiency = home["ortg"] * 0.93
    away_q1_efficiency = away["ortg"] * 0.93
    
    home_q1_points = (home_q1_efficiency / 100) * avg_q1_possessions * (100 / away["drtg"])
    away_q1_points = (away_q1_efficiency / 100) * avg_q1_possessions * (100 / home["drtg"])
    
    avg_pace = (home["pace"] + away["pace"]) / 2
    pace_factor = avg_pace / 70
    home_q1_points *= pace_factor
    away_q1_points *= pace_factor
    
    home_q1_points *= 1.05  # Home court advantage in Q1
    
    home_ctx = context_score(home["rotation_depth"], home["injury_status"], 
                             home["coach_stability"], home["motivation"])
    away_ctx = context_score(away["rotation_depth"], away["injury_status"], 
                             away["coach_stability"], away["motivation"])
    ctx_adjustment = (home_ctx - away_ctx) * 0.3
    
    home_q1_points += ctx_adjustment * 0.5
    away_q1_points -= ctx_adjustment * 0.5
    
    q1_spread = home_q1_points - away_q1_points
    q1_total = home_q1_points + away_q1_points
    
    q1_score = q1_spread * 0.7
    q1_prob_home = clamp(sigmoid(q1_score / 3.0))
    
    tie_prob = 0.08
    q1_prob_home_ml = q1_prob_home * (1 - tie_prob) + tie_prob * 0.5
    
    return {
        "home_q1_points": round(home_q1_points, 1),
        "away_q1_points": round(away_q1_points, 1),
        "q1_spread": round(q1_spread, 1),
        "q1_total": round(q1_total, 1),
        "q1_prob_home_win": round(q1_prob_home, 3),
        "q1_prob_home_ml": round(q1_prob_home_ml, 3),
        "q1_pace_factor": round(pace_factor, 2),
        "q1_ctx_adjustment": round(ctx_adjustment, 2)
    }


def eu_efficiency_gap(team: TeamMetrics, opp: TeamMetrics) -> float:
    """Calculate efficiency gap between team and opponent (European template)"""
    return (team.ortg - team.drtg) - (opp.ortg - opp.drtg)


def eu_historical_gap(current_gap: float, baseline_gap: float, recent_gap: float) -> float:
    """Blend current, baseline, and recent efficiency gaps (European template)"""
    return (current_gap - baseline_gap) * 0.6 + (recent_gap - baseline_gap) * 0.4


def eu_rest_travel_score(rest_days: int, travel_km: float, back_to_back: bool, three_in_six: bool) -> float:
    """Score rest and travel factors (European template)"""
    score = 0.0
    if rest_days >= 3:
        score += 2.0
    elif rest_days == 2:
        score += 1.0
    else:
        score -= 1.0
    if travel_km >= 2000:
        score -= 2.0
    elif travel_km >= 1000:
        score -= 1.0
    if back_to_back:
        score -= 2.0
    if three_in_six:
        score -= 1.0
    return score


def eu_team_context_score(rotation_depth: int, injury_status: str, coach_stability: str, motivation: str) -> float:
    """Score contextual factors for a team (European template)"""
    score = 0.0
    if rotation_depth >= 10:
        score += 1.0
    elif rotation_depth <= 7:
        score -= 1.0
    score += color_score(injury_status)
    score += color_score(coach_stability) * 0.5
    score += color_score(motivation) * 0.5
    return score


def eu_market_filter(open_line: float, current_line: float, model_edge: float) -> float:
    """Validate model edge against market movement (European template)"""
    movement = current_line - open_line
    if abs(model_edge - movement) < 1.5:
        return 2.0
    if abs(model_edge - movement) < 3.0:
        return 1.0
    return -1.0


def eu_home_away_split(home_split_edge: float, away_split_edge: float) -> float:
    """Calculate home/away split advantage (European template)"""
    return home_split_edge - away_split_edge


def eu_score_to_prob(score: float) -> float:
    """Convert raw score to win probability (European version)"""
    return clamp(sigmoid((score - 4.0) / 2.5))


def eu_recommendation(prob: float, market_ok: bool) -> str:
    """Generate recommendation based on probability and market validation (European template)"""
    if not market_ok:
        return "Pass"
    if prob >= 0.63:
        return "Strong lean"
    if prob >= 0.57:
        return "Moderate lean"
    if prob >= 0.53:
        return "Slight lean"
    return "Pass"


def eu_build_full_game(home: TeamMetrics, away: TeamMetrics, ctx: GameContext) -> Dict[str, Any]:
    """Build full game prediction using European template"""
    current_gap = eu_efficiency_gap(home, away)
    baseline_gap = home.baseline_net - away.baseline_net
    recent_gap = home.recent_net - away.recent_net
    hist_gap = eu_historical_gap(current_gap, baseline_gap, recent_gap)
    rest_gap = eu_rest_travel_score(home.rest_days, home.travel_km, home.back_to_back, home.three_in_six) - \
               eu_rest_travel_score(away.rest_days, away.travel_km, away.back_to_back, away.three_in_six)
    split_gap = eu_home_away_split(home.split_edge, away.split_edge)
    ctx_gap = eu_team_context_score(home.rotation_depth, home.injury_status, home.coach_stability, home.motivation) - \
              eu_team_context_score(away.rotation_depth, away.injury_status, away.coach_stability, away.motivation)
    model_edge = hist_gap * 0.8 + rest_gap * 0.9 + split_gap * 0.6 + ctx_gap * 0.8
    market_score = eu_market_filter(ctx.open_line, ctx.current_line, model_edge)
    total_score = model_edge + market_score * 0.9
    prob = eu_score_to_prob(total_score)
    market_ok = market_score >= 0
    lean = eu_recommendation(prob, market_ok)
    return {
        "record_type": "full_game",
        "current_gap": round(current_gap, 2),
        "baseline_gap": round(baseline_gap, 2),
        "recent_gap": round(recent_gap, 2),
        "historical_gap": round(hist_gap, 2),
        "rest_gap": round(rest_gap, 2),
        "split_gap": round(split_gap, 2),
        "context_gap": round(ctx_gap, 2),
        "model_edge": round(model_edge, 2),
        "market_score": round(market_score, 2),
        "probability": round(prob, 4),
        "lean": lean,
        "projected_home_score": round(80 + total_score * 2.0, 1),
        "projected_away_score": round(78 - total_score * 1.0, 1),
        "projected_total": round(158 + total_score, 1),
    }


def eu_build_q1(home: TeamMetrics, away: TeamMetrics, q1: Q1Metrics, ctx: GameContext) -> Dict[str, Any]:
    """Build Q1 prediction using European template"""
    q1_model = (
        (q1.pts_for - q1.pts_against) * 0.8
        + q1.home_edge * 0.7
        + color_score(q1.coach_fast_start) * 0.8
        + color_score(q1.injury_status) * 0.7
        + (q1.starting_five_net * 0.4)
    )
    q1_market_ok = abs((q1.current_line - q1.open_line)) <= 3.0
    prob = eu_score_to_prob(q1_model)
    lean = eu_recommendation(prob, q1_market_ok)
    return {
        "record_type": "q1",
        "q1_model": round(q1_model, 2),
        "probability": round(prob, 4),
        "lean": lean,
        "projected_q1_home": round(q1.pts_for + q1.home_edge * 0.5, 1),
        "projected_q1_away": round(q1.pts_against - q1.home_edge * 0.2, 1),
        "projected_q1_total": round(q1.pts_for + q1.pts_against, 1),
    }


def eu_build_prop(prop: PlayerProp, team: TeamMetrics, opp: TeamMetrics, expected_pace: float) -> Dict[str, Any]:
    """Build player prop prediction using European template"""
    pace_factor = expected_pace / max(team.pace, 1e-6)
    matchup = (opp.drtg - 110.0) * 0.05 + (opp.drtg - prop.opp_position_def_rating) * 0.03
    role_factor = {"starter": 1.0, "sixth": 0.9, "bench": 0.75}.get(prop.role.lower(), 0.9)
    minutes_factor = prop.minutes_proj / 28.0
    injury_factor = {"green": 1.0, "yellow": 0.95, "red": 0.85}.get(prop.injury_boost.lower(), 0.95)
    blowout_factor = {"green": 1.0, "yellow": 0.95, "red": 0.85}.get(prop.blowout_risk.lower(), 0.95)
    model_projection = prop.player_avg * pace_factor * role_factor * minutes_factor * injury_factor * blowout_factor + matchup
    edge = model_projection - prop.prop_line
    return {
        "record_type": "prop",
        "player_name": prop.player_name,
        "team": prop.team,
        "opponent": prop.opponent,
        "prop_type": prop.prop_type,
        "prop_line": prop.prop_line,
        "model_projection": round(model_projection, 2),
        "edge": round(edge, 2),
        "minutes_proj": prop.minutes_proj,
        "usage_rate": prop.usage_rate,
        "role": prop.role,
        "open_prop_line": prop.open_prop_line,
        "current_prop_line": prop.current_prop_line,
    }


def eu_export_json(records: List[Dict[str, Any]], path: str) -> None:
    """Export records to JSON file"""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(records, f, indent=2)


def eu_export_csv(records: List[Dict[str, Any]], path: str) -> None:
    """Export records to CSV file"""
    if not records:
        return
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)


# ============================================================================
# BASKETBALL PROCESSORS
# ============================================================================

def _extract_basketball_team_data(row: Dict, prefix: str) -> Dict:
    """Extract team-specific basketball data from a row with given prefix ('home' or 'away').

    Cleans up the bloated dictionaries in process_basketball_game.
    """
    return {
        "ortg": to_num(row.get(f"{prefix}_ortg")),
        "drtg": to_num(row.get(f"{prefix}_drtg")),
        "baseline_net": to_num(row.get(f"{prefix}_baseline_net")),
        "recent_net": to_num(row.get(f"{prefix}_recent_net")),
        "pace": to_num(row.get(f"{prefix}_pace")),
        "rest_days": int(to_num(row.get(f"{prefix}_rest_days"), 0)),
        "travel_km": to_num(row.get(f"{prefix}_travel_km"), 0),
        "back_to_back": to_bool(row.get(f"{prefix}_back_to_back")),
        "three_in_six": to_bool(row.get(f"{prefix}_three_in_six")),
        "split_edge": to_num(row.get(f"{prefix}_split_edge")),
        "rotation_depth": int(to_num(row.get(f"{prefix}_rotation_depth"), 8)),
        "injury_status": str(row.get(f"{prefix}_injury_status", "yellow")),
        "coach_stability": str(row.get(f"{prefix}_coach_stability", "yellow")),
        "motivation": str(row.get(f"{prefix}_motivation", "yellow")),
        "open_line": to_num(row.get(f"{prefix}_open_line"), 0),
        "current_line": to_num(row.get(f"{prefix}_current_line"), 0),
    }


def process_basketball_game(row: Dict) -> Dict:
    """Process a basketball game record"""
    home_tm = _extract_basketball_team_data(row, "home")
    away_tm = _extract_basketball_team_data(row, "away")

    home_ortg = home_tm["ortg"]

    home_drtg = to_num(row.get("home_drtg"))
    away_ortg = to_num(row.get("away_ortg"))
    away_drtg = to_num(row.get("away_drtg"))
    
    current_gap = efficiency_gap(home_ortg, home_drtg, away_ortg, away_drtg)
    baseline_gap = to_num(row.get("home_baseline_net")) - to_num(row.get("away_baseline_net"))
    recent_gap = to_num(row.get("home_recent_net")) - to_num(row.get("away_recent_net"))
    hist_gap = historical_efficiency_gap(current_gap, baseline_gap, recent_gap)
    pace_gap = pace_edge(to_num(row.get("home_pace")), to_num(row.get("away_pace")))
    
    home_rest = rest_travel_score(to_num(row.get("home_rest_days")), 0, False, False)
    away_rest = rest_travel_score(
        to_num(row.get("away_rest_days")), to_num(row.get("away_travel_km")),
        to_bool(row.get("away_back_to_back")), to_bool(row.get("away_three_in_six"))
    )
    rest_gap = home_rest - away_rest
    
    split_gap = home_away_score(to_num(row.get("home_split_edge")), to_num(row.get("away_split_edge")))
    ctx_gap = context_score(
        row.get("home_rotation_depth"), row.get("home_injury_status"),
        row.get("home_coach_stability"), row.get("home_motivation")
    )
    
    model_edge = hist_gap * 0.8 + rest_gap * 0.9 + split_gap * 0.6 + ctx_gap * 0.8 + pace_gap * 0.15
    market_score, market_text = market_filter(
        to_num(row.get("home_open_line")), to_num(row.get("home_current_line")), model_edge
    )
    total_score = model_edge + market_score * 0.9
    prob_home = score_to_prob(total_score)
    
    if market_score < 0:
        lean = "Pass"
    elif prob_home >= 0.60:
        lean = f"Lean {row.get('home_team', '')}"
    elif prob_home <= 0.40:
        lean = f"Lean {row.get('away_team', '')}"
    else:
        lean = "Pass"
    
    home = {
        "ortg": home_ortg, "drtg": home_drtg,
        "pace": to_num(row.get("home_pace")),
        "rotation_depth": row.get("home_rotation_depth", "yellow"),
        "injury_status": row.get("home_injury_status", "yellow"),
        "coach_stability": row.get("home_coach_stability", "yellow"),
        "motivation": row.get("home_motivation", "yellow")
    }
    away = {
        "ortg": away_ortg, "drtg": away_drtg,
        "pace": to_num(row.get("away_pace")),
        "rotation_depth": row.get("away_rotation_depth", "yellow"),
        "injury_status": row.get("away_injury_status", "yellow"),
        "coach_stability": row.get("away_coach_stability", "yellow"),
        "motivation": row.get("away_motivation", "yellow")
    }
    q1_proj = project_basketball_q1(home, away)
    
    q1_market_line = to_num(row.get("home_current_line"), 0) * 0.4
    q1_edge = q1_proj["q1_spread"] - q1_market_line
    if abs(q1_edge) >= 2.0:
        q1_lean = f"Lean {row.get('home_team', '')} Q1 {q1_market_line:+.1f}" if q1_edge > 0 else f"Lean {row.get('away_team', '')} Q1 {-q1_market_line:+.1f}"
    else:
        q1_lean = "Pass Q1"
    
    # Also run European template analysis
    eu_result = {}
    try:
        ctx = GameContext(
            game_id=row.get("game_id", ""),
            date=row.get("date", ""),
            league=row.get("league", ""),
            record_type="full_game",
            home_team=row.get("home_team", ""),
            away_team=row.get("away_team", ""),
            market_line=to_num(row.get("market_line"), 0),
            current_line=to_num(row.get("current_line"), 0),
            open_line=to_num(row.get("open_line"), 0),
            notes=row.get("notes", "")
        )
        home_tm = TeamMetrics(
            ortg=home_ortg, drtg=home_drtg,
            baseline_net=to_num(row.get("home_baseline_net")),
            recent_net=to_num(row.get("home_recent_net")),
            pace=to_num(row.get("home_pace")),
            rest_days=int(to_num(row.get("home_rest_days"), 0)),
            travel_km=0,
            back_to_back=False,
            three_in_six=False,
            split_edge=to_num(row.get("home_split_edge")),
            rotation_depth=int(to_num(row.get("home_rotation_depth"), 8)),
            injury_status=str(row.get("home_injury_status", "yellow")),
            coach_stability=str(row.get("home_coach_stability", "yellow")),
            motivation=str(row.get("home_motivation", "yellow")),
            open_line=to_num(row.get("home_open_line"), 0),
            current_line=to_num(row.get("home_current_line"), 0)
        )
        away_tm = TeamMetrics(
            ortg=away_ortg, drtg=away_drtg,
            baseline_net=to_num(row.get("away_baseline_net")),
            recent_net=to_num(row.get("away_recent_net")),
            pace=to_num(row.get("away_pace")),
            rest_days=int(to_num(row.get("away_rest_days"), 0)),
            travel_km=to_num(row.get("away_travel_km"), 0),
            back_to_back=to_bool(row.get("away_back_to_back")),
            three_in_six=to_bool(row.get("away_three_in_six")),
            split_edge=to_num(row.get("away_split_edge")),
            rotation_depth=int(to_num(row.get("away_rotation_depth"), 8)),
            injury_status=str(row.get("away_injury_status", "yellow")),
            coach_stability=str(row.get("away_coach_stability", "yellow")),
            motivation=str(row.get("away_motivation", "yellow")),
            open_line=to_num(row.get("away_open_line"), 0),
            current_line=to_num(row.get("away_current_line"), 0)
        )
        eu_result = eu_build_full_game(home_tm, away_tm, ctx)
    except Exception:
        pass
    
    return {
        "model_score": round(total_score, 4),
        "model_prob": round(prob_home, 4),
        "lean": lean,
        "q1_proj_home": q1_proj["home_q1_points"],
        "q1_proj_away": q1_proj["away_q1_points"],
        "q1_spread": q1_proj["q1_spread"],
        "q1_total": q1_proj["q1_total"],
        "q1_prob_home": q1_proj["q1_prob_home_win"],
        "q1_lean": q1_lean,
        "details": f"current_gap={current_gap:.2f}; hist_gap={hist_gap:.2f}; pace_gap={pace_gap:.2f}; rest_gap={rest_gap:.2f}; split_gap={split_gap:.2f}; ctx_gap={ctx_gap:.2f}; {market_text}; q1_spread={q1_proj['q1_spread']:+.1f}; q1_total={q1_proj['q1_total']:.1f}",
        **eu_result
    }


def process_basketball_q1(row: Dict) -> Dict:
    """Process a basketball Q1 record"""
    score = 0
    score += (to_num(row.get("q1_pts_for")) - to_num(row.get("q1_pts_against"))) * 0.25
    score += (to_num(row.get("q1_pace")) - 20) * 0.10
    score += to_num(row.get("q1_starting_five_net")) * 0.30
    score += (to_num(row.get("q1_rebounds")) - to_num(row.get("q1_turnovers"))) * 0.10
    score += (to_num(row.get("q1_fg_pct")) - 45) * 0.08
    score += (to_num(row.get("q1_3pt_pct")) - 33) * 0.05
    score += (to_num(row.get("q1_ft_rate")) - 20) * 0.04
    score += to_num(row.get("q1_home_edge")) * 0.50
    score += color_score(row.get("q1_coach_fast_start")) * 1.0
    score += color_score(row.get("q1_injury_status")) * 1.0
    
    market_text = "Q1 market skipped"
    q1_open_line = row.get("q1_open_line")
    if q1_open_line is not None and (not HAS_PANDAS or not pd.isna(q1_open_line)):
        market_score, market_text = market_filter(
            to_num(q1_open_line), to_num(row.get("q1_current_line")), score
        )
        score += market_score * 0.7
    
    prob = score_to_prob(score)
    lean = "Pass"
    if prob >= 0.60:
        lean = f"Lean {row.get('home_team', '')} Q1"
    elif prob <= 0.40:
        lean = f"Lean {row.get('away_team', '')} Q1"
    
    return {
        "model_score": round(score, 4),
        "model_prob": round(prob, 4),
        "lean": lean,
        "details": market_text
    }


def process_basketball_prop(row: Dict) -> Dict:
    """Process a basketball player prop record"""
    score = 0
    score += (to_num(row.get("player_avg")) - to_num(row.get("prop_line"))) * 0.35
    score += (to_num(row.get("minutes_proj")) - 20) * 0.20
    score += (to_num(row.get("usage_rate")) - 20) * 0.08
    score += (to_num(row.get("game_pace")) - 70) * 0.05
    score += (to_num(row.get("opp_def_rating")) - 100) * -0.03
    score += (to_num(row.get("opp_position_def_rating")) - 100) * -0.03
    score += color_score(row.get("injury_boost")) * 1.0
    score -= color_score(row.get("blowout_risk")) * 1.0
    
    role = str(row.get("role", "")).strip().lower()
    score += 1.0 if role == "starter" else 0.2 if role == "sixth" else -0.3
    
    open_prop_line = row.get("open_prop_line")
    current_prop_line = row.get("current_prop_line")
    if open_prop_line and current_prop_line:
        score += (to_num(open_prop_line) - to_num(current_prop_line)) * 0.25
    
    prob = score_to_prob(score)
    lean = "Pass"
    if prob >= 0.60:
        lean = f"Lean Over {row.get('player_name', '')} {row.get('prop_type', '')}"
    elif prob <= 0.40:
        lean = f"Lean Under {row.get('player_name', '')} {row.get('prop_type', '')}"
    
    return {
        "model_score": round(score, 4),
        "model_prob": round(prob, 4),
        "lean": lean,
        "details": f"player_avg={to_num(row.get('player_avg')):.2f}; minutes={to_num(row.get('minutes_proj')):.2f}; usage={to_num(row.get('usage_rate')):.2f}; pace={to_num(row.get('game_pace')):.2f}"
    }


# ============================================================================
# SOCCER-SPECIFIC FUNCTIONS (Goals & Corners) - Advanced Poisson Model
# ============================================================================

LEAGUE_CONFIGS = {
    'A-League': {
        'goal_variance': 1.05,
        'corner_multiplier': 1.0,
        'travel_fatigue_threshold': 2000,
        'avg_goals_per_game': 2.85
    },
    'Bundesliga': {
        'goal_variance': 1.10,
        'corner_multiplier': 1.15,
        'travel_fatigue_threshold': 500,
        'avg_goals_per_game': 3.10
    },
    'NZ_National_League': {
        'goal_variance': 1.35,
        'corner_multiplier': 0.95,
        'travel_fatigue_threshold': 1000,
        'avg_goals_per_game': 3.55
    },
    'default': {
        'goal_variance': 1.0,
        'corner_multiplier': 1.0,
        'travel_fatigue_threshold': 1500,
        'avg_goals_per_game': 2.70
    }
}


def get_league_config(league_name: str) -> Dict:
    """Get league-specific configuration"""
    return LEAGUE_CONFIGS.get(league_name, LEAGUE_CONFIGS['default'])


def apply_travel_fatigue_modifier(is_home: bool, travel_km: float, league_config: Dict) -> float:
    """Apply travel fatigue modifier based on league thresholds"""
    if is_home:
        return 1.0
    threshold = league_config.get('travel_fatigue_threshold', 2000)
    if travel_km > threshold:
        return 0.85
    return 1.0


class SoccerHandicapper:
    """A model designed to predict Goals (HT/FT) and Corners"""
    
    def __init__(self, league_name: str):
        self.league = league_name
        self.config = get_league_config(league_name)
        self.data = None

    def load_data(self, df) -> 'SoccerHandicapper':
        self.data = df
        return self

    def calculate_tactical_metrics(self) -> 'SoccerHandicapper':
        if self.data is None or not HAS_PANDAS:
            return self
        self.data['rolling_xg_ht'] = self.data.groupby('team')['xg_ht'].transform(
            lambda x: x.rolling(5, min_periods=1).mean())
        self.data['rolling_corners'] = self.data.groupby('team')['corners'].transform(
            lambda x: x.rolling(5, min_periods=1).mean())
        avg_passes = self.data['passes_final_third'].mean() * 2
        self.data['field_tilt_score'] = self.data['passes_final_third'] / avg_passes if avg_passes > 0 else 0.5
        self.data['ppda'] = self.data['passes_final_third'] / self.data['defensive_actions'].replace(0, 1)
        return self

    def predict_match(self, home_team: str, away_team: str, h_travel: float = 0, a_travel: float = 0) -> Dict:
        if self.data is None:
            return {
                'match': f"{home_team} vs {away_team}",
                'exp_goals_ht': 0,
                'exp_corners_total': 0,
                'over_0.5_ht_prob': 0,
                'over_10.5_corners_prob': 0
            }
        home_data = self.data[self.data['team'] == home_team]
        away_data = self.data[self.data['team'] == away_team]
        home_xg_avg = home_data['rolling_xg_ht'].iloc[-1] if len(home_data) > 0 else 1.0
        away_xg_avg = away_data['rolling_xg_ht'].iloc[-1] if len(away_data) > 0 else 1.0
        home_corner_avg = home_data['rolling_corners'].iloc[-1] if len(home_data) > 0 else 5.0
        away_corner_avg = away_data['rolling_corners'].iloc[-1] if len(away_data) > 0 else 5.0
        h_mod = apply_travel_fatigue_modifier(True, h_travel, self.config)
        a_mod = apply_travel_fatigue_modifier(False, a_travel, self.config)
        exp_goals_ht = (home_xg_avg + away_xg_avg) * self.config['goal_variance'] * (h_mod * a_mod)
        exp_corners = (home_corner_avg + away_corner_avg) * self.config['corner_multiplier']
        try:
            over_05_ht_prob = 1 - math.exp(-exp_goals_ht)
            over_105_corners_prob = 1 - sum(math.exp(-exp_corners) * exp_corners**k / math.factorial(k) for k in range(0, 11))
        except Exception:
            over_05_ht_prob = 0.5
            over_105_corners_prob = 0.5
        return {
            'match': f"{home_team} vs {away_team}",
            'exp_goals_ht': round(exp_goals_ht, 2),
            'exp_corners_total': round(exp_corners, 2),
            'over_0.5_ht_prob': round(over_05_ht_prob, 4),
            'over_10.5_corners_prob': round(over_105_corners_prob, 4)
        }




def team_goal_strength(xg_for: float, xg_against: float, shots: float, sot: float,
                       goals_for: float, goals_against: float, tempo: float,
                       home: int, missing_attacker: int, missing_creator: int,
                       missing_cb: int, missing_gk: int) -> float:
    """Calculate team goal strength score"""
    score = 0.0
    score += 1.25 * (xg_for - 1.35)
    score += -0.95 * (xg_against - 1.25)
    score += 0.12 * (shots - 11)
    score += 0.18 * (sot - 4)
    score += 0.10 * (goals_for - 1.2)
    score += -0.10 * (goals_against - 1.1)
    score += 0.25 * tempo
    score += 0.20 * home
    score += -0.30 * missing_attacker
    score += -0.22 * missing_creator
    score += 0.24 * (missing_cb + missing_gk)
    return score


def team_btts_strength(xg_for: float, xg_against: float, goals_for: float,
                       goals_against: float, sot: float, tempo: float,
                       final_third_pressure: float, missing_attacker: int,
                       missing_cb: int, missing_gk: int, clean_sheets_last10: int) -> float:
    """Calculate team BTTS strength score"""
    score = 0.0
    score += 1.05 * (xg_for - 1.20)
    score += 0.95 * (xg_against - 1.25)
    score += 0.10 * (goals_for - 1.2)
    score += 0.10 * (goals_against - 1.1)
    score += 0.12 * (sot - 3.5)
    score += 0.18 * tempo
    score += 0.15 * final_third_pressure
    score += -0.35 * missing_attacker
    score += 0.28 * (missing_cb + missing_gk)
    score += -0.20 * clean_sheets_last10 / 10.0
    return score


def team_corner_strength(shots: float, sot: float, final_third_pressure: float,
                         width_crossing: float, tempo: float, home: int,
                         missing_cb: int, missing_gk: int, missing_attacker: int) -> float:
    """Calculate team corner strength score"""
    score = 0.0
    score += 0.28 * (shots - 12)
    score += 0.18 * (sot - 4)
    score += 0.90 * final_third_pressure
    score += 0.75 * width_crossing
    score += 0.25 * tempo
    score += 0.30 * home
    score += 0.25 * (missing_cb + missing_gk)
    score += -0.20 * missing_attacker
    return score


def estimate_team_goals(team_xg_for: float, team_sot: float, team_tempo: float,
                        team_home: int, team_missing_attacker: int, team_missing_creator: int,
                        opp_xg_against: float, opp_missing_cb: int, opp_missing_gk: int) -> float:
    """Estimate team's expected goals"""
    lam = 0.55 * team_xg_for + 0.30 * opp_xg_against + 0.15 * team_sot
    lam += 0.10 * team_tempo + 0.10 * team_home
    lam += -0.15 * team_missing_attacker - 0.10 * team_missing_creator
    lam += 0.12 * (opp_missing_cb + opp_missing_gk)
    return max(0.20, lam)


def estimate_btts_prob(home_xg_for: float, away_xg_for: float,
                       home_btts_strength: float, away_btts_strength: float) -> float:
    """Estimate BTTS probability"""
    p_home_scores = poisson_at_least_one(max(0.25, home_xg_for))
    p_away_scores = poisson_at_least_one(max(0.25, away_xg_for))
    structural = sigmoid((home_btts_strength + away_btts_strength) / 2.0)
    return clamp(0.45 * structural + 0.55 * (p_home_scores * p_away_scores))


def estimate_corner_total(home_corner_strength: float, away_corner_strength: float,
                          weather_penalty: float, referee_flow: float,
                          must_win_home: int, must_win_away: int) -> float:
    """Estimate total corners"""
    base = 9.2
    total = base + 0.75 * (home_corner_strength + away_corner_strength)
    total += -0.15 * weather_penalty
    total += 0.10 * referee_flow
    total += 0.20 * (must_win_home + must_win_away)
    return max(4.0, total)


def market_recommendation(over_prob: float, line: float, threshold: float = PROB_THRESHOLD_LEAN) -> str:
    """Generate market recommendation based on probability"""
    if over_prob >= threshold:
        return f"Over {line}"
    elif over_prob <= 1 - threshold:
        return f"Under {line}"
    return "Pass"


def btts_recommendation(btts_prob: float, threshold: float = PROB_THRESHOLD_LEAN) -> str:
    """Generate BTTS market recommendation"""
    if btts_prob >= threshold:
        return "BTTS Yes"
    elif btts_prob <= 1 - threshold:
        return "BTTS No"
    return "Pass"


# ============================================================================
# SOCCER DATA EXTRACTION HELPERS
# ============================================================================

def _extract_soccer_team_data(row: Dict, prefix: str, defaults: Dict = None) -> Dict:
    """Extract team-specific soccer data from a row with given prefix.
    
    Args:
        row: The data row
        prefix: 'home' or 'away'
        defaults: Dictionary of default values for missing fields
    
    Returns:
        Dictionary with extracted team data
    """
    if defaults is None:
        defaults = {}
    
    default_map = {
        'xg_for': defaults.get('xg_for', 1.5 if prefix == 'home' else 1.3),
        'xg_against': defaults.get('xg_against', 1.25 if prefix == 'home' else 1.35),
        'shots': defaults.get('shots', 12 if prefix == 'home' else 11),
        'sot': defaults.get('sot', 4 if prefix == 'home' else 3.5),
        'goals_for': defaults.get('goals_for', 1.3 if prefix == 'home' else 1.1),
        'goals_against': defaults.get('goals_against', 1.1 if prefix == 'home' else 1.2),
        'clean_sheets': defaults.get('clean_sheets', 3 if prefix == 'home' else 2),
        'missing_attacker': defaults.get('missing_attacker', 0),
        'missing_creator': defaults.get('missing_creator', 0),
        'missing_cb': defaults.get('missing_cb', 0),
        'missing_gk': defaults.get('missing_gk', 0),
        'tempo': defaults.get('tempo', 0),
        'width_crossing': defaults.get('width_crossing', 0.5),
        'final_third_pressure': defaults.get('final_third_pressure', 0.5),
    }
    
    return {
        'xg_for': to_num(row.get(f"{prefix}_xg_for"), default_map['xg_for']),
        'xg_against': to_num(row.get(f"{prefix}_xg_against"), default_map['xg_against']),
        'shots': to_num(row.get(f"{prefix}_shots"), default_map['shots']),
        'sot': to_num(row.get(f"{prefix}_sot"), default_map['sot']),
        'goals_for': to_num(row.get(f"{prefix}_goals_for"), default_map['goals_for']),
        'goals_against': to_num(row.get(f"{prefix}_goals_against"), default_map['goals_against']),
        'clean_sheets': int(to_num(row.get(f"{prefix}_clean_sheets_last10"), default_map['clean_sheets'])),
        'missing_attacker': int(to_num(row.get(f"{prefix}_missing_attacker"), default_map['missing_attacker'])),
        'missing_creator': int(to_num(row.get(f"{prefix}_missing_creator"), default_map['missing_creator'])),
        'missing_cb': int(to_num(row.get(f"{prefix}_missing_cb"), default_map['missing_cb'])),
        'missing_gk': int(to_num(row.get(f"{prefix}_missing_gk"), default_map['missing_gk'])),
        'tempo': to_num(row.get(f"{prefix}_tempo"), default_map['tempo']),
        'width_crossing': to_num(row.get(f"{prefix}_width_crossing"), default_map['width_crossing']),
        'final_third_pressure': to_num(row.get(f"{prefix}_final_third_pressure"), default_map['final_third_pressure']),
        'advantage': 1 if prefix == 'home' else 0,
    }


def process_soccer_goals(row: Dict) -> Dict:
    """Process a soccer goals total record"""
    home = _extract_soccer_team_data(row, 'home')
    away = _extract_soccer_team_data(row, 'away')
    
    weather_penalty = to_num(row.get("weather_penalty"), 0)
    referee_flow = to_num(row.get("referee_flow"), 0)
    must_win_home = int(to_num(row.get("must_win_home"), 0))
    must_win_away = int(to_num(row.get("must_win_away"), 0))
    
    home_goal_strength = team_goal_strength(
        home['xg_for'], home['xg_against'], home['shots'], home['sot'],
        home['goals_for'], home['goals_against'], home['tempo'], home['advantage'],
        home['missing_attacker'], home['missing_creator'], home['missing_cb'], home['missing_gk']
    )
    away_goal_strength = team_goal_strength(
        away['xg_for'], away['xg_against'], away['shots'], away['sot'],
        away['goals_for'], away['goals_against'], away['tempo'], away['advantage'],
        away['missing_attacker'], away['missing_creator'], away['missing_cb'], away['missing_gk']
    )
    
    home_btts_strength = team_btts_strength(
        home['xg_for'], home['xg_against'], home['goals_for'], home['goals_against'],
        home['sot'], home['tempo'], home['final_third_pressure'], home['missing_attacker'],
        home['missing_cb'], home['missing_gk'], home['clean_sheets']
    )
    away_btts_strength = team_btts_strength(
        away['xg_for'], away['xg_against'], away['goals_for'], away['goals_against'],
        away['sot'], away['tempo'], away['final_third_pressure'], away['missing_attacker'],
        away['missing_cb'], away['missing_gk'], away['clean_sheets']
    )
    
    home_lam = estimate_team_goals(
        home['xg_for'], home['sot'], home['tempo'], home['advantage'],
        home['missing_attacker'], home['missing_creator'],
        away['xg_against'], away['missing_cb'], away['missing_gk']
    )
    away_lam = estimate_team_goals(
        away['xg_for'], away['sot'], away['tempo'], away['advantage'],
        away['missing_attacker'], away['missing_creator'],
        home['xg_against'], home['missing_cb'], home['missing_gk']
    )
    total_lam = home_lam + away_lam
    
    p_over_15 = poisson_over_prob(total_lam, 1.5)
    p_over_25 = poisson_over_prob(total_lam, 2.5)
    p_over_35 = poisson_over_prob(total_lam, 3.5)
    
    p_btts = estimate_btts_prob(home['xg_for'], away['xg_for'], home_btts_strength, away_btts_strength)
    
    market_line = to_num(row.get("market_line"), 2.5)
    
    if market_line <= 1.5:
        prob_over = p_over_15
    elif market_line <= 2.5:
        prob_over = p_over_25
    else:
        prob_over = p_over_35
    
    lean = market_recommendation(prob_over, market_line)
    
    return {
        "model_score": round(total_lam - market_line, 4),
        "model_prob": round(prob_over, 4),
        "lean": lean,
        "details": f"home_lam={home_lam:.2f}; away_lam={away_lam:.2f}; total_lam={total_lam:.2f}; p_over_25={p_over_25:.3f}; btts={p_btts:.3f}; home_strength={home_goal_strength:.2f}; away_strength={away_goal_strength:.2f}"
    }


def process_soccer_corners(row: Dict) -> Dict:
    """Process a soccer corners total record"""
    home = _extract_soccer_team_data(row, 'home', {'shots': 12, 'sot': 4})
    away = _extract_soccer_team_data(row, 'away', {'shots': 11, 'sot': 3.5})
    
    weather_penalty = to_num(row.get("weather_penalty"), 0)
    referee_flow = to_num(row.get("referee_flow"), 0)
    must_win_home = int(to_num(row.get("must_win_home"), 0))
    must_win_away = int(to_num(row.get("must_win_away"), 0))
    
    home_corner_strength = team_corner_strength(
        home['shots'], home['sot'], home['final_third_pressure'], home['width_crossing'],
        home['tempo'], home['advantage'], home['missing_cb'], home['missing_gk'], home['missing_attacker']
    )
    away_corner_strength = team_corner_strength(
        away['shots'], away['sot'], away['final_third_pressure'], away['width_crossing'],
        away['tempo'], away['advantage'], away['missing_cb'], away['missing_gk'], away['missing_attacker']
    )
    
    corner_total = estimate_corner_total(
        home_corner_strength, away_corner_strength,
        weather_penalty, referee_flow, must_win_home, must_win_away
    )
    
    p_corners_85 = poisson_over_prob(corner_total, 8.5)
    p_corners_95 = poisson_over_prob(corner_total, 9.5)
    p_corners_105 = poisson_over_prob(corner_total, 10.5)
    
    market_line = to_num(row.get("market_line"), 9.5)
    
    if market_line <= 8.5:
        prob_over = p_corners_85
    elif market_line <= 9.5:
        prob_over = p_corners_95
    else:
        prob_over = p_corners_105
    
    lean = market_recommendation(prob_over, market_line)
    
    return {
        "model_score": round(corner_total - market_line, 4),
        "model_prob": round(prob_over, 4),
        "lean": lean,
        "details": f"corner_total={corner_total:.2f}; home_corner_strength={home_corner_strength:.2f}; away_corner_strength={away_corner_strength:.2f}; p_over_95={p_corners_95:.3f}; market_line={market_line}"
    }


def process_soccer_btts(row: Dict) -> Dict:
    """Process a soccer BTTS record"""
    home = _extract_soccer_team_data(row, 'home')
    away = _extract_soccer_team_data(row, 'away')
    
    home_btts_strength = team_btts_strength(
        home['xg_for'], home['xg_against'], home['goals_for'], home['goals_against'],
        home['sot'], home['tempo'], home['final_third_pressure'], home['missing_attacker'],
        home['missing_cb'], home['missing_gk'], home['clean_sheets']
    )
    away_btts_strength = team_btts_strength(
        away['xg_for'], away['xg_against'], away['goals_for'], away['goals_against'],
        away['sot'], away['tempo'], away['final_third_pressure'], away['missing_attacker'],
        away['missing_cb'], away['missing_gk'], away['clean_sheets']
    )
    
    home_lam = estimate_team_goals(
        home['xg_for'], home['sot'], home['tempo'], home['advantage'],
        home['missing_attacker'], home['missing_creator'],
        away['xg_against'], away['missing_cb'], away['missing_gk']
    )
    away_lam = estimate_team_goals(
        away['xg_for'], away['sot'], away['tempo'], away['advantage'],
        away['missing_attacker'], away['missing_creator'],
        home['xg_against'], home['missing_cb'], home['missing_gk']
    )
    
    p_home_scores = poisson_at_least_one(max(0.25, home_lam))
    p_away_scores = poisson_at_least_one(max(0.25, away_lam))
    
    structural = sigmoid((home_btts_strength + away_btts_strength) / 2.0)
    btts_prob = clamp(0.45 * structural + 0.55 * (p_home_scores * p_away_scores))
    
    # Adjustments
    defensive_weakness = (home['xg_against'] + away['xg_against'] - 2.5) * 0.05
    btts_prob = clamp(btts_prob + defensive_weakness)
    
    missing_defenders = (home['missing_cb'] + home['missing_gk'] + away['missing_cb'] + away['missing_gk']) * 0.02
    btts_prob = clamp(btts_prob + missing_defenders)
    
    tempo_factor = (home['tempo'] + away['tempo']) * 0.03
    btts_prob = clamp(btts_prob + tempo_factor)
    
    lean = btts_recommendation(btts_prob)
    
    return {
        "model_score": round(btts_prob - 0.5, 4),
        "model_prob": round(btts_prob, 4),
        "lean": lean,
        "details": f"btts_prob={btts_prob:.3f}; home_lam={home_lam:.2f}; away_lam={away_lam:.2f}; p_home_scores={p_home_scores:.3f}; p_away_scores={p_away_scores:.3f}; home_btts_strength={home_btts_strength:.2f}; away_btts_strength={away_btts_strength:.2f}"
    }


# ============================================================================
# DATA HANDLING
# ============================================================================

def ensure_directories():
    """Ensure input and output directories exist"""
    Path("input").mkdir(parents=True, exist_ok=True)
    Path("output").mkdir(parents=True, exist_ok=True)


def ensure_template(path=INPUT_CSV):
    """Create template CSV if it doesn't exist"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    
    if not p.exists() or p.stat().st_size == 0:
        columns = [
            "record_type", "game_id", "date", "league", "home_team", "away_team",
            "entity_name", "stat_name", "stat_value", "secondary_value",
            "market_line", "current_line", "open_line", "notes",
            "home_ortg", "home_drtg", "home_baseline_net", "home_recent_net",
            "home_pace", "home_rest_days", "home_travel_km", "home_back_to_back",
            "home_three_in_six", "home_split_edge", "home_rotation_depth",
            "home_injury_status", "home_coach_stability", "home_motivation",
            "home_open_line", "home_current_line",
            "away_ortg", "away_drtg", "away_baseline_net", "away_recent_net",
            "away_pace", "away_rest_days", "away_travel_km", "away_back_to_back",
            "away_three_in_six", "away_split_edge", "away_rotation_depth",
            "away_injury_status", "away_coach_stability", "away_motivation",
            "away_open_line", "away_current_line",
            "q1_pts_for", "q1_pts_against", "q1_pace", "q1_starting_five_net",
            "q1_turnovers", "q1_rebounds", "q1_fg_pct", "q1_3pt_pct", "q1_ft_rate",
            "q1_home_edge", "q1_coach_fast_start", "q1_injury_status",
            "player_name", "team", "opponent", "prop_type", "prop_line",
            "player_avg", "minutes_proj", "usage_rate", "game_pace",
            "opp_def_rating", "opp_position_def_rating", "injury_boost",
            "blowout_risk", "role", "open_prop_line", "current_prop_line",
            "home_xg_for", "home_xg_against", "home_shots", "home_sot",
            "home_goals_for", "home_goals_against", "home_clean_sheets_last10",
            "home_missing_attacker", "home_missing_creator", "home_missing_cb", "home_missing_gk",
            "home_tempo", "home_width_crossing", "home_final_third_pressure",
            "away_xg_for", "away_xg_against", "away_shots", "away_sot",
            "away_goals_for", "away_goals_against", "away_clean_sheets_last10",
            "away_missing_attacker", "away_missing_creator", "away_missing_cb", "away_missing_gk",
            "away_tempo", "away_width_crossing", "away_final_third_pressure",
            "weather_penalty", "referee_flow", "must_win_home", "must_win_away"
        ]
        
        if HAS_PANDAS:
            pd.DataFrame(columns=columns).to_csv(p, index=False)
        else:
            with open(p, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
        
        return True
    return False


def read_csv(path) -> List[Dict]:
    """Read CSV file and return list of dictionaries"""
    if HAS_PANDAS:
        df = pd.read_csv(path)
        return df.to_dict('records')
    else:
        with open(path, 'r') as f:
            reader = csv.DictReader(f)
            return list(reader)


def write_csv(data: List[Dict], path: str):
    """Write list of dictionaries to CSV file"""
    if not data:
        return
    
    columns = list(data[0].keys())
    
    if HAS_PANDAS:
        pd.DataFrame(data).to_csv(path, index=False, columns=columns)
    else:
        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(data)


# ============================================================================
# MAIN PROCESSING ENGINE
# ============================================================================

def process_record(row: Dict) -> Dict:
    """Process a single record based on its type"""
    record_type = str(row.get("record_type", "")).strip().lower()
    
    processors = {
        "game": process_basketball_game,
        "q1": process_basketball_q1,
        "prop": process_basketball_prop,
        "soccer_goals": process_soccer_goals,
        "soccer_corners": process_soccer_corners,
        "soccer_btts": process_soccer_btts,
    }
    
    processor = processors.get(record_type)
    if processor:
        return processor(row)
    
    return {
        "model_score": None,
        "model_prob": None,
        "lean": "Skipped",
        "details": f"Unknown record_type: {record_type}"
    }


def run_universal_match(record_type: str, core: Dict, metrics: Dict) -> Dict:
    """
    Universal model entry point for programmatic access.

    Args:
        record_type: Type of record ('game', 'q1', 'prop', 'soccer_goals', 'soccer_corners', 'soccer_btts')
        core: Dictionary with common fields (home_team, away_team, league, date, market_line, etc.)
        metrics: Dictionary with sport-specific metrics using exact column names

    Returns:
        Dictionary with prediction results including model_score, model_prob, lean, and details
    """
    rt = str(record_type).strip().lower()

    row: Dict = {
        "record_type": rt,
        "game_id": core.get("game_id")
        or f"{core.get('league','')}-{core.get('date','')}-{core.get('home_team','')[:8]}-{core.get('away_team','')[:8]}",
        "date": core.get("date", ""),
        "league": core.get("league", ""),
        "home_team": core.get("home_team", ""),
        "away_team": core.get("away_team", ""),
        "entity_name": core.get("entity_name", ""),
        "stat_name": core.get("stat_name", ""),
        "stat_value": core.get("stat_value", ""),
        "secondary_value": core.get("secondary_value", ""),
        "market_line": core.get("market_line"),
        "current_line": core.get("current_line"),
        "open_line": core.get("open_line"),
        "notes": core.get("notes", ""),
    }

    row.update(metrics)
    result = process_record(row)

    return {
        "home_team": row.get("home_team", ""),
        "away_team": row.get("away_team", ""),
        "league": row.get("league", ""),
        "date": row.get("date", ""),
        "record_type": rt,
        "row": row,
        **result,
    }


def run_basketball_game_automated(
    home_team: str,
    away_team: str,
    league: str,
    date: str,
    market_line: float,
    current_line: float,
    open_line: float,
    home_params: Dict,
    away_params: Dict,
    notes: str = "",
) -> Dict:
    """
    Run a single basketball full-game record entirely in code.

    Args:
        home_params/away_params: Dictionary with keys matching CSV columns
            (ortg, drtg, baseline_net, recent_net, pace, rest_days, travel_km,
             back_to_back, three_in_six, split_edge, rotation_depth, injury_status,
             coach_stability, motivation)
    """
    row: Dict = {
        "record_type": "game",
        "game_id": f"{league}-{date}-{home_team[:8]}-{away_team[:8]}",
        "date": date,
        "league": league,
        "home_team": home_team,
        "away_team": away_team,
        "market_line": market_line,
        "current_line": current_line,
        "open_line": open_line,
        "notes": notes,
        "home_ortg": home_params.get("ortg"),
        "home_drtg": home_params.get("drtg"),
        "home_baseline_net": home_params.get("baseline_net"),
        "home_recent_net": home_params.get("recent_net"),
        "home_pace": home_params.get("pace"),
        "home_rest_days": home_params.get("rest_days"),
        "home_travel_km": home_params.get("travel_km"),
        "home_back_to_back": int(bool(home_params.get("back_to_back", False))),
        "home_three_in_six": int(bool(home_params.get("three_in_six", False))),
        "home_split_edge": home_params.get("split_edge"),
        "home_rotation_depth": home_params.get("rotation_depth"),
        "home_injury_status": home_params.get("injury_status"),
        "home_coach_stability": home_params.get("coach_stability"),
        "home_motivation": home_params.get("motivation"),
        "away_ortg": away_params.get("ortg"),
        "away_drtg": away_params.get("drtg"),
        "away_baseline_net": away_params.get("baseline_net"),
        "away_recent_net": away_params.get("recent_net"),
        "away_pace": away_params.get("pace"),
        "away_rest_days": away_params.get("rest_days"),
        "away_travel_km": away_params.get("travel_km"),
        "away_back_to_back": int(bool(away_params.get("back_to_back", False))),
        "away_three_in_six": int(bool(away_params.get("three_in_six", False))),
        "away_split_edge": away_params.get("split_edge"),
        "away_rotation_depth": away_params.get("rotation_depth"),
        "away_injury_status": away_params.get("injury_status"),
        "away_coach_stability": away_params.get("coach_stability"),
        "away_motivation": away_params.get("motivation"),
    }

    result = process_record(row)

    return {
        "home_team": home_team,
        "away_team": away_team,
        "league": league,
        "date": date,
        "row": row,
        **result,
    }


def main():
    """Main entry point for the multi-sport model"""
    import sys
    
    input_file = INPUT_CSV
    if len(sys.argv) > 2 and sys.argv[1] == "--input":
        input_file = sys.argv[2]
    
    print("=" * 80)
    print("MULTI-SPORT HANDICAPPING MODEL")
    print("=" * 80)
    print(f"Input file: {input_file}")
    
    ensure_directories()
    
    created = ensure_template()
    if created:
        print(f"\nCreated template: {INPUT_CSV}")
        print("Fill it with rows using record_type values:")
        print("  - game: Basketball full game")
        print("  - q1: Basketball first quarter")
        print("  - prop: Basketball player props")
        print("  - soccer_goals: Soccer goals total")
        print("  - soccer_corners: Soccer corners total")
        print("  - soccer_btts: Soccer both-teams-to-score")
        return
    
    try:
        records = read_csv(input_file)
        print(f"\nLoaded {len(records)} records from {input_file}")
    except Exception as e:
        print(f"\n[ERROR] Failed to read input file: {e}")
        return
    
    results = []
    for row in records:
        record_type = str(row.get("record_type", "")).strip().lower()
        
        base = {
            "timestamp": datetime.now().isoformat(),
            "record_type": record_type,
            "game_id": row.get("game_id", ""),
            "date": row.get("date", ""),
            "league": row.get("league", ""),
            "home_team": row.get("home_team", ""),
            "away_team": row.get("away_team", ""),
            "entity_name": row.get("entity_name", ""),
            "stat_name": row.get("stat_name", ""),
            "stat_value": row.get("stat_value", ""),
            "secondary_value": row.get("secondary_value", ""),
            "market_line": row.get("market_line", ""),
            "current_line": row.get("current_line", ""),
            "open_line": row.get("open_line", ""),
            "notes": row.get("notes", "")
        }
        
        res = process_record(row)
        results.append({**base, **res})
        
        sport = "Basketball" if record_type in ["game", "q1", "prop"] else "Soccer"
        print(f"\n[{sport}] {row.get('home_team', 'N/A')} vs {row.get('away_team', 'N/A')}")
        print(f"  Type: {record_type}")
        print(f"  Score: {res['model_score']}")
        print(f"  Probability: {res['model_prob']}")
        print(f"  Lean: {res['lean']}")
    
    output_columns = [
        "timestamp", "record_type", "game_id", "date", "league",
        "home_team", "away_team", "entity_name", "stat_name",
        "stat_value", "secondary_value", "market_line", "current_line",
        "open_line", "notes", "model_score", "model_prob", "lean", "details"
    ]
    
    write_csv(results, OUTPUT_CSV)
    
    print(f"\n{'=' * 80}")
    print("RESULTS SUMMARY")
    print(f"{'=' * 80}")
    
    total_records = len(results)
    leans = [r for r in results if r["lean"] not in ["Pass", "Skipped"]]
    passes = total_records - len(leans)
    
    print(f"Total Records Processed: {total_records}")
    print(f"Recommendations (Leans): {len(leans)}")
    print(f"Passes: {passes}")
    
    if leans:
        print(f"\n{'=' * 80}")
        print("RECOMMENDATIONS:")
        print(f"{'=' * 80}")
        for r in leans:
            print(f"  {r['lean']} | Prob: {r['model_prob']:.3f} | Score: {r['model_score']:.2f}")
            print(f"    {r['home_team']} vs {r['away_team']} ({r['league']})")
            print(f"    Details: {r['details']}")
            print()
    
    print(f"\nResults saved to: {OUTPUT_CSV}")
    print(f"{'=' * 80}")
    
    eu_results = [r for r in results if r.get("record_type") == "full_game"]
    if eu_results:
        eu_output_path = "output/european_template_results.json"
        eu_export_json(eu_results, eu_output_path)
        print(f"\nEuropean Template results saved to: {eu_output_path}")


def interactive_mode():
    """Interactive mode for analyzing a single game"""
    print("\n" + "=" * 80)
    print("INTERACTIVE MODE - Select Sport")
    print("=" * 80)
    print("1. Basketball (Full Game)")
    print("2. Basketball (First Quarter)")
    print("3. Soccer (Goals Total)")
    print("4. Soccer (Corners Total)")
    print("5. Soccer (BTTS)")
    print("6. Exit")
    
    choice = input("\nEnter choice (1-6): ").strip()
    
    if choice == "1":
        print("\n--- Basketball Full Game Analysis ---")
        print("Please use CSV input or the run_universal_match() function for now.")
    elif choice == "2":
        print("\n--- Basketball Q1 Analysis ---")
        print("Please use CSV input or the run_universal_match() function for now.")
    elif choice == "3":
        print("\n--- Soccer Goals Analysis ---")
        print("Please use CSV input or the run_universal_match() function for now.")
    elif choice == "4":
        print("\n--- Soccer Corners Analysis ---")
        print("Please use CSV input or the run_universal_match() function for now.")
    elif choice == "5":
        print("\n--- Soccer BTTS Analysis ---")
        print("Please use CSV input or the run_universal_match() function for now.")
    elif choice == "6":
        print("Goodbye!")
    else:
        print("Invalid choice. Please run again.")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_mode()
    elif len(sys.argv) > 1 and sys.argv[1] == "--auto-demo":
        # Universal automated demo: Manawatu Jets vs Wellington Saints
        today = datetime.now().strftime("%Y-%m-%d")

        core = {
            "home_team": "Manawatu Jets",
            "away_team": "Wellington Saints",
            "league": "NZNBL",
            "date": today,
            "market_line": -7.5,
            "current_line": -7.5,
            "open_line": -6.5,
            "notes": "Universal demo run: Jets vs Saints",
        }

        metrics = {
            # Home (Jets)
            "home_ortg": 106.0,
            "home_drtg": 113.0,
            "home_baseline_net": -5.0,
            "home_recent_net": -3.0,
            "home_pace": 73.0,
            "home_rest_days": 2,
            "home_travel_km": 0.0,
            "home_back_to_back": 0,
            "home_three_in_six": 0,
            "home_split_edge": 1.0,
            "home_rotation_depth": "yellow",
            "home_injury_status": "yellow",
            "home_coach_stability": "yellow",
            "home_motivation": "green",
            # Away (Saints)
            "away_ortg": 114.0,
            "away_drtg": 107.0,
            "away_baseline_net": 7.0,
            "away_recent_net": 6.0,
            "away_pace": 72.0,
            "away_rest_days": 3,
            "away_travel_km": 150.0,
            "away_back_to_back": 0,
            "away_three_in_six": 0,
            "away_split_edge": 2.0,
            "away_rotation_depth": "green",
            "away_injury_status": "green",
            "away_coach_stability": "green",
            "away_motivation": "green",
        }

        result = run_universal_match("game", core, metrics)

        print("=" * 80)
        print(f"UNIVERSAL DEMO: {result['home_team']} vs {result['away_team']} ({result['league']})")
        print("=" * 80)
        print(f"Type:        {result['record_type']}")
        print(f"Date:        {result['date']}")
        print(f"Score:       {result['model_score']}")
        print(f"Probability: {result['model_prob']}")
        print(f"Lean:        {result['lean']}")
        print(f"Details:     {result['details']}")
        print("=" * 80)
    else:
        main()