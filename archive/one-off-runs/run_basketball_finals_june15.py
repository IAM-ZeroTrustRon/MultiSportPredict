#!/usr/bin/env python
"""
Deep Dive Analysis — June 15 Basketball Finals Doubleheader

1) Polish PLK Finals (Game 4): Zastal Zielona Góra vs SK Legia Warszawa
   Series: Legia leads 2-1 (Best-of-5)
   Time: 2:15 PM EDT | Venue: CRS Hall, Zielona Góra

2) French LNB Pro B Finals (Game 2): Poitiers Basket 86 vs Élan Béarnais Pau-Lacq-Orthez
   Series: Poitiers leads 1-0
   Time: 2:30 PM EDT | Venue: Salle Saint-Éloi, Poitiers
"""

import sys
import json
import math
from datetime import datetime
from pathlib import Path

from models.basketball_predictor import (
    BasketballPredictor,
    FIBATeamMetrics,
    FIBAContext,
    fiba_build_full_game,
    fiba_build_q1,
    fiba_efficiency_gap,
    fiba_team_net_rating,
    fiba_rest_travel_score,
    fiba_team_context_score,
    fiba_score_to_prob,
    fiba_recommendation,
    fiba_market_filter,
)

from core.confidence_engine import confidence_score, bet_recommendation


def sigmoid(x: float) -> float:
    x = max(-500, min(500, x))
    return 1 / (1 + math.exp(-x))


def clamp(x: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, x))


