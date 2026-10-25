#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
fixture_guard.py — Verify Fixtures Exist Before Prediction
============================================================
Prevents predictions for matches that don't exist. Returns the real
home/away orientation from the API so models apply home advantage
to the correct side.

Usage:
    from fixture_guard import verify_fixture
    valid, message, home_is_actual = verify_fixture("baseball", "LG Twins", "Lotte Giants", "2026-08-31")
    if not valid:
        print(f"Cannot run prediction: {message}")
        return

    from fixture_guard import verify_fixture
    valid, message, home_order = verify_fixture("soccer", "Manchester United", "Liverpool", "2026-08-31", "Premier League")
    if home_order is not None:
        if home_order == "reversed":
            print(f"Feed says {message} is home; reversing teams")
"""

from __future__ import annotations

import json
import re
from datetime import datetime, date as calendar_date
import unicodedata
from zoneinfo import ZoneInfo
from typing import Tuple, Optional

try:
    import requests
except ImportError:
    requests = None  # type: ignore


def verify_fixture(
    sport: str,
    home: str,
    away: str,
    date: str,
    league: Optional[str] = None,
) -> Tuple[bool, str, Optional[str]]:
    """
    Verify a fixture exists and return actual home/away orientation.

    Args:
        sport: "baseball" | "mlb" | "kbo" | "soccer" | "tennis"
        home: Home team/player name
        away: Away team/player name
        date: YYYY-MM-DD; soccer uses America/New_York, matching msp.py
        league: League name (optional, helps narrow search for soccer/tennis)

    Returns:
        (is_valid, message, home_orientation)
        - is_valid: True if fixture found/verified
        - message: Human-readable result or reason for refusal
        - home_orientation: None if not verified; "correct" if home param matches
          feed; "reversed" if home and away are swapped in the feed
    """
    sport = sport.strip().lower()
    if sport in ("baseball", "mlb"):
        return _verify_mlb(home, away, date)
    if sport == "kbo":
        return _verify_kbo(home, away, date)
    if sport in ("soccer", "football"):
        return _verify_soccer(home, away, date, league)
    if sport == "tennis":
        return _verify_tennis(home, away, date, league)
    return False, f"Unknown sport: {sport}", None


def _verify_mlb(home: str, away: str, date: str) -> Tuple[bool, str, Optional[str]]:
    """Verify MLB fixture via statsapi.mlb.com."""
    if not requests:
        return False, "requests library not available", None

    try:
        url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date}"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        games = resp.json() or []

        # Normalize team names for matching
        home_norm = home.strip().lower()
        away_norm = away.strip().lower()

        for game in games:
            home_team = game.get("teams", {}).get("home", {}).get("team", {}).get("name", "").lower()
            away_team = game.get("teams", {}).get("away", {}).get("team", {}).get("name", "").lower()

            if (home_norm in home_team or home_team in home_norm) and \
               (away_norm in away_team or away_team in away_norm):
                feed_home = game.get("teams", {}).get("home", {}).get("team", {}).get("name", "?")
                feed_away = game.get("teams", {}).get("away", {}).get("team", {}).get("name", "?")
                return True, f"MLB game found: {feed_home} vs {feed_away}", "correct"

        return False, f"No MLB game found on {date} matching {home} vs {away}", None

    except Exception as e:
        return False, f"MLB fixture check failed: {e}", None


def _verify_kbo(home: str, away: str, date: str) -> Tuple[bool, str, Optional[str]]:
    """Verify KBO fixture via mykbostats.com."""
    if not requests:
        return False, "requests library not available", None

    try:
        # mykbostats.com structure: /schedule/?year=2026&month=8&day=31
        parts = date.split("-")
        if len(parts) != 3:
            return False, f"Invalid date format (expect YYYY-MM-DD): {date}", None
        year, month, day = parts

        url = f"https://www.mykbostats.com/schedule/?year={year}&month={month}&day={day}"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        text = resp.text

        # Look for team names in the HTML (rough pattern match)
        home_norm = home.strip().lower()
        away_norm = away.strip().lower()

        # Common KBO team abbreviations and names
        team_map = {
            "lg twins": "lg", "lotte giants": "lotte", "kia tigers": "kia",
            "samsung lions": "samsung", "sk wyverns": "sk", "nc dinos": "nc",
            "doosan bears": "doosan", "hanwha eagles": "hanwha", "kiwoom heroes": "kiwoom",
        }

        home_key = team_map.get(home_norm, home_norm)
        away_key = team_map.get(away_norm, away_norm)

        if home_key in text and away_key in text:
            return True, f"KBO game found on {date}: {home} vs {away}", "correct"

        return False, f"No KBO game found on {date} matching {home} vs {away}", None

    except Exception as e:
        return False, f"KBO fixture check failed: {e}", None


# League names are explicit: unknown/missing competitions must never query EPL.
SOCCER_LEAGUE_KEYS = {
    "epl": "eng.1", "premier league": "eng.1", "championship": "eng.2",
    "serie a": "ita.1", "serie b": "ita.2", "la liga": "esp.1",
    "bundesliga": "ger.1", "ligue 1": "fra.1", "eredivisie": "ned.1",
    "liga mx": "mex.1", "mls": "usa.1",
}
SOCCER_DATE_ZONE = ZoneInfo("America/New_York")


def _soccer_name_key(value):
    """Exact accent/punctuation-insensitive identity; never substring/fuzzy match."""
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(c for c in text if c.isalnum() and not unicodedata.combining(c))


# Only explicit variants of the two Bundesliga identities involved in the
# recorded failure. Other short names must actually be published in the feed.
SOCCER_NAME_ALIASES = {"ger.1": {
    "stuttgart": "vfbstuttgart",
    "mgladbach": "borussiamonchengladbach",
    "gladbach": "borussiamonchengladbach",
    "borussiamoenchengladbach": "borussiamonchengladbach",
}}


def _verify_soccer(home: str, away: str, date: str, league: Optional[str]) -> Tuple[bool, str, Optional[str]]:
    """Verify a unique dated ESPN card, retaining the public orientation tuple.

    ESPN's date query selects the board, but the card's timezone-aware kickoff
    is independently checked against the requested project (Eastern) date.
    This verifies fixture identity, not data readiness or betting eligibility.
    """
    league_norm = " ".join(str(league or "").casefold().split())
    league_key = SOCCER_LEAGUE_KEYS.get(league_norm)
    if league_key is None:
        return False, f"Unsupported soccer league {league!r}; supply a configured competition (no default league)", None
    try:
        requested = calendar_date.fromisoformat(date)
        if requested.isoformat() != date:
            raise ValueError("Use YYYY-MM-DD")
    except (TypeError, ValueError):
        return False, f"Invalid soccer fixture date {date!r}; expected YYYY-MM-DD", None
    aliases = SOCCER_NAME_ALIASES.get(league_key, {})
    def key(name):
        normalized = _soccer_name_key(name)
        return aliases.get(normalized, normalized)
    home_key, away_key = key(home), key(away)
    if not home_key or not away_key or home_key == away_key:
        return False, "Soccer fixture requires two distinct nonempty team names", None
    if not requests:
        return False, "requests library not available", None
    try:
        url = f"https://site.web.api.espn.com/apis/site/v2/sports/soccer/{league_key}/scoreboard"
        resp = requests.get(url, params={"dates": requested.strftime("%Y%m%d")}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict) or not isinstance(data.get("events"), list):
            return False, "Soccer scoreboard has no valid events list; fixture unverified", None
        matches = []
        for event in data["events"]:
            if not isinstance(event, dict) or not isinstance(event.get("competitions"), list):
                continue
            for comp in event["competitions"]:
                if not isinstance(comp, dict):
                    continue
                try:
                    kickoff = datetime.fromisoformat(str(comp.get("date") or event.get("date")).replace("Z", "+00:00"))
                    if kickoff.tzinfo is None or kickoff.astimezone(SOCCER_DATE_ZONE).date() != requested:
                        continue
                    if comp.get("date") and event.get("date"):
                        event_start = datetime.fromisoformat(str(event["date"]).replace("Z", "+00:00"))
                        if event_start.tzinfo is None or event_start != kickoff:
                            continue
                except (TypeError, ValueError):
                    continue
                status = comp.get("status") or event.get("status") or {}
                if not isinstance(status, dict) or not isinstance(status.get("type", {}), dict):
                    continue
                state = str(status.get("type", {}).get("name", "")).upper()
                if any(token in state for token in ("POSTPONED", "CANCELED", "CANCELLED", "SUSPENDED", "ABANDONED")):
                    continue
                competitors = comp.get("competitors")
                if not isinstance(competitors, list) or len(competitors) != 2:
                    continue
                sides = {}
                for competitor in competitors:
                    if not isinstance(competitor, dict):
                        break
                    side, team = competitor.get("homeAway"), competitor.get("team")
                    if side not in {"home", "away"} or side in sides or not isinstance(team, dict) or not team.get("displayName"):
                        break
                    sides[side] = team
                if set(sides) != {"home", "away"}:
                    continue
                names = {side: {key(team.get(field)) for field in ("displayName", "shortDisplayName", "name", "abbreviation") if team.get(field)}
                         for side, team in sides.items()}
                if any(candidate in names["home"] and candidate in names["away"] for candidate in (home_key, away_key)):
                    return False, "Ambiguous soccer team identities in feed; fixture unverified", None
                orientations = []
                if home_key in names["home"] and away_key in names["away"]:
                    orientations.append("correct")
                if home_key in names["away"] and away_key in names["home"]:
                    orientations.append("reversed")
                # Shared aliases cannot establish which team is which.
                if len(orientations) > 1:
                    return False, "Ambiguous soccer team identities in feed; fixture unverified", None
                if orientations:
                    ident = str(comp.get("id") or event.get("id") or "").strip()
                    if ident:
                        matches.append((orientations[0], sides["home"]["displayName"], sides["away"]["displayName"], ident, kickoff))
        if len(matches) > 1:
            return False, f"Ambiguous soccer fixture: {len(matches)} matching cards in {league} on {date}", None
        if not matches:
            return False, f"No uniquely verified soccer match in {league} on {date} (America/New_York): {home} vs {away}", None
        orientation, actual_home, actual_away, ident, kickoff = matches[0]
        return True, (f"Soccer fixture verified: Home {actual_home} | Away {actual_away} | "
                      f"Date {date} (America/New_York) | Kickoff {kickoff.isoformat()} | Event {ident}"), orientation
    except Exception as exc:
        # Keep network/parse failures a refusal without exposing request details.
        return False, f"Soccer fixture check failed ({type(exc).__name__}); check source availability and retry", None


def _verify_tennis(home: str, away: str, date: str, league: Optional[str]) -> Tuple[bool, str, Optional[str]]:
    """Tennis: no reachable draw feed."""
    return False, "Tennis fixture verification: no reachable draw feed available", None


if __name__ == "__main__":
    import sys

    # Windows redirected output may default to cp1252, which cannot print the
    # verification marker (or all team names). Match the other UTF-8 runners.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 5:
        print("Usage: fixture_guard.py <sport> <home> <away> <date> [league]")
        sys.exit(1)

    sport_arg = sys.argv[1]
    home_arg = sys.argv[2]
    away_arg = sys.argv[3]
    date_arg = sys.argv[4]
    league_arg = sys.argv[5] if len(sys.argv) > 5 else None

    valid, msg, orientation = verify_fixture(sport_arg, home_arg, away_arg, date_arg, league_arg)
    status = "✓" if valid else "✗"
    print(f"{status} {msg}")
    if orientation:
        print(f"  Home orientation: {orientation}")
    sys.exit(0 if valid else 1)
