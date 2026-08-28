#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ingest_all_sports.py - One daily scraper for every league in MultiSportPredict
==============================================================================

Runs one adapter per league, writes each result into the JSON/CSV store that
team_stats_provider.py (and the predictors behind it) already read, and never
lets one dead source kill the rest of the run.

    LEAGUE          SOURCE                                    -> STORE
    -----------------------------------------------------------------------
    MLB   (teams)   statsapi.mlb.com  (official MLB API)      data/baseball_stats.json
    MLB   (probables) statsapi.mlb.com                        data/mlb_probables.json
    MLB   (players) pybaseball (existing ingest_mlb.py)       data/mlb_stats.json
    KBO   (teams)   mykbostats.com team splits                data/baseball_stats.json
    EuroLeague      euroleague-api (live.euroleague.net)      data/euroleague_stats.json
    KBL             basketball.realgm.com league 63           data/basketball_stats.json
    NZ NBL          basketball.realgm.com league 75           data/basketball_stats.json
    ATP + Challenger  JeffSackmann/tennis_atp CSVs            data/tennis/atp_matches.csv
    Soccer          existing ingest_soccer.py                 data/soccer_stats.json

USAGE
    python ingest_all_sports.py                    # everything (this is what the daily job runs)
    python ingest_all_sports.py --check            # test every source, write nothing
    python ingest_all_sports.py --only kbo tennis  # just those adapters
    python ingest_all_sports.py --skip soccer      # everything except soccer
    python ingest_all_sports.py --list             # show adapter names

EXIT CODES
    0 = every selected adapter succeeded
    1 = at least one adapter failed (the rest still wrote their data)
    2 = every selected adapter failed

DESIGN RULES THIS FILE FOLLOWS (they match ARCHITECTURE.md):
  * Never invent a number. If a source omits a field, the field is omitted from
    the record -- it is not filled with a league average. Downstream code is
    expected to warn on a missing field, which is the whole point.
  * Every record carries "source" and "updated" so you can always tell where a
    number came from and how stale it is.
  * Stores are MERGED, never overwritten, and written atomically via a .tmp
    file + os.replace, so a crash mid-write cannot corrupt a store.
  * Keys beginning with "_" (like _league_baseline) are preserved on merge.

DATA-SOURCE NOTE: statsapi.mlb.com and the Sackmann CSVs are public feeds meant
to be read programmatically. mykbostats.com and basketball.realgm.com are
ordinary web pages, so this script requests them at human pace (one page every
few seconds, one request per page per day) and caches responses. Sackmann's
tennis data is CC BY-NC-SA 4.0: fine for your own analysis, and it requires
attribution and forbids commercial redistribution. koreabaseball.com is
deliberately NOT used here -- its robots.txt disallows automated access.
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
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

# --------------------------------------------------------------------------
# PATHS -- these are the files team_stats_provider.py already reads.
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

BASEBALL_STORE = DATA / "baseball_stats.json"        # MLB + KBO team metrics
MLB_PROBABLES_STORE = DATA / "mlb_probables.json"    # today's announced starters
BASKETBALL_STORE = DATA / "basketball_stats.json"    # KBL + NZNBL (provider reads this for those leagues)
EUROLEAGUE_STORE = DATA / "euroleague_stats.json"    # EuroLeague (provider reads this)
TENNIS_DIR = DATA / "tennis"
TENNIS_MATCHES_CSV = TENNIS_DIR / "atp_matches.csv"  # feed for models/tennis_elo.py
TENNIS_META = TENNIS_DIR / "atp_meta.json"
CACHE_DIR = DATA / "cache" / "ingest"
LOG_DIR = ROOT / "logs"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
POLITE_DELAY_SECONDS = 3.0   # between requests to the same scraped host
HTTP_TIMEOUT = 30
TODAY = _dt.date.today().isoformat()

_last_request_at: Dict[str, float] = {}

# requests is already a project dependency. It is preferred over urllib because
# it sends a full browser-like header set and handles gzip/redirects, which is
# the difference between a 200 and a 403 on sites that screen simple clients.
try:
    import requests  # type: ignore
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "application/json,text/csv,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

DEBUG = False


def debug(message: str) -> None:
    if DEBUG:
        print(f"    [DEBUG] {message}", flush=True)


class FetchError(Exception):
    """One failed URL attempt, carrying the HTTP status when there was one."""

    def __init__(self, url: str, status: Optional[int] = None, reason: str = "") -> None:
        self.url = url
        self.status = status
        self.reason = reason
        label = f"HTTP {status}" if status else (reason or "request failed")
        super().__init__(f"{label}: {url}")


# ==========================================================================
# SMALL UTILITIES
# ==========================================================================

def log(message: str) -> None:
    print(message, flush=True)


def _host_of(url: str) -> str:
    match = re.match(r"https?://([^/]+)", url)
    return match.group(1) if match else url


def _raw_get(url: str, *, referer: Optional[str] = None, polite: bool = False) -> str:
    """One HTTP GET. Raises FetchError on any failure, with the status if known."""
    if polite:
        host = _host_of(url)
        elapsed = time.time() - _last_request_at.get(host, 0.0)
        if elapsed < POLITE_DELAY_SECONDS:
            time.sleep(POLITE_DELAY_SECONDS - elapsed)
        _last_request_at[host] = time.time()

    headers = dict(BROWSER_HEADERS)
    if referer:
        headers["Referer"] = referer
        headers["Sec-Fetch-Site"] = "same-origin"

    if _HAS_REQUESTS:
        try:
            response = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT)
        except Exception as exc:  # noqa: BLE001
            raise FetchError(url, reason=type(exc).__name__) from exc
        if response.status_code != 200:
            raise FetchError(url, status=response.status_code)
        response.encoding = response.encoding or "utf-8"
        return response.text

    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers=headers), timeout=HTTP_TIMEOUT
        ) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise FetchError(url, status=exc.code) from exc
    except Exception as exc:  # noqa: BLE001
        raise FetchError(url, reason=type(exc).__name__) from exc


def http_get(url: str, *, cache_key: Optional[str] = None, cache_hours: float = 12.0,
             polite: bool = False, referer: Optional[str] = None,
             alternates: Optional[Sequence[str]] = None) -> str:
    """GET a URL as text, with an on-disk cache, rate limiting, and mirrors.

    The cache means re-running during the day to debug one adapter does not
    hammer anyone's site. `alternates` are equivalent URLs tried in order when
    the primary fails -- some networks and filters block one host but not a
    CDN mirror of the same file.
    """
    cache_path: Optional[Path] = None
    if cache_key:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = CACHE_DIR / f"{cache_key}.cache"
        if cache_path.exists():
            age_hours = (time.time() - cache_path.stat().st_mtime) / 3600.0
            if age_hours < cache_hours:
                debug(f"cache hit ({age_hours:.1f}h old): {cache_key}")
                return cache_path.read_text(encoding="utf-8", errors="replace")

    failures: List[FetchError] = []
    for candidate in [url, *(alternates or [])]:
        try:
            debug(f"GET {candidate}")
            text = _raw_get(candidate, referer=referer, polite=polite)
        except FetchError as exc:
            debug(f"  -> {exc}")
            failures.append(exc)
            continue
        if cache_path is not None:
            cache_path.write_text(text, encoding="utf-8")
        return text

    primary = failures[0]
    if len(failures) > 1:
        primary.reason = (primary.reason or "") + \
            f" (also tried {len(failures) - 1} mirror(s), all failed)"
    raise primary


