#!/usr/bin/env python
"""
LIVE Match Analysis — FIFA World Cup 2026
New Zealand vs Egypt — Group G
Venue: BC Place, Vancouver | 13th Minute | 0-0

Covers: Goals, BTTS, Corners, Match Outcome, Player Props (Goalscorer)
Pushes strong bets and full analysis to Discord.
"""

import os
import sys
import json
import math
import datetime as _dt
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# MultiSportModel imports
# ---------------------------------------------------------------------------
from MultiSportModel import (
    team_goal_strength,
    team_btts_strength,
    team_corner_strength,
    estimate_team_goals,
    estimate_btts_prob,
    estimate_corner_total,
    poisson_over_prob,
    poisson_at_least_one,
    market_recommendation,
    btts_recommendation,
    get_league_config,
)
from core.confidence_engine import confidence_score, bet_recommendation


# ===========================================================================
# TEAM DATA — calibrated to World Cup 2026 context
# ===========================================================================

# New Zealand (4-4-2) — Group G, drew vs Iran in opening match
# Elijah Just scored in 6th min; Chris Wood had 4 shots; limited quality overall
NZ_DATA = {
    "xg_for":              0.85,   # modest attacking threat
    "xg_against":          1.45,   # vulnerable vs quality opposition
    "shots":               9.5,
    "sot":                 3.2,
    "goals_for":           0.85,
    "goals_against":       1.35,
    "clean_sheets":        3,      # out of last 10 matches
    "missing_attacker":    0,
    "missing_creator":     0,
    "missing_cb":          0,
    "missing_gk":          0,
    "tempo":               0.05,
    "width_crossing":      0.50,
    "final_third_pressure": 0.38,
}

# Egypt (4-2-3-1) — drew vs Belgium; Ashour scored (19th), Salah assist, Marmoush 0.63 xG
EGYPT_DATA = {
    "xg_for":              1.35,   # dangerous: Salah + Marmoush + Ashour
    "xg_against":          1.15,   # compact defensive block
    "shots":               12.0,
    "sot":                 4.5,
    "goals_for":           1.30,
    "goals_against":       1.05,
    "clean_sheets":        4,
    "missing_attacker":    0,
    "missing_creator":     0,
    "missing_cb":          0,
    "missing_gk":          0,
    "tempo":               0.25,
    "width_crossing":      0.62,
    "final_third_pressure": 0.52,
}

# Market lines (pre-match / live opening)
MARKET = {
    "goals_line":    2.5,
    "corner_line":   8.5,
    "corner_line2":  9.5,
    "current_line":  2.5,
    "open_line":     2.5,
    # Implied probabilities from market odds
    "egypt_ml_implied":  0.636,   # -175 → 63.6%
    "draw_implied":      0.244,   # +310 → 24.4%
    "nz_ml_implied":     0.167,   # +500 → 16.7%
    "over25_implied":    0.452,   # +122 → 45.2%
}

# Player prop implied probabilities (first-goal odds)
PLAYER_PROPS = [
    {"name": "Mohamed Salah",   "team": "Egypt",       "odds": "+340",  "implied": 0.227},
    {"name": "Omar Marmoush",   "team": "Egypt",       "odds": "+500",  "implied": 0.167},
    {"name": "Chris Wood",      "team": "New Zealand", "odds": "+800",  "implied": 0.111},
    {"name": "Emam Ashour",     "team": "Egypt",       "odds": "+1000", "implied": 0.091},
    {"name": "Elijah Just",     "team": "New Zealand", "odds": "+1100", "implied": 0.083},
]

# Estimated xG share for goalscorer props (proportion of team xG assigned to each player)
PLAYER_XG_SHARE = {
    "Mohamed Salah":  0.35,   # world-class; handles PKs
    "Omar Marmoush":  0.28,   # 0.63 xG vs Belgium, 5 shots
    "Emam Ashour":    0.18,   # scored vs Belgium (19th min)
    "Chris Wood":     0.42,   # 4 shots vs Iran; primary NZ striker
    "Elijah Just":    0.25,   # scored in 6th min vs Iran
}


