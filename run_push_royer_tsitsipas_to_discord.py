#!/usr/bin/env python
"""
ATP Masters Event — Valentin Royer vs Stefanos Tsitsipas
=========================================================
Runs the real Elo-based tennis model (models/tennis_predictor.py),
routes confidence through core/confidence_engine.py, and pushes the
result to Discord via the dedicated recommendations webhook.

This script simulates a matchup between a top-tier player and a challenger,
drawing analytical inspiration from similar past analyses.

Usage:
    python run_push_royer_tsitsipas_to_discord.py          # run + push
    python run_push_royer_tsitsipas_to_discord.py --dry-run # print payload only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Ensure project root on sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv("c:/MultiSportPredict/.env")

from models.tennis_predictor import predict_tennis_match
from core.confidence_engine import confidence_score, bet_recommendation, get_volatility
from discord_integration import push_recommendation_to_discord

# Match config — Assuming a hard court Masters event, best-of-3
HOME_PLAYER = "Valentin Royer"
AWAY_PLAYER = "Stefanos Tsitsipas"
SURFACE = "hard"
TOURNAMENT = "ATP Masters Event"
ROUND = "Round of 64"
BEST_OF_5 = False


def run_match(dry_run: bool = False) -> dict:
    print("=" * 60)
    print(f"ATP MASTERS — {HOME_PLAYER} vs {AWAY_PLAYER}")
    print("=" * 60)

    # Market odds imply Tsitsipas is a heavy favorite.
    # Royer ~15% win prob, Tsitsipas ~85%.
    market_prob_home = 0.15
    market_home_odds = "+550"
    market_away_odds = "-800"

    # 1) Real model prediction
    result = predict_tennis_match(
        home_player=HOME_PLAYER,
        away_player=AWAY_PLAYER,
        surface=SURFACE,
        best_of_5=BEST_OF_5,
        tournament=TOURNAMENT,
        round_name=ROUND,
        market_prob=market_prob_home,
        market_home_odds=market_home_odds,
        market_away_odds=market_away_odds,
    )

    ml = result.get("moneyline", {})

    # 2) Confidence via core/confidence_engine.py
    model_prob = ml.get("home_win_prob", 0.5)
    model_edge = (model_prob - market_prob_home) * 100.0
    vol = get_volatility("tennis_moneyline")
    conf_score = confidence_score(model_edge, volatility=vol)
    conf_tier = bet_recommendation(conf_score, "tennis_moneyline")

    # 3) Attach engine-confidence and analytical context to the result
    result["confidence_score"] = conf_score
    result["confidence_tier"] = conf_tier
    result["surface"] = SURFACE
    result["tournament_name"] = TOURNAMENT
    result["home_player"] = HOME_PLAYER
    result["away_player"] = AWAY_PLAYER

    # 3b) Attach value-play perspectives, similar to the Tsitsipas vs Buse analysis.
    result["value_plays"] = {
        "original_lean": "Tsitsipas to dominate, but moneyline is unplayable. "
                        "Focus on props: set spread and under total games.",
        "plays": {
            "Set Spread (Tsitsipas -1.5 Sets)": "-200",
            "Total Games (Under 20.5)": "-110",
            "Player Prop (Tsitsipas Aces Over 8.5)": "-115",
        },
        "deep_dive": {
            "Target": "Tsitsipas 2-0 (straight sets)",
            "Angle": "Under total games",
            "Rationale": "Significant gap in ranking, experience, and serving power. "
                         "Royer lacks the weapons to consistently hold serve against a Top 15 player. "
                         "Expect scores like 6-3, 6-2.",
        },
        "model_view": {
            "favorite": ml.get("lean", "coin_flip") or "coin_flip",
            "favorite_win_prob": max(model_prob, 1 - model_prob),
            "notes": "Elo model heavily favors Tsitsipas. The value is in how efficiently he wins, not if.",
        },
    }

    # 4) Push to Discord
    print("\nPushing recommendation to Discord...")
    push_recommendation_to_discord(result, dry_run=dry_run)
    print("[OK] Discord push attempted (see logs for confirmation).")

    return result


def main():
    parser = argparse.ArgumentParser(description="ATP Masters: Royer vs Tsitsipas -> Discord")
    parser.add_argument("--dry-run", action="store_true", help="Print payload without posting")
    args = parser.parse_args()
    run_match(dry_run=args.dry_run)


if __name__ == "__main__":
    main()