def http_get_json(url: str, **kwargs: Any) -> Any:
    return json.loads(http_get(url, **kwargs))


def to_float(value: Any) -> Optional[float]:
    """Parse a number out of a string, returning None rather than guessing."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("%", "")
    if text in {"", "-", "--", "N/A", "NA", ".", "null", "None"}:
        return None
    if text.startswith("."):          # RealGM writes ".475" for 47.5%
        text = "0" + text
    try:
        return float(text)
    except ValueError:
        return None


def safe_div(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def rounded(value: Optional[float], places: int = 3) -> Optional[float]:
    return None if value is None else round(value, places)


def merge_store(records: Dict[str, Dict[str, Any]], path: Path) -> int:
    """Merge records into a JSON store atomically, preserving "_"-prefixed keys.

    Overwriting instead of merging is how data quietly disappears: it is what
    would wipe _league_baseline out of euroleague_stats.json, and what would
    delete every KBL team the moment NZNBL was ingested into the same file.
    """
    existing: Dict[str, Any] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            backup = path.with_suffix(".corrupt.json")
            path.replace(backup)
            log(f"    [WARNING] {path.name} was not valid JSON. Moved it to {backup.name} and started fresh.")
            existing = {}
    existing.update(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return len(records)


def write_text_atomic(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="")
    os.replace(temporary, path)


# ==========================================================================
# HTML TABLE PARSER (stdlib only -- no BeautifulSoup dependency)
# ==========================================================================

class _TableParser(HTMLParser):
    """Extract every <table> on a page as a list of row-cell-lists."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: List[List[List[str]]] = []
        self._table: Optional[List[List[str]]] = None
        self._row: Optional[List[str]] = None
        self._cell: Optional[List[str]] = None
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag == "table":
            self._depth += 1
            if self._depth == 1:
                self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(re.sub(r"\s+", " ", "".join(self._cell)).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if any(cell for cell in self._row):
                self._table.append(self._row)
            self._row = None
        elif tag == "table":
            if self._depth == 1 and self._table is not None:
                self.tables.append(self._table)
                self._table = None
            self._depth = max(0, self._depth - 1)

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def parse_tables(html: str) -> List[List[List[str]]]:
    parser = _TableParser()
    parser.feed(html)
    return parser.tables


def table_to_dicts(table: List[List[str]], *, name_column: str = "Team") -> List[Dict[str, str]]:
    """Turn a raw table into dict rows keyed by its header row.

    Handles the common case where the header row has one fewer cell than the
    data rows because the team-name column header is blank.
    """
    if len(table) < 2:
        return []
    # A blank header cell is how both RealGM and mykbostats label the team
    # column. Name the first blank one after the team column and give any
    # others a positional name so they cannot collide with each other.
    header: List[str] = []
    used_name_column = False
    for position, cell in enumerate(table[0]):
        label = cell.strip()
        if not label:
            if not used_name_column:
                label, used_name_column = name_column, True
            else:
                label = f"col{position}"
        header.append(label)

    rows: List[Dict[str, str]] = []
    for raw in table[1:]:
        cells = list(raw)
        keys = list(header)
        if len(cells) == len(keys) + 1:
            keys = [name_column] + keys
        elif len(cells) != len(keys):
            if len(cells) < len(keys):
                keys = keys[:len(cells)]
            else:
                cells = cells[:len(keys)]
        row = {key.strip(): value for key, value in zip(keys, cells)}
        # The team name is not always under a header called "Team": mykbostats
        # labels that column "Season" (the split type). Keep the first cell
        # under a stable key so adapters never depend on the header wording.
        if cells:
            row["_col0"] = cells[0]
        if any(value for value in row.values()):
            rows.append(row)
    return rows


def row_name(row: Dict[str, str], *preferred: str) -> str:
    """Best guess at the entity name in a table row."""
    for key in preferred:
        value = (row.get(key) or "").strip()
        if value:
            return re.sub(r"\s+", " ", value)
    return re.sub(r"\s+", " ", (row.get("_col0") or "").strip())


def pick_table(tables: List[List[List[str]]], required_headers: Sequence[str]) -> Optional[List[List[str]]]:
    """Return the first table whose header row contains all required headers."""
    wanted = {header.lower() for header in required_headers}
    for table in tables:
        if not table:
            continue
        header = {cell.strip().lower() for cell in table[0]}
        if wanted <= header:
            return table
    return None


# ==========================================================================
# SEASON HELPERS
# ==========================================================================

def calendar_year_season() -> int:
    """Leagues that run inside one calendar year (MLB, KBO, NZ NBL)."""
    return _dt.date.today().year


def winter_season_end_year() -> int:
    """Leagues that straddle a new year (EuroLeague, KBL).

    RealGM and EuroLeague label these by the season's *ending* year, e.g. the
    2025-26 KBL season is '2026'. From September onward we are in the season
    that ends next year.
    """
    today = _dt.date.today()
    return today.year + 1 if today.month >= 9 else today.year


def euroleague_start_year() -> int:
    """euroleague-api labels a season by its *starting* year (2025 = 2025-26)."""
    return winter_season_end_year() - 1


# ==========================================================================
# ADAPTER RESULT
# ==========================================================================

class AdapterResult:
    def __init__(self, name: str) -> None:
        self.name = name
        self.ok = False
        self.count = 0
        self.detail = ""
        self.error: Optional[str] = None
        self.warnings: List[str] = []

    def succeed(self, count: int, detail: str = "") -> "AdapterResult":
        self.ok, self.count, self.detail = True, count, detail
        return self

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        log(f"    [WARNING] {message}")


# ==========================================================================
# ADAPTER: MLB TEAM METRICS  (statsapi.mlb.com -- official, public, no key)
# ==========================================================================

MLB_TEAM_STATS_URL = (
    "https://statsapi.mlb.com/api/v1/teams/stats"
    "?season={season}&group={group}&stats=season&sportIds=1"
)


def _mlb_group(season: int, group: str, check: bool) -> Dict[str, Dict[str, Any]]:
    """team name -> stat dict, with the team id kept for cross-feed joins.

    Feeds disagree on team naming: teams/stats says "Tampa Bay Rays" while the
    standings feed says "Rays". Joining on the numeric team id instead of the
    name is the only thing that matches reliably.
    """
    url = MLB_TEAM_STATS_URL.format(season=season, group=group)
    payload = http_get_json(url, cache_key=f"mlb_{group}_{season}", cache_hours=6.0)
    out: Dict[str, Dict[str, Any]] = {}
    for block in payload.get("stats", []):
        for split in block.get("splits", []):
            team_block = split.get("team") or {}
            team = team_block.get("name")
            if team:
                stat = dict(split.get("stat", {}) or {})
                if team_block.get("id") is not None:
                    stat["_team_id"] = team_block["id"]
                out[str(team).strip()] = stat
    return out


MLB_STANDINGS_URL = (
    "https://statsapi.mlb.com/api/v1/standings"
    "?leagueId=103,104&season={season}&standingsTypes=regularSeason"
)


def _mlb_standings(season: int) -> Dict[Any, Dict[str, Any]]:
    """Record-based context: home/away strength, last-ten form, streak, run diff.

    The standings feed carries win/loss splits but NOT runs splits -- there is
    no home/away runs-per-game in this feed, so none is reported. What is here
    is real: how a club performs at home vs on the road, and how it has played
    over its last ten, which season-long averages cannot show.
    """
    payload = http_get_json(MLB_STANDINGS_URL.format(season=season),
                            cache_key=f"mlb_standings_{season}", cache_hours=6.0)
    # Keyed by numeric team id. The standings feed abbreviates names ("Rays")
    # where teams/stats spells them out ("Tampa Bay Rays"), so a name-keyed
    # join silently matched almost nothing.
    out: Dict[Any, Dict[str, Any]] = {}
    for group in payload.get("records", []):
        for entry in group.get("teamRecords", []):
            team_id = (entry.get("team") or {}).get("id")
            if team_id is None:
                continue
            context: Dict[str, Any] = {}
            wins, losses = to_float(entry.get("wins")), to_float(entry.get("losses"))
            if wins is not None and losses is not None:
                context["wins"] = int(wins)
                context["losses"] = int(losses)
            for key, source in (("win_pct", "winningPercentage"),):
                value = to_float(entry.get(source))
                if value is not None:
                    context[key] = value

            games = to_float(entry.get("gamesPlayed"))
            differential = to_float(entry.get("runDifferential"))
            if differential is not None and games:
                context["run_diff_per_game"] = round(differential / games, 3)

            splits = {
                str(split.get("type")): split
                for split in (entry.get("records") or {}).get("splitRecords", [])
            }
            for label, split_type in (("home", "home"), ("away", "away"), ("l10", "lastTen")):
                split = splits.get(split_type)
                if not split:
                    continue
                split_wins, split_losses = to_float(split.get("wins")), to_float(split.get("losses"))
                pct = to_float(split.get("pct"))
                if split_wins is not None and split_losses is not None:
                    context[f"{label}_record"] = f"{int(split_wins)}-{int(split_losses)}"
                if pct is not None:
                    context[f"{label}_win_pct"] = pct

            streak = entry.get("streak") or {}
            if streak.get("streakCode"):
                context["streak"] = str(streak["streakCode"])

            # Pythagorean expectation -- the record run differential implies.
            for expected in (entry.get("records") or {}).get("expectedRecords", []):
                if str(expected.get("type", "")).lower() in {"xwinloss", "x-winloss"}:
                    pct = to_float(expected.get("pct"))
                    if pct is not None:
                        context["pythag_win_pct"] = pct
                    break

            out[team_id] = context
    return out


def ingest_mlb_teams(check: bool = False, season: Optional[int] = None) -> AdapterResult:
    """Season-to-date team run scoring, run prevention, ERA, WHIP, OBP, SLG,
    plus home/away strength and last-ten form from the standings feed."""
    result = AdapterResult("mlb")
    season = season or calendar_year_season()
    log(f"[MLB] Fetching team hitting + pitching for {season} from statsapi.mlb.com ...")

    hitting = _mlb_group(season, "hitting", check)
    pitching = _mlb_group(season, "pitching", check)
    if not hitting or not pitching:
        raise RuntimeError(f"statsapi returned no team rows for {season} "
                           f"(hitting={len(hitting)}, pitching={len(pitching)})")

    records: Dict[str, Dict[str, Any]] = {}
    for team, bat in hitting.items():
        pit = pitching.get(team, {})
        games = to_float(bat.get("gamesPlayed"))
        runs_scored = to_float(bat.get("runs"))
        runs_allowed = to_float(pit.get("runs"))

        record: Dict[str, Any] = {
            "league": "MLB",
            "season": season,
            "games": int(games) if games else None,
            "source": "statsapi.mlb.com",
            "updated": TODAY,
            "_team_id": bat.get("_team_id"),   # internal join key, stripped before writing
        }
        # Per-game rates -- statsapi gives season totals for counting stats.
        record["runs"] = rounded(safe_div(runs_scored, games), 3)
        record["runs_allowed"] = rounded(safe_div(runs_allowed, games), 3)
        # Rate stats are already rates; carry them straight through.
        for key, source_key, source in (
            ("era", "era", pit), ("whip", "whip", pit),
            ("k9", "strikeoutsPer9Inn", pit), ("bb9", "walksPer9Inn", pit),
            ("obp", "obp", bat), ("slg", "slg", bat),
            ("ops", "ops", bat), ("avg", "avg", bat),
        ):
            value = to_float(source.get(source_key))
            if value is not None:
                record[key] = value

        # Drop keys we could not fill rather than inventing a league average.
        records[team] = {k: v for k, v in record.items() if v is not None}

    # Enrichment: home/away strength, last-ten form, streak, run differential.
    # A failure here must not lose the season averages already collected.
    try:
        standings = _mlb_standings(season)
        enriched = 0
        unmatched: List[str] = []
        for team, record in records.items():
            context = standings.get(record.get("_team_id"))
            if context:
                record.update(context)
                enriched += 1
            else:
                unmatched.append(team)
        debug(f"standings enrichment applied to {enriched}/{len(records)} teams")
        if unmatched:
            result.warn(f"No standings row for {len(unmatched)} team(s): "
                        f"{', '.join(unmatched[:5])}")
    except Exception as exc:  # noqa: BLE001
        result.warn(f"Standings enrichment unavailable ({type(exc).__name__}: {exc}). "
                    f"Season averages were still collected.")

    complete = [t for t, r in records.items() if {"runs", "runs_allowed", "era"} <= r.keys()]
    if len(complete) < len(records):
        result.warn(f"{len(records) - len(complete)} MLB team(s) missing runs/ERA; "
                    f"their records were written without those fields.")

    with_form = sum(1 for r in records.values() if "l10_win_pct" in r)
    for record in records.values():
        record.pop("_team_id", None)      # join key, not data
    if check:
        return result.succeed(len(records),
                              f"{len(records)} teams, {with_form} with form/splits "
                              f"(dry run, nothing written)")

    merge_store(records, BASEBALL_STORE)
    return result.succeed(len(records),
                          f"{len(records)} teams ({with_form} with home/away + L10 form) "
                          f"-> {BASEBALL_STORE.name}")


# ==========================================================================
# ADAPTER: MLB PROBABLE STARTERS (today + tomorrow)
# ==========================================================================

MLB_SCHEDULE_URL = (
    "https://statsapi.mlb.com/api/v1/schedule"
    "?sportId=1&startDate={start}&endDate={end}&hydrate=probablePitcher,team"
)


def ingest_mlb_probables(check: bool = False, season: Optional[int] = None) -> AdapterResult:
    """Announced starting pitchers for today and tomorrow, with their season ERA/K9."""
    result = AdapterResult("mlb-probables")
    start = _dt.date.today()
    end = start + _dt.timedelta(days=1)
    log(f"[MLB] Fetching probable starters for {start} .. {end} ...")

    payload = http_get_json(
        MLB_SCHEDULE_URL.format(start=start.isoformat(), end=end.isoformat()),
        cache_key=f"mlb_sched_{start.isoformat()}", cache_hours=3.0,
    )

    # Season pitcher stats, so a probable arrives with real ERA/K9 attached.
    season = season or calendar_year_season()
    pitcher_stats: Dict[int, Dict[str, Any]] = {}
    try:
        stats_url = ("https://statsapi.mlb.com/api/v1/stats?stats=season&group=pitching"
                     f"&season={season}&sportId=1&limit=2000&playerPool=All")
        blob = http_get_json(stats_url, cache_key=f"mlb_pitchers_{season}", cache_hours=6.0)
        for block in blob.get("stats", []):
            for split in block.get("splits", []):
                player = split.get("player") or {}
                pid = player.get("id")
                if pid is not None:
                    pitcher_stats[int(pid)] = split.get("stat", {}) or {}
    except Exception as exc:  # noqa: BLE001
        result.warn(f"Could not attach season ERA/K9 to probables: {exc}")

    games: List[Dict[str, Any]] = []
    for day in payload.get("dates", []):
        for game in day.get("games", []):
            teams = game.get("teams", {})
            entry: Dict[str, Any] = {
                "game_date": day.get("date"),
                "game_pk": game.get("gamePk"),
                "status": (game.get("status") or {}).get("detailedState"),
            }
            for side in ("home", "away"):
                block = teams.get(side, {}) or {}
                entry[f"{side}_team"] = ((block.get("team") or {}).get("name"))
                probable = block.get("probablePitcher") or {}
                name = probable.get("fullName")
                entry[f"{side}_pitcher"] = name
                pid = probable.get("id")
                stat = pitcher_stats.get(int(pid)) if pid is not None else None
                if stat:
                    era = to_float(stat.get("era"))
                    k9 = to_float(stat.get("strikeoutsPer9Inn"))
                    if era is not None:
                        entry[f"{side}_pitcher_era"] = era
                    if k9 is not None:
                        entry[f"{side}_pitcher_k9"] = k9
            games.append(entry)

    named = sum(1 for g in games if g.get("home_pitcher") and g.get("away_pitcher"))
    if games and named == 0:
        result.warn("No probable pitchers announced yet for these dates.")

    if check:
        return result.succeed(len(games), f"{len(games)} games, {named} with both starters (dry run)")

    payload_out = {
        "generated": TODAY,
        "source": "statsapi.mlb.com",
        "season": season,
        "games": games,
    }
    MLB_PROBABLES_STORE.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(json.dumps(payload_out, indent=2) + "\n", MLB_PROBABLES_STORE)
    return result.succeed(len(games), f"{len(games)} games ({named} with both starters) -> {MLB_PROBABLES_STORE.name}")


# ==========================================================================
# ADAPTER: MLB PLAYER PROPS (delegates to the existing pybaseball ingestor)
# ==========================================================================

def ingest_mlb_players(check: bool = False, season: Optional[int] = None) -> AdapterResult:
    """Run the project's existing pybaseball ingestor for wOBA/ISO/K% player props.

    Kept as a delegation rather than reimplemented on statsapi because statsapi
    does not publish wOBA, and computing a fake one would be exactly the kind of
    invented number the rest of this file refuses to write.
    """
    result = AdapterResult("mlb-players")
    try:
        import pybaseball  # noqa: F401
    except ImportError:
        result.warn("pybaseball is not installed -- skipping MLB player props. "
                    "Install it with: pip install pybaseball")
        return result.succeed(0, "skipped (pybaseball not installed)")

    if check:
        return result.succeed(0, "pybaseball present (dry run, not fetched)")

    sys.path.insert(0, str(ROOT))
    from ingest_mlb import fetch_and_store_mlb  # type: ignore

    data = fetch_and_store_mlb(season or calendar_year_season())
    count = len(data.get("pitchers", {})) + len(data.get("batters", {}))
    return result.succeed(count, f"{len(data.get('pitchers', {}))} pitchers, "
                                 f"{len(data.get('batters', {}))} batters -> data/mlb_stats.json")


# ==========================================================================
# ADAPTER: KBO TEAM METRICS  (mykbostats.com team splits)
# ==========================================================================

KBO_SPLITS_URL = "https://mykbostats.com/stats/team_splits/{season}"

# mykbostats writes team names without spaces in some views; normalize to the
# spellings universal_runner.py is called with.
KBO_NAME_FIXES = {
    "KTWiz": "KT Wiz", "SamsungLions": "Samsung Lions", "LGTwins": "LG Twins",
    "KiaTigers": "KIA Tigers", "Kia Tigers": "KIA Tigers", "NCDinos": "NC Dinos",
    "LotteGiants": "Lotte Giants", "DoosanBears": "Doosan Bears",
    "SSGLanders": "SSG Landers", "HanwhaEagles": "Hanwha Eagles",
    "KiwoomHeroes": "Kiwoom Heroes", "OBBears": "Doosan Bears",
}


def _kbo_normalize(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", name).strip()
    if cleaned in KBO_NAME_FIXES:
        return KBO_NAME_FIXES[cleaned]
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", cleaned)
    return KBO_NAME_FIXES.get(spaced, spaced)


def ingest_kbo_teams(check: bool = False, season: Optional[int] = None) -> AdapterResult:
    """Team runs/game, runs allowed/game, starter ERA and bullpen ERA."""
    result = AdapterResult("kbo")
    season = season or calendar_year_season()
    url = KBO_SPLITS_URL.format(season=season)
    log(f"[KBO] Fetching team splits for {season} from mykbostats.com ...")

    html = http_get(url, cache_key=f"kbo_splits_{season}", cache_hours=6.0, polite=True,
                    referer="https://mykbostats.com/")
    tables = parse_tables(html)
    table = pick_table(tables, ["G", "R/G", "-R/G"])
    if table is None:
        raise RuntimeError(
            f"No team-splits table found at {url}. The page layout may have changed -- "
            f"open it in a browser and check that a table with G / R/G / -R/G columns is present."
        )

    # The first table on the page is the full-season split; the others are
    # home/away/etc. The team-name column is headed "Season", not "Team".
    debug(f"KBO header row: {table[0]}")
    rows = table_to_dicts(table, name_column="Team")
    records: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        team = _kbo_normalize(row_name(row, "Team"))
        if not team or team.lower() in {"team", "season", "total", "league", "average"}:
            continue
        games = to_float(row.get("G"))
        runs_for = to_float(row.get("R/G"))
        runs_against = to_float(row.get("-R/G"))
        era_sp = to_float(row.get("ERASP"))
        era_rp = to_float(row.get("ERARP"))

        if runs_for is None or runs_against is None:
            result.warn(f"{team}: no runs data on the splits page; skipped.")
            continue

        record: Dict[str, Any] = {
            "league": "KBO",
            "season": season,
            "runs": runs_for,
            "runs_allowed": runs_against,
            "source": "mykbostats.com/stats/team_splits",
            "updated": TODAY,
        }
        if games:
            record["games"] = int(games)
        if era_sp is not None:
            record["era"] = era_sp          # rotation ERA is what the run model wants
            record["era_sp"] = era_sp
        if era_rp is not None:
            record["era_rp"] = era_rp
        if (batting_avg := to_float(row.get("BA"))) is not None:
            record["avg"] = batting_avg
        records[team] = record

    if not records:
        raise RuntimeError("KBO splits table parsed but contained no usable team rows")

    missing_era = [t for t, r in records.items() if "era" not in r]
    if missing_era:
        result.warn(f"No starter ERA for: {', '.join(missing_era)}")

    if check:
        return result.succeed(len(records), f"{len(records)} teams (dry run, nothing written)")

    merge_store(records, BASEBALL_STORE)
    return result.succeed(len(records), f"{len(records)} teams -> {BASEBALL_STORE.name}")


# ==========================================================================
# ADAPTER: EUROLEAGUE  (euroleague-api package)
# ==========================================================================

def ingest_euroleague(check: bool = False, season: Optional[int] = None) -> AdapterResult:
    """EuroLeague team ORTG/DRTG/pace, merged so _league_baseline survives.

    The project's older ingest_hoops.py wrote this file with a plain overwrite,
    which deleted the _league_baseline block that
    team_stats_provider.get_euroleague_league_baseline() reads. This merges.
    """
    result = AdapterResult("euroleague")
    try:
        from euroleague_api.team_stats import TeamStats  # type: ignore
    except ImportError:
        result.warn("euroleague-api is not installed -- skipping EuroLeague. "
                    "Install it with: pip install euroleague-api")
        return result.succeed(0, "skipped (euroleague-api not installed)")

    season = season or euroleague_start_year()
    log(f"[EuroLeague] Fetching team stats for the {season}-{str(season + 1)[2:]} season ...")

    # euroleague-api 0.1.1 takes the STAT TYPE as the first positional argument
    # and the season as a keyword -- get_team_stats(season) reads the year as a
    # statistic name and raises. Own and opponent box scores are pulled
    # separately so ORTG/DRTG/pace are computed here with the same possession
    # formula used for every other basketball league, instead of trusting a
    # column name that may be spelled differently between versions.
    def fetch(endpoint: str, year: int) -> Any:
        return TeamStats("E").get_team_stats_single_season(
            endpoint=endpoint, season=year, phase_type_code=None, statistic_mode="PerGame"
        )

    own = opponent = None
    tried: List[int] = []
    for candidate in (season, season - 1):
        tried.append(candidate)
        try:
            own = fetch("traditional", candidate)
            opponent = fetch("opponentsTraditional", candidate)
        except Exception as exc:  # noqa: BLE001
            result.warn(f"EuroLeague season {candidate}: {type(exc).__name__}: {exc}")
            own = opponent = None
        if own is not None and not own.empty:
            season = candidate
            break

    if own is None or own.empty:
        raise RuntimeError(f"EuroLeague API returned no rows for seasons {tried}")
    debug(f"EuroLeague columns: {list(own.columns)}")

    def find(frame: Any, *fragments: str) -> Optional[str]:
        """Locate a column by fuzzy name so a renamed field does not break us."""
        squashed = {re.sub(r"[^a-z0-9]", "", str(c).lower()): c for c in frame.columns}
        for fragment in fragments:
            key = re.sub(r"[^a-z0-9]", "", fragment.lower())
            if key in squashed:
                return squashed[key]
        for fragment in fragments:
            key = re.sub(r"[^a-z0-9]", "", fragment.lower())
            for flat, original in squashed.items():
                if key and key in flat:
                    return original
        return None

    def box(frame: Any) -> Dict[str, Dict[str, float]]:
        """team -> {points, fga, fta, orb, tov} using per-game values."""
        name_col = find(frame, "team.name", "teamName", "team", "name")
        points_col = find(frame, "pointsScored", "points")
        fga2 = find(frame, "twoPointersAttempted", "fieldGoalsAttempted2")
        fga3 = find(frame, "threePointersAttempted", "fieldGoalsAttempted3")
        fga_all = find(frame, "fieldGoalsAttempted")
        fta_col = find(frame, "freeThrowsAttempted")
        orb_col = find(frame, "offensiveRebounds")
        tov_col = find(frame, "turnovers", "turnoversCommitted")
        if not all((name_col, points_col, fta_col, orb_col, tov_col)) or not (fga_all or (fga2 and fga3)):
            raise RuntimeError(
                "EuroLeague response is missing box-score columns needed for possessions. "
                f"Columns returned: {list(frame.columns)}"
            )
        out: Dict[str, Dict[str, float]] = {}
        for _, row in frame.iterrows():
            team = str(row.get(name_col) or "").strip()
            if not team:
                continue
            if fga_all:
                fga = to_float(row.get(fga_all))
            else:
                two, three = to_float(row.get(fga2)), to_float(row.get(fga3))
                fga = None if two is None or three is None else two + three
            values = {
                "points": to_float(row.get(points_col)),
                "fga": fga,
                "fta": to_float(row.get(fta_col)),
                "orb": to_float(row.get(orb_col)),
                "tov": to_float(row.get(tov_col)),
            }
            if all(v is not None for v in values.values()):
                out[team] = values  # type: ignore[assignment]
        return out

    own_box = box(own)
    opponent_box = box(opponent) if opponent is not None and not opponent.empty else {}
    if not opponent_box:
        result.warn("EuroLeague opponent stats unavailable -- DRTG will be omitted, not guessed.")

    if check:
        return result.succeed(len(own_box),
                              f"{len(own_box)} teams, season {season} (dry run)")

    def possessions(values: Dict[str, float]) -> Optional[float]:
        total = values["fga"] + 0.44 * values["fta"] - values["orb"] + values["tov"]
        return total if total > 0 else None

    records: Dict[str, Dict[str, Any]] = {}
    incomplete: List[str] = []
    for team, values in own_box.items():
        own_possessions = possessions(values)
        if own_possessions is None:
            incomplete.append(team)
            continue
        record: Dict[str, Any] = {
            "league": "EuroLeague",
            "season": season,
            "ortg": round(100.0 * values["points"] / own_possessions, 3),
            "source": "euroleague-api (traditional + opponentsTraditional)",
            "updated": TODAY,
        }
        against = opponent_box.get(team)
        opponent_possessions = possessions(against) if against else None
        if against and opponent_possessions:
            record["drtg"] = round(100.0 * against["points"] / opponent_possessions, 3)
            record["pace"] = round((own_possessions + opponent_possessions) / 2.0, 3)
            record["baseline_net"] = round(record["ortg"] - record["drtg"], 3)
        else:
            record["pace"] = round(own_possessions, 3)
        records[team] = record

    if incomplete:
        result.warn(f"{len(incomplete)} EuroLeague team(s) had unusable box scores, skipped: "
                    f"{', '.join(incomplete[:6])}")
    if not records:
        raise RuntimeError("EuroLeague returned rows but none produced usable ratings")

    merge_store(records, EUROLEAGUE_STORE)
    return result.succeed(len(records), f"{len(records)} teams (season {season}) -> {EUROLEAGUE_STORE.name}")


# ==========================================================================
# ADAPTER: REALGM BASKETBALL  (KBL and NZ NBL)
# ==========================================================================

REALGM_URL = ("https://basketball.realgm.com/international/league/{league_id}/{slug}"
              "/team-stats/{season}/Averages/{side}")

REALGM_LEAGUES = {
    "kbl": {
        "league_id": 63,
        "slug": "south-korean-kbl",
        "display": "KBL",
        "seasons": lambda: [winter_season_end_year(), winter_season_end_year() - 1],
    },
    "nznbl": {
        "league_id": 75,
        "slug": "New-Zealand-NBL",
        "display": "NZ NBL",
        "seasons": lambda: [calendar_year_season(), calendar_year_season() - 1],
    },
}

_REALGM_REQUIRED = ["Team", "GP", "PPG", "FGA", "FTA", "ORB", "TOV"]


def _realgm_side(league_key: str, season: int, side: str) -> List[Dict[str, str]]:
    config = REALGM_LEAGUES[league_key]
    url = REALGM_URL.format(league_id=config["league_id"], slug=config["slug"],
                            season=season, side=side)
    html = http_get(url, cache_key=f"realgm_{league_key}_{season}_{side}",
                    cache_hours=12.0, polite=True,
                    referer=f"https://basketball.realgm.com/international/league/"
                            f"{config['league_id']}/{config['slug']}/team-stats")
    tables = parse_tables(html)
    debug(f"RealGM {league_key} {side}: {len(tables)} table(s); "
          f"first header = {tables[0][0] if tables else 'none'}")
    table = pick_table(tables, _REALGM_REQUIRED)
    if table is None:
        return []
    return table_to_dicts(table)


def _possessions(row: Dict[str, str]) -> Optional[float]:
    """Standard possession estimate: FGA + 0.44*FTA - ORB + TOV (per game)."""
    fga, fta = to_float(row.get("FGA")), to_float(row.get("FTA"))
    orb, tov = to_float(row.get("ORB")), to_float(row.get("TOV"))
    if None in (fga, fta, orb, tov):
        return None
    possessions = fga + 0.44 * fta - orb + tov
    return possessions if possessions > 0 else None


def ingest_realgm(league_key: str, check: bool = False, season: Optional[int] = None) -> AdapterResult:
    """Team ORTG/DRTG/pace for a RealGM international league."""
    config = REALGM_LEAGUES[league_key]
    result = AdapterResult(league_key)
    candidates = [season] if season else config["seasons"]()

    team_rows: List[Dict[str, str]] = []
    opponent_rows: List[Dict[str, str]] = []
    used_season: Optional[int] = None
    for candidate in candidates:
        log(f"[{config['display']}] Fetching RealGM team + opponent averages for {candidate} ...")
        team_rows = _realgm_side(league_key, candidate, "Team_Totals")
        if not team_rows:
            continue
        opponent_rows = _realgm_side(league_key, candidate, "Opponent_Totals")
        used_season = candidate
        break

    if not team_rows or used_season is None:
        raise RuntimeError(
            f"No team stats table found for {config['display']} in seasons {candidates}. "
            f"Check {REALGM_URL.format(league_id=config['league_id'], slug=config['slug'], season=candidates[0], side='Team_Totals')}"
        )
    if not opponent_rows:
        result.warn(f"{config['display']}: opponent table unavailable -- DRTG will be omitted, "
                    f"not guessed. Predictions needing DRTG will warn instead of using a fake value.")

    opponents = {row.get("Team", "").strip(): row for row in opponent_rows}

    records: Dict[str, Dict[str, Any]] = {}
    for row in team_rows:
        team = re.sub(r"\s+", " ", row.get("Team", "")).strip()
        if not team or team.lower() in {"team", "league average", "total"}:
            continue
        games = to_float(row.get("GP"))
        points = to_float(row.get("PPG"))
        team_possessions = _possessions(row)
        if points is None or team_possessions is None:
            result.warn(f"{team}: incomplete box-score columns; skipped.")
            continue

        record: Dict[str, Any] = {
            "league": config["display"],
            "season": used_season,
            "ortg": round(100.0 * points / team_possessions, 3),
            "source": f"basketball.realgm.com/league/{config['league_id']}",
            "updated": TODAY,
        }
        if games:
            record["games"] = int(games)

        opponent = opponents.get(team)
        opponent_possessions = _possessions(opponent) if opponent else None
        opponent_points = to_float(opponent.get("PPG")) if opponent else None

        if opponent_points is not None and opponent_possessions is not None:
            record["drtg"] = round(100.0 * opponent_points / opponent_possessions, 3)
            record["pace"] = round((team_possessions + opponent_possessions) / 2.0, 3)
            record["baseline_net"] = round(record["ortg"] - record["drtg"], 3)
        else:
            record["pace"] = round(team_possessions, 3)

        if (three := to_float(row.get("3P%"))) is not None:
            record["three_pt_pct"] = three
        # ORB% needs the opponent's defensive rebounds to be meaningful.
        opponent_drb = to_float(opponent.get("DRB")) if opponent else None
        own_orb = to_float(row.get("ORB"))
        if own_orb is not None and opponent_drb is not None and (own_orb + opponent_drb) > 0:
            record["orb_pct"] = round(own_orb / (own_orb + opponent_drb), 3)

        records[team] = record

    if not records:
        raise RuntimeError(f"{config['display']}: table parsed but produced no usable teams")

    without_drtg = [t for t, r in records.items() if "drtg" not in r]
    if without_drtg:
        result.warn(f"{len(without_drtg)} {config['display']} team(s) have no DRTG "
                    f"(no matching opponent row): {', '.join(without_drtg[:5])}")

    if check:
        return result.succeed(len(records), f"{len(records)} teams, season {used_season} (dry run)")

    merge_store(records, BASKETBALL_STORE)
    return result.succeed(len(records), f"{len(records)} teams (season {used_season}) -> {BASKETBALL_STORE.name}")


def ingest_kbl(check: bool = False, season: Optional[int] = None) -> AdapterResult:
    return ingest_realgm("kbl", check=check, season=season)


def ingest_nznbl(check: bool = False, season: Optional[int] = None) -> AdapterResult:
    return ingest_realgm("nznbl", check=check, season=season)


# ==========================================================================
# ADAPTER: TENNIS  (ATP main tour + Challenger, Jeff Sackmann's CSVs)
# ==========================================================================

TENNIS_YEARS_BACK = 3          # rolling Elo window
_SURFACE_MAP = {"hard": "hard", "clay": "clay", "grass": "grass", "carpet": "hard"}

# The same files served four ways. Some networks, DNS filters and security
# suites block raw.githubusercontent.com outright and answer 404 for every
# path on it, which looks exactly like "the file does not exist" -- so a
# mirror list is the difference between working and mysteriously empty.
SACKMANN_MIRRORS = [
    "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/{name}",
    "https://cdn.jsdelivr.net/gh/JeffSackmann/tennis_atp@master/{name}",
    "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/main/{name}",
    "https://github.com/JeffSackmann/tennis_atp/raw/master/{name}",
]


def _sackmann_files(year: int) -> List[Tuple[str, str]]:
    """(tier, filename) pairs to try for a season. Missing files are skipped."""
    return [
        ("atp", f"atp_matches_{year}.csv"),
        ("challenger", f"atp_matches_qual_chall_{year}.csv"),
    ]


def ingest_tennis(check: bool = False, season: Optional[int] = None) -> AdapterResult:
    """Build the match-history CSV that models/tennis_elo.py loads.

    Output columns are exactly what TennisElo.load_match_history() expects:
        winner_name, loser_name, surface, tournament_date
    plus tier/tourney/round columns it ignores but you may want when auditing.

    Sackmann publishes the current year's main-tour file continuously and the
    qualifying/Challenger file on a lag, so a 404 on one of them is normal and
    is reported, not treated as a failure.
    """
    result = AdapterResult("tennis")
    end_year = season or calendar_year_season()
    years = list(range(end_year - TENNIS_YEARS_BACK + 1, end_year + 1))
    log(f"[Tennis] Fetching ATP main-tour + Challenger results for {years[0]}-{years[-1]} ...")

    rows: List[Dict[str, str]] = []
    fetched: List[str] = []
    missing = 0
    attempted = 0
    for year in years:
        for tier, filename in _sackmann_files(year):
            attempted += 1
            urls = [pattern.format(name=filename) for pattern in SACKMANN_MIRRORS]
            try:
                text = http_get(urls[0], cache_key=f"tennis_{filename}",
                                cache_hours=12.0, alternates=urls[1:])
            except FetchError as exc:
                missing += 1
                if exc.status == 404:
                    result.warn(f"{filename}: not available (404 from every mirror). "
                                f"Current-year Challenger files are published on a lag, "
                                f"so this is expected for the newest season.")
                else:
                    result.warn(f"{filename}: {exc}")
                continue
            except Exception as exc:  # noqa: BLE001
                missing += 1
                result.warn(f"{filename} failed ({type(exc).__name__}) -- skipped.")
                continue

            reader = csv.DictReader(io.StringIO(text))
            added = 0
            for record in reader:
                winner = (record.get("winner_name") or "").strip()
                loser = (record.get("loser_name") or "").strip()
                if not winner or not loser:
                    continue
                surface = _SURFACE_MAP.get((record.get("surface") or "").strip().lower(), "hard")
                raw_date = (record.get("tourney_date") or "").strip()
                if len(raw_date) == 8 and raw_date.isdigit():
                    date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
                else:
                    date = raw_date
                rows.append({
                    "winner_name": winner,
                    "loser_name": loser,
                    "surface": surface,
                    "tournament_date": date,
                    "tier": tier,
                    "tourney_name": (record.get("tourney_name") or "").strip(),
                    "round": (record.get("round") or "").strip(),
                })
                added += 1
            fetched.append(f"{filename} ({added})")

    if not rows:
        raise RuntimeError(
            f"All {attempted} tennis files failed across {len(SACKMANN_MIRRORS)} mirrors "
            f"(raw.githubusercontent.com, jsDelivr, github.com). Files for past seasons "
            f"definitely exist, so this is a network block, not missing data -- check "
            f"whether a firewall, VPN, DNS filter or antivirus is intercepting these hosts. "
            f"Test in a browser: https://cdn.jsdelivr.net/gh/JeffSackmann/tennis_atp@master/"
            f"atp_matches_{years[0]}.csv"
        )

    rows.sort(key=lambda r: r["tournament_date"])   # Elo must be applied chronologically
    tiers = {tier: sum(1 for r in rows if r["tier"] == tier) for tier in {r["tier"] for r in rows}}
    players = len({r["winner_name"] for r in rows} | {r["loser_name"] for r in rows})

    if check:
        return result.succeed(len(rows), f"{len(rows)} matches, {players} players (dry run)")

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=[
        "winner_name", "loser_name", "surface", "tournament_date",
        "tier", "tourney_name", "round",
    ], lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    write_text_atomic(buffer.getvalue(), TENNIS_MATCHES_CSV)

    write_text_atomic(json.dumps({
        "generated": TODAY,
        "years": years,
        "matches": len(rows),
        "players": players,
        "by_tier": tiers,
        "files": fetched,
        "source": "https://github.com/JeffSackmann/tennis_atp",
        "license": "CC BY-NC-SA 4.0 (attribution required, non-commercial)",
    }, indent=2) + "\n", TENNIS_META)

    detail = ", ".join(f"{tier}={count}" for tier, count in sorted(tiers.items()))
    return result.succeed(len(rows), f"{len(rows)} matches ({detail}), {players} players -> {TENNIS_MATCHES_CSV.name}")


# ==========================================================================
# ADAPTER: SOCCER (delegates to the existing ingestor)
# ==========================================================================

ESPN_SOCCER_LEAGUES = ["liga_mx", "epl", "la_liga", "bundesliga", "serie_a",
                       "ligue_1", "eredivisie", "mls"]


def ingest_soccer_espn_delegate(check: bool = False,
                                season: Optional[int] = None) -> AdapterResult:
    """Soccer team goals from ESPN, for leagues FBref will not serve us.

    FBref returns 403 to this machine, so the soccerdata path below produces
    nothing. ESPN has no bot wall and covers Liga MX, which FBref coverage was
    always thin on anyway. The trade is that ESPN publishes no xG, so these
    rows carry goals-derived estimates tagged data_tier 2 -- never mistake
    them for real expected goals.
    """
    result = AdapterResult("soccer-espn")
    sys.path.insert(0, str(ROOT))
    from ingest_soccer_espn import ingest_league  # type: ignore

    total = 0
    failed: List[str] = []
    for league in ESPN_SOCCER_LEAGUES:
        try:
            teams, _ = ingest_league(league, check, False, season)
            total += teams
        except Exception as exc:  # noqa: BLE001
            result.warn(f"{league}: {type(exc).__name__}: {exc}")
            failed.append(league)

    if not total:
        raise RuntimeError(f"No ESPN soccer teams ingested (all {len(failed)} league(s) failed)")
    detail = f"{total} teams across {len(ESPN_SOCCER_LEAGUES) - len(failed)} league(s)"
    return result.succeed(total, detail + (" (dry run)" if check else " -> data/soccer_stats.json"))


def ingest_soccer_delegate(check: bool = False, season: Optional[int] = None) -> AdapterResult:
    result = AdapterResult("soccer")
    if check:
        return result.succeed(0, "delegates to ingest_soccer.py (dry run, not fetched)")
    sys.path.insert(0, str(ROOT))
    from ingest_soccer import DEFAULT_LEAGUES, _current_season, fetch_and_store_soccer  # type: ignore

    records = fetch_and_store_soccer(_current_season(), DEFAULT_LEAGUES)
    return result.succeed(len(records), f"{len(records)} teams -> data/soccer_stats.json")


# ==========================================================================
# REGISTRY + RUNNER
# ==========================================================================

Adapter = Callable[..., AdapterResult]

ADAPTERS: "Dict[str, Tuple[str, Adapter]]" = {
    "mlb":            ("MLB team metrics (statsapi.mlb.com)",            ingest_mlb_teams),
    "mlb-probables":  ("MLB probable starters, today + tomorrow",        ingest_mlb_probables),
    "mlb-players":    ("MLB player props via pybaseball",                ingest_mlb_players),
    "kbo":            ("KBO team metrics (mykbostats.com)",              ingest_kbo_teams),
    "euroleague":     ("EuroLeague ORTG/DRTG/pace (euroleague-api)",     ingest_euroleague),
    "kbl":            ("Korean Basketball League (RealGM)",              ingest_kbl),
    "nznbl":          ("New Zealand NBL (RealGM)",                       ingest_nznbl),
    "tennis":         ("ATP + Challenger match history (Sackmann)",      ingest_tennis),
    "soccer-espn":    ("Soccer goals incl. Liga MX (ESPN)",              ingest_soccer_espn_delegate),
    "soccer":         ("Soccer xG via existing ingest_soccer.py (FBref)", ingest_soccer_delegate),
}

# soccer-espn runs before soccer so that when FBref is reachable again its real
# xG overwrites the ESPN goals estimate rather than the other way round.
DEFAULT_ORDER = ["mlb", "mlb-probables", "mlb-players", "kbo",
                 "euroleague", "kbl", "nznbl", "tennis", "soccer-espn", "soccer"]


def run(selected: List[str], check: bool, season: Optional[int]) -> int:
    started = _dt.datetime.now()
    mode = "CHECK (no files written)" if check else "INGEST"
    log("=" * 72)
    log(f"MultiSportPredict daily ingestion - {mode} - {started:%Y-%m-%d %H:%M:%S}")
    log("=" * 72)

    results: List[AdapterResult] = []
    for name in selected:
        description, adapter = ADAPTERS[name]
        log(f"\n--- {name}: {description}")
        try:
            results.append(adapter(check=check, season=season))
        except Exception as exc:  # noqa: BLE001
            failed = AdapterResult(name)
            failed.error = f"{type(exc).__name__}: {exc}"
            log(f"    [FAILED] {failed.error}")
            results.append(failed)

    log("\n" + "=" * 72)
    log("SUMMARY")
    log("=" * 72)
    succeeded = [r for r in results if r.ok]
    failed = [r for r in results if not r.ok]
    for outcome in results:
        marker = "OK  " if outcome.ok else "FAIL"
        log(f"  [{marker}] {outcome.name:<15} {outcome.detail or outcome.error or ''}")
        for warning in outcome.warnings:
            log(f"         warning: {warning}")

    elapsed = (_dt.datetime.now() - started).total_seconds()
    log(f"\n{len(succeeded)}/{len(results)} adapters succeeded in {elapsed:.0f}s")

    if not succeeded:
        log("\nEvery adapter failed. That usually means no internet access, not nine broken sites.")
        return 2
    if failed:
        log(f"\n{len(failed)} adapter(s) failed. The others still wrote their data, so today's "
            f"predictions for those leagues are fine.")
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Daily multi-sport data ingestion for MultiSportPredict.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Adapters: " + ", ".join(DEFAULT_ORDER),
    )
    parser.add_argument("--only", nargs="+", metavar="ADAPTER",
                        help="Run only these adapters.")
    parser.add_argument("--skip", nargs="+", metavar="ADAPTER", default=[],
                        help="Run everything except these adapters.")
    parser.add_argument("--check", action="store_true",
                        help="Contact every source and report what it returns, but write nothing.")
    parser.add_argument("--season", type=int, default=None,
                        help="Force a season year. Each adapter otherwise picks its own.")
    parser.add_argument("--list", action="store_true", help="List adapters and exit.")
    parser.add_argument("--no-cache", action="store_true",
                        help="Ignore the on-disk response cache and refetch everything.")
    parser.add_argument("--debug", action="store_true",
                        help="Print every URL tried and the raw column names each source "
                             "returned. Use this when an adapter fails and the reason is not "
                             "obvious from the error.")
    args = parser.parse_args()

    global DEBUG
    DEBUG = args.debug

    if args.list:
        for name in DEFAULT_ORDER:
            print(f"  {name:<15} {ADAPTERS[name][0]}")
        return

    if args.no_cache and CACHE_DIR.exists():
        for stale in CACHE_DIR.glob("*.cache"):
            stale.unlink()
        log("[*] Response cache cleared.")

    selected = args.only if args.only else list(DEFAULT_ORDER)
    unknown = [name for name in selected + list(args.skip) if name not in ADAPTERS]
    if unknown:
        parser.error(f"Unknown adapter(s): {', '.join(unknown)}. "
                     f"Valid names: {', '.join(DEFAULT_ORDER)}")
    selected = [name for name in selected if name not in set(args.skip)]
    if not selected:
        parser.error("Nothing left to run after --skip.")

    # The delegated ingestors (ingest_mlb.py, ingest_soccer.py) write to
    # relative paths like "data/mlb_stats.json", so the working directory has
    # to be the project root no matter how this script was invoked -- a
    # scheduled task does not necessarily start where the script lives.
    os.chdir(ROOT)
    DATA.mkdir(parents=True, exist_ok=True)
    sys.exit(run(selected, args.check, args.season))


if __name__ == "__main__":
    main()
