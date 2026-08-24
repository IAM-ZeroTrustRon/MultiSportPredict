#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
auto_mlb_scraper.py — Daily MLB Automation Engine
==================================================
Fetches today's MLB schedule + probable starters from the official, free
MLB Stats API (no API key required), computes live SP metrics, and fires
universal_runner.py for every game with confirmed starters.

Usage:
    python auto_mlb_scraper.py
    python auto_mlb_scraper.py --date 2026-06-19
    python auto_mlb_scraper.py --dry-run          # print commands without executing
    python auto_mlb_scraper.py --market-total 9.0 # override default O/U total

MLB Stats API (free, official):
    Schedule:  https://statsapi.mlb.com/api/v1/schedule
    People:    https://statsapi.mlb.com/api/v1/people/{id}
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    print("[ERROR] 'requests' library not installed. Run: pip install requests")
    sys.exit(1)

# ---------------------------------------------------------------------------
# MLB STATS API CONSTANTS
# ---------------------------------------------------------------------------
MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
MLB_PEOPLE_URL   = "https://statsapi.mlb.com/api/v1/people/{pitcher_id}"

# MLB franchise abbreviation map (Stats API teamName → 3-letter abbr used by our engine)
# Covers all 30 franchises + common aliases
MLB_ABBR_MAP: Dict[str, str] = {
    # AL East
    "New York Yankees":     "NYY",
    "Boston Red Sox":       "BOS",
    "Tampa Bay Rays":       "TB",
    "Baltimore Orioles":    "BAL",
    "Toronto Blue Jays":    "TOR",
    # AL Central
    "Chicago White Sox":    "CWS",
    "Cleveland Guardians":  "CLE",
    "Detroit Tigers":       "DET",
    "Kansas City Royals":   "KC",
    "Minnesota Twins":      "MIN",
    # AL West
    "Houston Astros":       "HOU",
    "Los Angeles Angels":   "LAA",
    "Oakland Athletics":    "OAK",
    "Seattle Mariners":     "SEA",
    "Texas Rangers":        "TEX",
    # NL East
    "Atlanta Braves":       "ATL",
    "Miami Marlins":        "MIA",
    "New York Mets":        "NYM",
    "Philadelphia Phillies":"PHI",
    "Washington Nationals": "WSH",
    # NL Central
    "Chicago Cubs":         "CHC",
    "Cincinnati Reds":      "CIN",
    "Milwaukee Brewers":    "MIL",
    "Pittsburgh Pirates":   "PIT",
    "St. Louis Cardinals":  "STL",
    # NL West
    "Arizona Diamondbacks": "ARI",
    "Colorado Rockies":     "COL",
    "Los Angeles Dodgers":  "LAD",
    "San Diego Padres":     "SD",
    "San Francisco Giants": "SF",
    # Athletics relocation alias
    "Athletics":            "OAK",
}

# Default fallback pitcher stats when the season stat hydration returns empty
DEFAULT_ERA  = 4.50
DEFAULT_K9   = 8.0
DEFAULT_IP   = 30.0
DEFAULT_SO   = 27


# ---------------------------------------------------------------------------
# DATA CLASSES (plain dicts for simplicity)
# ---------------------------------------------------------------------------

