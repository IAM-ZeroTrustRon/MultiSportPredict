"""Public NHL fixtures and published MoneyPuck downloads with explicit provenance."""
import csv
import datetime as dt
import hashlib
import json
import os
import time
from pathlib import Path

import pandas as pd
import numpy as np
import requests

from sports_feed import ROOT, EASTERN, atomic_json

NHL = "https://api-web.nhle.com/v1"
MP = "https://moneypuck.com/moneypuck/playerData"
CACHE = ROOT / "data/cache/nhl"
TEAM_COLUMNS = ["team", "season", "gameId", "gameDate", "situation", "home_or_away",
                "xGoalsFor", "xGoalsAgainst", "iceTime", "shotAttemptsFor", "shotAttemptsAgainst",
                "highDangerShotsFor", "highDangerShotsAgainst", "shotsOnGoalAgainst", "goalsAgainst",
                "goalsFor"]
# Even strength plus the two special-teams rows MoneyPuck publishes per team
# game. 5on4 is the team's power play; 4on5 is its penalty kill.
SITUATIONS = {"5on5": "advanced_5on5", "5on4": "pp", "4on5": "pk"}


def utcnow():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def stamp(value):
    result = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("NHL timestamps must include a timezone")
    return result


def get_json(url, hours=6):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (hashlib.sha256(url.encode()).hexdigest()+".json")
    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        if 0 <= (stamp(utcnow())-stamp(cached["retrieved_utc"])).total_seconds() < hours*3600:
            return cached["data"], cached["retrieved_utc"]
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=(10, 45))
            response.raise_for_status()
            payload = response.json()
            break
        except (requests.RequestException, ValueError):
            if attempt==2:raise
            time.sleep(1+attempt)
    received = utcnow()
    atomic_json(path, dict(source_url=url, retrieved_utc=received, data=payload))
    return payload, received


