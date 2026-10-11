"""Preserve soccer samples separately by competition and starting season."""
from __future__ import annotations
import re

BUCKET = "_competition_records"
ALIASES = {"epl": "premier league", "eng-premier league": "premier league",
           "esp-la liga": "la liga", "ger-bundesliga": "bundesliga",
           "ita-serie a": "serie a", "fra-ligue 1": "ligue 1",
           "french ligue 1": "ligue 1", "german bundesliga": "bundesliga",
           "spanish la liga": "la liga",
           "ned-eredivisie": "eredivisie", "ned-eerste divisie": "eerste divisie"}


def league_key(value):
    text = " ".join(str(value or "").strip().lower().split())
    return ALIASES.get(text, text)


def season_key(value):
    if isinstance(value, dict):
        for key in ("year", "startDate", "displayName"):
            if value.get(key) is not None:
                return season_key(value[key])
    match = re.search(r"\b(19\d{2}|20\d{2})", str(value or ""))
    return match.group(1) if match else str(value or "unknown")


def merge_records(existing, incoming):
    result = dict(existing)
    bucket = {league: {season: dict(teams) for season, teams in seasons.items()}
              for league, seasons in existing.get(BUCKET, {}).items()}
    # Migrate legacy samples before updating, so overwritten competitions survive.
    for source in (existing, incoming):
        for team, record in source.items():
            if team.startswith("_") or not isinstance(record, dict):
                continue
            league = league_key(record.get("league"))
            season = season_key(record.get("season"))
            bucket.setdefault(league, {}).setdefault(season, {})[team] = dict(record)
    for team, record in incoming.items():
        if team.startswith("_") or not isinstance(record, dict):
            continue
        old = result.get(team)
        if not isinstance(old, dict):
            result[team] = record
            continue
        same_league = league_key(old.get("league")) == league_key(record.get("league"))
        newer = season_key(record.get("season")) >= season_key(old.get("season"))
        # Keep domestic primary samples when continental standings arrive.
        old_europe = league_key(old.get("league")).startswith("uefa ")
        new_europe = league_key(record.get("league")).startswith("uefa ")
        if (same_league and newer) or (old_europe and not new_europe):
            result[team] = record
    result[BUCKET] = bucket
    return result


def competition_view(store, league=None):
    if not league:
        return {name: dict(record) for name, record in store.items()
                if not name.startswith("_") and isinstance(record, dict)}
    wanted = league_key(league)
    candidates = {}
    for name, record in store.items():
        if not name.startswith("_") and isinstance(record, dict) and league_key(record.get("league")) == wanted:
            candidates.setdefault(name, {})[season_key(record.get("season"))] = record
    for season, teams in store.get(BUCKET, {}).get(wanted, {}).items():
        for name, record in teams.items():
            candidates.setdefault(name, {})[season] = record
    return {name: dict(seasons[max(seasons)]) for name, seasons in candidates.items()}


def audit_records(store):
    # Audit one latest sample per team/competition, without counting legacy aliases twice.
    leagues = {league_key(r.get("league")) for n, r in store.items()
               if not n.startswith("_") and isinstance(r, dict)}
    leagues.update(store.get(BUCKET, {}))
    return {f"{name} [{record.get('league', league)}]": record
            for league in sorted(leagues)
            for name, record in competition_view(store, league).items()}
