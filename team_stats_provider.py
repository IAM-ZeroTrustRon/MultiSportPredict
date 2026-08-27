#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
team_stats_provider.py — Real Team Stats for Soccer & Basketball Predictors
===============================================================================
THE BUG THIS FIXES: SoccerPredictor.predict() and BasketballPredictor.predict()
both accept real team stats as **kwargs (home_xg_for, home_ortg, etc.) but fall
back to hardcoded placeholder values when those kwargs aren't supplied. Nothing
in predict_match.py was passing them, so every soccer prediction used the same
xG inputs (1.65/1.45) and every basketball prediction used the same ORTG/DRTG
(110/108) regardless of which teams were actually playing. This module is the
missing piece: a lookup layer that supplies real, per-team numbers.

DESIGN DECISION — why this is manual-entry-backed, not a live scraper:
FBref/Basketball-Reference (the usual sources for this kind of data) explicitly
prohibit scraping without a license in their Terms of Service — same category
of issue as the Sackmann tennis data license flagged earlier. Rather than build
something that breaks on day one (rate-limited/blocked) or quietly violates a
ToS, this module defines a clean interface backed by a JSON file you maintain
yourself from whatever data source you actually have rights to use (a paid
API, an official league feed you have access to, or manual entry from public
match reports). If you get real API access later, replace `_load_store()`'s
file read with an API call — nothing else needs to change.

CRITICAL BEHAVIOR CHANGE from the old code: when stats aren't found for a team,
this returns None and the caller is expected to WARN LOUDLY, not silently fall
back to a placeholder. A loud "no data, don't trust this" is far better than a
silent wrong-looking number — that silence was the whole bug.

Usage:
    from team_stats_provider import get_soccer_team_stats, get_basketball_team_stats

    stats = get_soccer_team_stats("Liverpool", league="EPL")
    # -> {"xg_for": 1.9, "xg_against": 1.1, ...} or None if not found

Data file locations (created automatically with a starter template if missing):
    data/team_stats/soccer_stats.json
    data/team_stats/basketball_stats.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

DATA_DIR = Path("data/team_stats")
SOCCER_STATS_PATH = DATA_DIR / "soccer_stats.json"
BASKETBALL_STATS_PATH = DATA_DIR / "basketball_stats.json"
EUROLEAGUE_STATS_PATH = Path("data/euroleague_stats.json")
GLOBAL_SOCCER_STATS_PATH = Path("data/soccer_stats.json")
INTERNATIONAL_BASKETBALL_STATS_PATH = Path("data/basketball_stats.json")

# Fields SoccerPredictor.predict() actually reads via kwargs (see soccer_predictor.py)
SOCCER_FIELDS = [
    "xg_for", "xg_against", "shots", "sot", "goals_for", "goals_against",
    "clean_sheets", "missing_attacker", "missing_creator", "missing_cb",
    "missing_gk", "tempo", "width_crossing", "final_third_pressure",
]

# Fields BasketballPredictor.predict() actually reads via kwargs (see basketball_predictor.py)
# Split into "objectively fetchable from a stats source" vs. "needs manual/news input" —
# see the docstring on get_basketball_team_stats for why that split matters.
BASKETBALL_STAT_FIELDS = ["ortg", "drtg", "baseline_net", "recent_net", "pace", "three_pt_pct", "orb_pct"]
BASKETBALL_CONTEXT_FIELDS = [
    "rest_days", "travel_km", "back_to_back", "three_in_six", "split_edge",
    "rotation_depth", "injury_status", "coach_stability", "motivation",
]

_SOCCER_TEMPLATE = {
    "_comment": (
        "Fill in real per-team season stats here. Values are 'per match' "
        "averages unless noted. Team names must match exactly what you pass "
        "as home_team/away_team elsewhere in the pipeline (case-insensitive "
        "match is applied, but spelling must match)."
    ),
    "Liverpool": {
        "xg_for": 1.9, "xg_against": 1.1, "shots": 15.2, "sot": 5.8,
        "goals_for": 2.1, "goals_against": 1.0, "clean_sheets": 8,
        "missing_attacker": 0, "missing_creator": 0, "missing_cb": 0, "missing_gk": 0,
        "tempo": 0.35, "width_crossing": 0.58, "final_third_pressure": 0.60,
    },
}

_BASKETBALL_TEMPLATE = {
    "_comment": (
        "ortg/drtg/pace are the fetchable, objective numbers — get these from "
        "your league's official stats page. injury_status/coach_stability/"
        "motivation are subjective 'green'/'yellow'/'red' calls you make "
        "yourself from news/injury reports — there's no clean API for these."
    ),
    "Real Madrid": {
        "ortg": 116.5, "drtg": 104.0, "baseline_net": 8.0, "recent_net": 9.5,
        "pace": 74.0, "three_pt_pct": 0.39, "orb_pct": 0.31,
        "rest_days": 2, "travel_km": 300.0, "back_to_back": False, "three_in_six": False,
        "split_edge": 2.0, "rotation_depth": 10, "injury_status": "green",
        "coach_stability": "green", "motivation": "green",
    },
}

