#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
data_guard.py - Refuse to predict from data that is the wrong age

WHY THIS EXISTS
    A season-folder sorting bug quietly loaded the 1999/2000 Premier League and
    Eredivisie into the store. The download worked, the parse worked, the run
    reported success, and two predictions were produced from 25-year-old squads.
    The only symptom was Wimbledon appearing in a team list -- something a human
    had to notice by eye.

    Every record already carries `season` and `updated`. Nothing was reading
    them. This does.

USE AS A COMMAND
    python data_guard.py                 audit every store
    python data_guard.py --sport soccer
    python data_guard.py --strict        exit 1 if anything is stale

USE FROM A RUNNER
    from data_guard import check_records, describe

    problems = check_records({"Liverpool": rec, ...}, "soccer")
    if any(p.severity == "error" for p in problems):
        ... refuse to run

DESIGN
    An old season is an ERROR, not a warning. Stale-but-recent data is a
    warning, because mid-week numbers being two days old is normal and blocking
    on it would train you to ignore the guard. The distinction is the point:
    warnings you can dismiss, errors you cannot.

    NFL deliberately stores the PRIOR season as an early-season prior, so one
    season back is expected there and is reported as information, not a fault.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
TODAY = _dt.date.today()

STORES: Dict[str, List[Path]] = {
    "soccer":     [DATA / "soccer_stats.json", DATA / "team_stats" / "soccer_stats.json"],
    "baseball":   [DATA / "baseball_stats.json"],
    "nfl":        [DATA / "nfl_stats.json"],
    "basketball": [DATA / "euroleague_stats.json", DATA / "basketball_stats.json"],
    "tennis":     [DATA / "tennis" / "players.json"],
}

# How old the `updated` stamp may get before it is worth mentioning.
MAX_AGE_DAYS: Dict[str, int] = {
    "soccer": 10, "baseball": 3, "basketball": 10, "nfl": 14, "tennis": 10,
}

# Fewest games before a team's numbers mean anything. Below this the record is
# blocked: a 1-game sample produced 6-goal projections and 54% "edges".
MIN_GAMES: Dict[str, int] = {
    "soccer": 5, "baseball": 15, "basketball": 5, "nfl": 4,
    # Mirrors ingest_tennis.MIN_MATCHES -- if the two disagree, the ingest
    # marks a player enough_matches=True that the guard then blocks.
    "tennis": 8,
}

# Tennis records are per PLAYER, not per team, and were written by a different
# ingest with its own field names: the sample count is `matches`, not `games`,
# and the grouping is `tour` (atp/wta), not `league`. Without these the guard
# loads the store, finds neither field, and reports every player clean -- the
# silent pass this module exists to prevent.
COUNT_FIELD: Dict[str, str] = {"tennis": "matches"}
GROUP_FIELD: Dict[str, str] = {"tennis": "tour"}
UNIT: Dict[str, str] = {"tennis": "players"}

# Sports whose store legitimately holds a completed prior season.
# EuroLeague runs October-May, so through the summer the most recent real data
# IS last season -- flagging that as an error would be crying wolf. NFL stores
# the prior season deliberately, as the early-season prior.
PRIOR_SEASON_IS_FINE = {"nfl", "basketball"}


class Problem:
    def __init__(self, severity: str, team: str, message: str) -> None:
        self.severity = severity        # "error" | "warn" | "info"
        self.team = team
        self.message = message

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.severity} {self.team}: {self.message}>"


# ==========================================================================
# SEASON HANDLING
# ==========================================================================

def parse_season(value: Any) -> Optional[int]:
    """Return the season's START year from any of the shapes in these stores.

    Seen in the wild: 2026, "2026", "2026/2027", "2026-27", "2025-26".
    """
    if value is None:
        return None
    if isinstance(value, dict):
        # ESPN ingests write season as {"year": 2026, "startDate": ...,
        # "displayName": "2026-27 French Ligue 1"}. Stringifying that dict
        # matched nothing, so every ESPN-sourced record was reported "no
        # season recorded" and the wrong-season ERROR this module exists to
        # raise could never fire for them -- the guard was blind to the data
        # shape it now receives most often. Unpack a year-bearing field and
        # re-parse it, so ESPN records enjoy the same season check as the
        # string-store records.
        for key in ("year", "startDate", "date", "name", "displayName", "season"):
            nested = value.get(key)
            if nested is not None:
                parsed = parse_season(nested)
                if parsed is not None:
                    return parsed
        return None
    if isinstance(value, (int, float)):
        year = int(value)
        return year if 1900 <= year <= 2100 else None
    text = str(value).strip()
    if not text:
        return None
    match = re.match(r"^(\d{4})", text)
    if match:
        year = int(match.group(1))
        return year if 1900 <= year <= 2100 else None
    return None


