#!/usr/bin/env python3
"""
Push the comprehensive July 2026 MultiSportPredict Record to Discord.
Posts a rich embed with the full month's performance summary across all sports.
"""
import json
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

try:
    import requests
except ImportError:
    print("ERROR: requests library not installed.")
    sys.exit(1)

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
if not WEBHOOK_URL or WEBHOOK_URL == "None":
    print("ERROR: DISCORD_WEBHOOK_URL not set in .env")
    sys.exit(1)

# ---------------------------------------------------------------------------
# COLOR CONSTANTS
# ---------------------------------------------------------------------------
COLOR_GREEN = 3066993
COLOR_BLUE = 10181046
COLOR_YELLOW = 16776960
COLOR_RED = 15158332
COLOR_PURPLE = 10181046
COLOR_GOLD = 16766720

SPORT_EMOJIS = {
    "Baseball": "⚾",
    "Tennis": "🎾",
    "Basketball": "🏀",
    "Soccer": "⚽",
}

def push_july_report():
    """Push July 2026 comprehensive report to Discord as rich embeds."""

    now = datetime.utcnow().isoformat() + "Z"

    # ================================================================
    # EMBED 1 — Executive Summary
    # ================================================================
    embed1 = {
        "title": "📊 MultiSportPredict — July 2026 Record",
        "description": (
            "**Comprehensive Monthly Performance Summary**\n"
            "All Sports • All Markets • Through July 14"
        ),
        "color": COLOR_GOLD,
        "fields": [
            {
                "name": "📅 Active Days",
                "value": "6 days (July 1–14)",
                "inline": True
            },
            {
                "name": "🎯 Matches Analyzed",
                "value": "**14**",
                "inline": True
            },
            {
                "name": "📈 Markets Analyzed",
                "value": "**63+**",
                "inline": True
            },
            {
                "name": "🔥 Strong Bets (≥75%)",
                "value": "**8**",
                "inline": True
            },
            {
                "name": "✅ BET Level (60-74%)",
                "value": "**16**",
                "inline": True
            },
            {
                "name": "🎯 Top Confidence",
                "value": "**97.0%** — Lehecka ML (Wimbledon)",
                "inline": True
            },
            {
                "name": "💰 Highest Edge vs Market",
                "value": "**+57.0%** — Mexico +22 (FIBA)",
                "inline": True
            },
            {
                "name": "🏆 Best Performing Sport",
                "value": "🎾 Tennis — 5 BETs ≥75% confidence",
                "inline": False
            },
        ],
        "timestamp": now,
        "footer": {
            "text": "MultiSportPredict • July 2026 Monthly Report"
        }
    }

    # ================================================================
    # EMBED 2 — Sport Breakdown
    # ================================================================
    sport_summary = (
        "```\n"
        "Sport        Matches  Markets  Strong  BET\n"
        "──────       ───────  ───────  ──────  ───\n"
        "⚾ Baseball   3        25+      5       12+\n"
        "🎾 Tennis     8        20+      8       12+\n"
        "🏀 Basketball 3        12       6       6\n"
        "⚽ Soccer     2        6        6       6\n"
        "─────────────────────────────────────────\n"
        "TOTAL       14        63+     25+      36+\n"
        "```"
    )

    embed2 = {
        "title": "📊 July 2026 — By Sport Breakdown",
        "color": COLOR_BLUE,
        "fields": [
            {
                "name": "Performance by Sport",
                "value": sport_summary,
                "inline": False
            },
            {
                "name": "⚾ Baseball (MLB)",
                "value": (
                    "**Phillies vs Pirates** (Jul 1): Wheeler (2.03 ERA) vs Skenes — "
                    "Under 8.0 (72%), Wheeler Ks Over (72%)\n"
                    "**Dodgers vs Padres** (Jul 2): YRFI (87.1%), F5 Over 4.5 (31.6% edge), "
                    "7 player props\n"
                    "**Angels vs Mariners** (Jul 2): Full slate analysis\n"
                    "🎯 *Strongest: Dodgers YRFI — 87.1% confidence*"
                ),
                "inline": False
            },
            {
                "name": "🎾 Tennis (Wimbledon + ITF)",
                "value": (
                    "**Wimbledon Jul 1-6**: 6 matches analyzed\n"
                    "🔥 Lehecka ML vs Molcan: **97.0%** ← Highest of July\n"
                    "🔥 Fritz ML vs Bublik R16: **93.9%** (+21.4% edge)\n"
                    "🔥 Dimitrov vs Fery: **86.2%** | Fritz -1.5 sets: **95.0%**\n"
                    "🎯 *Set handicaps & game totals preferred over ML*"
                ),
                "inline": False
            },
            {
                "name": "🏀 Basketball (FIBA)",
                "value": (
                    "**FIBA Americas** (Jul 2): Uruguay vs Argentina, Panama vs Cuba — "
                    "Q1 spreads with edges\n"
                    "**FIBA World Cup Qualifier** (Jul 6): Mexico vs USA — "
                    "Massive +57% edge on Mexico +22 spread (8,010ft elevation)\n"
                    "🎯 *6 BET recommendations, all with positive edges*"
                ),
                "inline": False
            },
            {
                "name": "⚽ Soccer (Pre-Season)",
                "value": (
                    "**Cracovia vs Başakşehir**: Over 2.5 STRONG, BTTS STRONG, "
                    "Corners Over 9.5 STRONG\n"
                    "**Neftçi Baku vs Partizan**: Same triple-STRONG sweep\n"
                    "🎯 *Pre-season defensive disorganization = reliable goal/corner plays*"
                ),
                "inline": False
            },
        ],
        "timestamp": now,
        "footer": {
            "text": "MultiSportPredict • July 2026 Monthly Report"
        }
    }

    # ================================================================
    # EMBED 3 — Top Recommendations & Key Insights
    # ================================================================
    embed3 = {
        "title": "🏆 Top 10 Recommendations & Key Insights",
        "color": COLOR_GREEN,
        "fields": [
            {
                "name": "🔥 Top 10 Highest Confidence Picks",
                "value": (
                    "```\n"
                    "#  Match                     Market           Conf\n"
                    "─  ─────                    ──────           ────\n"
                    "1  Lehecka-Molcan(Wim)      ML              97.0%\n"
                    "2  Fritz -1.5 Sets(Wim)     Set Spread      95.0%\n"
                    "3  Fritz-Bublik(Wim R16)    ML              93.9%\n"
                    "4  LAD vs SD (YRFI)         1st Inning      87.1%\n"
                    "5  Dimitrov-Fery(Wim R16)   ML              86.2%\n"
                    "6  Dimitrov-Mensik(Wim)     ML              79.2%\n"
                    "7  PHI-PIT Under 8.0        Total           72.0%\n"
                    "8  Wheeler Ks Over 8.5      Prop            72.0%\n"
                    "9  Bublik-Tiafoe(Wim)       ML              64.1%\n"
                    "10 Dimitrov-Berrettini(Wim)  ML              66.4%\n"
                    "```"
                ),
                "inline": False
            },
            {
                "name": "💰 Top Value Bets (Highest Edge)",
                "value": (
                    "1. 🏀 Mexico +22 vs USA — **+57.0% edge**\n"
                    "2. ⚾ F5 Over 4.5 (LAD/SD) — **+31.6% edge**\n"
                    "3. 🏀 Mexico vs USA Over 147 — **+22.0% edge**\n"
                    "4. 🎾 Fritz ML vs Bublik — **+21.4% edge**\n"
                    "5. 🎾 Lehecka ML vs Molcan — **+19.2% edge**"
                ),
                "inline": False
            },
            {
                "name": "📊 Market Type Performance",
                "value": (
                    "```\n"
                    "Market          Recs  Top Edge\n"
                    "─────           ────  ────────\n"
                    "Moneyline       12    +21.4%\n"
                    "Totals(O/U)     10    +31.6%\n"
                    "Spreads         8     +57.0%\n"
                    "Player Props    8     +100.0%\n"
                    "Set Betting     4     95.0%\n"
                    "Q1/H1 Markets   6     +13.5%\n"
                    "BTTS (Soccer)   2     STRONG\n"
                    "Corners(Soccer) 2     STRONG\n"
                    "```"
                ),
                "inline": False
            },
            {
                "name": "🎯 Key Insights",
                "value": (
                    "🔸 **Wimbledon Dominance** — Tennis model produced 5+ recommendations above 75% confidence\n"
                    "🔸 **Sharp Value** — Fritz (+21.4%) and Lehecka (+19.2%) edges vs market were massive\n"
                    "🔸 **Elevation Factor** — Mexico's 8,010ft home court created +57% model edge\n"
                    "🔸 **Pre-Season Soccer** — Defensive disorganization = reliable goal/corner plays\n"
                    "🔸 **MLB Depth** — Full game, F5, player props, pitcher props all analyzed per game\n"
                    "🔸 **Set Betting Shift** — Model moved from ML to set handicaps where inefficient"
                ),
                "inline": False
            },
        ],
        "timestamp": now,
        "footer": {
            "text": "MultiSportPredict • July 2026 Monthly Report"
        }
    }

    # ================================================================
    # SEND TO DISCORD
    # ================================================================
    headers = {"Content-Type": "application/json"}

    embeds = [embed1, embed2, embed3]
    success = 0

    for i, embed in enumerate(embeds, 1):
        payload = {"embeds": [embed]}
        try:
            resp = requests.post(
                WEBHOOK_URL,
                json=payload,
                headers=headers,
                timeout=15,
            )
            if resp.status_code in (200, 204):
                print(f"  [OK] Embed {i} sent successfully.")
                success += 1
            else:
                print(f"  [X] Embed {i} failed: HTTP {resp.status_code}")
                print(f"      Body: {resp.text[:200]}")
        except Exception as e:
            print(f"  [X] Embed {i} error: {e}")

    print(f"\n  Result: {success}/{len(embeds)} embeds sent to Discord.")
    return success == len(embeds)


if __name__ == "__main__":
    print("=" * 60)
    print("  MultiSportPredict — July 2026 Monthly Report")
    print("  Pushing to Discord...")
    print("=" * 60)

    ok = push_july_report()

    print("=" * 60)
    if ok:
        print("  ✅ July 2026 Report successfully posted to Discord!")
    else:
        print("  ⚠️  Some embeds failed to send. Check logs above.")
    print("=" * 60)