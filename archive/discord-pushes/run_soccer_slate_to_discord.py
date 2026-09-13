"""
DEPRECATED — Use discord_integration.push_slate_to_discord() instead.

This module exists for backward compatibility only. All new code should
import push_slate_to_discord from discord_integration.

The same slate content is defined in predict_match.py run_soccer_slate()
and pushed as a single consolidated message to prevent duplicate Discord pushes.
"""

import os
import warnings

warnings.warn(
    "run_soccer_slate_to_discord.py is deprecated. Use discord_integration.push_slate_to_discord() "
    "or run: python predict_match.py --slate --push-discord",
    DeprecationWarning,
    stacklevel=2,
)

from dotenv import load_dotenv
from discord_integration import push_slate_to_discord

load_dotenv()
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")


def evaluate_and_push_slate() -> None:
    """
    Delegates to consolidated push_slate_to_discord to avoid duplicate pushes.
    """
    slate = [
        {
            "home": "Shelbourne",
            "away": "Bohemians",
            "market": "BTTS",
            "projected": "62% Probability",
            "edge": "+4.5%",
            "rec": "BOTH TEAMS TO SCORE - YES",
        },
        {
            "home": "Shamrock Rovers",
            "away": "Derry City",
            "market": "Total Goals: 2.5",
            "projected": "1.8 Goals",
            "edge": "+6.2%",
            "rec": "UNDER 2.5 GOALS",
        },
        {
            "home": "Al Qadsia",
            "away": "Kazma SC",
            "market": "Total Goals: 2.5",
            "projected": "3.4 Goals",
            "edge": "+7.1%",
            "rec": "OVER 2.5 GOALS",
        },
        {
            "home": "RB do Norte U20",
            "away": "Manauara U20",
            "market": "Total Goals: 3.5",
            "projected": "2.1 Goals",
            "edge": "+5.8%",
            "rec": "UNDER 3.5 GOALS",
        },
    ]

    print(f"Delegating {len(slate)} matches to consolidated push_slate_to_discord...")
    success = push_slate_to_discord(slate, sport="soccer", webhook_url=DISCORD_WEBHOOK)
    if success:
        print(f"✅ Consolidated slate pushed to Discord ({len(slate)} matches).")
    else:
        print("❌ Failed to push slate to Discord.")
    print("Batch execution complete.")


if __name__ == "__main__":
    evaluate_and_push_slate()
