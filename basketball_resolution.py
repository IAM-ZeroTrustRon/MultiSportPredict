"""Competition-scoped basketball resolution and explicit hybrid observations.

Score history remains the production model input. Missing records trigger one
supported public refresh, never a guessed provider key or a silent baseline.
"""
import datetime as dt
import json
import math
import statistics
import unicodedata

from sports_feed import ROOT, today

ALIASES = {
    "AUSTRALIAN NBL": "NBL", "AUSTRALIAN_NBL": "NBL", "AU NBL": "NBL",
    "NZ NBL": "NZNBL", "NZ_NBL": "NZNBL", "NEW ZEALAND NBL": "NZNBL",
    "BUNDESLIGA": "BBL", "GERMAN BBL": "BBL",
}
SCORE_LEAGUES = {"NBA", "WNBA", "NCAAB", "NCAAW", "NBL", "NZNBL", "KBL", "BBL"}


def canonical_league(value):
    key = str(value or "").strip().upper()
    if not key:
        raise ValueError("Basketball requires a league")
    return ALIASES.get(key, key)


def name_key(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value).casefold()
                   if c.isalnum() and not unicodedata.combining(c))


def load_history(league):
    # Unknown competition names are never interpolated into file paths.
    if league not in SCORE_LEAGUES:
        return {"league": league, "games": []}
    path = ROOT / f"data/basketball_{league.lower()}_games.json"
    if not path.exists():
        return {"league": league, "games": []}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if data.get("league") != league or any(g.get("league") != league for g in data["games"]):
        raise ValueError(f"Competition mismatch in {path.name}; refusing cross-league data")
    return data


def refresh_history(league, day):
    from ingest_basketball_espn import LEAGUES, ingest
    if league in LEAGUES:
        year = dt.date.fromisoformat(day).year
        return ingest(league, [year - 1, year, year + 1])
    if league in {"KBL", "NZNBL", "BBL"}:
        from ingest_basketball_official import ingest as official
        return official(league)
    return None  # No provider adapter is claimed for an unknown competition.


def eligible_games(data, cutoff):
    rows, seen = [], set()
    for g in data.get("games", []):
        if (g.get("league") != data["league"] or g.get("completed") is not True
                or g.get("season_type") in (1, "1")
                or g.get("status") in {"STATUS_POSTPONED", "STATUS_CANCELED"}):
            continue
        try:
            stamp = dt.date.fromisoformat(g["date"])
            scores = [g[s + "_score"] for s in ("home", "away")]
            if stamp >= dt.date.fromisoformat(cutoff) or any(
                    isinstance(x, bool) or not math.isfinite(float(x)) or float(x) < 0 for x in scores):
                continue
            if not g["game_id"] or g["home_team"] == g["away_team"]:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        if g["game_id"] not in seen:
            seen.add(g["game_id"])
            rows.append(g)
    return rows


def find_fixture(data, first, second, day):
    pair = {name_key(first), name_key(second)}
    hits = [g for g in data.get("games", []) if g.get("date") == day
            and {name_key(g["home_team"]), name_key(g["away_team"])} == pair]
    if len(hits) > 1:
        raise ValueError("Ambiguous basketball fixture; more than one event matches")
    if not hits:
        return None
    game = hits[0]
    if game.get("completed") or game.get("status") in {
            "STATUS_IN_PROGRESS", "STATUS_HALFTIME", "STATUS_POSTPONED", "STATUS_CANCELED"}:
        raise ValueError("Fixture is completed, in play, postponed or canceled")
    stamp = dt.datetime.fromisoformat(game["start_time"].replace("Z", "+00:00"))
    from sports_feed import EASTERN
    if stamp.tzinfo is None or stamp.astimezone(EASTERN).date().isoformat() != day:
        raise ValueError("Fixture kickoff/date mismatch")
    if stamp <= dt.datetime.now(dt.timezone.utc):
        raise ValueError("Fixture has already started")
    return game