def analyze_polish_plk_game4():
    """Zastal Zielona Góra vs SK Legia Warszawa — Game 4 of PLK Finals"""
    
    print("\n" + "=" * 80)
    print("POLISH PLK FINALS — GAME 4 (Best-of-5)")
    print("Zastal Zielona Góra vs SK Legia Warszawa")
    print("CRS Hall, Zielona Góra — 2:15 PM EDT")
    print(f"Series: Legia leads 2-1 (Game 1: Zastal 77-74, Game 2: Legia 104-82, Game 3: Legia 79-63)")
    print("=" * 80 + "\n")

    # ========================================================
    # SK Legia Warszawa (Away — road favorite)
    # ========================================================
    # After dropping Game 1, Legia has outscored Zastal by 38 over Games 2-3
    # Game 3: Held Zastal to 63 points in a defensive masterclass
    # Deep rotation: Tass and Ponsar bring elite frontcourt relief
    # Perimeter defense: Graves and Shungu have eliminated Zastal's P&R looks
    legia_metrics = FIBATeamMetrics(
        ortg_per_100=118.5,
        drtg_per_100=104.5,
        baseline_net_per_100=10.0,
        recent_net_per_100=15.0,  # Dominant last 2 games
        pace_per_40=74.0,
        rest_days=1,  # Back-to-back with Game 3
        travel_km=0,   # Same city as Game 3
        back_to_back=True,
        three_in_six=False,
        split_edge=-1.0,  # Road team in finals
        rotation_depth=10,  # Tass, Ponsar provide depth
        injury_status='green',
        coach_stability='green',
        motivation='green',  # Can close out series today
        three_pt_pct=0.38,
        orb_pct=0.28,
    )

    # ========================================================
    # Zastal Zielona Góra (Home — desperate)
    # ========================================================
    # Maximum desperation: down 2-1 in best-of-5 (elimination)
    # Home court advantage blunted by Game 3 struggle (63 pts)
    # Starting lineup looked gassed in 2nd half of Game 3
    # Garrison struggling against Legia's length
    # Zastal sold out to stop Graves, leaving Pluta open
    zastal_metrics = FIBATeamMetrics(
        ortg_per_100=108.0,
        drtg_per_100=112.0,
        baseline_net_per_100=2.0,
        recent_net_per_100=-4.0,  # Struggled badly in Game 3
        pace_per_40=71.0,
        rest_days=1,  # Back-to-back
        travel_km=0,
        back_to_back=True,
        three_in_six=False,
        split_edge=2.5,  # Strong home court — but crowd was quiet in G3
        rotation_depth=8,  # Bench looked thin in Game 3
        injury_status='yellow',  # Signs of fatigue
        coach_stability='green',
        motivation='red',  # Desperation — but can go either way
        three_pt_pct=0.35,
        orb_pct=0.30,
    )

    # Market context
    # Opened Legia -4.5 to -5.5, now -6 (sharp movement)
    # Under 158.5 — sharps backing slow, physical closeout game
    ctx = FIBAContext(
        game_id="Zastal_vs_Legia_G4",
        date="2026-06-15",
        league="Polish_PLK",
        home_team="Zastal Zielona Góra",
        away_team="SK Legia Warszawa",
        market_line=-6.0,     # Legia -6 (negative = road favorite)
        current_line=-6.0,    # Current line
        open_line=-5.0,       # Opened -5, sharp money pushed to -6
    )

    # ========================================================
    # FULL GAME PREDICTION
    # ========================================================
    print("1. FULL GAME PREDICTION")
    print("-" * 40)

    full_game = fiba_build_full_game(zastal_metrics, legia_metrics, ctx)
    
    print(f"   Efficiency Gaps:")
    print(f"      Current Gap: {full_game['current_gap']:+.2f}")
    print(f"      Baseline Gap: {full_game['baseline_gap']:+.2f}")
    print(f"      Recent Gap: {full_game['recent_gap']:+.2f}")
    print(f"      Historical Gap: {full_game['historical_gap']:+.2f}")
    print(f"   Rest Gap: {full_game['rest_gap']:+.2f}")
    print(f"   Context Gap: {full_game['context_gap']:+.2f}")
    print(f"   Model Edge: {full_game['model_edge']:+.2f}")
    print(f"   Market Score: {full_game['market_score']:+.2f}")
    print()
    print(f"   Projected Score: Zastal {full_game['projected_home_score']:.1f} - {full_game['projected_away_score']:.1f} Legia")
    print(f"   Projected Total: {full_game['projected_total']:.1f}")
    print(f"   Win Probability (Legia): {full_game['probability']:.1%}")
    print(f"   Lean: {full_game['lean']}")
    print()

    # ========================================================
    # SPREAD ANALYSIS (Legia -6 / Zastal +6)
    # ========================================================
    print("2. SPREAD & MONEYLINE ANALYSIS")
    print("-" * 40)

    projected_spread = full_game['projected_away_score'] - full_game['projected_home_score']
    market_spread = -6.0  # Legia -6
    spread_edge = projected_spread - market_spread
    spread_conf = confidence_score(spread_edge * 2, volatility=0.6)
    
    print(f"   Projected Spread: Legia {projected_spread:+.1f}")
    print(f"   Market Spread: Legia {market_spread:+.0f}")
    print(f"   Spread Edge: {spread_edge:+.2f} points")
    print(f"   Spread Confidence: {spread_conf:.1f}%")
    print(f"   Spread Recommendation: {'LEGIA -6' if spread_edge > 0 else 'ZASTAL +6'} ({bet_recommendation(spread_conf)})")
    print()

    # ========================================================
    # TOTAL ANALYSIS (O/U 158.5)
    # ========================================================
    print("3. TOTAL ANALYSIS (O/U 158.5)")
    print("-" * 40)

    projected_total = full_game['projected_total']
    market_total = 158.5
    total_edge = projected_total - market_total
    total_conf = confidence_score(total_edge / 158.5 * 100, volatility=0.55)

    # Game 1: 151, Game 2: 186, Game 3: 142
    # Sharps backing Under after seeing Legia's defense
    # Zastal scored 63 in G3 — but should regress toward mean at home
    print(f"   Projected Total: {projected_total:.1f}")
    print(f"   Market Total: {market_total}")
    print(f"   Edge: {total_edge:+.1f} points")
    print(f"   Series Totals: G1=151, G2=186, G3=142")
    print(f"   Total Confidence: {total_conf:.1f}%")
    print(f"   Total Recommendation: {'OVER' if total_edge > 0 else 'UNDER'} ({bet_recommendation(total_conf)})")
    print()

    # ========================================================
    # PLAYER PROP ANALYSIS
    # ========================================================
    print("4. PLAYER PROPS ANALYSIS")
    print("-" * 40)

    # Andrzej Pluta Jr. (Legia) OVER 13.5 Points
    # Zastal selling out to stop Graves' penetration → Pluta gets open looks
    pluta_proj = 17.5
    pluta_edge = pluta_proj - 13.5
    pluta_conf = confidence_score(pluta_edge * 5, volatility=0.5)
    print(f"   Andrzej Pluta Jr. (Legia) — Points: O/U 13.5")
    print(f"      Projection: {pluta_proj:.1f} | Edge: +{pluta_edge:.1f}")
    print(f"      Confidence: {pluta_conf:.1f}%")
    print(f"      Logic: Zastal blitzing P&R, leaving Pluta wide open on perimeter")
    print(f"      Recommendation: OVER 13.5 ({bet_recommendation(pluta_conf)})")
    print()

    # Conley Garrison (Zastal) UNDER 14.5 Points
    # Struggling against Legia's length (Graves, Shungu)
    # Expected to pick up early fouls or focus on distribution
    garrison_proj = 10.5
    garrison_edge = 14.5 - garrison_proj
    garrison_conf = confidence_score(garrison_edge * 5, volatility=0.5)
    print(f"   Conley Garrison (Zastal) — Points: O/U 14.5")
    print(f"      Projection: {garrison_proj:.1f} | Edge: +{garrison_edge:.1f}")
    print(f"      Confidence: {garrison_conf:.1f}%")
    print(f"      Logic: Struggling vs Legia's length; early fouls / distribution focus")
    print(f"      Recommendation: UNDER 14.5 ({bet_recommendation(garrison_conf)})")
    print()

    # ========================================================
    # GAME 4 SITUATIONAL ANALYSIS
    # ========================================================
    print("5. GAME 4 — SITUATIONAL HANDICAPPING")
    print("-" * 40)
    print(f"   Series Scenario: Legia leads 2-1 (Best-of-5)")
    print(f"   Legia Motivation: Championship closeout on road (extreme)")
    print(f"   Zastal Motivation: Elimination game (maximum desperation)")
    print(f"   Fatigue: Both on back-to-back, Zastal's starters looked gassed in G3")
    print(f"   Rotation Edge: Legia (10 deep) vs Zastal (8 deep) — critical in G4")
    print(f"   Defensive Trend: Legia held Zastal to 63 points (42.2% FG) in G3")
    print(f"   Market Movement: -4.5 -> -6 (sharp money on Legia)")
    print(f"   Under Movement: 158.5 sharp action (slow, physical closeout expected)")
    print()

    # ========================================================
    # FINAL RECOMMENDATIONS — POLISH PLK
    # ========================================================
    plk_results = {
        "match": "Zastal Zielona Góra vs SK Legia Warszawa",
        "league": "Polish PLK Finals — Game 4 (Best-of-5)",
        "date": "2026-06-15",
        "time": "2:15 PM EDT",
        "venue": "CRS Hall, Zielona Góra",
        "series_status": "Legia leads 2-1",
        "full_game_prediction": {
            "projected_home_score": full_game['projected_home_score'],
            "projected_away_score": full_game['projected_away_score'],
            "projected_total": full_game['projected_total'],
            "projected_spread": round(projected_spread, 1),
            "model_edge": full_game['model_edge'],
            "win_probability": round(full_game['probability'], 3),
            "lean": full_game['lean'],
        },
        "spread_analysis": {
            "market_line": "Legia -6",
            "projected_spread": round(projected_spread, 1),
            "edge": round(spread_edge, 2),
            "confidence": round(spread_conf, 1),
            "recommendation": f"LEGIA -6" if spread_edge > 0 else f"ZASTAL +6",
        },
        "total_analysis": {
            "market_total": market_total,
            "projected_total": round(projected_total, 1),
            "edge": round(total_edge, 1),
            "confidence": round(total_conf, 1),
            "recommendation": "OVER" if total_edge > 0 else "UNDER",
        },
        "player_props": {
            "andrzej_pluta_jr_pts": {
                "line": 13.5,
                "projection": pluta_proj,
                "edge": round(pluta_edge, 1),
                "confidence": round(pluta_conf, 1),
                "recommendation": "OVER 13.5",
            },
            "conley_garrison_pts": {
                "line": 14.5,
                "projection": garrison_proj,
                "edge": round(garrison_edge, 1),
                "confidence": round(garrison_conf, 1),
                "recommendation": "UNDER 14.5",
            },
        },
        "recommendations": {
            "spread": f"LEGIA -6 (Conf: {round(spread_conf, 1)}%)",
            "total": f"{'OVER' if total_edge > 0 else 'UNDER'} {market_total} (Conf: {round(total_conf, 1)}%)",
            "top_prop": f"Andrzej Pluta Jr. OVER 13.5 PTS (Conf: {round(pluta_conf, 1)}%)",
        },
    }
    
    print()
    print("   === POLISH PLK RECOMMENDATIONS ===")
    print(f"   Spread: {plk_results['recommendations']['spread']}")
    print(f"   Total: {plk_results['recommendations']['total']}")
    print(f"   Top Prop: {plk_results['recommendations']['top_prop']}")
    print()
    print("=" * 80)

    return plk_results


