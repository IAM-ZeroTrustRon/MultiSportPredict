#!/usr/bin/env python
"""
Batch Soccer Predictor for MultiSportPredict
=============================================
Runs model inference on a predefined set of soccer matches using the
SoccerPredictor module and pushes results to Discord via the existing
discord_integration module.

Usage:
    python batch_run_soccer.py                         # dry run (no Discord push)
    python batch_run_soccer.py --push                  # live push to Discord
    python batch_run_soccer.py --push --dry-run        # print payload only
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timezone

# Ensure the project root is on sys.path for imports
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv

from models.soccer_predictor import SoccerPredictor
from discord_integration import push_to_discord

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("batch_run_soccer")

load_dotenv()

# ---------------------------------------------------------------------------
# MATCH DEFINITIONS
# ---------------------------------------------------------------------------
# Each match includes team-specific xG/shots metrics so that the SoccerPredictor
# produces differentiated predictions for each matchup.
# Where no specific data is available, the predictor's built-in _name_derived_stats()
# fallback will generate deterministic stats from the team name.
# ---------------------------------------------------------------------------

MATCHES = [
    {
        "id": "col_hjk_2026",
        "name": "Coleraine vs HJK Helsinki",
        "home_team": "Coleraine",
        "away_team": "HJK Helsinki",
        "league": "UEFA Europa League Qualifying",
        "market_line": 0.0,
        "market_total": 2.5,
    },
    {
        "id": "din_alm_2026",
        "name": "Dinamo Tirana vs NK Aluminij",
        "home_team": "Dinamo Tirana",
        "away_team": "NK Aluminij",
        "league": "UEFA Conference League Qualifying",
        "market_line": 0.0,
        "market_total": 2.5,
    },
]


# ---------------------------------------------------------------------------
# CORE FUNCTIONS
# ---------------------------------------------------------------------------

def format_prediction_output(match_name: str, prediction: dict) -> str:
    """Format a prediction dict into a human-readable string."""
    game = prediction.get("game", {})
    preds = prediction.get("predictions", {})
    goals_analysis = prediction.get("goals_analysis", {})
    corners_analysis = prediction.get("corners_analysis", {})

    lines = [
        f"Match: {match_name}",
        f"  Projected: {game.get('projected_home_goals', 'N/A'):.2f} - {game.get('projected_away_goals', 'N/A'):.2f} "
        f"(Total: {game.get('projected_total_goals', 'N/A'):.2f})",
        f"  1X2 Probs: H {game.get('home_win_prob', 0)*100:.1f}% | D {game.get('draw_prob', 0)*100:.1f}% | A {game.get('away_win_prob', 0)*100:.1f}%",
        f"  Over 2.5: {goals_analysis.get('over_25_prob', 0)*100:.1f}%",
        f"  BTTS: {prediction.get('btts_probability', 0)*100:.1f}%",
        f"  Corners: {corners_analysis.get('projection', 'N/A')}",
        f"  Total Edge: {preds.get('total', {}).get('edge', 0):+.3f} "
        f"(Conf: {preds.get('total', {}).get('confidence', 0):.1f}%)",
    ]
    return "\n".join(lines)


def push_match_to_discord(match_name: str, prediction: dict, dry_run: bool = False) -> bool:
    """
    Push a single match prediction to Discord via the existing discord_integration module.

    Args:
        match_name: Display name for the match
        prediction: Output dict from SoccerPredictor.predict()
        dry_run: If True, print payload instead of posting

    Returns:
        True if push was successful (or dry-run), False otherwise
    """
    game = prediction.get("game", {})
    preds = prediction.get("predictions", {})
    btts_prob = prediction.get("btts_probability", 0)
    corner_proj = prediction.get("corner_projection", 0)
    goals_analysis = prediction.get("goals_analysis", {})

    home = prediction.get("home_team", "Home")
    away = prediction.get("away_team", "Away")

    home_win_pct = game.get("home_win_prob", 0) * 100
    draw_pct = game.get("draw_prob", 0) * 100
    away_win_pct = game.get("away_win_prob", 0) * 100

    # Build recommendation string
    total_rec = preds.get("total", {}).get("recommendation", "PASS")
    total_conf = preds.get("total", {}).get("confidence", 0)
    total_edge = preds.get("total", {}).get("edge", 0)

    btts_edge = (btts_prob - 0.5) * 100
    btts_rec = preds.get("btts", {}).get("recommendation", "PASS")

    # Format additional fields for the embed
    additional_fields = {
        "1X2": f"H {home_win_pct:.1f}% | D {draw_pct:.1f}% | A {away_win_pct:.1f}%",
        "Over 2.5": f"{goals_analysis.get('over_25_prob', 0)*100:.1f}%",
        "Corners": f"{corner_proj:.1f}",
        "Recommendation": f"Total: {total_rec} ({total_edge:+.3f} edge, {total_conf:.1f}% conf) | BTTS: {btts_rec} ({btts_edge:+.1f}% edge)",
    }

    if dry_run:
        logger.info("[DRY RUN] Would push to Discord for match: %s", match_name)
        logger.info("[DRY RUN] Payload sport=soccer, home=%s, away=%s, recommendation=%s, confidence=%.1f, edge=%+.3f",
                    home, away, total_rec, total_conf, total_edge)
        return True

    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url or webhook_url == "None":
        logger.warning("DISCORD_WEBHOOK_URL not set. Skipping Discord push for %s.", match_name)
        return False

    # Use the existing discord_integration.push_to_discord with keyword arguments
    success = push_to_discord(
        sport="soccer",
        home=home,
        away=away,
        recommendation=f"Total: {total_rec} | BTTS: {btts_rec}",
        confidence=total_conf,
        edge=f"{total_edge:+.3f}",
        market_total=prediction.get("predictions", {}).get("total", {}).get("market_total", 2.5),
        use_embed=True,
        webhook_url=webhook_url,
        additional_fields=additional_fields,
    )

    if success:
        logger.info("[SUCCESS] Pushed %s to Discord.", match_name)
    else:
        logger.error("[FAILED] Could not push %s to Discord.", match_name)

    return success


def run_soccer_batch(dry_run: bool = False, push: bool = False):
    """
    Run batch predictions for all defined soccer matches.

    Args:
        dry_run: If True, print predictions without pushing to Discord
        push: If True, push results to Discord (ignored if dry_run=True)
    """
    logger.info("Initializing SoccerPredictor...")
    predictor = SoccerPredictor(league="default")

    logger.info("Starting batch prediction run for %d match(es)...", len(MATCHES))
    print("=" * 60)

    for match in MATCHES:
        match_name = match["name"]
        logger.info("Running inference for %s...", match_name)

        try:
            # Call predict with correct signature
            prediction = predictor.predict(
                features=None,
                model=None,
                home_team=match["home_team"],
                away_team=match["away_team"],
                market_line=match.get("market_line", 0.0),
                market_total=match.get("market_total", 2.5),
                league=match.get("league", "default"),
                # Pass optional override stats if provided in match definition
                **{k: v for k, v in match.items()
                   if k.startswith(("home_", "away_")) and k not in ("home_team", "away_team")},
            )

            # Log formatted output
            print(format_prediction_output(match_name, prediction))
            print("-" * 45)

            # Push to Discord if requested
            if push:
                push_match_to_discord(match_name, prediction, dry_run=dry_run)
                print("-" * 45)

        except Exception as e:
            logger.error("Failed to process %s: %s", match_name, e, exc_info=True)
            print(f"[ERROR] {match_name}: {e}")
            print("-" * 45)

    logger.info("Batch run complete.")


# ---------------------------------------------------------------------------
# CLI ENTRY POINT
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Batch soccer prediction runner with optional Discord push."
    )
    parser.add_argument(
        "--push", "-p",
        action="store_true",
        help="Push predictions to Discord via webhook",
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        default=True,
        help="Run in dry-run mode (print payloads, no actual post). Default: True",
    )
    parser.add_argument(
        "--no-dry-run", "-nd",
        action="store_false",
        dest="dry_run",
        help="Disable dry-run mode (actually post to Discord when --push is set)",
    )
    args = parser.parse_args()

    # Default: dry_run=True unless --no-dry-run is explicitly passed
    dry_run = args.dry_run
    push = args.push

    if push:
        if dry_run:
            logger.info("DRY RUN MODE: Predictions will be computed and printed, "
                        "but NOT posted to Discord.")
        else:
            webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
            if not webhook_url or webhook_url == "None":
                logger.warning("DISCORD_WEBHOOK_URL is not set. "
                               "Set it in your .env file or environment variables.")
                logger.warning("Falling back to dry-run mode.")
                dry_run = True

    run_soccer_batch(dry_run=dry_run, push=push)


if __name__ == "__main__":
    main()
