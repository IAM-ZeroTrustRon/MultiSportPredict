"""Explicit exploratory forecast from disclosed league baselines.

For a fixture whose teams or league have no verified history, this produces a
deliberately weak estimate instead of refusing outright -- and it says so on
every line. Nothing here is a betting recommendation:

  * every substituted input is listed in ``substitutions`` with its value,
    where it came from, and why it was needed
  * no price is read, no EV is computed, no selection is recommended
  * the stored row carries cohort='EXPLORATORY', so it can never be pooled with
    forecasts built from verified team data

A baseline forecast can be a starting point for discussion. It cannot make an
unsupported fixture reliably predictable, and the output says that too.

Usage:
    venv/Scripts/python.exe -u exploratory.py --sport basketball --league NBA \
        --home "Team A" --away "Team B"
    venv/Scripts/python.exe -u exploratory.py --sport soccer --league "Serie A" \
        --home Torino --away Monza --store
"""
import argparse
import datetime as dt
import math
from typing import Optional

EXPLORATORY_LABEL = "EXPLORATORY - baseline only, no value claim"

# League scoring baselines. These are deliberately round, documented numbers,
# not fitted parameters: the point is disclosure, not a hidden model.
BASKETBALL_BASELINES = {
    "NBA": dict(points=112.0, margin_sd=16.5),
    "WNBA": dict(points=80.0, margin_sd=13.0),
    "NCAAB": dict(points=74.0, margin_sd=12.5),
    "NCAAW": dict(points=68.0, margin_sd=12.0),
    "KBL": dict(points=78.0, margin_sd=12.0),
    "NZNBL": dict(points=82.0, margin_sd=13.0),
    "NBL": dict(points=88.0, margin_sd=13.0),
    "BBL": dict(points=80.0, margin_sd=13.0),
}
SOCCER_BASELINES = {
    "SERIE A": dict(goals=1.35),
    "BUNDESLIGA": dict(goals=1.55),
    "PREMIER LEAGUE": dict(goals=1.45),
    "LA LIGA": dict(goals=1.30),
    "LIGUE 1": dict(goals=1.30),
    "MLS": dict(goals=1.45),
}
DEFAULT_BASKETBALL = dict(points=80.0, margin_sd=14.0)
DEFAULT_SOCCER = dict(goals=1.40)
HOME_ADVANTAGE = {"basketball": 1.7, "soccer": 0.20}


def normal_cdf(value):
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def basketball_forecast(league, home, away):
    baseline = BASKETBALL_BASELINES.get(str(league).upper())
    substitutions = []
    if baseline is None:
        baseline = DEFAULT_BASKETBALL
        substitutions.append(dict(
            input="league scoring baseline", value=f"{baseline['points']:.1f} pts/team",
            source="generic fallback", why=f"league {league!r} has no configured baseline"))
    else:
        substitutions.append(dict(
            input="league scoring baseline", value=f"{baseline['points']:.1f} pts/team",
            source=f"configured baseline for {str(league).upper()}",
            why="both teams' scoring rates are unknown"))
    substitutions += [
        dict(input="team offensive/defensive ratings", value="league average for both teams",
             source="placeholder", why="no verified current-season team metrics"),
        dict(input="home-court advantage", value=f"{HOME_ADVANTAGE['basketball']:+.1f} pts",
             source="generic constant", why="venue-specific effect not measured"),
        dict(input="margin volatility", value=f"{baseline['margin_sd']:.1f} pts",
             source="configured baseline", why="no fitted residual distribution"),
        dict(input="injuries, lineups, rest, travel", value="ignored",
             source="not modelled", why="no verified availability data"),
    ]
    margin = HOME_ADVANTAGE["basketball"]
    home_points = baseline["points"] + margin / 2
    away_points = baseline["points"] - margin / 2
    home_win = normal_cdf(margin / baseline["margin_sd"])
    return dict(
        projection=dict(home_points=round(home_points, 1), away_points=round(away_points, 1),
                        margin=round(margin, 2),
                        margin_sd=baseline["margin_sd"]),
        probabilities=dict(home_win=home_win, away_win=1.0 - home_win, draw=None),
        substitutions=substitutions)


