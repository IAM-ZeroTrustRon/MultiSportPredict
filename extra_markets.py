#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

FIRST_HALF_FRACTION = 0.45
TEAM_GOAL_LINES = [0.5, 1.5, 2.5]
TEAM_CORNER_LINES = [3.5, 4.5, 5.5]
FIRST_HALF_GOAL_LINES = [0.5, 1.5]

# Below this, an attacking number is not a real signal -- it is what a team
# one game into a season, with xG "estimated from goals" (see
# soccer_stats.json's own source note), looks like after a scoreless loss.
# Aston Villa's 2026/27 xg_for is a genuine, present 0.0 -- not missing, not
# None -- and treating it as a real attacking rate drove the corner split to
# 100/0. These floors are population minimums: a Premier League team's true
# per-game xG or shot count essentially never sits below them over any
# sample that means anything.
MIN_RELIABLE_XG = 0.3
MIN_RELIABLE_SHOTS = 3.0
LEAGUE_AVG_XG = 1.4        # roughly average team xG per match
LEAGUE_AVG_SHOTS = 12.0    # roughly average team shots per match


def _poisson_pmf(k: int, lam: float) -> float:
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def _over_prob(lam: float, line: float) -> float:
    k_max = int(line) + 1
    under = sum(_poisson_pmf(k, lam) for k in range(0, k_max))
    return max(0.0, min(1.0, 1.0 - under))


def _dig(d: Dict[str, Any], *keys, default=None):
    for k in keys:
        if isinstance(k, (list, tuple)):
            cur = d
            ok = True
            for part in k:
                if isinstance(cur, dict) and part in cur:
                    cur = cur[part]
                else:
                    ok = False
                    break
            if ok:
                return cur
        elif k in d:
            return d[k]
    return default