def expected_season(sport: str, today: Optional[_dt.date] = None) -> int:
    """The season a fresh ingest should be returning right now."""
    today = today or TODAY
    if sport == "soccer":
        # European calendar: a season starting in August is labelled by its
        # starting year, so before July we are still in last year's season.
        return today.year if today.month >= 7 else today.year - 1
    if sport == "basketball":
        # EuroLeague tips off in October, not August.
        return today.year if today.month >= 10 else today.year - 1
    if sport == "nfl":
        return today.year if today.month >= 8 else today.year - 1
    # Baseball and tennis both run inside a single calendar year, so the
    # season label is just the year. Tennis is deliberately NOT in
    # PRIOR_SEASON_IS_FINE: the tour runs January-November, so a player whose
    # newest record is last season has not been seen in months and their form
    # is not what you are about to bet on.
    return today.year


def days_since(stamp: Any) -> Optional[int]:
    if not stamp:
        return None
    text = str(stamp)[:10]
    try:
        return (TODAY - _dt.date.fromisoformat(text)).days
    except ValueError:
        return None


# ==========================================================================
# CHECKS
# ==========================================================================

def check_records(records: Dict[str, Dict[str, Any]], sport: str,
                  today: Optional[_dt.date] = None) -> List[Problem]:
    """Inspect a team->record mapping. Returns every problem found."""
    problems: List[Problem] = []
    target = expected_season(sport, today)
    limit = MAX_AGE_DAYS.get(sport, 14)

    for team, record in records.items():
        if team.startswith("_") or not isinstance(record, dict):
            continue

        season = parse_season(record.get("season"))
        if season is None:
            problems.append(Problem(
                "warn", team, "no season recorded -- age cannot be verified"))
        else:
            behind = target - season
            if behind >= 2:
                problems.append(Problem(
                    "error", team,
                    f"season {season} is {behind} seasons behind {target}"))
            elif behind == 1:
                severity = "info" if sport in PRIOR_SEASON_IS_FINE else "error"
                note = ("prior season, expected for early-season priors"
                        if severity == "info"
                        else f"season {season} is last season, not {target}")
                problems.append(Problem(severity, team, note))
            elif behind < 0:
                problems.append(Problem(
                    "warn", team, f"season {season} is ahead of {target}"))

        games = record.get(COUNT_FIELD.get(sport, "games"))
        floor = MIN_GAMES.get(sport)
        if floor is not None and isinstance(games, (int, float)):
            if games < floor:
                problems.append(Problem(
                    "error", team,
                    f"only {int(games)} game(s) played, need {floor} "
                    f"before the numbers mean anything"))

        age = days_since(record.get("updated"))
        if age is None:
            problems.append(Problem("warn", team, "no updated stamp"))
        elif age > limit:
            problems.append(Problem(
                "warn", team, f"last updated {age} days ago (limit {limit})"))

    return problems


def describe(problems: Iterable[Problem], limit: int = 6) -> str:
    """A one-paragraph summary for a runner to print."""
    problems = list(problems)
    errors = [p for p in problems if p.severity == "error"]
    warnings = [p for p in problems if p.severity == "warn"]
    if not errors and not warnings:
        return "data age OK"
    lines: List[str] = []
    if errors:
        # This used to say "wrong season" for every error, including the
        # too-few-games ones -- which sends you looking for a stale download
        # when the real answer is that the season is three weeks old.
        kinds = {("season" if "season" in p.message else
                  "sample" if "game" in p.message else "other") for p in errors}
        label = ("the wrong season" if kinds == {"season"} else
                 "too thin to use" if kinds == {"sample"} else "unusable")
        lines.append(f"{len(errors)} record(s) are {label}:")
        for problem in errors[:limit]:
            lines.append(f"    {problem.team}: {problem.message}")
        if len(errors) > limit:
            lines.append(f"    ... and {len(errors) - limit} more")
    if warnings:
        shown = warnings[:limit]
        lines.append(f"{len(warnings)} stale/unverifiable record(s):")
        for problem in shown:
            lines.append(f"    {problem.team}: {problem.message}")
        if len(warnings) > limit:
            lines.append(f"    ... and {len(warnings) - limit} more")
    return "\n".join(lines)


