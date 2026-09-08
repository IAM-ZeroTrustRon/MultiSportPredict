#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
live_odds.py - Auto-fetched market odds, cached per (league/tournament, day)

WHY THIS EXISTS
    Before this, tennis had no odds ingestor at all (odds only arrived via
    manual --p1-ml/--p2-ml), and soccer only fetched when --live-odds was
    passed explicitly. The result: a run with incomplete inputs produces
    "PASS, model probability only" -- not because there's no edge, but
    because nobody typed the price in -- so the same game got run twice:
    once bare, then again by hand with a price typed in. This module makes
    fetching the price the DEFAULT path. Manual CLI odds still override it.

COVERAGE, VERIFIED AGAINST THE REAL API -- NOT ASSUMED
    Tennis is keyed per TOURNAMENT ("tennis_atp_us_open"), never a general
    "tennis_atp"/"tennis_wta" feed. Between majors this list is empty --
    that MUST produce an explicit "no market for this tour right now"
    result, never a silent empty-looking-priced card. Only the h2h market
    exists for tennis; no set-betting markets are available here.

    12 of the 13 soccer leagues in this project's store are covered.
    Eerste Divisie is NOT -- checked the full /v4/sports list directly, no
    Dutch second-tier key exists under any name. It is marked
    covered=False in SOCCER_LEAGUES below, not left to fail into an empty
    fetch every single day.

    Region is per-league, not global. Tested all 13 leagues directly:
    requesting the "us" region for Saudi Pro League and Turkish Super Lig
    returns real fixtures with ZERO bookmakers attached -- those two are
    priced by EU-region books, not US ones. The other 11 are fine on "us".
    A single hardcoded region would look like coverage and silently return
    nothing for exactly the two leagues just added this project.

COST, MEASURED DIRECTLY (the x-requests-last response header, not the docs)
    1 credit per market requested per call, and cost does NOT scale with
    how many games are in that league that day -- one call returns every
    game in the league/tournament for one flat cost.

CACHING
    One fetch per (league key or tournament key, calendar day), written to
    data/odds_cache/. Every cache file records fetched_at (UTC). A cache
    older than MAX_CACHE_AGE_HOURS is refreshed rather than reused -- a
    price captured at 6am should not silently price an evening kickoff.
    Every result this module returns carries captured_at, so a card built
    from a cached price can show when that price was taken rather than
    presenting it as current.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    requests = None

ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "data" / "odds_cache"
ODDS_BASE = "https://api.the-odds-api.com/v4"
MAX_CACHE_AGE_HOURS = 4
UA = "Mozilla/5.0 (MultiSportPredict live odds)"

# league name (as this project already spells it, lowercased) -> Odds API
# config. Region is data, not a branch in the fetch logic -- see module
# docstring for why that matters. covered=False leagues never attempt a
# fetch; they return "not_covered" immediately, every time, cheaply.
SOCCER_LEAGUES: Dict[str, Dict[str, Any]] = {
    "premier league":    {"key": "soccer_epl", "region": "us", "covered": True},
    "bundesliga":        {"key": "soccer_germany_bundesliga", "region": "us", "covered": True},
    "2. bundesliga":     {"key": "soccer_germany_bundesliga2", "region": "us", "covered": True},
    "la liga":           {"key": "soccer_spain_la_liga", "region": "us", "covered": True},
    "serie a":           {"key": "soccer_italy_serie_a", "region": "us", "covered": True},
    "serie b":           {"key": "soccer_italy_serie_b", "region": "us", "covered": True},
    "championship":      {"key": "soccer_efl_champ", "region": "us", "covered": True},
    "eredivisie":        {"key": "soccer_netherlands_eredivisie", "region": "us", "covered": True},
    "liga mx":           {"key": "soccer_mexico_ligamx", "region": "us", "covered": True},
    "mls":               {"key": "soccer_usa_mls", "region": "us", "covered": True},
    "superliga":         {"key": "soccer_denmark_superliga", "region": "us", "covered": True},
    "saudi pro league":  {"key": "soccer_saudi_arabia_pro_league", "region": "eu", "covered": True},
    "turkish super lig": {"key": "soccer_turkey_super_league", "region": "eu", "covered": True},
    "eerste divisie":    {"key": None, "region": None, "covered": False,
                          "reason": ("no Dutch second-tier key exists in The Odds API's "
                                    "sports list -- checked directly, not assumed")},
    "champions league":  {"key": None, "region": None, "covered": False,
                          "reason": ("NOT the same kind of 'checked directly' as the row above -- "
                                    "the live /v4/sports discovery call needed to confirm this was "
                                    "blocked before it could run. The Odds API's public catalog "
                                    "generally lists a 'soccer_uefa_champs_league' key, but that is "
                                    "unverified against this project's actual account/plan. Marked "
                                    "not-covered on purpose so a UCL fetch fails loud (this reason) "
                                    "instead of silently returning nothing -- re-run the discovery "
                                    "check and fill in a real key/region before flipping this to True.")},
}


