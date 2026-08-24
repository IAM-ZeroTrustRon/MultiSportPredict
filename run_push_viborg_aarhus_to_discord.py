#!/usr/bin/env python
"""
Runs a soccer match prediction for Viborg vs Aarhus AGF and pushes it to Discord.

This script uses the existing SoccerPredictor model and the discord_integration module
to send a formatted, rich embed for a single match.

Usage:
    python run_push_viborg_aarhus_to_discord.py          # run + push
    python run_push_viborg_aarhus_to_discord.py --dry-run # print payload only
"""

import os
import logging
import argparse
from pathlib import Path

import pandas as pd

from dotenv import load_dotenv

# Ensure the project root is on sys.path for imports
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in os.getcwd():
    os.chdir(PROJECT_ROOT)

# Load environment variables from .env file
load_dotenv()

from models.soccer_predictor import SoccerPredictor
from discord_integration import push_soccer_prediction_to_discord, test_webhook

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --- Match Data ---
HOME_TEAM = "Viborg"
AWAY_TEAM = "Aarhus AGF"
LEAGUE = "Danish Superliga" # Assuming Danish Superliga for these teams
MATCH_NAME = f"{HOME_TEAM} vs {AWAY_TEAM}"
MARKET_TOTAL = 2.5 # Common total goals line for soccer
MARKET_LINE = 0.0  # Placeholder for spread/moneyline context

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Soccer prediction for Viborg vs Aarhus AGF")
    parser.add_argument("--dry-run", action="store_true", help="Print Discord payload without posting")
    args = parser.parse_args()

    logger.info("Running prediction for: %s (%s)", MATCH_NAME, LEAGUE)

    if not args.dry_run and not test_webhook():
        logger.error("Discord webhook not configured or failed test. Check DISCORD_WEBHOOK_URL in your .env file.")
        return

    predictor = SoccerPredictor(league=LEAGUE)
    prediction_data = predictor.predict(
        features=pd.DataFrame(),
        model=None,
        home_team=HOME_TEAM,
        away_team=AWAY_TEAM,
        market_total=MARKET_TOTAL,
        market_line=MARKET_LINE,
        league=LEAGUE
    )

    success = push_soccer_prediction_to_discord(match_name=MATCH_NAME, prediction_data=prediction_data, dry_run=args.dry_run)

    if success:
        logger.info("Successfully pushed prediction for '%s' to Discord (or dry-run).", MATCH_NAME)
    else:
        logger.error("Failed to push prediction for '%s' to Discord.", MATCH_NAME)

if __name__ == "__main__":
    main()
