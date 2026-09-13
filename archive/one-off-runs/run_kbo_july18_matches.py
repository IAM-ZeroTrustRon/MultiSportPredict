#!/usr/bin/env python
"""
KBO July 18, 2026 Match Analysis
==================================
1. KIA Tigers vs SSG Landers (Incheon SSG Landers Field)
2. Kiwoom Heroes vs Hanwha Eagles (Daejeon Hanwha Life Ballpark)

Pushes strong bet recommendations to Discord with organized embeds.
"""

import sys
import os
import json
import math
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

from core.confidence_engine import confidence_score, bet_recommendation
from discord_integration import (
    create_organized_prediction_embed,
    COLORS,
)


# ============================================================================
# MATH UTILITIES
# ============================================================================

def sigmoid(x: float) -> float:
    x = max(-500, min(500, x))
    return 1 / (1 + math.exp(-x))

def clamp(x: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, x))

def poisson_over_prob(lam: float, line: float) -> float:
    n = int(math.floor(line))
    if abs(line - n) < 1e-9:
        return 1 - sum(math.exp(-lam) * lam**k / math.factorial(k) for k in range(0, n + 1))
    threshold = int(math.floor(line))
    return 1 - sum(math.exp(-lam) * lam**k / math.factorial(k) for k in range(0, threshold + 1))


# ============================================================================
# KBO CONFIGURATION
# ============================================================================

KBO_CONFIG = {
    'avg_runs_per_game': 10.2,
    'avg_hits_per_game': 10.5,
    'avg_home_runs_per_game': 1.8,
    'home_advantage': 0.35,
}

# ============================================================================
# TEAM STATS — Updated for July 18, 2026 based on user-provided context
# ============================================================================

def get_team_stats(team: str) -> Dict[str, Any]:
    """Get estimated team statistics for KBO teams based on current form."""
    t = team.upper().strip()

    # SSG Landers (Home vs KIA) — inconsistent, volatile H2H
    if "SSG" in t or "LANDERS" in t:
        return {
            'team_name': 'SSG Landers',
            'abbreviation': 'SSG',
            'runs_per_game': 5.2,
            'runs_allowed_per_game': 5.0,
            'batting_avg': 0.275,
            'on_base_pct': 0.345,
            'slugging_pct': 0.435,
            'ops': 0.780,
            'home_runs_per_game': 1.0,
            'strikeouts_per_game': 7.5,
            'walks_per_game': 3.5,
            'hits_per_game': 9.5,
            'era': 4.80,
            'whip': 1.42,
            'quality_start_pct': 0.40,
            'bullpen_era': 4.50,
            'recent_form': 0.50,
            'home_record': 0.55,
            'vs_opponent_record': 0.50,
        }

    # KIA Tigers (Away vs SSG) — 46-2 record, dominant offense
    if "KIA" in t or "TIGERS" in t:
        return {
            'team_name': 'KIA Tigers',
            'abbreviation': 'KIA',
            'runs_per_game': 5.8,
            'runs_allowed_per_game': 4.2,
            'batting_avg': 0.290,
            'on_base_pct': 0.360,
            'slugging_pct': 0.460,
            'ops': 0.820,
            'home_runs_per_game': 1.2,
            'strikeouts_per_game': 7.0,
            'walks_per_game': 3.8,
            'hits_per_game': 10.2,
            'era': 3.90,
            'whip': 1.28,
            'quality_start_pct': 0.55,
            'bullpen_era': 3.60,
            'recent_form': 0.80,
            'away_record': 0.70,
            'vs_opponent_record': 0.60,
        }

    # Kiwoom Heroes (Away vs Hanwha) — 5-game win streak vs Hanwha
    if "KIWOOM" in t or "HEROES" in t:
        return {
            'team_name': 'Kiwoom Heroes',
            'abbreviation': 'KIWOOM',
            'runs_per_game': 5.5,
            'runs_allowed_per_game': 4.8,
            'batting_avg': 0.282,
            'on_base_pct': 0.350,
            'slugging_pct': 0.450,
            'ops': 0.800,
            'home_runs_per_game': 1.1,
            'strikeouts_per_game': 7.2,
            'walks_per_game': 3.6,
            'hits_per_game': 10.0,
            'era': 4.40,
            'whip': 1.35,
            'quality_start_pct': 0.48,
            'bullpen_era': 4.10,
            'recent_form': 0.70,
            'away_record': 0.55,
            'vs_opponent_record': 0.75,  # Dominant vs Hanwha
        }

    # Hanwha Eagles (Home vs Kiwoom) — skidding, 40-42-2 record
    if "HANWHA" in t or "EAGLES" in t:
        return {
            'team_name': 'Hanwha Eagles',
            'abbreviation': 'HAN',
            'runs_per_game': 4.8,
            'runs_allowed_per_game': 5.5,
            'batting_avg': 0.265,
            'on_base_pct': 0.330,
            'slugging_pct': 0.410,
            'ops': 0.740,
            'home_runs_per_game': 0.9,
            'strikeouts_per_game': 8.0,
            'walks_per_game': 3.2,
            'hits_per_game': 9.0,
            'era': 5.20,
            'whip': 1.50,
            'quality_start_pct': 0.30,
            'bullpen_era': 5.00,
            'recent_form': 0.35,
            'home_record': 0.45,
            'vs_opponent_record': 0.25,  # 5 straight losses to Kiwoom
        }

    # Default
    return {
        'team_name': team,
        'abbreviation': team[:3].upper(),
        'runs_per_game': 5.0,
        'runs_allowed_per_game': 5.0,
        'batting_avg': 0.270,
        'on_base_pct': 0.340,
        'slugging_pct': 0.420,
        'ops': 0.760,
        'home_runs_per_game': 1.0,
        'strikeouts_per_game': 7.5,
        'walks_per_game': 3.5,
        'hits_per_game': 9.5,
        'era': 4.80,
        'whip': 1.40,
        'quality_start_pct': 0.40,
        'bullpen_era': 4.50,
        'recent_form': 0.50,
        'home_record': 0.50,
        'away_record': 0.45,
        'vs_opponent_record': 0.50,
    }


