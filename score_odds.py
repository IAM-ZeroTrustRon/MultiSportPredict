"""Verified bookmaker pairs for score runners; no guessed lines or prices."""
import datetime as dt
from sports_feed import EASTERN

KEYS = {"NCAAF": "americanfootball_ncaaf", "NBA": "basketball_nba", "WNBA": "basketball_wnba", "NCAAB": "basketball_ncaab", "NCAAW": "basketball_wncaab"}


def fetch(league):
    from live_odds import _fetch_odds_key, _api_key
    if not _api_key():
        raise ValueError("--odds requires ODDS_API_KEY in .env")
    if league not in KEYS:
        raise ValueError(f"{league} is absent from the account sports catalogue; supply manual lines and odds")
    events, error = _fetch_odds_key(KEYS[league], "us", "h2h,spreads,totals")
    if error:
        # Do not echo HTTP request exceptions: they can contain the API key.
        raise ValueError("Odds fetch failed; check account access and connection")
    return events or []


def for_fixture(events, game):
    from grade_predictions import normalise_team
    norm = lambda n: normalise_team(n, game["league"].lower())
    matches = []
    for event in events:
        stamp = event.get("commence_time")
        if not stamp:
            continue
        date = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(EASTERN).date().isoformat()
        if (date == game["date"] and norm(event.get("home_team", "")) == norm(game["home_team"])
                and norm(event.get("away_team", "")) == norm(game["away_team"])):
            matches.append(event)
    if len(matches) != 1:
        return [], "No uniquely matched odds event; prices remain absent"
    event = matches[0]
    # Both sides of a market must come from the same bookmaker and same line.
    for book in event.get("bookmakers", []):
        specs = []
        for market in book.get("markets", []):
            kind = market.get("key")
            prices = {o["name"]: o for o in market.get("outcomes", [])}
            if kind in {"h2h", "spreads"}:
                a, b = prices.get(event["home_team"]), prices.get(event["away_team"])
            elif kind == "totals":
                a, b = prices.get("Over"), prices.get("Under")
            else:
                continue
            if not a or not b or a.get("price") is None or b.get("price") is None:
                continue
            if kind == "spreads" and (a.get("point") is None or b.get("point") != -a["point"]):
                continue
            if kind == "totals" and (a.get("point") is None or b.get("point") != a["point"]):
                continue
            specs.append({"kind": {"h2h":"moneyline", "spreads":"spread", "totals":"total"}[kind],
                "line": 0.5 if kind == "h2h" else a["point"], "price_a": a["price"], "price_b": b["price"],
                "bookmaker": book.get("key"), "updated": market.get("last_update") or book.get("last_update")})
        if specs:
            return specs, f"Bookmaker {book.get('key')}; event {event['id']}"
    return [], "No complete bookmaker pairs; prices remain absent"
