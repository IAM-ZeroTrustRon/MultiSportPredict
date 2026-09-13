#!/usr/bin/env python
"""Push Netherlands vs Sweden prediction to Discord with organized format"""

import requests
import os
from scipy.stats import poisson
from dotenv import load_dotenv

load_dotenv()

def calculate_btts_probability(home_goals: float, away_goals: float) -> float:
    """Calculate Both Teams to Score probability."""
    home_scores_zero = poisson.pmf(0, home_goals)
    away_scores_zero = poisson.pmf(0, away_goals)
    both_score_zero = home_scores_zero * away_scores_zero
    btts_prob = 1 - (home_scores_zero + away_scores_zero - both_score_zero)
    return max(0.0, min(1.0, btts_prob))

def push_organized_prediction_to_discord():
    """Push organized prediction with Strong/Medium/Pass bets"""
    
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    
    if not webhook_url:
        print("❌ DISCORD_WEBHOOK_URL not set")
        return False
    
    # Calculate probabilities
    btts_prob = calculate_btts_probability(2.16, 1.77)  # Netherlands 2.16, Sweden 1.77
    
    # Organize bets by strength
    strong_bets = [
        {
            "name": "💰 Over 2.5 Goals",
            "prob": 72,
            "edge": "+1.4 goals"
        },
        {
            "name": "🔶 Corners Over 8.5",
            "prob": 76,
            "edge": "High volume expected"
        },
        {
            "name": "🤝 Both Teams Score",
            "prob": int(btts_prob * 100),
            "edge": "Both offensive"
        }
    ]
    
    medium_bets = [
        {
            "name": "🔸 Corners Over 9.5",
            "prob": 65,
            "edge": "Medium-high volume"
        }
    ]
    
    pass_bets = [
        {
            "name": "❌ Netherlands Moneyline",
            "prob": 47,
            "edge": "Too close to 50/50"
        },
        {
            "name": "❌ Corners Over 10.5",
            "prob": 53,
            "edge": "Slight edge only"
        }
    ]
    
    projected_stats = {
        "Projected Score": "Netherlands 2.2 - Sweden 1.8",
        "Expected Total": "3.9 Goals",
        "Netherlands Win": "46.5%",
        "Draw": "21.2%",
        "Sweden Win": "32.2%"
    }
    
    # Build the organized embed
    fields = []
    
    # Strong Bets
    strong_text = ""
    for bet in strong_bets:
        strong_text += f"🟢 {bet['name']}: **{bet['prob']}%**\n   └─ {bet['edge']}\n"
    fields.append({
        "name": "💪 STRONG BETS (≥65% Confidence)",
        "value": strong_text.strip(),
        "inline": False
    })
    
    # Medium Bets
    medium_text = ""
    for bet in medium_bets:
        medium_text += f"🟡 {bet['name']}: **{bet['prob']}%**\n   └─ {bet['edge']}\n"
    fields.append({
        "name": "⚠️  MEDIUM BETS (55-65% Confidence)",
        "value": medium_text.strip(),
        "inline": False
    })
    
    # Pass Bets
    pass_text = ""
    for bet in pass_bets:
        pass_text += f"🔴 {bet['name']}: {bet['prob']}%\n   └─ {bet['edge']}\n"
    fields.append({
        "name": "❌ PASS (<55% Confidence)",
        "value": pass_text.strip(),
        "inline": False
    })
    
    # Stats
    stats_text = ""
    for stat_name, stat_value in projected_stats.items():
        stats_text += f"• {stat_name}: {stat_value}\n"
    fields.append({
        "name": "📊 Match Statistics",
        "value": stats_text.strip(),
        "inline": False
    })
    
    # Create embed
    embed = {
        "title": "⚽ NETHERLANDS vs SWEDEN",
        "description": "**Soccer Prediction** - World Cup\n🏟️ Multi-Market Analysis",
        "color": 3066993,  # Green for strong bets
        "fields": fields,
        "footer": {
            "text": "MultiSportPredict • Smart Betting Guide"
        }
    }
    
    payload = {"embeds": [embed]}
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        
        if response.status_code in (200, 204):
            return True
        else:
            print(f"❌ Discord error: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Request error: {e}")
        return False

if __name__ == "__main__":
    if push_organized_prediction_to_discord():
        print("✅ Organized prediction successfully pushed to Discord!")
        print("\n📊 BET BREAKDOWN:")
        print("   💪 STRONG BETS (Recommended):")
        print("      • Over 2.5 Goals: 72%")
        print("      • Corners Over 8.5: 76%")
        print("      • BTTS: 73%")
        print("\n   ⚠️  MEDIUM BETS (Optional):")
        print("      • Corners Over 9.5: 65%")
        print("\n   ❌ PASS (Skip):")
        print("      • Moneyline: 47%")
        print("      • Corners Over 10.5: 53%")
    else:
        print("❌ Failed to push prediction to Discord")