# ============================================================================
# CORE ANALYSIS FUNCTIONS
# ============================================================================

def project_team_runs(home_stats: Dict, away_stats: Dict) -> Tuple[float, float, float]:
    """Project runs for both teams."""
    home_offense = home_stats['runs_per_game'] / KBO_CONFIG['avg_runs_per_game'] * 2
    away_pitching = away_stats['era'] / 4.80
    home_lam = (home_offense * 0.4 + away_pitching * 0.4 + 1.0) * 2.2
    home_lam += KBO_CONFIG['home_advantage']
    home_lam *= (0.9 + home_stats['recent_form'] * 0.2)

    away_offense = away_stats['runs_per_game'] / KBO_CONFIG['avg_runs_per_game'] * 2
    home_pitching = home_stats['era'] / 4.80
    away_lam = (away_offense * 0.4 + home_pitching * 0.4 + 1.0) * 2.0
    away_lam *= 0.92
    away_lam *= (0.9 + away_stats['recent_form'] * 0.2)

    total_lam = home_lam + away_lam
    return home_lam, away_lam, total_lam


def calculate_win_probability(home_lam: float, away_lam: float) -> Dict[str, float]:
    """Calculate win probabilities."""
    total = home_lam + away_lam
    if total == 0:
        return {'home': 0.5, 'away': 0.5}
    home_win = home_lam / total
    home_win = home_win * 0.85 + 0.12
    return {'home': clamp(home_win), 'away': clamp(1 - home_win)}


def project_run_line(home_lam: float, away_lam: float, line: float = -1.5) -> Dict[str, Any]:
    """Project run line outcome."""
    spread = home_lam - away_lam
    edge = spread - line
    std_dev = 3.5
    z_score = edge / std_dev
    prob = sigmoid(z_score * 1.5)
    return {
        'model_spread': round(spread, 2),
        'market_line': line,
        'edge': round(edge, 2),
        'probability': round(prob, 3),
    }