def prepare(league, first, second, day, refresh=True):
    """Return the local/refreshed source and fixture, with one refresh at most."""
    league = canonical_league(league)
    dt.date.fromisoformat(day)
    if day < today():
        raise ValueError("Use today or a future date for a new basketball forecast")
    if not first.strip() or not second.strip() or name_key(first) == name_key(second):
        raise ValueError("Supply two distinct team names")
    data = load_history(league)
    fixture = find_fixture(data, first, second, day)
    cutoff = min(today(), day)
    games = eligible_games(data, cutoff)
    counts = [sum(name_key(t) in (name_key(g['home_team']), name_key(g['away_team']))
                  for g in games) for t in (first, second)]
    updated = data.get("updated")
    stale = not updated or (dt.date.fromisoformat(today()) - dt.date.fromisoformat(updated)).days > 7
    notes = []
    if refresh and (fixture is None or min(counts) < 5 or len(games) < 80 or stale):
        print(f"Resolving {league}: refreshing supported public history and schedules...")
        try:
            sourced = refresh_history(league, day)
            if sourced is not None:
                data = load_history(league)  # Persisted source is the next run's local hit.
                notes.append("Supported public source refreshed")
            else:
                notes.append("No supported automatic source for this competition")
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            # Do not echo URLs/exceptions that might carry credentials.
            notes.append(f"Public refresh failed ({type(exc).__name__}); retained existing data")
        fixture = find_fixture(data, first, second, day)
    return data, fixture, notes


def team_metrics(data, team, cutoff, season=None):
    """Actual pre-cutoff points, not invented possession/efficiency statistics."""
    rows = [g for g in eligible_games(data, cutoff)
            if (season is None or g.get("season") == season)
            and name_key(team) in (name_key(g["home_team"]), name_key(g["away_team"]))]
    if not rows:
        return {}
    scored, allowed = [], []
    for g in rows:
        side = "home" if name_key(team) == name_key(g["home_team"]) else "away"
        other = "away" if side == "home" else "home"
        scored.append(float(g[side + "_score"]))
        allowed.append(float(g[other + "_score"]))
    return {"points_for": statistics.mean(scored), "points_against": statistics.mean(allowed),
            "games": len(rows), "source": "competition-scoped completed score history",
            "latest_game": max(g["date"] for g in rows)}


def measured_rates(league, team, cutoff, season):
    """Use only dated, season/competition-scoped measured efficiencies.

    Undated starter templates and foreign-league namesakes are not evidence.
    Current-day refreshes are usable for current forecasts, never historical ones.
    """
    result = {}
    for relative in ('data/basketball_stats.json', 'data/team_stats/basketball_stats.json',
                     'data/euroleague_stats.json'):
        path = ROOT / relative
        if not path.exists():
            continue
        records = json.loads(path.read_text(encoding='utf-8-sig'))
        for name, row in records.items():
            if name.startswith('_') or name_key(name) != name_key(team) or not isinstance(row, dict):
                continue
            if canonical_league(row.get('league') or 'UNSCOPED') != league or season is None or row.get('season') != season:
                continue
            try:
                stamp = dt.date.fromisoformat(str(row['updated'])[:10])
                age = (dt.date.fromisoformat(cutoff) - stamp).days
                if not 0 <= age <= 7 or float(row['games']) <= 0 or not row.get('source'):
                    continue
            except (KeyError, TypeError, ValueError):
                continue
            for field in ('pace', 'ortg', 'drtg'):
                value = row.get(field)
                try:
                    if value is not None and not isinstance(value, bool) and math.isfinite(float(value)) and float(value) > 0:
                        result[field] = dict(value=float(value), source=row['source'], updated=row['updated'])
                except (TypeError, ValueError):
                    continue
    return result


