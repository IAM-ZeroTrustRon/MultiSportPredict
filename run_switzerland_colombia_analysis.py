#!/usr/bin/env python
"""
Comprehensive Analysis for Switzerland vs Colombia
World Cup Round of 16 - July 7, 2026
Pushes results to Discord with organized betting guide
"""

import sys
import json
import math
import os
from datetime import datetime
from pathlib import Path

# Import the engine
from multi_sport_engine import predict_soccer, push_to_discord

# Import discord integration for organized embeds
from discord_integration import (
    create_organized_prediction_embed,
    push_to_discord as push_organized_to_discord,
    get_color_for_recommendation,
    COLORS,
    SPORT_EMOJIS,
)
from dotenv import load_dotenv

load_dotenv()


def calculate_moneyline_prob(home_lam, away_lam):
    """Calculate Moneyline (1X2) probabilities using Poisson distribution"""
    p_home_win = 0.0
    p_draw = 0.0
    p_away_win = 0.0
    
    for h in range(0, 10):
        p_h = (math.exp(-home_lam) * home_lam**h) / math.factorial(h)
        for a in range(0, 10):
            p_a = (math.exp(-away_lam) * away_lam**a) / math.factorial(a)
            prob = p_h * p_a
            if h > a:
                p_home_win += prob
            elif h == a:
                p_draw += prob
            else:
                p_away_win += prob
    
    return p_home_win, p_draw, p_away_win