def analyze_kbo_match(
    home_team: str,
    away_team: str,
    market_total: float = 9.5,
    market_spread: float = -1.5,
    venue: str = "KBO Stadium",
    date: str = "2026-07-18",
) -> Dict[str, Any]:
    """Comprehensive KBO match analysis."""
    home_stats = get_team_stats(home_team)
    away_stats = get_team_stats(away_team)

    home_lam, away_lam, total_lam = project_team_runs(home_stats, away_stats)

    # Over/Under probabilities
    p_over_75 = poisson_over_prob(total_lam, 7.5)
    p_over_85 = poisson_over_prob(total_lam, 8.5)
    p_over_95 = poisson_over_prob(total_lam, 9.5)
    p_over_105 = poisson_over_prob(total_lam, 10.5)

    # Win probability
    win_probs = calculate_win_probability(home_lam, away_lam)

    # Run line
    run_line_proj = project_run_line(home_lam, away_lam, market_spread)
    rl_confidence = confidence_score(run_line_proj['edge'], volatility=0.40)
    rl_recommendation = bet_recommendation(rl_confidence)

    # Totals
    totals_edge = total_lam - market_total
    if market_total <= 7.5:
        totals_prob = p_over_75
    elif market_total <= 8.5:
        totals_prob = p_over_85
    elif market_total <= 9.5:
        totals_prob = p_over_95
    else:
        totals_prob = p_over_105
    t_confidence = confidence_score(totals_edge, volatility=0.38)
    if totals_prob >= 0.57:
        t_recommendation = f"Over {market_total}"
    elif totals_prob <= 0.43:
        t_recommendation = f"Under {market_total}"
    else:
        t_recommendation = "Pass"

    # Moneyline
    home_ml_prob = win_probs['home']
    away_ml_prob = win_probs['away']
    if home_ml_prob >= 0.57:
        ml_recommendation = f"Moneyline {home_stats['team_name']}"
    elif away_ml_prob >= 0.57:
        ml_recommendation = f"Moneyline {away_stats['team_name']}"
    else:
        ml_recommendation = "Pass"

    # Team Totals
    home_team_over_55 = poisson_over_prob(home_lam, 5.5)
    away_team_over_45 = poisson_over_prob(away_lam, 4.5)

    # Player Props (Matt Davidson for Kiwoom, Na Sung-beom for KIA)
    player_props = {}
    if "KIWOOM" in away_stats['abbreviation'] or "KIWOOM" in home_stats['abbreviation']:
        # Matt Davidson — 7-for-10 post All-Star break, HR on July 17
        davidson_tb_proj = 1.8  # Total bases projection
        davidson_hr_prob = 0.18  # HR probability
        player_props['matt_davidson'] = {
            'total_bases': round(davidson_tb_proj, 2),
            'hr_probability': round(davidson_hr_prob, 3),
            'tb_line': 1.5,
            'tb_edge': round(davidson_tb_proj - 1.5, 2),
        }

    return {
        "game_info": {
            "home_team": home_stats['team_name'],
            "away_team": away_stats['team_name'],
            "league": "KBO",
            "date": date,
            "venue": venue,
        },
        "team_stats": {"home": home_stats, "away": away_stats},
        "projections": {
            "home_runs": round(home_lam, 2),
            "away_runs": round(away_lam, 2),
            "total_runs": round(total_lam, 2),
            "home_win_prob": round(win_probs['home'], 3),
            "away_win_prob": round(win_probs['away'], 3),
        },
        "totals_analysis": {
            "over_75_prob": round(p_over_75, 3),
            "over_85_prob": round(p_over_85, 3),
            "over_95_prob": round(p_over_95, 3),
            "over_105_prob": round(p_over_105, 3),
            "market_total": market_total,
            "model_total": round(total_lam, 2),
            "edge": round(totals_edge, 2),
            "over_probability": round(totals_prob, 3),
            "confidence": round(t_confidence, 1),
            "recommendation": t_recommendation,
        },
        "run_line_analysis": {
            "model_spread": run_line_proj['model_spread'],
            "market_line": run_line_proj['market_line'],
            "edge": run_line_proj['edge'],
            "cover_probability": run_line_proj['probability'],
            "confidence": round(rl_confidence, 1),
            "recommendation": rl_recommendation,
        },
        "moneyline_analysis": {
            "home_win_prob": round(home_ml_prob, 3),
            "away_win_prob": round(away_ml_prob, 3),
            "recommendation": ml_recommendation,
        },
        "team_totals": {
            "home_over_55_prob": round(home_team_over_55, 3),
            "away_over_45_prob": round(away_team_over_45, 3),
        },
        "player_props": player_props,
        "recommendations": {
            "run_line": rl_recommendation,
            "total": t_recommendation,
            "moneyline": ml_recommendation,
        },
        "timestamp": datetime.now().isoformat(),
    }