def analyze_french_lnb_pro_b_game2():
    """Poitiers Basket 86 vs Élan Béarnais Pau-Lacq-Orthez — Game 2 of Finals"""
    
    print("\n" + "=" * 80)
    print("FRENCH LNB PRO B FINALS — GAME 2 (Best-of-3)")
    print("Poitiers Basket 86 vs Élan Béarnais Pau-Lacq-Orthez")
    print("Salle Saint-Éloi, Poitiers — 2:30 PM EDT")
    print(f"Series: Poitiers leads 1-0 (Game 1: Poitiers 106-82 at Pau)")
    print("=" * 80 + "\n")

    # ========================================================
    # Poitiers Basket 86 (Home — up 1-0)
    # ========================================================
    # Game 1: Blowout 106-82 win AT Pau (traveled and dominated)
    # Shooting ungodly percentage from mid-range
    # Dominated transition track
    # Starters rested entire 4th quarter
    # 7'1" Ngoy completely altered paint when he checked in
    poitiers_metrics = FIBATeamMetrics(
        ortg_per_100=120.0,
        drtg_per_100=105.0,
        baseline_net_per_100=8.0,
        recent_net_per_100=18.0,  # Just won by 24 on road
        pace_per_40=76.0,  # Fast-paced transition team
        rest_days=2,  # Normal rest between games
        travel_km=0,    # At home (no travel from Game 1 blowout)
        back_to_back=False,
        three_in_six=False,
        split_edge=3.0,  # Strong home court
        rotation_depth=10,  # Ngoy adds size off bench
        injury_status='green',
        coach_stability='green',
        motivation='green',  # Can go up 2-0 at home
        three_pt_pct=0.38,
        orb_pct=0.32,  # Ngoy + Idowu = rebounding edge
    )

    # ========================================================
    # Élan Béarnais Pau-Lacq-Orthez (Away — must-win)
    # ========================================================
    # Game 1: Embarrassed 82-106 on home floor
    # Must respond — aggressive first quarter expected
    # Travel: 4-hour bus ride after devastating loss
    # Nze maxed out minutes expected
    # Pau lacks structural height to contest Idowu/Ngoy
    pau_metrics = FIBATeamMetrics(
        ortg_per_100=109.0,
        drtg_per_100=113.0,
        baseline_net_per_100=1.0,
        recent_net_per_100=-3.0,  # Just got blown out
        pace_per_40=73.0,
        rest_days=2,
        travel_km=350,  # 4-hour bus ride after Game 1
        back_to_back=False,
        three_in_six=False,
        split_edge=-2.0,  # Poor road form
        rotation_depth=9,
        injury_status='yellow',  # Morale damage from Game 1 blowout
        coach_stability='yellow',
        motivation='red',  # Pride + survival — can go either way
        three_pt_pct=0.34,
        orb_pct=0.26,  # No answer for Poitiers' size
    )

    # Market context
    # Poitiers opened -6.5, held firm
    # Sharps targeting First Quarter Over 41.5
    ctx = FIBAContext(
        game_id="Poitiers_vs_Pau_G2",
        date="2026-06-15",
        league="French_LNB_Pro_B",
        home_team="Poitiers Basket 86",
        away_team="Élan Béarnais Pau-Lacq-Orthez",
        market_line=-6.5,      # Poitiers -6.5
        current_line=-6.5,     # Held firm
        open_line=-6.5,        # Opened same
    )

    # ========================================================
    # FULL GAME PREDICTION
    # ========================================================
    print("1. FULL GAME PREDICTION")
    print("-" * 40)

    full_game = fiba_build_full_game(poitiers_metrics, pau_metrics, ctx)
    
    print(f"   Efficiency Gaps:")
    print(f"      Current Gap: {full_game['current_gap']:+.2f}")
    print(f"      Baseline Gap: {full_game['baseline_gap']:+.2f}")
    print(f"      Recent Gap: {full_game['recent_gap']:+.2f}")
    print(f"      Historical Gap: {full_game['historical_gap']:+.2f}")
    print(f"   Rest Gap: {full_game['rest_gap']:+.2f}")
    print(f"   Context Gap: {full_game['context_gap']:+.2f}")
    print(f"   Model Edge: {full_game['model_edge']:+.2f}")
    print(f"   Market Score: {full_game['market_score']:+.2f}")
    print()
    print(f"   Projected Score: Poitiers {full_game['projected_home_score']:.1f} - {full_game['projected_away_score']:.1f} Pau")
    print(f"   Projected Total: {full_game['projected_total']:.1f}")
    print(f"   Win Probability (Poitiers): {full_game['probability']:.1%}")
    print(f"   Lean: {full_game['lean']}")
    print()

    # ========================================================
    # SPREAD ANALYSIS (Poitiers -6.5)
    # ========================================================
    print("2. SPREAD & MONEYLINE ANALYSIS")
    print("-" * 40)

    projected_spread = full_game['projected_home_score'] - full_game['projected_away_score']
    market_spread = -6.5  # Poitiers -6.5
    spread_edge = projected_spread - abs(market_spread)
    spread_conf = confidence_score(spread_edge * 2, volatility=0.6)

    print(f"   Projected Spread: Poitiers {projected_spread:+.1f}")
    print(f"   Market Spread: Poitiers {abs(market_spread):.0f}")
    print(f"   Spread Edge: {spread_edge:+.2f} points")
    print(f"   Spread Confidence: {spread_conf:.1f}%")
    print(f"   Spread Recommendation: {'POITIERS -6.5' if spread_edge > 0 else 'PAU +6.5'} ({bet_recommendation(spread_conf)})")
    print()

    # ========================================================
    # TOTAL ANALYSIS (O/U ~170)
    # ========================================================
    print("3. TOTAL ANALYSIS")
    print("-" * 40)

    projected_total = full_game['projected_total']
    market_total = 170.5
    total_edge = projected_total - market_total
    total_conf = confidence_score(total_edge / 170.5 * 100, volatility=0.55)

    print(f"   Projected Total: {projected_total:.1f}")
    print(f"   Market Total: {market_total}")
    print(f"   Edge: {total_edge:+.1f} points")
    print(f"   Total Confidence: {total_conf:.1f}%")
    print(f"   Total Recommendation: {'OVER' if total_edge > 0 else 'UNDER'} ({bet_recommendation(total_conf)})")
    print()

    # ========================================================
    # FIRST QUARTER ANALYSIS
    # ========================================================
    print("4. FIRST QUARTER ANALYSIS")
    print("-" * 40)

    # Pau expected to play with extreme urgency early
    # Sharps targeting Q1 OVER 41.5
    # Poitiers in rhythm from Game 1 blowout
    # Pau needs fast start to avoid getting buried
    q1_projected_total = 44.5  # Expected high-paced Q1
    q1_market_total = 41.5
    q1_edge = q1_projected_total - q1_market_total
    q1_conf = confidence_score(q1_edge / 41.5 * 100, volatility=0.5)

    print(f"   Projected Q1 Total: {q1_projected_total:.1f}")
    print(f"   Market Q1 Total: {q1_market_total}")
    print(f"   Edge: {q1_edge:+.1f} points")
    print(f"   Q1 Confidence: {q1_conf:.1f}%")
    print(f"   Logic: Pau plays desperate, Poitiers in rhythm, both want fast start")
    print(f"   Q1 Recommendation: OVER {q1_market_total} ({bet_recommendation(q1_conf)})")
    print()

    # ========================================================
    # PLAYER PROP ANALYSIS
    # ========================================================
    print("5. PLAYER PROPS ANALYSIS")
    print("-" * 40)

    # Marcus Hammond (Poitiers) OVER 16.5 Points
    # Unguardable in P&R in Game 1
    # Back at home, will hunt his shot
    hammond_proj = 21.5
    hammond_edge = hammond_proj - 16.5
    hammond_conf = confidence_score(hammond_edge * 5, volatility=0.5)
    print(f"   Marcus Hammond (Poitiers) — Points: O/U 16.5")
    print(f"      Projection: {hammond_proj:.1f} | Edge: +{hammond_edge:.1f}")
    print(f"      Confidence: {hammond_conf:.1f}%")
    print(f"      Logic: Unguardable in P&R in G1; back at home hunting shots")
    print(f"      Recommendation: OVER 16.5 ({bet_recommendation(hammond_conf)})")
    print()

    # Bryce Nze (Pau-Orthez) OVER 8.5 Rebounds
    # Maxed-out minutes with back against the wall
    # Must clear defensive glass to prevent Poitiers 2nd chances
    nze_proj = 11.5
    nze_edge = nze_proj - 8.5
    nze_conf = confidence_score(nze_edge * 5, volatility=0.5)
    print(f"   Bryce Nze (Pau-Orthez) — Rebounds: O/U 8.5")
    print(f"      Projection: {nze_proj:.1f} | Edge: +{nze_edge:.1f}")
    print(f"      Confidence: {nze_conf:.1f}%")
    print(f"      Logic: Max minutes, must dominate glass for Pau to have a chance")
    print(f"      Recommendation: OVER 8.5 ({bet_recommendation(nze_conf)})")
    print()

    # ========================================================
    # GAME 2 SITUATIONAL ANALYSIS
    # ========================================================
    print("6. GAME 2 — SITUATIONAL HANDICAPPING")
    print("-" * 40)
    print(f"   Series Scenario: Poitiers leads 1-0 (Best-of-3)")
    print(f"   Poitiers: Can take commanding 2-0 lead at home")
    print(f"   Pau: Must win or face elimination (pride + survival)")
    print(f"   Travel Edge: Poitiers rested at home; Pau 4-hour bus ride after G1 blowout")
    print(f"   Rest Edge: Poitiers starters sat entire 4th Q of Game 1 (blowout)")
    print(f"   Size Edge: Poitiers' 7'1\" Ngoy + Idowu vs Pau's lack of structural height")
    print(f"   Market: Poitiers -6.5 held firm - no public overreaction to G1")
    print(f"   Q1 Target: Sharps on OVER 41.5 (Pau desperate, Poitiers in rhythm)")
    print()

    # ========================================================
    # FINAL RECOMMENDATIONS — FRENCH LNB PRO B
    # ========================================================
    lnb_results = {
        "match": "Poitiers Basket 86 vs Élan Béarnais Pau-Lacq-Orthez",
        "league": "French LNB Pro B Finals — Game 2 (Best-of-3)",
        "date": "2026-06-15",
        "time": "2:30 PM EDT",
        "venue": "Salle Saint-Éloi, Poitiers",
        "series_status": "Poitiers leads 1-0",
        "full_game_prediction": {
            "projected_home_score": full_game['projected_home_score'],
            "projected_away_score": full_game['projected_away_score'],
            "projected_total": full_game['projected_total'],
            "projected_spread": round(projected_spread, 1),
            "model_edge": full_game['model_edge'],
            "win_probability": round(full_game['probability'], 3),
            "lean": full_game['lean'],
        },
        "spread_analysis": {
            "market_line": "Poitiers -6.5",
            "projected_spread": round(projected_spread, 1),
            "edge": round(spread_edge, 2),
            "confidence": round(spread_conf, 1),
            "recommendation": f"POITIERS -6.5" if spread_edge > 0 else f"PAU +6.5",
        },
        "total_analysis": {
            "market_total": market_total,
            "projected_total": round(projected_total, 1),
            "edge": round(total_edge, 1),
            "confidence": round(total_conf, 1),
            "recommendation": "OVER" if total_edge > 0 else "UNDER",
        },
        "first_quarter_analysis": {
            "market_total": q1_market_total,
            "projected_total": q1_projected_total,
            "edge": round(q1_edge, 1),
            "confidence": round(q1_conf, 1),
            "recommendation": f"OVER {q1_market_total}",
            "logic": "Pau desperate fast start + Poitiers in rhythm",
        },
        "player_props": {
            "marcus_hammond_pts": {
                "line": 16.5,
                "projection": hammond_proj,
                "edge": round(hammond_edge, 1),
                "confidence": round(hammond_conf, 1),
                "recommendation": "OVER 16.5",
            },
            "bryce_nze_reb": {
                "line": 8.5,
                "projection": nze_proj,
                "edge": round(nze_edge, 1),
                "confidence": round(nze_conf, 1),
                "recommendation": "OVER 8.5",
            },
        },
        "recommendations": {
            "spread": f"POITIERS -6.5 (Conf: {round(spread_conf, 1)}%)",
            "total": f"{'OVER' if total_edge > 0 else 'UNDER'} {market_total} (Conf: {round(total_conf, 1)}%)",
            "first_quarter": f"OVER {q1_market_total} (Conf: {round(q1_conf, 1)}%)",
            "top_prop": f"Marcus Hammond OVER 16.5 PTS (Conf: {round(hammond_conf, 1)}%)",
        },
    }

    print()
    print("   === LNB PRO B RECOMMENDATIONS ===")
    print(f"   Spread: {lnb_results['recommendations']['spread']}")
    print(f"   Total: {lnb_results['recommendations']['total']}")
    print(f"   First Quarter: {lnb_results['recommendations']['first_quarter']}")
    print(f"   Top Prop: {lnb_results['recommendations']['top_prop']}")
    print()
    print("=" * 80)

    return lnb_results


