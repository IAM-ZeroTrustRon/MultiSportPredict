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
    "mexico":    {"page": "mexico.php",      "league": "Liga MX"},
    "argentina": {"page": "argentina.php",   "league": "Liga Profesional"},
    "brazil":    {"page": "brazil.php",      "league": "Serie A (BRA)"},
    "usa":       {"page": "usa.php",         "league": "MLS"},
    "england":   {"page": "englandm.php",    "league": "Premier League"},
    "spain":     {"page": "spainm.php",      "league": "La Liga"},
    "germany":   {"page": "germanym.php",    "league": "Bundesliga"},
    "italy":     {"page": "italym.php",      "league": "Serie A"},
    "france":    {"page": "francem.php",     "league": "Ligue 1"},
    "netherlands": {"page": "netherlandsm.php", "league": "Eredivisie"},
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


def choose_csv(links: List[str], country: str) -> List[str]:
    """Prefer the consolidated 'new/' file, else the most recent season file."""
    new_format = [u for u in links if "/new/" in u.lower()]
    if new_format:
        debug(f"using new-format file(s): {new_format}")
        return new_format[:1]
    # Classic layout: /mmz4281/2526/E0.csv -- the season folder is 4 digits.
    seasonal = sorted(
        (u for u in links if re.search(r"/\d{4}/", u)),
        key=lambda u: re.search(r"/(\d{4})/", u).group(1),
        reverse=True,
    )
    debug(f"using seasonal file(s): {seasonal[:2]}")
    return seasonal[:2]


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


def aggregate(rows: List[Dict[str, Any]], league_name: str,
              season: Optional[str]) -> Dict[str, Dict[str, Any]]:
    """Per-team per-game goals, with home/away splits and last-5 form."""
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

    records: Dict[str, Dict[str, Any]] = {}
    for team, bucket in totals.items():
        games = bucket["games"]
        if games < 1:
            continue
        goals_for = round(bucket["gf"] / games, 3)
        goals_against = round(bucket["ga"] / games, 3)
        record: Dict[str, Any] = {
            "league": league_name,
            "season": season or "",
            "games": int(games),
            "goals_for": goals_for,
            "goals_against": goals_against,
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
        raise RuntimeError(f"Could not pick a CSV from: {links[:5]}")

    rows: List[Dict[str, Any]] = []
    for index, url in enumerate(chosen):
        log(f"    downloading {url}")
        text = fetch(url, save_as=f"fd_{key}_{index}.csv")
        rows.extend(parse_matches(text, config.get("league_code")))

    if not rows:
        raise RuntimeError(
            f"No usable match rows parsed. Saved to data/cache/probe/fd_{key}_0.csv"
        )

    season = latest_season(rows)
    if season:
        rows = [r for r in rows if r["season"] == season]
        log(f"    season {season}: {len(rows)} match(es)")
    else:
        log(f"    {len(rows)} match(es) (no season column)")

    records = aggregate(rows, league_name, season)
    log(f"    {len(records)} team(s)")
    for team in list(records)[:5]:
        row = records[team]
        home = row.get("home_goals_for", "-")
        away = row.get("away_goals_for", "-")
        log(f"      {team:<26} GF/g {row['goals_for']:<6} GA/g {row['goals_against']:<6} "
            f"(home {home} / away {away})")

    if check:
        log("    (check mode -- nothing written)")
    else:
        merge_store(records, OUTPUT)
        log(f"    merged into {OUTPUT.relative_to(ROOT)}")
    return len(records)


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