# ============================================================================
# BET CLASSIFICATION
# ============================================================================

def classify_kbo_bets(result: Dict[str, Any]) -> Tuple[List, List, List, Dict]:
    """Classify KBO betting markets into strong/medium/pass."""
    proj = result["projections"]
    totals = result["totals_analysis"]
    rl = result["run_line_analysis"]
    ml = result["moneyline_analysis"]
    tt = result["team_totals"]
    props = result.get("player_props", {})
    home = result["game_info"]["home_team"]
    away = result["game_info"]["away_team"]

    strong_bets = []
    medium_bets = []
    pass_bets = []

    # ---- Over/Under ----
    ou_prob = totals["over_probability"]
    ou_name = totals["recommendation"]
    ou_item = {"name": f"Total Runs {ou_name}", "prob": ou_prob * 100, "edge": f"Model {totals['model_total']:.1f}"}
    if ou_prob >= 0.60:
        strong_bets.append(ou_item)
    elif ou_prob >= 0.50:
        medium_bets.append(ou_item)
    else:
        pass_bets.append(ou_item)

    # ---- Moneyline ----
    home_win = ml["home_win_prob"]
    away_win = ml["away_win_prob"]
    if home_win >= 0.55:
        ml_item = {"name": f"Moneyline: {home}", "prob": home_win * 100, "edge": f"{home_win*100:.0f}% implied"}
        if home_win >= 0.60:
            strong_bets.append(ml_item)
        else:
            medium_bets.append(ml_item)
    elif away_win >= 0.55:
        ml_item = {"name": f"Moneyline: {away}", "prob": away_win * 100, "edge": f"{away_win*100:.0f}% implied"}
        if away_win >= 0.60:
            strong_bets.append(ml_item)
        else:
            medium_bets.append(ml_item)
    else:
        pass_bets.append({"name": "Moneyline", "prob": 50, "edge": "Too close"})

    # ---- Run Line ----
    rl_prob = rl["cover_probability"]
    rl_name = f"{home} {rl['market_line']:+.1f}" if rl_prob > 0.5 else f"{away} +{abs(rl['market_line']):.1f}"
    rl_item = {"name": f"Run Line: {rl_name}", "prob": rl_prob * 100, "edge": f"Spread {rl['model_spread']:+.2f}"}
    if rl_prob >= 0.60:
        strong_bets.append(rl_item)
    elif rl_prob >= 0.50:
        medium_bets.append(rl_item)
    else:
        pass_bets.append(rl_item)

    # ---- Team Totals ----
    home_tt = tt["home_over_55_prob"]
    if home_tt >= 0.50:
        tt_item = {"name": f"{home} Team Total Over 5.5", "prob": home_tt * 100, "edge": f"Proj {proj['home_runs']:.1f}"}
        if home_tt >= 0.55:
            strong_bets.append(tt_item)
        else:
            medium_bets.append(tt_item)

    away_tt = tt["away_over_45_prob"]
    if away_tt >= 0.50:
        tt_item = {"name": f"{away} Team Total Over 4.5", "prob": away_tt * 100, "edge": f"Proj {proj['away_runs']:.1f}"}
        if away_tt >= 0.55:
            strong_bets.append(tt_item)
        else:
            medium_bets.append(tt_item)

    # ---- Player Props ----
    if "matt_davidson" in props:
        md = props["matt_davidson"]
        tb_item = {"name": "Matt Davidson Total Bases Over 1.5", "prob": 65, "edge": f"Proj {md['total_bases']:.1f}"}
        strong_bets.append(tb_item)
        hr_item = {"name": "Matt Davidson HR", "prob": md['hr_probability'] * 100, "edge": f"{md['hr_probability']*100:.0f}% prob"}
        if md['hr_probability'] >= 0.15:
            medium_bets.append(hr_item)
        else:
            pass_bets.append(hr_item)

    # ---- Projected Stats ----
    projected_stats = {
        "Projected Score": f"{home} {proj['home_runs']:.1f} - {proj['away_runs']:.1f} {away}",
        "Expected Total": f"{proj['total_runs']:.1f} Runs",
        f"{home} Win": f"{proj['home_win_prob']*100:.1f}%",
        f"{away} Win": f"{proj['away_win_prob']*100:.1f}%",
    }

    return strong_bets, medium_bets, pass_bets, projected_stats


