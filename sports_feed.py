"""ESPN event ingestion with local caches and explicit feed provenance."""
import datetime as dt
import hashlib
import json
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
EASTERN = ZoneInfo("America/New_York")


def today():
    return dt.datetime.now(EASTERN).date().isoformat()


def fetch_json(url, cache_hours=6):
    path = ROOT / "data/cache/sports" / (hashlib.sha256(url.encode()).hexdigest() + ".json")
    if path.exists() and dt.datetime.now().timestamp() - path.stat().st_mtime < cache_hours * 3600:
        return json.loads(path.read_text(encoding="utf-8"))
    headers = {"User-Agent": "Mozilla/5.0"}
    if url.startswith("https://api.wtatennis.com/"):
        headers["account"] = "wta"  # Public account header used by the WTA website.
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=40) as response:
        payload = json.loads(response.read())
    atomic_json(path, payload)
    return payload


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def parse_game(event, league):
    competition = (event.get("competitions") or [{}])[0]
    sides = {x.get("homeAway"): x for x in competition.get("competitors", [])}
    if set(sides) != {"home", "away"}:
        return None
    timestamp = event.get("date") or competition.get("date")
    if not timestamp:
        return None
    stamp = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    status = competition.get("status", {}).get("type", {})
    row = {"game_id": str(event["id"]), "date": stamp.astimezone(EASTERN).date().isoformat(),
           "start_time": stamp.isoformat(), "season": int(event.get("season", {}).get("year", stamp.year)),
           "league": league, "completed": bool(status.get("completed")),
           "status": status.get("name"), "neutral_site": bool(competition.get("neutralSite")),
           "source": "ESPN scoreboard/schedule"}
    for side, item in sides.items():
        team = item.get("team", {})
        if not team.get("displayName") or not team.get("id"):
            return None
        raw = item.get("score")
        if isinstance(raw, dict):
            raw = raw.get("value") if raw.get("value") is not None else raw.get("displayValue")
        try:
            score = float(raw) if raw is not None else None
        except (ValueError, TypeError):
            return None
        row.update({side + "_team": team["displayName"], side + "_id": str(team["id"]),
                    side + "_score": score})
    if row["completed"] and (row["home_score"] is None or row["away_score"] is None):
        return None
    return row
