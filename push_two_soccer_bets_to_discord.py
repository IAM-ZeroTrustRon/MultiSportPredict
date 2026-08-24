#!/usr/bin/env python
"""
Push Two Soccer Match Recommendations to Discord
=================================================
Pushes probability-adjusted betting recommendations for:

  1. Sandefjord vs KFUM Oslo (Eliteserien)
     - Over 2.5 goals (small +EV at ~1.95)
     - Sandefjord score first (good if odds >= 1.75)
     - Sandefjord ML (fair at ~1.90; +EV if >= 2.00)

  2. Wycombe vs Stevenage (League One)
     - Over 2.5 goals (strongest edge, big attack vs weak away D)
     - Wycombe ML (+EV at >= 1.75, very strong at >= 1.80)
     - Wycombe score first (good at odds >= 1.70)

Uses the pre-computed model probabilities and EV values from the analysis.
Sends one rich embed per match to the configured Discord webhook.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

# Ensure project root on sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv("c:/MultiSportPredict/.env")

# Webhook destination
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# ---------------------------------------------------------------------------
# MATCH DATA (Probability-adjusted recommendations)
# ---------------------------------------------------------------------------
MATCHES = [
    {
        "league": "Eliteserien",
        "home": "Sandefjord",
        "away": "KFUM Oslo",
        "probabilities": {
            "home_win": 0.525,
            "draw": 0.241,
            "away_win": 0.234,
            "over25": 0.527,
            "btts": 0.528,
            "home_score_first": 0.577,
        },
        "goals_model": {
            "home_xg": 1.45,
            "away_xg": 1.27,
            "expected_total": 2.72,
        },
        "recommendations": [
            {
                "name": "Over 2.5 goals",
                "ev": "+0.03",
                "odds": "~1.95",
                "reason": "Expected goals ~2.7, over2.5_prob ~0.53; small positive EV at ~1.95.",
            },
            {
                "name": "Sandefjord score first",
                "ev": "+0.04",
                "odds": ">=1.75",
                "reason": "0.58 probability; good if odds are at least 1.75.",
            },
            {
                "name": "Sandefjord ML",
                "ev": "0.00 → +EV",
                "odds": "~1.90 / >=2.00",
                "reason": "Fair at ~1.90; becomes +EV if you can get 2.00 or better.",
            },
        ],
    },
    {
        "league": "League One",
        "home": "Wycombe",
        "away": "Stevenage",
        "probabilities": {
            "home_win": 0.60,
            "draw": 0.22,
            "away_win": 0.18,
            "over25": 0.61,
            "btts": 0.50,
            "home_score_first": 0.65,
        },
        "goals_model": {
            "home_xg": 1.96,
            "away_xg": 0.92,
            "expected_total": 2.88,
        },
        "recommendations": [
            {
                "name": "Over 2.5 goals",
                "ev": "+0.13",
                "odds": "~1.85",
                "reason": "Strongest edge; over2.5_prob ~0.61, big home attack vs weak away defense.",
            },
            {
                "name": "Wycombe ML",
                "ev": "+0.05",
                "odds": ">=1.75 / >=1.80",
                "reason": "0.60 win prob; +EV at 1.75+, very strong at 1.80+.",
            },
            {
                "name": "Wycombe score first",
                "ev": "+0.11",
                "odds": ">=1.70",
                "reason": "0.65 probability; good at odds of 1.70 or better.",
            },
        ],
    },
]


def build_embed(match: dict) -> dict:
    """Build a rich Discord embed for a match's recommendations."""
    p = match["probabilities"]
    g = match["goals_model"]

    # Probability table
    probs = (
        f"**1X2**\n"
        f"🏠 {match['home']}: {p['home_win']*100:.1f}%\n"
        f"🤝 Draw: {p['draw']*100:.1f}%\n"
        f"✈️ {match['away']}: {p['away_win']*100:.1f}%\n\n"
        f"**Markets**\n"
        f"⚽ Over 2.5: {p['over25']*100:.1f}%\n"
        f"🤝 BTTS Yes: {p['btts']*100:.1f}%\n"
        f"🎯 {match['home']} Score First: {p['home_score_first']*100:.1f}%"
    )

    expected_goals = (
        f"🏠 {match['home']} xG: {g['home_xg']:.2f}\n"
        f"✈️ {match['away']} xG: {g['away_xg']:.2f}\n"
        f"📈 Expected Total: {g['expected_total']:.2f}"
    )

    # Recommendations section
    rec_lines = []
    for i, rec in enumerate(match["recommendations"], 1):
        rec_lines.append(
            f"**{i}. {rec['name']}**\n"
            f"   └─ EV: {rec['ev']} | Odds: {rec['odds']}\n"
            f"      {rec['reason']}"
        )
    recommendations = "\n\n".join(rec_lines)

    embed = {
        "title": f"⚽ {match['home'].upper()} vs {match['away'].upper()}",
        "description": (
            f"**{match['league']}** — Probability-Adjusted Recommendations"
        ),
        "color": 3066993,  # Green
        "fields": [
            {
                "name": "📊 Probabilities",
                "value": probs,
                "inline": True,
            },
            {
                "name": "🎯 Expected Goals Model",
                "value": expected_goals,
                "inline": True,
            },
            {
                "name": "💰 Recommended Bets",
                "value": recommendations,
                "inline": False,
            },
        ],
        "footer": {"text": "MultiSportPredict • Betting Recommendations"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return embed


def push_to_discord() -> bool:
    """Push both match embeds to Discord."""
    if not WEBHOOK_URL or WEBHOOK_URL == "None":
        print("ERROR: DISCORD_WEBHOOK_URL not set in .env file")
        return False

    success_count = 0
    total = len(MATCHES)

    for match in MATCHES:
        embed = build_embed(match)
        payload = {"embeds": [embed]}
        try:
            resp = requests.post(
                WEBHOOK_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            if resp.status_code in (200, 204):
                print(
                    f"✅ Pushed {match['home']} vs {match['away']} "
                    f"({match['league']}) to Discord."
                )
                success_count += 1
            else:
                print(
                    f"❌ Failed to push {match['home']} vs {match['away']}: "
                    f"HTTP {resp.status_code} — {resp.text[:200]}"
                )
        except Exception as exc:
            print(
                f"❌ Error pushing {match['home']} vs {match['away']}: {exc}"
            )

    print(f"\n{'✅' if success_count == total else '⚠️'}  "
          f"Pushed {success_count}/{total} match embeds to Discord.")
    return success_count == total


def main() -> None:
    print("=" * 70)
    print("TWO MATCH BETTING RECOMMENDATIONS -> DISCORD")
    print("=" * 70)
    push_to_discord()


if __name__ == "__main__":
    main()
