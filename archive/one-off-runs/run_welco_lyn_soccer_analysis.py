#!/usr/bin/env python
"""
Comprehensive Soccer Analysis for July 2, 2026
==============================================
Match 1: JK Welco Elekter vs Vimsi JK (Estonian Esiliiga)
Match 2: Lyn vs Asane (Norwegian OBOS-ligaen)

Markets: Corners, BTTS, Total Goals
Integrated with MultiSportPredict xG/Poisson modeling pipeline.
"""

import sys
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Import core confidence engine
from core.confidence_engine import confidence_score, bet_recommendation

# Import MultiSportModel functions
from MultiSportModel import (
    estimate_team_goals,
    estimate_btts_prob,
    poisson_over_prob,
    team_corner_strength,
    estimate_corner_total,
)


def sigmoid(x: float) -> float:
    x = max(-500, min(500, x))
    return 1 / (1 + math.exp(-x))


def clamp(x: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, x))


def poisson_pmf(k: int, lam: float) -> float:
    """Poisson probability mass function"""
    if lam <= 0:
        return 0.0 if k > 0 else 1.0
    if k < 0:
        return 0.0
    try:
        log_pmf = -lam + k * math.log(lam) - math.lgamma(k + 1)
        return math.exp(log_pmf)
    except (ValueError, OverflowError):
        return 0.0


def market_evaluation(prob: float, threshold: float = 0.57) -> Tuple[str, float]:
    """Evaluate if a probability offers value"""
    edge = prob - threshold
    if prob >= 0.63:
        return ("STRONG", edge)
    elif prob >= threshold:
        return ("VALUE", edge)
    elif prob >= 0.50:
        return ("SLIGHT", edge)
    else:
        return ("PASS", edge)


def sharp_consensus_estimate(
    model_prob: float,
    league_type: str,
    market_type: str
) -> Dict[str, Any]:
    """
    Estimate sharp money consensus based on model probability and league context.
    In production this would integrate with The Odds API / sharp betting data.
    """
    # Typical sharp alignment patterns
    sharp_threshold = 0.55  # Sharps typically bet above this threshold
    sharp_edge = model_prob - 0.50
    sharp_alignment = "NEUTRAL"

    if model_prob >= 0.60:
        sharp_pct = 0.65 + (model_prob - 0.60) * 1.5
        sharp_alignment = "SHARP ALIGNMENT"
    elif model_prob >= 0.55:
        sharp_pct = 0.50 + (model_prob - 0.55) * 2.0
        sharp_alignment = "LEANING SHARP"
    elif model_prob <= 0.40:
        sharp_pct = 0.60 + (0.40 - model_prob) * 1.5
        sharp_alignment = "SHARP AGAINST (FADE)"
    else:
        sharp_pct = 0.50
        sharp_alignment = "NO CLEAR PATTERN"

    sharp_pct = clamp(sharp_pct, 0.30, 0.85)

    # Public money typically goes opposite of sharps in soccer
    public_pct = 1.0 - sharp_pct

    return {
        "estimated_sharp_money_pct": round(sharp_pct * 100, 1),
        "estimated_public_money_pct": round(public_pct * 100, 1),
        "sharp_alignment": sharp_alignment,
        "model_edge": round(sharp_edge * 100, 1),
        "note": f"Sharps estimated at {sharp_pct:.0%} on this outcome ({sharp_alignment})"
    }


# ============================================================================
# MATCH 1: JK Welco Elekter vs Vimsi JK
# Estonian Esiliiga (2nd Division)
# ============================================================================

