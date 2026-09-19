#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ingest_tennis.py - Build the ATP/WTA match history the Elo engine runs on

    python ingest_tennis.py                       ATP + WTA, 2025 and 2026
    python ingest_tennis.py --years 2024 2025 2026
    python ingest_tennis.py --tours atp
    python ingest_tennis.py --check               download and report, write nothing
    python ingest_tennis.py --list "Alcaraz"      who is in the store

WHAT IT WRITES
    data/tennis/matches.csv    winner_name, loser_name, surface, tournament_date
                               -- the four columns models/tennis_elo.py reads
    data/tennis/players.json   per-player summary: matches, surface splits,
                               last match date, best ranking seen

WHY THIS SOURCE
    Jeff Sackmann's tennis_atp repository -- the usual answer -- is no longer
    publicly reachable, and the GitHub API returns 403 from here. FBref-style
    scrapers are behind Cloudflare. tennis-data.co.uk publishes one archive per
    season per tour, covers ATP from 2000 and WTA from 2007, and answers
    plainly. It is the same kind of source as football-data.co.uk, which is the
    only soccer feed that still works.

WHY ORDER MATTERS MORE THAN IT LOOKS
    Elo is sequential: every match updates a rating that the next match reads.
    Feeding 2026 before 2025, or one tournament's matches out of order, produces
    ratings that are arithmetically fine and factually wrong -- and nothing
    downstream can tell. Every row from every file is therefore pooled and
    sorted by date before a single line is written.

WHAT IS DROPPED, AND WHY
    Walkovers. A walkover is an administrative result, not evidence about how
    two players compare, and letting one move a rating is the same error as
    predicting from a one-game sample. Retirements are KEPT: a player who
    retires at 2-6 0-3 did lose that match on court.

NAMES
    This feed spells players "Alcaraz C.", not "Carlos Alcaraz". Names are
    stored exactly as the feed writes them, because a name you can trace back
    to a source is worth more than one this script improved on its own.
    run_tennis.py does the translation, and refuses when it is ambiguous.
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
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "data" / "tennis"

# The site answered plain http until 2026-08-30 and began refusing it some time
# before 2026-09-18, which surfaced as four identical HTTPErrors and a store
# frozen 19 days out of date. Try https first and keep http as the fallback so
# a reversal on their side does not break this again.
BASE = "https://www.tennis-data.co.uk"
BASE_FALLBACK = "http://www.tennis-data.co.uk"
UA = {"User-Agent": "Mozilla/5.0 (MultiSportPredict tennis ingest)"}

SURFACES = {"hard", "clay", "grass", "carpet"}

# Fewest matches before a player's Elo is worth quoting. Below this the rating
# is mostly the starting constant wearing a player's name.
MIN_MATCHES = 8


def log(message: str = "") -> None:
    print(message, flush=True)


def rule(char: str = "=") -> None:
    log(char * 78)


# ==========================================================================
# DOWNLOAD
# ==========================================================================

def archive_urls(tour: str, year: int) -> List[str]:
    """Every URL worth trying for one tour-season, best first.

    Two things are easy to get wrong here, and both return HTTP 300 rather than
    404 because the server has mod_negotiation on: the file is .xlsx, not .zip,
    and for the women's tour only the DIRECTORY carries the 'w'. The women's
    2026 season is /2026w/2026.xlsx -- not /2026w/2026w.xlsx.

    The .zip spellings stay as fallbacks because older seasons were published
    that way and a 300 costs one wasted request, not a wrong answer.
    """
    directory = f"{year}w" if tour == "wta" else f"{year}"
    names = [f"{year}.xlsx", f"{year}.xls", f"{year}.zip", f"{directory}.zip"]
    return ([f"{BASE}/{directory}/{n}" for n in names]
            + [f"{BASE_FALLBACK}/{directory}/{n}" for n in names])


