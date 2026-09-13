#!/usr/bin/env python
"""
Australia Select vs Netherlands - June 22, 2026
===============================================
International Friendlies Basketball Analysis
Location: Hangzhou, Zhejiang, China (Neutral Floor)

Key Context:
- Australia on back-to-back fatigue (lost 91-81 to China yesterday)
- Australia fielding emerging "Select" team, not primary Olympic roster
- Netherlands relying on half-court FIBA execution
- FIBA officiating crews notoriously strict on defensive cylinder
"""

import requests
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()


def analyze_australia_select_vs_netherlands():
    """
    Comprehensive analysis of Australia Select vs Netherlands
    focusing on fatigue angles, officiating tendencies, and style mismatches.
    """
    
    # Match Context
    match_info = {
        "date": "June 22, 2026",
        "location": "Hangzhou, Zhejiang, China",
        "floor": "Neutral",
        "competition": "International Friendlies",
        "australia_team": "Australia Select (emerging talent)",
        "australia_coach": "Luke Brennan (SEM Phoenix)",
        "netherlands_team": "Netherlands (Primary FIBA Roster)",
    }
    
    # Australia Select Context
    australia_context = {
        "key_players": {
            "Emmett Adair": "Primary offensive engine (18 pts yesterday)",
            "Reyne Smith": "Captain, perimeter scoring (14 pts yesterday)",
            "Jacob Holt": "Frontcourt battle player"
        },
        "style": "High defensive physicality → transition pace offense",
        "roster_depth": "Biwali Bayles, Sam Brown, Kuai Deng, Daniel Foster, Ben Griscti, William Johnston, Harry Rouhliadeff",
        "fatigue_status": "CRITICAL - Back-to-back with 24-hour turnaround",
        "yesterday_result": "Lost 91-81 to China (heavy minutes, physical game)",
        "first_quarter_concern": "Coach explicitly noted 'poor start' yesterday"
    }
    
    # Netherlands Context
    netherlands_context = {
        "style": "Classic European FIBA system",
        "approach": "Half-court execution, high pick-and-roll continuity",
        "defensive_strategy": "Exploit over-aggressive closeouts to neutralize Australia pace",
        "tempo_control": "Attempt to keep game in half-court to neutralize Australia athleticism",
        "rest_advantage": "Fresh team (assumed normal rest)"
    }
    
    # Officiating Analysis
    officiating = {
        "crew_type": "FIBA mixed-region (Asia)",
        "tendencies": "Notoriously strict on defensive cylinder and transition take fouls",
        "impact_on_australia": "Aggressive physical defense = early foul trouble + early bonus FT for Netherlands",
        "key_angle": "Tight FIBA whistle pushes 1Q and First Half totals OVER"
    }
    
    # Current Market Lines (as provided)
    market_lines = {
        "spread": {
            "line": "Australia -7.5",
            "moneyline_odds": 1.65,
            "implied_win_prob": 0.60
        },
        "1q_line": "Australia -2.5 (approx)",
    }
    
    # Sharp Consensus Analysis
    sharp_angles = {
        "strongest_angle": {
            "pick": "Netherlands +2.5 (1Q)",
            "confidence_pct": 78,
            "reasoning": [
                "Australia's documented 'poor starts' from yesterday",
                "Massive fatigue from 24-hour turnaround after heavy game",
                "Inexperienced 'Select' roster without rhythm",
                "Neutral floor removes home court advantage",
                "FIBA tight whistle = early foul trouble for Australia defense"
            ],
            "edge": "Sharp professionals targeting Australia's first-quarter vulnerability"
        },
        "secondary_angles": [
            {
                "pick": "Netherlands +3 (Full Game Spread)",
                "confidence_pct": 65,
                "reasoning": "Professional money skeptical of -7.5 spread in this spot",
                "edge": "Risk/reward attractive for Netherlands with points"
            },
            {
                "pick": "1Q Over (or First Half Over) based on FIBA whistles",
                "confidence_pct": 72,
                "reasoning": [
                    "Australia's aggressive defense will be called strictly by FIBA",
                    "Early fouls = bonus FTs for Netherlands = more points in 1Q",
                    "Expected tight whistle on transition fouls"
                ],
                "edge": "Officiating tendency creates automatic scoring increase"
            },
            {
                "pick": "Under 160 Total (Full Game)",
                "confidence_pct": 64,
                "reasoning": [
                    "Fatigue forces game into half-court grind in 2nd half",
                    "Netherlands' possession-heavy style slows tempo",
                    "Legs tire in 4th quarter = reduced scoring pace",
                    "Australia can't maintain uptempo pace with fresh legs"
                ],
                "edge": "Style clash + fatigue creates lower-scoring 2nd half"
            }
        ]
    }
    
    # Betting Recommendations
    recommendations = {
        "strong_bets": [
            {
                "name": "💪 Netherlands +2.5 (1Q)",
                "confidence": 78,
                "probability": "78%",
                "edge": "Australia's fatigue + poor starts documented + FIBA whistle",
                "stake": "STRONG BET - Maximum value",
                "explanation": "Sharpest angle on the board. Australia's back-to-back legs will show in first 12 minutes."
            },
            {
                "name": "💪 1Q/First Half Over (specific line TBD)",
                "confidence": 72,
                "probability": "72%",
                "edge": "FIBA officiating = tight whistle on Australia's physical defense = bonus FTs",
                "stake": "STRONG BET",
                "explanation": "Coach Brennan noted Australia 'ramped up physicality' yesterday. FIBA will call this strictly → early fouls → free throws."
            },
            {
                "name": "🟢 Netherlands +3 (Full Game)",
                "confidence": 65,
                "probability": "65%",
                "edge": "Sharp consensus skeptical of -7.5; inexperienced Select roster; fatigue compounding",
                "stake": "BET",
                "explanation": "Professional money heavily skeptical. Australia -7.5 is too many possessions in this spot."
            }
        ],
        "secondary_bets": [
            {
                "name": "🟡 Under 160 Total",
                "confidence": 64,
                "probability": "64%",
                "edge": "Fatigue → half-court grind → reduced 2nd half pace → legs tire 4Q",
                "stake": "LEAN/MEDIUM",
                "explanation": "Australia can't maintain uptempo pace; Netherlands controls tempo. Game grinds in 2H."
            }
        ],
        "fade_bets": [
            {
                "name": "❌ Australia -7.5 (Spread)",
                "confidence": 25,
                "probability": "25%",
                "edge": "Laying 7.5 vs fresh, methodical European team is excessive",
                "explanation": "Sharp consensus fading Australia hard. Too many possessions."
            },
            {
                "name": "❌ Australia -2.5 (1Q)",
                "confidence": 30,
                "probability": "30%",
                "edge": "Back-to-back fatigue + poor starts = early hole",
                "explanation": "Australia's documented struggles out of the gate will show up immediately."
            }
        ]
    }
    
    return {
        "match_info": match_info,
        "australia_context": australia_context,
        "netherlands_context": netherlands_context,
        "officiating": officiating,
        "market_lines": market_lines,
        "sharp_angles": sharp_angles,
        "recommendations": recommendations
    }