def soccer_forecast(league, home, away):
    baseline = SOCCER_BASELINES.get(str(league).upper())
    substitutions = []
    if baseline is None:
        baseline = DEFAULT_SOCCER
        substitutions.append(dict(
            input="league goals baseline", value=f"{baseline['goals']:.2f} goals/team",
            source="generic fallback", why=f"league {league!r} has no configured baseline"))
    else:
        substitutions.append(dict(
            input="league goals baseline", value=f"{baseline['goals']:.2f} goals/team",
            source=f"configured baseline for {str(league).upper()}",
            why="both teams' scoring and conceding rates are unknown"))
    substitutions += [
        dict(input="team xG for/against", value="league average for both teams",
             source="placeholder", why="no verified team metrics"),
        dict(input="home advantage", value=f"+{HOME_ADVANTAGE['soccer']:.2f} goals",
             source="generic constant", why="venue-specific effect not measured"),
        dict(input="lineups, injuries, motivation", value="ignored",
             source="not modelled", why="no verified availability data"),
    ]
    home_rate = baseline["goals"] + HOME_ADVANTAGE["soccer"] / 2
    away_rate = baseline["goals"] - HOME_ADVANTAGE["soccer"] / 2
    limit = 8
    home_win = draw = away_win = 0.0
    for h in range(limit + 1):
        for a in range(limit + 1):
            mass = (math.exp(-home_rate) * home_rate ** h / math.factorial(h)
                    * math.exp(-away_rate) * away_rate ** a / math.factorial(a))
            if h > a:
                home_win += mass
            elif h == a:
                draw += mass
            else:
                away_win += mass
    total = home_win + draw + away_win
    return dict(
        projection=dict(home_goals=round(home_rate, 2), away_goals=round(away_rate, 2)),
        probabilities=dict(home_win=home_win / total, draw=draw / total,
                           away_win=away_win / total),
        substitutions=substitutions)


def build(sport, league, home, away, game_date=None):
    sport = (sport or "").strip().lower()
    if sport == "basketball":
        body = basketball_forecast(league, home, away)
    elif sport in ("soccer", "football"):
        sport = "soccer"
        body = soccer_forecast(league, home, away)
    else:
        raise ValueError("exploratory mode supports basketball and soccer only")
    game_date = game_date or dt.date.today().isoformat()
    dt.date.fromisoformat(game_date)
    probabilities = body["probabilities"]
    return {
        "sport": sport, "league": str(league), "home_team": home, "away_team": away,
        "game_date": game_date,
        "mode": "exploratory", "exploratory": True,
        "projection": body["projection"], "probabilities": probabilities,
        "substitutions": body["substitutions"],
        "recommendation": EXPLORATORY_LABEL,
        "note": ("Exploratory baseline forecast. Every substituted input is listed. "
                 "No price was read, no EV was computed, and nothing here is a "
                 "betting recommendation. Placeholder inputs cannot make an "
                 "unsupported fixture reliably predictable."),
        "event_key": f"exploratory:{sport}:{game_date}:{home}:{away}",
    }


def format_report(result):
    lines = ["EXPLORATORY FORECAST - disclosed baseline inputs",
             f"{result['league']} {result['game_date']} | {result['away_team']} @ {result['home_team']}"]
    projection = result["projection"]
    if result["sport"] == "basketball":
        lines.append(f"Baseline score: {result['home_team']} {projection['home_points']} | "
                     f"{result['away_team']} {projection['away_points']}")
    else:
        lines.append(f"Baseline goals: {result['home_team']} {projection['home_goals']} | "
                     f"{result['away_team']} {projection['away_goals']}")
    probabilities = result["probabilities"]
    lines.append(f"Home win: {probabilities['home_win']:.1%}"
                 + (f" | Draw: {probabilities['draw']:.1%}" if probabilities.get("draw") is not None else "")
                 + f" | Away win: {probabilities['away_win']:.1%}")
    lines += ["", "SUBSTITUTED INPUTS - every placeholder is listed"]
    for item in result["substitutions"]:
        lines.append(f"  - {item['input']}: {item['value']}  [{item['source']}]  ({item['why']})")
    lines += ["", "Value: unavailable - no price was read and no EV is claimed.",
              "Probability and value are separate signals; this forecast has neither "
              "a verified team basis nor a price.",
              result["note"]]
    return "\n".join(lines)


def store(result, db_path=None):
    """Persist as an EXPLORATORY cohort row, outside the value record."""
    from core.historical_storage import init_db, store_prediction
    init_db(db_path)
    probabilities = result["probabilities"]
    market_type = "moneyline"
    return store_prediction(
        sport=result["sport"], home_team=result["home_team"], away_team=result["away_team"],
        market_type=market_type, model_value=float(probabilities["home_win"]),
        market_value=0.5, edge=None, confidence=None,
        recommendation=result["recommendation"], raw_json=result,
        db_path=db_path, league=result["league"], stake_size=None)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sport", required=True, choices=["basketball", "soccer"])
    parser.add_argument("--league", required=True)
    parser.add_argument("--home", required=True)
    parser.add_argument("--away", required=True)
    parser.add_argument("--date", default=None)
    parser.add_argument("--store", action="store_true",
                        help="save as an EXPLORATORY cohort row (outside the value record)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    import json
    result = build(args.sport, args.league, args.home, args.away, args.date)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_report(result))
    if args.store:
        row_id = store(result)
        print(f"\n[stored] id={row_id} cohort=EXPLORATORY (not part of the value record)")
    return result


if __name__ == "__main__":
    main()
