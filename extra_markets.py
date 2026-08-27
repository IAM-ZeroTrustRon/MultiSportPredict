#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

FIRST_HALF_FRACTION = 0.45
TEAM_GOAL_LINES = [0.5, 1.5, 2.5]
TEAM_CORNER_LINES = [3.5, 4.5, 5.5]
FIRST_HALF_GOAL_LINES = [0.5, 1.5]


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


def _team_corner_split(corners_total: float, home_attack: float, away_attack: float) -> Dict[str, Any]:
    total_attack = (home_attack or 0) + (away_attack or 0)
    if total_attack <= 0:
        home_share, away_share = 0.5, 0.5
    else:
        home_share = home_attack / total_attack
        away_share = 1.0 - home_share
    return {
        "home_corners_proj": round(corners_total * home_share, 2),
        "away_corners_proj": round(corners_total * away_share, 2),
        "split_method": "attacking_share" if total_attack > 0 else "even_split_no_data",
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
        home_attack = core["home_xg"] if core["home_xg"] is not None else core["home_shots"]
        away_attack = core["away_xg"] if core["away_xg"] is not None else core["away_shots"]
        split = _team_corner_split(core["corners_total"], home_attack, away_attack)
        out["team_corners"] = {
            "home": {**_team_goal_market(split["home_corners_proj"], TEAM_CORNER_LINES),
                     "projection": split["home_corners_proj"]},
            "away": {**_team_goal_market(split["away_corners_proj"], TEAM_CORNER_LINES),
                     "projection": split["away_corners_proj"]},
            "split_method": split["split_method"],
        }
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