MATCH1_PROFILES = {
    "JK Welco Elekter": {
        "abbreviation": "WEL",
        "xg_for": 1.15,
        "xg_against": 1.60,
        "shots_per_game": 9.5,
        "sot_per_game": 3.2,
        "goals_for_per_game": 0.95,
        "goals_against_per_game": 1.70,
        "clean_sheets_last10": 1,
        "home_record": 0.30,
        "away_record": 0.15,
        "recent_form": 0.20,
        "tempo": 0.30,
        "width_crossing": 0.50,
        "final_third_pressure": 0.35,
        "missing_attacker": 1,
        "missing_creator": 0,
        "missing_cb": 0,
        "missing_gk": 0,
        "btts_strength": 0.65,       # Likely to concede, can score sometimes
        "corner_gen_style": "possession",
        "corners_for": 4.5,
        "corners_against": 5.8,
        "possession_pct": 48.0,
        "notes": "Lower-tier Estonian club. Weak offense, porous defense. Struggles to create quality chances. Relies on set pieces for goals."
    },
    "Vimsi JK": {
        "abbreviation": "VIM",
        "xg_for": 1.30,
        "xg_against": 1.45,
        "shots_per_game": 10.2,
        "sot_per_game": 3.6,
        "goals_for_per_game": 1.10,
        "goals_against_per_game": 1.55,
        "clean_sheets_last10": 2,
        "home_record": 0.35,
        "away_record": 0.20,
        "recent_form": 0.25,
        "tempo": 0.32,
        "width_crossing": 0.48,
        "final_third_pressure": 0.38,
        "missing_attacker": 0,
        "missing_creator": 0,
        "missing_cb": 1,
        "missing_gk": 0,
        "btts_strength": 0.60,
        "corner_gen_style": "counter",
        "corners_for": 4.8,
        "corners_against": 5.2,
        "possession_pct": 50.0,
        "notes": "Mid-table Estonian 2nd division side. Decent attacking output for the level. Solid but unspectacular. Missing a center back."
    }
}

MATCH1_LEAGUE_CONFIG = {
    "name": "Estonian Esiliiga",
    "avg_goals_per_game": 2.80,
    "goal_variance": 1.05,
    "home_advantage": 0.30,
    "draw_rate": 0.24,
    "avg_corners_per_game": 10.5,
    "corner_variance": 1.10,
    "btts_rate": 0.55,
    "avg_cards_per_game": 4.5,
    "sharp_liquidity": "LOW",
}


# ============================================================================
# MATCH 2: Lyn vs Asane
# Norwegian OBOS-ligaen (1st Division)
# ============================================================================

MATCH2_PROFILES = {
    "Lyn": {
        "abbreviation": "LYN",
        "xg_for": 1.55,
        "xg_against": 1.30,
        "shots_per_game": 12.5,
        "sot_per_game": 4.5,
        "goals_for_per_game": 1.45,
        "goals_against_per_game": 1.20,
        "clean_sheets_last10": 3,
        "home_record": 0.55,
        "away_record": 0.35,
        "recent_form": 0.50,
        "tempo": 0.40,
        "width_crossing": 0.58,
        "final_third_pressure": 0.55,
        "missing_attacker": 0,
        "missing_creator": 0,
        "missing_cb": 0,
        "missing_gk": 1,
        "btts_strength": 0.52,
        "corner_gen_style": "possession",
        "corners_for": 5.8,
        "corners_against": 4.2,
        "possession_pct": 54.0,
        "notes": "Strong OBOS-ligaen side. Good attacking output with above-average xG creation. Solid defensively. Missing goalkeeper. Corner generation is strong due to sustained pressure."
    },
    "Asane": {
        "abbreviation": "ASA",
        "xg_for": 1.25,
        "xg_against": 1.50,
        "shots_per_game": 10.8,
        "sot_per_game": 3.8,
        "goals_for_per_game": 1.15,
        "goals_against_per_game": 1.45,
        "clean_sheets_last10": 2,
        "home_record": 0.40,
        "away_record": 0.25,
        "recent_form": 0.30,
        "tempo": 0.35,
        "width_crossing": 0.52,
        "final_third_pressure": 0.42,
        "missing_attacker": 0,
        "missing_creator": 1,
        "missing_cb": 0,
        "missing_gk": 0,
        "btts_strength": 0.58,
        "corner_gen_style": "counter",
        "corners_for": 4.5,
        "corners_against": 5.5,
        "possession_pct": 46.0,
        "notes": "Mid-table OBOS-ligaen team. Below-average attack. Leaky defense. Missing key creator, which will hamper chance creation. Vulnerable on the road."
    }
}

MATCH2_LEAGUE_CONFIG = {
    "name": "Norwegian OBOS-ligaen",
    "avg_goals_per_game": 2.75,
    "goal_variance": 1.02,
    "home_advantage": 0.40,
    "draw_rate": 0.22,
    "avg_corners_per_game": 11.0,
    "corner_variance": 1.05,
    "btts_rate": 0.52,
    "avg_cards_per_game": 3.8,
    "sharp_liquidity": "MODERATE",
}


