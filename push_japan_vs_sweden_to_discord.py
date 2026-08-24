#!/usr/bin/env python
"""Run model for Japan vs Sweden and push prediction to Discord.

Usage:
  python push_japan_vs_sweden_to_discord.py [--league "World Cup"] [--market-total 2.5] [--market-line 0.25]

Env:
  DISCORD_WEBHOOK_URL must be set (or in .env)
"""

import os
import argparse

from dotenv import load_dotenv

load_dotenv()


def build_payload(result: dict, league: str) -> tuple[str, float, str, float, float]:
    """Create (recommendation, confidence, edge, projected_total, btts_prob)."""
    game = result.get("game", {})
    predictions = result.get("predictions", {})

    # Main recommendation: choose the strongest among side/total/btts by confidence
    side = predictions.get("side", {})
    total = predictions.get("total", {})
    btts = predictions.get("btts", {})

    candidates = [
        (side.get("recommendation", "PASS"), float(side.get("confidence", 50.0)), str(side.get("edge", 0.0))),
        (total.get("recommendation", "PASS"), float(total.get("confidence", 50.0)), str(total.get("edge", 0.0))),
        (btts.get("recommendation", "PASS"), float(btts.get("confidence", 50.0)), str(btts.get("probability", 0.0))),
    ]
    candidates_sorted = sorted(candidates, key=lambda x: x[1], reverse=True)
    recommendation, confidence, edge = candidates_sorted[0]

    projected_total = float(game.get("projected_total_goals", 0.0))
    btts_prob = float(result.get("btts_probability", predictions.get("btts", {}).get("probability", 0.0)) or 0.0)

    # normalize edge string
    try:
        edge_val = float(edge)
        edge_str = f"{edge_val:+.3f}" if edge_val != 0 else "+0.000"
    except Exception:
        edge_str = str(edge)

    return recommendation, confidence, edge_str, projected_total, btts_prob


def push(result: dict, webhook_url: str, home: str, away: str, league: str, market_total: float, market_line: float) -> bool:
    """Push via existing webhook helper."""
    from universal_runner import push_to_discord

    game = result.get("game", {})
    predictions = result.get("predictions", {})

    recommendation, confidence, edge, projected_total, btts_prob = build_payload(result, league)

    side_rec = predictions.get("side", {}).get("recommendation", "PASS")
    total_rec = predictions.get("total", {}).get("recommendation", "PASS")
    btts_rec = predictions.get("btts", {}).get("recommendation", "PASS")

    extra_metrics = " | ".join(
        [
            f"Projected: {game.get('projected_home_goals', 0)}-{game.get('projected_away_goals', 0)}",
            f"1X2: H {game.get('home_win_prob', 0):.3f} D {game.get('draw_prob', 0):.3f} A {game.get('away_win_prob', 0):.3f}",
            f"BTTS Prob: {btts_prob:.3f}",
            f"Corners: {result.get('corner_projection', 0)}",
            f"Recs: SIDE {side_rec} / TOTAL {total_rec} / BTTS {btts_rec}",
        ]
    )

    return push_to_discord(
        sport="soccer",
        home=home,
        away=away,
        market_total=market_total,
        projected_total=projected_total,
        edge=edge,
        recommendation=recommendation,
        webhook_url=webhook_url,
        extra_metrics=extra_metrics,
        confidence=confidence,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", default="World Cup")
    parser.add_argument("--market-total", type=float, default=2.5)
    parser.add_argument("--market-line", type=float, default=0.25)
    args = parser.parse_args()

    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        raise SystemExit("DISCORD_WEBHOOK_URL is not set. Put it in .env or export env var.")

    from models.soccer_predictor import SoccerPredictor

    home = "Japan"
    away = "Sweden"

    predictor = SoccerPredictor(league=args.league)
    result = predictor.predict(
        features=None,
        model=None,
        home_team=home,
        away_team=away,
        market_line=args.market_line,
        market_total=args.market_total,
    )

    ok = push(
        result=result,
        webhook_url=webhook_url,
        home=home,
        away=away,
        league=args.league,
        market_total=args.market_total,
        market_line=args.market_line,
    )

    if ok:
        print(f"[SUCCESS] Pushed Japan vs Sweden ({args.league}) to Discord.")
    else:
        print(f"[FAIL] Discord push failed for Japan vs Sweden ({args.league}).")


if __name__ == "__main__":
    main()

