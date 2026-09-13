import argparse
import os
import sys
from typing import List

import pandas as pd
from dotenv import load_dotenv

from models.soccer_predictor import SoccerPredictor
from universal_runner import push_to_discord

# Try to import live stats ingester (optional - falls back to synthetic data)
try:
    from soccer.live_stats_ingest import get_match_stats
    HAS_LIVE_STATS = True
except ImportError:
    HAS_LIVE_STATS = False


def _build_extra_metrics(result: dict, args: argparse.Namespace) -> str:
    game = result.get("game", {})
    parts: List[str] = [
        (
            f"1X2: H {game.get('home_win_prob', 0):.3f} "
            f"D {game.get('draw_prob', 0):.3f} "
            f"A {game.get('away_win_prob', 0):.3f}"
        ),
        f"BTTS Prob: {result.get('btts_probability', 0):.3f}",
        f"Corners: {result.get('corner_projection', 0)}",
    ]

    if args.minute is not None:
        parts.append(f"Minute: {args.minute}")
    if args.home_score is not None and args.away_score is not None:
        parts.append(f"Live Score: {args.home_score}-{args.away_score}")
    if args.corners_home is not None and args.corners_away is not None:
        parts.append(f"Live Corners: H {args.corners_home} A {args.corners_away}")

    if args.note:
        parts.append(f"Note: {args.note}")

    return " | ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run soccer model and push result to Discord")
    parser.add_argument("--home", required=True, help="Home team")
    parser.add_argument("--away", required=True, help="Away team")
    parser.add_argument("--league", default="default", help="League config key/name")
    parser.add_argument("--market-line", type=float, default=0.0, help="Market side line")
    parser.add_argument("--market-total", type=float, default=2.5, help="Market total line")

    # Optional live-state context
    parser.add_argument("--minute", type=int, default=None, help="Current match minute")
    parser.add_argument("--home-score", type=int, default=None, help="Current home score")
    parser.add_argument("--away-score", type=int, default=None, help="Current away score")
    parser.add_argument("--corners-home", type=int, default=None, help="Current home corners")
    parser.add_argument("--corners-away", type=int, default=None, help="Current away corners")
    parser.add_argument("--note", default="", help="Optional context note appended to Discord message")

    args = parser.parse_args()

    load_dotenv()
    webhook = os.getenv("DISCORD_WEBHOOK_URL")

    predictor = SoccerPredictor(league=args.league)

    # Fetch live stats if available (provides real team data instead of synthetic)
    live_kwargs = {}
    if HAS_LIVE_STATS:
        try:
            print(f"[LiveStats] Fetching real team data for {args.home} vs {args.away}...")
            live_kwargs = get_match_stats(args.home, args.away, args.league)
            source = live_kwargs.get('_data_source', 'unknown')
            print(f"[LiveStats] Data source: {source}")
            if source == 'fallback':
                print(f"[LiveStats] Using name-derived fallback (FBRef unavailable)")
        except Exception as e:
            print(f"[LiveStats] Error fetching live stats: {e}")
            print(f"[LiveStats] Falling back to synthetic data")

    result = predictor.predict(
        features=pd.DataFrame(),
        model=None,
        home_team=args.home,
        away_team=args.away,
        market_line=args.market_line,
        market_total=args.market_total,
        **live_kwargs,
    )

    game = result.get("game", {})
    predictions = result.get("predictions", {})

    rec_side = predictions.get("side", {}).get("recommendation", "PASS")
    rec_total = predictions.get("total", {}).get("recommendation", "PASS")
    rec_btts = predictions.get("btts", {}).get("recommendation", "PASS")
    recommendation = f"SIDE: {rec_side} | TOTAL: {rec_total} | BTTS: {rec_btts}"

    projected_total = float(game.get("projected_total_goals", 0.0))
    total_edge = float(predictions.get("total", {}).get("edge", 0.0))
    extra_metrics = _build_extra_metrics(result, args)

    ok = push_to_discord(
        sport="soccer",
        home=args.home,
        away=args.away,
        market_total=args.market_total,
        projected_total=projected_total,
        edge=f"{total_edge:+.3f}",
        recommendation=recommendation,
        webhook_url=webhook,
        extra_metrics=extra_metrics,
    )

    print(f"DISCORD_PUSH_OK={ok}")
    print(
        f"ProjectedGoals: {game.get('projected_home_goals', 0)}-{game.get('projected_away_goals', 0)} "
        f"(Total {projected_total:.2f})"
    )


if __name__ == "__main__":
    main()
