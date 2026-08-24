#!/usr/bin/env python
"""
ATP National Bank Open (Montreal Masters 1000) — 3 Matches -> Discord
======================================================================
Runs three Round-of-32 hard-court matches through the real Elo-based tennis
model (models/tennis_predictor.py), routes confidence through
core/confidence_engine.py, attaches the consolidated value-play perspectives
for each match, and pushes all three recommendations to Discord via the
dedicated recommendations webhook.

Matches (Friday, Aug 7 2026, ~12:30 PM EDT, Outdoor Hard, Rogers Court):
    1. Daniel Merida Aguilar vs Alex Michelsen
    2. Zizou Bergs vs Ben Shelton
    3. Learner Tien vs Tommy Paul

Usage:
    python run_montreal_atp_three_matches_to_discord.py            # run + push (all 3)
    python run_montreal_atp_three_matches_to_discord.py --dry-run  # print payloads only
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

# Shared match context — National Bank Open (Montreal), hard court, best-of-3
SURFACE = "hard"
TOURNAMENT = "National Bank Open — Montreal"
ROUND = "Round of 32"
BEST_OF_5 = False

# ---------------------------------------------------------------------------
# Match definitions: (home, away, market_implied_prob_of_home, value_plays)
#
# market_implied_prob is used to compute the model edge vs market. "home" is
# the first-listed name; the favorite may be either side — the model computes it.
# ---------------------------------------------------------------------------
MATCHES = [
    {
        "home_player": "Daniel Merida Aguilar",
        "away_player": "Alex Michelsen",
        # Market: Merida ~27-29%, Michelsen ~71-73% (home = Merida)
        "market_implied_prob": 0.29,
        "market_home_odds": "+250",
        "market_away_odds": "-270",
        "value_plays": {
            "original_lean": "Merida's return edge + hot form can keep this live; "
                            "over the total in a tight baseline battle",
            "plays": {
                "Spread (Michelsen -1.5 Sets)": "-120 ballpark",
                "Total (Over 22.5 games)": "-110",
                "Dog (Merida ML +270)": "small positive-EV if return shows up",
            },
            "deep_dive": {
                "Target": "Alex Michelsen -1.5 Sets (straight sets 2-0)",
                "Angle": "Serve dominance + strength-of-schedule + prior H2H control",
                "Rationale": "Michelsen won 6-3 6-4 at Indian Wells on hard; "
                            "1st-serve win +22 pts; Merida's wins are vs weaker "
                            "opposition (avg opp rank ~174).",
            },
            "model_view": {
                "favorite": "Alex Michelsen",
                "notes": "Serve-dominant favorite; Merida return edge supports Over 22.5",
            },
        },
    },
    {
        "home_player": "Zizou Bergs",
        "away_player": "Ben Shelton",
        # Market: Bergs ~27-32%, Shelton ~68-73% (home = Bergs)
        "market_implied_prob": 0.30,
        "market_home_odds": "+225",
        "market_away_odds": "-275",
        "value_plays": {
            "original_lean": "Shelton's serve monster + Bergs' live return -> one tight set "
                            "likely; lean Over 22.5 and Shelton -3.5 games plus money",
            "plays": {
                "Spread (Shelton -3.5 games)": "+122",
                "Total (Over 22.5 games)": "-108",
                "Favorite (Shelton -1.5 Sets)": "-130 ballpark",
            },
            "deep_dive": {
                "Target": "Ben Shelton -3.5 games / -1.5 sets",
                "Angle": "Strongest serve of all three favorites (career 1st-win 76%)",
                "Rationale": "Shelton YTD 14-5 on hard vs avg opp rank ~198; Bergs returns "
                            "well (career 39%) but his wins are built vs avg opp rank ~453.",
            },
            "model_view": {
                "favorite": "Ben Shelton",
                "notes": "Serve-dominant favorite; Over 22.5 has structural support",
            },
        },
    },
    {
        "home_player": "Learner Tien",
        "away_player": "Tommy Paul",
        # Market: Tien ~40-45%, Paul ~55-60% (home = Tien)
        "market_implied_prob": 0.42,
        "market_home_odds": "+140",
        "market_away_odds": "-165",
        "value_plays": {
            "original_lean": "Closest of the three — Tien's elite return + pressure profile "
                            "(TB 66%, deciding sets 75%) makes him the most dangerous dog; "
                            "lean Over 22.5 and TB Yes",
            "plays": {
                "Total (Over 22.5 games)": "-110",
                "Tiebreak (Yes, any set)": "value play",
                "Dog (Tien ML +140)": "small positive-EV if pressure model weighted",
            },
            "deep_dive": {
                "Target": "Over 22.5 games / Tien +1.5 sets live dog",
                "Angle": "Tien is the elite returner + best pressure player across all three",
                "Rationale": "Prior H2H at Delray was extremely close (4-6 6-4 6-3); Tien "
                            "won Washington coming in; Paul has the serve and schedule edge "
                            "but Tien neutralizes with return quality.",
            },
            "model_view": {
                "favorite": "Tommy Paul",
                "notes": "Most balanced match; Tien is the most dangerous dog of the trio",
            },
        },
    },
]


def run_match(cfg: dict, dry_run: bool = False) -> dict:
    home = cfg["home_player"]
    away = cfg["away_player"]
    market_prob = cfg.get("market_implied_prob")
    print("=" * 60)
    print(f"ATP MONTREAL — {home} vs {away}")
    print("=" * 60)

    # 1) Real model prediction
    result = predict_tennis_match(
        home_player=home,
        away_player=away,
        surface=SURFACE,
        best_of_5=BEST_OF_5,
        tournament=TOURNAMENT,
        round_name=ROUND,
        market_prob=market_prob,
        market_home_odds=cfg.get("market_home_odds"),
        market_away_odds=cfg.get("market_away_odds"),
    )

    ml = result.get("moneyline", {})

    # 2) Confidence via core/confidence_engine.py
    model_prob = ml.get("home_win_prob", 0.5)
    implied_market_prob = market_prob if market_prob is not None else 0.5
    model_edge = (model_prob - implied_market_prob) * 100.0
    vol = get_volatility("tennis_moneyline")
    conf_score = confidence_score(model_edge, volatility=vol)
    conf_tier = bet_recommendation(conf_score, "tennis_moneyline")

    # 3) Attach engine-confidence + context to the result
    result["confidence_score"] = conf_score
    result["confidence_tier"] = conf_tier
    result["surface"] = SURFACE
    result["tournament_name"] = TOURNAMENT
    result["home_player"] = home
    result["away_player"] = away
    result["value_plays"] = cfg["value_plays"]
    result["value_plays"]["model_view"]["favorite_win_prob"] = max(
        model_prob, 1 - model_prob
    )

    # Console output
    print(f"Tournament: {TOURNAMENT} | Surface: {SURFACE.capitalize()} | Round: {ROUND}")
    print(f"Win Prob:   {home} {model_prob:.1%} | {away} {1-model_prob:.1%}")
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
        print(f"Elo:        {home}={elo.get(home,'N/A'):.0f} | "
              f"{away}={elo.get(away,'N/A'):.0f}")
    dr = result.get("dominance_ratio", {})
    if dr:
        print(f"DR:         {home}={dr.get(home,'N/A')} | "
              f"{away}={dr.get(away,'N/A')}")

    # Save output
    out_dir = Path("output/tennis")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{home.replace(' ','_')}_vs_{away.replace(' ','_')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nResults saved to: {out_path}")

    # 4) Push to Discord
    print("\nPushing recommendation to Discord...")
    if dry_run:
        print("[DRY RUN] Skipping actual Discord post.")
        return result
    push_recommendation_to_discord(result, dry_run=False)
    print("[OK] Discord push attempted (see logs for confirmation).\n")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="ATP Montreal 3 matches -> Discord"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print payloads without posting")
    args = parser.parse_args()

    print(f"\n=== ATP MONTREAL 3-MATCH REPORT ({len(MATCHES)} matches) ===")
    for cfg in MATCHES:
        run_match(cfg, dry_run=args.dry_run)

    print("=" * 60)
    print("ALL MATCHES PROCESSED.")
    print("=" * 60)


if __name__ == "__main__":
    main()