def download_csv(url, name, required, hours=20):
    """Validate before promotion; a failed transfer cannot replace the good file."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / name
    manifest = path.with_suffix(".manifest.json")
    if path.exists() and manifest.exists():
        meta = json.loads(manifest.read_text(encoding="utf-8"))
        if 0 <= (stamp(utcnow())-stamp(meta["retrieved_utc"])).total_seconds() < hours*3600:
            return path, meta
    temporary = path.with_suffix(".download")
    try:
        digest = hashlib.sha256()
        with requests.get(url, stream=True, timeout=(10, 90)) as response:
            response.raise_for_status()
            with temporary.open("wb") as handle:
                for chunk in response.iter_content(1024*1024):
                    if chunk:
                        handle.write(chunk); digest.update(chunk)
            upstream = response.headers.get("Last-Modified")
        with temporary.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not set(required).issubset(reader.fieldnames or []):
                raise ValueError("MoneyPuck CSV schema changed; required columns absent")
            if next(reader, None) is None:
                raise ValueError("MoneyPuck CSV is empty; previous cache retained")
        meta = dict(source_url=url, retrieved_utc=utcnow(), upstream_last_modified=upstream,
                    sha256=digest.hexdigest(), attribution="MoneyPuck.com; non-commercial published download",
                    schema=list(required))
        # Never claim a failed cache refresh is current.
        os.replace(temporary, path)
        atomic_json(manifest, meta)
        return path, meta
    finally:
        temporary.unlink(missing_ok=True)


def parse_game(raw, retrieved, source):
    if raw.get("gameType") not in (2, 3):
        return None
    start = stamp(raw["startTimeUTC"])
    year = str(raw["season"])
    if len(year) != 8 or int(year[4:]) != int(year[:4])+1:
        raise ValueError("Invalid NHL season ID")
    state = raw["gameState"]
    if raw.get('gameScheduleState') not in (None,'OK') and state not in {'OFF','FINAL'}:
        state=raw['gameScheduleState']
    completed = state in {"OFF", "FINAL"}
    result = dict(game_id=str(raw["id"]), league="NHL", season=int(year),
                  season_start=int(year[:4]), season_type=raw["gameType"],
                  date=start.astimezone(EASTERN).date().isoformat(), start_time=start.isoformat(),
                  completed=completed, status=state, source=source, retrieved_utc=retrieved,
                  neutral_site=bool(raw.get("neutralSite")),
                  final_period=raw.get("gameOutcome", {}).get("lastPeriodType"))
    for side in ("home", "away"):
        team = raw[side+"Team"]
        result[side+"_id"] = str(team["id"])
        result[side+"_abbrev"] = team["abbrev"]
        result[side+"_team"] = team["placeName"]["default"]+" "+team["commonName"]["default"]
        value = team.get("score")
        if completed and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            raise ValueError("Invalid completed NHL score")
        result[side+"_score"] = value if completed else None
    if completed:
        h, a = result["home_score"], result["away_score"]
        period = result["final_period"]
        if period not in {"REG", "OT", "SO"} or h == a:
            raise ValueError("Completed NHL game lacks a verified finishing phase")
        if period in {"OT", "SO"}:
            if abs(h-a) != 1 or (period == "SO" and raw["gameType"] == 3):
                raise ValueError("Impossible NHL extra-time result")
            # Sudden-death OT and official shootout scoring add exactly one
            # winning goal to the tied regulation score (NHL Rule 84).
            result["regulation_home"] = result["regulation_away"] = min(h, a)
            result["regulation_basis"] = "Verified OT/SO finish; official winning-goal convention"
        else:
            result.update(regulation_home=h, regulation_away=a, regulation_basis="Official regulation finish")
    return result


def schedule(day):
    dt.date.fromisoformat(day)
    url = NHL+"/schedule/"+day
    payload, retrieved = get_json(url, .1)
    games = [parse_game(g, retrieved, url) for week in payload.get("gameWeek", []) for g in week.get("games", [])]
    return [g for g in games if g]


def team_history(abbrev, season):
    url = f"{NHL}/club-schedule-season/{abbrev}/{season}{season+1}"
    data, retrieved = get_json(url, 12)
    return [row for g in data.get("games", []) if (row := parse_game(g, retrieved, url))]


def money_team_rows(path, min_season):
    chunks = []
    for chunk in pd.read_csv(path, usecols=TEAM_COLUMNS, chunksize=30000):
        chunk = chunk[chunk["situation"].isin(list(SITUATIONS)) & (chunk["season"] >= min_season)]
        chunks.append(chunk)
    if not chunks:
        raise ValueError("No MoneyPuck 5-on-5 history")
    frame = pd.concat(chunks, ignore_index=True)
    if frame.empty or frame.duplicated(["gameId", "team", "situation"]).any():
        raise ValueError("Empty or duplicated MoneyPuck team/game/situation rows")
    numeric = [c for c in TEAM_COLUMNS if c not in {"team", "situation", "home_or_away", "gameDate"}]
    frame[numeric] = frame[numeric].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(frame[numeric].to_numpy()).all() or (frame[numeric] < 0).any().any():
        raise ValueError("Missing/negative MoneyPuck statistics")
    # Published files can include zero-exposure rows (a team with no power play
    # in a game is legitimate). They are retained for join integrity and are
    # excluded from rate aggregation rather than divided or imputed.
    zero = int((frame["iceTime"] == 0).sum())
    if zero:print(f"MoneyPuck: {zero} zero-exposure team rows carry no rate",flush=True)
    return frame.to_dict("records")


def attach_advanced(games, rows):
    by_game = {}
    for row in rows:
        situation = str(row["situation"])
        if situation not in SITUATIONS:
            continue
        by_game.setdefault((str(int(row["gameId"])), situation), []).append(row)
    matched = 0
    for game in games:
        if not game["completed"]:
            continue
        groups = {situation: by_game.get((game["game_id"], situation), []) for situation in SITUATIONS}
        if not any(groups.values()):
            continue
        # A partial MoneyPuck game cannot supply a complete pregame profile.
        # Missing or duplicated situations are refused instead of interpolated.
        for situation, entries in groups.items():
            if len(entries) != 2:
                raise ValueError(f"MoneyPuck {situation} rows for event {game['game_id']} are not exactly two teams")
        attached, special = {}, {}
        for side, orientation in (("home", "HOME"), ("away", "AWAY")):
            picked = {}
            for situation in SITUATIONS:
                matches = [r for r in groups[situation] if str(r["home_or_away"]).upper() == orientation
                           and r["team"] == game[side+"_abbrev"]]
                if len(matches) != 1:
                    raise ValueError(f"Unverified MoneyPuck/NHL team mapping for event {game['game_id']}")
                row = matches[0]
                day = dt.datetime.strptime(str(int(row["gameDate"])), "%Y%m%d").date().isoformat()
                if int(row["season"]) != game["season_start"] or day != game["date"]:
                    raise ValueError("MoneyPuck season/date join mismatch")
                picked[situation] = row
            attached[side] = picked["5on5"]
            special[side] = {SITUATIONS[s]: picked[s] for s in ("5on4", "4on5")}
        game["advanced_5on5"] = attached
        game["special_teams"] = special
        matched += 1
    return matched
