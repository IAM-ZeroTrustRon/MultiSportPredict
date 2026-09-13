#!/usr/bin/env python
"""
Push Tennis Slate Results to Discord
====================================
Pushes 3 tennis match analyses to Discord via the shared Discord webhook.

Matches:
  1. Sol Ailin Larraya Guidi vs Lorena Schaedel  (W35 Chacabuco, R16 - Clay)  -> BET Larraya Guidi
  2. Valentina Steiner vs Julie Pastkova         (ITF Circuit)                 -> PASS (high variance)
  3. Oscar Brown vs Ben Gusic Wan                (M25 Roehampton, R16)         -> BET Oscar Brown

Each match is rendered as a rich embed with tournament details, deep dive
analysis, sharp report, and prediction. Consensus targets are enforced.
"""

import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
import requests

# Load environment variables from .env
load_dotenv("c:/MultiSportPredict/.env")

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Discord embed colors
GREEN = 3066993   # Strong bet / win
RED = 15158332    # Pass / avoid
BLUE = 3447003    # Informational


def build_match_embed(match: dict) -> dict:
    """Build a rich Discord embed for a single tennis match."""
    color = GREEN if match["prediction_type"] == "BET" else RED
    return {
        "title": f"🎾 {match['matchup']}",
        "description": (
            f"**{match['tournament']}** | {match.get('round', '')} | "
            f"Surface: **{match['surface']}**"
        ),
        "color": color,
        "fields": [
            {
                "name": "🔍 The Deep Dive",
                "value": match["deep_dive"],
                "inline": False,
            },
            {
                "name": "📡 Sharp Report",
                "value": match["sharp_report"],
                "inline": False,
            },
            {
                "name": "🎯 Prediction",
                "value": (
                    f"**{match['prediction_verdict']}**\n\n"
                    f"Consensus Target: **{match['consensus_target']}**\n"
                    + (f"Reasoning: {match['reasoning']}" if match.get("reasoning") else "")
                ),
                "inline": False,
            },
        ],
        "footer": {
            "text": (
                f"MultiSportPredict Tennis Slate | Umpire Tendencies Enforced | "
                f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
            )
        },
    }


def main() -> None:
    if not DISCORD_WEBHOOK_URL:
        print("❌ DISCORD_WEBHOOK_URL not found in .env")
        sys.exit(1)

    matches = [
        {
            "matchup": "Sol Ailin Larraya Guidi vs Lorena Schaedel",
            "tournament": "W35 Chacabuco",
            "round": "Round of 16",
            "surface": "Clay",
            "deep_dive": (
                "Larraya Guidi (WTA 1,469th) enters this matchup riding the momentum "
                "of a clean 2-0 victory over F. Massardo Brain. While Schaedel holds a "
                "slightly higher overall ranking (WTA 1,080th), the recent form and "
                "market action tell a different story."
            ),
            "sharp_report": (
                "Syndicate money heavily favors Larraya Guidi. Current betting lines "
                "sit with Larraya Guidi as a massive -400 favorite, with Schaedel "
                "returning +275 as the underdog."
            ),
            "prediction_verdict": "✅ Larraya Guidi to WIN",
            "consensus_target": "Larraya Guidi",
            "prediction_type": "BET",
            "reasoning": (
                "Highly safe pick to anchor a parlay based on the overwhelming "
                "market consensus."
            ),
        },
        {
            "matchup": "Valentina Steiner vs Julie Pastkova",
            "tournament": "ITF Circuit",
            "round": "Matchplay",
            "surface": "Hard",
            "deep_dive": (
                "Steiner has been a high-volume competitor across the ITF Germany "
                "circuit this summer, demonstrating highly resilient baseline "
                "exchanges. However, she can occasionally struggle with double faults "
                "during tight service games, which leaves her vulnerable to early breaks."
            ),
            "sharp_report": (
                "There is very little sharp action or insider line movement currently "
                "available on this specific matchup. Without a clear market consensus "
                "or heavily lopsided prediction data, the variance is significantly "
                "higher."
            ),
            "prediction_verdict": "❌ PASS — Avoid",
            "consensus_target": "None - High Variance",
            "prediction_type": "PASS",
            "reasoning": (
                "Avoid slotting this match into any primary parlays to protect your "
                "bankroll from unpredictable, low-visibility ITF results."
            ),
        },
        {
            "matchup": "Oscar Brown vs Ben Gusic Wan",
            "tournament": "M25 Roehampton",
            "round": "Round of 16",
            "surface": "Hard",
            "deep_dive": (
                "This all-British matchup features two rising prospects. Gusic Wan has "
                "an impressive junior pedigree and accolades in the Kent tennis circuit, "
                "but Brown's recent upward mobility on the ITF tour gives him the edge "
                "in current competitive form."
            ),
            "sharp_report": (
                "Prediction markets heavily favor Oscar Brown, who is currently trading "
                "at a 64% implied probability to win, compared to Gusic Wan's 36%. The "
                "smart money is backing Brown's consistency."
            ),
            "prediction_verdict": "✅ Oscar Brown to WIN",
            "consensus_target": "Oscar Brown",
            "prediction_type": "BET",
            "reasoning": (
                "A solid, calculated addition for straight bets or as a secondary "
                "parlay leg."
            ),
        },
    ]

    print("=" * 60)
    print("  TENNIS SLATE — DISCORD PUSH")
    print("=" * 60)
    print(f"  Matches to push: {len(matches)}")
    print()

    success_count = 0
    for i, match in enumerate(matches, 1):
        embed = build_match_embed(match)
        payload = {"embeds": [embed]}
        try:
            response = requests.post(
                DISCORD_WEBHOOK_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            if response.status_code in (200, 204):
                success_count += 1
                print(f"  ✅ [{i}/{len(matches)}] {match['matchup']} — pushed")
            else:
                print(
                    f"  ❌ [{i}/{len(matches)}] {match['matchup']} — failed "
                    f"({response.status_code}: {response.text[:200]})"
                )
        except Exception as exc:
            print(f"  ❌ [{i}/{len(matches)}] {match['matchup']} — error: {exc}")

    print()
    print("=" * 60)
    if success_count == len(matches):
        print(f"  ✅ ALL {success_count} EMBEDS PUSHED SUCCESSFULLY!")
    else:
        print(f"  ⚠️  {success_count}/{len(matches)} embeds pushed successfully")
    print("=" * 60)


if __name__ == "__main__":
    main()
