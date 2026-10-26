"""Verified pregame availability for NBA player props.

One endpoint is used: the game summary for the exact fixture being projected. The
league-wide injuries feed is deliberately **not** used to qualify a per-game
snapshot. An earlier version anchored freshness on that feed's ``timestamp``, which
answered a different question ("is the league page current?") than the one that
matters ("is this game's availability data current?"), and would happily stamp a
stale fixture block as fresh because an unrelated endpoint was ticking.

Freshness therefore comes only from the event's own data:

* ``retrieved_at`` is stamped when this exact event payload was observed. That is
  the publication clock for the snapshot, and it is re-checked on every read, so a
  persisted snapshot goes stale instead of staying valid forever.
* each designation carries its own ``date``. A designation dated in the future is
  corrupt and is rejected outright. An old designation is *disclosed*, not deleted:
  a player ruled out in September is still out, and deleting that would silently
  convert a known absence into "unknown".

Event identity is verified too. The requested event id must appear on the payload,
both teams must be present with ids, and every designation's team must be one of
the two competing teams. A designation that cannot be tied to this fixture is
dropped rather than trusted.

Nothing here ever returns "available" as a default. A player who is absent from a
fresh report is UNKNOWN, because not being listed is not proof of fitness.
"""

from __future__ import annotations

import datetime as dt

import requests

EVENT_SOURCE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={event}"
MAX_SNAPSHOT_AGE_HOURS = 6.0
REQUEST_TIMEOUT = 30


def _get(url):
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def _parse_stamp(value):
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def _age_hours(stamp, now):
    """Age of a published timestamp, or ``(None, problem)`` when unusable.

    A timestamp after ``now`` is treated as corrupt data, not as a very fresh
    report: clocks do not run backwards and a future stamp means the field cannot
    be trusted for this decision.
    """
    if stamp is None:
        return None, "timestamp missing or unparseable"
    age = (now - stamp).total_seconds() / 3600
    if age < 0:
        return None, f"timestamp {stamp.isoformat()} is in the future; treated as corrupt"
    return age, None


def event_identity(payload, event_id):
    """Verify the payload really describes the requested fixture."""
    header = payload.get("header") or {}
    competition = (header.get("competitions") or [{}])[0]
    declared = {str(value) for value in (header.get("id"), competition.get("id")) if value}
    uid = str(header.get("uid") or "")
    if "~e:" in uid:
        declared.add(uid.rsplit("~e:", 1)[1])
    if str(event_id) not in declared:
        return {"verified": False, "requested": str(event_id), "declared": sorted(declared),
                "detail": "payload does not declare the requested event id"}

    sides = {}
    for competitor in competition.get("competitors") or []:
        team_id = str((competitor.get("team") or {}).get("id") or "")
        side = competitor.get("homeAway")
        if side in {"home", "away"} and team_id:
            sides[side] = team_id
    if set(sides) != {"home", "away"}:
        return {"verified": False, "requested": str(event_id), "declared": sorted(declared),
                "detail": "payload does not name both competing teams"}

    return {"verified": True, "requested": str(event_id), "declared": sorted(declared),
            "home_team_id": sides["home"], "away_team_id": sides["away"],
            "team_ids": sorted(sides.values()),
            "status": (((competition.get("status") or {}).get("type") or {}).get("name") or ""),
            "kickoff": competition.get("date") or None,
            "detail": "event id and both team ids verified on the event payload"}


def _designation(entry, team_id, team_name, team_ids, now, problems,
                 max_age_hours=MAX_SNAPSHOT_AGE_HOURS):
    """Build one validated designation, or ``None`` when it cannot be trusted."""
    athlete = entry.get("athlete") or {}
    player_id = str(athlete.get("id") or "")
    if not player_id:
        problems.append({"player_id": None, "team_id": team_id,
                         "reason": "designation carries no athlete id"})
        return None
    if team_id not in team_ids:
        problems.append({"player_id": player_id, "team_id": team_id,
                         "reason": "designation team is not competing in this fixture"})
        return None

    status = (entry.get("status") or "").strip()
    if not status:
        problems.append({"player_id": player_id, "team_id": team_id,
                         "reason": "designation carries no status"})
        return None

    published = _parse_stamp(entry.get("date"))
    age, problem = _age_hours(published, now)
    if problem and published is not None:
        problems.append({"player_id": player_id, "team_id": team_id, "reason": problem})
        return None
    return {
        "player_id": player_id,
        "player": athlete.get("displayName"),
        "designation": status.upper(),
        "team": team_name,
        "team_id": team_id,
        "team_verified": True,
        "designation_date": published.isoformat() if published else None,
        "designation_age_hours": round(age, 2) if age is not None else None,
        "designation_undated": published is None,
        # Disclosed, not enforced: an old "Out" is still an out.
        "designation_older_than_limit": bool(age is not None and age > max_age_hours),
        "detail": entry.get("shortComment"),
    }


