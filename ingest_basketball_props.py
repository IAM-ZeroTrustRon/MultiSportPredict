"""NBA player-game ingestion for prop research.

Source: ESPN public box scores. One request per finished game, chosen because it is
the only permitted source verified to return, together, starter status, a
did-not-play flag with a reason, minutes, PTS/REB/AST and overtime periods. A
player game log alone was rejected for this job: it omits non-appearances and
carries no starter flag, so DNPs and production cannot be told apart.

RealGM is deliberately not scraped. No verified permission for automated retrieval
was established, so it stays a manual research reference and the ingested rows
never claim it as a source.

Rows are append-only research data in ``data/basketball_props``. No second
database is created and nothing here writes a team-pick prediction.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import Counter
from pathlib import Path

from sports_feed import EASTERN, ROOT, atomic_json, fetch_json, today

COMPETITION = "NBA"
SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date}"
SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={event}"
STORE = ROOT / "data/basketball_props/player_games.json"
REGISTRY = ROOT / "data/basketball_props/registry.json"
MIN_COMPLETED_GAMES = 4


def to_float(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text in {"--", "-", "N/A"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def date_range(start, end):
    current = dt.date.fromisoformat(start)
    last = dt.date.fromisoformat(end)
    while current <= last:
        yield current.isoformat()
        current += dt.timedelta(days=1)


def _competitors(competition):
    return competition.get("competitors") or []


def _eastern_date(stamp):
    if not stamp:
        return None
    parsed = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return parsed.astimezone(EASTERN).date().isoformat()


def season_label_for(season_year):
    """Derive NBA's cross-year label when the feed omits it."""
    if not isinstance(season_year, int):
        return None
    return f"{season_year - 1}-{str(season_year)[2:]}"


def _periods(payload):
    """Periods played, derived from the linescore so overtime is measured not assumed."""
    header = payload.get("header") or {}
    competition = (header.get("competitions") or [{}])[0]
    periods = 0
    for side in _competitors(competition):
        periods = max(periods, len(side.get("linescores") or []))
    return periods


def parse_summary(event, payload, retrieved_at):
    """Extract one row per listed player, preserving DNPs as their own status."""
    header = payload.get("header") or {}
    competition = (header.get("competitions") or [{}])[0]
    sides = _competitors(competition)
    home_id = next((str(s.get("team", {}).get("id")) for s in sides if s.get("homeAway") == "home"), None)
    away_id = next((str(s.get("team", {}).get("id")) for s in sides if s.get("homeAway") == "away"), None)
    names = {str(s.get("team", {}).get("id")): s.get("team", {}).get("displayName") for s in sides}
    stamp = event.get("date") or competition.get("date")
    game_date = _eastern_date(stamp)
    # A calendar year is not a season. ESPN's season.year is the year the season
    # ends, so April 2026 games are season 2026 while October 2026 games are 2027.
    season = (payload.get("header") or {}).get("season") or {}
    season_year = season.get("year")
    season_type = season.get("type")
    season_label = season.get("displayName") or season_label_for(season_year)
    periods = _periods(payload)
    overtime = periods > 4
    source = SUMMARY.format(event=event.get("id"))
    rows = []

    for block in (payload.get("boxscore") or {}).get("players") or []:
        team = block.get("team") or {}
        team_id = str(team.get("id"))
        team_name = team.get("displayName") or names.get(team_id)
        opponent_id = away_id if team_id == home_id else home_id
        statistics = block.get("statistics") or []
        if not statistics or not team_id:
            continue
        block_stats = statistics[0]
        columns = [str(n).upper() for n in (block_stats.get("names") or [])]
        index = {name: position for position, name in enumerate(columns)}

        def cell(values, name):
            position = index.get(name)
            if position is None or position >= len(values):
                return None
            return values[position]

        for entry in block_stats.get("athletes") or []:
            athlete = entry.get("athlete") or {}
            if not athlete.get("id"):
                continue
            values = entry.get("stats") or []
            did_not_play = bool(entry.get("didNotPlay"))
            minutes = None if did_not_play else to_float(cell(values, "MIN"))
            rows.append({
                "player_id": str(athlete.get("id")),
                "player_name": athlete.get("displayName"),
                "team_id": team_id,
                "team": team_name,
                "home": team_id == home_id,
                "opponent_id": opponent_id,
                "opponent": names.get(opponent_id),
                "event_id": str(event.get("id")),
                "game_date": game_date,
                "game_datetime": stamp,
                "season": season_year,
                "season_type": season_type,
                "season_label": season_label,
                "competition": COMPETITION,
                "status": "dnp" if did_not_play else "played",
                "starter": bool(entry.get("starter")),
                "did_not_play": did_not_play,
                "reason": (entry.get("reason") or None),
                "minutes": minutes if not did_not_play else 0.0,
                "points": None if did_not_play else to_float(cell(values, "PTS")),
                "rebounds": None if did_not_play else to_float(cell(values, "REB")),
                "assists": None if did_not_play else to_float(cell(values, "AST")),
                "overtime": overtime,
                "periods": periods,
                "source": source,
                "retrieved_at": retrieved_at,
            })
    return rows


