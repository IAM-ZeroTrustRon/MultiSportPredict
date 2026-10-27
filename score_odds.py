"""Verified bookmaker pairs for score runners; no guessed lines or prices."""
import datetime as dt
from sports_feed import EASTERN

KEYS = {"NCAAF": "americanfootball_ncaaf", "NBA": "basketball_nba", "WNBA": "basketball_wnba", "NCAAB": "basketball_ncaab", "NCAAW": "basketball_wncaab"}
KEYS['NHL'] = 'icehockey_nhl'
# Verified present in the account catalogue (basketball_nbl).
KEYS['NBL'] = 'basketball_nbl'


def fetch(league, usage=None):
    from live_odds import _fetch_odds_key, _api_key
    if not _api_key():
        raise ValueError("--odds requires ODDS_API_KEY in .env")
    if league not in KEYS:
        raise ValueError(f"{league} is absent from the account sports catalogue; supply manual lines and odds")
    events, error = (_fetch_odds_key(KEYS[league], "us", "h2h,spreads,totals") if usage is None
                     else _fetch_odds_key(KEYS[league], "us", "h2h,spreads,totals", usage=usage))
    if error:
        # Do not echo HTTP request exceptions: they can contain the API key.
        raise ValueError("Odds fetch failed; check account access and connection")
    return events or []


def for_fixture(events, game, include_periods=False, now=None):
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
            key = market.get("key")
            if not isinstance(key,str):continue
            if game['league']=='NHL':
                # Only standard full-game pairs; a three-way regulation price
                # cannot be silently treated as OT-inclusive moneyline.
                if key not in {'h2h','spreads','totals'} or len(market.get('outcomes',[]))!=2:continue
                updated=market.get('last_update') or book.get('last_update')
                try:
                    stamp=dt.datetime.fromisoformat(updated.replace('Z','+00:00'))
                    age=((now or dt.datetime.now(dt.timezone.utc))-stamp).total_seconds()
                except (AttributeError,TypeError,ValueError):continue
                if stamp.tzinfo is None or not -5<=age<=900:continue
            period = next((p for p in ('h1','q1') if key.endswith('_'+p)), None)
            if period and not include_periods:continue
            kind = key.rsplit('_',1)[0] if period else key
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
                "bookmaker": book.get("key"), "updated": market.get("last_update") or book.get("last_update"),
                **({"period":period,"pricing_status":"EV unavailable - no calibrated period model"} if period else {}),
                # The provider event ID is how a stored quote is paired with the
                # closing price of the same event, for every league.
                'source_event_id': event['id'],
                'scope': 'period_only' if period else ('official_final_including_ot_so' if game['league']=='NHL' else 'full_game_including_overtime'),
                **({'scope':'official_final_including_ot_so','timestamp_basis':'bookmaker update'} if game['league']=='NHL' else {})})
        if any(not s.get("period") for s in specs):
            return specs, f"Bookmaker {book.get('key')}; event {event['id']}"
    return [], "No complete bookmaker pairs; prices remain absent"