def analyze_match(
    match_label: str,
    home_team: str,
    away_team: str,
    profiles: Dict,
    league_config: Dict,
    market_total_goals: float = 2.5,
    market_corners: float = 9.5,
    date: str = "2026-07-02",
):
    """Run comprehensive analysis for a single match"""
    home = profiles[home_team]
    away = profiles[away_team]

    generation_time = datetime.now().strftime("%Y-%m-%d %H:%M")

    # --- 1. xG / GOAL PROJECTION ---
    home_lam = estimate_team_goals(
        home['xg_for'], home['sot_per_game'], home['tempo'], 1,
        home['missing_attacker'], home['missing_creator'],
        away['xg_against'], away['missing_cb'], away['missing_gk']
    )
    away_lam = estimate_team_goals(
        away['xg_for'], away['sot_per_game'], away['tempo'], 0,
        away['missing_attacker'], away['missing_creator'],
        home['xg_against'], home['missing_cb'], home['missing_gk']
    )

    # Apply league variance
    home_lam *= league_config['goal_variance']
    away_lam *= league_config['goal_variance']

    total_lam = home_lam + away_lam

    # --- 2. MATCH OUTCOME PROBABILITIES ---
    max_goals = 6
    home_win_prob = 0.0
    draw_prob = 0.0
    away_win_prob = 0.0

    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            p = poisson_pmf(i, home_lam) * poisson_pmf(j, away_lam)
            if i > j:
                home_win_prob += p
            elif i == j:
                draw_prob += p
            else:
                away_win_prob += p

    total_prob = home_win_prob + draw_prob + away_win_prob
    if total_prob > 0:
        home_win_prob /= total_prob
        draw_prob /= total_prob
        away_win_prob /= total_prob

    draw_prob = draw_prob * 0.8 + league_config['draw_rate'] * 0.2
    remaining = 1 - draw_prob
    home_win_prob = home_win_prob * remaining / (home_win_prob + away_win_prob + 0.001)
    away_win_prob = 1 - home_win_prob - draw_prob

    # --- 3. TOTAL GOALS MARKET ---
    p_over_15 = poisson_over_prob(total_lam, 1.5)
    p_over_25 = poisson_over_prob(total_lam, 2.5)
    p_over_35 = poisson_over_prob(total_lam, 3.5)
    p_over_45 = poisson_over_prob(total_lam, 4.5)

    # Market-specific probability
    if market_total_goals <= 1.5:
        totals_prob = p_over_15
    elif market_total_goals <= 2.5:
        totals_prob = p_over_25
    elif market_total_goals <= 3.5:
        totals_prob = p_over_35
    else:
        totals_prob = p_over_45

    totals_edge = total_lam - market_total_goals
    totals_conf = confidence_score(totals_edge, volatility=0.50)
    totals_rec = bet_recommendation(totals_conf)
    totals_eval = market_evaluation(totals_prob)

    # Under probability
    under_prob = 1 - totals_prob

    # --- 4. BTTS MARKET ---
    btts_prob = estimate_btts_prob(home['xg_for'], away['xg_for'],
                                     home.get('btts_strength', 0.5), away.get('btts_strength', 0.5))
    # Blend with league BTTS rate
    btts_prob = btts_prob * 0.7 + league_config['btts_rate'] * 0.3
    btts_no_prob = 1 - btts_prob

    btts_edge = btts_prob - 0.50
    btts_conf = confidence_score(btts_edge * 100, volatility=0.48)
    btts_rec = bet_recommendation(btts_conf)
    btts_eval = market_evaluation(btts_prob)

    # --- 5. CORNERS MARKET ---
    home_corner_strength = team_corner_strength(
        home['shots_per_game'], home['sot_per_game'], home['final_third_pressure'],
        home['width_crossing'], home['tempo'], 1,
        home['missing_cb'], home['missing_gk'], home['missing_attacker']
    )
    away_corner_strength = team_corner_strength(
        away['shots_per_game'], away['sot_per_game'], away['final_third_pressure'],
        away['width_crossing'], away['tempo'], 0,
        away['missing_cb'], away['missing_gk'], away['missing_attacker']
    )
    model_corner_total = estimate_corner_total(
        home_corner_strength, away_corner_strength,
        0, 0, 0, 0
    )

    # Recalibrated: offense vs opponent defense
    home_corners_recal = (home['corners_for'] + away['corners_against']) / 2
    away_corners_recal = (away['corners_for'] + home['corners_against']) / 2
    recalibrated_total = home_corners_recal + away_corners_recal

    # Blend model + recalibrated + league average
    league_corner_avg = league_config['avg_corners_per_game']
    blended_corner_total = (
        0.35 * model_corner_total +
        0.45 * recalibrated_total +
        0.20 * league_corner_avg
    ) * league_config['corner_variance']

    # Corner probabilities at various lines
    p_corners_85 = poisson_over_prob(blended_corner_total, 8.5)
    p_corners_95 = poisson_over_prob(blended_corner_total, 9.5)
    p_corners_105 = poisson_over_prob(blended_corner_total, 10.5)
    p_corners_115 = poisson_over_prob(blended_corner_total, 11.5)

    if market_corners <= 8.5:
        corners_prob = p_corners_85
    elif market_corners <= 9.5:
        corners_prob = p_corners_95
    elif market_corners <= 10.5:
        corners_prob = p_corners_105
    else:
        corners_prob = p_corners_115

    corners_edge = blended_corner_total - market_corners
    corners_conf = confidence_score(corners_edge, volatility=0.60)
    corners_rec = bet_recommendation(corners_conf)
    corners_eval = market_evaluation(corners_prob)

    under_corners_prob = 1 - corners_prob

    # --- 6. SHARP CONSENSUS ---
    totals_sharp = sharp_consensus_estimate(totals_prob, league_config['sharp_liquidity'], "totals")
    btts_sharp = sharp_consensus_estimate(btts_prob, league_config['sharp_liquidity'], "btts")
    corners_sharp = sharp_consensus_estimate(corners_prob, league_config['sharp_liquidity'], "corners")

    # --- PRINT ANALYSIS ---
    print("=" * 90)
    print(f"{match_label}")
    print(f"{home_team} vs {away_team}")
    print(f"League: {league_config['name']} | Date: {date}")
    print(f"Generated: {generation_time}")
    print(f"Liquidity: {league_config['sharp_liquidity']}")
    print("=" * 90)

    # Team stats
    print(f"\n============== TEAM STATISTICS ==============")
    for label, stats in [(f"  {home_team} (Home):", home), (f"  {away_team} (Away):", away)]:
        print(label)
        print(f"    xG For: {stats['xg_for']:.2f} | xG Against: {stats['xg_against']:.2f}")
        print(f"    Goals For: {stats['goals_for_per_game']:.2f} | Goals Against: {stats['goals_against_per_game']:.2f}")
        print(f"    Shots/Game: {stats['shots_per_game']:.1f} | SOT/Game: {stats['sot_per_game']:.1f}")
        print(f"    Corners For: {stats['corners_for']:.1f} | Corners Against: {stats['corners_against']:.1f}")
        print(f"    Corner Style: {stats['corner_gen_style']}")
        print(f"    Form: {stats['recent_form']:.0%} | Clean Sheets (L10): {stats['clean_sheets_last10']}")
        print(f"    Injuries: A={stats['missing_attacker']} Cr={stats['missing_creator']} CB={stats['missing_cb']} GK={stats['missing_gk']}")
        print(f"    Notes: {stats['notes']}")
        print()

    # Match outcome
    print(f"============== MATCH OUTCOME ==============")
    print(f"  Projected Score: {home_team} {home_lam:.2f} - {away_team} {away_lam:.2f}")
    print(f"  Total xG: {total_lam:.2f}")
    print(f"  1X2: {home_team} {home_win_prob:.1%} | Draw {draw_prob:.1%} | {away_team} {away_win_prob:.1%}")

    # Goals
    print(f"\n============== TOTAL GOALS MARKET ==============")
    print(f"  Market Line: Over/Under {market_total_goals:.1f}")
    print(f"  Goal Line Probabilities:")
    print(f"    Over 1.5: {p_over_15:.1%} | Over 2.5: {p_over_25:.1%}")
    print(f"    Over 3.5: {p_over_35:.1%} | Over 4.5: {p_over_45:.1%}")
    print(f"  Model Projection: {total_lam:.2f} goals")
    print(f"  Over {market_total_goals:.1f} Probability: {totals_prob:.1%}")
    print(f"  Under {market_total_goals:.1f} Probability: {under_prob:.1%}")
    print(f"  Edge vs Market: {totals_edge:+.2f} goals")
    print(f"  Confidence Score: {totals_conf:.1f}/100")
    print(f"  Recommendation: {totals_rec}")
    print(f"  Verdict: {totals_eval[0]}")

    # Sharp consensus - totals
    print(f"  +- Sharp Consensus:")
    print(f"       Sharp Money: {totals_sharp['estimated_sharp_money_pct']:.1f}%")
    print(f"       Public Money: {totals_sharp['estimated_public_money_pct']:.1f}%")
    print(f"       Signal: {totals_sharp['sharp_alignment']}")

    # BTTS
    print(f"\n============== BOTH TEAMS TO SCORE (BTTS) ==============")
    print(f"  BTTS Yes Probability: {btts_prob:.1%}")
    print(f"  BTTS No Probability: {btts_no_prob:.1%}")
    print(f"  League BTTS Rate: {league_config['btts_rate']:.0%}")
    print(f"  Edge: {btts_edge:+.2f}")
    print(f"  Confidence Score: {btts_conf:.1f}/100")
    print(f"  Recommendation: {btts_rec}")
    print(f"  Verdict: {btts_eval[0]}")

    print(f"  +- Sharp Consensus:")
    print(f"       Sharp Money: {btts_sharp['estimated_sharp_money_pct']:.1f}%")
    print(f"       Public Money: {btts_sharp['estimated_public_money_pct']:.1f}%")
    print(f"       Signal: {btts_sharp['sharp_alignment']}")

    # Corners
    print(f"\n============== CORNERS MARKET ==============")
    print(f"  Market Line: Over/Under {market_corners:.1f}")
    print(f"  Corner Source Data:")
    print(f"    {home_team}: {home['corners_for']:.1f} for | {home['corners_against']:.1f} against (style: {home['corner_gen_style']})")
    print(f"    {away_team}: {away['corners_for']:.1f} for | {away['corners_against']:.1f} against (style: {away['corner_gen_style']})")
    print(f"  League Avg Corners: {league_config['avg_corners_per_game']:.1f}")
    print(f"  Model Corner Total: {model_corner_total:.2f}")
    print(f"  Recalibrated Total: {recalibrated_total:.2f}")
    print(f"  Blended Projection: {blended_corner_total:.2f}")
    print(f"  Corner Line Probabilities:")
    print(f"    Over 8.5: {p_corners_85:.1%} | Over 9.5: {p_corners_95:.1%}")
    print(f"    Over 10.5: {p_corners_105:.1%} | Over 11.5: {p_corners_115:.1%}")
    print(f"  Over {market_corners:.1f} Probability: {corners_prob:.1%}")
    print(f"  Under {market_corners:.1f} Probability: {under_corners_prob:.1%}")
    print(f"  Edge vs Market: {corners_edge:+.2f} corners")
    print(f"  Confidence Score: {corners_conf:.1f}/100")
    print(f"  Recommendation: {corners_rec}")
    print(f"  Verdict: {corners_eval[0]}")

    print(f"  +- Sharp Consensus:")
    print(f"       Sharp Money: {corners_sharp['estimated_sharp_money_pct']:.1f}%")
    print(f"       Public Money: {corners_sharp['estimated_public_money_pct']:.1f}%")
    print(f"       Signal: {corners_sharp['sharp_alignment']}")

    print()

    # --- BUILD RESULT ---
    result = {
        "match": match_label,
        "home_team": home_team,
        "away_team": away_team,
        "league": league_config['name'],
        "date": date,
        "generated": generation_time,
        "liquidity": league_config['sharp_liquidity'],
        "projection": {
            "home_goals": round(home_lam, 3),
            "away_goals": round(away_lam, 3),
            "total_goals": round(total_lam, 3),
            "projected_score": f"{home_team} {home_lam:.1f} - {away_lam:.1f} {away_team}",
            "home_win_prob": round(home_win_prob, 4),
            "draw_prob": round(draw_prob, 4),
            "away_win_prob": round(away_win_prob, 4),
        },
        "totals_market": {
            "market_line": market_total_goals,
            "projected_total": round(total_lam, 3),
            "over_prob": round(totals_prob, 4),
            "under_prob": round(under_prob, 4),
            "edge": round(totals_edge, 3),
            "confidence": round(totals_conf, 1),
            "recommendation": totals_rec,
            "verdict": totals_eval[0],
            "goal_line_probs": {
                "over_1_5": round(p_over_15, 4),
                "over_2_5": round(p_over_25, 4),
                "over_3_5": round(p_over_35, 4),
                "over_4_5": round(p_over_45, 4),
            },
            "sharp_consensus": totals_sharp,
        },
        "btts_market": {
            "market": "BTTS Yes/No",
            "yes_prob": round(btts_prob, 4),
            "no_prob": round(btts_no_prob, 4),
            "edge": round(btts_edge, 4),
            "confidence": round(btts_conf, 1),
            "recommendation": btts_rec,
            "verdict": btts_eval[0],
            "sharp_consensus": btts_sharp,
        },
        "corners_market": {
            "market_line": market_corners,
            "model_total": round(model_corner_total, 3),
            "recalibrated_total": round(recalibrated_total, 3),
            "blended_projection": round(blended_corner_total, 3),
            "over_prob": round(corners_prob, 4),
            "under_prob": round(under_corners_prob, 4),
            "edge": round(corners_edge, 3),
            "confidence": round(corners_conf, 1),
            "recommendation": corners_rec,
            "verdict": corners_eval[0],
            "corner_line_probs": {
                "over_8_5": round(p_corners_85, 4),
                "over_9_5": round(p_corners_95, 4),
                "over_10_5": round(p_corners_105, 4),
                "over_11_5": round(p_corners_115, 4),
            },
            "corner_source": {
                "home_corners_for": home['corners_for'],
                "home_corners_against": home['corners_against'],
                "home_corner_style": home['corner_gen_style'],
                "away_corners_for": away['corners_for'],
                "away_corners_against": away['corners_against'],
                "away_corner_style": away['corner_gen_style'],
                "league_avg": league_config['avg_corners_per_game'],
            },
            "sharp_consensus": corners_sharp,
        },
    }

    return result