def main():
    """Run basketball finals doubleheader analysis"""
    
    print("=" * 80)
    print("BASKETBALL FINALS DOUBLEHEADER — JUNE 15, 2026")
    print("=" * 80)
    
    # --- POLISH PLK FINALS GAME 4 ---
    plk = analyze_polish_plk_game4()
    
    # --- FRENCH LNB PRO B FINALS GAME 2 ---
    lnb = analyze_french_lnb_pro_b_game2()
    
    # Save combined results
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    combined_results = {
        "timestamp": datetime.now().isoformat(),
        "polish_plk_game4": plk,
        "french_lnb_pro_b_game2": lnb,
    }
    
    output_path = output_dir / "basketball_finals_june15_analysis.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(combined_results, f, indent=2, ensure_ascii=False)
    
    # Print master summary
    print("\n" + "=" * 80)
    print("MASTER RECOMMENDATIONS SUMMARY")
    print("=" * 80)
    
    print("\n--- POLISH PLK FINALS (Game 4) ---")
    print(f"  Match: Zastal Zielona Gora vs SK Legia Warszawa")
    print(f"  Series: Legia leads 2-1 | Time: 2:15 PM EDT")
    print(f"  Projected: Zastal {plk['full_game_prediction']['projected_home_score']:.1f} - {plk['full_game_prediction']['projected_away_score']:.1f} Legia")
    print(f"  Legia Win Prob: {plk['full_game_prediction']['win_probability']:.1%}")
    print(f"  Spread: {plk['recommendations']['spread']}")
    print(f"  Total: {plk['recommendations']['total']}")
    print(f"  Pluta Jr. OVER 13.5 PTS: Conf {plk['player_props']['andrzej_pluta_jr_pts']['confidence']:.1f}%")
    print(f"  Garrison UNDER 14.5 PTS: Conf {plk['player_props']['conley_garrison_pts']['confidence']:.1f}%")
    
    print("\n--- FRENCH LNB PRO B FINALS (Game 2) ---")
    print(f"  Match: Poitiers Basket 86 vs Pau-Lacq-Orthez")
    print(f"  Series: Poitiers leads 1-0 | Time: 2:30 PM EDT")
    print(f"  Projected: Poitiers {lnb['full_game_prediction']['projected_home_score']:.1f} - {lnb['full_game_prediction']['projected_away_score']:.1f} Pau")
    print(f"  Poitiers Win Prob: {lnb['full_game_prediction']['win_probability']:.1%}")
    print(f"  Spread: {lnb['recommendations']['spread']}")
    print(f"  Total: {lnb['recommendations']['total']}")
    print(f"  First Quarter: {lnb['recommendations']['first_quarter']}")
    print(f"  Hammond OVER 16.5 PTS: Conf {lnb['player_props']['marcus_hammond_pts']['confidence']:.1f}%")
    print(f"  Nze OVER 8.5 REB: Conf {lnb['player_props']['bryce_nze_reb']['confidence']:.1f}%")
    
    print(f"\nResults saved to: {output_path}")
    print()


if __name__ == "__main__":
    main()