def log(message: str = "") -> None:
    print(message, flush=True)


def _api_key() -> Optional[str]:
    key = os.environ.get("ODDS_API_KEY", "").strip()
    if key:
        return key
    env_path = ROOT / ".env"
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if raw.strip().startswith("ODDS_API_KEY"):
                return raw.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _cache_path(tag: str, date: _dt.date) -> Path:
    safe = tag.replace("/", "_")
    return CACHE_DIR / f"{safe}_{date.isoformat()}.json"


def _read_cache(tag: str, date: _dt.date) -> Optional[Dict[str, Any]]:
    path = _cache_path(tag, date)
    if not path.exists():
        return None
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    fetched_at = blob.get("fetched_at")
    if not fetched_at:
        return None
    try:
        age_hours = (_dt.datetime.now(_dt.timezone.utc)
                    - _dt.datetime.fromisoformat(fetched_at)).total_seconds() / 3600.0
    except ValueError:
        return None
    if age_hours > MAX_CACHE_AGE_HOURS:
        return None
    return blob


def _write_cache(tag: str, date: _dt.date, region: str, events: List[Dict[str, Any]]) -> str:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fetched_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    path = _cache_path(tag, date)
    path.write_text(json.dumps({
        "fetched_at": fetched_at, "region": region, "events": events,
    }, ensure_ascii=False), encoding="utf-8")
    return fetched_at


def _fetch_odds_key(sport_key: str, region: str, markets: str) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """One real API call. Returns (events, error) -- error is None on success."""
    if requests is None:
        return None, "requests library not installed"
    key = _api_key()
    if not key:
        return None, "ODDS_API_KEY not configured"
    try:
        resp = requests.get(
            f"{ODDS_BASE}/sports/{sport_key}/odds",
            params={"apiKey": key, "regions": region, "markets": markets, "oddsFormat": "american"},
            headers={"User-Agent": UA}, timeout=20,
        )
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"
    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code}"
    try:
        return resp.json(), None
    except ValueError:
        return None, "non-JSON response"


def _find_event(events: List[Dict[str, Any]], home: str, away: str) -> Optional[Dict[str, Any]]:
    def squash(name: str) -> str:
        return "".join(ch for ch in (name or "").lower() if ch.isalnum())

    home_s, away_s = squash(home), squash(away)
    for event in events:
        eh, ea = squash(event.get("home_team", "")), squash(event.get("away_team", ""))
        if (home_s in eh or eh in home_s) and (away_s in ea or ea in away_s):
            return event
        if (home_s in ea or ea in home_s) and (away_s in eh or eh in away_s):
            event = dict(event)
            event["_swapped"] = True
            return event
    return None