def fetch(url: str, timeout: int = 180, attempts: int = 3) -> bytes:
    """Download one season file, retrying a timeout but not a 404.

    The current season's workbook is the largest and the slowest to serve, and
    a single 60s attempt kept losing it -- which quietly left the men's ratings
    frozen at the end of the previous November while everything else looked
    fine. A missing file is answered immediately and is not worth retrying;
    a timeout usually is.
    """
    last: Exception = RuntimeError("no attempt made")
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            # "HTTPError" alone told us nothing when all eight URLs failed at
            # once. The status separates "file not published yet" (404) from
            # "the server is refusing us" (403) from a scheme problem.
            exc.msp_detail = f"HTTP {exc.code} {exc.reason}"
            raise                                   # retrying a status changes nothing
        except Exception as exc:                    # noqa: BLE001
            last = exc
            if attempt < attempts:
                log(f"               {url.rsplit('/', 1)[-1]}: "
                    f"{type(exc).__name__}, retrying ({attempt}/{attempts - 1})")
                time.sleep(3 * attempt)
    raise last


# ==========================================================================
# READING THE WORKBOOK
#
# pandas + openpyxl is the short path. The stdlib path below exists because
# openpyxl is not in this venv, and an ingest that cannot run until a pip
# install succeeds is an ingest that does not run tonight. An .xlsx is a zip
# of XML; for a single flat sheet that is a readable amount of work.
# ==========================================================================

def rows_via_pandas(blob: bytes) -> Optional[List[Dict[str, Any]]]:
    try:
        import pandas
    except ImportError:
        return None
    try:
        frame = pandas.read_excel(io.BytesIO(blob))
    except Exception:      # noqa: BLE001  -- missing openpyxl lands here too
        return None
    return frame.to_dict("records")


def _column_index(reference: str) -> int:
    """'A' -> 0, 'AB' -> 27. Cell refs are base-26 with no zero digit."""
    letters = re.match(r"[A-Z]+", reference)
    if not letters:
        return 0
    index = 0
    for char in letters.group(0):
        index = index * 26 + (ord(char) - 64)
    return index - 1