def _extract_core_numbers(
    result: Dict[str, Any],
    home_stats: Optional[Dict[str, Any]] = None,
    away_stats: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    home_goals = _dig(result, ("game", "projected_home_goals"), "projected_home_goals", default=None)
    away_goals = _dig(result, ("game", "projected_away_goals"), "projected_away_goals", default=None)
    corners_total = _dig(result, ("corners", "projection"), "corner_projection", default=None)

    team_metrics = result.get("team_metrics", {})
    home_m = home_stats or {}
    away_m = away_stats or {}
    if isinstance(team_metrics.get("home"), dict):
        home_m = {**home_m, **team_metrics["home"]}
    if isinstance(team_metrics.get("away"), dict):
        away_m = {**away_m, **team_metrics["away"]}

    return {
        "home_goals": float(home_goals) if home_goals is not None else None,
        "away_goals": float(away_goals) if away_goals is not None else None,
        "corners_total": float(corners_total) if corners_total is not None else None,
        "home_xg": float(home_m.get("xg_for")) if home_m.get("xg_for") is not None else None,
        "away_xg": float(away_m.get("xg_for")) if away_m.get("xg_for") is not None else None,
        "home_shots": float(home_m.get("shots")) if home_m.get("shots") is not None else None,
        "away_shots": float(away_m.get("shots")) if away_m.get("shots") is not None else None,
    }


def _team_goal_market(projected: float, lines: List[float]) -> Dict[str, float]:
    return {f"over_{str(line).replace('.', '')}": round(_over_prob(projected, line), 3) for line in lines}


def _reliable(value: Optional[float], metric: str) -> bool:
    """False for None (truly absent) AND for a present-but-degenerate value
    (Villa's 0.0) -- both mean 'no real signal', and the split math cannot
    tell them apart unless it checks explicitly."""
    if value is None:
        return False
    floor = MIN_RELIABLE_XG if metric == "xg" else MIN_RELIABLE_SHOTS
    return value >= floor


def _team_corner_split(corners_total: float,
                       home_attack: Optional[float], away_attack: Optional[float],
                       home_metric: str = "xg", away_metric: str = "xg") -> Dict[str, Any]:
    home_ok, away_ok = _reliable(home_attack, home_metric), _reliable(away_attack, away_metric)

    if not home_ok and not away_ok:
        # No reliable signal on either side. 50/50 is not a fallback
        # standing in for a real split -- it is the correct statement of
        # "no information", and is labelled as such below.
        return {
            "home_corners_proj": round(corners_total * 0.5, 2),
            "away_corners_proj": round(corners_total * 0.5, 2),
            "split_method": "even_split_no_data",
            "degraded": True,
            "degraded_reason": "neither side has a reliable attacking number",
        }

    if home_ok != away_ok:
        # One side is real, the other is missing or too thin to trust. The
        # old behavior filled the gap with 0, which forced a 100/0 split
        # regardless of how strong the known side's number actually was --
        # a home xG of 0.3 produced the same 100/0 as a home xG of 3.0.
        # Substituting a league-average baseline keeps the known number
        # meaningful relative to something, without inventing data for the
        # side that has none.
        if home_ok:
            baseline = LEAGUE_AVG_XG if away_metric == "xg" else LEAGUE_AVG_SHOTS
            effective_home, effective_away = home_attack, baseline
            weak_side, weak_value = "away", away_attack
        else:
            baseline = LEAGUE_AVG_XG if home_metric == "xg" else LEAGUE_AVG_SHOTS
            effective_home, effective_away = baseline, away_attack
            weak_side, weak_value = "home", home_attack
        total = effective_home + effective_away
        home_share = effective_home / total if total > 0 else 0.5
        return {
            "home_corners_proj": round(corners_total * home_share, 2),
            "away_corners_proj": round(corners_total * (1.0 - home_share), 2),
            "split_method": "attacking_share_partial_data",
            "degraded": True,
            "degraded_reason": (f"{weak_side} attacking number is missing or unreliable "
                               f"(value={weak_value}) -- substituted a league-average "
                               f"baseline ({baseline:g}) instead of collapsing to 0"),
        }

    total_attack = home_attack + away_attack
    if total_attack <= 0:
        return {
            "home_corners_proj": round(corners_total * 0.5, 2),
            "away_corners_proj": round(corners_total * 0.5, 2),
            "split_method": "even_split_no_data",
            "degraded": True,
            "degraded_reason": "both attacking numbers present but sum to zero",
        }
    home_share = home_attack / total_attack
    return {
        "home_corners_proj": round(corners_total * home_share, 2),
        "away_corners_proj": round(corners_total * (1.0 - home_share), 2),
        "split_method": "attacking_share",
        "degraded": False,
    }


def compute_extra_markets(
    result: Dict[str, Any],
    home_stats: Optional[Dict[str, Any]] = None,
    away_stats: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    core = _extract_core_numbers(result, home_stats, away_stats)
    out: Dict[str, Any] = {"_extra_markets_source": "derived_from_existing_projection"}

    missing = [k for k in ("home_goals", "away_goals") if core[k] is None]
    if missing:
        out["_warning"] = f"Could not find {missing} in the result dict - team goal markets skipped."
        return out

    home_goals, away_goals = core["home_goals"], core["away_goals"]
    match_total = home_goals + away_goals

    out["team_total_goals"] = {
        "home": _team_goal_market(home_goals, TEAM_GOAL_LINES),
        "away": _team_goal_market(away_goals, TEAM_GOAL_LINES),
    }

    if core["corners_total"] is not None:
        home_attack, home_metric = ((core["home_xg"], "xg") if core["home_xg"] is not None
                                    else (core["home_shots"], "shots"))
        away_attack, away_metric = ((core["away_xg"], "xg") if core["away_xg"] is not None
                                    else (core["away_shots"], "shots"))
        split = _team_corner_split(core["corners_total"], home_attack, away_attack,
                                   home_metric, away_metric)
        out["team_corners"] = {
            "home": {**_team_goal_market(split["home_corners_proj"], TEAM_CORNER_LINES),
                     "projection": split["home_corners_proj"]},
            "away": {**_team_goal_market(split["away_corners_proj"], TEAM_CORNER_LINES),
                     "projection": split["away_corners_proj"]},
            "split_method": split["split_method"],
            "degraded": split.get("degraded", False),
        }
        if split.get("degraded_reason"):
            out["team_corners"]["degraded_reason"] = split["degraded_reason"]
    else:
        out["team_corners"] = {"_warning": "No match corner projection found in result - team corners skipped."}

    fh_total = match_total * FIRST_HALF_FRACTION
    out["first_half_goals"] = {
        "projection": round(fh_total, 2),
        "fraction_used": FIRST_HALF_FRACTION,
        **_team_goal_market(fh_total, FIRST_HALF_GOAL_LINES),
    }

    btts = _dig(result, ("btts", "probability"), ("predictions", "btts", "probability"), default=None)
    if btts is not None:
        out["btts_confirmed"] = {"probability": round(float(btts), 3)}
    else:
        out["btts_confirmed"] = {"_warning": "BTTS not found in result - check SoccerPredictor output key."}

    return out


def enrich_result(
    result: Dict[str, Any],
    home_team: str = "",
    away_team: str = "",
    home_stats: Optional[Dict[str, Any]] = None,
    away_stats: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    enriched = dict(result)
    enriched["extra_markets"] = compute_extra_markets(result, home_stats, away_stats)
    enriched["extra_markets"]["_teams"] = {"home": home_team, "away": away_team}
    return enriched


def print_extra_markets(enriched: Dict[str, Any]) -> None:
    em = enriched.get("extra_markets", {})
    teams = em.get("_teams", {})
    home_name = teams.get("home", "Home")
    away_name = teams.get("away", "Away")

    print("\n" + "-" * 60)
    print("EXTRA MARKETS (derived - see extra_markets.py for methodology)")
    print("-" * 60)

    if "_warning" in em:
        print(f"[WARNING] {em['_warning']}")
        return

    ttg = em.get("team_total_goals", {})
    if ttg:
        print(f"\n{home_name} Team Total Goals:")
        for line, prob in ttg.get("home", {}).items():
            print(f"  Over {line.replace('over_', '')[0]}.{line.replace('over_', '')[1:]}: {prob*100:.1f}%")
        print(f"{away_name} Team Total Goals:")
        for line, prob in ttg.get("away", {}).items():
            print(f"  Over {line.replace('over_', '')[0]}.{line.replace('over_', '')[1:]}: {prob*100:.1f}%")

    tc = em.get("team_corners", {})
    if tc and "_warning" not in tc:
        print(f"\n{home_name} Team Corners (proj {tc['home']['projection']}, split method: {tc['split_method']}):")
        for line, prob in tc["home"].items():
            if line.startswith("over_"):
                print(f"  Over {line.replace('over_', '')[0]}.{line.replace('over_', '')[1:]}: {prob*100:.1f}%")
        print(f"{away_name} Team Corners (proj {tc['away']['projection']}):")
        for line, prob in tc["away"].items():
            if line.startswith("over_"):
                print(f"  Over {line.replace('over_', '')[0]}.{line.replace('over_', '')[1:]}: {prob*100:.1f}%")
    elif tc:
        print(f"\n[WARNING] {tc.get('_warning')}")

    fh = em.get("first_half_goals", {})
    if fh:
        print(f"\n1st Half Total Goals (proj {fh['projection']}, using {fh['fraction_used']*100:.0f}% of match total):")
        for line, prob in fh.items():
            if line.startswith("over_"):
                print(f"  Over {line.replace('over_', '')[0]}.{line.replace('over_', '')[1:]}: {prob*100:.1f}%")

    btts = em.get("btts_confirmed", {})
    if btts and "probability" in btts:
        print(f"\nBTTS: {btts['probability']*100:.1f}%")

    print("-" * 60)


if __name__ == "__main__":
    fake_result = {
        "game": {"projected_home_goals": 2.14, "projected_away_goals": 1.30},
        "corners": {"projection": 10.0},
        "team_metrics": {
            "home": {"xg_for": 1.3, "xg_against": 0.6, "shots": 11.0},
            "away": {"xg_for": 1.1, "xg_against": 1.8, "shots": 10.0},
        },
        "btts": {"probability": 0.639},
    }
    enriched = enrich_result(fake_result, home_team="Bradford City", away_team="Burnley")
    print_extra_markets(enriched)
    print("\nextra_markets.py OK")