def scoreboard(date):
    # The scoreboard endpoint takes a compact YYYYMMDD date, not an ISO string.
    payload = fetch_json(SCOREBOARD.format(date=str(date).replace("-", "")), cache_hours=12)
    return payload.get("events") or []


def finished_events(date):
    events = []
    for event in scoreboard(date):
        competition = (event.get("competitions") or [{}])[0]
        state = (((competition.get("status") or {}).get("type") or {}).get("name") or "")
        if state in {"STATUS_FINAL", "STATUS_FULL_TIME"}:
            events.append(event)
    return events


def load_store():
    if not STORE.exists():
        return {"competition": COMPETITION, "games": []}
    return json.loads(STORE.read_text(encoding="utf-8-sig"))


def ingest(start, end, cache_hours=24, refresh=False, max_games=None, verbose=True):
    existing = load_store()
    seen = {str(r.get("event_id")) for r in existing.get("games") or []}
    retrieved_at = dt.datetime.now(dt.timezone.utc).isoformat()
    rows, events_done, skipped = [], [], 0
    dates = list(date_range(start, end))
    for date in dates:
        for event in finished_events(date):
            event_id = str(event.get("id"))
            if event_id in seen and not refresh:
                skipped += 1
                continue
            if max_games is not None and len(events_done) >= max_games:
                break
            payload = fetch_json(SUMMARY.format(event=event_id), cache_hours=cache_hours)
            parsed = parse_summary(event, payload, retrieved_at)
            if not parsed:
                continue
            rows.extend(parsed)
            events_done.append(event_id)
            if verbose:
                print(f"  {date} {event.get('name')}: {len(parsed)} player rows")
        if max_games is not None and len(events_done) >= max_games:
            break

    merged = {str(r.get("player_id")) + "|" + str(r.get("event_id")): r
              for r in (existing.get("games") or []) if r.get("event_id") not in events_done}
    for row in rows:
        merged[str(row["player_id"]) + "|" + str(row["event_id"])] = row
    games = sorted(merged.values(), key=lambda r: (str(r.get("game_date")), str(r.get("event_id")),
                                                   str(r.get("player_id"))))

    completion = {
        "competition": COMPETITION,
        "source": "ESPN public box scores",
        "source_url_template": SUMMARY,
        "updated": today(),
        "retrieved_at": retrieved_at,
        "games": games,
    }
    completed_events = {r["event_id"] for r in games if r.get("status") == "played"}
    if len(completed_events) < MIN_COMPLETED_GAMES and not refresh:
        raise ValueError(f"Only {len(completed_events)} completed game(s) available; existing store retained")

    registry = build_registry(games, retrieved_at)
    atomic_json(STORE, completion)
    atomic_json(REGISTRY, registry)

    reasons = Counter((r.get("reason") or "UNSPECIFIED").upper()
                      for r in games if r.get("status") == "dnp")
    summary = {
        "events_ingested": len(events_done),
        "events_already_stored": skipped,
        "player_rows": len(games),
        "events_total": len(completed_events),
        "players": len(registry["players"]),
        "teams": len(registry["teams"]),
        "dnp_rows": sum(1 for r in games if r.get("status") == "dnp"),
        "rows_without_verified_season": sum(1 for r in games if r.get("season") is None),
        "seasons": sorted({r.get("season_label") for r in games if r.get("season_label")}),
        "dnp_reasons": dict(reasons),
        "date_range": [games[0]["game_date"], games[-1]["game_date"]] if games else None,
        "store": str(STORE.relative_to(ROOT)),
        "registry": str(REGISTRY.relative_to(ROOT)),
    }
    if verbose:
        print(json.dumps(summary, indent=2))
    return summary


def build_registry(rows, retrieved_at):
    players, teams = {}, {}
    for row in rows:
        teams[str(row["team_id"])] = row.get("team")
        player = players.setdefault(str(row["player_id"]), {
            "name": row.get("player_name"), "team_ids": set(), "appearances": 0})
        player["team_ids"].add(str(row["team_id"]))
        if row.get("status") == "played":
            player["appearances"] += 1
    for player in players.values():
        player["team_ids"] = sorted(player["team_ids"])
    return {"competition": COMPETITION, "retrieved_at": retrieved_at,
            "teams": teams, "players": players}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="start", default=None, help="First date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="end", default=None, help="Last date (default today)")
    parser.add_argument("--days", type=int, default=21, help="Look-back window if --from is omitted")
    parser.add_argument("--cache-hours", type=float, default=24)
    parser.add_argument("--refresh", action="store_true", help="Re-fetch games already stored")
    parser.add_argument("--max-games", type=int, default=None)
    args = parser.parse_args(argv)
    end = args.end or today()
    start = args.start or (dt.date.fromisoformat(end) - dt.timedelta(days=args.days)).isoformat()
    ingest(start, end, args.cache_hours, args.refresh, args.max_games)


if __name__ == "__main__":
    main()
