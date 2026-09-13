#!/usr/bin/env python
"""
BBL Finals Game 2: FC Bayern Munich vs ALBA Berlin
Sunday, June 14, 2026 - SAP Garden
Bayern leads 1-0 (102-94 Game 1)
"""
import sys
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from MultiSportModel import eu_build_full_game, project_basketball_q1, eu_score_to_prob, GameContext, TeamMetrics
from core.confidence_engine import confidence_score, bet_recommendation

def clamp(x, low=0.0, high=1.0):
    return max(low, min(high, x))

GAME1_ANALYTICS = {
    "regression_factor": 0.88,
    "bayern_fg_regression": 0.460,
    "obst_regression_pts": 18.5,
    "pace_slowdown": 0.92,
    "sharp_market_total": 172.5,
    "under_confidence": 65.0,
}

def run_analysis():
    generation_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    print("=" * 80)
    print("EASYCREDIT BBL FINALS - GAME 2 ANALYSIS")
    print("FC Bayern Munich vs ALBA Berlin")
    print("Sunday, June 14, 2026 - SAP Garden")
    print("Series: Bayern leads 1-0 (102-94 Game 1)")
    print(f"Timestamp: {generation_time}")
    print("=" * 80)
    print()

    # ── 1. GAME 1 RECAP ──
    print("1. GAME 1 DATA & ADVANCED METRICS")
    print("-" * 60)
    print("    Game 1: Bayern 102 - ALBA 94 (Total: 196)")
    print("    Bayern FG%: ~60% (Outlier - textbook negative regression spot)")
    print("    Andi Obst: 33 pts (10/11 FG in 1st half - historic)")
    print("    ALBA Interior: Agbakoko 21 pts (controlled early)")
    print("    Key: Bayern shot ~60% = unsustainable. Regression incoming.")
    print()

    # ── 2. TEAM DATA ──
    ortg_bayern = 109.5 * GAME1_ANALYTICS["regression_factor"]
    ortg_bayern = max(103, ortg_bayern)
    drtg_bayern = 107.8
    ortg_alba = 110.2
    drtg_alba = 109.5
    game2_pace = 98.0 * GAME1_ANALYTICS["pace_slowdown"]

    print("2. TEAM EFFICIENCY ANALYSIS (Regression-Adjusted)")
    print("-" * 60)
    print(f"    Bayern Munich (Home):")
    print(f"      ORTG: {ortg_bayern:.1f} (REGRESSED from Game 1 ~60% shooting)")
    print(f"      DRTG: {drtg_bayern:.1f} | Net: {ortg_bayern - drtg_bayern:+.1f}")
    print(f"      Series: up 1-0 | Game 1: 102 pts")
    print(f"    ALBA Berlin (Away):")
    print(f"      ORTG: {ortg_alba:.1f} | DRTG: {drtg_alba:.1f} | Net: {ortg_alba - drtg_alba:+.1f}")
    print(f"      Game 1: 94 pts | Interior edge: Agbakoko 21 pts")
    print(f"      Game 2 Strategy: Slow pace, force half-court battle")
    print()

    # ── 3. PACE ANALYSIS ──
    print("3. PACE ANALYSIS (Game 2 Adjustment)")
    print("-" * 60)
    print(f"    Game 1 Pace: ~102 (elevated, 196 total points)")
    print(f"    Game 2 Projected Pace: {game2_pace:.1f} (ALBA slowing it down)")
    print(f"    ALBA must drag game into mud to neutralize Bayern shooters")
    print()

    # ── 4. MODEL RUN (European Basketball Template) ──
    print("4. FULL GAME PROJECTION (European Template)")
    print("-" * 60)

    ctx = GameContext(
        game_id="FC_Bayern_Munich_vs_ALBA_Berlin_Game2",
        date="2026-06-14",
        league="BBL (Germany) - Finals Game 2",
        record_type="full_game",
        home_team="FC Bayern Munich",
        away_team="ALBA Berlin",
        market_line=-4.5,
        current_line=-4.5,
        open_line=-3.5,
    )

    home_tm = TeamMetrics(
        ortg=ortg_bayern, drtg=drtg_bayern, baseline_net=1.7, recent_net=4.0,
        pace=game2_pace, rest_days=2, travel_km=0, back_to_back=False, three_in_six=False,
        split_edge=1.0, rotation_depth=10, injury_status="green",
        coach_stability="green", motivation="green", open_line=-3.5, current_line=-4.5,
    )

    away_tm = TeamMetrics(
        ortg=ortg_alba, drtg=drtg_alba, baseline_net=0.7, recent_net=0.5,
        pace=game2_pace, rest_days=2, travel_km=560, back_to_back=False, three_in_six=False,
        split_edge=2.0, rotation_depth=9, injury_status="green",
        coach_stability="green", motivation="green", open_line=3.5, current_line=4.5,
    )

    full_game = eu_build_full_game(home_tm, away_tm, ctx)

    print(f"    Model Edge: {full_game['model_edge']:+.2f}")
    print(f"    Win Probability: {full_game['probability']:.3f}")
    print(f"    Projected: Bayern {full_game['projected_home_score']:.1f} - ALBA {full_game['projected_away_score']:.1f}")
    print(f"    Projected Total: {full_game['projected_total']:.1f}")
    print(f"    Recommendation: {full_game['lean']}")
    print()

    # ── 5. Q1 PROJECTION ──
    print("5. FIRST QUARTER (1Q) PROJECTION")
    print("-" * 60)
    q1 = project_basketball_q1(
        {"ortg": ortg_bayern, "drtg": drtg_bayern, "pace": game2_pace,
         "rotation_depth": 10, "injury_status": "green", "coach_stability": "green", "motivation": "green"},
        {"ortg": ortg_alba, "drtg": drtg_alba, "pace": game2_pace,
         "rotation_depth": 9, "injury_status": "green", "coach_stability": "green", "motivation": "green"},
    )
    print(f"    1Q: Bayern {q1['home_q1_points']:.1f} - ALBA {q1['away_q1_points']:.1f}")
    print(f"    1Q Spread: {q1['q1_spread']:+.1f} | 1Q Total: {q1['q1_total']:.1f}")
    print()

    # ── 6. TOTALS ANALYSIS ──
    print("6. TOTALS ANALYSIS (Sharp Consensus - UNDER)")
    print("-" * 60)
    model_total = full_game['projected_total']
    market_total = GAME1_ANALYTICS['sharp_market_total']
    total_edge = model_total - market_total
    total_conf = confidence_score(total_edge, volatility=0.55)
    total_rec = bet_recommendation(total_conf, "euro_totals")

    print(f"    Game 1 Total: 196 pts (inflated)")
    print(f"    Market Total: {market_total}")
    print(f"    Model Total: {model_total:.1f}")
    print(f"    Edge: {total_edge:+.1f}")
    print(f"    Confidence: {total_conf:.1f}% | Recommendation: {total_rec}")
    print()

    # ── 7. WIN PROBABILITY ──
    print("7. WIN PROBABILITY")
    print("-" * 60)
    ml_prob = clamp(0.49)
    ml_prob_model = full_game['probability']
    side_edge = abs(ml_prob_model - 0.5) * 100
    side_conf = confidence_score(side_edge, volatility=0.55)
    side_rec = bet_recommendation(side_conf, "euro_sides")

    print(f"    Bayern Win: {ml_prob_model:.1%}")
    print(f"    ALBA Win: {1 - ml_prob_model:.1%}")
    print(f"    Side Edge: {side_edge:.1f} | Confidence: {side_conf:.1f}%")
    print(f"    Recommendation: {side_rec}")
    print()

    # ── 8. SHARP CONSENSUS ──
    print("8. SHARP CONSENSUS & REGRESSION ANALYSIS")
    print("-" * 60)
    print("    MARKET LEAN: Under (Total Points)")
    print("    Strategy: Fade Game 1 hype. Public will smash Over after 196pt game.")
    print("    Regression: Bayern shooting from 60% -> ~46% (massive)")
    print("    Andi Obst: 33pts Game 1 -> ~18.5pts projection (historic outlier)")
    print("    ALBA Paint Edge: Agbakoko 21pts interior. Will force half-court battle.")
    print("    ALBA Plan: Slow tempo, guard perimeter, physical game.")
    print("    Sharp View: Market inflated. Under is the sharp play.")
    print()

    # ── 9. PLAYER PROPS ──
    print("9. KEY PLAYER PROPS")
    print("-" * 60)
    print("    LEAN: Andi Obst Under 18.5 pts (regression from 33 pts)")
    print("    LEAN: Agbakoko Over 14.5 pts (paint edge + Game 1 dominance)")
    print("    LEAN: Under 172.5 total points")
    print()

    # ── 10. FINAL RECOMMENDATIONS ──
    print("=" * 80)
    print("FINAL RECOMMENDATIONS")
    print("=" * 80)
    print(f"    Match: FC Bayern Munich vs ALBA Berlin (BBL Finals G2)")
    print(f"    Projected: Bayern {full_game['projected_home_score']:.1f} - ALBA {full_game['projected_away_score']:.1f}")
    print(f"    Total: {full_game['projected_total']:.1f}")
    print()
    print(f"    UNDER {market_total} (Model: {model_total:.1f}, Conf: {total_conf:.1f}%)")
    print(f"    SIDE: {'Bayern' if ml_prob_model > 0.5 else 'ALBA'} ({ml_prob_model:.1%}/{1-ml_prob_model:.1%}) Conf: {side_conf:.1f}%")
    print(f"    1Q Total: {q1['q1_total']:.1f}")
    print()
    print("=" * 80)

    # Build result
    result = {
        "sport": "basketball",
        "league": "BBL (Germany) - BBL Finals Game 2",
        "matchup": "FC Bayern Munich vs ALBA Berlin",
        "date": "2026-06-14",
        "venue": "SAP Garden",
        "series_context": "Bayern leads 1-0 (102-94 Game 1)",
        "generated_at": generation_time,
        "game1_data": {
            "result": "Bayern 102 - ALBA 94",
            "bayern_fg_pct": "~60%",
            "andi_obst_pts": 33,
            "agbakoko_pts": 21,
            "total_points": 196,
        },
        "projections": {
            "home_score": round(full_game['projected_home_score'], 1),
            "away_score": round(full_game['projected_away_score'], 1),
            "total": round(full_game['projected_total'], 1),
        },
        "regression_analysis": {
            "bayern_ortg_regessed": round(ortg_bayern, 1),
            "pace_projected": round(game2_pace, 1),
            "obst_projected_pts": GAME1_ANALYTICS["obst_regression_pts"],
        },
        "totals": {
            "market_total": market_total,
            "model_total": round(model_total, 1),
            "edge": round(total_edge, 1),
            "confidence": round(total_conf, 1),
            "recommendation": total_rec,
            "lean": "Under",
        },
        "side": {
            "home_prob": round(ml_prob_model, 4),
            "away_prob": round(1 - ml_prob_model, 4),
            "confidence": round(side_conf, 1),
            "recommendation": side_rec,
        },
        "q1": {
            "home_q1": round(q1['home_q1_points'], 1),
            "away_q1": round(q1['away_q1_points'], 1),
            "q1_spread": round(q1['q1_spread'], 1),
            "q1_total": round(q1['q1_total'], 1),
        },
        "sharp_consensus": {
            "lean": "Under",
            "strategy": "Fade Game 1 hype, anticipate ALBA tempo slowdown",
            "regression_factor": GAME1_ANALYTICS["regression_factor"],
            "obst_regression": True,
            "alba_paint_edge": True,
        },
        "recommendations": {
            "total": f"Under {market_total}",
            "side": f"{'Bayern' if ml_prob_model > 0.5 else 'ALBA'} ML",
            "prop_obst_under": "Under 18.5 pts",
            "prop_agbakoko_over": "Over 14.5 pts",
        },
    }

    # Save to file
    out_dir = Path("output/basketball")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "bayern_munich_vs_alba_berlin_game2_analysis.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nResults saved to: {out_path}")

    return result


if __name__ == "__main__":
    run_analysis()