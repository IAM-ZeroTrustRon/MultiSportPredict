#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ingest_soccer_fd.py - Soccer team metrics from football-data.co.uk

WHY THIS SOURCE
    Three soccer sources have now been ruled out on this machine:
      FBref  -> HTTP 403 (Cloudflare)
      ESPN   -> HTTP 403 (Akamai "Access Denied")
    football-data.co.uk answered 200 in the probe. It publishes match-level
    results as plain CSV, which is better than a standings table: real fixtures
    mean home/away splits and recent form can be computed rather than guessed.

    Liga MX is covered at https://www.football-data.co.uk/mexico.php

HOW IT FINDS FILES
    It does NOT hardcode a CSV path. It loads the country page and reads the
    .csv links off it, because guessing URLs has failed twice already. Every
    response is saved to data/cache/probe/ so a parsing problem can be fixed
    against the real bytes.

WHAT YOU GET, AND WHAT YOU DON'T
    Goals, games, home/away splits, and last-5 form -- all real, from actual
    results. NO expected goals: this source publishes none. xG here is derived
    from goals and tagged data_tier 2, the same convention the Eerste Divisie
    already uses. Do not read it as real xG.

USAGE
    python ingest_soccer_fd.py --countries mexico
    python ingest_soccer_fd.py --countries mexico england spain --check
    python ingest_soccer_fd.py --list
    python ingest_soccer_fd.py --countries mexico --debug
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import io
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUTPUT = DATA / "soccer_stats.json"
PROBE = DATA / "cache" / "probe"

BASE = "https://www.football-data.co.uk/"
TIMEOUT = 40
TODAY = _dt.date.today()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

try:
    import requests
except ImportError:
    sys.exit("requests is required:  pip install requests")

# country key -> (index page, league label to keep, division codes if the CSV
# carries several). "new"-format files hold every league for a country in one
# CSV with Country/League columns; the classic files are one league per file.
COUNTRIES: Dict[str, Dict[str, Any]] = {
    # "new"-format countries: one CSV holding every league, with Country/League
    # columns and a Season column.
    "mexico":    {"page": "mexico.php",    "league": "Liga MX"},
    "argentina": {"page": "argentina.php", "league": "Liga Profesional"},
    "brazil":    {"page": "brazil.php",    "league": "Serie A (BRA)"},
    "usa":       {"page": "usa.php",       "league": "MLS"},

    # Classic-format countries: one CSV per division per season, named by a
    # division code. The code decides the league -- E0 and E1 are different
    # competitions and must not be merged into one bucket.
    "england":     {"page": "englandm.php", "league": "Premier League",
                    "divisions": {"E0": "Premier League", "E1": "Championship"}},
    "netherlands": {"page": "netherlandsm.php", "league": "Eredivisie",
                    "divisions": {"N1": "Eredivisie"}},
    "spain":     {"page": "spainm.php",   "league": "La Liga",
                  "divisions": {"SP1": "La Liga", "SP2": "Segunda Division"}},
    "germany":   {"page": "germanym.php", "league": "Bundesliga",
                  "divisions": {"D1": "Bundesliga", "D2": "2. Bundesliga"}},
    "italy":     {"page": "italym.php",   "league": "Serie A",
                  "divisions": {"I1": "Serie A", "I2": "Serie B"}},
    "france":    {"page": "francem.php",  "league": "Ligue 1",
                  "divisions": {"F1": "Ligue 1", "F2": "Ligue 2"}},
}

DEBUG = False


def log(message: str = "") -> None:
    print(message, flush=True)


def debug(message: str) -> None:
    if DEBUG:
        log(f"    [debug] {message}")


def fetch(url: str, save_as: Optional[str] = None) -> str:
    response = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
    if save_as:
        PROBE.mkdir(parents=True, exist_ok=True)
        (PROBE / save_as).write_text(response.text, encoding="utf-8", errors="replace")
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code} from {url}")
    return response.text