def _find_tennis_event(events: List[Dict[str, Any]], home: str, away: str) -> Optional[Dict[str, Any]]:
    """Same job as _find_event, but tennis needs its own matcher.

    The store (and every stored prediction) spells a player "Khachanov K."
    -- surname, initial. The Odds API spells the same player "Karen
    Khachanov" -- full given name, surname. Squashing both whole strings
    and checking containment (what _find_event does for team names) never
    matches these: "khachanovk" is not a substring of "karenkhachanov" or
    the reverse. Match on SURNAME alone instead, reusing run_tennis.py's
    own surname-splitting logic so a compound surname ("Van De Zandschulp")
    is handled the same way here as everywhere else in this project.
    """
    from run_tennis import split_key, squash as tennis_squash

    def surname_of(name: str) -> str:
        if re.match(r"^.+\s[A-Z](\.[A-Z])*\.?$", name.strip()):
            surname, _initial = split_key(name)
            return tennis_squash(surname)
        # A bare full name ("Karen Khachanov") has no reliable surname/given
        # split without a name database -- fall back to the whole squashed
        # string and let containment do the work; single-word "surnames"
        # from the store side will still match correctly against this.
        return tennis_squash(name)

    home_s, away_s = surname_of(home), surname_of(away)
    for event in events:
        eh = tennis_squash(event.get("home_team", ""))
        ea = tennis_squash(event.get("away_team", ""))
        if home_s and away_s and (home_s in eh) and (away_s in ea):
            return event
        if home_s and away_s and (home_s in ea) and (away_s in eh):
            event = dict(event)
            event["_swapped"] = True
            return event
    return None


