#!/usr/bin/env python
"""
Universal Match Analysis Runner
==============================
Run any sport match through a single CLI entry point.

Usage:
    python run_match.py --sport soccer --home "Switzerland" --away "Bosnia-Herzegovina" --market-line 0.0 --market-total 2.5 --market-corners 9.5
    python run_match.py --sport basketball --home "Alba Berlin" --away "Brose Bamberg" --league "BBL"
    python run_match.py --sport baseball --home "Yankees" --away "Red Sox" --date 2026-06-17
"""

import argparse
import sys
from pathlib import Path
import pandas as pd


def run_soccer_match(home, away, market_line=0.0, market_total=2.5, market_corners=9.5, store_to_db=False, **kwargs):
    from soccer.soccer_predict_game import run_soccer_game
    return run_soccer_game(
        home_team=home,
        away_team=away,
        market_line=market_line,
        market_total=market_total,
        market_corners=market_corners,
        store_to_db=store_to_db,
    )


def run_basketball_match(home, away, league=None, market_line=0.0, market_total=160.0, store_to_db=False, **kwargs):
    from models.basketball_predictor import BasketballPredictor
    predictor = BasketballPredictor(league=league or "default")
    predictor.load_data()
    features = predictor.feature_engineering(pd.DataFrame())
    result = predictor.predict(
        features=features,
        model=None,
        home_team=home,
        away_team=away,
        market_line=market_line,
        current_line=market_line,
        open_line=market_line,
        date=kwargs.get('date'),
    )
    return result


def run_baseball_match(home, away, date=None, market_line=0.0, market_total=8.5, store_to_db=False, **kwargs):
    from models.baseball_predictor import BaseballPredictor
    predictor = BaseballPredictor()
    data = predictor.load_data(home_team=home, away_team=away)
    features = predictor.feature_engineering(data)
    league = data.get("league", "MLB")
    result = predictor.predict(
        features=features,
        model=None,
        home_team=home,
        away_team=away,
        league=league,
        date=date,
    )
    return result


SPORT_RUNNERS = {
    "soccer": run_soccer_match,
    "basketball": run_basketball_match,
    "baseball": run_baseball_match,
}


def main():
    parser = argparse.ArgumentParser(description="Universal match analysis runner")
    parser.add_argument("--sport", required=True, choices=list(SPORT_RUNNERS.keys()), help="Sport type")
    parser.add_argument("--home", required=True, help="Home team name")
    parser.add_argument("--away", required=True, help="Away team name")
    parser.add_argument("--league", default=None, help="League/competition name")
    parser.add_argument("--date", default=None, help="Match date")
    parser.add_argument("--market-line", default=0.0, type=float, help="Market line/spread")
    parser.add_argument("--market-total", default=0.0, type=float, help="Market total")
    parser.add_argument("--market-corners", default=9.5, type=float, help="Soccer corners market line")
    parser.add_argument("--store-to-db", action="store_true", help="Store prediction to database")

    args = parser.parse_args()

    runner = SPORT_RUNNERS[args.sport]
    result = runner(
        home=args.home,
        away=args.away,
        league=args.league,
        date=args.date,
        market_line=args.market_line,
        market_total=args.market_total,
        market_corners=args.market_corners,
        store_to_db=args.store_to_db,
    )

    print("\n=== ANALYSIS COMPLETE ===")
    return result


if __name__ == "__main__":
    main()