def _excel_serial_to_date(value: float) -> Optional[str]:
    """Excel counts days from 1899-12-30 (the offset absorbs its 1900 leap bug)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not 20000 < number < 60000:          # outside ~1954..2064, not a date
        return None
    stamp = _dt.date(1899, 12, 30) + _dt.timedelta(days=int(number))
    return stamp.isoformat()


def rows_via_stdlib(blob: bytes) -> List[Dict[str, Any]]:
    """Parse the first worksheet of an .xlsx with nothing but the stdlib."""
    import xml.etree.ElementTree as ET

    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(blob)) as book:
        names = book.namelist()
        sheet_name = next((n for n in names if n.startswith("xl/worksheets/sheet")), None)
        if sheet_name is None:
            raise ValueError("no worksheet inside the workbook")

        shared: List[str] = []
        if "xl/sharedStrings.xml" in names:
            tree = ET.fromstring(book.read("xl/sharedStrings.xml"))
            for item in tree.findall(f"{namespace}si"):
                shared.append("".join(t.text or "" for t in item.iter(f"{namespace}t")))

        sheet = ET.fromstring(book.read(sheet_name))

    table: List[List[Any]] = []
    for row in sheet.iter(f"{namespace}row"):
        cells: Dict[int, Any] = {}
        for cell in row.findall(f"{namespace}c"):
            reference = cell.get("r") or "A1"
            kind = cell.get("t")
            value_node = cell.find(f"{namespace}v")
            if kind == "inlineStr":
                node = cell.find(f"{namespace}is")
                text = "".join(t.text or "" for t in node.iter(f"{namespace}t")) if node is not None else ""
            elif value_node is None:
                text = ""
            elif kind == "s":
                index = int(value_node.text or 0)
                text = shared[index] if 0 <= index < len(shared) else ""
            else:
                text = value_node.text or ""
            cells[_column_index(reference)] = text
        width = (max(cells) + 1) if cells else 0
        table.append([cells.get(i, "") for i in range(width)])

    if not table:
        return []
    header = [str(h).strip() for h in table[0]]
    records: List[Dict[str, Any]] = []
    for line in table[1:]:
        if not any(str(v).strip() for v in line):
            continue
        record = {header[i]: line[i] for i in range(min(len(header), len(line)))}
        records.append(record)
    return records


def read_archive(blob: bytes, url: str = "") -> List[Dict[str, Any]]:
    """Return rows from a season file, zipped or not.

    An .xlsx IS a zip, so "does it unzip" cannot tell the two apart. What
    distinguishes them is what is inside: a real archive holds a workbook or a
    csv; a bare .xlsx holds xl/worksheets/... and no such member.
    """
    name, inner = url, blob
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            members = archive.namelist()
            candidates = [n for n in members
                          if n.lower().endswith((".xlsx", ".xls", ".csv"))]
            if candidates:
                name = candidates[0]
                inner = archive.read(name)
            elif not any(n.startswith("xl/") for n in members):
                raise ValueError(f"archive holds nothing readable: {members[:6]}")
    except zipfile.BadZipFile:
        pass          # not a zip at all -- a bare .xls or .csv download

    if name.lower().endswith(".csv"):
        text = inner.decode("utf-8-sig", errors="replace")
        return list(csv.DictReader(io.StringIO(text)))

    rows = rows_via_pandas(inner)
    if rows is not None:
        return rows
    if name.lower().endswith(".xls"):
        raise ValueError(
            f"{name} is the old .xls format, which needs pandas + xlrd.\n"
            f"    Either install it:  pip install xlrd\n"
            f"    or skip that season: --years 2024 2025 2026 (all .xlsx)")
    return rows_via_stdlib(inner)


# ==========================================================================
# NORMALISING A ROW
# ==========================================================================

def pick(record: Dict[str, Any], *names: str) -> Any:
    """Read a column by any of its known spellings. Returns None when absent.

    Column headers are matched case-insensitively and stripped, because the
    ATP and WTA workbooks disagree on capitalisation from season to season and
    a KeyError on 'Best of' vs 'Best Of' would drop an entire year silently.
    """
    lookup = {str(k).strip().lower(): v for k, v in record.items()}
    for name in names:
        if name.lower() in lookup:
            value = lookup[name.lower()]
            if value is None:
                continue
            text = str(value).strip()
            if text and text.lower() not in ("nan", "nat", "none"):
                return value
    return None


def as_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    if not text:
        return None
    # pandas hands back '2026-08-24 00:00:00'; the stdlib path hands back a serial.
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        return match.group(0)
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", text)      # dd/mm/yyyy
    if match:
        day, month, year = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    return _excel_serial_to_date(text)


def as_int(value: Any) -> Optional[int]:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


class Match:
    __slots__ = ("winner", "loser", "surface", "date", "tour",
                 "tournament", "round_name", "wrank", "lrank", "comment")

    def __init__(self, **kwargs: Any) -> None:
        for key in self.__slots__:
            setattr(self, key, kwargs.get(key))


def parse_rows(records: Iterable[Dict[str, Any]], tour: str) -> Tuple[List[Match], Dict[str, int]]:
    """Turn workbook rows into Match objects. Returns (matches, reasons dropped)."""
    matches: List[Match] = []
    dropped: Dict[str, int] = {}

    def drop(reason: str) -> None:
        dropped[reason] = dropped.get(reason, 0) + 1

    for record in records:
        winner = pick(record, "Winner")
        loser = pick(record, "Loser")
        surface = pick(record, "Surface")
        date = as_date(pick(record, "Date"))

        if not winner or not loser:
            drop("no winner/loser")
            continue
        if not date:
            drop("unreadable date")
            continue

        surface_text = str(surface or "").strip().lower()
        if surface_text not in SURFACES:
            # Elo's own loader silently rewrites an unknown surface to "hard".
            # Counting it here means the summary shows how often that happened
            # instead of it disappearing into the ratings.
            drop(f"unknown surface {surface_text or '(blank)'!r} -> hard")
            surface_text = "hard"

        comment = str(pick(record, "Comment") or "").strip()
        if comment.lower().startswith("walkover"):
            drop("walkover")
            continue

        matches.append(Match(
            winner=str(winner).strip(), loser=str(loser).strip(),
            surface=surface_text, date=date, tour=tour,
            tournament=str(pick(record, "Tournament") or "").strip(),
            round_name=str(pick(record, "Round") or "").strip(),
            wrank=as_int(pick(record, "WRank")), lrank=as_int(pick(record, "LRank")),
            comment=comment,
        ))
    return matches, dropped


# ==========================================================================
# THE STORE
# ==========================================================================

def build_players(matches: List[Match]) -> Dict[str, Any]:
    players: Dict[str, Dict[str, Any]] = {}

    def slot(name: str, tour: str) -> Dict[str, Any]:
        if name not in players:
            players[name] = {
                "tour": tour, "matches": 0, "wins": 0, "losses": 0,
                "by_surface": {}, "first_seen": None, "last_seen": None,
                "best_rank": None, "last_rank": None,
                "data_tier": 1,
                "source": "tennis-data.co.uk season archives",
            }
        return players[name]

    for match in sorted(matches, key=lambda m: m.date):
        for name, won, rank in ((match.winner, True, match.wrank),
                                (match.loser, False, match.lrank)):
            record = slot(name, match.tour)
            record["matches"] += 1
            record["wins" if won else "losses"] += 1

            surface = record["by_surface"].setdefault(
                match.surface, {"matches": 0, "wins": 0})
            surface["matches"] += 1
            if won:
                surface["wins"] += 1

            if record["first_seen"] is None:
                record["first_seen"] = match.date
            record["last_seen"] = match.date
            if rank:
                record["last_rank"] = rank
                if record["best_rank"] is None or rank < record["best_rank"]:
                    record["best_rank"] = rank

    today = _dt.date.today().isoformat()
    for record in players.values():
        record["updated"] = today
        record["season"] = record["last_seen"][:4] if record["last_seen"] else None
        record["enough_matches"] = record["matches"] >= MIN_MATCHES
        for surface in record["by_surface"].values():
            surface["win_pct"] = round(surface["wins"] / surface["matches"], 3)
    return players


def write_atomic(path: Path, text: str) -> None:
    """Write through a temp file so an interrupted run cannot leave a half
    file that parses as valid and is missing half the season."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


