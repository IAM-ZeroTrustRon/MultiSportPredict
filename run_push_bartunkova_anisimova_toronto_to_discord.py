#!/usr/bin/env python
"""
WTA Toronto 2026 — Nikola Bartunkova vs Amanda Anisimova
=========================================================
Runs the real Elo-based tennis model (models/tennis_predictor.py),
routes confidence through core/confidence_engine.py, and pushes the
result to Discord via the dedicated recommendations webhook.

Usage:
    python run_push_bartunkova_anisimova_toronto_to_discord.py          # run + push
    python run_push_bartunkova_anisimova_toronto_to_discord.py --dry-run # print payload only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
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

# Match config — WTA Toronto (National Bank Open), hard court, best-of-3
HOME_PLAYER = "Nikola Bartunkova"
AWAY_PLAYER = "Amanda Anisimova"
SURFACE = "hard"
TOURNAMENT = "National Bank Open"
ROUND = "Round of 32"
BEST_OF_5 = False


def run_match(dry_run: bool = False) -> dict:
    print("=" * 60)
    print(f"WTA TORONTO — {HOME_PLAYER} vs {AWAY_PLAYER}")
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

    # 3b) Attach both value-play perspectives discussed for this match.
    #     1) Original value plays (underdog spread + over total + set lean)
    #     2) Deep-dive plays (favorite straight sets + under total)
    #     These are presented alongside the raw Elo model output for context.
    result["value_plays"] = {
        "original_lean": "Bartunkova +3.5 games keeps it competitive; "
                        "over the total in a tight baseline battle",
        "plays": {
            "Spread (Bartunkova +3.5 games)": "-120",
            "Total (Over 21.5 games)": "-105",
            "Set Lean (Anisimova 2-1 or Bartunkova +1.5 sets)": "+280 ballpark",
        },
        "deep_dive": {
            "Target": "Amanda Anisimova -1.5 Sets (straight sets 2-0)",
            "Angle": "Under total games (early breaks in both sets)",
            "Rationale": "Rested top-10 firepower vs a rising unseeded defender",
        },
        "model_view": {
            "favorite": ml.get("lean", "coin_flip") or "coin_flip",
            "favorite_win_prob": max(model_prob, 1 - model_prob),
            "notes": "Elo model favors Anisimova; total model leans UNDER at 22.5",
        },
    }

    # Console output
    print(f"Tournament: {TOURNAMENT} | Surface: {SURFACE.capitalize()} | Round: {ROUND}")
    print(f"Win Prob:   {HOME_PLAYER} {model_prob:.1%} | {AWAY_PLAYER} {1-model_prob:.1%}")
    print(f"Lean:       {ml.get('lean','')}")
    print(f"Confidence (core engine): {conf_score:.1f}% — {conf_tier}")
    sets = result.get("sets", {})
    if sets:
        print(f"Sets O/U:   {sets.get('recommendation_sets_ou','')}")
        print(f"Spread:     {sets.get('recommendation_spread','')}")
    tg = result.get("total_games", {})
    if isinstance(tg, dict):
        print(f"Total games:{tg.get('recommendation','')} ({tg.get('line','')})")
    elo = result.get("elo_ratings", {})
    if elo:
        print(f"Elo:        {HOME_PLAYER}={elo.get(HOME_PLAYER,'N/A'):.0f} | "
              f"{AWAY_PLAYER}={elo.get(AWAY_PLAYER,'N/A'):.0f}")
    dr = result.get("dominance_ratio", {})
    if dr:
        print(f"DR:         {HOME_PLAYER}={dr.get(HOME_PLAYER,'N/A')} | "
              f"{AWAY_PLAYER}={dr.get(AWAY_PLAYER,'N/A')}")

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
    push_recommendation_to_discord(result, dry_run=False)
    print("[OK] Discord push attempted (see logs for confirmation).")

    return result


def main():
    parser = argparse.ArgumentParser(description="WTA Toronto: Bartunkova vs Anisimova -> Discord")
    parser.add_argument("--dry-run", action="store_true", help="Print payload without posting")
    args = parser.parse_args()
    run_match(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