def guard_teams(records: Dict[str, Dict[str, Any]], sport: str,
                teams: Iterable[str]) -> Tuple[bool, str]:
    """Check only the clubs about to be used. Returns (safe, message).

    Scoped to the teams in play on purpose: one stale club in an unrelated
    league should not block a slate that does not touch it.
    """
    wanted = {t for t in teams if t}
    subset = {name: record for name, record in records.items() if name in wanted}
    if not subset:
        return True, "no records to check"
    problems = check_records(subset, sport)
    safe = not any(p.severity == "error" for p in problems)
    return safe, describe(problems)


# ==========================================================================
# CLI
# ==========================================================================

def load_store(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def audit(sport: str) -> Tuple[int, int, int, int, int]:
    total = errors = warnings = 0
    season_errors = sample_errors = 0
    for path in STORES.get(sport, []):
        store = load_store(path)
        records = {k: v for k, v in store.items()
                   if not k.startswith("_") and isinstance(v, dict)}
        if not records:
            print(f"  {path.name:<32} (missing or empty)")
            continue

        problems = check_records(records, sport)
        group_key = GROUP_FIELD.get(sport, "league")
        by_league: Dict[str, List[str]] = {}
        for team, record in records.items():
            by_league.setdefault(str(record.get(group_key, "?")), []).append(team)

        errored = {p.team for p in problems if p.severity == "error"}
        warned = {p.team for p in problems if p.severity == "warn"}
        total += len(records)
        errors += len(errored)
        warnings += len(warned)
        for team in errored:
            msgs = [p.message for p in problems
                    if p.severity == "error" and p.team == team]
            if any("season" in m for m in msgs):
                season_errors += 1
            if any("game" in m for m in msgs):
                sample_errors += 1

        print(f"  {path.name}")
        for league, members in sorted(by_league.items()):
            seasons = sorted({str(records[t].get("season", "?")) for t in members})
            stamps = sorted({str(records[t].get("updated", "?"))[:10] for t in members})
            bad = len([t for t in members if t in errored])
            reasons = {("season" if "season" in p.message else "sample")
                       for p in problems
                       if p.severity == "error" and p.team in members}
            flag = (f"  <-- {bad} " + ("WRONG SEASON" if reasons == {"season"}
                                       else "TOO FEW GAMES" if reasons == {"sample"}
                                       else "UNUSABLE")) if bad else ""
            print(f"    {league:<24} {len(members):>3} {UNIT.get(sport, 'teams'):<7} "
                  f"season {','.join(seasons[:3]):<12} updated {stamps[-1]}{flag}")

        for problem in [p for p in problems if p.severity == "error"][:4]:
            print(f"      ERROR {problem.team}: {problem.message}")
    return total, errors, warnings, season_errors, sample_errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sport", choices=sorted(STORES), default=None)
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 if any record is the wrong season.")
    args = parser.parse_args()

    sports = [args.sport] if args.sport else sorted(STORES)
    print("=" * 78)
    print(f"DATA AGE AUDIT  -  {TODAY}")
    print("=" * 78)

    total = errors = warnings = season_errors = sample_errors = 0
    for sport in sports:
        print(f"\n[{sport}]  expecting season {expected_season(sport)}"
              + ("  (prior season is acceptable here)"
                 if sport in PRIOR_SEASON_IS_FINE else ""))
        counts = audit(sport)
        total += counts[0]
        errors += counts[1]
        warnings += counts[2]
        season_errors += counts[3]
        sample_errors += counts[4]

    print("\n" + "=" * 78)
    print(f"{total} record(s): {errors} unusable "
          f"({season_errors} wrong season, {sample_errors} too few games), "
          f"{warnings} stale or unverifiable")
    if season_errors:
        print("\nWrong-season records will produce confident predictions from data")
        print("that does not describe the teams playing. Re-ingest before running a")
        print("slate that touches them.")
    if sample_errors:
        print("\nToo-few-games teams are on a correct season but their record is")
        print("too thin to mean anything yet. Re-ingest once more games are played")
        print("and re-run the slate - the guard refuses these on purpose.")
    print("=" * 78)
    sys.exit(1 if (args.strict and errors) else 0)


if __name__ == "__main__":
    main()