# ===========================================================================
# CORE ANALYSIS
# ===========================================================================

def run_analysis():
    print()
    print("=" * 80)
    print("FIFA WORLD CUP 2026 — GROUP G (LIVE · 13th Minute · 0-0)")
    print("  NEW ZEALAND  vs  EGYPT")
    print("  Venue: BC Place, Vancouver")
    print("=" * 80)
    print()

    league = "default"   # World Cup neutral-venue → use default config (goal_variance=1.0)
    config = get_league_config(league)
    WORLD_CUP_FACTOR = 0.90   # defensive structure adjustment for WC group stage

    # ------------------------------------------------------------------ #
    # 1. TEAM ANALYSIS                                                    #
    # ------------------------------------------------------------------ #
    print("1. TEAM OFFENSIVE / DEFENSIVE PROFILE")
    print("-" * 40)
    print(f"   New Zealand   | xG For: {NZ_DATA['xg_for']:.2f}  xG Against: {NZ_DATA['xg_against']:.2f}"
          f"  Shots: {NZ_DATA['shots']:.0f}  SoT: {NZ_DATA['sot']:.1f}")
    print(f"                  Goals For: {NZ_DATA['goals_for']:.2f}  Goals Against: {NZ_DATA['goals_against']:.2f}"
          f"  Clean Sheets: {NZ_DATA['clean_sheets']}/10")
    print()
    print(f"   Egypt          | xG For: {EGYPT_DATA['xg_for']:.2f}  xG Against: {EGYPT_DATA['xg_against']:.2f}"
          f"  Shots: {EGYPT_DATA['shots']:.0f}  SoT: {EGYPT_DATA['sot']:.1f}")
    print(f"                  Goals For: {EGYPT_DATA['goals_for']:.2f}  Goals Against: {EGYPT_DATA['goals_against']:.2f}"
          f"  Clean Sheets: {EGYPT_DATA['clean_sheets']}/10")
    print()

    # ------------------------------------------------------------------ #
    # 2. GOAL STRENGTH                                                    #
    # ------------------------------------------------------------------ #
    print("2. GOAL STRENGTH")
    print("-" * 40)

    # Neutral venue → home=0 for both
    nz_gs = team_goal_strength(
        NZ_DATA['xg_for'],    NZ_DATA['xg_against'],    NZ_DATA['shots'],   NZ_DATA['sot'],
        NZ_DATA['goals_for'], NZ_DATA['goals_against'],  NZ_DATA['tempo'],  0,
        NZ_DATA['missing_attacker'], NZ_DATA['missing_creator'],
        NZ_DATA['missing_cb'],       NZ_DATA['missing_gk'],
    )
    egypt_gs = team_goal_strength(
        EGYPT_DATA['xg_for'],    EGYPT_DATA['xg_against'],    EGYPT_DATA['shots'],   EGYPT_DATA['sot'],
        EGYPT_DATA['goals_for'], EGYPT_DATA['goals_against'],  EGYPT_DATA['tempo'],  0,
        EGYPT_DATA['missing_attacker'], EGYPT_DATA['missing_creator'],
        EGYPT_DATA['missing_cb'],       EGYPT_DATA['missing_gk'],
    )
    print(f"   New Zealand Goal Strength : {nz_gs:+.2f}")
    print(f"   Egypt Goal Strength       : {egypt_gs:+.2f}")
    print(f"   Strength Diff (EGY - NZL) : {egypt_gs - nz_gs:+.2f}  → Egypt advantage")
    print()

    # ------------------------------------------------------------------ #
    # 3. EXPECTED GOALS                                                   #
    # ------------------------------------------------------------------ #
    print("3. EXPECTED GOALS PROJECTION")
    print("-" * 40)

    nz_lam = estimate_team_goals(
        NZ_DATA['xg_for'],    NZ_DATA['sot'],    NZ_DATA['tempo'],   0,
        NZ_DATA['missing_attacker'],   NZ_DATA['missing_creator'],
        EGYPT_DATA['xg_against'],      EGYPT_DATA['missing_cb'], EGYPT_DATA['missing_gk'],
    )
    egypt_lam = estimate_team_goals(
        EGYPT_DATA['xg_for'],  EGYPT_DATA['sot'],  EGYPT_DATA['tempo'], 0,
        EGYPT_DATA['missing_attacker'], EGYPT_DATA['missing_creator'],
        NZ_DATA['xg_against'],          NZ_DATA['missing_cb'],    NZ_DATA['missing_gk'],
    )

    # Apply league config + World Cup neutral-venue defensive factor
    nz_lam    *= config['goal_variance'] * WORLD_CUP_FACTOR
    egypt_lam *= config['goal_variance'] * WORLD_CUP_FACTOR

    total_lam = nz_lam + egypt_lam

    p_over_15 = poisson_over_prob(total_lam, 1.5)
    p_over_25 = poisson_over_prob(total_lam, 2.5)
    p_over_35 = poisson_over_prob(total_lam, 3.5)

    print(f"   New Zealand  Expected Goals : {nz_lam:.2f}")
    print(f"   Egypt        Expected Goals : {egypt_lam:.2f}")
    print(f"   Total Expected Goals        : {total_lam:.2f}")
    print()
    print(f"   Over 1.5 Goals  : {p_over_15:.1%}")
    print(f"   Over 2.5 Goals  : {p_over_25:.1%}   (market implied: {MARKET['over25_implied']:.1%})")
    print(f"   Over 3.5 Goals  : {p_over_35:.1%}")
    print()

    goals_edge = total_lam - MARKET['goals_line']
    goals_conf = confidence_score(goals_edge * 10, volatility=0.55)
    goals_lean = market_recommendation(p_over_25, MARKET['goals_line'])
    print(f"   Goals Lean      : {goals_lean}  (conf: {goals_conf:.1f}%)")
    print()

    # ------------------------------------------------------------------ #
    # 4. BTTS                                                             #
    # ------------------------------------------------------------------ #
    print("4. BOTH TEAMS TO SCORE (BTTS)")
    print("-" * 40)

    nz_btts = team_btts_strength(
        NZ_DATA['xg_for'],    NZ_DATA['xg_against'],    NZ_DATA['goals_for'],   NZ_DATA['goals_against'],
        NZ_DATA['sot'],       NZ_DATA['tempo'],          NZ_DATA['final_third_pressure'],
        NZ_DATA['missing_attacker'], NZ_DATA['missing_cb'], NZ_DATA['missing_gk'],
        NZ_DATA['clean_sheets'],
    )
    egypt_btts = team_btts_strength(
        EGYPT_DATA['xg_for'],    EGYPT_DATA['xg_against'],    EGYPT_DATA['goals_for'],   EGYPT_DATA['goals_against'],
        EGYPT_DATA['sot'],       EGYPT_DATA['tempo'],          EGYPT_DATA['final_third_pressure'],
        EGYPT_DATA['missing_attacker'], EGYPT_DATA['missing_cb'], EGYPT_DATA['missing_gk'],
        EGYPT_DATA['clean_sheets'],
    )
    btts_raw = estimate_btts_prob(nz_lam, egypt_lam, nz_btts, egypt_btts)

    # World Cup defensive adjustment + tempo/missing-defender micro factors
    missing_def_factor = (
        NZ_DATA['missing_cb'] + NZ_DATA['missing_gk'] +
        EGYPT_DATA['missing_cb'] + EGYPT_DATA['missing_gk']
    ) * 0.02
    tempo_factor = (NZ_DATA['tempo'] + EGYPT_DATA['tempo']) * 0.03
    btts_prob = max(0.0, min(1.0, btts_raw + missing_def_factor + tempo_factor))
    btts_prob *= WORLD_CUP_FACTOR   # WC group-stage defensive caution

    btts_edge = (btts_prob - 0.50) * 100
    btts_conf = confidence_score(btts_edge, volatility=0.48)
    btts_lean = btts_recommendation(btts_prob)

    print(f"   NZ BTTS Strength     : {nz_btts:+.2f}")
    print(f"   Egypt BTTS Strength  : {egypt_btts:+.2f}")
    print(f"   BTTS Probability     : {btts_prob:.1%}")
    print(f"   BTTS Confidence      : {btts_conf:.1f}%")
    print(f"   BTTS Recommendation  : {btts_lean}")
    print()

    # ------------------------------------------------------------------ #
    # 5. CORNERS                                                          #
    # ------------------------------------------------------------------ #
    print("5. CORNERS PROJECTION")
    print("-" * 40)

    nz_cs = team_corner_strength(
        NZ_DATA['shots'],  NZ_DATA['sot'],  NZ_DATA['final_third_pressure'],
        NZ_DATA['width_crossing'],  NZ_DATA['tempo'],  0,
        NZ_DATA['missing_cb'],  NZ_DATA['missing_gk'],  NZ_DATA['missing_attacker'],
    )
    egypt_cs = team_corner_strength(
        EGYPT_DATA['shots'],  EGYPT_DATA['sot'],  EGYPT_DATA['final_third_pressure'],
        EGYPT_DATA['width_crossing'],  EGYPT_DATA['tempo'],  0,
        EGYPT_DATA['missing_cb'],  EGYPT_DATA['missing_gk'],  EGYPT_DATA['missing_attacker'],
    )
    # Egypt must-win pressure (need 1st WC win) adds corner volume
    corner_total = estimate_corner_total(
        nz_cs, egypt_cs,
        weather_penalty=0,
        referee_flow=0,
        must_win_home=0,    # NZ would settle for a draw
        must_win_away=1,    # Egypt pressing for 1st WC win
    )
    p_corners_85 = poisson_over_prob(corner_total, 8.5)
    p_corners_95 = poisson_over_prob(corner_total, 9.5)
    p_corners_105 = poisson_over_prob(corner_total, 10.5)

    print(f"   NZ Corner Strength    : {nz_cs:+.2f}")
    print(f"   Egypt Corner Strength : {egypt_cs:+.2f}")
    print(f"   Projected Corners     : {corner_total:.1f}")
    print()
    print(f"   Over 8.5  Corners : {p_corners_85:.1%}")
    print(f"   Over 9.5  Corners : {p_corners_95:.1%}")
    print(f"   Over 10.5 Corners : {p_corners_105:.1%}")
    print()

    # ------------------------------------------------------------------ #
    # 6. MATCH OUTCOME                                                    #
    # ------------------------------------------------------------------ #
    print("6. MATCH OUTCOME PROJECTION")
    print("-" * 40)

    # Simple ratio method (Poisson-based)
    raw_nz_win   = (nz_lam / total_lam) * 0.75 + 0.05
    raw_egypt_win = (egypt_lam / total_lam) * 0.75 + 0.05
    raw_draw      = max(0.0, 1 - raw_nz_win - raw_egypt_win)

    # Enforce World Cup draw floor
    if raw_draw < 0.20:
        raw_draw = 0.20
        norm = raw_nz_win + raw_egypt_win
        if norm > 0:
            raw_nz_win   *= (1 - raw_draw) / norm
            raw_egypt_win *= (1 - raw_draw) / norm

    # Blend with Opta/market consensus (Opta: EGY 59.6%, Draw 22.7%, NZ 17.7%)
    OPTA_EGY  = 0.596
    OPTA_DRAW = 0.227
    OPTA_NZ   = 0.177
    BLEND = 0.55   # weight to Opta/market consensus

    egypt_win_prob = BLEND * OPTA_EGY   + (1 - BLEND) * raw_egypt_win
    draw_prob      = BLEND * OPTA_DRAW  + (1 - BLEND) * raw_draw
    nz_win_prob    = BLEND * OPTA_NZ    + (1 - BLEND) * raw_nz_win

    # Normalize
    total_prob = egypt_win_prob + draw_prob + nz_win_prob
    egypt_win_prob /= total_prob
    draw_prob      /= total_prob
    nz_win_prob    /= total_prob

    print(f"   New Zealand Win : {nz_win_prob:.1%}  (market implied: {MARKET['nz_ml_implied']:.1%})")
    print(f"   Draw            : {draw_prob:.1%}  (market implied: {MARKET['draw_implied']:.1%})")
    print(f"   Egypt Win       : {egypt_win_prob:.1%}  (market implied: {MARKET['egypt_ml_implied']:.1%})")
    print()

    if egypt_win_prob >= 0.55:
        outcome_lean = "Egypt Win"
    elif nz_win_prob >= 0.45:
        outcome_lean = "New Zealand Win"
    elif draw_prob >= 0.30:
        outcome_lean = "Draw"
    else:
        outcome_lean = "Pass"
    print(f"   Outcome Lean : {outcome_lean}")
    print()

    # ------------------------------------------------------------------ #
    # 7. PLAYER PROP — GOALSCORER ANALYSIS                                #
    # ------------------------------------------------------------------ #
    print("7. PLAYER PROP — FIRST GOALSCORER")
    print("-" * 40)
    print(f"   Total Expected Goals : {total_lam:.2f}")
    print(f"   P(at least 1 goal)   : {poisson_at_least_one(total_lam):.1%}")
    print()

    prop_results = []
    for prop in PLAYER_PROPS:
        player  = prop["name"]
        team    = prop["team"]
        odds    = prop["odds"]
        implied = prop["implied"]

        team_lam = egypt_lam if team == "Egypt" else nz_lam
        share    = PLAYER_XG_SHARE.get(player, 0.20)
        player_xg = team_lam * share

        anytime_prob  = 1 - math.exp(-player_xg)
        # P(first goal) ≈ player_xG / total_xG * P(at least 1 goal)
        p_at_least_1  = 1 - math.exp(-total_lam)
        first_goal_prob = (player_xg / total_lam) * p_at_least_1

        edge_pct = (first_goal_prob - implied) * 100
        edge_label = f"{edge_pct:+.1f}%"

        if first_goal_prob >= implied * 1.20:
            rec = "VALUE BET"
        elif first_goal_prob >= implied * 1.08:
            rec = "slight value"
        elif first_goal_prob >= implied * 0.92:
            rec = "fair value"
        else:
            rec = "overpriced"

        prop_results.append({
            "name": player,
            "team": team,
            "odds": odds,
            "implied": implied,
            "player_xg": round(player_xg, 3),
            "anytime_prob": round(anytime_prob, 3),
            "first_goal_prob": round(first_goal_prob, 3),
            "edge_pct": round(edge_pct, 1),
            "rec": rec,
        })

        print(f"   {player:<20} ({team:<15}) | Odds: {odds:<7} Implied: {implied:.1%}"
              f"  | Model: {first_goal_prob:.1%}  Edge: {edge_label}  → {rec}")

    print()

    # ------------------------------------------------------------------ #
    # 8. FINAL SUMMARY                                                    #
    # ------------------------------------------------------------------ #
    print("=" * 80)
    print("FINAL ANALYSIS SUMMARY")
    print("=" * 80)
    print()
    print(f"   Match          : New Zealand vs Egypt — FIFA World Cup 2026 Group G")
    print(f"   Status         : LIVE (13th Minute, 0-0)")
    print(f"   Venue          : BC Place, Vancouver")
    print()
    print(f"   Projected Score: NZL {nz_lam:.1f} – EGY {egypt_lam:.1f}")
    print(f"   Total xG       : {total_lam:.2f}")
    print()
    print(f"   Egypt Win      : {egypt_win_prob:.1%}")
    print(f"   Draw           : {draw_prob:.1%}")
    print(f"   NZ Win         : {nz_win_prob:.1%}")
    print()
    print(f"   Over 2.5 Goals : {p_over_25:.1%}  (model edge vs +122: +{(p_over_25 - MARKET['over25_implied'])*100:.1f}%)")
    print(f"   BTTS           : {btts_prob:.1%}  → {btts_lean}")
    print(f"   Corners        : {corner_total:.1f} projected")
    print()

    # Build bet tiers
    strong_bets  = []
    medium_bets  = []
    pass_bets    = []

    # Over 2.5 Goals
    over25_edge = p_over_25 - MARKET['over25_implied']
    over25_conf = confidence_score(over25_edge * 100, volatility=0.55)
    if p_over_25 >= 0.57:
        strong_bets.append({
            "name": f"⚽ Over 2.5 Goals (+122)",
            "prob": round(p_over_25 * 100, 1),
            "edge": f"Model {p_over_25:.1%} vs implied {MARKET['over25_implied']:.1%} (+{over25_edge*100:.1f}%)",
        })
    elif p_over_25 >= 0.52:
        medium_bets.append({
            "name": f"⚽ Over 2.5 Goals (+122)",
            "prob": round(p_over_25 * 100, 1),
            "edge": f"Model {p_over_25:.1%} vs implied {MARKET['over25_implied']:.1%}",
        })
    else:
        pass_bets.append({
            "name": "⚽ Over 2.5 Goals (+122)",
            "prob": round(p_over_25 * 100, 1),
            "edge": "insufficient model edge",
        })

    # Corners Over 8.5
    if p_corners_85 >= 0.67:
        strong_bets.append({
            "name": "📐 Corners Over 8.5",
            "prob": round(p_corners_85 * 100, 1),
            "edge": f"Projected {corner_total:.1f} corners | Egypt pressing for 1st WC win",
        })
    elif p_corners_85 >= 0.58:
        medium_bets.append({
            "name": "📐 Corners Over 8.5",
            "prob": round(p_corners_85 * 100, 1),
            "edge": f"Projected {corner_total:.1f} corners",
        })

    # Corners Over 9.5
    if p_corners_95 >= 0.58:
        medium_bets.append({
            "name": "📐 Corners Over 9.5",
            "prob": round(p_corners_95 * 100, 1),
            "edge": f"Projected {corner_total:.1f} corners",
        })

    # BTTS
    if btts_prob >= 0.57:
        strong_bets.append({
            "name": "🤝 BTTS Yes",
            "prob": round(btts_prob * 100, 1),
            "edge": f"NZ scored vs Iran (6th min); Egypt scored vs Belgium (19th min)",
        })
    elif btts_prob >= 0.52:
        medium_bets.append({
            "name": "🤝 BTTS Yes",
            "prob": round(btts_prob * 100, 1),
            "edge": f"Both teams scored in Matchday 1",
        })

    # Egypt ML — market says -175 (63.6%), model closer to ~53-56%
    egypt_ml_edge = egypt_win_prob - MARKET['egypt_ml_implied']
    if egypt_ml_edge > 0.05:
        strong_bets.append({
            "name": f"🇪🇬 Egypt ML (-175)",
            "prob": round(egypt_win_prob * 100, 1),
            "edge": f"Model {egypt_win_prob:.1%} vs implied {MARKET['egypt_ml_implied']:.1%}",
        })
    else:
        pass_bets.append({
            "name": "🇪🇬 Egypt ML (-175)",
            "prob": round(egypt_win_prob * 100, 1),
            "edge": "Market slightly overprices Egypt; no edge",
        })

    # Player props
    value_props = [p for p in prop_results if p["rec"] in ("VALUE BET", "slight value")]
    for vp in value_props:
        entry = {
            "name": f"👤 {vp['name']} First Goal ({vp['odds']})",
            "prob": round(vp["first_goal_prob"] * 100, 1),
            "edge": f"Model {vp['first_goal_prob']:.1%} vs implied {vp['implied']:.1%} ({vp['edge_pct']:+.1f}%)",
        }
        if vp["rec"] == "VALUE BET":
            strong_bets.append(entry)
        else:
            medium_bets.append(entry)

    # Anything not in strong/medium goes to pass
    all_prop_names = {p["name"] for p in prop_results}
    covered = {b["name"].split(" First")[0].replace("👤 ", "").strip() for b in strong_bets + medium_bets
               if "First Goal" in b["name"]}
    for p in prop_results:
        if p["name"] not in covered and p["rec"] not in ("VALUE BET", "slight value"):
            pass_bets.append({
                "name": f"👤 {p['name']} First Goal ({p['odds']})",
                "prob": round(p["first_goal_prob"] * 100, 1),
                "edge": p["rec"],
            })

    print("   BET TIERS:")
    print(f"   STRONG  ({len(strong_bets)}): " + " | ".join(b["name"] for b in strong_bets))
    print(f"   MEDIUM  ({len(medium_bets)}): " + " | ".join(b["name"] for b in medium_bets))
    print(f"   PASS    ({len(pass_bets)}): "   + " | ".join(b["name"] for b in pass_bets))
    print()

    # ------------------------------------------------------------------ #
    # 9. SAVE JSON                                                        #
    # ------------------------------------------------------------------ #
    results = {
        "match": {
            "home":        "New Zealand",
            "away":        "Egypt",
            "competition": "FIFA World Cup 2026",
            "group":       "G",
            "venue":       "BC Place, Vancouver",
            "status":      "LIVE — 13th Minute, 0-0",
            "date":        "2026-06-21",
        },
        "projections": {
            "nz_xg":             round(nz_lam, 2),
            "egypt_xg":          round(egypt_lam, 2),
            "total_xg":          round(total_lam, 2),
            "nz_win_prob":       round(nz_win_prob, 3),
            "draw_prob":         round(draw_prob, 3),
            "egypt_win_prob":    round(egypt_win_prob, 3),
        },
        "goals": {
            "over_15":        round(p_over_15, 3),
            "over_25":        round(p_over_25, 3),
            "over_35":        round(p_over_35, 3),
            "lean":           goals_lean,
            "confidence_pct": round(goals_conf, 1),
        },
        "btts": {
            "probability": round(btts_prob, 3),
            "confidence":  round(btts_conf, 1),
            "lean":        btts_lean,
        },
        "corners": {
            "projected":     round(corner_total, 1),
            "over_85":       round(p_corners_85, 3),
            "over_95":       round(p_corners_95, 3),
            "over_105":      round(p_corners_105, 3),
        },
        "player_props":  prop_results,
        "strong_bets":   strong_bets,
        "medium_bets":   medium_bets,
        "pass_bets":     pass_bets,
        "timestamp":     datetime.now().isoformat(),
    }

    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "new_zealand_vs_egypt_wc2026_analysis.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"   Results saved to: {out_path}")
    print()

    return results


