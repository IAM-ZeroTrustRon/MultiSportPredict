#!/usr/bin/env python
"""
Batch Discord Push for MultiSportPredict
=========================================
Runs model inference on predefined soccer matches and pushes results
to Discord via the shared discord_integration module.

Usage:
    python batch_discord_push.py --push            # live push to Discord
    python batch_discord_push.py --dry-run         # dry run (no post)
    python batch_discord_push.py                   # runs inference, prints to console
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timezone

from dotenv import load_dotenv

# Ensure the project root is on sys.path for imports
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Load environment variables for local execution
load_dotenv('c:/MultiSportPredict/.env')

# MultiSportPredict local imports
from models.soccer_predictor import SoccerPredictor
from discord_integration import push_soccer_prediction_to_discord, push_to_discord

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("batch_discord_push")


# ---------------------------------------------------------------------------
# MATCH DEFINITIONS
# ---------------------------------------------------------------------------
MATCHES = [
    {"id": "vas_org_2026", "name": "Vasteras SK FK vs Orgryte"},
    {"id": "pog_leg_2026", "name": "Pogon Szczecin vs Legia Warszawa"},
    {"id": "ucd_cor_2026", "name": "UC Dublin vs Cork City"},
    {"id": "vik_kef_2026", "name": "Vikingur Reykjavik vs Keflavik"},
]


# ---------------------------------------------------------------------------
# CORE FUNCTIONS
# ---------------------------------------------------------------------------

def format_prediction_output(match_name: str, prediction: dict) -> str:
    """Format a prediction dict into a human-readable string."""
    game = prediction.get("game", {})
    preds = prediction.get("predictions", {})
    goals_analysis = prediction.get("goals_analysis", {})
    btts_prob = prediction.get("btts_probability", 0)
    corner_proj = prediction.get("corner_projection", 0)

    home = prediction.get("home_team", "Home")
    away = prediction.get("away_team", "Away")

    home_win_pct = game.get("home_win_prob", 0) * 100
    draw_pct = game.get("draw_prob", 0) * 100
    away_win_pct = game.get("away_win_prob", 0) * 100

    total_rec = preds.get("total", {}).get("recommendation", "PASS")
    total_conf = preds.get("total", {}).get("confidence", 0)
    total_edge = preds.get("total", {}).get("edge", 0)

    lines = [
        f"Match: {match_name}",
        f"  {home} vs {away}",
        f"  1X2 Probs: H {home_win_pct:.1f}% | D {draw_pct:.1f}% | A {away_win_pct:.1f}%",
        f"  Over 2.5: {goals_analysis.get('over_25_prob', 0)*100:.1f}%",
        f"  BTTS: {btts_prob*100:.1f}%",
        f"  Corners: {corner_proj:.1f}",
        f"  Recommendation: {total_rec} (edge: {total_edge:+.3f}, conf: {total_conf:.1f}%)",
    ]
    return "\n".join(lines)


def run_soccer_batch(dry_run: bool = False, push: bool = False):
    """
    Run batch predictions for all defined soccer matches.

    Args:
        dry_run: If True, print payloads without actually posting to Discord
        push: If True, push results to Discord
    """
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if push and (not webhook_url or webhook_url == "None"):
        logger.warning("DISCORD_WEBHOOK_URL not set. Falling back to dry-run mode.")
        dry_run = True
        push = False

    predictor = SoccerPredictor(league="default")

    print("Starting batch prediction run...")
    print("=" * 60)

    for match in MATCHES:
        match_name = match["name"]
        print(f"Ingesting data for {match_name}...")

        # Derive home/away team names from match name
        parts = match_name.split(" vs ")
        home_team = parts[0].strip() if len(parts) == 2 else match_name
        away_team = parts[1].strip() if len(parts) == 2 else "Opponent"

        print(f"Running inference for {match_name}...")
        try:
            prediction = predictor.predict(
                features=None,
                model=None,
                home_team=home_team,
                away_team=away_team,
                market_line=0.0,
                market_total=2.5,
            )

            # Print formatted output to console
            print(format_prediction_output(match_name, prediction))

            # Push to Discord (via shared discord_integration module)
            if push and not dry_run:
                success = push_soccer_prediction_to_discord(
                    match_name=match_name,
                    prediction_data=prediction,
                    webhook_url=webhook_url,
                )
                status = "SUCCESS" if success else "FAILED"
                print(f"[{status}] Pushed {match_name} to Discord.")
            elif dry_run and push:
                # Print the payload without posting
                game = prediction.get("game", {})
                preds = prediction.get("predictions", {})
                print(
                    f"[DRY RUN] Would push {match_name}: "
                    f"sport=soccer, home={home_team}, away={away_team}, "
                    f"recommendation={preds.get('total', {}).get('recommendation', 'N/A')}"
                )

        except Exception as e:
            logger.error(f"Inference failed for {match_name}: {e}")
            print(f"[ERROR] Inference failed for {match_name}: {e}")

        print("-" * 45)

    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}] [INFO] Batch run complete.")


# ---------------------------------------------------------------------------
# CLI ENTRY POINT
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Batch soccer prediction runner with Discord push."
    )
    parser.add_argument(
        "--push", "-p",
        action="store_true",
        help="Push predictions to Discord via webhook",
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        default=False,
        help="Run in dry-run mode (print payloads, no actual post).",
    )
    parser.add_argument(
        "--no-dry-run", "-nd",
        action="store_false",
        dest="dry_run",
        help="Disable dry-run mode (actually post to Discord when --push is set)",
    )
    args = parser.parse_args()

    dry_run = args.dry_run
    push = args.push

    if push and dry_run:
        logger.info("DRY RUN MODE: Predictions computed and payloads printed, "
                     "but NOT posted to Discord.")

    run_soccer_batch(dry_run=dry_run, push=push)


if __name__ == "__main__":
    main()