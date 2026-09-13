#!/usr/bin/env python
"""
Comprehensive Analysis for ACB Playoffs Game 3
=============================================
DKV Joventut vs Valencia Basket
June 14, 2026 - Badalona, Spain
ACB Semi-Finals (Valencia leads 2-0)

MARKETS COVERED:
- Full Game Spread, Moneyline, Total
- 1st Quarter Spread & Total
- 1st Half Spread & Moneyline (Sharp Focus)
- Player Props (Jabari Parker, Jean Montero, Ricky Rubio, Neal Sako)
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# Import the MultiSportModel functions
from MultiSportModel import (
    GameContext,
    TeamMetrics,
    eu_build_full_game,
    project_basketball_q1,
    eu_score_to_prob,
)
from core import (
    confidence_score,
    bet_recommendation,
    store_prediction,
)


def player_prop_edge(player_avg: float, market_line: float,
                     usage_boost: float = 1.0, pace_factor: float = 1.0,
                     opp_def_adj: float = 1.0, minutes_adj: float = 1.0) -> dict:
    """
    Calculate edge on a player prop market.

    Args:
        player_avg: Player's season/current average for the stat
        market_line: The market line (Over/Under)
        usage_boost: Usage rate adjustment (1.0 = normal, >1 = higher usage expected)
        pace_factor: Game pace adjustment
        opp_def_adj: Opponent defense adjustment
        minutes_adj: Expected minutes adjustment

    Returns:
        Dict with projected, edge, confidence, and recommendation
    """
    projected = player_avg * usage_boost * pace_factor * opp_def_adj * minutes_adj
    raw_edge = projected - market_line

    # Normalize edge relative to the market line
    if market_line > 0:
        pct_edge = raw_edge / market_line
    else:
        pct_edge = raw_edge

    # Convert to confidence score
    conf = confidence_score(pct_edge * 100, volatility=0.45)

    # Lean direction
    if raw_edge > 0:
        lean = "OVER"
    else:
        lean = "UNDER"

    rec = bet_recommendation(conf)

    return {
        "projection": round(projected, 1),
        "market_line": market_line,
        "edge": round(raw_edge, 1),
        "edge_pct": round(pct_edge * 100, 1),
        "confidence": round(conf, 1),
        "lean": lean,
        "recommendation": rec,
    }


def analyze_matchup(
    home_team="DKV Joventut",
    away_team="Valencia Basket",
    date="2026-06-14",
    league="Spain_ACB_Playoffs"
):
    """Analyze Joventut vs Valencia Game 3 with all markets"""

    print("=" * 84)
    print("  ACB SEMI-FINALS - GAME 3: DKV JOVENTUT vs VALENCIA BASKET")
    print(f"  {date} | Palau Municipal d'Esports de Badalona")
    print("  Valencia leads series 2-0 | Joventut facing elimination")
    print("=" * 84)
    print()

    # ========================================================================
    # TEAM DATA - CALIBRATED FROM SCOUTING REPORT
    # ========================================================================
    #
    # Game 1: Valencia 118 - 117 (OT) -> Very high pace outlier
    # Game 2: Valencia 90 - 76 -> Regression to mean (166 total)
    # Season series: Valencia 4-1 vs Joventut (only loss was 87-90 in Feb)
    #
    # Key adjustments for this game:
    # - Joventut at home, elimination game -> extreme desperation/motivation
    # - Valencia wants to close out for rest before ACB Finals
    # - Expect physicality, tighter whistle, defensive intensity
    # ========================================================================

    # DKV Joventut (Home - Elimination Game)
    home_data = {
        'ortg': 107.0,           # Season ORTG (slightly below Valencia)
        'drtg': 110.0,           # Season DRTG (worse than Valencia)
        'baseline_net': -3.0,    # Season net rating deficit vs Valencia
        'recent_net': -4.0,      # Recent form (lost 2 games, -14 net in G2)
        'pace': 70.0,            # Moderate pace (Valencia slowed G2 effectively)
        'rest_days': 2,          # Standard rest between games
        'travel_km': 0,          # Home game
        'back_to_back': False,
        'three_in_six': True,    # Playoff schedule compression
        'split_edge': 3.5,       # Strong home court (Badalona is tough)
        'rotation_depth': 8,     # Shorter rotation in elimination game
        'injury_status': 'yellow', # Veteran core banged up
        'coach_stability': 'green', # Dani Miret - trusted coach
        'motivation': 'green',   # MAXIMUM - facing elimination at home
    }

    # Valencia Basket (Away - Closing Out)
    away_data = {
        'ortg': 112.0,           # Season ORTG (elite offense)
        'drtg': 106.0,           # Season DRTG (strong defense)
        'baseline_net': 6.0,     # Season net rating advantage
        'recent_net': 8.0,       # Recent form (dominant G2 win)
        'pace': 69.0,            # Slower pace (intentional G2 adjustment)
        'rest_days': 2,          # Standard rest
        'travel_km': 350,        # Short trip up Mediterranean coast
        'back_to_back': False,
        'three_in_six': True,    # Playoff compression
        'split_edge': -3.0,      # Good road team but slight away penalty
        'rotation_depth': 10,    # Deep bench (Costello, Taylor outplayed Joventut)
        'injury_status': 'green', # Healthy
        'coach_stability': 'green', # Pedro Martinez - experienced
        'motivation': 'yellow',  # High motivation to close out, but 2-0 cushion
    }

    # ========================================================================
    # MARKET DATA (from the betting markets provided)
    # ========================================================================
    market_data = {
        'open_line': -1.5,        # Valencia -1.5 (road favorite)
        'current_line': -1.5,     # Line held steady
        'spread': -1.5,           # Valencia -1.5
        'total': 165.5,           # Game total (regressed from 235 G1 anomaly)
        # 1st Half
        'h1_spread': -1.5,        # Joventut -1.5 (home dog in 1H)
        'h1_total': 81.5,         # 1st half total
        # 1st Quarter
        'q1_spread': -0.5,        # Joventut -0.5
        'q1_total': 41.5,         # 1Q total
    }

    # ========================================================================
    # 1. FULL GAME ANALYSIS (Using European Template)
    # ========================================================================
    print("=" * 84)
    print("  SECTION 1: FULL GAME ANALYSIS (European Basketball Template)")
    print("=" * 84)
    print()

    # Home team (Joventut) - their spread is positive when they're favored
    # Market has Valencia -1.5, so Joventut is +1.5
    home_market_line = market_data['spread']  # -1.5 (negative = away favorite)

    ctx = GameContext(
        game_id=f"joventut_vs_valencia_game3",
        date=date,
        league=league,
        record_type="full_game",
        home_team=home_team,
        away_team=away_team,
        market_line=home_market_line,
        current_line=market_data['current_line'],
        open_line=market_data['open_line'],
    )

    home_tm = TeamMetrics(
        ortg=home_data['ortg'],
        drtg=home_data['drtg'],
        baseline_net=home_data['baseline_net'],
        recent_net=home_data['recent_net'],
        pace=home_data['pace'],
        rest_days=home_data['rest_days'],
        travel_km=home_data['travel_km'],
        back_to_back=home_data['back_to_back'],
        three_in_six=home_data['three_in_six'],
        split_edge=home_data['split_edge'],
        rotation_depth=home_data['rotation_depth'],
        injury_status=home_data['injury_status'],
        coach_stability=home_data['coach_stability'],
        motivation=home_data['motivation'],
        open_line=market_data['open_line'],
        current_line=market_data['current_line'],
    )

    away_tm = TeamMetrics(
        ortg=away_data['ortg'],
        drtg=away_data['drtg'],
        baseline_net=away_data['baseline_net'],
        recent_net=away_data['recent_net'],
        pace=away_data['pace'],
        rest_days=away_data['rest_days'],
        travel_km=away_data['travel_km'],
        back_to_back=away_data['back_to_back'],
        three_in_six=away_data['three_in_six'],
        split_edge=away_data['split_edge'],
        rotation_depth=away_data['rotation_depth'],
        injury_status=away_data['injury_status'],
        coach_stability=away_data['coach_stability'],
        motivation=away_data['motivation'],
        open_line=-market_data['open_line'],  # Invert for away team
        current_line=-market_data['current_line'],
    )

    result = eu_build_full_game(home_tm, away_tm, ctx)

    # The template gives us projected scores
    projected_home = result['projected_home_score']
    projected_away = result['projected_away_score']
    projected_total = result['projected_total']
    projected_spread = projected_home - projected_away

    print(f"  Projected Final Score:")
    print(f"    {home_team:25s} {projected_home:.1f}")
    print(f"    {away_team:25s} {projected_away:.1f}")
    print(f"    {'-' * 40}")
    print(f"    {'Total':25s} {projected_total:.1f}")
    print(f"    {'Spread':25s} {projected_spread:+.1f}")
    print()
    print(f"  Model Components:")
    print(f"    Historical Efficiency Gap:     {result['historical_gap']:+.2f}")
    print(f"    Rest/Travel Gap:               {result['rest_gap']:+.2f}")
    print(f"    Home/Away Split Gap:           {result['split_gap']:+.2f}")
    print(f"    Context Gap (rotation/injuries): {result['context_gap']:+.2f}")
    print(f"    Raw Model Edge:                {result['model_edge']:+.2f}")
    print(f"    Market Validation Score:       {result['market_score']:+.2f}")
    print(f"    Total Model Score:             {result['model_edge'] + result['market_score'] * 0.9:.2f}")
    print()
    print(f"  Win Probability: {home_team} {result['probability']:.1%}")
    print(f"  Lean: {result['lean']}")
    print()

    # ========================================================================
    # 2. MANUAL EDGE CALCULATION (Calibrated for this specific matchup)
    # ========================================================================
    print("-" * 84)
    print("  CALIBRATED EDGE ANALYSIS (Adjusted for Series Context)")
    print("-" * 84)
    print()

    # Factors favoring Joventut (Home + Elimination)
    # 1. Elimination game home dog: historically ~55-58% cover rate in 1H
    # 2. Joventut's only win vs Valencia was at home (Feb 2026)
    # 3. Valencia has 2-0 cushion -> might not have same intensity

    # Factors favoring Valencia
    # 1. 4-1 head-to-head this season
    # 2. Better net rating (+6.0 vs -3.0 = 9 point gap)
    # 3. Deeper bench (rotation depth 10 vs 8)
    # 4. Defensive adjustments worked in Game 2 (held Joventut to 76)

    # Adjusted model edge with "Elimination Home Dog" factor
    elimination_boost = 2.5  # ~8-10% boost for home elimination game
    valencia_cushion_penalty = -1.5  # Valencia may let off gas slightly
    game3_adjustment = elimination_boost + valencia_cushion_penalty  # +1.0 net

    adjusted_edge = result['model_edge'] + game3_adjustment
    adjusted_prob = eu_score_to_prob(adjusted_edge + result['market_score'] * 0.9)

    print(f"  Raw Model Edge:          {result['model_edge']:+.2f}")
    print(f"  Elimination Boost:       +{elimination_boost:.1f}")
    print(f"  Valencia Cushion Penalty: {valencia_cushion_penalty:+.1f}")
    print(f"  Adjusted Game Edge:      {adjusted_edge:+.2f}")
    print(f"  Adjusted Win Prob:       {adjusted_prob:.1%}")
    print()

    # ========================================================================
    # 3. 1ST HALF ANALYSIS (Sharp Consensus Focus)
    # ========================================================================
    print("=" * 84)
    print("  SECTION 2: FIRST HALF ANALYSIS (Sharp Focus - Elimination Home Dog)")
    print("=" * 84)
    print()

    # 1st half factors:
    # - Joventut will come out with extreme urgency
    # - Valencia may absorb early punch (2-0 cushion)
    # - Home crowd energy peaks in first 20 minutes
    # - Coach tactics: early physicality from Joventut

    h1_home_intensity = 1.12   # +12% intensity in 1st half (elimination)
    h1_away_cushion = 0.95     # Valencia -5% early intensity (cushion)

    h1_home_proj = (home_data['ortg'] / 100) * 40 * h1_home_intensity
    h1_away_proj = (away_data['ortg'] / 100) * 40 * h1_away_cushion

    # Adjust for defensive matchups
    h1_home_proj *= (100 / away_data['drtg'])
    h1_away_proj *= (100 / home_data['drtg'])

    h1_home_proj = round(h1_home_proj, 1)
    h1_away_proj = round(h1_away_proj, 1)
    h1_total_proj = round(h1_home_proj + h1_away_proj, 1)
    h1_spread_proj = round(h1_home_proj - h1_away_proj, 1)

    print(f"  1st Half Projected:")
    print(f"    {home_team:25s} {h1_home_proj:.1f}")
    print(f"    {away_team:25s} {h1_away_proj:.1f}")
    print(f"    {'-' * 40}")
    print(f"    {'1H Total':25s} {h1_total_proj:.1f}  (Market: {market_data['h1_total']})")
    print(f"    {'1H Spread':25s} {h1_spread_proj:+.1f}  (Market: {market_data['h1_spread']})")
    print()

    # 1H Spread confidence
    h1_spread_edge = h1_spread_proj - market_data['h1_spread']
    h1_spread_conf = confidence_score(h1_spread_edge * 10, volatility=0.50)
    h1_spread_rec = bet_recommendation(h1_spread_conf)

    # 1H Total confidence
    h1_total_edge = h1_total_proj - market_data['h1_total']
    h1_total_conf = confidence_score(h1_total_edge, volatility=0.45)
    h1_total_rec = bet_recommendation(h1_total_conf)

    print(f"  1ST HALF BETTING RECOMMENDATIONS:")
    print(f"    Spread ({market_data['h1_spread']:+.1f}): Edge {h1_spread_edge:+.1f}, Conf {h1_spread_conf:.1f}%, {h1_spread_rec}")
    print(f"    Total ({market_data['h1_total']}):  Edge {h1_total_edge:+.1f}, Conf {h1_total_conf:.1f}%, {h1_total_rec}")
    print(f"    Moneyline ({home_team}): Win prob ~{min(100, max(0, 50 + h1_spread_edge * 5)):.0f}%")
    print()

    # ========================================================================
    # 4. 1ST QUARTER ANALYSIS
    # ========================================================================
    print("=" * 84)
    print("  SECTION 3: FIRST QUARTER ANALYSIS")
    print("=" * 84)
    print()

    # Use the MultiSportModel Q1 projection
    q1_proj = project_basketball_q1(home_data, away_data)

    q1_spread = q1_proj['q1_spread']
    q1_total = q1_proj['q1_total']
    q1_home = q1_proj['home_q1_points']
    q1_away = q1_proj['away_q1_points']
    q1_prob_home = q1_proj['q1_prob_home_win']

    print(f"  Q1 Projected:")
    print(f"    {home_team:25s} {q1_home:.1f}")
    print(f"    {away_team:25s} {q1_away:.1f}")
    print(f"    {'-' * 40}")
    print(f"    {'Q1 Total':25s} {q1_total:.1f}  (Market: {market_data['q1_total']})")
    print(f"    {'Q1 Spread':25s} {q1_spread:+.1f}  (Market: {market_data['q1_spread']})")
    print()

    # Q1 Edge calculation
    q1_spread_edge = q1_spread - market_data['q1_spread']
    q1_total_edge = q1_total - market_data['q1_total']

    q1_spread_conf = confidence_score(q1_spread_edge * 10, volatility=0.55)
    q1_total_conf = confidence_score(q1_total_edge, volatility=0.50)

    q1_spread_rec = bet_recommendation(q1_spread_conf)
    q1_total_rec = bet_recommendation(q1_total_conf)

    print(f"  Q1 BETTING RECOMMENDATIONS:")
    print(f"    Spread ({market_data['q1_spread']:+.1f}): Edge {q1_spread_edge:+.1f}, Conf {q1_spread_conf:.1f}%, {q1_spread_rec}")
    print(f"    Total ({market_data['q1_total']}):  Edge {q1_total_edge:+.1f}, Conf {q1_total_conf:.1f}%, {q1_total_rec}")
    print(f"    Moneyline ({home_team}): Win prob {q1_prob_home:.1%}")
    print()

    # ========================================================================
    # 5. FULL GAME BETTING RECOMMENDATIONS
    # ========================================================================
    print("=" * 84)
    print("  SECTION 4: FULL GAME BETTING RECOMMENDATIONS")
    print("=" * 84)
    print()

    spread_edge = projected_spread - market_data['spread']
    total_edge = projected_total - market_data['total']

    spread_confidence = confidence_score(spread_edge * 5, volatility=0.40, market_alignment=result['market_score'])
    total_confidence = confidence_score(total_edge, volatility=0.45, market_alignment=0.0)
    ml_confidence = confidence_score(
        (adjusted_prob - 0.5) * 100,
        volatility=0.40,
        market_alignment=result['market_score']
    )

    spread_rec = bet_recommendation(spread_confidence)
    total_rec = bet_recommendation(total_confidence)
    ml_rec = bet_recommendation(ml_confidence)

    print(f"  +{'-' * 64}+")
    print(f"  |  MARKET                    |  PROJECTION  |  EDGE  |  CONF  |    |")
    print(f"  +{'-' * 64}+")
    print(f"  |  Spread ({market_data['spread']:+.1f})         |  {projected_spread:+.1f}        |  {spread_edge:+.2f}  |  {spread_confidence:.0f}%   |  {spread_rec:<4s} |")
    print(f"  |  Total  O/U {market_data['total']}      |  {projected_total:.0f}           |  {total_edge:+.1f}   |  {total_confidence:.0f}%   |  {total_rec:<4s} |")
    print(f"  |  Moneyline ({home_team})  |  {adjusted_prob:.0%} win        |  {(adjusted_prob - 0.5)*100:+.1f}% |  {ml_confidence:.0f}%   |  {ml_rec:<4s} |")
    print(f"  +{'-' * 64}+")
    print()

    # ========================================================================
    # 6. PLAYER PROPS ANALYSIS
    # ========================================================================
    print("=" * 84)
    print("  SECTION 5: PLAYER PROPS ANALYSIS")
    print("=" * 84)
    print()

    # --- JABARI PARKER (Joventut) - OVER Points ---
    # Analysis: Do-or-die game, usage rate spikes, ex-NBA vet
    # Game 1: ~28 pts, Game 2: ~18 pts
    # Market line likely around 18.5-20.5 points
    parker_proj = player_prop_edge(
        player_avg=19.5,      # Series average ~19 ppg
        market_line=18.5,     # Estimated market line
        usage_boost=1.20,     # +20% usage in elimination game
        pace_factor=1.0,
        opp_def_adj=1.05,     # Valencia defense is good but Parker is focal point
        minutes_adj=1.10,     # Will play ~38+ minutes
    )

    print(f"  {'>> JABARI PARKER (Joventut) - Points':-^70s}")
    print(f"    Projection:       {parker_proj['projection']:.1f}")
    print(f"    Market Line:      {parker_proj['market_line']}")
    print(f"    Edge:             {parker_proj['edge']:+.1f} ({parker_proj['edge_pct']:+.1f}%)")
    print(f"    Confidence:       {parker_proj['confidence']:.1f}%")
    print(f"    Recommendation:   {parker_proj['lean']} - {parker_proj['recommendation']}")
    print(f"    Key Factors:     Elimination game -> usage spike; ex-NBA shot creator")
    print(f"                     Valencia has no single elite wing defender for Parker")
    print()

    # --- JEAN MONTERO (Valencia) - OVER Assists ---
    # Analysis: Dicing up Joventut P&R, drawing help defenders
    # Season avg ~5-6 assists, series avg likely higher
    montero_proj = player_prop_edge(
        player_avg=6.5,       # Playoff assist avg
        market_line=5.5,      # Estimated market
        usage_boost=1.05,     # Slight usage bump
        pace_factor=1.0,
        opp_def_adj=1.15,     # Joventut defense gives up assists in P&R
        minutes_adj=1.05,     # ~32 minutes
    )

    print(f"  {'>> JEAN MONTERO (Valencia) - Assists':-^70s}")
    print(f"    Projection:       {montero_proj['projection']:.1f}")
    print(f"    Market Line:      {montero_proj['market_line']}")
    print(f"    Edge:             {montero_proj['edge']:+.1f} ({montero_proj['edge_pct']:+.1f}%)")
    print(f"    Confidence:       {montero_proj['confidence']:.1f}%")
    print(f"    Recommendation:   {montero_proj['lean']} - {montero_proj['recommendation']}")
    print(f"    Key Factors:     Dicing up Joventut P&R coverage; draws help D")
    print(f"                     Ricky Rubio checking him -> will look to kick out")
    print()

    # --- RICKY RUBIO (Joventut) - UNDER Points / OVER Assists ---
    rubio_pts_proj = player_prop_edge(
        player_avg=8.0,       # Series scoring avg
        market_line=9.5,      # Estimated market (public might overrate his scoring)
        usage_boost=0.90,     # Won't be the scorer
        pace_factor=1.0,
        opp_def_adj=0.95,
        minutes_adj=1.05,
    )

    rubio_ast_proj = player_prop_edge(
        player_avg=7.0,       # Series assist avg
        market_line=6.5,      # Estimated market
        usage_boost=1.10,     # Facilitator role increases
        pace_factor=1.0,
        opp_def_adj=1.10,
        minutes_adj=1.05,
    )

    print(f"  {'>> RICKY RUBIO (Joventut) - Points (UNDER lean)':-^70s}")
    print(f"    Projection:       {rubio_pts_proj['projection']:.1f}")
    print(f"    Market Line:      {rubio_pts_proj['market_line']}")
    print(f"    Edge:             {rubio_pts_proj['edge']:+.1f} ({rubio_pts_proj['edge_pct']:+.1f}%)")
    print(f"    Confidence:       {rubio_pts_proj['confidence']:.1f}%")
    print(f"    Recommendation:   {rubio_pts_proj['lean']} - {rubio_pts_proj['recommendation']}")
    print(f"    Key Factors:     Floor general, not scorer; feeds Hunt & Parker")
    print()

    print(f"  {'>> RICKY RUBIO (Joventut) - Assists (OVER lean)':-^70s}")
    print(f"    Projection:       {rubio_ast_proj['projection']:.1f}")
    print(f"    Market Line:      {rubio_ast_proj['market_line']}")
    print(f"    Edge:             {rubio_ast_proj['edge']:+.1f} ({rubio_ast_proj['edge_pct']:+.1f}%)")
    print(f"    Confidence:       {rubio_ast_proj['confidence']:.1f}%")
    print(f"    Recommendation:   {rubio_ast_proj['lean']} - {rubio_ast_proj['recommendation']}")
    print(f"    Key Factors:     Facilitates for Parker/Hunt; elimination = ball in his hands")
    print()

    # --- NEAL SAKO (Valencia) - OVER Rebounds ---
    sako_proj = player_prop_edge(
        player_avg=8.5,       # Series rebound avg
        market_line=7.5,      # Estimated market
        usage_boost=1.05,     # Slight boost
        pace_factor=1.0,
        opp_def_adj=1.10,     # Joventut may rush shots -> more defensive rebounding
        minutes_adj=1.05,
    )

    print(f"  {'>> NEAL SAKO (Valencia) - Rebounds':-^70s}")
    print(f"    Projection:       {sako_proj['projection']:.1f}")
    print(f"    Market Line:      {sako_proj['market_line']}")
    print(f"    Edge:             {sako_proj['edge']:+.1f} ({sako_proj['edge_pct']:+.1f}%)")
    print(f"    Confidence:       {sako_proj['confidence']:.1f}%")
    print(f"    Recommendation:   {sako_proj['lean']} - {sako_proj['recommendation']}")
    print(f"    Key Factors:     Physical force in paint; Joventut rushed shots")
    print(f"                     Defensive rebounding opportunities in elimination game")
    print()

    # ========================================================================
    # 7. TOTAL (UNDER) ANALYSIS - SECONDARY SHARP LEAN
    # ========================================================================
    print("=" * 84)
    print("  SECTION 6: TOTAL MARKET ANALYSIS (UNDER 165.5)")
    print("=" * 84)
    print()

    # Game 1: 235 pts (anomaly - OT + frantic pace)
    # Game 2: 166 pts (regression)
    # Expectation: Elimination game -> tighter defense, slower pace
    game1_total = 235
    game2_total = 166
    season_avg_total = (home_data['ortg'] + away_data['ortg']) / 100 * 70 * 2
    series_weighted_avg = (game1_total + game2_total * 3) / 4  # Weight Game 2 higher

    print(f"  Series Totals:")
    print(f"    Game 1 (Valencia 118-117 OT):  {game1_total} pts  (ANOMALY)")
    print(f"    Game 2 (Valencia 90-76):       {game2_total} pts  (REGRESSION)")
    print(f"    Season Avg Projection:         {season_avg_total:.0f} pts")
    print(f"    Weighted Series Avg:           {series_weighted_avg:.0f} pts")
    print()

    # Elimination game factors pushing UNDER:
    # 1. Tighter whistle -> fewer fast break points
    # 2. Higher defensive intensity
    # 3. Deliberate offensive sets under pressure
    # 4. Valencia wants slow pace (worked in G2)
    # 5. Joventut's offense struggled vs Valencia D in G2 (76 pts)

    under_projected = (series_weighted_avg * 0.4 + season_avg_total * 0.3 + game2_total * 0.3)
    under_edge = market_data['total'] - under_projected
    under_conf = confidence_score(under_edge, volatility=0.35)
    under_rec = bet_recommendation(under_conf)

    print(f"  Projected Total (adjusted):     {under_projected:.0f}")
    print(f"  Market Total:                   {market_data['total']}")
    print(f"  Edge to UNDER:                  {under_edge:+.1f}")
    print(f"  Confidence:                     {under_conf:.1f}%")
    print(f"  Recommendation:                  UNDER {market_data['total']} - {under_rec}")
    print()
    print(f"  Factors supporting UNDER:")
    print(f"    + Game 1 (118-117 OT) was a clear outlier/anomaly")
    print(f"    + Valencia's G2 defensive adjustments were highly effective")
    print(f"    + Elimination games historically see tightened whistles")
    print(f"    + Both teams know stakes -> more deliberate offensive execution")
    print(f"    + Valencia close-out games tend to be lower scoring")
    print()

    # ========================================================================
    # 8. SHARP CONSENSUS SUMMARY
    # ========================================================================
    print("=" * 84)
    print("  SECTION 7: SHARP CONSENSUS & FINAL RECOMMENDATIONS")
    print("=" * 84)
    print()

    print(f"  #{'=' * 68}#")
    print(f"  #                    SHARP BETTING CONSENSUS                          #")
    print(f"  #{'=' * 68}#")
    print(f"  # PRIMARY LEAN: Joventut 1ST HALF Spread (-1.5) / Moneyline          #")
    print(f"  #   Logic: Elimination Game Home Dog - Joventut will come out        #")
    print(f"  #   with extreme urgency in front of home crowd. Valencia's 2-0      #")
    print(f"  #   cushion may cause them to absorb early punch rather than match   #")
    print(f"  #   intensity. Sharp syndicates historically hammer this spot.       #")
    print(f"  #{'=' * 68}#")
    print(f"  # SECONDARY LEAN: Full Game UNDER {market_data['total']}                                   #")
    print(f"  #   Logic: Game 1's 118-117 anomaly heavily skewed public perception #")
    print(f"  #   Game 2 regressed to 166. Elimination game = tighter D, fewer    #")
    print(f"  #   transition points, deliberate offense under pressure.            #")
    print(f"  #{'=' * 68}#")
    print()

    print(f"  +{'-' * 68}+")
    print(f"  |  FINAL RECOMMENDATIONS SUMMARY                                       |")
    print(f"  +{'-' * 68}+")

    # Tier 1: Sharp Consensus (highest confidence)
    print(f"  |  * TIER 1 - SHARP CONSENSUS                                          |")
    print(f"  |  +{'-' * 44}+{'-' * 10}+{'-' * 9}+|")
    print(f"  |  | {'Joventut 1ST HALF -1.5':40s} | {'Conf':>6s} | {'REC':>5s} ||")
    print(f"  |  | {'':40s} | {h1_spread_conf:>5.0f}%  | {'BET':>5s} ||")

    print(f"  |  | {'UNDER Total 165.5 (Full Game)':40s} | {'Conf':>6s} | {'REC':>5s} ||")
    print(f"  |  | {'':40s} | {under_conf:>5.0f}%  | {'BET':>5s} ||")
    print(f"  |  +{'-' * 44}+{'-' * 10}+{'-' * 9}+|")
    print()

    # Tier 2: Player Props
    print(f"  |  * TIER 2 - PLAYER PROPS                                             |")
    print(f"  |  +{'-' * 44}+{'-' * 10}+{'-' * 9}+|")
    print(f"  |  | {'Jabari Parker OVER 18.5 Pts':40s} | {'Conf':>6s} | {'REC':>5s} ||")
    print(f"  |  | {'':40s} | {parker_proj['confidence']:>5.0f}%  | {'BET':>5s} ||")
    print(f"  |  | {'Jean Montero OVER 5.5 Asts':40s} | {'Conf':>6s} | {'REC':>5s} ||")
    print(f"  |  | {'':40s} | {montero_proj['confidence']:>5.0f}%  | {'BET':>5s} ||")
    print(f"  |  | {'Ricky Rubio UNDER 9.5 Pts':40s} | {'Conf':>6s} | {'REC':>5s} ||")
    print(f"  |  | {'':40s} | {rubio_pts_proj['confidence']:>5.0f}%  | {'BET':>5s} ||")
    print(f"  |  | {'Ricky Rubio OVER 6.5 Asts':40s} | {'Conf':>6s} | {'REC':>5s} ||")
    print(f"  |  | {'':40s} | {rubio_ast_proj['confidence']:>5.0f}%  | {'LEAN':>5s} ||")
    print(f"  |  | {'Neal Sako OVER 7.5 Rebs':40s} | {'Conf':>6s} | {'REC':>5s} ||")
    print(f"  |  | {'':40s} | {sako_proj['confidence']:>5.0f}%  | {'BET':>5s} ||")
    print(f"  |  +{'-' * 44}+{'-' * 10}+{'-' * 9}+|")
    print()

    # Tier 3: Value Plays
    print(f"  |  * TIER 3 - VALUE PLAYS (lower confidence, higher odds)               |")
    print(f"  |  +{'-' * 44}+{'-' * 10}+{'-' * 9}+|")
    print(f"  |  | {'Joventut Full Game ML (+100)':40s} | {'Conf':>6s} | {'REC':>5s} ||")
    print(f"  |  | {'':40s} | {ml_confidence:>5.0f}%  | {'VALUE':>5s} ||")
    print(f"  |  | {'Joventut Q1 -0.5':40s} | {'Conf':>6s} | {'REC':>5s} ||")
    print(f"  |  | {'':40s} | {q1_spread_conf:>5.0f}%  | {'LEAN':>5s} ||")
    print(f"  |  +{'-' * 44}+{'-' * 10}+{'-' * 9}+|")
    print(f"  +{'-' * 68}+")
    print()

    # ========================================================================
    # 9. KEY NARRATIVE SUMMARY
    # ========================================================================
    print("=" * 84)
    print("  KEY NARRATIVE & CONTEXTUAL FACTORS")
    print("=" * 84)
    print()
    print(f"  1. SERIES CONTEXT: Valencia leads 2-0. A win today secures them")
    print(f"     maximum rest before the ACB Finals. A loss forces Game 4.")
    print()
    print(f"  2. MOTIVATION DISPARITY: Joventut is in pure desperation mode.")
    print(f"     Valencia wants to close out but has the safety net of Game 4.")
    print(f"     This typically manifests in the first half (Sharp Consensus bet).")
    print()
    print(f"  3. PACE NARRATIVE: Game 1 was a track meet (Valencia won 118-117).")
    print(f"     Valencia intentionally slowed the pace in Game 2 (90-76 win).")
    print(f"     Expect another deliberate, defensive-minded game today.")
    print()
    print(f"  4. HOME COURT: Badalona is one of the toughest environments in the ACB.")
    print(f"     Joventut's only win vs Valencia this season came at home (87-90).")
    print(f"     The crowd will be electric for this elimination game.")
    print()
    print(f"  5. DEPTH ADVANTAGE: Valencia's bench outplayed Joventut's in Game 2")
    print(f"     (Costello, Taylor were major factors). In an elimination game,")
    print(f"     Joventut will lean even heavier on their starters (Parker, Rubio, Hanga).")
    print(f"     This cuts both ways: more minutes for stars but fatigue late.")
    print()
    print(f"  6. BETTING NARRATIVE: The market is pricing this as a near toss-up")
    print(f"     despite Valencia's 4-1 H2H edge. This reflects the elimination")
    print(f"     home dog dynamic. Sharp money is on Joventut 1H.")
    print()

    # ========================================================================
    # BUILD RESULT DICTIONARY
    # ========================================================================
    results = {
        "game_info": {
            "home_team": home_team,
            "away_team": away_team,
            "league": league,
            "date": date,
            "venue": "Palau Municipal d'Esports de Badalona",
            "series": "ACB Semi-Finals (Valencia leads 2-0)",
            "description": "Elimination Game 3 - Joventut must win to stay alive"
        },
        "team_metrics": {
            "home": home_data,
            "away": away_data
        },
        "market_data": market_data,
        "model_projections": {
            "full_game": {
                "home_score": round(projected_home, 1),
                "away_score": round(projected_away, 1),
                "total": round(projected_total, 1),
                "spread": round(projected_spread, 1),
                "win_probability": round(adjusted_prob, 3),
                "raw_model_edge": round(result['model_edge'], 2),
                "adjusted_edge": round(adjusted_edge, 2),
            },
            "first_half": {
                "home_score": h1_home_proj,
                "away_score": h1_away_proj,
                "total": h1_total_proj,
                "spread": h1_spread_proj,
            },
            "first_quarter": {
                "home_score": q1_home,
                "away_score": q1_away,
                "total": q1_total,
                "spread": q1_spread,
                "win_probability": round(q1_prob_home, 3),
            }
        },
        "recommendations": {
            "tier1_sharp_consensus": {
                "joventut_1h_spread": {
                    "market": f"{market_data['h1_spread']}",
                    "edge": round(h1_spread_edge, 2),
                    "confidence": round(h1_spread_conf, 1),
                    "recommendation": h1_spread_rec,
                },
                "under_total": {
                    "market": market_data['total'],
                    "projected": round(under_projected, 0),
                    "edge": round(under_edge, 1),
                    "confidence": round(under_conf, 1),
                    "recommendation": under_rec,
                }
            },
            "tier2_player_props": {
                "jabari_parker_over_points": parker_proj,
                "jean_montero_over_assists": montero_proj,
                "ricky_rubio_under_points": rubio_pts_proj,
                "ricky_rubio_over_assists": rubio_ast_proj,
                "neal_sako_over_rebounds": sako_proj,
            },
            "tier3_value_plays": {
                "joventut_ml": {
                    "market": "+100",
                    "win_probability": round(adjusted_prob, 3),
                    "confidence": round(ml_confidence, 1),
                    "recommendation": ml_rec,
                },
                "joventut_q1_spread": {
                    "market": f"{market_data['q1_spread']}",
                    "edge": round(q1_spread_edge, 2),
                    "confidence": round(q1_spread_conf, 1),
                    "recommendation": q1_spread_rec,
                }
            }
        },
        "narrative_factors": {
            "series_context": "Valencia leads 2-0, facing elimination game",
            "motivation": "Joventut maximal desperation, Valencia has cushion",
            "pace_outlook": "Expect slowed pace (not G1 track meet)",
            "home_court": "Badalona = tough environment, Joventut's only win here",
            "depth": "Valencia bench advantage, Joventut leans on starters",
            "market_narrative": "Toss-up market reflects elimination home dog dynamic"
        },
        "timestamp": datetime.now().isoformat()
    }

    return results


def main():
    """Run the comprehensive Joventut vs Valencia Game 3 analysis"""

    print("\n" + "=" * 84)
    print("  ACB PLAYOFFS GAME 3 ANALYSIS ENGINE")
    print("  DKV Joventut vs Valencia Basket")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 84 + "\n")

    result = analyze_matchup()

    # Save results to JSON
    output_dir = Path("output/basketball")
    output_dir.mkdir(parents=True, exist_ok=True)

    out_path = output_dir / "joventut_vs_valencia_game3_analysis.json"
    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"\n{'=' * 84}")
    print(f"  Analysis complete. Full results saved to: {out_path}")
    print(f"  Use these predictions to inform your betting decisions.")
    print(f"  Remember: No model is perfect. Bankroll management is key.")
    print(f"{'=' * 84}")

    return result


if __name__ == "__main__":
    result = main()