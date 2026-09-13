"""
Valerenga Football Elite vs Aalesund FK — Norwegian Eliteserien
================================================================
Dedicated script to run the soccer prediction model and push the
result to Discord with rich embed formatting.

Usage:
    python run_valerenga_alesund.py

Requires:
    - .env file with DISCORD_WEBHOOK_URL set
"""

from run_soccer_to_discord import main as run_soccer_to_discord_main


def main() -> None:
    import sys

    sys.argv = [
        "run_soccer_to_discord.py",
        "--home",
        "Valerenga",
        "--away",
        "Aalesund",
        "--league",
        "Norwegian Eliteserien",
        "--market-total",
        "2.5",
    ]
    run_soccer_to_discord_main()


if __name__ == "__main__":
    main()