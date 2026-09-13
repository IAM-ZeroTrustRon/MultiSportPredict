#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Run Den Bosch vs Al Fayha match analysis and push results to Discord in rich embed format.

Teams:
  - Den Bosch (FC Den Bosch) - Dutch Eerste Divisie club
  - Al Fayha (Al Fayha FC) - Saudi Pro League club
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
        print("❌ DISCORD_WEBHOOK_URL not set in .env")
        return False

    print("=" * 60)
    print("  DEN BOSCH vs AL FAYHA - Match Analysis")
    print("=" * 60)

    # Create predictor with default league config
    # Den Bosch plays in Eerste Divisie, Al Fayha in Saudi Pro League
    # Use a neutral default league config
    predictor = SoccerPredictor(league="default")

    # Custom team metrics for Den Bosch (Dutch Eerste Divisie)
    # Den Bosch - mid-table Eerste Divisie team, decent attack at home
    den_bosch_metrics = {
        "home_xg_for": 1.55,
        "home_xg_against": 1.35,
        "home_shots": 12.5,
        "home_sot": 4.2,
        "home_goals_for": 1.5,
        "home_goals_against": 1.3,
        "home_clean_sheets": 3,
        "home_missing_attacker": 0,
        "home_missing_creator": 0,
        "home_missing_cb": 0,
        "home_missing_gk": 0,
        "home_tempo": 0.35,
        "home_width_crossing": 0.50,
        "home_final_third_pressure": 0.50,
    }

    # Al Fayha - Saudi Pro League team, solid defensively
    al_fayha_metrics = {
        "away_xg_for": 1.30,
        "away_xg_against": 1.20,
        "away_shots": 11.0,
        "away_sot": 3.8,
        "away_goals_for": 1.2,
        "away_goals_against": 1.1,
        "away_clean_sheets": 4,
        "away_missing_attacker": 0,
        "away_missing_creator": 0,
        "away_missing_cb": 0,
        "away_missing_gk": 0,
        "away_tempo": 0.25,
        "away_width_crossing": 0.45,
        "away_final_third_pressure": 0.45,
    }

    # Combine metrics
    match_kwargs = {**den_bosch_metrics, **al_fayha_metrics}

    # Run prediction
    print("\n📊 Running prediction model...")
    result = predictor.predict(
        features=pd.DataFrame(),
        model=None,
        home_team="Den Bosch",
        away_team="Al Fayha",
        market_line=0.0,
        market_total=2.5,
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

    home_team = result.get("home_team", "Den Bosch")
    away_team = result.get("away_team", "Al Fayha")

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
    print(f"\n  📍 Projected Score: {home_team} {home_goals:.2f} - {away_goals:.2f} {away_team}")
    print(f"  🎯 Total Goals: {total_goals:.2f}")
    print(f"\n  📊 Match Outcome:")
    print(f"     {home_team} Win: {home_win_pct:.1f}%")
    print(f"     Draw:          {draw_pct:.1f}%")
    print(f"     {away_team} Win: {away_win_pct:.1f}%")
    print(f"\n  🥅 Goal Probabilities:")
    print(f"     Over 1.5: {over_15:.1f}%")
    print(f"     Over 2.5: {over_25:.1f}%")
    print(f"     Over 3.5: {over_35:.1f}%")
    print(f"\n  🤝 BTTS: {btts_prob:.1%}")
    print(f"\n  🔲 Corners:")
    print(f"     Projected: {corners_proj_val}")
    print(f"     Over 8.5: {corners_85:.1f}%")
    print(f"     Over 9.5: {corners_95:.1f}%")
    print(f"\n  💰 Betting Recommendations:")
    print(f"     Side (AH): {side_rec} (Conf: {side_conf:.1f}%, Edge: {side_edge:+.3f})")
    print(f"     Total:     {total_rec} (Conf: {total_conf:.1f}%, Edge: {total_edge:+.3f})")
    print(f"     BTTS:      {btts_rec} (Conf: {btts_conf:.1f}%)")

    # ----------------------------------------------------------------
    # Build RICH Discord Embed
    # ----------------------------------------------------------------
    print("\n\n📤 Building rich Discord embed...")

    # Determine overall recommendation from strongest bet
    all_recs = []
    if side_rec in ("STRONG BET", "BET"):
        all_recs.append((side_conf, side_rec, "Side (AH)"))
    if total_rec in ("STRONG BET", "BET"):
        all_recs.append((total_conf, total_rec, "Total Goals"))
    if btts_rec in ("STRONG BET", "BET"):
        all_recs.append((btts_conf, btts_rec, "BTTS"))

    # Determine embed color
    if side_rec == "STRONG BET" or total_rec == "STRONG BET":
        embed_color = COLORS["strong_bet"]  # Green
    elif side_rec == "BET" or total_rec == "BET":
        embed_color = COLORS["bet"]  # Blue
    elif side_rec == "LEAN" or total_rec == "LEAN":
        embed_color = COLORS["lean"]  # Yellow
    else:
        embed_color = COLORS["neutral"]  # Gray

    # Match outcome text
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
        f"🏟️ **Projected Score:** {home_team} {home_goals:.2f} - {away_goals:.2f} {away_team}\n"
        f"📊 **Expected Total:** {total_goals:.2f} Goals\n"
        f"🎯 **Favorite:** {favorite} ({favorite_pct:.1f}%)"
    )
    fields.append({
        "name": "📋 MATCH OVERVIEW",
        "value": match_overview,
        "inline": False
    })

    # 2. Match Outcome Probabilities
    outcome_text = (
        f"🟢 **{home_team} Win:** {home_win_pct:.1f}%\n"
        f"🟡 **Draw:** {draw_pct:.1f}%\n"
        f"🔴 **{away_team} Win:** {away_win_pct:.1f}%"
    )
    fields.append({
        "name": "📊 MATCH OUTCOME (1X2)",
        "value": outcome_text,
        "inline": True
    })

    # 3. Goal Probabilities
    goals_text = (
        f"⚽ **Over 1.5:** {over_15:.1f}%\n"
        f"⚽⚽ **Over 2.5:** {over_25:.1f}%\n"
        f"⚽⚽⚽ **Over 3.5:** {over_35:.1f}%"
    )
    fields.append({
        "name": "🥅 GOAL PROBABILITIES",
        "value": goals_text,
        "inline": True
    })

    # 4. BTTS & Corners
    btts_text = (
        f"🤝 **BTTS:** {btts_prob:.1%}\n"
        f"🔲 **Corners Proj:** {corners_proj_val}\n"
        f"🔲 **Over 8.5:** {corners_85:.1f}%\n"
        f"🔲 **Over 9.5:** {corners_95:.1f}%"
    )
    fields.append({
        "name": "🤝 BTTS & CORNERS",
        "value": btts_text,
        "inline": True
    })

    # 5. Betting Recommendations
    side_emoji = "🟢" if side_rec in ("STRONG BET", "BET") else "🟡" if side_rec == "LEAN" else "⚪"
    total_emoji = "🟢" if total_rec in ("STRONG BET", "BET") else "🟡" if total_rec == "LEAN" else "⚪"
    btts_emoji = "🟢" if btts_rec in ("STRONG BET", "BET") else "🟡" if btts_rec == "LEAN" else "⚪"

    bets_text = (
        f"{side_emoji} **Side (AH):** {side_rec} | Conf: {side_conf:.1f}% | Edge: {side_edge:+.3f}\n"
        f"{total_emoji} **Total:** {total_rec} | Conf: {total_conf:.1f}% | Edge: {total_edge:+.3f}\n"
        f"{btts_emoji} **BTTS:** {btts_rec} | Conf: {btts_conf:.1f}%"
    )
    fields.append({
        "name": "💰 BETTING RECOMMENDATIONS",
        "value": bets_text,
        "inline": False
    })

    # 6. Match Summary
    # Determine the strongest recommendation
    if side_rec == "STRONG BET" or total_rec == "STRONG BET":
        summary = "🔥 **STRONG BET Available** - High confidence play identified"
    elif side_rec == "BET" or total_rec == "BET":
        summary = "✅ **BET Recommended** - Good value opportunity"
    elif side_rec == "LEAN" or total_rec == "LEAN":
        summary = "⚠️ **LEAN** - Moderate interest, monitor closely"
    else:
        summary = "⏸️ **PASS** - No strong value identified, skip this match"

    fields.append({
        "name": "📌 SUMMARY",
        "value": summary,
        "inline": False
    })

    # Create the embed
    embed = {
        "title": "⚽ DEN BOSCH vs AL FAYHA",
        "description": (
            "**Soccer Friendly / Pre-Season Match**\n"
            f"🏟️ {home_team} (Netherlands) vs {away_team} (Saudi Arabia)\n"
            f"📅 Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC"
        ),
        "color": embed_color,
        "fields": fields,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "footer": {
            "text": "MultiSportPredict • Bivariate Poisson Model"
        }
    }

    payload = {"embeds": [embed]}

    # Print the embed payload for debugging
    print(f"\n📤 Embed payload prepared ({len(fields)} fields)")
    print(f"   Color: #{embed_color:06x}")
    print(f"   Title: {embed['title']}")

    # ----------------------------------------------------------------
    # PUSH TO DISCORD
    # ----------------------------------------------------------------
    print("\n📤 Pushing to Discord...")

    try:
        import requests

        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )

        if response.status_code in (200, 204):
            print("\n✅ SUCCESS: Rich prediction pushed to Discord!")
            print(f"   Match: {home_team} vs {away_team}")
            print(f"   Projected: {home_goals:.2f} - {away_goals:.2f}")
            print(f"   Best Bet: {side_rec} / {total_rec}")
            return True
        else:
            print(f"\n❌ Discord push failed: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"\n❌ Error pushing to Discord: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)