def snapshot(event_id, max_age_hours=MAX_SNAPSHOT_AGE_HOURS, now=None, fetch=_get):
    """Return a timestamped, identity-checked availability snapshot for one game.

    ``fresh=False`` means the observation cannot be trusted, and callers must treat
    every player as unknown. Nothing here returns "available" by default.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)

    problems = []
    payload = None
    try:
        payload = fetch(EVENT_SOURCE.format(event=event_id))
    except Exception as exc:  # network failure degrades to unknown, never available
        problems.append({"player_id": None, "team_id": None,
                         "reason": f"event availability block unavailable: {exc}"})

    identity = {"verified": False, "requested": str(event_id),
                "detail": "event payload unavailable"}
    season = None
    event_name = None
    if payload is not None:
        identity = event_identity(payload, event_id)
        header = payload.get("header") or {}
        competition = (header.get("competitions") or [{}])[0]
        names = {side.get("homeAway"): (side.get("team") or {}).get("displayName")
                 for side in competition.get("competitors") or []}
        if names.get("away") and names.get("home"):
            event_name = f"{names['away']} at {names['home']}"
        season_year = (header.get("season") or {}).get("year")
        season = {
            "year": season_year,
            "type": (header.get("season") or {}).get("type"),
            "label": (header.get("season") or {}).get("displayName") or (
                f"{season_year - 1}-{str(season_year)[2:]}" if isinstance(season_year, int) else None),
        }
    identity.setdefault("team_ids", [])

    players = {}
    if identity.get("verified"):
        team_ids = set(identity.get("team_ids") or [])
        for block in payload.get("injuries") or []:
            team = block.get("team") or {}
            team_id = str(team.get("id") or "")
            for entry in block.get("injuries") or []:
                record = _designation(entry, team_id, team.get("displayName"), team_ids,
                                      now, problems, max_age_hours)
                if record is not None:
                    players[record["player_id"]] = record

    # The snapshot is observed now; its age is re-derived from this stamp on every read.
    freshness_problem = None
    if payload is None:
        freshness_problem = problems[0]["reason"] if problems else "event payload unavailable"
    elif not identity.get("verified"):
        freshness_problem = identity.get("detail")

    return {
        "event_id": str(event_id),
        "source": EVENT_SOURCE.format(event=event_id),
        "retrieved_at": now.isoformat(),
        "max_age_hours": max_age_hours,
        "age_hours": 0.0 if freshness_problem is None else None,
        "fresh": freshness_problem is None,
        "freshness_problem": freshness_problem,
        "identity": identity,
        "season": season,
        "event_name": event_name,
        "players": players,
        "rejected_designations": problems,
        "listed_players": len(players),
        "note": ("Designations only, freshness from this fixture's own payload. A player "
                 "absent from this report is unknown, not available."),
    }


def designation_for(snapshot_payload, player_id, now=None):
    """Availability designation for one player, or ``None`` when unverified.

    The stored snapshot's own publication age is re-checked here, so loading an old
    snapshot cannot revive an expired report.
    """
    if not snapshot_payload or not snapshot_payload.get("fresh"):
        return None
    if not (snapshot_payload.get("identity") or {}).get("verified"):
        return None
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    stamp = _parse_stamp(snapshot_payload.get("retrieved_at"))
    age, problem = _age_hours(stamp, now)
    if problem or age > (snapshot_payload.get("max_age_hours") or MAX_SNAPSHOT_AGE_HOURS):
        return None
    entry = (snapshot_payload.get("players") or {}).get(str(player_id))
    if not entry or not entry.get("team_verified"):
        return None
    return entry.get("designation")


def summary_line(snapshot_payload):
    if not snapshot_payload:
        return "availability: no report"
    if not snapshot_payload.get("fresh"):
        return f"availability: UNVERIFIED ({snapshot_payload.get('freshness_problem')})"
    identity = snapshot_payload.get("identity") or {}
    rejected = len(snapshot_payload.get("rejected_designations") or [])
    return (f"availability: {snapshot_payload.get('listed_players')} validated designation(s) "
            f"for event {snapshot_payload.get('event_id')} "
            f"(teams {', '.join(identity.get('team_ids') or [])}), "
            f"observed {snapshot_payload.get('age_hours')}h ago, "
            f"{rejected} rejected")
