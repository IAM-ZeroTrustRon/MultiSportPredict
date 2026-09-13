#!/usr/bin/env python
"""
Run Two Soccer Matches Through predict_match.py Model -> Discord
=================================================================
Runs the following matches through the SoccerPredictor (Bivariate Poisson
+ Dixon-Coles) model, routes confidence through core/confidence_engine.py,
produces recommended strong bets, and pushes them to Discord:

  1. FC Urartu vs FC Syunik (Armenian Premier League)
  2. Tobol Kostanay vs Partizan Belgrade (UEFA Conference League - 3rd Qual)

Seed data (team metrics) is derived from the provided market analysis to
inform the model's xG / shot / tempo inputs.

Usage:
    python run_urartu_syunik_tobol_partizan_to_discord.py            # run + push
    python run_urartu_syunik_tobol_partizan_to_discord.py --dry-run  # print payloads only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

# Ensure project root on sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv("c:/MultiSportPredict/.env")

from models.soccer_predictor import SoccerPredictor
from core.confidence_engine import confidence_score, bet_recommendation, get_volatility

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# ---------------------------------------------------------------------------
# MATCH DEFINITIONS (seed data informed team metrics)
# ---------------------------------------------------------------------------
MATCHES = [
    {
        "league": "Armenian Premier League",
        "home": "FC Urartu",
        "away": "FC Syunik",
        "market_total": 2.5,
        "market_context": {
            "home_ml_implied": 0.714,
            "draw_implied": 0.211,
            "away_ml_implied": 0.154,
            "home_odds": "-250",
            "draw_odds": "+375",
            "away_odds": "+550",
        },
        "team_metrics": {
            # Urartu: heavyweight, possession-dominant, strong defense
            "home_xg_for": 1.85,
            "home_xg_against": 0.75,
            "home_shots": 14.5,
            "home_sot": 5.0,
            "home_goals_for": 1.8,
            "home_goals_against": 0.8,
            "home_clean_sheets": 5,
            "home_tempo": 0.55,
            "home_width_crossing": 0.60,
            "home_final_third_pressure": 0.60,
            # Syunik: low block, minimal scoring threat
            "away_xg_for": 0.55,
            "away_xg_against": 1.80,
            "away_shots": 7.5,
            "away_sot": 2.2,
            "away_goals_for": 0.55,
            "away_goals_against": 1.75,
            "away_clean_sheets": 1,
            "away_tempo": 0.10,
            "away_width_crossing": 0.40,
            "away_final_third_pressure": 0.30,
        },
        "analytical_bets": [
            {
                "name": "FC Urartu Moneyline",
                "odds": "-250",
                "reason": "Heavyweight vs lower-tier side; secure parlay leg.",
            },
            {
                "name": "Under 2.5 Goals",
                "odds": "N/A",
                "reason": "Correct score markets favor 2-0 / 1-0; Syunik low block limits chances.",
            },
            {
                "name": "BTTS No",
                "odds": "N/A",
                "reason": "Syunik scoring odds exceptionally low; Urartu clean sheet highly probable.",
            },
        ],
    },
    {
        "league": "UEFA Conference League - 3rd Qual",
        "home": "Tobol Kostanay",
        "away": "Partizan Belgrade",
        "market_total": 2.5,
        "market_context": {
            "home_ml_implied": 0.348,
            "draw_implied": 0.308,
            "away_ml_implied": 0.465,
            "home_odds": "+187",
            "draw_odds": "+225",
            "away_odds": "+115",
        },
        "team_metrics": {
            # Tobol: struggling, must push forward (negative game script)
            "home_xg_for": 1.05,
            "home_xg_against": 1.50,
            "home_shots": 10.0,
            "home_sot": 3.5,
            "home_goals_for": 0.95,
            "home_goals_against": 1.55,
            "home_clean_sheets": 2,
            "home_tempo": 0.40,
            "home_width_crossing": 0.50,
            "home_final_third_pressure": 0.50,
            # Partizan: phenomenal form (WLWWWW), leads 3-0 aggregate
            "away_xg_for": 1.70,
            "away_xg_against": 0.90,
            "away_shots": 13.0,
            "away_sot": 4.5,
            "away_goals_for": 1.80,
            "away_goals_against": 0.90,
            "away_clean_sheets": 4,
            "away_tempo": 0.40,
            "away_width_crossing": 0.55,
            "away_final_third_pressure": 0.55,
        },
        "analytical_bets": [
            {
                "name": "Partizan Belgrade to Score First",
                "odds": "-125",
                "reason": "Partizan in phenomenal form; Tobol must push forward leaving transition space.",
            },
            {
                "name": "BTTS Yes",
                "odds": "-200",
                "reason": "Tobol pushing for 3-goal deficit creates open game; Partizan efficient in transition.",
            },
        ],
    },
]


def run_model(cfg: dict) -> dict:
    """Run a match through the SoccerPredictor model with seed-data metrics."""
    predictor = SoccerPredictor(league=cfg["league"])
    result = predictor.predict(
        features=None,
        model=None,
        home_team=cfg["home"],
        away_team=cfg["away"],
        market_line=0.0,
        market_total=cfg["market_total"],
        **cfg["team_metrics"],
    )
    return result


def compute_confidence(result: dict, cfg: dict) -> dict:
    """Compute confidence scores for each market using core/confidence_engine.py."""
    game = result["game"]
    preds = result["predictions"]

    # 1) Moneyline / Sides confidence
    home_prob = game["home_win_prob"]
    away_prob = game["away_win_prob"]
    draw_prob = game["draw_prob"]
    market_home = cfg["market_context"]["home_ml_implied"]
    market_away = cfg["market_context"]["away_ml_implied"]

    # Model edge vs market for the favorite side
    if home_prob >= away_prob:
        model_side_prob = home_prob
        market_side_prob = market_home
        side_team = cfg["home"]
    else:
        model_side_prob = away_prob
        market_side_prob = market_away
        side_team = cfg["away"]

    side_edge = (model_side_prob - market_side_prob) * 100.0
    side_vol = get_volatility("soccer_sides")
    side_conf = confidence_score(side_edge, volatility=side_vol)
    side_rec = bet_recommendation(side_conf, "soccer_sides")

    # 2) Total goals confidence
    total_edge = preds["total"]["edge"]
    total_vol = get_volatility("soccer_totals")
    total_conf = confidence_score(total_edge, volatility=total_vol)
    total_rec = bet_recommendation(total_conf, "soccer_totals")

    # 3) BTTS confidence
    btts_prob = result["btts_probability"]
    btts_edge = (btts_prob - 0.5) * 100.0
    btts_vol = get_volatility("soccer_btts")
    btts_conf = confidence_score(btts_edge, volatility=btts_vol)
    btts_rec = bet_recommendation(btts_conf, "soccer_btts")

    return {
        "side": {
            "team": side_team,
            "model_prob": model_side_prob,
            "market_prob": market_side_prob,
            "edge_pct": side_edge,
            "confidence": side_conf,
            "recommendation": side_rec,
        },
        "total": {
            "model_total": preds["total"]["model_total_xg"],
            "market_total": cfg["market_total"],
            "edge": total_edge,
            "confidence": total_conf,
            "recommendation": total_rec,
        },
        "btts": {
            "probability": btts_prob,
            "edge_pct": btts_edge,
            "confidence": btts_conf,
            "recommendation": btts_rec,
        },
    }


def build_embed(cfg: dict, result: dict, conf: dict) -> dict:
    """Build a rich Discord embed for a match's strong bet recommendations."""
    game = result["game"]
    preds = result["predictions"]

    # Probability table
    probs = (
        f"**1X2**\n"
        f"🏠 {cfg['home']}: {game['home_win_prob']*100:.1f}%\n"
        f"🤝 Draw: {game['draw_prob']*100:.1f}%\n"
        f"✈️ {cfg['away']}: {game['away_win_prob']*100:.1f}%\n\n"
        f"**Markets**\n"
        f"⚽ Over 2.5: {result['goals_analysis']['over_25_prob']*100:.1f}%\n"
        f"🤝 BTTS Yes: {result['btts_probability']*100:.1f}%\n"
        f"📐 Corners: {result['corner_projection']:.1f}"
    )

    expected_goals = (
        f"🏠 {cfg['home']} xG: {game['projected_home_goals']:.2f}\n"
        f"✈️ {cfg['away']} xG: {game['projected_away_goals']:.2f}\n"
        f"📈 Expected Total: {game['projected_total_goals']:.2f}"
    )

    # Confidence summary
    conf_lines = []
    side = conf["side"]
    conf_lines.append(
        f"**{side['team']} ML** — {side['confidence']:.1f}% ({side['recommendation']})\n"
        f"   └─ Model {side['model_prob']*100:.1f}% vs Market {side['market_prob']*100:.1f}% "
        f"(Edge {side['edge_pct']:+.1f}%)"
    )
    total = conf["total"]
    conf_lines.append(
        f"**Total O/U {total['market_total']}** — {total['confidence']:.1f}% ({total['recommendation']})\n"
        f"   └─ Model {total['model_total']:.2f} vs Line {total['market_total']} "
        f"(Edge {total['edge']:+.2f})"
    )
    btts = conf["btts"]
    conf_lines.append(
        f"**BTTS** — {btts['confidence']:.1f}% ({btts['recommendation']})\n"
        f"   └─ Yes {btts['probability']*100:.1f}% (Edge {btts['edge_pct']:+.1f}%)"
    )
    confidence_section = "\n\n".join(conf_lines)

    # Strong bet recommendations
    rec_lines = []
    for i, rec in enumerate(cfg["analytical_bets"], 1):
        rec_lines.append(
            f"**{i}. {rec['name']}**\n"
            f"   └─ Odds: {rec['odds']}\n"
            f"      {rec['reason']}"
        )
    recommendations = "\n\n".join(rec_lines)

    embed = {
        "title": f"⚽ {cfg['home'].upper()} vs {cfg['away'].upper()}",
        "description": f"**{cfg['league']}** — Model Analysis & Strong Bets",
        "color": 3066993,  # Green
        "fields": [
            {
                "name": "📊 Model Probabilities",
                "value": probs,
                "inline": True,
            },
            {
                "name": "🎯 Expected Goals Model",
                "value": expected_goals,
                "inline": True,
            },
            {
                "name": "📈 Confidence (Core Engine)",
                "value": confidence_section,
                "inline": False,
            },
            {
                "name": "💰 Recommended Strong Bets",
                "value": recommendations,
                "inline": False,
            },
        ],
        "footer": {"text": "MultiSportPredict • Model-Driven Betting Guide"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return embed


def push_to_discord(embeds: list) -> bool:
    """Push all match embeds to Discord."""
    if not WEBHOOK_URL or WEBHOOK_URL == "None":
        print("ERROR: DISCORD_WEBHOOK_URL not set in .env file")
        return False

    success_count = 0
    total = len(embeds)

    for embed in embeds:
        payload = {"embeds": [embed]}
        try:
            resp = requests.post(
                WEBHOOK_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            if resp.status_code in (200, 204):
                print(f"✅ Pushed {embed['title']} to Discord.")
                success_count += 1
            else:
                print(
                    f"❌ Failed to push {embed['title']}: "
                    f"HTTP {resp.status_code} — {resp.text[:200]}"
                )
        except Exception as exc:
            print(f"❌ Error pushing {embed['title']}: {exc}")

    print(f"\n{'✅' if success_count == total else '⚠️'}  "
          f"Pushed {success_count}/{total} match embeds to Discord.")
    return success_count == total


def main():
    parser = argparse.ArgumentParser(
        description="Run 2 soccer matches through model -> Discord"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print payloads without posting")
    args = parser.parse_args()

    print("=" * 70)
    print("SOCCER MODEL ANALYSIS -> DISCORD (2 MATCHES)")
    print("=" * 70)

    embeds = []
    for cfg in MATCHES:
        print(f"\n--- {cfg['home']} vs {cfg['away']} ({cfg['league']}) ---")

        # 1) Run the model
        result = run_model(cfg)
        game = result["game"]
        print(f"Projected: {cfg['home']} {game['projected_home_goals']:.2f} "
              f"- {cfg['away']} {game['projected_away_goals']:.2f}")
        print(f"Win Prob:  {cfg['home']} {game['home_win_prob']:.1%} | "
              f"Draw {game['draw_prob']:.1%} | "
              f"{cfg['away']} {game['away_win_prob']:.1%}")
        print(f"BTTS:      {result['btts_probability']:.1%}")
        print(f"Over 2.5:  {result['goals_analysis']['over_25_prob']:.1%}")
        print(f"Corners:   {result['corner_projection']:.1f}")

        # 2) Compute confidence via core engine
        conf = compute_confidence(result, cfg)
        print(f"Confidence: ML {conf['side']['confidence']:.1f}% "
              f"({conf['side']['recommendation']}) | "
              f"Total {conf['total']['confidence']:.1f}% "
              f"({conf['total']['recommendation']}) | "
              f"BTTS {conf['btts']['confidence']:.1f}% "
              f"({conf['btts']['recommendation']})")

        # 3) Build embed
        embed = build_embed(cfg, result, conf)
        embeds.append(embed)

        # Save output
        out_dir = Path("output/soccer")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{cfg['home'].replace(' ', '_')}_vs_{cfg['away'].replace(' ', '_')}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"Results saved to: {out_path}")

    # 4) Push to Discord
    print("\n" + "=" * 70)
    if args.dry_run:
        print("[DRY RUN] Printing payloads without posting...")
        for embed in embeds:
            print(json.dumps({"embeds": [embed]}, indent=2, default=str))
        print("\n[DRY RUN] Complete.")
    else:
        push_to_discord(embeds)

    print("=" * 70)
    print("ALL MATCHES PROCESSED.")


if __name__ == "__main__":
    main()