def _extract_soccer_market(event: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for book in event.get("bookmakers", []) or []:
        for market in book.get("markets", []) or []:
            if market["key"] == "h2h" and "home_ml" not in out:
                for outcome in market.get("outcomes", []):
                    name = outcome.get("name")
                    price = outcome.get("price")
                    if name == event.get("home_team"):
                        out["home_ml"] = price
                    elif name == event.get("away_team"):
                        out["away_ml"] = price
                    elif name and str(name).lower() == "draw":
                        out["draw_ml"] = price
            if market["key"] == "totals" and "total_line" not in out:
                for outcome in market.get("outcomes", []):
                    if outcome.get("point") is not None:
                        out["total_line"] = outcome["point"]
                    if str(outcome.get("name", "")).lower() == "over":
                        out["over_price"] = outcome.get("price")
                    elif str(outcome.get("name", "")).lower() == "under":
                        out["under_price"] = outcome.get("price")
        if "home_ml" in out:
            break
    return out


def get_soccer_odds(league: Optional[str], home: str, away: str,
                    force_refresh: bool = False) -> Dict[str, Any]:
    """Auto-fetched soccer moneyline + total, cached per (league, day).

    Returns a dict always carrying "status" and "captured_at" (None unless
    a real price was found). Never invents a price -- an unmatched fixture
    or an uncovered league comes back with status/reason explaining why,
    not a filled-in guess.
    """
    league_norm = (league or "").strip().lower()
    config = SOCCER_LEAGUES.get(league_norm)
    if config is None:
        return {"status": "unknown_league", "captured_at": None,
                "reason": f"'{league}' is not in SOCCER_LEAGUES -- add it there first"}
    if not config.get("covered"):
        return {"status": "not_covered", "captured_at": None,
                "reason": config.get("reason", "this league has no Odds API key")}

    sport_key, region = config["key"], config["region"]
    today = _dt.date.today()
    cache = None if force_refresh else _read_cache(sport_key, today)
    if cache is None:
        events, error = _fetch_odds_key(sport_key, region, "h2h,totals")
        if error:
            return {"status": "error", "captured_at": None, "reason": error}
        fetched_at = _write_cache(sport_key, today, region, events)
    else:
        events, fetched_at = cache["events"], cache["fetched_at"]

    event = _find_event(events, home, away)
    if event is None:
        return {"status": "no_fixture", "captured_at": fetched_at,
                "reason": f"no odds-feed fixture matched {home!r} vs {away!r} in {sport_key} today"}

    market = _extract_soccer_market(event)
    if not market:
        return {"status": "no_bookmaker", "captured_at": fetched_at,
                "reason": "fixture found but no bookmaker has priced it yet"}
    if event.get("_swapped"):
        market["home_ml"], market["away_ml"] = market.get("away_ml"), market.get("home_ml")
    market.update({"status": "live" if cache is None else "cached", "captured_at": fetched_at})
    return market


def _discover_tennis_tournaments(tour: str) -> Tuple[List[str], Optional[str]]:
    """Which tennis_{tour}_* sport keys The Odds API currently lists.

    Tennis has no general feed -- only whichever tournament is being priced
    right now. Between majors this is legitimately empty; the caller must
    treat that as "no market for this tour right now", not as a failure.
    """
    key = _api_key()
    if not key:
        return [], "ODDS_API_KEY not configured"
    if requests is None:
        return [], "requests library not installed"
    try:
        resp = requests.get(f"{ODDS_BASE}/sports", params={"apiKey": key},
                           headers={"User-Agent": UA}, timeout=20)
    except Exception as exc:  # noqa: BLE001
        return [], f"{type(exc).__name__}: {exc}"
    if resp.status_code != 200:
        return [], f"HTTP {resp.status_code}"
    try:
        sports = resp.json()
    except ValueError:
        return [], "non-JSON response"
    prefix = f"tennis_{tour.lower()}_"
    return [s["key"] for s in sports if s.get("key", "").startswith(prefix) and s.get("active")], None


def get_tennis_odds(tour: str, home: str, away: str,
                    force_refresh: bool = False) -> Dict[str, Any]:
    """Auto-fetched tennis moneyline (h2h only -- no set markets exist here).

    tour: "atp" or "wta". Discovers the active tournament key(s) at
    runtime rather than a hardcoded sport key, since that key changes
    every tournament and goes empty between majors.
    """
    tour_norm = (tour or "").strip().lower()
    if tour_norm not in ("atp", "wta"):
        return {"status": "unknown_tour", "captured_at": None,
                "reason": f"tour must be 'atp' or 'wta', got {tour!r}"}

    today = _dt.date.today()
    discovery_tag = f"tennis_{tour_norm}_discovery"
    cached_keys = None if force_refresh else _read_cache(discovery_tag, today)
    if cached_keys is not None:
        tournament_keys = [e["key"] for e in cached_keys["events"]]
    else:
        tournament_keys, error = _discover_tennis_tournaments(tour_norm)
        if error:
            return {"status": "error", "captured_at": None, "reason": error}
        _write_cache(discovery_tag, today, "n/a", [{"key": k} for k in tournament_keys])

    if not tournament_keys:
        return {"status": "no_active_tournament", "captured_at": None,
                "reason": f"The Odds API lists no active {tour_norm.upper()} tournament right now "
                         f"-- this is the between-majors gap, not an error"}

    for sport_key in tournament_keys:
        cache = None if force_refresh else _read_cache(sport_key, today)
        if cache is None:
            events, error = _fetch_odds_key(sport_key, "us", "h2h")
            if error:
                continue
            fetched_at = _write_cache(sport_key, today, "us", events)
        else:
            events, fetched_at = cache["events"], cache["fetched_at"]

        event = _find_tennis_event(events, home, away)
        if event is None:
            continue
        market = _extract_soccer_market(event)  # same h2h shape, no draw possible
        if not market:
            continue
        if event.get("_swapped"):
            market["home_ml"], market["away_ml"] = market.get("away_ml"), market.get("home_ml")
        market.update({"status": "live" if cache is None else "cached",
                      "captured_at": fetched_at, "tournament_key": sport_key})
        return market

    return {"status": "no_fixture", "captured_at": None,
            "reason": f"no odds-feed fixture matched {home!r} vs {away!r} in "
                     f"{', '.join(tournament_keys)}"}