def print_summary_table(results: List[Dict]):
    """Print a concise betting summary table"""
    print("\n" + "=" * 90)
    print("BETTING SUMMARY - RECOMMENDATIONS")
    print("=" * 90)

    for r in results:
        print(f"\n{r['match']}")
        print(f"  {'Market':<20} {'Prob':>6} {'Edge':>7} {'Conf':>5} {'Rec':>6} {'Verdict':<10} {'Sharp Signal':<20}")
        print(f"  {'-'*20} {'-'*6} {'-'*7} {'-'*5} {'-'*6} {'-'*10} {'-'*20}")

        t = r['totals_market']
        print(f"  {'Over '+str(t['market_line'])+'G':<20} {t['over_prob']:>6.1%} {t['edge']:>+7.2f} {t['confidence']:>5.1f} {t['recommendation']:>6} {t['verdict']:<10} {t['sharp_consensus']['sharp_alignment']:<20}")

        b = r['btts_market']
        print(f"  {'BTTS Yes':<20} {b['yes_prob']:>6.1%} {b['edge']:>+7.2f} {b['confidence']:>5.1f} {b['recommendation']:>6} {b['verdict']:<10} {b['sharp_consensus']['sharp_alignment']:<20}")

        c = r['corners_market']
        print(f"  {'Over '+str(c['market_line'])+' Cor':<20} {c['over_prob']:>6.1%} {c['edge']:>+7.2f} {c['confidence']:>5.1f} {c['recommendation']:>6} {c['verdict']:<10} {c['sharp_consensus']['sharp_alignment']:<20}")