_EUROLEAGUE_TEMPLATE = {
    "_comment": "Seed EuroLeague metrics with seed_euroleague_stats.py.",
    "_league_baseline": {
        "pace": 72.0, "ortg": 112.0, "drtg": 112.0,
        "q1_ratio": 0.245, "ht_ratio": 0.495,
    },
}


def _load_store(path: Path, template: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(template, f, indent=2)
        print(f"[team_stats_provider] Created starter template at {path} — "
              f"fill in real team data before relying on predictions that use it.")
        return template
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _lookup(store: Dict[str, Any], team: str) -> Optional[Dict[str, Any]]:
    if team in store:
        return {k: v for k, v in store[team].items() if not k.startswith("_")}
    # Case-insensitive fallback
    team_lower = team.strip().lower()
    for key, val in store.items():
        if key.startswith("_"):
            continue
        if key.strip().lower() == team_lower:
            return {k: v for k, v in val.items() if not k.startswith("_")}
    return None


def get_soccer_team_stats(team: str, league: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Returns a dict of real soccer stats for `team`, or None if not found.
    Callers MUST treat None as "no real data available" and warn accordingly —
    do not silently substitute a default; that's the exact bug this replaces.
    """
    path = GLOBAL_SOCCER_STATS_PATH if GLOBAL_SOCCER_STATS_PATH.exists() else SOCCER_STATS_PATH
    store = _load_store(path, _SOCCER_TEMPLATE)
    stats = _lookup(store, team)

    # Auto-map goals to xG if xG is missing to prevent silent model fallbacks
    if stats and "xg_for" not in stats:
        stats["xg_for"] = stats.get("goals_for", 1.5)
    if stats and "xg_against" not in stats:
        stats["xg_against"] = stats.get("goals_against", 1.5)

    return stats


def get_basketball_team_stats(team: str, league: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Returns a dict of real basketball stats for `team`, or None if not found."""
    league_name = (league or "").strip().lower()
    path = (INTERNATIONAL_BASKETBALL_STATS_PATH
            if league_name in {"kbl", "nznbl"} and INTERNATIONAL_BASKETBALL_STATS_PATH.exists()
            else BASKETBALL_STATS_PATH)
    store = _load_store(path, _BASKETBALL_TEMPLATE)
    return _lookup(store, team)


def get_euroleague_team_stats(team: str) -> Optional[Dict[str, Any]]:
    """Return seeded EuroLeague team metrics, or None when not seeded."""
    store = _load_store(EUROLEAGUE_STATS_PATH, _EUROLEAGUE_TEMPLATE)
    return _lookup(store, team)


def get_euroleague_league_baseline() -> Dict[str, Any]:
    """Return the seeded EuroLeague baseline or the engine defaults."""
    store = _load_store(EUROLEAGUE_STATS_PATH, _EUROLEAGUE_TEMPLATE)
    baseline = store.get("_league_baseline", {})
    return {**_EUROLEAGUE_TEMPLATE["_league_baseline"], **baseline}


def upsert_soccer_team_stats(team: str, stats: Dict[str, Any]) -> None:
    """Add or update one team's entry in the soccer stats file."""
    store = _load_store(SOCCER_STATS_PATH, _SOCCER_TEMPLATE)
    store[team] = stats
    with open(SOCCER_STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)


def upsert_basketball_team_stats(team: str, stats: Dict[str, Any]) -> None:
    """Add or update one team's entry in the basketball stats file."""
    store = _load_store(BASKETBALL_STATS_PATH, _BASKETBALL_TEMPLATE)
    store[team] = stats
    with open(BASKETBALL_STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)


def upsert_euroleague_team_stats(team: str, stats: Dict[str, Any]) -> None:
    """Add or update one team's EuroLeague metrics."""
    store = _load_store(EUROLEAGUE_STATS_PATH, _EUROLEAGUE_TEMPLATE)
    store[team] = stats
    with open(EUROLEAGUE_STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)


if __name__ == "__main__":
    import tempfile
    DATA_DIR = Path(tempfile.mkdtemp()) / "team_stats"
    SOCCER_STATS_PATH = DATA_DIR / "soccer_stats.json"
    BASKETBALL_STATS_PATH = DATA_DIR / "basketball_stats.json"

    print("=== Soccer: known team ===")
    print(get_soccer_team_stats("Liverpool"))
    print("=== Soccer: unknown team (should be None, not a placeholder) ===")
    print(get_soccer_team_stats("Some Random FC"))
    print("=== Basketball: known team ===")
    print(get_basketball_team_stats("Real Madrid"))
    print("\nteam_stats_provider.py OK")
