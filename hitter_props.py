#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
hitter_props.py - Real per-player hitter projections, MLB Stats API

WHY THIS EXISTS
    The configured path for hitter props (ingest_mlb_props.py -> pybaseball
    -> FanGraphs) is dead on this machine: FanGraphs returns HTTP 403, the
    same Cloudflare block that already killed FBref for soccer. The old
    "Home runs (H/A)" row in the embed was TEAM-level anyway, not a player
    prop, and you found hardcoded constants standing in for shots/tempo
    elsewhere in this project today -- this file does not add another one.
    Every number here is either a real per-player season stat from
    statsapi.mlb.com (same host this project already trusts for schedules)
    or a probability derived from one. Nothing is invented.

LINEUPS ARE TIME-OF-DAY GATED, NOT A DATA GAP
    MLB does not post a confirmed starting lineup until roughly 2-4 hours
    before first pitch -- checked today's slate directly: every game is
    hours away, and the boxscore endpoint's batters list is empty for all
    of them right now. That is expected, not broken. get_lineup() returns
    an explicit "not_posted_yet" status rather than guessing who's likely
    to start; there is no "usual lineup" fallback here, on purpose -- a
    guessed lineup dressed up as a real one is exactly the failure mode
    this whole project has been fighting today.

THE PROJECTION, AND WHAT IT ASSUMES
    Each batter's real season rates (hits/PA, HR/PA) are converted to a
    per-game probability via a fixed expected-plate-appearances assumption
    (4.3, the rough average for a full 9-inning game). This does NOT vary
    by batting order slot (a leadoff hitter really does see more PA than a
    #9 hitter) or by the opposing starter -- both are real, known
    simplifications, not hidden ones. Treat this as a first-pass model,
    same as everything else in this project tagged data_tier 2: directionally
    real, not finely calibrated. Grade it before leaning on it.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None

STATS_BASE = "https://statsapi.mlb.com/api/v1"
UA = "Mozilla/5.0 (MultiSportPredict hitter props)"
EXPECTED_PA_PER_GAME = 4.3  # league-average plate appearances in a 9-inning game


def _get(url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    if requests is None:
        return None
    try:
        resp = requests.get(url, params=params or {}, headers={"User-Agent": UA}, timeout=20)
    except Exception:  # noqa: BLE001
        return None
    if resp.status_code != 200:
        return None
    try:
        return resp.json()
    except ValueError:
        return None


def find_game_pk(home_team: str, away_team: str, date: Optional[str] = None) -> Optional[int]:
    """Today's (or a given date's) real MLB gamePk for this matchup, or None."""
    date = date or _dt.date.today().isoformat()
    payload = _get(f"{STATS_BASE}/schedule", {"sportId": 1, "date": date})
    if not payload:
        return None

    def squash(name: str) -> str:
        return "".join(ch for ch in (name or "").lower() if ch.isalnum())

    home_s, away_s = squash(home_team), squash(away_team)
    for day in payload.get("dates", []):
        for game in day.get("games", []):
            gh = squash(game.get("teams", {}).get("home", {}).get("team", {}).get("name", ""))
            ga = squash(game.get("teams", {}).get("away", {}).get("team", {}).get("name", ""))
            if (home_s in gh or gh in home_s) and (away_s in ga or ga in away_s):
                return game.get("gamePk")
    return None


def get_lineup(game_pk: int) -> Dict[str, Any]:
    """Confirmed starting batters for a real game, or an explicit not-yet state.

    Never falls back to a guessed/typical lineup -- see module docstring.
    """
    box = _get(f"{STATS_BASE}/game/{game_pk}/boxscore")
    if box is None:
        return {"status": "error", "home": [], "away": []}
    home_batters = box.get("teams", {}).get("home", {}).get("batters", []) or []
    away_batters = box.get("teams", {}).get("away", {}).get("batters", []) or []
    if not home_batters and not away_batters:
        return {"status": "not_posted_yet", "home": [], "away": [],
                "reason": "MLB has not posted a confirmed lineup for this game yet "
                         "(typically 2-4 hours before first pitch)"}
    home_players = box.get("teams", {}).get("home", {}).get("players", {})
    away_players = box.get("teams", {}).get("away", {}).get("players", {})

    def names(ids: List[int], players: Dict[str, Any]) -> List[Dict[str, Any]]:
        out = []
        for pid in ids:
            p = players.get(f"ID{pid}", {})
            person = p.get("person", {})
            if person.get("fullName"):
                out.append({"id": pid, "name": person["fullName"],
                           "position": p.get("position", {}).get("abbreviation")})
        return out

    return {"status": "posted", "home": names(home_batters, home_players),
           "away": names(away_batters, away_players)}


def get_batter_season_stats(player_id: int, season: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Real season hitting stats for one real player, or None if unavailable."""
    season = season or _dt.date.today().year
    payload = _get(f"{STATS_BASE}/people/{player_id}/stats",
                   {"stats": "season", "season": season, "group": "hitting"})
    if not payload:
        return None
    try:
        stat = payload["stats"][0]["splits"][0]["stat"]
    except (KeyError, IndexError, TypeError):
        return None
    pa = stat.get("plateAppearances")
    if not pa:
        return None
    return {
        "games": stat.get("gamesPlayed"), "pa": pa, "ab": stat.get("atBats"),
        "hits": stat.get("hits"), "home_runs": stat.get("homeRuns"),
        "avg": stat.get("avg"), "obp": stat.get("obp"), "slg": stat.get("slg"),
    }


def project_batter(player_id: int, player_name: str, season: Optional[int] = None) -> Dict[str, Any]:
    """P(>=1 hit) and P(>=1 HR) for one real batter, from real season rates.

    Returns an explicit "insufficient_sample" state rather than a number
    when the season is too thin to mean anything -- same MIN_MATCHES-style
    floor this project already applies to soccer/tennis, just for PA.
    """
    stats = get_batter_season_stats(player_id, season)
    if stats is None:
        return {"player": player_name, "status": "no_stats"}
    pa = stats["pa"]
    if pa < 30:  # same spirit as the soccer/tennis "need N before it means anything" floors
        return {"player": player_name, "status": "insufficient_sample",
                "pa": pa, "reason": f"only {pa} plate appearances this season -- too thin to project"}

    hit_rate = stats["hits"] / pa
    hr_rate = stats["home_runs"] / pa
    p_hit = 1.0 - (1.0 - hit_rate) ** EXPECTED_PA_PER_GAME
    p_hr = 1.0 - (1.0 - hr_rate) ** EXPECTED_PA_PER_GAME

    return {
        "player": player_name, "status": "ok", "pa_season": pa,
        "hit_prob": round(p_hit, 3), "hr_prob": round(p_hr, 3),
        "season_avg": stats["avg"], "season_hr": stats["home_runs"],
        "data_tier": 2,
        "note": (f"derived from {pa} real season PA, {EXPECTED_PA_PER_GAME} expected "
                f"PA/game assumed -- not calibrated by batting order slot"),
    }


def get_game_hitter_props(home_team: str, away_team: str, date: Optional[str] = None) -> Dict[str, Any]:
    """The one function callers should use: real lineup -> real per-player projections.

    Never invents a lineup or a player's rate. Every non-"ok" status
    explains exactly why there's nothing to show, the same way live_odds.py
    does for market prices.
    """
    game_pk = find_game_pk(home_team, away_team, date)
    if game_pk is None:
        return {"status": "no_game_found", "home": [], "away": [],
                "reason": f"no real MLB game found for {home_team!r} vs {away_team!r} on "
                         f"{date or _dt.date.today().isoformat()}"}
    lineup = get_lineup(game_pk)
    if lineup["status"] != "posted":
        return {"status": lineup["status"], "home": [], "away": [],
                "reason": lineup.get("reason", "lineup unavailable"), "game_pk": game_pk}

    def project_side(batters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [project_batter(b["id"], b["name"]) for b in batters]

    return {"status": "ok", "game_pk": game_pk,
           "home": project_side(lineup["home"]), "away": project_side(lineup["away"])}