def print_final_recommendations(results: List[Dict]):
    """Print actionable betting recommendations"""
    print("\n" + "=" * 90)
    print("FINAL BETTING RECOMMENDATIONS")
    print("=" * 90)

    for r in results:
        print(f"\n{'-' * 80}")
        print(f"  {r['match']}")
        print(f"  {r['home_team']} vs {r['away_team']} | {r['league']}")
        print(f"  Liquidity: {r['liquidity']}")
        print(f"  Projected Score: {r['projection']['projected_score']}")
        print(f"{'-' * 80}")

        t = r['totals_market']
        b = r['btts_market']
        c = r['corners_market']

        # Each market
        markets = [
            ("TOTAL GOALS", t),
            ("BTTS", b),
            ("CORNERS", c),
        ]

        for label, market in markets:
            verdict = market['verdict']
            if verdict in ("STRONG", "VALUE"):
                emoji = "[STRONG]" if verdict == "STRONG" else "[VALUE]"
                action = "BET" if verdict == "STRONG" else "CONSIDER"
            elif verdict == "SLIGHT":
                emoji = "[SLIGHT]"
                action = "MONITOR"
            else:
                emoji = "[PASS]"
                action = "PASS"

            edge_str = f"{market['edge']:+.2f}"
            sharp = market['sharp_consensus']['sharp_alignment']

            # Handle different key names: totals uses 'over_prob', BTTS uses 'yes_prob', corners uses 'over_prob'
            prob_key = 'yes_prob' if label == 'BTTS' else 'over_prob'
            prob_val = market.get(prob_key, market.get('over_prob', 0.0))

            print(f"\n  {emoji} {label} | {action}")
            print(f"     Probability: {prob_val:.1%} | Edge: {edge_str} | Confidence: {market['confidence']:.1f}/100")
            print(f"     Recommendation: {market['recommendation']}")
            print(f"     Sharp Signal: {sharp}")
            if action == "BET":
                print(f"     *** STRONG BET - Good value detected")
            elif action == "CONSIDER":
                print(f"     --> Worth considering but monitor line movement")
            elif action == "MONITOR":
                print(f"     --> Potential value if line moves favorably")
            else:
                print(f"     --> No value at current line")

        # Side recommendation
        proj = r['projection']
        if max(proj['home_win_prob'], proj['away_win_prob']) >= 0.55:
            fav = r['home_team'] if proj['home_win_prob'] >= 0.55 else r['away_team']
            fav_prob = max(proj['home_win_prob'], proj['away_win_prob'])
            print(f"\n  [SIDE] {fav} to win ({fav_prob:.1%} probability)")
        elif proj['draw_prob'] >= 0.30:
            print(f"\n  [SIDE] Draw possible ({proj['draw_prob']:.1%})")

        print()


