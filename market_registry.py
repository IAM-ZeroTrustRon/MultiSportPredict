"""Required market families and provider-key adapters.

Provider support is a per-league runtime fact, not implied by a family being
listed here. An unverified sport key is probed but never reported as covered
until an event and a quote are actually returned.
"""

from __future__ import annotations

from typing import Dict, List, Tuple


BASKETBALL_LEAGUES = {
    "NBA": {"key": "basketball_nba", "region": "us", "verified": True},
    "WNBA": {"key": "basketball_wnba", "region": "us", "verified": True},
    "NCAAB": {"key": "basketball_ncaab", "region": "us", "verified": True},
    "NCAAW": {"key": "basketball_wncaab", "region": "us", "verified": True},
    "EUROLEAGUE": {"key": "basketball_euroleague", "region": "eu", "verified": False},
    "KBL": {"key": None, "region": "kr", "verified": False},
    "NZNBL": {"key": None, "region": "au", "verified": False},
    "BBL": {"key": None, "region": "eu", "verified": False},
}

_BB_MARKETS: List[Tuple[str, str, str, List[str]]] = [
    ("q1", "moneyline", "1st Quarter moneyline", ["h2h_q1", "h2h_3_way_q1"]),
    ("q1", "spread", "1st Quarter spread", ["spreads_q1", "alternate_spreads_q1"]),
    ("q1", "total", "1st Quarter total", ["totals_q1", "alternate_totals_q1"]),
    ("q1", "home_team_total", "1st Quarter home team total", ["team_totals_q1", "alternate_team_totals_q1"]),
    ("q1", "away_team_total", "1st Quarter away team total", ["team_totals_q1", "alternate_team_totals_q1"]),
    ("h1", "moneyline", "1st Half moneyline", ["h2h_h1", "h2h_3_way_h1"]),
    ("h1", "spread", "1st Half spread", ["spreads_h1", "alternate_spreads_h1"]),
    ("h1", "total", "1st Half total", ["totals_h1", "alternate_totals_h1"]),
    ("h1", "home_team_total", "1st Half home team total", ["team_totals_h1", "alternate_team_totals_h1"]),
    ("h1", "away_team_total", "1st Half away team total", ["team_totals_h1", "alternate_team_totals_h1"]),
    ("fg", "moneyline", "Full Game moneyline", ["h2h"]),
    ("fg", "spread", "Full Game spread", ["spreads", "alternate_spreads"]),
    ("fg", "total", "Full Game total", ["totals", "alternate_totals"]),
    ("fg", "home_team_total", "Full Game home team total", ["team_totals", "alternate_team_totals"]),
    ("fg", "away_team_total", "Full Game away team total", ["team_totals", "alternate_team_totals"]),
]
for _prop in ("points", "rebounds", "assists"):
    _BB_MARKETS.append(("fg", f"player_{_prop}", f"Player {_prop}", [f"player_{_prop}"]))

_SOCCER_MARKETS: List[Tuple[str, str, str, List[str]]] = [
    ("h1", "moneyline_3way", "1st Half 1X2", ["h2h_3_way_h1", "h2h_h1"]),
    ("h1", "asian_handicap", "1st Half Asian handicap", ["spreads_h1", "alternate_spreads_h1"]),
    ("h1", "match_total", "1st Half match goals", ["totals_h1", "alternate_totals_h1"]),
    ("h1", "home_team_total", "1st Half home team goals", ["team_totals_h1", "alternate_team_totals_h1"]),
    ("h1", "away_team_total", "1st Half away team goals", ["team_totals_h1", "alternate_team_totals_h1"]),
    ("fg", "moneyline_3way", "Full Game 1X2", ["h2h"]),
    ("fg", "asian_handicap", "Full Game Asian handicap", ["spreads", "alternate_spreads"]),
    ("fg", "match_total", "Full Game match goals", ["totals", "alternate_totals"]),
    ("fg", "home_team_total", "Full Game home team goals", ["team_totals", "alternate_team_totals"]),
    ("fg", "away_team_total", "Full Game away team goals", ["team_totals", "alternate_team_totals"]),
    ("fg", "corner_total", "Full Game corners", ["alternate_totals_corners"]),
    ("fg", "home_corner_total", "Home team corners", ["alternate_team_totals_corners"]),
    ("fg", "away_corner_total", "Away team corners", ["alternate_team_totals_corners"]),
    ("fg", "corner_handicap", "Corner handicap", ["alternate_spreads_corners"]),
    ("h1", "corner_total", "1st Half corners", ["alternate_totals_corners_h1"]),
    ("h1", "home_corner_total", "1st Half home team corners", ["alternate_team_totals_corners_h1"]),
    ("h1", "away_corner_total", "1st Half away team corners", ["alternate_team_totals_corners_h1"]),
    ("h1", "corner_handicap", "1st Half corner handicap", ["alternate_spreads_corners_h1"]),
    ("fg", "anytime_scorer", "Anytime goalscorer", ["player_goal_scorer_anytime", "player_anytime_goalscorer"]),
]


def _normalise_league(value: str) -> str:
    cleaned = " ".join(value.upper().replace("GERMAN ", "").replace("NEW ZEALAND ", "").split())
    aliases = {"EUROLEAGUE": "EUROLEAGUE", "EURO LEAGUE": "EUROLEAGUE",
               "NZ NBL": "NZNBL", "NBL": "NZNBL", "BUNDESLIGA": "BBL",
               "GERMAN BBL": "BBL", "COLLEGE": "NCAAB"}
    return aliases.get(cleaned, cleaned)


def basketball_source(league: str):
    canonical = _normalise_league(league)
    return canonical, BASKETBALL_LEAGUES.get(canonical)


def market_families(sport: str):
    return list(_BB_MARKETS if sport.lower() == "basketball" else _SOCCER_MARKETS)


def market_keys(sport: str) -> List[str]:
    return sorted({key for _, _, _, keys in market_families(sport) for key in keys})
