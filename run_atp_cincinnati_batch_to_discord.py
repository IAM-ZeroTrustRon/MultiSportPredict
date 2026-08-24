#!/usr/bin/env python
"""
ATP Cincinnati Open - Today's Batch -> Discord (Strong Picks Only)
====================================================================
Runs today's (Aug 18, 2026) ATP Cincinnati Round-of-3 hard-court matches
through the real Elo-based tennis model (models/tennis_predictor.py),
routes confidence through core/confidence_engine.py, and pushes ONLY
recommendations that reach the STRONG BET tier (confidence >= 72 for
tennis_moneyline) to Discord via the dedicated recommendations webhook.

Usage:
    python run_atp_cincinnati_batch_to_discord.py              # run + push
    python run_atp_cincinnati_batch_to_discord.py --dry-run    # print payloads only
    python run_atp_cincinnati_batch_to_discord.py --no-push    # console only, no Discord
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
from core.confidence_engine import (
    confidence_score,
    bet_recommendation,
    get_volatility,
    get_thresholds,
)
from discord_integration import push_recommendation_to_discord

# ---------------------------------------------------------------------------
# Match context — ATP Cincinnati Open, hard court, best-of-3
# ---------------------------------------------------------------------------
SURFACE = "hard"
TOURNAMENT = "ATP Cincinnati Open"
ROUND = "Round 3"
BEST_OF_5 = False

# --- Matchups for today (Tue Aug 18, 2026) ---
# Market odds are not available for today's slate; the model will run on raw Elo.
MATCHES = [
    {
        "home_player": "Nuno Borges",
        "away_player": "Andrey Rublev",
        "market_prob": None,
        "market_home_odds": None,
        "market_away_odds": None,
        "value_plays": {
            "original_lean": "Rublev is the higher-ranked seed with more surface "
                            "form; Borges is a solid hard-court player, but the "
                            "model sees a dry edge.",
            "plays": {},
            "deep_dive": {
                "Target": "El-Model dry-run recommendation based on surface Elo.",
                "Angle": "Elo surface gap + seeded form",
                "Rationale": "No market odds available for automated pipeline "
                             "in this environment; treating market as efficient.",
            },
            "model_view": {
                "favorite": "",
                "notes": "Confidence computed from model-vs-market edge "
                         "(market prob defaults 50%).",
            },
        },
    },
    {
        "home_player": "Lorenzo Musetti",
        "away_player": "Michael Zheng",
        "market_prob": None,
        "market_home_odds": None,
        "market_away_odds": None,
        "value_plays": {
            "original_lean": "Musetti has the higher profile, but Zheng is in-form.",
            "plays": {},
            "deep_dive": {
                "Target": "Model edge from Elo",
                "Angle": "Elo surface-gap dry-run",
                "Rationale": "No market odds available; model runs off Elo ratings.",
            },
            "model_view": {
                "favorite": "",
                "notes": "Model computed from Elo surface data.",
            },
        },
    },
    {
        "home_player": "Daniel Merida",
        "away_player": "Taylor Fritz",
        "market_prob": None,
        "market_home_odds": None,
        "market_away_odds": None,
        "value_plays": {
            "original_lean": "Merida has been solid on hard courts this summer, "
                            "but Fritz has the higher ceiling and more overall "
                            "surface experience in big Masters matches.",
            "plays": {},
            "deep_dive": {
                "Target": "Model edge from Elo",
                "Angle": "Elo surface rating dry-run",
                "Rationale": "No market odds available; model dry-run.",
            },
            "model_view": {
                "favorite": "",
                "notes": "Model computed from Elo surface data.",
            },
        },
    },
    {
        "home_player": "Daniil Medvedev",
        "away_player": "Brandon Nakashima",
        "market_prob": None,
        "market_home_odds": None,
        "market_away_odds": None,
        "value_plays": {
            "original_lean": "Dry-run based on Elo.",
            "plays": {},
            "deep_dive": {
                "Target": "Model edge from Elo",
                "Angle": "Elo surface rating dry-run",
                "Rationale": "No market odds available; model dry-run.",
            },
            "model_view": {
                "favorite": "",
                "notes": "Model computed from Elo surface data.",
            },
        },
    },
    {
        "home_player": "Adam Walton",
        "away_player": "Jaime Faria",
        "market_prob": None,
        "market_home_odds": None,
        "market_away_odds": None,
        "value_plays": {
            "original_lean": "Dry-run.",
            "plays": {},
            "deep_dive": {
                "Target": "Model edge from Elo",
                "Angle": "Elo surface rating dry-run",
                "Rationale": "No market odds available; model dry-run.",
            },
            "model_view": {
                "favorite": "",
                "notes": "Model computed from Elo surface data.",
            },
        },
    },
    {
        "home_player": "Felix Auger-Aliassime",
        "away_player": "Juan Manuel Cerundolo",
        "market_prob": None,
        "market_home_odds": None,
        "market_away_odds": None,
        "value_plays": {
            "original_lean": "Dry-run.",
            "plays": {},
            "deep_dive": {
                "Target": "Model edge from Elo",
                "Angle": "Elo surface rating dry-run",
                "Rationale": "No market odds available; model dry-run.",
            },
            "model_view": {
                "favorite": "",
                "notes": "Model computed from Elo surface data.",
            },
        },
    },
]


def _american_to_prob(odds: str) -> float:
    """Convert American odds string to implied win probability."""
    if odds is None:
        return 0.5
    v = int(odds.replace("+", ""))
    if v < 0:
        dec = 1 + (100 / abs(v))
    else:
        dec = 1 + (v / 100)
    return 1.0 / dec if dec > 1 else 0.5


def run_match(cfg: dict, dry_run: bool = False, push: bool = True) -> dict:
    """Run a single match prediction, compute confidence, push if STRONG."""
    home = cfg["home_player"]
    away = cfg["away_player"]
    market_prob = cfg.get("market_prob")
    market_home_odds = cfg.get("market_home_odds")
    market_away_odds = cfg.get("market_away_odds")

    # If market_prob not set but odds provided, derive it
    if market_prob is None and market_home_odds and market_away_odds:
        ph = _american_to_prob(market_home_odds)
        pa = _american_to_prob(market_away_odds)
        market_prob = ph / (ph + pa) if (ph + pa) > 0 else 0.5

    print("=" * 60)
    print(f"ATP CINCINNATI — {home} vs {away}")
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
        market_home_odds=market_home_odds,
        market_away_odds=market_away_odds,
    )

    ml = result.get("moneyline", {})
    model_prob = ml.get("home_win_prob", 0.5)

    # 2) Confidence via core/confidence_engine.py
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
    if result["value_plays"]["model_view"].get("favorite") in (None, ""):
        result["value_plays"]["model_view"]["favorite"] = ml.get("lean", "coin_flip") or "coin_flip"
    result["value_plays"]["model_view"]["favorite_win_prob"] = max(model_prob, 1 - model_prob)

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

    # 4) Push to Discord — ONLY if STRONG BET
    if conf_tier == "STRONG BET":
        print("\n[STRONG BET] Pushing to Discord...")
        if dry_run:
            print("[DRY RUN] Skipping actual Discord post.")
        elif push:
            push_recommendation_to_discord(result, dry_run=False)
            print("[OK] Discord push attempted (see logs for confirmation).")
        else:
            print("[SKIP] --no-push specified. Not posting to Discord.")
    else:
        print(f"\n[SKIP] {conf_tier} - Below STRONG threshold ({get_thresholds('tennis_moneyline')['strong']}). Skipping Discord push.")
        print(f"    (Threshold: {get_thresholds('tennis_moneyline')['strong']} for STRONG BET)")

    print()
    return result


def main():
    parser = argparse.ArgumentParser(
        description="ATP Cincinnati batch -> Discord (STRONG picks only)"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print payloads without posting")
    parser.add_argument("--no-push", action="store_true",
                        help="Do not push to Discord (console only)")
    args = parser.parse_args()

    print(f"\n=== ATP CINCINNATI BATCH ({len(MATCHES)} matches) ===")
    print("Pushing ONLY STRONG BET recommendations to Discord.")
    print("=" * 60)

    results = []
    for cfg in MATCHES:
        r = run_match(cfg, dry_run=args.dry_run, push=not args.no_push)
        results.append(r)

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for r in results:
        ml = r.get("moneyline", {})
        home = r.get("home_player", "?")
        away = r.get("away_player", "?")
        tier = r.get("confidence_tier", "N/A")
        prob = ml.get("home_win_prob", 0.5)
        print(f"  {home} vs {away}: {prob:.1%} / {1-prob:.1%} | "
              f"conf={r.get('confidence_score', 0):.1f}% | {tier}")

    strong = [r for r in results if r.get("confidence_tier") == "STRONG BET"]
    print(f"\n  Strong picks pushed: {len(strong)}/{len(results)}")

    print("=" * 60)
    print("ALL MATCHES PROCESSED.")
    print("=" * 60)


if __name__ == "__main__":
    main()