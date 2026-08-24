#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Run FC Nõmme United vs JK Narva Trans match analysis and push results to Discord.

Meistriliiga (Estonian League) - Match Date: July 31, 2026
Kickoff: 12:00 PM EDT - Tallinn, Männiku staadion

Based on comprehensive H2H, odds, and team performance data.
"""

import os
import sys
import json
from datetime import datetime

# Ensure UTF-8 output on Windows terminals (prevents encoding errors)
try:
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())
except Exception:
    pass

import pandas as pd
from dotenv import load_dotenv

# Load environment variables (Discord webhook URL)
load_dotenv()

# Import the soccer predictor
from models.soccer_predictor import SoccerPredictor

# Import Discord integration
from discord_integration import (
    push_to_discord,
    create_prediction_embed,
    create_organized_prediction_embed,
    get_color_for_recommendation,
    COLORS,
    SPORT_EMOJIS,
    test_webhook,
)


def main():
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url or webhook_url == "None":
        print("DISCORD_WEBHOOK_URL not set in .env")
        return False

    print("=" * 60)
    print("  FC NÕMME UNITED vs JK NARVA TRANS")
    print("  Meistriliiga - July 31, 2026 - 12:00 PM EDT")
    print("=" * 60)

    # Create predictor with default league config
    predictor = SoccerPredictor(league="default")

    # ===================================================================
    # Team Metrics based on provided data
    # ===================================================================
    #
    # Nõmme United (Home):
    #   - 7th place, 25 pts, dominated H2H (3-0-0, 11 goals in 3 meetings)
    #   - Won 5-1 and 2-1 vs Narva this season
    #   - ML: 1.80 (-125), Team Total O1.5: -163
    #   - Key attackers: Beglarishvili, Chisala
    #
    # Narva Trans (Away):
    #   - 10th place (last), 13 pts, -32 GD
    #   - Conceded 47 GA in 20 matches (2.35/game), 2.88/game away
    #   - ML: 3.40 (+240), Team Total O1.5: +123
    #
    # Market Context:
    #   - Over 2.5: 1.41 (heavily juiced), Over 3.5: ~2.00-2.10
    #   - BTTS Yes: 1.42 (heavily favored)
    # ===================================================================

    nomme_metrics = {
        "home_xg_for": 1.70,         # Strong attack, 11 goals in 3 H2H
        "home_xg_against": 1.25,     # Decent defense
        "home_shots": 13.0,
        "home_sot": 4.5,
        "home_goals_for": 1.8,       # Strong scoring form
        "home_goals_against": 1.2,
        "home_clean_sheets": 4,      # 4 clean sheets in last 10
        "home_missing_attacker": 0,
        "home_missing_creator": 0,
        "home_missing_cb": 0,
        "home_missing_gk": 0,
        "home_tempo": 0.40,          # Forward-leaning, aggressive
        "home_width_crossing": 0.50,
        "home_final_third_pressure": 0.55,
    }

    narva_metrics = {
        "away_xg_for": 1.10,         # Struggling attack
        "away_xg_against": 1.80,     # Leaky defense (2.35/game, 2.88 away)
        "away_shots": 10.0,
        "away_sot": 3.2,
        "away_goals_for": 0.9,       # Low scoring
        "away_goals_against": 2.35,  # Very leaky
        "away_clean_sheets": 1,      # Rarely keeps clean sheet
        "away_missing_attacker": 0,
        "away_missing_creator": 0,
        "away_missing_cb": 0,
        "away_missing_gk": 0,
        "away_tempo": 0.20,          # Defensive, reactive
        "away_width_crossing": 0.45,
        "away_final_third_pressure": 0.35,
    }

    # Combine metrics
    match_kwargs = {**nomme_metrics, **narva_metrics}

    # Run prediction
    print("\n[DATA] Running prediction model with provided metrics...")
    print(f"       Nõmme United xG For: {nomme_metrics['home_xg_for']:.2f}")
    print(f"       Narva Trans xG Against: {narva_metrics['away_xg_against']:.2f}")
    print(f"       Market: ML 1.80 (-125) | O2.5 1.41 | BTTS 1.42")

    result = predictor.predict(
        features=pd.DataFrame(),
        model=None,
        home_team="Nõmme United",
        away_team="Narva Trans",
        market_line=-0.75,      # Reflecting -125 favorite (Asian Handicap)
        market_total=3.0,       # Between O2.5 and O3.5 given odds
        league="default",
        **match_kwargs,
    )

    # Extract data from result
    game = result.get("game", {})
    predictions = result.get("predictions", {})
    goals_analysis = result.get("goals_analysis", {})
    corners_analysis = result.get("corners_analysis", {})
    btts_prob = result.get("btts_probability", 0)
    corner_proj = result.get("corner_projection", 0)

    home_team = result.get("home_team", "Nõmme United")
    away_team = result.get("away_team", "Narva Trans")

    home_goals = game.get("projected_home_goals", 0)
    away_goals = game.get("projected_away_goals", 0)
    total_goals = game.get("projected_total_goals", 0)
    home_win_pct = game.get("home_win_prob", 0) * 100
    draw_pct = game.get("draw_prob", 0) * 100
    away_win_pct = game.get("away_win_prob", 0) * 100

    # Side prediction
    side_rec = predictions.get("side", {}).get("recommendation", "PASS")
    side_conf = predictions.get("side", {}).get("confidence", 0)
    side_edge = predictions.get("side", {}).get("edge", 0)

    # Total prediction
    total_rec = predictions.get("total", {}).get("recommendation", "PASS")
    total_conf = predictions.get("total", {}).get("confidence", 0)
    total_edge = predictions.get("total", {}).get("edge", 0)

    # BTTS prediction
    btts_rec = predictions.get("btts", {}).get("recommendation", "PASS")
    btts_conf = predictions.get("btts", {}).get("confidence", 0)

    # Goal probabilities
    over_15 = goals_analysis.get("over_15_prob", 0) * 100
    over_25 = goals_analysis.get("over_25_prob", 0) * 100
    over_35 = goals_analysis.get("over_35_prob", 0) * 100

    # Corners
    corners_proj_val = corners_analysis.get("projection", 0)
    corners_85 = corners_analysis.get("over_85_prob", 0) * 100
    corners_95 = corners_analysis.get("over_95_prob", 0) * 100

    # Print summary to console
    print(f"\n{'=' * 60}")
    print(f"  MATCH: {home_team} vs {away_team}")
    print(f"{'=' * 60}")
    print(f"\n  [PROJECTED SCORE] {home_team} {home_goals:.2f} - {away_goals:.2f} {away_team}")
    print(f"  [TOTAL GOALS] {total_goals:.2f}")
    print(f"\n  [MATCH OUTCOME]")
    print(f"     {home_team} Win: {home_win_pct:.1f}%")
    print(f"     Draw:          {draw_pct:.1f}%")
    print(f"     {away_team} Win: {away_win_pct:.1f}%")
    print(f"\n  [GOAL PROBABILITIES]")
    print(f"     Over 1.5: {over_15:.1f}%")
    print(f"     Over 2.5: {over_25:.1f}%")
    print(f"     Over 3.5: {over_35:.1f}%")
    print(f"\n  [BTTS] {btts_prob:.1%}")
    print(f"\n  [CORNERS]")
    print(f"     Projected: {corners_proj_val}")
    print(f"     Over 8.5: {corners_85:.1f}%")
    print(f"     Over 9.5: {corners_95:.1f}%")
    print(f"\n  [BETTING RECOMMENDATIONS]")
    print(f"     Side (AH -0.75): {side_rec} (Conf: {side_conf:.1f}%, Edge: {side_edge:+.3f})")
    print(f"     Total (O/U 3.0): {total_rec} (Conf: {total_conf:.1f}%, Edge: {total_edge:+.3f})")
    print(f"     BTTS:            {btts_rec} (Conf: {btts_conf:.1f}%)")

    # ================================================================
    # Build RICH Discord Embed
    # ================================================================
    print("\n\n[DISCORD] Building rich embed...")

    # Determine embed color based on strongest recommendation
    if side_rec == "STRONG BET" or total_rec == "STRONG BET":
        embed_color = COLORS["strong_bet"]  # Green
    elif side_rec == "BET" or total_rec == "BET":
        embed_color = COLORS["bet"]  # Blue
    elif side_rec == "LEAN" or total_rec == "LEAN":
        embed_color = COLORS["lean"]  # Yellow
    else:
        embed_color = COLORS["neutral"]  # Gray

    # Determine favorite
    if home_win_pct >= 50:
        favorite = home_team
        favorite_pct = home_win_pct
    elif away_win_pct >= 50:
        favorite = away_team
        favorite_pct = away_win_pct
    else:
        favorite = "Draw"
        favorite_pct = draw_pct

    # Build fields
    fields = []

    # 1. Match Overview
    match_overview = (
        f"**[HOME]** {home_team} (7th, 25 pts)\n"
        f"**[AWAY]** {away_team} (10th, 13 pts, -32 GD)\n"
        f"**[H2H 2026]** {home_team} leads 3-0-0\n"
        f"**[KICKOFF]** Today 12:00 PM EDT | Männiku staadion"
    )
    fields.append({
        "name": "MATCH OVERVIEW",
        "value": match_overview,
        "inline": False
    })

    # 2. Projected Score & Match Outcome
    score_text = (
        f"**Projected Score:** {home_team} {home_goals:.2f} - {away_goals:.2f} {away_team}\n"
        f"**Expected Total:** {total_goals:.2f} Goals\n"
        f"**Favorite:** {favorite} ({favorite_pct:.1f}%)"
    )
    fields.append({
        "name": "PROJECTED SCORE",
        "value": score_text,
        "inline": False
    })

    # 3. Match Outcome Probabilities
    outcome_text = (
        f"**{home_team} Win:** {home_win_pct:.1f}%\n"
        f"**Draw:** {draw_pct:.1f}%\n"
        f"**{away_team} Win:** {away_win_pct:.1f}%"
    )
    fields.append({
        "name": "MATCH OUTCOME (1X2)",
        "value": outcome_text,
        "inline": True
    })

    # 4. Goal Probabilities
    goals_text = (
        f"**Over 1.5:** {over_15:.1f}%\n"
        f"**Over 2.5:** {over_25:.1f}%\n"
        f"**Over 3.5:** {over_35:.1f}%"
    )
    fields.append({
        "name": "GOAL PROBABILITIES",
        "value": goals_text,
        "inline": True
    })

    # 5. BTTS & Corners
    btts_corners_text = (
        f"**BTTS:** {btts_prob:.1%} (Market: 1.42)\n"
        f"**Corners Proj:** {corners_proj_val}\n"
        f"**Over 8.5:** {corners_85:.1f}%\n"
        f"**Over 9.5:** {corners_95:.1f}%"
    )
    fields.append({
        "name": "BTTS & CORNERS",
        "value": btts_corners_text,
        "inline": True
    })

    # 6. Betting Recommendations
    side_emoji = "GREEN" if side_rec in ("STRONG BET", "BET") else "YELLOW" if side_rec == "LEAN" else "GRAY"
    total_emoji = "GREEN" if total_rec in ("STRONG BET", "BET") else "YELLOW" if total_rec == "LEAN" else "GRAY"
    btts_emoji = "GREEN" if btts_rec in ("STRONG BET", "BET") else "YELLOW" if btts_rec == "LEAN" else "GRAY"

    bets_text = (
        f"**Side (AH -0.75):** {side_rec} | Conf: {side_conf:.1f}% | Edge: {side_edge:+.3f}\n"
        f"**Total (O/U 3.0):** {total_rec} | Conf: {total_conf:.1f}% | Edge: {total_edge:+.3f}\n"
        f"**BTTS:** {btts_rec} | Conf: {btts_conf:.1f}% | Market: 1.42 Yes"
    )
    fields.append({
        "name": "BETTING RECOMMENDATIONS",
        "value": bets_text,
        "inline": False
    })

    # 7. H2H Context
    h2h_text = (
        "Nõmme United has won **ALL THREE** meetings vs Narva Trans in 2026:\n"
        "   June 13: Won 2-1 (away)\n"
        "   April 11: Won 5-1 (home)\n"
        "   Scored 11 goals across 3 H2H matches"
    )
    fields.append({
        "name": "HEAD-TO-HEAD CONTEXT",
        "value": h2h_text,
        "inline": False
    })

    # 8. Summary
    if side_rec == "STRONG BET" or total_rec == "STRONG BET":
        summary = "**STRONG BET Available** - High confidence play identified with strong edge"
    elif side_rec == "BET" or total_rec == "BET":
        summary = "**BET Recommended** - Good value opportunity based on model analysis"
    elif side_rec == "LEAN" or total_rec == "LEAN":
        summary = "**LEAN** - Moderate interest, monitor closer to kickoff"
    else:
        # Provide a manual insight even when model says PASS
        summary = (
            "**Model: PASS** - No algorithm play, but H2H dominance and market support Nõmme. "
            "Over 2.5 heavily juiced at 1.41, BTTS 1.42. "
            "Narva concedes 2.88/game away - goals expected."
        )

    fields.append({
        "name": "SUMMARY",
        "value": summary,
        "inline": False
    })

    # Create the embed
    embed = {
        "title": "NÕMME UNITED vs NARVA TRANS",
        "description": (
            "**Meistriliiga** - Matchday\n"
            "Stadium: Männiku staadion, Tallinn\n"
            "Kickoff: July 31, 2026 - 12:00 PM EDT"
        ),
        "color": embed_color,
        "fields": fields,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "footer": {
            "text": "MultiSportPredict • Bivariate Poisson Model"
        }
    }

    payload = {"embeds": [embed]}

    # Print the embed payload info
    print(f"   Embed: {len(fields)} fields, color=#{embed_color:06x}")

    # ================================================================
    # PUSH TO DISCORD
    # ================================================================
    print("\n[DISCORD] Pushing to Discord...")

    try:
        import requests

        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )

        if response.status_code in (200, 204):
            print("\n[SUCCESS] Rich prediction pushed to Discord!")
            print(f"   Match: {home_team} vs {away_team}")
            print(f"   Projected: {home_goals:.2f} - {away_goals:.2f}")
            print(f"   Best Bet: {side_rec} / {total_rec} / {btts_rec}")
            return True
        else:
            print(f"\n[ERROR] Discord push failed: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"\n[ERROR] Exception pushing to Discord: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)