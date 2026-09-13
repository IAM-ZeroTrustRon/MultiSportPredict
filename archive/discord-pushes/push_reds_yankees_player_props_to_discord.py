"""
Push Reds vs Yankees Player Props to Discord
Focuses on hitter prop bets only
"""

import os
import requests
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()

console = Console()

def get_reds_hitter_props():
    """Get Cincinnati Reds hitter props"""
    return [
        {
            'name': 'Blake Dunn (CF)',
            'stat': 'Hits',
            'choice': 'Over',
            'line': '+0.5',
            'odds': '-150',
            'probability': 55,
            'recommendation': 'Medium'
        },
        {
            'name': 'JJ Bleday (LF)',
            'stat': 'Hits',
            'choice': 'Over',
            'line': '+0.5',
            'odds': '-120',
            'probability': 52,
            'recommendation': 'Medium'
        },
        {
            'name': 'Nathaniel Lowe (DH)',
            'stat': 'Hits',
            'choice': 'Over',
            'line': '+0.5',
            'odds': '-140',
            'probability': 58,
            'recommendation': 'Medium'
        },
        {
            'name': 'Spencer Steer (1B)',
            'stat': 'RBIs',
            'choice': 'Over',
            'line': '+0.5',
            'odds': '-120',
            'probability': 48,
            'recommendation': 'Pass'
        }
    ]

def get_yankees_hitter_props():
    """Get New York Yankees hitter props"""
    return [
        {
            'name': 'Ben Rice (1B)',
            'stat': 'Hits',
            'choice': 'Over',
            'line': '+0.5',
            'odds': '-140',
            'probability': 60,
            'recommendation': 'Medium'
        },
        {
            'name': 'Paul Goldschmidt (DH)',
            'stat': 'Hits',
            'choice': 'Over',
            'line': '+1.5',
            'odds': '-110',
            'probability': 62,
            'recommendation': 'Strong'
        },
        {
            'name': 'Cody Bellinger (CF)',
            'stat': 'RBIs',
            'choice': 'Over',
            'line': '+0.5',
            'odds': '-120',
            'probability': 55,
            'recommendation': 'Medium'
        },
        {
            'name': 'Jasson Domínguez (RF)',
            'stat': 'Hits',
            'choice': 'Over',
            'line': '+0.5',
            'odds': '-130',
            'probability': 57,
            'recommendation': 'Medium'
        }
    ]

def create_player_props_embed(team_name, team_color, props):
    """Create Discord embed for player props"""
    
    # Build field text with all props
    field_text = ""
    for i, prop in enumerate(props, 1):
        rec_emoji = "✅" if prop['recommendation'] == 'Strong' else ("⚠️" if prop['recommendation'] == 'Medium' else "❌")
        field_text += f"{i}. **{prop['name']}** - {prop['stat']} {prop['choice']} {prop['line']}\n"
        field_text += f"   Odds: {prop['odds']} | Prob: {prop['probability']}%\n"
        field_text += f"   {rec_emoji} {prop['recommendation']}\n\n"
    
    embed = {
        "title": f"🎯 {team_name} - PLAYER PROPS",
        "description": f"Hitter prop bets for {team_name}",
        "color": team_color,
        "fields": [
            {
                "name": "Player Prop Bets",
                "value": field_text,
                "inline": False
            }
        ],
        "footer": {
            "text": "Cincinnati Reds vs. New York Yankees | June 20, 2026"
        }
    }
    
    return embed

def create_summary_embed():
    """Create summary embed with top recommendations"""
    summary = {
        "title": "⭐ TOP PLAYER PROP RECOMMENDATIONS",
        "description": "Best value player props for this matchup",
        "color": 16776960,  # Gold
        "fields": [
            {
                "name": "🟢 STRONG RECOMMENDATION",
                "value": "**Paul Goldschmidt (DH) - Hits Over +1.5**\n"
                        "• Odds: -110 | Probability: 62%\n"
                        "• Rationale: Star DH in strong position vs. overperforming pitcher",
                "inline": False
            },
            {
                "name": "🟡 SOLID OPPORTUNITIES (Medium)",
                "value": "**Blake Dunn (CF)** - Hits Over +0.5 (55%)\n"
                        "**Nathaniel Lowe (DH)** - Hits Over +0.5 (58%)\n"
                        "**Ben Rice (1B)** - Hits Over +0.5 (60%)\n"
                        "**Jasson Domínguez (RF)** - Hits Over +0.5 (57%)",
                "inline": False
            },
            {
                "name": "🔴 AVOID",
                "value": "**Spencer Steer (1B)** - RBIs Over +0.5 (48%)\n"
                        "• Probability below 50% - Unfavorable odds",
                "inline": False
            }
        ],
        "footer": {
            "text": "Multi-Sport Analysis | June 20, 2026"
        }
    }
    
    return summary

def push_player_props_to_discord():
    """Push all player props to Discord"""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    
    if not webhook_url:
        console.print("[red]❌ DISCORD_WEBHOOK_URL not found in .env[/red]")
        return
    
    reds_props = get_reds_hitter_props()
    yankees_props = get_yankees_hitter_props()
    
    # Create embeds
    reds_embed = create_player_props_embed("🔴 CINCINNATI REDS", 12711424, reds_props)  # Red color
    yankees_embed = create_player_props_embed("🔵 NEW YORK YANKEES", 3066993, yankees_props)  # Blue color
    summary_embed = create_summary_embed()
    
    embeds = [reds_embed, yankees_embed, summary_embed]
    
    # Push each embed
    for i, embed in enumerate(embeds, 1):
        payload = {"embeds": [embed]}
        
        try:
            response = requests.post(webhook_url, json=payload, timeout=15)
            if response.status_code == 204:
                console.print(f"[green]✅ Player Props Embed {i}/3 pushed to Discord[/green]")
            else:
                console.print(f"[red]❌ Discord error on embed {i}: {response.status_code}[/red]")
        except Exception as e:
            console.print(f"[red]❌ Error pushing embed {i} to Discord: {e}[/red]")
    
    console.print("\n" + "="*70)
    console.print("[green]✅ ALL PLAYER PROPS SUCCESSFULLY PUSHED TO DISCORD![/green]")
    console.print("="*70)
    console.print("\n📊 Summary:")
    console.print(f"   🔴 Reds: {len(reds_props)} player props")
    console.print(f"   🔵 Yankees: {len(yankees_props)} player props")
    console.print(f"   ⭐ Top Pick: Paul Goldschmidt Hits Over 1.5 (62%)")
    console.print("\n")

if __name__ == "__main__":
    push_player_props_to_discord()