# ============================================================================
# DISCORD PUSH
# ============================================================================

def push_match_to_discord(result: Dict[str, Any]) -> bool:
    """Push a single match's organized prediction to Discord."""
    home = result["game_info"]["home_team"]
    away = result["game_info"]["away_team"]
    strong_bets, medium_bets, pass_bets, projected_stats = classify_kbo_bets(result)

    embed = create_organized_prediction_embed(
        sport="baseball",
        home=home,
        away=away,
        strong_bets=strong_bets,
        medium_bets=medium_bets,
        pass_bets=pass_bets,
        projected_stats=projected_stats,
    )

    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        logger.error("DISCORD_WEBHOOK_URL not set.")
        return False

    try:
        import requests
        payload = {"embeds": [embed]}
        resp = requests.post(webhook_url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
        if resp.status_code in (200, 204):
            logger.info(f"Pushed {home} vs {away} to Discord.")
            return True
        else:
            logger.error(f"Discord push failed: {resp.status_code}")
            return False
    except Exception as e:
        logger.error(f"Discord push error: {e}")
        return False


def push_slate_to_discord(all_results: List[Dict[str, Any]]) -> bool:
    """Push consolidated slate message."""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return False

    lines = ["[KBO SLATE - July 18, 2026 - 2 Matches]", ""]
    for r in all_results:
        info = r["game_info"]
        proj = r["projections"]
        lines.append(f"**{info['away_team']} @ {info['home_team']}** ({info['venue']})")
        lines.append(f"   |- Projected: {info['away_team']} {proj['away_runs']:.1f} - {proj['home_runs']:.1f} {info['home_team']}")
        lines.append(f"   |- Total: {proj['total_runs']:.1f}")
        lines.append(f"   |- {info['home_team']} Win: {proj['home_win_prob']:.0%} | {info['away_team']} Win: {proj['away_win_prob']:.0%}")
        strong_bets, _, _, _ = classify_kbo_bets(r)
        if strong_bets:
            recs = " | ".join([f"{b['name']}: {b['prob']:.0f}%" for b in strong_bets[:3]])
            lines.append(f"   |- STRONG: {recs}")
        lines.append("")

    lines.append("MultiSportPredict - KBO Smart Betting Guide")
    content = "\n".join(lines)

    try:
        import requests
        resp = requests.post(webhook_url, json={"content": content},
                             headers={"Content-Type": "application/json"}, timeout=15)
        return resp.status_code in (200, 204)
    except Exception as e:
        logger.error(f"Slate push error: {e}")
        return False


# ============================================================================
# MAIN
# ============================================================================

def print_match_summary(result: Dict[str, Any]):
    """Print terminal summary."""
    info = result["game_info"]
    proj = result["projections"]
    totals = result["totals_analysis"]
    rl = result["run_line_analysis"]
    ml = result["moneyline_analysis"]

    print(f"\n{'='*70}")
    print(f"  {info['away_team']} @ {info['home_team']}")
    print(f"  {info['league']} | {info['date']} | {info['venue']}")
    print(f"{'='*70}")
    print(f"  Projected: {info['away_team']} {proj['away_runs']:.1f} - {proj['home_runs']:.1f} {info['home_team']}")
    print(f"  Total: {proj['total_runs']:.1f}")
    print(f"  {info['home_team']} Win: {proj['home_win_prob']:.1%}")
    print(f"  {info['away_team']} Win: {proj['away_win_prob']:.1%}")
    print(f"  Over {totals['market_total']}: {totals['over_probability']:.1%} (Conf: {totals['confidence']:.0f}%)")
    print(f"  Run Line ({rl['market_line']:+.1f}): {rl['recommendation']} (Conf: {rl['confidence']:.0f}%)")
    print(f"  Moneyline: {ml['recommendation']}")

    strong_bets, medium_bets, pass_bets, _ = classify_kbo_bets(result)
    if strong_bets:
        print(f"\n  STRONG BETS:")
        for b in strong_bets:
            print(f"    [+] {b['name']}: {b['prob']:.0f}% ({b['edge']})")
    if medium_bets:
        print(f"\n  MEDIUM BETS:")
        for b in medium_bets:
            print(f"    [!] {b['name']}: {b['prob']:.0f}% ({b['edge']})")
    if pass_bets:
        print(f"\n  PASS:")
        for b in pass_bets:
            print(f"    [-] {b['name']}: {b['prob']:.0f}%")


def main():
    print("=" * 70)
    print("KBO MATCH ANALYSIS - July 18, 2026")
    print("=" * 70)

    # ── MATCH 1: KIA Tigers @ SSG Landers ──
    print("\n[MATCH 1] KIA Tigers @ SSG Landers (Incheon SSG Landers Field)")
    result1 = analyze_kbo_match(
        home_team="SSG Landers",
        away_team="KIA Tigers",
        market_total=9.5,
        market_spread=-1.5,
        venue="Incheon SSG Landers Field",
        date="2026-07-18",
    )
    print_match_summary(result1)

    # ── MATCH 2: Kiwoom Heroes @ Hanwha Eagles ──
    print("\n[MATCH 2] Kiwoom Heroes @ Hanwha Eagles (Daejeon Hanwha Life Ballpark)")
    result2 = analyze_kbo_match(
        home_team="Hanwha Eagles",
        away_team="Kiwoom Heroes",
        market_total=9.5,
        market_spread=-1.5,
        venue="Daejeon Hanwha Life Ballpark",
        date="2026-07-18",
    )
    print_match_summary(result2)

    # ── Push to Discord ──
    print("\nPushing to Discord...")
    all_results = [result1, result2]

    slate_ok = push_slate_to_discord(all_results)
    print(f"  Slate push: {'OK' if slate_ok else 'FAIL'}")

    match_results = []
    for r in all_results:
        ok = push_match_to_discord(r)
        match_results.append(ok)
        label = f"{r['game_info']['away_team']} @ {r['game_info']['home_team']}"
        print(f"  {label}: {'OK' if ok else 'FAIL'}")

    print("\nComplete!")
    print(f"  KIA Tigers @ SSG Landers: {'OK' if match_results[0] else 'FAILED'}")
    print(f"  Kiwoom Heroes @ Hanwha Eagles: {'OK' if match_results[1] else 'FAILED'}")


if __name__ == "__main__":
    main()