def to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if text in {"", "-", "NA", "N/A"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


# ==========================================================================
# DISCOVERY
# ==========================================================================

CSV_LINK = re.compile(r'href\s*=\s*["\']([^"\']+\.csv)["\']', re.IGNORECASE)


def find_csv_links(html: str, page_url: str) -> List[str]:
    links = []
    for href in CSV_LINK.findall(html):
        absolute = urljoin(page_url, href)
        if absolute not in links:
            links.append(absolute)
    return links


def season_start_year(code: str) -> int:
    """'2627' -> 2026, '9900' -> 1999.

    These four-digit folder names are two 2-digit years glued together, so
    sorting them as strings puts the 1990s at the top: '9900' > '2627'. That is
    exactly how a run meant to fetch 2026/27 quietly returned the 1999/2000
    season instead -- with Wimbledon and Bradford in the Premier League.
    """
    two = int(code[:2])
    return (1900 + two) if two >= 90 else (2000 + two)


def choose_csv(links: List[str], country: str) -> List[Tuple[str, Optional[str]]]:
    """Return [(url, division_code)] for the most recent season available."""
    new_format = [u for u in links if "/new/" in u.lower()]
    if new_format:
        debug(f"new-format file: {new_format[0]}")
        return [(new_format[0], None)]

    config = COUNTRIES[country]
    divisions = config.get("divisions") or {}

    seasoned: List[Tuple[int, str, str]] = []
    for url in links:
        match = re.search(r"/(\d{4})/([A-Za-z0-9]+)\.csv$", url)
        if not match:
            continue
        code, division = match.group(1), match.group(2).upper()
        if divisions and division not in divisions:
            continue
        seasoned.append((season_start_year(code), division, url))

    if not seasoned:
        return []

    latest = max(year for year, _, _ in seasoned)
    chosen = [(url, division) for year, division, url in seasoned if year == latest]
    log(f"    latest season on the page: {latest}/{str(latest + 1)[2:]}")
    for url, division in chosen:
        log(f"      {division} -> {divisions.get(division, division)}")
    return chosen


# ==========================================================================
# PARSING
# ==========================================================================

def parse_matches(text: str, league_filter: Optional[str]) -> List[Dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    rows: List[Dict[str, Any]] = []
    for row in reader:
        home = (row.get("Home") or row.get("HomeTeam") or "").strip()
        away = (row.get("Away") or row.get("AwayTeam") or "").strip()
        home_goals = to_float(row.get("HG") if row.get("HG") is not None else row.get("FTHG"))
        away_goals = to_float(row.get("AG") if row.get("AG") is not None else row.get("FTAG"))
        if not home or not away or home_goals is None or away_goals is None:
            continue
        rows.append({
            "home": home, "away": away,
            "home_goals": home_goals, "away_goals": away_goals,
            "season": (row.get("Season") or "").strip(),
            "league": (row.get("League") or "").strip(),
            "date": (row.get("Date") or "").strip(),
        })
    if league_filter:
        matching = [r for r in rows if r["league"] and
                    league_filter.lower() in r["league"].lower()]
        if matching:
            rows = matching
    return rows


def latest_season(rows: List[Dict[str, Any]]) -> Optional[str]:
    seasons = sorted({r["season"] for r in rows if r["season"]})
    return seasons[-1] if seasons else None


# Games needed before a team's own rate is trusted on its own. Below this the
# rate is blended toward the league average -- one 3-0 win must not make a club
# a 3.0 goals-per-game side.
REGRESSION_K = 6


def aggregate(rows: List[Dict[str, Any]], league_name: str,
              season: Optional[str]) -> Dict[str, Dict[str, Any]]:
    """Per-team per-game goals, with home/away splits and last-5 form.

    Small samples are regressed toward the league average. Two games into a
    season a club that has scored twice is not a 1.0-goals-per-game team, it is
    a team we know almost nothing about. Reporting the raw rate produced 5-6
    goal projections and edges above 50%, which are not opinions, they are
    arithmetic on noise.
    """
    totals: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    recent: Dict[str, List[float]] = defaultdict(list)

    for row in rows:
        for team, scored, conceded, venue in (
            (row["home"], row["home_goals"], row["away_goals"], "home"),
            (row["away"], row["away_goals"], row["home_goals"], "away"),
        ):
            bucket = totals[team]
            bucket["games"] += 1
            bucket["gf"] += scored
            bucket["ga"] += conceded
            bucket[f"{venue}_games"] += 1
            bucket[f"{venue}_gf"] += scored
            bucket[f"{venue}_ga"] += conceded
            if scored > conceded:
                bucket["wins"] += 1
                recent[team].append(3.0)
            elif scored == conceded:
                bucket["draws"] += 1
                recent[team].append(1.0)
            else:
                bucket["losses"] += 1
                recent[team].append(0.0)

    # League average goals per team per game, from every match in the sample.
    league_games = sum(b["games"] for b in totals.values())
    league_goals = sum(b["gf"] for b in totals.values())
    league_avg = (league_goals / league_games) if league_games else 1.35

    records: Dict[str, Dict[str, Any]] = {}
    for team, bucket in totals.items():
        games = bucket["games"]
        if games < 1:
            continue
        raw_for = bucket["gf"] / games
        raw_against = bucket["ga"] / games

        weight = games / (games + REGRESSION_K)
        goals_for = round(weight * raw_for + (1 - weight) * league_avg, 3)
        goals_against = round(weight * raw_against + (1 - weight) * league_avg, 3)
        record: Dict[str, Any] = {
            "league": league_name,
            "season": season or "",
            "games": int(games),
            "goals_for": goals_for,
            "goals_against": goals_against,
            "goals_for_raw": round(raw_for, 3),
            "goals_against_raw": round(raw_against, 3),
            "regression_weight": round(weight, 3),
            "league_avg_goals": round(league_avg, 3),
            # No xG in this feed. Goals stand in, tagged so nothing downstream
            # treats it as a real expected-goals figure.
            "xg_for": goals_for,
            "xg_against": goals_against,
            "data_tier": 2,
            "wins": int(bucket["wins"]),
            "draws": int(bucket["draws"]),
            "losses": int(bucket["losses"]),
            "source": "football-data.co.uk (xG estimated from goals -- no xG in this feed)",
            "updated": TODAY.isoformat(),
        }
        for venue in ("home", "away"):
            venue_games = bucket[f"{venue}_games"]
            if venue_games:
                record[f"{venue}_goals_for"] = round(bucket[f"{venue}_gf"] / venue_games, 3)
                record[f"{venue}_goals_against"] = round(bucket[f"{venue}_ga"] / venue_games, 3)
                record[f"{venue}_games"] = int(venue_games)
        form = recent[team][-5:]
        if form:
            record["form_last5_ppg"] = round(sum(form) / len(form), 3)
        records[team] = record
    return records


# ==========================================================================
# STORE
# ==========================================================================

def merge_store(records: Dict[str, Dict[str, Any]], path: Path) -> None:
    existing: Dict[str, Any] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            backup = path.with_suffix(".corrupt.json")
            path.replace(backup)
            log(f"    [warn] {path.name} was not valid JSON; moved to {backup.name}")
    existing.update(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    os.replace(temporary, path)


# ==========================================================================
# PER-COUNTRY
# ==========================================================================

def ingest_country(key: str, check: bool) -> int:
    config = COUNTRIES[key]
    page_url = urljoin(BASE, config["page"])
    league_name = config["league"]
    log(f"\n[{league_name}]  {page_url}")

    html = fetch(page_url, save_as=f"fd_{key}.html")
    links = find_csv_links(html, page_url)
    log(f"    {len(links)} csv link(s) on the page")
    if not links:
        raise RuntimeError(
            f"No .csv links found on {page_url}. The page was saved to "
            f"data/cache/probe/fd_{key}.html -- the real markup is in there."
        )

    chosen = choose_csv(links, key)
    if not chosen:
        raise RuntimeError(
            f"No usable CSV found for {key}. Page saved to "
            f"data/cache/probe/fd_{key}.html")

    divisions = config.get("divisions") or {}
    total_teams = 0
    folder_season = ""
    for index, (url, division) in enumerate(chosen):
        this_league = divisions.get(division, league_name) if division else league_name
        folder_match = re.search(r"/(\d{4})/", url)
        if folder_match:
            start = season_start_year(folder_match.group(1))
            folder_season = f"{start}/{start + 1}"
        log(f"    downloading {url}")
        text = fetch(url, save_as=f"fd_{key}_{division or index}.csv")
        rows = parse_matches(text, None)
        if not rows:
            log(f"    [warn] no usable rows in {url}")
            continue

        season = latest_season(rows)
        if season:
            rows = [r for r in rows if r["season"] == season]
            log(f"    {this_league}: season {season}, {len(rows)} match(es)")
        else:
            # Classic per-division files carry no Season column. Take it from
            # the folder code instead -- an unlabelled record cannot be age
            # checked, which is exactly how 1999 data went unnoticed.
            season = folder_season
            log(f"    {this_league}: season {season} (from folder), "
                f"{len(rows)} match(es)")

        division_records = aggregate(rows, this_league, season)
        log(f"    {this_league}: {len(division_records)} team(s)")
        for team in list(division_records)[:4]:
            row = division_records[team]
            log(f"      {team:<24} GF/g {row['goals_for']:<6} GA/g {row['goals_against']}")

        if check:
            log("    (check mode -- nothing written)")
        else:
            merge_store(division_records, OUTPUT)
        total_teams += len(division_records)

    if not total_teams:
        raise RuntimeError(f"{key}: downloaded but produced no teams")
    if not check:
        log(f"    merged into {OUTPUT.relative_to(ROOT)}")
    return total_teams


def main() -> None:
    global DEBUG
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--countries", nargs="+", default=["mexico"])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--check", action="store_true", help="Fetch and report, write nothing.")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    DEBUG = args.debug

    if args.list:
        log("Available countries:\n")
        for key, config in COUNTRIES.items():
            log(f"  {key:<14} {config['page']:<20} {config['league']}")
        return

    selected = list(COUNTRIES) if args.all else args.countries
    unknown = [k for k in selected if k not in COUNTRIES]
    if unknown:
        parser.error(f"Unknown: {', '.join(unknown)}. Try --list")

    log("=" * 74)
    log(f"football-data.co.uk ingestion  -  {TODAY}"
        + ("  (CHECK, nothing written)" if args.check else ""))
    log("=" * 74)

    total = 0
    failures: List[str] = []
    for key in selected:
        try:
            total += ingest_country(key, args.check)
        except Exception as exc:  # noqa: BLE001
            log(f"    [FAILED] {type(exc).__name__}: {exc}")
            failures.append(key)

    log("\n" + "=" * 74)
    log(f"{total} team(s) across {len(selected) - len(failures)}/{len(selected)} country(ies)")
    if failures:
        log(f"Failed: {', '.join(failures)}")
    if total and not args.check:
        log(f"\nWritten to {OUTPUT.relative_to(ROOT)}.")
        log("Reminder: xG in these rows is ESTIMATED FROM GOALS (Tier 2).")
    log("=" * 74)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