# ==========================================================================
# MAIN
# ==========================================================================

def do_list(pattern: str) -> int:
    store_path = OUT_DIR / "players.json"
    if not store_path.exists():
        log(f"No store at {store_path}. Run the ingest first.")
        return 1
    store = json.loads(store_path.read_text(encoding="utf-8-sig"))
    needle = pattern.strip().lower()
    hits = {n: r for n, r in store.items() if needle in n.lower()} if needle else store
    if not hits:
        log(f"Nobody matching {pattern!r} in {len(store)} players.")
        return 1
    log(f"{len(hits)} match(es):\n")
    for name in sorted(hits):
        record = hits[name]
        surfaces = "  ".join(
            f"{s}:{d['wins']}-{d['matches'] - d['wins']}"
            for s, d in sorted(record["by_surface"].items()))
        flag = "" if record["enough_matches"] else f"   <- only {record['matches']} matches"
        log(f"  {name:<26} {record['tour'].upper():<4} "
            f"{record['wins']}-{record['losses']}  rank {record['last_rank'] or '?':<5} "
            f"{surfaces}{flag}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--years", nargs="+", type=int, default=[2025, 2026])
    parser.add_argument("--tours", nargs="+", default=["atp", "wta"],
                        choices=["atp", "wta"])
    parser.add_argument("--check", action="store_true",
                        help="Download and report, write nothing.")
    parser.add_argument("--list", metavar="NAME",
                        help="Search the existing store instead of ingesting.")
    args = parser.parse_args()

    if args.list is not None:
        sys.exit(do_list(args.list))

    rule()
    log(f"TENNIS INGEST  -  {', '.join(t.upper() for t in args.tours)}  "
        f"{', '.join(str(y) for y in args.years)}")
    rule()

    everything: List[Match] = []
    failures: List[str] = []

    for tour in args.tours:
        for year in sorted(args.years):
            label = f"{tour.upper()} {year}"
            blob, url, problems = None, "", []
            for candidate in archive_urls(tour, year):
                try:
                    blob, url = fetch(candidate), candidate
                    break
                except Exception as exc:                # noqa: BLE001
                    # Show the scheme and the status, not just "HTTPError".
                    scheme = candidate.split("://", 1)[0]
                    detail = getattr(exc, "msp_detail", None) or type(exc).__name__
                    problems.append(
                        f"{scheme}:{candidate.rsplit('/', 1)[-1]}: {detail}")
            if blob is None:
                log(f"  {label:<12} FAILED to download: {'; '.join(problems)}")
                failures.append(f"{label}")
                continue

            try:
                records = read_archive(blob, url)
                matches, dropped = parse_rows(records, tour)
            except Exception as exc:                    # noqa: BLE001
                log(f"  {label:<12} FAILED to parse: {type(exc).__name__}: {exc}")
                failures.append(f"{label} (parse)")
                continue

            span = (f"{min(m.date for m in matches)} .. {max(m.date for m in matches)}"
                    if matches else "no dated rows")
            log(f"  {label:<12} {len(matches):>5} matches   {span}")
            for reason, count in sorted(dropped.items()):
                log(f"               dropped {count:>4}  {reason}")
            everything.extend(matches)

    if not everything:
        rule()
        log("Nothing was ingested. Nothing was written -- the existing store, if")
        log("any, is untouched.")
        if failures:
            log("\nFailed: " + ", ".join(failures))
        rule()
        sys.exit(1)

    # Sequential ratings need chronological input. See the module docstring.
    everything.sort(key=lambda m: (m.date, m.tour, m.tournament, m.winner))

    players = build_players(everything)
    thin = sum(1 for r in players.values() if not r["enough_matches"])

    log("")
    rule("-")
    log(f"  {len(everything)} matches   {len(players)} players   "
        f"{min(m.date for m in everything)} .. {max(m.date for m in everything)}")
    log(f"  {thin} player(s) under {MIN_MATCHES} matches -- their Elo is mostly "
        f"the starting constant")
    by_surface: Dict[str, int] = {}
    for match in everything:
        by_surface[match.surface] = by_surface.get(match.surface, 0) + 1
    log("  by surface: " + ", ".join(f"{s} {n}" for s, n in sorted(by_surface.items())))
    rule("-")

    if args.check:
        log("\n--check: nothing was written.")
        return

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["winner_name", "loser_name", "surface", "tournament_date"])
    for match in everything:
        writer.writerow([match.winner, match.loser, match.surface, match.date])
    write_atomic(OUT_DIR / "matches.csv", buffer.getvalue())

    write_atomic(OUT_DIR / "players.json",
                 json.dumps(players, indent=2, ensure_ascii=False, sort_keys=True))

    # Kept so anything still pointing at the old filename keeps working.
    write_atomic(OUT_DIR / "atp_matches.csv", buffer.getvalue())

    log(f"\nWrote {OUT_DIR / 'matches.csv'}")
    log(f"Wrote {OUT_DIR / 'players.json'}")
    log(f"Wrote {OUT_DIR / 'atp_matches.csv'}  (same rows, legacy filename)")

    if failures:
        log("\nSeasons that did not load: " + ", ".join(failures))
        log("The store was built from the ones that did. Re-run to fill the gaps.")

    log("\nNext:")
    log("    venv/Scripts/python.exe ingest_tennis.py --list Alcaraz")
    log("    venv/Scripts/python.exe run_tennis.py --match \"Alcaraz C. vs Sinner J.\"")


if __name__ == "__main__":
    main()