# ===========================================================================
# DISCORD PUSH
# ===========================================================================

def push_to_discord(results: dict) -> bool:
    """Push full analysis + strong bets to Discord via webhook."""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("❌  DISCORD_WEBHOOK_URL not set in .env")
        return False

    p = results["projections"]
    g = results["goals"]
    b = results["btts"]
    c = results["corners"]
    strong = results["strong_bets"]
    medium = results["medium_bets"]
    pass_  = results["pass_bets"]
    props  = results["player_props"]

    fields = []

    # --- Match Status ---
    fields.append({
        "name": "📍 LIVE MATCH STATUS",
        "value": (
            "🟡 **13th Minute  |  0 - 0**\n"
            "🏟️ BC Place, Vancouver\n"
            "🏆 FIFA World Cup 2026 — Group G"
        ),
        "inline": False,
    })

    # --- Model Projections ---
    fields.append({
        "name": "📊 MODEL PROJECTIONS",
        "value": (
            f"• **NZL xG:** {p['nz_xg']}  |  **EGY xG:** {p['egypt_xg']}\n"
            f"• **Total xG:** {p['total_xg']}  |  Corners: **{c['projected']}** proj.\n"
            f"• NZ Win: **{p['nz_win_prob']:.1%}**  Draw: **{p['draw_prob']:.1%}**  Egypt Win: **{p['egypt_win_prob']:.1%}**\n"
            f"• Over 1.5: **{g['over_15']:.1%}**  Over 2.5: **{g['over_25']:.1%}**  Over 3.5: **{g['over_35']:.1%}**\n"
            f"• BTTS: **{b['probability']:.1%}**  ({b['lean']})"
        ),
        "inline": False,
    })

    # --- Strong Bets ---
    if strong:
        strong_lines = []
        for bet in strong:
            strong_lines.append(f"🟢 **{bet['name']}** — {bet['prob']:.1f}%\n   └ {bet['edge']}")
        fields.append({
            "name": f"💪 STRONG BETS ({len(strong)})",
            "value": "\n".join(strong_lines),
            "inline": False,
        })

    # --- Medium Bets ---
    if medium:
        med_lines = []
        for bet in medium:
            med_lines.append(f"🟡 **{bet['name']}** — {bet['prob']:.1f}%\n   └ {bet['edge']}")
        fields.append({
            "name": f"⚠️ MEDIUM BETS ({len(medium)})",
            "value": "\n".join(med_lines),
            "inline": False,
        })

    # --- Pass ---
    if pass_:
        pass_lines = []
        for bet in pass_:
            pass_lines.append(f"🔴 {bet['name']} — {bet['prob']:.1f}%  ({bet['edge']})")
        fields.append({
            "name": f"❌ PASS ({len(pass_)})",
            "value": "\n".join(pass_lines),
            "inline": False,
        })

    # --- Player Props Detail ---
    prop_lines = []
    for prop in props:
        tag = "🔥" if prop["rec"] == "VALUE BET" else ("➕" if prop["rec"] == "slight value" else "➖")
        prop_lines.append(
            f"{tag} **{prop['name']}** ({prop['team']}) {prop['odds']}\n"
            f"   └ Implied {prop['implied']:.1%} | Model {prop['first_goal_prob']:.1%} | Edge {prop['edge_pct']:+.1f}% → *{prop['rec']}*"
        )
    fields.append({
        "name": "🎯 GOALSCORER PROP ANALYSIS",
        "value": "\n".join(prop_lines),
        "inline": False,
    })

    # --- Tactical Context ---
    fields.append({
        "name": "📋 TACTICAL CONTEXT",
        "value": (
            "• **Egypt (-175)**: Salah leads attack on right, Marmoush CF (0.63 xG vs BEL)\n"
            "• **NZ (+500)**: 4-4-2 compact; Just scored 6th min vs Iran; Wood 4 shots vs Iran\n"
            "• Both teams scored early in Matchday 1 (Just 6', Ashour 19')\n"
            "• Neutral venue — no true home advantage\n"
            "• Opta: EGY 59.6% | Draw 22.7% | NZ 17.7%"
        ),
        "inline": False,
    })

    embed = {
        "title": "⚽  NEW ZEALAND  vs  EGYPT  — LIVE ANALYSIS",
        "description": (
            "**FIFA World Cup 2026 · Group G · 13' · 0-0**\n"
            "Full model analysis + betting recommendations"
        ),
        "color": 0x00B16A,    # green
        "fields": fields,
        "footer": {"text": "MultiSportPredict · World Cup 2026 Live Feed"},
        "timestamp": datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    payload = {"embeds": [embed]}

    try:
        resp = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        if resp.status_code in (200, 204):
            return True
        print(f"❌  Discord returned HTTP {resp.status_code}: {resp.text[:200]}")
        return False
    except requests.exceptions.RequestException as exc:
        print(f"❌  Request failed: {exc}")
        return False


# ===========================================================================
# ENTRY POINT
# ===========================================================================

if __name__ == "__main__":
    results = run_analysis()

    print("=" * 80)
    print("PUSHING TO DISCORD ...")
    print("=" * 80)

    if push_to_discord(results):
        print("✅  Analysis successfully pushed to Discord!")
        print()
        print("   STRONG BETS SENT:")
        for b in results["strong_bets"]:
            print(f"      • {b['name']}  ({b['prob']:.1f}%)")
        print()
        print("   MEDIUM BETS SENT:")
        for b in results["medium_bets"]:
            print(f"      • {b['name']}  ({b['prob']:.1f}%)")
    else:
        print("❌  Discord push failed.")
