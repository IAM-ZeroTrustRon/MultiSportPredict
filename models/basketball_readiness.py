"""Season-specific observation gates; old seasons cannot qualify a new roster."""
import datetime as dt
import math


MIN_SEASON_GAMES = {"NBA": 10, "NCAAB": 8}
PROJECTION_ONLY = "Insufficient current-season data — Projection only"


def season_game_counts(games, league, season, cutoff, teams=()):
    """Count distinct valid finals before the date, excluding preseason games.

    League season IDs (e.g. NBA 2027 spanning 2026–27) are authoritative;
    calendar years cannot identify a basketball season. Same-day results are
    excluded to match ScoreRatings' conservative pre-fixture training cutoff.
    """
    dt.date.fromisoformat(cutoff)
    if isinstance(season, bool) or not isinstance(season, int):
        raise ValueError("A verified integer league season ID is required")
    counts = {name: 0 for name in teams}
    seen = set()
    for g in games:
        if (g.get("league") != league or g.get("season") != season
                or g.get("completed") is not True
                or g.get("season_type") in (1, "1")
                or g.get("status") in {"STATUS_CANCELED", "STATUS_POSTPONED"}):
            continue
        try:
            day = dt.date.fromisoformat(g["date"])
            scores = [g[side + "_score"] for side in ("home", "away")]
            if (day >= dt.date.fromisoformat(cutoff)
                    or any(isinstance(v, bool) or v is None or not math.isfinite(float(v)) or float(v) < 0 for v in scores)):
                continue
            home, away, ident = g["home_team"], g["away_team"], g["game_id"]
            if not home or not away or home == away or not ident:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        if str(ident) in seen:
            continue
        seen.add(str(ident))
        for name in (home, away):
            counts[name] = counts.get(name, 0) + 1
    return counts


def season_count_metadata(games, league, cutoff, teams=()):
    seasons = sorted({g["season"] for g in games
                      if isinstance(g.get("season"), int) and not isinstance(g["season"], bool)})
    return {"counted_before": cutoff, "basis": "Distinct completed games; preseason and same-day/future finals excluded",
            "by_season": {str(s): season_game_counts(games, league, s, cutoff, teams) for s in seasons}}


def readiness(game, games, cutoff):
    league = str(game.get("league", "")).upper()
    if league not in MIN_SEASON_GAMES:
        return None  # No new policy is silently imposed on other sports/leagues.
    season = game.get("season")
    required = MIN_SEASON_GAMES[league]
    known = isinstance(season, int) and not isinstance(season, bool)
    counts = season_game_counts(games, league, season, cutoff) if known else {}
    home = counts.get(game["home_team"], 0) if known else None
    away = counts.get(game["away_team"], 0) if known else None
    eligible = known and min(home, away) >= required
    return {"season": season if known else None, "required_games": required,
            "season_games_played": {"home": home, "away": away},
            "counted_before": cutoff, "eligible": eligible,
            "status": "Current-season sample threshold met; model remains uncalibrated" if eligible else PROJECTION_ONLY,
            "reason": "Both teams meet the observation threshold" if eligible else
                      "Verified fixture season ID unavailable" if not known else
                      f"Both teams require at least {required} completed current-season games",
            "policy": "NBA 10 / NCAAB 8; observation policy, not a validated accuracy guarantee"}


def projection_only(result):
    return isinstance(result.get("readiness"), dict) and result["readiness"].get("eligible") is False


def observation_markets(markets, status=PROJECTION_ONLY):
    """Suppress recommendations in persisted data as well as in formatters."""
    return [{**m, "ev_a": None, "ev_b": None, "pick": None,
             "stake_size": None, "stake_basis": "unavailable: projection only",
             "recommendation": "INFO — " + status, "status": status,
             "note": "Score/probability observation only; EV and betting recommendations disabled"} for m in markets]
