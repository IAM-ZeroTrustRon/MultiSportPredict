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
    result, never a silent empty-looking-priced card. Tennis supports h2h,
    game spreads/totals and additional full-match lines where books offer them.

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

SOCCER_LEAGUE_ALIASES: Dict[str, str] = {
    "french ligue 1": "ligue 1",
    "ligue1": "ligue 1",
    "german bundesliga": "bundesliga",
    "spanish la liga": "la liga",
    "laliga": "la liga",
    "english premier league": "premier league",
    "epl": "premier league",
    "italian serie a": "serie a",
    "uefa champions league": "champions league",
    "ucl": "champions league",
}

# league name (as this project already spells it, lowercased) -> Odds API
# config. Region is data, not a branch in the fetch logic -- see module
# docstring for why that matters. covered=False leagues never attempt a
# fetch; they return "not_covered" immediately, every time, cheaply.
SOCCER_LEAGUES: Dict[str, Dict[str, Any]] = {
    "ligue 1":           {"key": "soccer_france_ligue_one", "region": "eu", "covered": True},
    "ligue1":            {"key": "soccer_france_ligue_one", "region": "eu", "covered": True},
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


def resolve_soccer_league(league: Optional[str]) -> Tuple[Optional[Dict[str, Any]], str, Optional[str]]:
    """Normalise a project league label to a SOCCER_LEAGUES config.

    Returns (config_or_None, canonical_key, status). status is "ok",
    "unknown_league", or "not_covered" -- never raises, so callers can
    label a card UNLISTED (simulation only) instead of crashing.
    """
    raw = (league or "").strip().lower()
    try:
        from soccer_store import league_key as _store_key
        canonical = _store_key(raw)
    except ImportError:
        canonical = " ".join(raw.split())
    canonical = SOCCER_LEAGUE_ALIASES.get(canonical, canonical)
    config = SOCCER_LEAGUES.get(canonical)
    if config is None:
        return None, canonical, "unknown_league"
    if not config.get("covered"):
        return config, canonical, "not_covered"
    return config, canonical, "ok"


def undiscovered_soccer_keys() -> List[str]:
    """SOCCER_LEAGUES keys whose Odds API key was never verified (key None)."""
    return [name for name, cfg in SOCCER_LEAGUES.items() if not cfg.get("key")]


# Market sets, locked by live discovery 2026-10-09 (NOT guessed):
#   soccer Ligue 1 event 17694e68...: pinnacle prices
#     h2h/spreads/totals + h2h_h1/spreads_h1/totals_h1 + btts/btts_h1
#     + alternate_totals_corners/alternate_spreads_corners
#   basketball EuroLeague event c000fe20...: fanduel/betmgm/betrivers price
#     h2h_h1/spreads_h1/totals_h1 + h2h_q1/spreads_q1/totals_q1 (US books;
#     EU books carry FG only). Q1 keys are real: h2h_q1/spreads_q1/totals_q1.
# Cost is 1 credit per market per call; H1/Q1/corners ride the SAME call,
# not new calls -- the slate stays ~1 call per (league, day).
SOCCER_FULL_MARKETS = ("h2h,spreads,totals,h2h_h1,spreads_h1,totals_h1,"
                       "alternate_totals_corners,alternate_spreads_corners,"
                       "btts,btts_h1,alternate_spreads,alternate_totals")
# The league /odds endpoint 422s on anything beyond h2h,spreads,totals
# (verified 2026-10-09) -- H1/corners/BTTS need the per-event endpoint.
SOCCER_BASE_MARKETS = "h2h,spreads,totals"
BASKETBALL_FULL_MARKETS = ("h2h,spreads,totals,h2h_h1,spreads_h1,totals_h1,"
                           "h2h_q1,spreads_q1,totals_q1,"
                           "alternate_spreads,alternate_totals")
# The league /odds endpoint 422s on H1/Q1 keys (verified 2026-10-09) --
# segments need the per-event /events/{id}/odds endpoint instead.
BASKETBALL_BASE_MARKETS = "h2h,spreads,totals"

BASKETBALL_LEAGUES: Dict[str, Dict[str, Any]] = {
    "euroleague": {"key": "basketball_euroleague", "region": "eu",
                   "covered": True},
    "sbl": {"key": None, "region": None, "covered": False,
            "reason": "no Swedish SBL key exists in The Odds API's sports "
                      "list -- checked /v4/sports directly, not assumed. "
                      "Seed ratings in basketball_stats.json and this runs "
                      "as UNLISTED (Simulation Only - No EV)."},
}

BASKETBALL_LEAGUE_ALIASES: Dict[str, str] = {
    "euro league": "euroleague",
}


def resolve_basketball_league(league: Optional[str]) -> Tuple[Optional[Dict[str, Any]], str, str]:
    """Same contract as resolve_soccer_league: (config, canonical, status)."""
    raw = " ".join((league or "").strip().lower().split())
    canonical = BASKETBALL_LEAGUE_ALIASES.get(raw, raw)
    config = BASKETBALL_LEAGUES.get(canonical)
    if config is None:
        return None, canonical, "unknown_league"
    if not config.get("covered"):
        return config, canonical, "not_covered"
    return config, canonical, "ok"


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


def _read_cache(tag: str, date: _dt.date, max_age_hours: Optional[float] = None) -> Optional[Dict[str, Any]]:
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
    if age_hours > (MAX_CACHE_AGE_HOURS if max_age_hours is None else max_age_hours):
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


def _fetch_event_odds(sport_key: str, event_id: str, region: str,
                      markets: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """One per-event API call (supports H1/Q1 keys the league endpoint 422s)."""
    if requests is None:
        return None, "requests library not installed"
    key = _api_key()
    if not key:
        return None, "ODDS_API_KEY not configured"
    try:
        resp = requests.get(
            f"{ODDS_BASE}/sports/{sport_key}/events/{event_id}/odds",
            params={"apiKey": key, "regions": region, "markets": markets,
                    "oddsFormat": "american"},
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


def _fetch_odds_key(sport_key: str, region: str, markets: str, usage=None) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
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
    if usage is not None:
        # Only quota headers are exposed; URLs/credentials never enter reports.
        usage.update({name: resp.headers.get(name) for name in
                      ("x-requests-last", "x-requests-used", "x-requests-remaining")})
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
            if market["key"] == "spreads" and "spread_line" not in out:
                # First book's handicap, same convention as totals above.
                # Outcomes are Home/Away with signed points; normalise to the
                # home side so callers have one signed number to compare.
                for outcome in market.get("outcomes", []) or []:
                    point = outcome.get("point")
                    price = outcome.get("price")
                    name = str(outcome.get("name", ""))
                    if point is None:
                        continue
                    if name == event.get("home_team"):
                        out.setdefault("spread_line", point)
                        if price is not None:
                            out.setdefault("spread_home_price", price)
                    elif name == event.get("away_team"):
                        if price is not None:
                            out.setdefault("spread_away_price", price)
                        if "spread_line" not in out:
                            try:
                                out["spread_line"] = -float(point)
                            except (TypeError, ValueError):
                                pass
            # First-half markets (pinnacle/gtbets price h2h_h1, spreads_h1,
            # totals_h1 on the discovered Ligue 1 event).
            if market["key"] == "h2h_h1" and "h1_home_ml" not in out:
                for outcome in market.get("outcomes", []) or []:
                    name, price = outcome.get("name"), outcome.get("price")
                    if name == event.get("home_team"):
                        out["h1_home_ml"] = price
                    elif name == event.get("away_team"):
                        out["h1_away_ml"] = price
                    elif name and str(name).lower() == "draw":
                        out["h1_draw_ml"] = price
            if market["key"] == "spreads_h1" and "h1_spread_line" not in out:
                for outcome in market.get("outcomes", []) or []:
                    point, price = outcome.get("point"), outcome.get("price")
                    name = str(outcome.get("name", ""))
                    if point is None:
                        continue
                    if name == event.get("home_team"):
                        out.setdefault("h1_spread_line", point)
                        if price is not None:
                            out.setdefault("h1_spread_home_price", price)
                    elif name == event.get("away_team"):
                        if price is not None:
                            out.setdefault("h1_spread_away_price", price)
                        if "h1_spread_line" not in out:
                            try:
                                out["h1_spread_line"] = -float(point)
                            except (TypeError, ValueError):
                                pass
            if market["key"] == "totals_h1" and "h1_total_line" not in out:
                for outcome in market.get("outcomes", []) or []:
                    if outcome.get("point") is not None:
                        out["h1_total_line"] = outcome["point"]
                    lname = str(outcome.get("name", "")).lower()
                    if lname == "over":
                        out["h1_over_price"] = outcome.get("price")
                    elif lname == "under":
                        out["h1_under_price"] = outcome.get("price")
            # Both-teams-to-score, FG + H1.
            if market["key"] == "btts" and "btts_yes_price" not in out:
                for outcome in market.get("outcomes", []) or []:
                    lname = str(outcome.get("name", "")).lower()
                    if lname == "yes":
                        out["btts_yes_price"] = outcome.get("price")
                    elif lname == "no":
                        out["btts_no_price"] = outcome.get("price")
            if market["key"] == "btts_h1" and "h1_btts_yes_price" not in out:
                for outcome in market.get("outcomes", []) or []:
                    lname = str(outcome.get("name", "")).lower()
                    if lname == "yes":
                        out["h1_btts_yes_price"] = outcome.get("price")
                    elif lname == "no":
                        out["h1_btts_no_price"] = outcome.get("price")
            # Corner totals: pinnacle alternate_totals_corners (first book).
            if market["key"] in ("alternate_totals_corners", "totals_corners") \
                    and "corner_total_line" not in out:
                for outcome in market.get("outcomes", []) or []:
                    if outcome.get("point") is not None:
                        out["corner_total_line"] = outcome["point"]
                    lname = str(outcome.get("name", "")).lower()
                    if lname == "over":
                        out["corner_over_price"] = outcome.get("price")
                    elif lname == "under":
                        out["corner_under_price"] = outcome.get("price")
            # Team totals: alternate markets with description Home/Away/team.
            if market["key"] in ("alternate_team_totals", "team_totals") and (
                    "team_total_home_line" not in out or "team_total_away_line" not in out):
                desc = str(market.get("description", "")).lower()
                home_side = "home" in desc or (event.get("home_team") or "").lower() in desc
                away_side = "away" in desc or (event.get("away_team") or "").lower() in desc
                side = ("home" if home_side and not away_side else
                        "away" if away_side and not home_side else None)
                if side is not None:
                    for outcome in market.get("outcomes", []) or []:
                        lname = str(outcome.get("name", "")).lower()
                        if outcome.get("point") is None or lname not in ("over", "under"):
                            continue
                        out.setdefault(f"team_total_{side}_line", outcome["point"])
                        if lname == "over":
                            out.setdefault(f"team_total_{side}_over_price", outcome.get("price"))
                        else:
                            out.setdefault(f"team_total_{side}_under_price", outcome.get("price"))
        if "home_ml" in out:
            break
    return out


def get_soccer_odds(league: Optional[str], home: str, away: str,
                    force_refresh: bool = False) -> Dict[str, Any]:
    """Auto-fetched soccer moneyline + total + spread, cached per (league, day).

    Returns a dict always carrying "status" and "captured_at" (None unless
    a real price was found). Never invents a price -- an unmatched fixture
    or an uncovered league comes back with status/reason explaining why,
    not a filled-in guess.
    """
    config, canonical, resolved = resolve_soccer_league(league)
    if resolved == "unknown_league":
        return {"status": "unknown_league", "captured_at": None,
                "reason": f"'{league}' is not in SOCCER_LEAGUES -- add it there first"}
    if resolved == "not_covered" or config is None:
        reason = (config or {}).get("reason", "this league has no Odds API key")
        return {"status": "not_covered", "captured_at": None, "reason": reason,
                "league_canonical": canonical}

    sport_key, region = config["key"], config["region"]
    today = _dt.date.today()
    cache = None if force_refresh else _read_cache(sport_key, today)
    if cache is None:
        # Stage 1: league endpoint with BASE markets only (H1/corners 422).
        events, error = _fetch_odds_key(sport_key, region, SOCCER_BASE_MARKETS)
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
    # Stage 2: per-event endpoint for H1/corners/BTTS/team-totals the league
    # call can't carry. Cached per (event_id, day) so re-runs cost nothing.
    seg_tag = f"{sport_key}_segments_{event.get('id')}"
    seg_cache = None if force_refresh else _read_cache(seg_tag, today)
    if seg_cache is None and event.get("id"):
        seg_event, seg_error = _fetch_event_odds(
            sport_key, str(event["id"]), region, SOCCER_FULL_MARKETS)
        if seg_event is not None:
            _write_cache(seg_tag, today, region, [seg_event])
            seg_cache = {"events": [seg_event], "fetched_at": fetched_at}
    if seg_cache is not None:
        seg_market = _extract_soccer_market(seg_cache["events"][0])
        for key, value in seg_market.items():
            market.setdefault(key, value)
    if not market:
        return {"status": "no_bookmaker", "captured_at": fetched_at,
                "reason": "fixture found but no bookmaker has priced it yet"}
    if event.get("_swapped"):
        market["home_ml"], market["away_ml"] = market.get("away_ml"), market.get("home_ml")
        if "spread_home_price" in market or "spread_away_price" in market:
            market["spread_home_price"], market["spread_away_price"] = (
                market.get("spread_away_price"), market.get("spread_home_price"))
        if market.get("spread_line") is not None:
            try:
                market["spread_line"] = -float(market["spread_line"])
            except (TypeError, ValueError):
                pass
        for prefix in ("h1_",):
            if market.get(f"{prefix}home_ml") is not None or market.get(f"{prefix}away_ml") is not None:
                market[f"{prefix}home_ml"], market[f"{prefix}away_ml"] = (
                    market.get(f"{prefix}away_ml"), market.get(f"{prefix}home_ml"))
            if market.get(f"{prefix}spread_line") is not None:
                try:
                    market[f"{prefix}spread_line"] = -float(market[f"{prefix}spread_line"])
                except (TypeError, ValueError):
                    pass
            hp, ap = f"{prefix}spread_home_price", f"{prefix}spread_away_price"
            if hp in market or ap in market:
                market[hp], market[ap] = market.get(ap), market.get(hp)
    market.update({"status": "live" if cache is None else "cached", "captured_at": fetched_at})
    return market


def _extract_mlb_market(event: Dict[str, Any]) -> Dict[str, Any]:
    """Moneyline + run line + total from one Odds API baseball event."""
    out: Dict[str, Any] = {}
    for book in event.get("bookmakers", []) or []:
        for market in book.get("markets", []) or []:
            if market["key"] == "h2h" and "home_ml" not in out:
                for outcome in market.get("outcomes", []) or []:
                    name = outcome.get("name")
                    price = outcome.get("price")
                    if name == event.get("home_team"):
                        out["home_ml"] = price
                    elif name == event.get("away_team"):
                        out["away_ml"] = price
            if market["key"] == "totals" and "total_line" not in out:
                for outcome in market.get("outcomes", []) or []:
                    if outcome.get("point") is not None:
                        out["total_line"] = outcome["point"]
                    lname = str(outcome.get("name", "")).lower()
                    if lname == "over":
                        out["over_price"] = outcome.get("price")
                    elif lname == "under":
                        out["under_price"] = outcome.get("price")
            if market["key"] == "spreads" and "runline" not in out:
                for outcome in market.get("outcomes", []) or []:
                    point = outcome.get("point")
                    price = outcome.get("price")
                    name = str(outcome.get("name", ""))
                    if point is None:
                        continue
                    if name == event.get("home_team"):
                        out.setdefault("runline_home", point)
                        if price is not None:
                            out.setdefault("runline_home_price", price)
                    elif name == event.get("away_team"):
                        out.setdefault("runline_away", point)
                        if price is not None:
                            out.setdefault("runline_away_price", price)
                if "runline_home" in out or "runline_away" in out:
                    out["runline"] = out.get("runline_home", out.get("runline_away"))
        if "home_ml" in out and "total_line" in out and "runline" in out:
            break
    return out


def _extract_basketball_market(event: Dict[str, Any]) -> Dict[str, Any]:
    """FG + H1 + Q1 moneyline/spread/total from one Odds API basketball event.

    Keys locked by live discovery 2026-10-09 on the Olympiacos-Efes event:
    h2h/spreads/totals (FG, EU+US books), h2h_h1/spreads_h1/totals_h1 and
    h2h_q1/spreads_q1/totals_q1 (US books: fanduel/betmgm/betrivers).
    First book wins per market; a missing segment stays absent, never
    invented. Spread lines are home-signed.
    """
    out: Dict[str, Any] = {}

    def _h2h(market: Dict[str, Any], prefix: str) -> None:
        for outcome in market.get("outcomes", []) or []:
            name, price = outcome.get("name"), outcome.get("price")
            if name == event.get("home_team"):
                out[f"{prefix}home_ml"] = price
            elif name == event.get("away_team"):
                out[f"{prefix}away_ml"] = price
            elif name and str(name).lower() == "draw":
                out[f"{prefix}draw_ml"] = price

    def _spread(market: Dict[str, Any], prefix: str) -> None:
        for outcome in market.get("outcomes", []) or []:
            point, price = outcome.get("point"), outcome.get("price")
            name = str(outcome.get("name", ""))
            if point is None:
                continue
            if name == event.get("home_team"):
                out.setdefault(f"{prefix}spread_line", point)
                if price is not None:
                    out.setdefault(f"{prefix}spread_home_price", price)
            elif name == event.get("away_team"):
                if price is not None:
                    out.setdefault(f"{prefix}spread_away_price", price)
                if f"{prefix}spread_line" not in out:
                    try:
                        out[f"{prefix}spread_line"] = -float(point)
                    except (TypeError, ValueError):
                        pass

    def _total(market: Dict[str, Any], prefix: str) -> None:
        for outcome in market.get("outcomes", []) or []:
            if outcome.get("point") is not None:
                out[f"{prefix}total_line"] = outcome["point"]
            lname = str(outcome.get("name", "")).lower()
            if lname == "over":
                out[f"{prefix}over_price"] = outcome.get("price")
            elif lname == "under":
                out[f"{prefix}under_price"] = outcome.get("price")

    for book in event.get("bookmakers", []) or []:
        for market in book.get("markets", []) or []:
            key = market.get("key", "")
            if key == "h2h" and "home_ml" not in out:
                _h2h(market, "")
            elif key == "spreads" and "spread_line" not in out:
                _spread(market, "")
            elif key == "totals" and "total_line" not in out:
                _total(market, "")
            elif key == "h2h_h1" and "h1_home_ml" not in out:
                _h2h(market, "h1_")
            elif key == "spreads_h1" and "h1_spread_line" not in out:
                _spread(market, "h1_")
            elif key == "totals_h1" and "h1_total_line" not in out:
                _total(market, "h1_")
            elif key == "h2h_q1" and "q1_home_ml" not in out:
                _h2h(market, "q1_")
            elif key == "spreads_q1" and "q1_spread_line" not in out:
                _spread(market, "q1_")
            elif key == "totals_q1" and "q1_total_line" not in out:
                _total(market, "q1_")
        if "home_ml" in out:
            break
    return out


def get_basketball_odds(home: str, away: str, league: Optional[str] = "EuroLeague",
                        force_refresh: bool = False) -> Dict[str, Any]:
    """Auto-fetched basketball FG+H1+Q1 markets, cached per (league, day)."""
    config, canonical, resolved = resolve_basketball_league(league)
    if resolved == "unknown_league":
        return {"status": "unknown_league", "captured_at": None,
                "reason": f"'{league}' is not in BASKETBALL_LEAGUES -- add it there first"}
    if resolved == "not_covered" or config is None:
        reason = (config or {}).get("reason", "this league has no Odds API key")
        return {"status": "not_covered", "captured_at": None, "reason": reason,
                "league_canonical": canonical}
    sport_key, region = config["key"], config["region"]
    today = _dt.date.today()
    cache = None if force_refresh else _read_cache(sport_key, today)
    if cache is None:
        # Stage 1: league endpoint with BASE markets only (H1/Q1 422 here).
        events, error = _fetch_odds_key(sport_key, region, BASKETBALL_BASE_MARKETS)
        if error:
            return {"status": "error", "captured_at": None, "reason": error}
        fetched_at = _write_cache(sport_key, today, region, events)
    else:
        events, fetched_at = cache["events"], cache["fetched_at"]
    event = _find_event(events, home, away)
    if event is None:
        return {"status": "no_fixture", "captured_at": fetched_at,
                "reason": f"no odds-feed fixture matched {home!r} vs {away!r} in {sport_key} today"}
    market = _extract_basketball_market(event)
    # Stage 2: per-event endpoint for H1/Q1 segments the league call can't
    # carry. Cached per (event_id, day) so a slate re-run costs nothing.
    seg_tag = f"{sport_key}_segments_{event.get('id')}"
    seg_cache = None if force_refresh else _read_cache(seg_tag, today)
    if seg_cache is None and event.get("id"):
        seg_event, seg_error = _fetch_event_odds(
            sport_key, str(event["id"]), region, BASKETBALL_FULL_MARKETS)
        seg_keys = ({m.get("key", "") for b in (seg_event or {}).get("bookmakers", []) or []
                     for m in b.get("markets", []) or []} if seg_event else set())
        if (seg_event is None or not ({"h2h_q1", "spreads_q1", "totals_q1"} & seg_keys)) \
                and region != "us":
            # H1/Q1 segment books are US-region (fanduel/betmgm/betrivers) --
            # retry there so EuroLeague still prices every segment.
            us_event, us_error = _fetch_event_odds(
                sport_key, str(event["id"]), "us", BASKETBALL_FULL_MARKETS)
            if us_event is not None:
                seg_event, seg_error = us_event, us_error
        if seg_event is not None:
            _write_cache(seg_tag, today, region, [seg_event])
            seg_cache = {"events": [seg_event], "fetched_at": fetched_at}
    if seg_cache is not None:
        seg_market = _extract_basketball_market(seg_cache["events"][0])
        for key, value in seg_market.items():
            market.setdefault(key, value)
    if not market:
        return {"status": "no_bookmaker", "captured_at": fetched_at,
                "reason": "fixture found but no bookmaker has priced it yet"}
    if event.get("_swapped"):
        market["home_ml"], market["away_ml"] = market.get("away_ml"), market.get("home_ml")
        if market.get("h1_home_ml") is not None or market.get("h1_away_ml") is not None:
            market["h1_home_ml"], market["h1_away_ml"] = (
                market.get("h1_away_ml"), market.get("h1_home_ml"))
        if market.get("q1_home_ml") is not None or market.get("q1_away_ml") is not None:
            market["q1_home_ml"], market["q1_away_ml"] = (
                market.get("q1_away_ml"), market.get("q1_home_ml"))
        for prefix in ("", "h1_", "q1_"):
            if market.get(f"{prefix}spread_line") is not None:
                try:
                    market[f"{prefix}spread_line"] = -float(market[f"{prefix}spread_line"])
                except (TypeError, ValueError):
                    pass
            hp, ap = f"{prefix}spread_home_price", f"{prefix}spread_away_price"
            if hp in market or ap in market:
                market[hp], market[ap] = market.get(ap), market.get(hp)
    market.update({"status": "live" if cache is None else "cached", "captured_at": fetched_at})
    return market


def get_mlb_odds(home: str, away: str,
                 force_refresh: bool = False) -> Dict[str, Any]:
    """Auto-fetched MLB moneyline + run line + total, cached per day.

    Same contract as get_soccer_odds: always carries "status" and
    "captured_at", never invents a price. KBO is not in the MLB odds
    feed -- callers must keep their KBO default and label it simulation.
    """
    sport_key, region = "baseball_mlb", "us"
    today = _dt.date.today()
    cache = None if force_refresh else _read_cache(sport_key, today)
    if cache is None:
        events, error = _fetch_odds_key(sport_key, region, "h2h,spreads,totals")
        if error:
            return {"status": "error", "captured_at": None, "reason": error}
        fetched_at = _write_cache(sport_key, today, region, events)
    else:
        events, fetched_at = cache["events"], cache["fetched_at"]

    event = _find_event(events, home, away)
    if event is None:
        return {"status": "no_fixture", "captured_at": fetched_at,
                "reason": f"no odds-feed fixture matched {home!r} vs {away!r} in {sport_key} today "
                          f"(offseason or schedule gap, not an error)"}

    market = _extract_mlb_market(event)
    if not market:
        return {"status": "no_bookmaker", "captured_at": fetched_at,
                "reason": "fixture found but no bookmaker has priced it yet"}
    if event.get("_swapped"):
        market["home_ml"], market["away_ml"] = market.get("away_ml"), market.get("home_ml")
        market["runline_home"], market["runline_away"] = (
            market.get("runline_away"), market.get("runline_home"))
        market["runline_home_price"], market["runline_away_price"] = (
            market.get("runline_away_price"), market.get("runline_home_price"))
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


def _extract_tennis_lines(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Pair prices within one book/line; orient handicaps to requested first player."""
    import math
    kinds = {"totals": "games_total", "alternate_totals": "games_total",
             "spreads": "games_spread", "alternate_spreads": "games_spread",
             "alternate_set_totals": "sets_total", "alternate_set_spreads": "sets_spread"}
    first = event.get("away_team") if event.get("_swapped") else event.get("home_team")
    second = event.get("home_team") if event.get("_swapped") else event.get("away_team")
    rows, seen = [], set()
    for book in event.get("bookmakers", []) or []:
        for market in book.get("markets", []) or []:
            kind = kinds.get(market.get("key"))
            if not kind:
                continue
            groups = {}
            for outcome in market.get("outcomes", []) or []:
                try:
                    point, price = float(outcome["point"]), float(outcome["price"])
                    if not math.isfinite(point) or not math.isfinite(price) or abs(price) < 100 or abs(point*2-round(point*2)) > 1e-8:
                        continue
                except (KeyError, TypeError, ValueError):
                    continue
                name = outcome.get("name")
                if kind.endswith("total"):
                    if name not in ("Over", "Under") or point < 0:
                        continue
                    side, line = ("a" if name == "Over" else "b"), point
                else:
                    if name not in (first, second):
                        continue
                    side, line = ("a", point) if name == first else ("b", -point)
                groups.setdefault(line, {})[side] = price
            for line, pair in groups.items():
                identity = (kind, line, book.get("key"))
                if set(pair) != {"a", "b"} or identity in seen:
                    continue
                seen.add(identity)
                rows.append(dict(kind=kind, line=line, price_a=pair["a"], price_b=pair["b"],
                                 line_origin="live sportsbook feed", bookmaker=book.get("title") or book.get("key"),
                                 bookmaker_key=book.get("key"), last_update=market.get("last_update") or book.get("last_update"),
                                 event_id=event.get("id"), market_key=market.get("key")))
    return rows


def _fetch_tennis_extra(sport_key: str, event_id: str):
    """Additional full-match markets require the provider's event endpoint."""
    if requests is None or not _api_key():
        return None, "Odds API unavailable"
    try:
        response = requests.get(f"{ODDS_BASE}/sports/{sport_key}/events/{event_id}/odds",
            params={"apiKey": _api_key(), "regions": "us", "oddsFormat": "american",
                    "markets": "alternate_totals,alternate_spreads,alternate_set_totals,alternate_set_spreads"},
            headers={"User-Agent": UA}, timeout=20)
        if response.status_code != 200:
            return None, f"HTTP {response.status_code}"
        return response.json(), None
    except Exception as exc:
        return None, type(exc).__name__  # Never expose the credential-bearing request URL.


def get_tennis_odds(tour: str, home: str, away: str,
                    force_refresh: bool = False) -> Dict[str, Any]:
    """Fetch moneyline, game lines and supported additional full-match markets.

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
        cache_tag = sport_key + "_full_match_v1"
        cache = None if force_refresh else _read_cache(cache_tag, today, max_age_hours=0.25)
        if cache is None:
            events, error = _fetch_odds_key(sport_key, "us", "h2h,spreads,totals")
            if error:
                continue
            fetched_at = _write_cache(cache_tag, today, "us", events)
        else:
            events, fetched_at = cache["events"], cache["fetched_at"]

        event = _find_tennis_event(events, home, away)
        if event is None:
            continue
        try:
            starts = _dt.datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))
            if starts <= _dt.datetime.now(_dt.timezone.utc):
                return {"status": "in_play", "captured_at": fetched_at,
                        "reason": "Matched fixture has started; this pre-match model cannot use in-play odds."}
        except (KeyError, TypeError, ValueError):
            return {"status": "error", "captured_at": fetched_at, "reason": "Fixture start time missing or invalid"}
        market = _extract_soccer_market(event)  # same h2h shape, no draw possible
        if not market:
            continue
        if event.get("_swapped"):
            market["home_ml"], market["away_ml"] = market.get("away_ml"), market.get("home_ml")
        lines = _extract_tennis_lines(event)
        extra_tag = sport_key + "_extras_" + event["id"]
        extra_cache = None if force_refresh else _read_cache(extra_tag, today, max_age_hours=0.25)
        extra_error = None
        if extra_cache is None:
            extra, extra_error = _fetch_tennis_extra(sport_key, event["id"])
            if extra is not None:
                _write_cache(extra_tag, today, "us", [extra])
        else:
            extra = extra_cache["events"][0]
        if extra:
            extra = dict(extra, _swapped=event.get("_swapped", False))
            extras = _extract_tennis_lines(extra)
            existing = {(r["kind"], r["line"], r["bookmaker_key"]) for r in lines}
            lines += [r for r in extras if (r["kind"], r["line"], r["bookmaker_key"]) not in existing]
        market["custom_markets"] = lines
        market["additional_markets_error"] = extra_error
        market.update({"status": "live" if cache is None else "cached",
                      "captured_at": fetched_at, "tournament_key": sport_key,
                      "commence_time": event.get("commence_time"), "event_id": event.get("id")})
        return market

    return {"status": "no_fixture", "captured_at": None,
            "reason": f"no odds-feed fixture matched {home!r} vs {away!r} in "
                     f"{', '.join(tournament_keys)}"}