def hybrid(data, first, second, day, fixture=None, notes=()):
    from exploratory import BASKETBALL_BASELINES, DEFAULT_BASKETBALL
    league = data["league"]
    baseline = BASKETBALL_BASELINES.get(league, DEFAULT_BASKETBALL)
    home, away = (fixture['home_team'], fixture['away_team']) if fixture else (first, second)
    cutoff = min(today(), day)
    history = eligible_games(data, cutoff)
    # A verified fixture season prevents old rosters masquerading as current rates.
    season = fixture.get("season") if fixture else max((g.get("season", 0) for g in history), default=None)
    history = [g for g in history if season is None or g.get("season") == season]
    points = [float(g[s + '_score']) for g in history for s in ('home', 'away')]
    prior = statistics.median(points) if points else baseline['points']
    source = "competition median of pre-cutoff final scores" if points else "configured round scoring assumption"
    substitutions, provenance, metrics = [], {}, {}
    for side, name in (("home", home), ("away", away)):
        measured = team_metrics(data, name, cutoff, season)
        # Stale records are not promoted as current, but remain visible in audit data.
        if measured and (dt.date.fromisoformat(cutoff) - dt.date.fromisoformat(measured['latest_game'])).days > 400:
            measured = {}
        values = {}
        for field in ("points_for", "points_against"):
            if field in measured:
                values[field] = measured[field]
            else:
                values[field] = prior
                substitutions.append(dict(input=f"{side}.{field}", value=prior,
                                          source=source, why="no eligible team scoring history"))
        metrics[side] = values
        rates = measured_rates(league, name, cutoff, season)
        # Preserve measured efficiencies/pace independently. With only final
        # scores available, a disclosed pace conversion retains actual scoring
        # averages rather than discarding them in favour of an average team.
        pace = rates.get('pace', {}).get('value', 75.0)
        if 'pace' not in rates:
            substitutions.append(dict(input=f'{side}.pace', value=pace,
                                      source='generic 75 possessions assumption', why='no measured possessions'))
        for field, scoring_field in (('ortg', 'points_for'), ('drtg', 'points_against')):
            values[field] = rates.get(field, {}).get('value', values[scoring_field] / pace * 100)
            if field not in rates:
                substitutions.append(dict(input=f'{side}.{field}', value=values[field],
                    source='scoring average / assumed or measured pace', why='no measured per-possession efficiency'))
        values['pace'] = pace
        provenance[side] = dict(name=name, status="SOURCED" if measured else "SUBSTITUTED",
                                metrics=values, games=measured.get('games', 0),
                                source=measured.get('source', source), season=season,
                                measured_rates=rates)
        if rates:
            provenance[side]['status'] = 'PARTIALLY SOURCED' if len(rates) < 3 else 'SOURCED RATES'
    margin_sd = baseline['margin_sd']
    hfa = 0 if fixture and fixture.get('neutral_site') else 1.7
    substitutions.extend([
        dict(input="home-court advantage", value=hfa, source="generic assumption" if hfa else "verified neutral venue",
             why="venue effect not fitted"),
        dict(input="margin/total volatility", value=f"{margin_sd}/{margin_sd * 1.5}",
             source="configured assumption", why="hybrid residual distribution not fitted"),
        dict(input="injuries, lineups, rest, travel", value="not included", source="unavailable",
             why="no verified availability inputs"),
    ])
    if not fixture:
        substitutions.append(dict(input="fixture and home/away", value=f"{home} home; {away} away",
                                  source="user-supplied order", why="no verified scheduled fixture"))
    pace = (metrics['home']['pace'] + metrics['away']['pace']) / 2
    hp = (metrics['home']['ortg'] + metrics['away']['drtg']) / 200 * pace + hfa / 2
    ap = (metrics['away']['ortg'] + metrics['home']['drtg']) / 200 * pace - hfa / 2
    return dict(sport="basketball", league=league, home_team=home, away_team=away,
                game_date=day, game_id=fixture['game_id'] if fixture else f"unverified:{day}:{home}:{away}",
                fixture=fixture or {}, exploratory=True, is_exploratory=True, mode="exploratory",
                cohort="EXPLORATORY", input_provenance=provenance, substitutions=substitutions,
                projection=dict(home_points=hp, away_points=ap, margin_sd=margin_sd,
                                total_sd=margin_sd * 1.5, training_cutoff=cutoff,
                                note="Hybrid scoring averages; uncertainty and venue effect assumed, not calibrated"),
                notes=list(notes), fixture_verified=bool(fixture))
