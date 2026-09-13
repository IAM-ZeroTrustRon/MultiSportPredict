#!/usr/bin/env python
"""
Runs a one-off soccer friendly prediction and pushes it to Discord.

This script demonstrates how to use the existing discord_integration module
to send a formatted, rich embed for a single match without needing to
re-implement the webhook logic in another language.

Usage:
    python run_soccer_friendly.py
"""

import os
import logging
from dotenv import load_dotenv

# Ensure the project root is on sys.path for imports
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in os.getcwd():
    os.chdir(PROJECT_ROOT)

# Load environment variables from .env file
load_dotenv()

from discord_integration import push_soccer_prediction_to_discord, test_webhook

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --- Match Data (from your PowerShell script) ---
MATCH_NAME = "Marseille vs Atletico Madrid"
PREDICTION_DATA = {
    "game": {"home_win_prob": 0.416, "away_win_prob": 0.584},
    "predictions": {
        "total": {
            "recommendation": "LEAN Atletico Madrid",
            "confidence": 58.4,
            "edge": 0,  # Not provided in original, default to 0
            "market_total": 2.5,
        }
    },
    "goals_analysis": {"over_25_prob": 0.64},  # Implied from -180 odds
    "btts_probability": 0.5,  # Neutral assumption
    "corner_projection": 9.5,
    "home_team": "Marseille",
    "away_team": "Atletico Madrid",
}

def main():
    """Main execution function."""
    logger.info("Running prediction for: %s", MATCH_NAME)

    if not test_webhook():
        logger.error("Discord webhook not configured or failed test. Check DISCORD_WEBHOOK_URL in your .env file.")
        return

    # Use the dedicated soccer push function for consistent formatting and features
    success = push_soccer_prediction_to_discord(match_name=MATCH_NAME, prediction_data=PREDICTION_DATA)

    if success:
        logger.info("Successfully pushed prediction for '%s' to Discord.", MATCH_NAME)
    else:
        logger.error("Failed to push prediction for '%s' to Discord.", MATCH_NAME)

if __name__ == "__main__":
    main()