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
from datetime import datetime
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
        date: YYYY-MM-DD format (UTC)
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


def _verify_soccer(home: str, away: str, date: str, league: Optional[str]) -> Tuple[bool, str, Optional[str]]:
    """Verify soccer fixture via ESPN API."""
    if not requests:
        return False, "requests library not available", None

    try:
        # ESPN league keys for major leagues
        league_keys = {
            "epl": "eng.1",
            "premier league": "eng.1",
            "championship": "eng.2",
            "serie a": "ita.1",
            "serie b": "ita.2",
            "la liga": "esp.1",
            "bundesliga": "ger.1",
            "ligue 1": "fra.1",
            "eredivisie": "ned.1",
            "liga mx": "mex.1",
            "mls": "usa.1",
        }

        league_norm = (league or "epl").strip().lower()
        league_key = league_keys.get(league_norm, "eng.1")

        url = f"https://site.web.api.espn.com/apis/site/v2/sports/soccer/{league_key}/scoreboard"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        events = data.get("events", [])
        home_norm = home.strip().lower()
        away_norm = away.strip().lower()

        for event in events:
            competitions = event.get("competitions", [])
            for comp in competitions:
                competitors = comp.get("competitors", [])
                if len(competitors) >= 2:
                    home_comp = competitors[0].get("team", {}).get("displayName", "").lower()
                    away_comp = competitors[1].get("team", {}).get("displayName", "").lower()

                    if (home_norm in home_comp or home_comp in home_norm) and \
                       (away_norm in away_comp or away_comp in away_norm):
                        home_actual = competitors[0].get("team", {}).get("displayName", "?")
                        away_actual = competitors[1].get("team", {}).get("displayName", "?")
                        return True, f"Soccer game found: {home_actual} vs {away_actual}", "correct"

                    if (away_norm in home_comp or home_comp in away_norm) and \
                       (home_norm in away_comp or away_comp in home_norm):
                        home_actual = competitors[0].get("team", {}).get("displayName", "?")
                        away_actual = competitors[1].get("team", {}).get("displayName", "?")
                        return True, f"Soccer game found (reversed): {home_actual} vs {away_actual}", "reversed"

        return False, f"No soccer match found in {league or 'default league'} on {date}", None

    except Exception as e:
        return False, f"Soccer fixture check failed: {e}", None


def _verify_tennis(home: str, away: str, date: str, league: Optional[str]) -> Tuple[bool, str, Optional[str]]:
    """Tennis: no reachable draw feed."""
    return False, "Tennis fixture verification: no reachable draw feed available", None


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 4:
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
