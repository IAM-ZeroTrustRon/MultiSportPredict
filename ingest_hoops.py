"""Fetch EuroLeague team efficiencies from the official API wrapper.

The installed ``euroleague-api`` exposes ``get_team_stats_single_season(endpoint,
season, phase_type_code=...)`` and returns per-game team totals, not the
``OffensiveRating``/``DefensiveRating``/``Possessions`` columns an older version
returned. This adapter therefore derives the three metrics the engine needs from
measured totals and states the method in the stored file:

    possessions  ~= FGA + 0.44 * FTA - ORB + TOV      (per game)
    pace         =  possessions per 40 minutes        (EuroLeague games are 40)
    ORtg         =  points scored  / possessions * 100
    DRtg         =  points allowed  / possessions * 100

Every record keeps its season, phase, games-played sample and retrieval time so a
thin sample is visible rather than hidden. If the official feed is unreachable or
returns no rows, this **fails** instead of writing a plausible default.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path
from typing import Any

OUTPUT_PATH = Path("data/euroleague_stats.json")
COMPETITION = "E"
SOURCE = "euroleague-api (official EuroLeague statistics)"
FTA_POSSESSION_WEIGHT = 0.44


def _number(row, key):
    value = row.get(key)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _team_records(frame, season, phase, retrieved_at):
    records = {}
    for _, row in frame.iterrows():
        name = str(row.get("team.name") or "").strip()
        if not name:
            continue
        games = _number(row, "gamesPlayed")
        points = _number(row, "pointsScored")
        two_att = _number(row, "twoPointersAttempted")
        three_att = _number(row, "threePointersAttempted")
        ft_att = _number(row, "freeThrowsAttempted")
        off_reb = _number(row, "offensiveRebounds")
        turnovers = _number(row, "turnovers")
        if None in (games, points, two_att, three_att, ft_att, off_reb, turnovers):
            continue
        if games <= 0:
            continue
        field_goals_attempted = two_att + three_att
        possessions = field_goals_attempted + FTA_POSSESSION_WEIGHT * ft_att - off_reb + turnovers
        if not math.isfinite(possessions) or possessions <= 0:
            continue
        records[name] = {
            "games": games,
            "points_for": points,
            "possessions": round(possessions, 2),
            "season": season,
            "phase": phase,
            "league": "EuroLeague",
            "source": SOURCE,
            "updated": retrieved_at,
        }
    return records


def fetch_and_store_euroleague(season: int | None = None, output: Path = OUTPUT_PATH,
                               phase: str = "RS") -> dict[str, Any]:
    try:
        from euroleague_api.team_stats import TeamStats
    except ImportError as exc:
        raise RuntimeError("euroleague-api is required: pip install euroleague-api") from exc

    season = season or dt.datetime.now(dt.timezone.utc).year
    print(f"[*] Fetching official EuroLeague team totals for season {season} ({phase})...")
    stats = TeamStats(COMPETITION)
    traditional = stats.get_team_stats_single_season("traditional", season, phase_type_code=phase)
    opponents = stats.get_team_stats_single_season("opponentsTraditional", season, phase_type_code=phase)
    if traditional is None or traditional.empty:
        raise RuntimeError(f"EuroLeague API returned no team totals for season {season}")

    retrieved_at = dt.datetime.now(dt.timezone.utc).isoformat()
    records = _team_records(traditional, season, phase, retrieved_at)
    allowed = {}
    if opponents is not None and not opponents.empty:
        for _, row in opponents.iterrows():
            name = str(row.get("team.name") or "").strip()
            value = _number(row, "pointsScored")
            if name and value is not None:
                allowed[name] = value

    missing_against = [name for name in records if name not in allowed]
    if missing_against:
        raise RuntimeError("No opponent points for: " + ", ".join(sorted(missing_against)[:5]))

    for name, record in records.items():
        possessions = record["possessions"]
        record["points_against"] = allowed[name]
        record["ortg"] = round(record["points_for"] / possessions * 100, 2)
        record["drtg"] = round(record["points_against"] / possessions * 100, 2)
        record["pace"] = round(possessions, 2)

    if not records:
        raise RuntimeError("EuroLeague API returned no complete team metrics")

    baseline = {
        "pace": round(sum(r["pace"] for r in records.values()) / len(records), 2),
        "ortg": round(sum(r["ortg"] for r in records.values()) / len(records), 2),
        "drtg": round(sum(r["drtg"] for r in records.values()) / len(records), 2),
        "q1_ratio": 0.245,
        "ht_ratio": 0.495,
    }
    document = {
        "_comment": ("Official EuroLeague regular-season team totals. ORtg/DRtg/pace are "
                     "derived from measured box-score totals; see _meta.method."),
        "_meta": {
            "season": season,
            "phase": phase,
            "source": SOURCE,
            "retrieved_at": retrieved_at,
            "method": ("possessions = FGA + 0.44*FTA - ORB + TOV; pace = possessions per 40 "
                       "minutes; ORtg/DRtg = points / possessions * 100"),
            "games_played": {name: record["games"] for name, record in records.items()},
            "warning": "A small games-played sample is a small sample, not a season average.",
        },
        "_league_baseline": baseline,
    }
    for name, record in sorted(records.items()):
        document[name] = record

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, output)
    print(f"[+] Saved {len(records)} EuroLeague teams to {output} "
          f"(season {season}, {phase}, {min(r['games'] for r in records.values()):.0f}-"
          f"{max(r['games'] for r in records.values()):.0f} games)")
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=None,
                        help="Season start year (2026 for 2026-27); defaults to the current UTC year")
    parser.add_argument("--phase", default="RS", choices=["RS", "PO", "FF"])
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    fetch_and_store_euroleague(args.season, args.output, args.phase)


if __name__ == "__main__":
    main()