def _safe_float(val: Any, default: float) -> float:
    """Safely cast a value to float, returning default on failure."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# MLB STATS API: SCHEDULE
# ---------------------------------------------------------------------------

def fetch_today_schedule(game_date: Optional[str] = None) -> List[Dict]:
    """
    Hit the official MLB Stats API schedule endpoint.

    Returns a list of game dicts, each containing:
        gamePk, officialDate, teams.home, teams.away,
        teams.home.probablePitcher, teams.away.probablePitcher
    """
    target_date = game_date or date.today().isoformat()   # e.g. "2026-06-19"

    params = {
        "sportId": 1,
        "date":    target_date,
        "hydrate": "probablePitcher",
    }

    print(f"[MLB API] Fetching schedule for {target_date} ...")
    try:
        resp = requests.get(MLB_SCHEDULE_URL, params=params, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"[ERROR] Schedule fetch failed: {exc}")
        return []

    data = resp.json()
    games: List[Dict] = []

    for date_block in data.get("dates", []):
        for game in date_block.get("games", []):
            games.append(game)

    print(f"[MLB API] Found {len(games)} game(s) on {target_date}.")
    return games


# ---------------------------------------------------------------------------
# MLB STATS API: PITCHER SEASON STATS
# ---------------------------------------------------------------------------

def fetch_pitcher_stats(pitcher_id: int) -> Dict[str, Any]:
    """
    Fetch a pitcher's current-season stats via the MLB Stats API people endpoint.

    Returns dict with keys: era, k9, k_proj_5_5, ip, so, full_name
    """
    url = MLB_PEOPLE_URL.format(pitcher_id=pitcher_id)
    params = {"hydrate": "stats(group=[pitching],type=[season])"}

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        print(f"  [WARN] Pitcher {pitcher_id} stats fetch failed: {exc}")
        return _default_pitcher_stats(pitcher_id)

    people = data.get("people", [])
    if not people:
        return _default_pitcher_stats(pitcher_id)

    person = people[0]
    full_name = person.get("fullName", f"Pitcher#{pitcher_id}")

    # Navigate to pitching season stats
    era  = DEFAULT_ERA
    ip   = DEFAULT_IP
    so   = DEFAULT_SO

    for stat_group in person.get("stats", []):
        if stat_group.get("group", {}).get("displayName", "").lower() != "pitching":
            continue
        splits = stat_group.get("splits", [])
        if not splits:
            continue
        season_stat = splits[0].get("stat", {})
        era = _safe_float(season_stat.get("era",  DEFAULT_ERA),  DEFAULT_ERA)
        ip  = _safe_float(season_stat.get("inningsPitched", DEFAULT_IP), DEFAULT_IP)
        so  = _safe_float(season_stat.get("strikeOuts",     DEFAULT_SO), DEFAULT_SO)
        break

    # Derived metrics
    k9     = (so / max(ip, 0.1)) * 9.0          # strikeouts per 9 innings
    k_proj = k9 / 9.0 * 5.5                      # expected Ks in 5.5 innings

    return {
        "pitcher_id": pitcher_id,
        "full_name":  full_name,
        "era":        round(era,    2),
        "ip":         round(ip,     1),
        "so":         int(so),
        "k9":         round(k9,     2),
        "k_proj_5_5": round(k_proj, 2),
    }


def _default_pitcher_stats(pitcher_id: int) -> Dict[str, Any]:
    """Return league-average fallback when stat fetch fails."""
    k_proj = DEFAULT_K9 / 9.0 * 5.5
    return {
        "pitcher_id": pitcher_id,
        "full_name":  f"Pitcher#{pitcher_id}",
        "era":        DEFAULT_ERA,
        "ip":         DEFAULT_IP,
        "so":         DEFAULT_SO,
        "k9":         DEFAULT_K9,
        "k_proj_5_5": round(k_proj, 2),
    }


# ---------------------------------------------------------------------------
# TEAM NAME → ABBREVIATION RESOLVER
# ---------------------------------------------------------------------------

def resolve_abbr(team_name: str) -> str:
    """Convert full franchise name to 3-letter abbreviation used by our engine."""
    # Direct lookup
    if team_name in MLB_ABBR_MAP:
        return MLB_ABBR_MAP[team_name]
    # Partial match fallback (e.g., "Yankees" → "NYY")
    for full_name, abbr in MLB_ABBR_MAP.items():
        if team_name.lower() in full_name.lower() or full_name.lower() in team_name.lower():
            return abbr
    # Final fallback: use first 3 chars uppercased
    return team_name[:3].upper()


# ---------------------------------------------------------------------------
# GAME PROCESSING PIPELINE
# ---------------------------------------------------------------------------

def process_game(game: Dict, market_total: float, dry_run: bool) -> Optional[Dict]:
    """
    Parse a single game dict from the MLB Stats API schedule.

    Returns None if the game should be skipped (no confirmed starters).
    """
    game_pk  = game.get("gamePk", "?")
    teams    = game.get("teams", {})
    home_d   = teams.get("home", {})
    away_d   = teams.get("away", {})

    home_name = home_d.get("team", {}).get("name", "HOME")
    away_name = away_d.get("team", {}).get("name", "AWAY")
    home_abbr = resolve_abbr(home_name)
    away_abbr = resolve_abbr(away_name)

    home_sp_raw = home_d.get("probablePitcher")
    away_sp_raw = away_d.get("probablePitcher")

    # Skip games where either starter hasn't been announced
    if not home_sp_raw or not away_sp_raw:
        print(f"[SKIP] {away_abbr} @ {home_abbr} (gamePk={game_pk}) - starter(s) not yet announced.")
        return None

    home_sp_id = home_sp_raw.get("id")
    away_sp_id = away_sp_raw.get("id")
    home_sp_name = home_sp_raw.get("fullName", f"ID#{home_sp_id}")
    away_sp_name = away_sp_raw.get("fullName", f"ID#{away_sp_id}")

    print(f"\n{'-' * 60}")
    print(f"  GAME  : {away_abbr} ({away_name}) @ {home_abbr} ({home_name})")
    print(f"  HOME SP: {home_sp_name} (ID: {home_sp_id})")
    print(f"  AWAY SP: {away_sp_name} (ID: {away_sp_id})")

    # Fetch live season stats for each pitcher
    print(f"  [MLB API] Fetching stats for {home_sp_name} ...")
    home_stats = fetch_pitcher_stats(home_sp_id)

    print(f"  [MLB API] Fetching stats for {away_sp_name} ...")
    away_stats = fetch_pitcher_stats(away_sp_id)

    # Print SP stat card
    print(f"\n  +-- SP Stat Card -----------------------------------------------+")
    print(f"  |  {home_sp_name:<26} |  ERA: {home_stats['era']:.2f} | K/9: {home_stats['k9']:.1f} | K-Proj(5.5): {home_stats['k_proj_5_5']:.1f}")
    print(f"  |  {away_sp_name:<26} |  ERA: {away_stats['era']:.2f} | K/9: {away_stats['k9']:.1f} | K-Proj(5.5): {away_stats['k_proj_5_5']:.1f}")
    print(f"  +---------------------------------------------------------------+")

    return {
        "game_pk":       game_pk,
        "home_abbr":     home_abbr,
        "away_abbr":     away_abbr,
        "home_sp_name":  home_sp_name,
        "away_sp_name":  away_sp_name,
        "home_era":      home_stats["era"],
        "home_k_proj":   home_stats["k_proj_5_5"],
        "away_era":      away_stats["era"],
        "away_k_proj":   away_stats["k_proj_5_5"],
        "market_total":  market_total,
    }


# ---------------------------------------------------------------------------
# SUBPROCESS: FIRE universal_runner.py
# ---------------------------------------------------------------------------

def fire_universal_runner(game_info: Dict, dry_run: bool) -> int:
    """
    Build and execute the universal_runner.py command for a single game.

    Returns the subprocess return code (0 = success).
    """
    cmd = [
        sys.executable,                   # e.g. python.exe
        "universal_runner.py",
        "--sport",         "baseball",
        "--home",          game_info["home_abbr"],
        "--away",          game_info["away_abbr"],
        "--markets",       "nrfi", "strikeouts",
        "--market-total",  str(game_info["market_total"]),
        "--home-sp-era",   str(game_info["home_era"]),
        "--home-sp-k",     str(game_info["home_k_proj"]),
        "--away-sp-era",   str(game_info["away_era"]),
        "--away-sp-k",     str(game_info["away_k_proj"]),
        "--store-to-db",
        "--push-discord",
    ]

    print(f"\n  [CMD] {' '.join(cmd)}\n")

    if dry_run:
        print("  [DRY-RUN] Command NOT executed.")
        return 0

    result = subprocess.run(cmd, check=False)
    return result.returncode


# ---------------------------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Daily MLB automation: fetch schedule → compute SP metrics → run universal_runner.py"
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Game date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--market-total",
        type=float,
        default=8.5,
        help="Default O/U market total to use for all games (default: 8.5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing them",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Optional path to save all processed game data as JSON",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("  AUTO MLB SCRAPER - Daily Prop Engine")
    print(f"  Target Date : {args.date or date.today().isoformat()}")
    print(f"  Market Total: {args.market_total}")
    print(f"  Dry-Run     : {args.dry_run}")
    print("=" * 70)

    # Step 1: Fetch today's schedule
    games = fetch_today_schedule(args.date)
    if not games:
        print("\n[INFO] No games found for this date. Exiting.")
        return

    # Step 2: Process each game
    processed: List[Dict] = []
    skipped  : int = 0
    succeeded: int = 0
    failed   : int = 0

    for game in games:
        game_info = process_game(game, args.market_total, args.dry_run)
        if game_info is None:
            skipped += 1
            continue

        processed.append(game_info)

        # Step 3: Fire universal_runner.py per game
        rc = fire_universal_runner(game_info, args.dry_run)
        if rc == 0:
            succeeded += 1
        else:
            failed += 1
            print(f"  [WARN] universal_runner.py exited with code {rc} for game {game_info['game_pk']}")

    # Step 4: Summary
    print("\n" + "=" * 70)
    print(f"  RUN COMPLETE")
    print(f"  Games processed : {len(processed)}")
    print(f"  Skipped (no SP) : {skipped}")
    print(f"  Succeeded       : {succeeded}")
    print(f"  Failed          : {failed}")
    print("=" * 70)

    # Optional JSON dump of all processed game data
    if args.output_json and processed:
        import json
        from pathlib import Path
        out = Path(args.output_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(processed, indent=2))
        print(f"\n[INFO] Game data written to: {out}")


if __name__ == "__main__":
    main()