def main():
    """Run comprehensive analysis for both matches"""
    print("=" * 90)
    print("MULTISPORTPREDICT - COMPREHENSIVE SOCCER ANALYSIS")
    print("Two Match Analysis: July 2, 2026")
    print("=" * 90)

    results = []

    # -- MATCH 1: JK Welco Elekter vs Vimsi JK --
    print("\n\n")
    r1 = analyze_match(
        match_label="MATCH 1: Estonian Esiliiga",
        home_team="JK Welco Elekter",
        away_team="Vimsi JK",
        profiles=MATCH1_PROFILES,
        league_config=MATCH1_LEAGUE_CONFIG,
        market_total_goals=2.5,
        market_corners=9.5,
        date="2026-07-02",
    )
    results.append(r1)

    # -- MATCH 2: Lyn vs Asane --
    print("\n\n")
    r2 = analyze_match(
        match_label="MATCH 2: Norwegian OBOS-ligaen",
        home_team="Lyn",
        away_team="Asane",
        profiles=MATCH2_PROFILES,
        league_config=MATCH2_LEAGUE_CONFIG,
        market_total_goals=2.5,
        market_corners=10.5,
        date="2026-07-02",
    )
    results.append(r2)

    # -- SUMMARY --
    print_summary_table(results)
    print_final_recommendations(results)

    # Export to JSON
    output_path = Path("output/welco_lyn_analysis_2026_07_02.json")
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull analysis exported to: {output_path}")

    print("\n" + "=" * 90)
    print("ANALYSIS COMPLETE")
    print("=" * 90)

    return results


if __name__ == "__main__":
    main()