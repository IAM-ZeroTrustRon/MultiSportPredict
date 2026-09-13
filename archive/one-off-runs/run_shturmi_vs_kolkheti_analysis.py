#!/usr/bin/env python
"""
SFC Shturmi vs FC Kolkheti Poti - June 22, 2026
Georgian Erovnuli Liga 2 | Defensive Grinder Analysis
Focus: Totals, Moneylines, BTTS, Corners
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()


def analyze_match():
    """Analysis of Shturmi vs Kolkheti Poti"""
    
    # Head-to-Head Data
    h2h = {
        "may_2": {"result": "Shturmi 1-0", "style": "Defensive grind, 2H goal"},
        "march_1": {"result": "1-1 Draw", "style": "Tight, balanced"},
    }
    
    # Model Projections
    model = {
        "kolkheti_win_prob": 0.37,
        "shturmi_win_prob": 0.30,
        "draw_prob": 0.33,
        "under_2_5_prob": 0.74,
        "btts_no_prob": 0.68,
        "most_likely_scores": ["1-0 (14%)", "1-1 (13%)", "0-0 (12%)"]
    }
    
    # Strong Bets
    bets = [
        {
            "name": "Under 2.5 Goals",
            "odds": 1.75,
            "confidence": 76,
            "edge": "74% model probability. Defensive grind pattern confirmed in both H2H meetings."
        },
        {
            "name": "BTTS No",
            "odds": 2.03,
            "confidence": 68,
            "edge": "1-0 most likely scoreline (14%). Single-team scoring fits defensive profile."
        },
        {
            "name": "Draw (Any Score)",
            "odds": 4.33,
            "confidence": 65,
            "edge": "33% model probability vs 4.33 implied odds. Previous match at same venue ended 1-1."
        }
    ]
    
    return h2h, model, bets


def push_to_discord():
    """Push analysis to Discord"""
    
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("ERROR: DISCORD_WEBHOOK_URL not set")
        return False
    
    h2h, model, bets = analyze_match()
    
    # Build fields
    fields = []
    
    # Overview
    fields.append({
        "name": "SHTURMI vs KOLKHETI POTI - June 22, 2026",
        "value": "Georgian Erovnuli Liga 2 | 10:00 AM EDT\nVenue: Fazizi Stadium (Kolkheti Home)",
        "inline": False
    })
    
    # Strong Bets
    strong_text = ""
    for bet in bets:
        strong_text += f"\n**{bet['name']}** @ {bet['odds']} | {bet['confidence']}%\n{bet['edge']}\n"
    fields.append({"name": "STRONG BETS", "value": strong_text.strip(), "inline": False})
    
    # Model Data
    model_text = f"**Win Probs:** Kolkheti 37% | Shturmi 30% | Draw 33%\n**Under 2.5:** 74% Probability\n**BTTS No:** 68% Probability\n**Most Likely:** 1-0 (14%), 1-1 (13%), 0-0 (12%)"
    fields.append({"name": "MODEL PROJECTIONS", "value": model_text, "inline": False})
    
    # H2H
    h2h_text = "**May 2:** Shturmi 1-0 (defensive grind, 2H goal)\n**March 1:** 1-1 Draw (tight, balanced)"
    fields.append({"name": "HEAD-TO-HEAD", "value": h2h_text, "inline": False})
    
    # Create embed
    embed = {
        "title": "SHTURMI vs KOLKHETI POTI",
        "description": "Defensive Grinder Analysis | UNDER 2.5 STRONG",
        "color": 3066993,
        "fields": fields,
        "footer": {"text": "MultiSportPredict | Sharp Consensus"}
    }
    
    payload = {"embeds": [embed]}
    
    try:
        response = requests.post(webhook_url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
        if response.status_code in (200, 204):
            print("SUCCESS: Analysis pushed to Discord!")
            print("\nSTRONG BETS:")
            for bet in bets:
                print(f"  • {bet['name']} @ {bet['odds']} ({bet['confidence']}% confidence)")
            return True
        else:
            print(f"ERROR: {response.status_code}")
            return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def print_analysis():
    """Print to console"""
    h2h, model, bets = analyze_match()
    
    print("\n" + "="*70)
    print("SHTURMI vs KOLKHETI POTI - SHARP ANALYSIS")
    print("="*70)
    
    print("\nH2H PATTERN:")
    print("  • May 2: Shturmi 1-0 (Defensive grind)")
    print("  • March 1: 1-1 Draw (Tight match)")
    print("  → Both incredibly low-scoring defensive affairs")
    
    print("\nMODEL PROJECTIONS:")
    print(f"  • Kolkheti Win: 37%")
    print(f"  • Shturmi Win: 30%")
    print(f"  • Draw: 33%")
    print(f"  • Under 2.5 Goals: 74%")
    print(f"  • BTTS No: 68%")
    
    print("\nMOST LIKELY SCORELINES:")
    print("  1. 1-0 (14%)")
    print("  2. 1-1 (13%)")
    print("  3. 0-0 (12%)")
    
    print("\nSTRONG BETS:")
    for i, bet in enumerate(bets, 1):
        print(f"\n{i}. {bet['name']} @ {bet['odds']}")
        print(f"   Confidence: {bet['confidence']}%")
        print(f"   Edge: {bet['edge']}")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    print("Running Shturmi vs Kolkheti Analysis...")
    print_analysis()
    print("\nPushing to Discord...")
    push_to_discord()