def push_analysis_to_discord():
    """Push Australia Select vs Netherlands analysis to Discord with organized bets"""
    
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    
    if not webhook_url:
        print("❌ DISCORD_WEBHOOK_URL not set in environment")
        return False
    
    analysis = analyze_australia_select_vs_netherlands()
    
    # Build organized embed with strong bets first
    fields = []
    
    # MATCH OVERVIEW
    match_context = f"""
**Date:** {analysis['match_info']['date']}
**Location:** {analysis['match_info']['location']} (Neutral Floor)
**Competition:** {analysis['match_info']['competition']}

**Australia Select** (Luke Brennan, SEM Phoenix)
🔴 **CRITICAL CONTEXT:** Back-to-back fatigue (lost 91-81 to China yesterday, 24-hour turnaround)
• Key Players: Emmett Adair (18 pts), Reyne Smith - Captain (14 pts), Jacob Holt
• Style: High defensive physicality → transition pace
• Concern: Coach noted "poor start" yesterday before rally

**Netherlands** (Primary FIBA Roster)
🟢 Fresh team, classic European half-court system
• Strategy: Pick-and-roll continuity, exploit overaggressive closeouts
• Goal: Control tempo, neutralize Australia's athleticism
    """
    fields.append({
        "name": "🏀 AUSTRALIA SELECT vs NETHERLANDS - June 22, 2026",
        "value": match_context.strip(),
        "inline": False
    })
    
    # STRONG BETS
    strong_text = ""
    for bet in analysis["recommendations"]["strong_bets"]:
        strong_text += f"\n🟢 **{bet['name']}** | {bet['confidence']}% Confidence\n"
        strong_text += f"   Edge: {bet['edge']}\n"
        strong_text += f"   └─ {bet['explanation']}\n"
    
    fields.append({
        "name": "💪 STRONG BETS (Sharp Consensus Angles)",
        "value": strong_text.strip(),
        "inline": False
    })
    
    # SECONDARY BETS
    secondary_text = ""
    for bet in analysis["recommendations"]["secondary_bets"]:
        secondary_text += f"\n🟡 **{bet['name']}** | {bet['confidence']}% Confidence\n"
        secondary_text += f"   Edge: {bet['edge']}\n"
        secondary_text += f"   └─ {bet['explanation']}\n"
    
    fields.append({
        "name": "⚠️  SECONDARY BETS (Medium Strength)",
        "value": secondary_text.strip(),
        "inline": False
    })
    
    # FADES
    fade_text = ""
    for bet in analysis["recommendations"]["fade_bets"]:
        fade_text += f"\n🔴 **{bet['name']}** | {bet['confidence']}% Win Probability\n"
        fade_text += f"   └─ {bet['explanation']}\n"
    
    fields.append({
        "name": "❌ FADES (Do NOT Bet These)",
        "value": fade_text.strip(),
        "inline": False
    })
    
    # KEY ANALYTICAL ANGLES
    angles_text = """
🔑 **#1 - Back-to-Back Fatigue (1Q Vulnerability)**
Australia is playing on direct back-to-back with only 24 hours rest after losing 91-81 to China in a highly physical game. Coach Brennan explicitly noted a "poor start" yesterday. Heavy legs + short turnaround = 1Q vulnerability.

🔑 **#2 - FIBA Officiating (Tight Whistle)**
FIBA Asia crews are notoriously strict on defensive cylinder and transition fouls. Australia "ramped up physicality on defense" to get back into yesterday's game. Expect tight whistle → early foul trouble → bonus free throws for Netherlands in 1Q.

🔑 **#3 - Style Mismatch (Pace vs Grind)**
Australia wants uptempo transition pace. Netherlands wants half-court pick-and-roll control. Fatigue + fast pace = Australia can't maintain. Second half becomes a grind.

🔑 **#4 - Roster Experience (Select vs Primary)**
Australia fielding emerging talent "Select" team (not Olympic/World Cup Boomers). Neutral floor removes home court. Experience gap matters in tight spots.
    """
    fields.append({
        "name": "🔍 Key Analytical Angles",
        "value": angles_text.strip(),
        "inline": False
    })
    
    # MARKET CONSENSUS
    market_text = """
**Current Lines:**
• Australia -7.5 (Moneyline ~1.65, 60% implied win prob)
• 1Q: Australia -2.5 (approx)

**Sharp Consensus:**
Professional money is HEAVILY skeptical of Australia -7.5 in this spot. The combination of:
1. Inexperienced Select roster
2. Neutral floor (no home advantage)
3. Back-to-back fatigue (zero rest advantage)
4. Fresh Netherlands FIBA team

...makes Australia an unattractive favorite at 7.5 points.
    """
    fields.append({
        "name": "📊 Market Consensus",
        "value": market_text.strip(),
        "inline": False
    })
    
    # Create embed
    embed = {
        "title": "🏀 AUSTRALIA SELECT vs NETHERLANDS SHARP ANALYSIS",
        "description": "International Friendlies • Hangzhou, China\n**BACK-TO-BACK FATIGUE + FIBA WHISTLE = STRONG BETS FOR NETHERLANDS**",
        "color": 3066993,  # Green for strong bets
        "fields": fields,
        "footer": {
            "text": "MultiSportPredict • Sharp Consensus Analysis | June 22, 2026"
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
            print("✅ Analysis successfully pushed to Discord!")
            print(f"\n📊 STRONG BETS IDENTIFIED:")
            for bet in analysis["recommendations"]["strong_bets"]:
                print(f"   • {bet['name']} ({bet['confidence']}% confidence)")
            return True
        else:
            print(f"❌ Discord error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Request error: {e}")
        return False


def print_analysis_to_console():
    """Print detailed analysis to console for reference"""
    analysis = analyze_australia_select_vs_netherlands()
    
    print("\n" + "="*80)
    print("🏀 AUSTRALIA SELECT vs NETHERLANDS - SHARP ANALYSIS")
    print("="*80)
    
    print(f"\n📅 {analysis['match_info']['date']} | {analysis['match_info']['location']}")
    print(f"🏟️  {analysis['match_info']['competition']}")
    
    print("\n" + "-"*80)
    print("⚠️  CRITICAL CONTEXT: BACK-TO-BACK FATIGUE")
    print("-"*80)
    print("Australia lost 91-81 to China YESTERDAY after heavy minutes.")
    print("24-hour turnaround = massive fatigue spot.")
    print("Coach noted 'poor start' yesterday before rally.")
    
    print("\n" + "-"*80)
    print("💪 STRONG BETS (Sharp Consensus)")
    print("-"*80)
    for i, bet in enumerate(analysis["recommendations"]["strong_bets"], 1):
        print(f"\n#{i} {bet['name']}")
        print(f"    Confidence: {bet['confidence']}%")
        print(f"    Edge: {bet['edge']}")
        print(f"    Explanation: {bet['explanation']}")
    
    print("\n" + "-"*80)
    print("🔑 KEY ANALYTICAL ANGLES")
    print("-"*80)
    print("1. Back-to-Back Fatigue: Australia's heavy legs from yesterday's loss")
    print("2. FIBA Officiating: Strict whistle on defensive cylinder = early fouls")
    print("3. Style Mismatch: Australia pace vs Netherlands half-court grind")
    print("4. Roster Experience: Select team vs primary FIBA roster on neutral floor")
    
    print("\n" + "-"*80)
    print("❌ FADES (Do NOT Bet)")
    print("-"*80)
    for bet in analysis["recommendations"]["fade_bets"]:
        print(f"\n• {bet['name']}")
        print(f"    Explanation: {bet['explanation']}")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    print("🚀 Running Australia Select vs Netherlands Analysis...")
    
    # Print to console
    print_analysis_to_console()
    
    # Push to Discord
    print("\n\n📤 Pushing strong bets to Discord...")
    if push_analysis_to_discord():
        print("\n✅ All strong bets successfully pushed to Discord!")
    else:
        print("\n⚠️  Failed to push to Discord. Check webhook URL and connection.")
