"""Strict pregame rolling NHL features, with no final-season average leakage."""
import datetime as dt
import json
import math
from pathlib import Path

import pandas as pd

from sports_feed import ROOT
from nhl_sources import stamp

TEAM_FEATURES = ["xgf60", "xga60", "xg_share", "corsi_share", "high_danger_shot_share", "team_save_pct",
                 "pp_goals60", "pk_goals_against60", "exposure_minutes",
                 "back_to_back", "games_last_7_days"]
NHL_FEATURES = [side+"_"+key for side in ("home", "away") for key in TEAM_FEATURES]+["rest_diff_days"]
FEATURE_VERSION = "nhl-5v5-st-rolling40-prior8-restcap7-v2"
BACK_TO_BACK_HOURS = 24


def _exposure(entries, key):
    """Sum one field over positive-exposure rows only; never divide by zero.

    A zero-minute row is a real published value (a team with no power play in a
    game). It carries no rate contribution and is never imputed or divided.
    """
    total = 0.0
    for entry in entries:
        if not entry:
            continue
        minutes = float(entry["iceTime"])
        if not math.isfinite(minutes) or minutes < 0:
            raise ValueError("Invalid advanced ice time")
        if minutes <= 0:
            continue
        value = float(entry[key])
        if not math.isfinite(value) or value < 0:
            raise ValueError("Invalid advanced feature history")
        total += value
    return total


def team_profile(game, games, side):
    ident = game[side+"_id"]
    earlier = [g for g in games if g["completed"] and g["date"] < game["date"]
               and g["season_start"] >= game["season_start"]-2
               and ident in (g["home_id"], g["away_id"])]
    earlier.sort(key=lambda g:g["start_time"])
    usable = []
    for g in earlier:
        orientation = "home" if g["home_id"] == ident else "away"
        row = g.get("advanced_5on5", {}).get(orientation)
        if row: usable.append((row, (g.get("special_teams") or {}).get(orientation) or {}))
    rows = usable[-40:]
    if len(rows) < 8:
        raise ValueError(f"{game[side+'_team']}: only {len(rows)} prior advanced-stat games; need 8")
    five = [r[0] for r in rows]
    power_play = [r[1].get("pp") for r in rows]
    penalty_kill = [r[1].get("pk") for r in rows]
    exposure = _exposure(five, "iceTime")
    xg_for = _exposure(five, "xGoalsFor")
    xg_against = _exposure(five, "xGoalsAgainst")
    pp_time = _exposure(power_play, "iceTime")
    pp_goals = _exposure(power_play, "goalsFor")
    pk_time = _exposure(penalty_kill, "iceTime")
    pk_goals = _exposure(penalty_kill, "goalsAgainst")
    attempts = _exposure(five, "shotAttemptsFor")+_exposure(five, "shotAttemptsAgainst")
    dangers = _exposure(five, "highDangerShotsFor")+_exposure(five, "highDangerShotsAgainst")
    shots = _exposure(five, "shotsOnGoalAgainst")
    goals_against = _exposure(five, "goalsAgainst")
    # Special-teams denominators are required, not optional: a missing 5-on-4 or
    # 4-on-5 history would silently pretend a team never had special teams.
    if min(exposure, xg_for+xg_against, attempts, dangers, shots, pp_time, pk_time) <= 0:
        raise ValueError("Advanced features lack valid exposure/denominators")
    if goals_against > shots or pp_goals > pp_time or pk_goals > pk_time:
        raise ValueError("Advanced features violate published count relationships")
    last = earlier[-1]
    rest = (stamp(game["start_time"])-stamp(last["start_time"])).total_seconds()/3600
    if rest <= 0:
        raise ValueError("Nonpositive pregame rest")
    window_start = stamp(game["start_time"])-dt.timedelta(days=7)
    profile = dict(xgf60=xg_for*3600/exposure,
                   xga60=xg_against*3600/exposure,
                   xg_share=xg_for/(xg_for+xg_against),
                   corsi_share=_exposure(five, "shotAttemptsFor")/attempts,
                   high_danger_shot_share=_exposure(five, "highDangerShotsFor")/dangers,
                   team_save_pct=1-goals_against/shots,
                   pp_goals60=pp_goals*3600/pp_time,
                   pk_goals_against60=pk_goals*3600/pk_time,
                   exposure_minutes=exposure/60,
                   back_to_back=int(rest < BACK_TO_BACK_HOURS),
                   games_last_7_days=sum(1 for g in earlier if stamp(g["start_time"]) >= window_start))
    return profile, dict(historical_advanced_games=len(usable), rolling_games=len(rows),
                         season_games_played=sum(g["season"]==game["season"] for g in earlier),
                         last_seen=last["start_time"], rest_hours=rest,
                         pp_games=sum(1 for entry in power_play if entry and float(entry["iceTime"]) > 0),
                         pk_games=sum(1 for entry in penalty_kill if entry and float(entry["iceTime"]) > 0))


def pregame_features(game, games):
    values = {}; observations = {}
    for side in ("home", "away"):
        profile, obs = team_profile(game, games, side)
        values.update({side+"_"+k:v for k, v in profile.items()}); observations[side] = obs
    values["rest_diff_days"] = (min(observations["home"]["rest_hours"], 168)-min(observations["away"]["rest_hours"], 168))/24
    return values, observations


def build_nhl_features(data=None, out_path=None):
    data = data or json.loads((ROOT/"data/nhl_games.json").read_text(encoding="utf-8"))
    games = data["games"]; rows = []; skipped = 0
    for game in games:
        if not game["completed"] or game["season_type"] != 2:
            continue
        try:
            features, obs = pregame_features(game, games)
        except ValueError:
            skipped += 1; continue
        rows.append(dict(game_id=game["game_id"], date=game["date"], start_time=game["start_time"],
                         season=game["season"], home_team=game["home_team"], away_team=game["away_team"],
                         regulation_home=game["regulation_home"], regulation_away=game["regulation_away"],
                         home_won=int(game["home_score"] > game["away_score"]), **features))
    if not rows:
        raise ValueError("No eligible NHL pregame features; existing feature file retained")
    rows.sort(key=lambda r:(r["date"], r["game_id"]))
    if out_path:
        path = Path(out_path); path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp"); pd.DataFrame(rows).to_csv(temp, index=False); temp.replace(path)
    print(f"NHL features: {len(rows)} pregame examples; {skipped} insufficient-history rows omitted", flush=True)
    return rows


if __name__=="__main__":
    build_nhl_features(out_path=ROOT/"data/processed/nhl_features.csv")
