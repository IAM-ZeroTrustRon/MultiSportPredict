#!/usr/bin/env python
"""
Run SoccerPredictor with seed data for 3 fixtures: Viborg vs AGF Aarhus,
Orebro SK vs IK Brage, and Rosenborg vs Viking.

This script maps user-supplied seed data (form, goals for/against, H2H
dominance, fatigue, momentum) into the SoccerPredictor's per-team override
coefficients, producing differentiated model recommendations for each match.

Usage:
    python run_aug14_three_soccer_matches.py                # console output only
    python run_aug14_three_soccer_matches.py --push-discord # + push to Discord
    python run_aug14_three_soccer_matches.py --dry-run      # print Discord payload only
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

# Ensure the project root is on sys.path for imports
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
from dotenv import load_dotenv

from models.soccer_predictor import SoccerPredictor

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("run_aug14_three_soccer_matches")

load_dotenv()

# ---------------------------------------------------------------------------
# MATCH DEFINITIONS — Seed data mapped to model coefficients
# ---------------------------------------------------------------------------
# The SoccerPredictor.predict() method accepts per-team override kwargs:
#   home_xg_for, home_xg_against, home_shots, home_sot, home_goals_for,
#   home_goals_against, home_clean_sheets, home_tempo, home_width_crossing,
#   home_final_third_pressure, home_missing_*, etc. (same for away).
#
# The seed data below is current as of mid-August 2026 and is mapped into
# these coefficients to give each matchup differentiated model output.
# ---------------------------------------------------------------------------

MATCHES = [
    {
        "name": "Viborg vs AGF Aarhus",
        "home_team": "Viborg",
        "away_team": "AGF Aarhus",
        "league": "Danish Superliga",
        "market_line": 0.0,
        "market_total": 2.5,
        # Viborg: 6th, form W L W L D, 1 GF / 1 GA, tightened up (2 clean sheets)
        "home_xg_for": 1.30,
        "home_xg_against": 1.25,
        "home_shots": 11.5,
        "home_sot": 3.8,
        "home_goals_for": 1.00,
        "home_goals_against": 1.00,
        "home_clean_sheets": 2,
        "home_tempo": 0.55,
        "home_width_crossing": 0.55,
        "home_final_third_pressure": 0.55,
        # AGF Aarhus: H2H dominance (6-2, 5-2 thrashings this year) but
        # European-qualifier fatigue is modeled via docked tempo/pressure.
        "away_xg_for": 1.70,
        "away_xg_against": 1.30,
        "away_shots": 12.5,
        "away_sot": 4.4,
        "away_goals_for": 1.50,
        "away_goals_against": 1.30,
        "away_clean_sheets": 2,
        "away_tempo": 0.40,
        "away_width_crossing": 0.50,
        "away_final_third_pressure": 0.45,
    },
    {
        "name": "Orebro SK vs IK Brage",
        "home_team": "Orebro SK",
        "away_team": "IK Brage",
        "league": "Superettan",
        "market_line": 0.0,
        "market_total": 2.5,
        # Orebro: 15th, ~0.83 GF/game (15 GF / 18), 1.56 GA/game, lost 3 of
        # last 4 at home — severely capped attack.
        "home_xg_for": 0.90,
        "home_xg_against": 1.60,
        "home_shots": 9.5,
        "home_sot": 3.0,
        "home_goals_for": 0.83,
        "home_goals_against": 1.56,
        "home_clean_sheets": 2,
        "home_tempo": 0.35,
        "home_width_crossing": 0.45,
        "home_final_third_pressure": 0.35,
        # Brage: 30 GF (1.67/game), 33 GA (1.83/game) — leaky defense plus
        # potent attack; H2H Over 2.5 hit rate 87.5% (7/8) → high lambdas.
        "away_xg_for": 1.65,
        "away_xg_against": 1.80,
        "away_shots": 12.0,
        "away_sot": 4.2,
        "away_goals_for": 1.67,
        "away_goals_against": 1.83,
        "away_clean_sheets": 1,
        "away_tempo": 0.45,
        "away_width_crossing": 0.55,
        "away_final_third_pressure": 0.55,
    },
    {
        "name": "Rosenborg vs Viking",
        "home_team": "Rosenborg",
        "away_team": "Viking",
        "league": "Eliteserien",
        "market_line": 0.0,
        "market_total": 2.5,
        # Rosenborg: winning momentum (W4 L1) driven by Chiakha's finishing;
        # Lerkendal fortress boosts home tempo/pressure.
        "home_xg_for": 1.80,
        "home_xg_against": 1.20,
        "home_shots": 13.5,
        "home_sot": 4.8,
        "home_goals_for": 1.90,
        "home_goals_against": 1.00,
        "home_clean_sheets": 3,
        "home_tempo": 0.60,
        "home_width_crossing": 0.60,
        "home_final_third_pressure": 0.60,
        # Viking: 39 GF / 16 (~2.44/90), +24 GD — elite attack even away.
        "away_xg_for": 2.10,
        "away_xg_against": 1.35,
        "away_shots": 14.0,
        "away_sot": 5.2,
        "away_goals_for": 2.25,
        "away_goals_against": 1.45,
        "away_clean_sheets": 2,
        "away_tempo": 0.50,
        "away_width_crossing": 0.55,
        "away_final_third_pressure": 0.65,
    },
]


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _parse_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def select_best_market(prediction: dict) -> dict:
    """
    Pick the highest-value recommendation from the model output.

    Returns a dict with market name, selection, probability, and confidence.
    """
    game = prediction.get("game", {})
    preds = prediction.get("predictions", {})
    goals = prediction.get("goals_analysis", {})
    btts_prob = _parse_float(prediction.get("btts_probability", 0))

    home_win = _parse_float(game.get("home_win_prob", 0))
    draw = _parse_float(game.get("draw_prob", 0))
    away_win = _parse_float(game.get("away_win_prob", 0))

    over_25 = _parse_float(goals.get("over_25_prob", 0))
    over_15 = _parse_float(goals.get("over_15_prob", 0))
    over_35 = _parse_float(goals.get("over_35_prob", 0))

    # Determine the best lean from the model (max probability above its base)
    candidates = []

    # Match outcome
    outcome = max(
        [("1X2: H", home_win), ("1X2: Draw", draw), ("1X2: A", away_win)],
        key=lambda x: x[1],
    )
    candidates.append(
        {
            "market": "1X2",
            "selection": outcome[0],
            "prob": outcome[1],
            "confidence": preds.get("side", {}).get("confidence", 0),
        }
    )

    # Total 2.5
    total_take = max(over_25, 1 - over_25)
    total_side = "Over 2.5" if over_25 >= 0.5 else "Under 2.5"
    candidates.append(
        {
            "market": "Total",
            "selection": total_side,
            "prob": total_take,
            "confidence": preds.get("total", {}).get("confidence", 0),
        }
    )

    # BTTS
    btts_take = max(btts_prob, 1 - btts_prob)
    btts_side = "BTTS Yes" if btts_prob >= 0.5 else "BTTS No"
    candidates.append(
        {
            "market": "BTTS",
            "selection": btts_side,
            "prob": btts_take,
            "confidence": preds.get("btts", {}).get("confidence", 0),
        }
    )

    # Over 1.5
    over_15_take = max(over_15, 1 - over_15)
    over_15_side = "Over 1.5" if over_15 >= 0.5 else "Under 1.5"
    candidates.append(
        {
            "market": "Alt Total",
            "selection": over_15_side,
            "prob": over_15_take,
            "confidence": preds.get("total", {}).get("confidence", 0),
        }
    )

    # Score the candidates: probability above the 50% base decides recommendation.
    # The market with the highest edge over 0.50 is the top pick.
    best = max(candidates, key=lambda c: c["prob"])
    return best


def format_prediction(match: dict, prediction: dict) -> str:
    """Format a single prediction into a readable console block."""
    game = prediction.get("game", {})
    preds = prediction.get("predictions", {})
    goals = prediction.get("goals_analysis", {})
    corners = prediction.get("corners_analysis", {})
    btts_prob = _parse_float(prediction.get("btts_probability", 0))

    home_win = _parse_float(game.get("home_win_prob", 0)) * 100
    draw = _parse_float(game.get("draw_prob", 0)) * 100
    away_win = _parse_float(game.get("away_win_prob", 0)) * 100
    hg = _parse_float(game.get("projected_home_goals", 0))
    ag = _parse_float(game.get("projected_away_goals", 0))
    tg = _parse_float(game.get("projected_total_goals", 0))

    sides = sorted(
        [("Home", home_win), ("Draw", draw), ("Away", away_win)],
        key=lambda x: x[1],
        reverse=True,
    )
    side_lean = sides[0][0]

    lines = []
    lines.append("=" * 70)
    lines.append(f"MATCH: {match['name']} ({match['league']})")
    lines.append("-" * 70)
    lines.append(f"  Projected Score: {match['home_team']} {hg:.2f} - {ag:.2f} {match['away_team']}")
    lines.append(f"  Projected Total Goals: {tg:.2f}")
    lines.append("")
    lines.append("  1X2 Probabilities:")
    lines.append(f"    Home ({match['home_team']}): {home_win:.1f}%")
    lines.append(f"    Draw:                     {draw:.1f}%")
    lines.append(f"    Away ({match['away_team']}): {away_win:.1f}%")
    lines.append(f"    Lean: {side_lean}")
    lines.append("")
    lines.append("  Goals Analysis:")
    lines.append(f"    Over 1.5: {goals.get('over_15_prob', 0) * 100:.1f}%")
    lines.append(f"    Over 2.5: {goals.get('over_25_prob', 0) * 100:.1f}%")
    lines.append(f"    Over 3.5: {goals.get('over_35_prob', 0) * 100:.1f}%")
    lines.append(f"    BTTS Yes: {btts_prob * 100:.1f}%")
    lines.append(f"    Corners:  {corners.get('projection', 0):.1f}")
    lines.append("")
    lines.append("  Model Recommendations:")
    the_best = select_best_market(prediction)
    lines.append(
        f"    ** TOP PICK: {the_best['selection']} "
        f"({the_best['prob'] * 100:.1f}%, conf {the_best['confidence']:.1f}%)"
    )

    total_edge = preds.get("total", {}).get("edge", 0)
    total_conf = preds.get("total", {}).get("confidence", 0)
    total_rec = preds.get("total", {}).get("recommendation", "PASS")
    btts_edge = btts_prob - 0.5  # model doesn't store edge in the btts dict; compute it
    btts_conf = preds.get("btts", {}).get("confidence", 0)
    btts_rec = preds.get("btts", {}).get("recommendation", "PASS")
    lines.append("")
    lines.append("  Betting Recommendations:")
    lines.append(f"    Total:  {total_rec} (edge {total_edge:+.3f}, conf {total_conf:.1f}%)")
    lines.append(f"    BTTS:   {btts_rec} (edge {btts_edge:+.3f}, conf {btts_conf:.1f}%)")
    lines.append("=" * 70)
    return "\n".join(lines)


def _pick_best_market(prediction: dict) -> dict:
    """Compute the single strongest recommendation from the model output."""
    game = prediction.get("game", {})
    preds = prediction.get("predictions", {})
    goals = prediction.get("goals_analysis", {})
    btts = _parse_float(prediction.get("btts_probability", 0))

    home = _parse_float(game.get("home_win_prob", 0))
    draw = _parse_float(game.get("draw_prob", 0))
    away = _parse_float(game.get("away_win_prob", 0))
    o15 = _parse_float(goals.get("over_15_prob", 0))
    o25 = _parse_float(goals.get("over_25_prob", 0))
    o35 = _parse_float(goals.get("over_35_prob", 0))

    # Only the "positive" (lean-oriented) side of each market is considered.
    candidates = [
        ("1X2 Home", home, preds.get("side", {}).get("confidence", 0)),
        ("1X2 Away", away, preds.get("side", {}).get("confidence", 0)),
        ("Over 1.5", o15, preds.get("total", {}).get("confidence", 0)),
        ("Over 2.5", o25, preds.get("total", {}).get("confidence", 0)),
        ("Over 3.5", o35, preds.get("total", {}).get("confidence", 0)),
        ("BTTS Yes", btts, preds.get("btts", {}).get("confidence", 0)),
    ]
    # Pick the market with the highest model probability
    best = max(candidates, key=lambda c: c[1])
    return {"selection": best[0], "prob": best[1], "confidence": best[2]}


def push_match_to_discord(match: dict, prediction: dict, dry_run: bool = False) -> bool:
    """Push a single match prediction to Discord using discord_integration."""
    try:
        from discord_integration import push_soccer_prediction_to_discord, test_webhook
    except ImportError:
        logger.error("discord_integration not available. Cannot push to Discord.")
        return False

    if not dry_run and not test_webhook():
        logger.error("Discord webhook not configured. Check DISCORD_WEBHOOK_URL in .env")
        return False

    return push_soccer_prediction_to_discord(
        match_name=match["name"],
        prediction_data=prediction,
        dry_run=dry_run,
    )


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run SoccerPredictor with seed data offline 3 matches."
    )
    parser.add_argument(
        "--push-discord",
        action="store_true",
        help="Push each prediction to Discord via webhook",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the Discord payload instead of posting",
    )
    args = parser.parse_args()

    logger.info("Initializing SoccerPredictor...")
    predictor = SoccerPredictor(league="default")

    results = []

    for match in MATCHES:
        match_name = match["name"]
        logger.info("Running inference for %s...", match_name)
        print(format_separator := "=" * 70)
        print(f"SERVER: {match_name}")
        print("=" * 70)

        try:
            # Pass only the model-override kwargs (skip the metadata keys)
            override_kwargs = {
                k: v
                for k, v in match.items()
                if k.startswith(("home_", "away_"))
                and k not in ("home_team", "away_team")
            }

            prediction = predictor.predict(
                features=None,
                model=None,
                home_team=match["home_team"],
                away_team=match["away_team"],
                market_line=match.get("market_line", 0.0),
                market_total=match.get("market_total", 2.5),
                league=match.get("league", "default"),
                **override_kwargs,
            )

            # Save JSON output
            out_dir = Path("output/soccer")
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{match['home_team'].replace(' ', '_')}_vs_{match['away_team'].replace(' ', '_')}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(prediction, f, indent=2, default=str)
            logger.info("Saved JSON to %s", out_path)

            # Print formatted output
            print(format_prediction(match, prediction))
            print()

            results.append({"match": match_name, "prediction": prediction})

            # Push to Discord
            if args.push_discord:
                ok = push_match_to_discord(match, prediction, dry_run=args.dry_run)
                logger.info("Discord push %s for %s", "OK" if ok else "FAILED", match_name)

        except Exception as e:
            logger.error("Failed to process %s: %s", match_name, e, exc_info=True)
            print(f"[ERROR] {match_name}: {e}")

    # Wrap-up summary
    print()
    print("=" * 70)
    print("FINAL RECOMMENDATIONS")
    print("=" * 70)
    for match, prediction in zip(MATCHES, results):
        best = _pick_best_market(prediction["prediction"])
        print(f"  {match['name']:<22} -> {best['selection']} ({best['prob']*100:.1f}%)")

    logger.info("Batch complete. %d/3 matches processed successfully.", len(results))


if __name__ == "__main__":
    main()