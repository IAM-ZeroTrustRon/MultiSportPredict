#!/usr/bin/env python
"""
ATP US Open 2026 — Miomir Kecmanovic vs Denis Shapovalov
==========================================================
Runs the real Elo-based tennis model (models/tennis_predictor.py),
routes confidence through core/confidence_engine.py, and pushes the
result to Discord via the dedicated recommendations webhook.

Usage:
    python run_push_kecmanovic_shapovalov_usopen.py          # run + push
    python run_push_kecmanovic_shapovalov_usopen.py --dry-run # print payload only
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
from discord_integration import push_prediction_to_all

# Match config — ATP US Open, hard court, best-of-5 (Grand Slam)
HOME_PLAYER = "Miomir Kecmanovic"
AWAY_PLAYER = "Denis Shapovalov"
SURFACE = "hard"
TOURNAMENT = "US Open"
ROUND = "First Round"
BEST_OF_5 = True


def run_match(dry_run: bool = False) -> dict:
    print("=" * 60)
    print(f"ATP US OPEN — {HOME_PLAYER} vs {AWAY_PLAYER}")
    print("=" * 60)

    # 1) Real model prediction
    result = predict_tennis_match(
        home_player=HOME_PLAYER,
        away_player=AWAY_PLAYER,
        surface=SURFACE,
        best_of_5=BEST_OF_5,
        tournament=TOURNAMENT,
        round_name=ROUND,
        market_prob=None,
        market_home_odds=None,
        market_away_odds=None,
    )

    ml = result.get("moneyline", {})

    # 2) Confidence via core/confidence_engine.py
    model_prob = ml.get("home_win_prob", 0.5)
    implied_market_prob = 0.5  # no market odds available
    model_edge = (model_prob - implied_market_prob) * 100.0
    vol = get_volatility("tennis_moneyline")
    conf_score = confidence_score(model_edge, volatility=vol)
    conf_tier = bet_recommendation(conf_score, "tennis_moneyline")

    # 3) Attach engine-confidence to the result
    result["confidence_score"] = conf_score
    result["confidence_tier"] = conf_tier
    result["surface"] = SURFACE
    result["tournament_name"] = TOURNAMENT
    result["home_player"] = HOME_PLAYER
    result["away_player"] = AWAY_PLAYER

    # 3b) Attach value plays from model output
    sets = result.get("sets", {})
    total_games = result.get("total_games", {})
    set_dist = result.get("set_distribution", {})
    fav_name = ml.get("lean", "coin_flip")

    result["value_plays"] = {
        "original_lean": (
            f"Model favors {fav_name} on hard court US Open. "
            f"Sets expected to go deep — high over probability."
        ),
        "plays": {
            "Spread (Underdog +1.5 Sets)": sets.get("recommendation_spread", ""),
            "Total Sets (Over 3.5)": f"P(over)={sets.get('over_35_prob', 0):.0%}",
            "Total Games (Over 40.5)": total_games.get("recommendation", ""),
        },
        "model_view": {
            "favorite": fav_name,
            "favorite_win_prob": max(model_prob, 1 - model_prob),
            "set_distribution": {
                "Shapovalov 3-1": f"{set_dist.get('1-3', 0):.0%}",
                "Shapovalov 3-2": f"{set_dist.get('2-3', 0):.0%}",
                "Shapovalov 3-0": f"{set_dist.get('0-3', 0):.0%}",
                "Kecmanovic 3-2": f"{set_dist.get('3-2', 0):.0%}",
            },
        },
    }

    # Console output
    print(f"\nTournament: {TOURNAMENT} | Surface: {SURFACE.capitalize()} | Round: {ROUND}")
    print(f"Win Prob:   {HOME_PLAYER} {model_prob:.1%} | {AWAY_PLAYER} {1-model_prob:.1%}")
    print(f"Lean:       {ml.get('lean', '')}")
    print(f"Confidence (core engine): {conf_score:.1f}% — {conf_tier}")
    if sets:
        print(f"Sets O/U:   {sets.get('recommendation_sets_ou', '')}")
        print(f"Spread:     {sets.get('recommendation_spread', '')}")
    if isinstance(total_games, dict):
        print(f"Total games:{total_games.get('recommendation', '')} ({total_games.get('line', '')})")
    elo_ratings = result.get("elo_ratings", {})
    if elo_ratings:
        print(f"Elo:        {HOME_PLAYER}={elo_ratings.get(HOME_PLAYER, 'N/A')} | "
              f"{AWAY_PLAYER}={elo_ratings.get(AWAY_PLAYER, 'N/A')}")
    dr = result.get("dominance_ratio", {})
    if dr:
        print(f"DR:         {HOME_PLAYER}={dr.get(HOME_PLAYER, 'N/A')} | "
              f"{AWAY_PLAYER}={dr.get(AWAY_PLAYER, 'N/A')}")

    # Save output
    out_dir = Path("output/tennis")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{HOME_PLAYER.replace(' ','_')}_vs_{AWAY_PLAYER.replace(' ','_')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nResults saved to: {out_path}")

    # 4) Push to Discord
    print("\nPushing recommendation to Discord...")
    if dry_run:
        print("[DRY RUN] Skipping actual Discord post.")
        return result
    push_prediction_to_all("tennis", result, dry_run=dry_run)
    print("[OK] Discord push attempted (see logs for confirmation).")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="ATP US Open: Kecmanovic vs Shapovalov -> Discord"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print payload without posting")
    args = parser.parse_args()
    run_match(dry_run=args.dry_run)


if __name__ == "__main__":
    main()