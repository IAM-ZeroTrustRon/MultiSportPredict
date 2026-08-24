# models/dispatcher.py
"""Sport dispatcher that routes match predictions to the correct predictor.

This legacy dispatcher was updated to use the current predictor modules
(models.basketball_predictor, models.soccer_predictor, models.baseball_predictor)
which replace the old non-existent modules (models.basketball_predict,
models.soccer_predict, models.kbo_predict).
"""

import sys


def dispatch(sport: str, home_team: str, away_team: str, league: str = None):
    """Run a prediction for a single match.

    Args:
        sport: Sport type ("basketball", "soccer", "kbo", or "baseball")
        home_team: Home team name
        away_team: Away team name
        league: Optional league name

    Returns:
        Prediction result dict.
    """
    sport = sport.lower().strip()

    if sport == "basketball":
        from models.basketball_predictor import BasketballPredictor
        predictor = BasketballPredictor(league=league or "EuroLeague")
        return predictor.predict(
            features=None, model=None,
            home_team=home_team, away_team=away_team
        )

    if sport == "soccer":
        from models.soccer_predictor import SoccerPredictor
        predictor = SoccerPredictor(league=league or "Premier League")
        return predictor.predict(
            features=None, model=None,
            home_team=home_team, away_team=away_team
        )

    if sport in ("kbo", "baseball"):
        from models.baseball_predictor import BaseballPredictor
        predictor = BaseballPredictor()
        league_key = "KBO" if sport == "kbo" else league or "MLB"
        data = predictor.load_data(league=league_key, home_team=home_team, away_team=away_team)
        features = predictor.feature_engineering(data)
        return predictor.predict(features, None, home_team, away_team, league_key)

    raise ValueError(f"Unsupported sport: {sport}")


def main():
    if len(sys.argv) < 4:
        print("Usage: python -m models.dispatcher <sport> <home_team> <away_team> [league]")
        sys.exit(1)

    sport = sys.argv[1]
    home_team = sys.argv[2]
    away_team = sys.argv[3]
    league = sys.argv[4] if len(sys.argv) > 4 else None
    result = dispatch(sport, home_team, away_team, league)
    print(result)


if __name__ == "__main__":
    main()