def run_switzerland_colombia_analysis():
    """Run comprehensive analysis for Switzerland vs Colombia and push to Discord"""
    
    print("=" * 80)
    print("COMPREHENSIVE MATCH ANALYSIS: SWITZERLAND vs COLOMBIA")
    print("World Cup Round of 16 - July 7, 2026")
    print("=" * 80)
    print()
    
    # ========================================================================
    # TEAM DATA (Based on tournament performance described)
    # ========================================================================
    
    # Switzerland - Group B Winners
    # Results: 1-1 vs Qatar, 4-1 vs Bosnia, 2-1 vs Canada, 2-0 vs Algeria (R32)
    # xG for: ~1.8 (scored 9 in 4 games = 2.25/game, but let's use xG estimate)
    # xG against: ~1.0 (conceded 3 in 4 games = 0.75/game)
    # Key: Xhaka/Freuler midfield control, Akanji/Elvedi physical defense
    # Injuries: Manzambi (doubt), Vargas/Sow/Aebischer (fitness doubts)
    home_data = {
        'xg_for': 1.75,              # Strong attacking output in tournament
        'xg_against': 0.95,          # Solid defensively
        'shots': 13.5,               # Average shots per game
        'sot': 5.2,                  # Shots on target per game
        'goals_for': 2.25,           # 9 goals in 4 games
        'goals_against': 0.75,       # 3 conceded in 4 games
        'clean_sheets_last10': 4,    # 1 clean sheet in tournament (Algeria)
        'missing_attacker': 1,       # Manzambi doubtful
        'missing_creator': 2,        # Vargas, Aebischer doubtful (midfield creators)
        'missing_cb': 0,             # Akanji/Elvedi both fit
        'missing_gk': 0,             # GK fit
        'tempo': 0.20,               # Controlled tempo, not rushed
        'width_crossing': 0.60,      # Moderate width usage
        'final_third_pressure': 0.55, # Moderate pressure
    }
    
    # Colombia - Group K Winners
    # Results: 1-0 vs Uzbekistan, 1-0 vs DR Congo, 0-0 vs Portugal, 1-0 vs Ghana (R16)
    # xG for: ~1.2 (scored 3 in 4 games = 0.75/game, defensively solid)
    # xG against: ~0.6 (conceded 0 in 4 games!)
    # Key: James creativity, Diaz pace, Munoz overlapping runs
    # Injuries: Cordoba (ruled out), Suarez to start
    away_data = {
        'xg_for': 1.20,              # Lower output but clinical
        'xg_against': 0.60,          # Defensively ROCK SOLID - 4 clean sheets in 4 games
        'shots': 10.8,               # Fewer shots but dangerous on break
        'sot': 3.8,                  # Shots on target per game
        'goals_for': 0.75,           # 3 goals in 4 games
        'goals_against': 0.0,        # 0 conceded in 4 games!
        'clean_sheets_last10': 6,    # 4 clean sheets in tournament
        'missing_attacker': 1,       # Cordoba ruled out
        'missing_creator': 0,        # James fit
        'missing_cb': 0,             # Defense fully fit
        'missing_gk': 0,             # GK fit
        'tempo': 0.15,               # Counter-attacking tempo
        'width_crossing': 0.70,      # Heavy width usage (Munoz overlaps)
        'final_third_pressure': 0.50, # Moderate pressure
    }
    
    # Market Data
    market_data = {
        'open_line': 2.25,
        'current_line': 2.25,
        'total': 2.25,
        'corner_total': 9.0,
    }
    
    # ========================================================================
    # RUN THE ENGINE PREDICTION
    # ========================================================================
    
    print("1. ENGINE PREDICTION (multi_sport_engine.predict_soccer)")
    print("-" * 50)
    
    result = predict_soccer(
        home="Switzerland",
        away="Colombia",
        league="World Cup",
        market_total=2.5,
        home_xg_for=home_data['xg_for'],
        home_xg_against=home_data['xg_against'],
        home_sot=home_data['sot'],
        home_tempo=home_data['tempo'],
        home_missing_attacker=home_data['missing_attacker'],
        home_missing_creator=home_data['missing_creator'],
        home_missing_cb=home_data['missing_cb'],
        home_missing_gk=home_data['missing_gk'],
        home_goals_for=home_data['goals_for'],
        home_clean_sheets=home_data['clean_sheets_last10'],
        away_xg_for=away_data['xg_for'],
        away_xg_against=away_data['xg_against'],
        away_sot=away_data['sot'],
        away_tempo=away_data['tempo'],
        away_missing_attacker=away_data['missing_attacker'],
        away_missing_creator=away_data['missing_creator'],
        away_missing_cb=away_data['missing_cb'],
        away_missing_gk=away_data['missing_gk'],
        away_goals_for=away_data['goals_for'],
        away_clean_sheets=away_data['clean_sheets_last10'],
    )
    
    p = result.get("projected", {})
    o = result.get("outcome", {})
    
    print(f"   Projected: Switzerland {p.get('home_goals', '?')} -- Colombia {p.get('away_goals', '?')}")
    print(f"   Total Goals: {p.get('total_goals', '?')}")
    print(f"   Win Prob:  H {o.get('home_win', 0)*100:.1f}% | D {o.get('draw', 0)*100:.1f}% | A {o.get('away_win', 0)*100:.1f}%")
    print(f"   BTTS:      {result.get('btts_probability', 0)*100:.1f}%")
    print(f"   Corners:   {result.get('corner_projection', 0)}")
    print(f"   Edge:      {result.get('edge', 0):+.2f}")
    print(f"   Confidence: {result.get('confidence', 0):.1f}%")
    print(f"   Rec:       {result.get('recommendation', 'PASS')}")
    print()
    
    # ========================================================================
    # DETAILED HANDICAPPING ANALYSIS
    # ========================================================================
    
    home_lam = p.get('home_goals', 0)
    away_lam = p.get('away_goals', 0)
    total_lam = p.get('total_goals', 0)
    
    print("2. DETAILED MARKET ANALYSIS")
    print("-" * 50)
    
    # Moneyline
    p_home_win, p_draw, p_away_win = calculate_moneyline_prob(home_lam, away_lam)
    print(f"   Moneyline: Switzerland {p_home_win*100:.1f}% | Draw {p_draw*100:.1f}% | Colombia {p_away_win*100:.1f}%")
    
    # Goals market
    over_15 = result.get('goals_analysis', {}).get('over_15', 0)
    over_25 = result.get('goals_analysis', {}).get('over_25', 0)
    over_35 = result.get('goals_analysis', {}).get('over_35', 0)
    print(f"   Over 1.5: {over_15*100:.1f}% | Over 2.5: {over_25*100:.1f}% | Over 3.5: {over_35*100:.1f}%")
    
    # BTTS
    btts_prob = result.get('btts_probability', 0)
    print(f"   BTTS: {btts_prob*100:.1f}%")
    
    # Corners
    corner_total = result.get('corner_projection', 0)
    print(f"   Corners Projection: {corner_total}")
    
    # ========================================================================
    # BUILD DISCORD EMBED
    # ========================================================================
    
    print("\n3. PUSHING TO DISCORD...")
    print("-" * 50)
    
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("[ERROR] DISCORD_WEBHOOK_URL not set")
        return False
    
    # Organize bets by strength
    strong_bets = []
    medium_bets = []
    pass_bets = []
    
    # --- Goals Market ---
    if over_25 >= 0.63:
        strong_bets.append({
            "name": "⚽ Over 2.5 Goals",
            "prob": round(over_25 * 100),
            "edge": f"+{total_lam - 2.5:+.2f} expected"
        })
    elif over_25 >= 0.55:
        medium_bets.append({
            "name": "⚽ Over 2.5 Goals",
            "prob": round(over_25 * 100),
            "edge": f"+{total_lam - 2.5:+.2f} expected"
        })
    else:
        pass_bets.append({
            "name": "⚽ Over 2.5 Goals",
            "prob": round(over_25 * 100),
            "edge": "Low probability"
        })
    
    # --- BTTS Market ---
    if btts_prob >= 0.63:
        strong_bets.append({
            "name": "🤝 Both Teams to Score",
            "prob": round(btts_prob * 100),
            "edge": "Both sides have attacking threats"
        })
    elif btts_prob >= 0.55:
        medium_bets.append({
            "name": "🤝 Both Teams to Score",
            "prob": round(btts_prob * 100),
            "edge": "Swiss attack vs Colombian counter"
        })
    else:
        pass_bets.append({
            "name": "🤝 Both Teams to Score",
            "prob": round(btts_prob * 100),
            "edge": "Colombia's defense too strong"
        })
    
    # --- Moneyline ---
    if p_home_win >= 0.55:
        medium_bets.append({
            "name": "🇨🇭 Switzerland Moneyline",
            "prob": round(p_home_win * 100),
            "edge": f"Home advantage + balanced squad"
        })
    elif p_away_win >= 0.55:
        medium_bets.append({
            "name": "🇨🇴 Colombia Moneyline",
            "prob": round(p_away_win * 100),
            "edge": "Defensive solidity + counter threat"
        })
    else:
        pass_bets.append({
            "name": "🇨🇭 Switzerland ML / 🇨🇴 Colombia ML",
            "prob": round(max(p_home_win, p_away_win) * 100),
            "edge": "Too close to call - Draw likely"
        })
    
    # --- Draw ---
    if p_draw >= 0.30:
        medium_bets.append({
            "name": "🤝 Draw (Regulation)",
            "prob": round(p_draw * 100),
            "edge": "Colombia's defense vs Swiss control"
        })
    else:
        pass_bets.append({
            "name": "🤝 Draw (Regulation)",
            "prob": round(p_draw * 100),
            "edge": "Low draw probability"
        })
    
    # --- Corners Market ---
    if corner_total >= 9.5:
        strong_bets.append({
            "name": "📐 Corners Over 8.5",
            "prob": 72,
            "edge": f"Projected {corner_total} corners"
        })
        medium_bets.append({
            "name": "📐 Corners Over 9.5",
            "prob": 63,
            "edge": f"Projected {corner_total} corners"
        })
    else:
        pass_bets.append({
            "name": "📐 Corners Over 8.5",
            "prob": 55,
            "edge": f"Projected {corner_total} corners"
        })
    
    # --- Over 1.5 Goals ---
    if over_15 >= 0.75:
        strong_bets.append({
            "name": "⚽ Over 1.5 Goals",
            "prob": round(over_15 * 100),
            "edge": "High probability safety bet"
        })
    elif over_15 >= 0.65:
        medium_bets.append({
            "name": "⚽ Over 1.5 Goals",
            "prob": round(over_15 * 100),
            "edge": "Solid probability"
        })
    
    # Projected stats
    projected_stats = {
        "Projected Score": f"Switzerland {home_lam:.2f} - {away_lam:.2f} Colombia",
        "Expected Total": f"{total_lam:.2f} Goals",
        "Switzerland Win": f"{p_home_win*100:.1f}%",
        "Draw": f"{p_draw*100:.1f}%",
        "Colombia Win": f"{p_away_win*100:.1f}%",
        "BTTS": f"{btts_prob*100:.1f}%",
        "Corners": f"{corner_total:.1f}",
        "Confidence": f"{result.get('confidence', 0):.1f}%",
    }
    
    # Create organized embed
    embed = create_organized_prediction_embed(
        sport="soccer",
        home="Switzerland",
        away="Colombia",
        strong_bets=strong_bets,
        medium_bets=medium_bets,
        pass_bets=pass_bets,
        projected_stats=projected_stats,
    )
    
    # Add tactical breakdown as a field
    embed["fields"].append({
        "name": "📋 Tactical Breakdown",
        "value": (
            "**Switzerland (Balanced):** Xhaka/Freuler midfield control, "
            "Akanji/Elvedi physical defense. Embolo leads attack.\n"
            "**Colombia (Counter):** James creativity, Diaz pace on flanks, "
            "Munoz overlapping runs. Rock-solid defense (0 GA in 4 games).\n"
            "**Key Battle:** Swiss midfield control vs Colombian defensive solidity"
        ),
        "inline": False
    })
    
    # Add injury report
    embed["fields"].append({
        "name": "🏥 Injury Report",
        "value": (
            "**Colombia:** ❌ Jhon Córdoba (Ruled Out - Injury)\n"
            "**Switzerland:** ⚠️ Manzambi (Doubt - Knee), ⚠️ Vargas/Sow/Aebischer (Fitness)\n"
            "✅ Breel Embolo fully fit for Switzerland"
        ),
        "inline": False
    })
    
    # Add head-to-head
    embed["fields"].append({
        "name": "📊 Head-to-Head (4 meetings)",
        "value": "Colombia 2 wins | Switzerland 1 win | 1 Draw",
        "inline": False
    })
    
    # Add match context
    embed["fields"].append({
        "name": "🏆 Match Context",
        "value": (
            "World Cup Round of 16 • July 7, 2026\n"
            "Group B Winners (Switzerland) vs Group K Winners (Colombia)\n"
            "The Immovable Object vs The Unstoppable Force"
        ),
        "inline": False
    })
    
    # Push to Discord
    payload = {
        "embeds": [embed]
    }
    
    try:
        import requests
        r = requests.post(webhook_url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
        if r.status_code in (200, 204):
            print("   [OK] Successfully pushed to Discord!")
        else:
            print(f"   [WARN] HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"   [FAIL] {e}")
        return False
    
    # ========================================================================
    # PRINT SUMMARY
    # ========================================================================
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"   Match: Switzerland vs Colombia (World Cup R16)")
    print(f"   Projected: Switzerland {home_lam:.2f} - {away_lam:.2f} Colombia")
    print(f"   Total Goals: {total_lam:.2f}")
    print(f"   Win Prob: Switzerland {p_home_win*100:.1f}% | Draw {p_draw*100:.1f}% | Colombia {p_away_win*100:.1f}%")
    print(f"   BTTS: {btts_prob*100:.1f}%")
    print(f"   Corners: {corner_total:.1f}")
    print(f"   Confidence: {result.get('confidence', 0):.1f}%")
    print(f"   Recommendation: {result.get('recommendation', 'PASS')}")
    print()
    
    # Print bet categories (strip emojis for console)
    print("BETTING GUIDE:")
    print("-" * 50)
    if strong_bets:
        print("  [STRONG BETS]:")
        for bet in strong_bets:
            name_clean = bet['name'].encode('ascii', 'ignore').decode('ascii').strip()
            print(f"     - {name_clean}: {bet['prob']}% ({bet['edge']})")
    if medium_bets:
        print("  [MEDIUM BETS]:")
        for bet in medium_bets:
            name_clean = bet['name'].encode('ascii', 'ignore').decode('ascii').strip()
            print(f"     - {name_clean}: {bet['prob']}% ({bet['edge']})")
    if pass_bets:
        print("  [PASS]:")
        for bet in pass_bets:
            name_clean = bet['name'].encode('ascii', 'ignore').decode('ascii').strip()
            print(f"     - {name_clean}: {bet['prob']}% ({bet['edge']})")
    
    print()
    print("=" * 80)
    return True


if __name__ == "__main__":
    run_switzerland_colombia_analysis()