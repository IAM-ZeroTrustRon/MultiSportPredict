#!/usr/bin/env python
"""
Wimbledon 2026 — Fourth Round (R16), July 6, 2026
==================================================
Match: Jiri Lehecka (#13) vs Alexander Zverev (#2) — Men's Singles R16

Scout Intel:
  - Zverev: 2026 French Open champion, dropped only 1 set in R1-R3, dispatched Giron easily.
    Historically poor Wimbledon record but has flipped the script in 2026.
    Model: ~75% win probability. Market: -303 ($1.33).
  - Lehecka: No. 13 seed, favorable draw, dropped only 1 set. ELITE serve on grass:
    48 aces in 3 rounds = 16/match. Sharps pounding his Aces Over 12.5.
  - H2H: 1-1 (both 2023) — no mental edge either direction.
  - Sharp Pick: Zverev -1.5 Sets (-166) — safety vs steep -303 ML.
  - Total Games O/U: ~40.5 | Over 3.5 Sets: ~+120 (Lehecka serve keeps sets close).
  - Umpire factor: strict 25s clock disrupts Zverev's deliberate rhythm → double faults.

Pushes rich analysis + player props + betting slip to Discord.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import requests
from dotenv import load_dotenv

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def prob_to_american(p: float) -> str:
    p = clamp(p, 0.001, 0.999)
    if p >= 0.5:
        return str(-round((p / (1 - p)) * 100))
    return f"+{round(((1 - p) / p) * 100)}"


def american_to_decimal(s: str) -> float:
    v = int(s.replace("+", ""))
    return round(1 + (100 / abs(v)), 2) if v < 0 else round(1 + (v / 100), 2)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PlayerProfile:
    name: str
    grass_skill: float          # 0-100
    serve_power: float          # 0-100
    return_quality: float       # 0-100
    form: float                 # 0-100
    experience: float           # 0-100
    court_coverage: float = 65.0
    ball_striking_weight: float = 65.0
    mental_focus: float = 65.0  # 0-100 — variance resistance
    home_boost: float = 0.0
    fatigue: float = 0.0        # 0-10 penalty


@dataclass
class MatchInput:
    event: str
    round_name: str
    court: str
    player_a: PlayerProfile
    player_b: PlayerProfile
    player_a_rank: str
    player_b_rank: str
    start_time_edt: str
    market_favorite: str
    market_ml_favorite: float       # implied probability
    market_ml_favorite_odds: str    # e.g. "-303"
    market_ml_underdog_odds: str    # e.g. "+237"
    spread_fav_odds: str = ""       # e.g. "-166" for Zverev -1.5
    spread_dog_odds: str = ""       # e.g. "+122" for Lehecka +1.5
    games_ou_line: float = 40.5
    h2h_note: str = ""
    notes: str = ""
    sharp_consensus: str = ""
    umpire_notes: str = ""
    scout_intel: str = ""
    exact_score_prediction: str = ""


@dataclass
class MatchOutput:
    event: str
    round_name: str
    court: str
    start_time: str
    player_a: str
    player_b: str
    player_a_rank: str
    player_b_rank: str
    a_win_prob: float
    b_win_prob: float
    a_fair_odds: str
    b_fair_odds: str
    a_fair_decimal: float
    b_fair_decimal: float
    model_favorite: str
    model_fav_prob: float
    market_fav_prob: float
    market_ml_favorite_odds: str
    market_ml_underdog_odds: str
    spread_fav_odds: str
    spread_dog_odds: str
    games_ou_line: float
    model_edge_vs_market_pct: float
    dominance_ratio_a: float
    dominance_ratio_b: float
    recommendation_ml: str
    recommendation_sets_ou: str
    recommendation_spread: str
    confidence_ml: float
    set_dist: dict
    p_over_35: float
    p_fav_spread: float
    analysis_summary: str
    sharp_consensus: str
    umpire_notes: str
    scout_intel: str
    stylistic_edge: str
    exact_score_prediction: str
    h2h_note: str


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def _strength(p: PlayerProfile) -> float:
    """Wimbledon-tuned weighted strength score."""
    base = (
        0.17 * p.grass_skill
        + 0.21 * p.serve_power
        + 0.14 * p.return_quality
        + 0.13 * p.form
        + 0.09 * p.experience
        + 0.11 * p.court_coverage
        + 0.08 * p.ball_striking_weight
        + 0.07 * p.mental_focus
    )
    base += p.home_boost
    base -= p.fatigue * 0.9
    return base


def _dr(p: PlayerProfile) -> float:
    """Dominance Ratio = RPW% / (1 - SPW%)."""
    spw = clamp(0.50 + (p.serve_power / 100.0) * 0.27 + (p.grass_skill / 100.0) * 0.08, 0.55, 0.87)
    rpw = clamp(0.20 + (p.return_quality / 100.0) * 0.24 + (p.form / 100.0) * 0.07, 0.18, 0.50)
    return round(rpw / (1.0 - spw), 4) if spw < 1.0 else 0.0


def _win_prob(a_str: float, b_str: float) -> float:
    delta = a_str - b_str
    return clamp(1.0 / (1.0 + math.exp(-(delta / 7.5))), 0.05, 0.95)


def _conf(p: float) -> float:
    return round(clamp(50 + abs(p - 0.5) * 125, 0, 98), 1)


def _set_dist(p: float) -> dict:
    """Best-of-5 set-score distribution (simplified empirical model)."""
    q = 1.0 - p
    w30 = p**3 * 1.00
    w31 = p**3 * q * 2.50
    w32 = p**3 * q**2 * 2.00
    l30 = q**3 * 1.00
    l31 = q**3 * p * 2.50
    l32 = q**3 * p**2 * 2.00
    tot = w30 + w31 + w32 + l30 + l31 + l32
    return {k: round(v / tot, 3) for k, v in
            [("3-0", w30), ("3-1", w31), ("3-2", w32),
             ("0-3", l30), ("1-3", l31), ("2-3", l32)]}


def _stylistic_edge(a: PlayerProfile, b: PlayerProfile) -> str:
    parts = []
    if a.serve_power > b.serve_power + 8:
        parts.append(f"{a.name}'s bigger serve ({a.serve_power:.0f}/100) = free points on grass")
    elif b.serve_power > a.serve_power + 8:
        parts.append(f"{b.name}'s bigger serve ({b.serve_power:.0f}/100) = free points on grass")
    if a.return_quality > b.return_quality + 8:
        parts.append(f"{a.name}'s superior return game extends rallies")
    elif b.return_quality > a.return_quality + 8:
        parts.append(f"{b.name}'s superior return game extends rallies")
    if a.ball_striking_weight > b.ball_striking_weight + 8:
        parts.append(f"{a.name}'s ball-striking dominance takes over on big points")
    elif b.ball_striking_weight > a.ball_striking_weight + 8:
        parts.append(f"{b.name}'s ball-striking dominance takes over on big points")
    if a.mental_focus < b.mental_focus - 10:
        parts.append(f"{a.name}'s mental variance ({a.mental_focus:.0f}/100) = liability in crunch time")
    elif b.mental_focus < a.mental_focus - 10:
        parts.append(f"{b.name}'s mental variance ({b.mental_focus:.0f}/100) = liability in crunch time")
    if a.experience > b.experience + 18:
        parts.append(f"{a.name}'s Grand Slam pedigree ({a.experience:.0f} vs {b.experience:.0f}) critical in R16")
    elif b.experience > a.experience + 18:
        parts.append(f"{b.name}'s Grand Slam pedigree ({b.experience:.0f} vs {a.experience:.0f}) critical in R16")
    if a.fatigue > b.fatigue + 2:
        parts.append(f"Fatigue watch: {a.name} ({a.fatigue:.0f}) vs {b.name} ({b.fatigue:.0f})")
    elif b.fatigue > a.fatigue + 2:
        parts.append(f"Fatigue watch: {b.name} ({b.fatigue:.0f}) vs {a.name} ({a.fatigue:.0f})")
    return " | ".join(parts) if parts else "Stylistically competitive — close matchup expected"


def analyze_match(m: MatchInput) -> MatchOutput:
    a_s = _strength(m.player_a)
    b_s = _strength(m.player_b)
    a_prob = _win_prob(a_s, b_s)
    b_prob = 1.0 - a_prob

    dr_a = _dr(m.player_a)
    dr_b = _dr(m.player_b)

    sd = _set_dist(a_prob)
    p_over_35 = round(1.0 - sd["3-0"] - sd["0-3"], 3)
    p_fav_spread = round(sd["3-0"] + sd["3-1"], 3) if a_prob > b_prob else round(sd["0-3"] + sd["1-3"], 3)

    model_fav = m.player_a.name if a_prob >= b_prob else m.player_b.name
    model_fav_prob = max(a_prob, b_prob)
    edge = (model_fav_prob - m.market_ml_favorite) * 100
    conf = _conf(model_fav_prob)

    # Moneyline rec
    if edge >= 4.5 and conf >= 63:
        rec_ml = f"✅ BET {model_fav} ML"
    elif edge >= 2.0 and conf >= 57:
        rec_ml = f"📌 LEAN {model_fav} ML"
    elif edge >= 0.5:
        rec_ml = f"👀 SLIGHT LEAN {model_fav} ML"
    else:
        rec_ml = f"⚖️ PASS — Market efficient"

    # Sets O/U
    if p_over_35 >= 0.55:
        rec_ou = f"📈 OVER 3.5 Sets — P(over)={p_over_35:.0%}"
    elif p_over_35 <= 0.40:
        rec_ou = f"📉 UNDER 3.5 Sets — P(3 or 4 sets)={1 - p_over_35:.0%}"
    else:
        rec_ou = f"⚖️ LEAN OVER 3.5 Sets — P(over)={p_over_35:.0%}"

    # Spread
    if p_fav_spread >= 0.52:
        rec_spread = f"🎯 {model_fav} -1.5 Sets — P={p_fav_spread:.0%}"
    elif p_fav_spread >= 0.46:
        rec_spread = f"📌 LEAN {model_fav} -1.5 Sets — P={p_fav_spread:.0%}"
    else:
        rec_spread = f"💡 TAKE Underdog +1.5 Sets — P(fav covers)={p_fav_spread:.0%} only"

    # DR note
    if dr_a - dr_b > 0.02:
        dr_note = f"{m.player_a.name} DR edge ({dr_a:.3f} vs {dr_b:.3f})"
    elif dr_b - dr_a > 0.02:
        dr_note = f"{m.player_b.name} DR edge ({dr_b:.3f} vs {dr_a:.3f})"
    else:
        dr_note = f"DR near-equal ({dr_a:.3f} vs {dr_b:.3f})"

    fa = prob_to_american(a_prob)
    fb = prob_to_american(b_prob)

    summary = "\n".join([
        f"**Model Prob:** {m.player_a.name} **{a_prob:.1%}** | {m.player_b.name} **{b_prob:.1%}**",
        f"**Market Prob:** {m.market_favorite} **{m.market_ml_favorite:.1%}** | Edge: {edge:+.1f}%",
        f"**Fair ML:** {m.player_a.name} {fa} | {m.player_b.name} {fb}",
        f"**DR:** {dr_note}",
        f"**Set Dist:** 3-0: {sd['3-0']:.0%} | 3-1: {sd['3-1']:.0%} | 3-2: {sd['3-2']:.0%}",
        f"**P(Over 3.5):** {p_over_35:.0%} | **P({model_fav} -1.5):** {p_fav_spread:.0%}",
        m.notes,
    ])

    return MatchOutput(
        event=m.event, round_name=m.round_name, court=m.court,
        start_time=m.start_time_edt,
        player_a=m.player_a.name, player_b=m.player_b.name,
        player_a_rank=m.player_a_rank, player_b_rank=m.player_b_rank,
        a_win_prob=round(a_prob, 4), b_win_prob=round(b_prob, 4),
        a_fair_odds=fa, b_fair_odds=fb,
        a_fair_decimal=american_to_decimal(fa),
        b_fair_decimal=american_to_decimal(fb),
        model_favorite=model_fav, model_fav_prob=round(model_fav_prob, 4),
        market_fav_prob=m.market_ml_favorite,
        market_ml_favorite_odds=m.market_ml_favorite_odds,
        market_ml_underdog_odds=m.market_ml_underdog_odds,
        spread_fav_odds=m.spread_fav_odds, spread_dog_odds=m.spread_dog_odds,
        games_ou_line=m.games_ou_line,
        model_edge_vs_market_pct=round(edge, 2),
        dominance_ratio_a=dr_a, dominance_ratio_b=dr_b,
        recommendation_ml=rec_ml, recommendation_sets_ou=rec_ou,
        recommendation_spread=rec_spread, confidence_ml=conf,
        set_dist=sd, p_over_35=p_over_35, p_fav_spread=p_fav_spread,
        analysis_summary=summary,
        sharp_consensus=m.sharp_consensus, umpire_notes=m.umpire_notes,
        scout_intel=m.scout_intel,
        stylistic_edge=_stylistic_edge(m.player_a, m.player_b),
        exact_score_prediction=m.exact_score_prediction,
        h2h_note=m.h2h_note,
    )


# ---------------------------------------------------------------------------
# Match definition
# ---------------------------------------------------------------------------

def build_match() -> MatchInput:
    return MatchInput(
        event="Wimbledon 2026 — Men's Singles R16",
        round_name="Round of 16 (4th Round)",
        court="Centre Court",
        start_time_edt="~1:00 PM EDT",
        player_a=PlayerProfile(
            name="Jiri Lehecka",
            grass_skill=77,          # No. 13 seed, solid grass performer
            serve_power=87,          # ELITE: 48 aces in 3 rounds = 16/match avg
            return_quality=67,       # Decent but not a weapon — serve is the game
            form=76,                 # Dropped only 1 set, favorable draw, confident
            experience=65,           # Tour experience but no deep Slam pedigree
            court_coverage=73,       # Adequate, athletic
            ball_striking_weight=74, # Solid baseline but not a Zverev-level weapon
            mental_focus=73,         # Consistent, plays rhythmically, unaffected by clock
            home_boost=0.0,
            fatigue=1.5,             # 3 matches, dropped 1 set — light load
        ),
        player_b=PlayerProfile(
            name="Alexander Zverev",
            grass_skill=81,          # 2026 Wimbledon flip: dropped only 1 set R1-R3
                                     # Previously poor grass record now corrected
            serve_power=88,          # One of the most lethal serves on tour
            return_quality=82,       # Elite backhand + return — primary weapon
            form=91,                 # 2026 French Open champion; dominant form all year
            experience=88,           # Multiple Slam QF/SF/F runs, Grand Slam champion
            court_coverage=83,       # Excellent movement, elite baseline wingspan
            ball_striking_weight=88, # Elite backhand in crunch time — decisive weapon
            mental_focus=85,         # New Grand Slam confidence; cleaned up double faults
                                     # BUT deliberate rhythm = strict clock vulnerability
            home_boost=0.0,
            fatigue=1.5,             # 3 mostly straight-set matches, minimal mileage
        ),
        player_a_rank="#13 (Seeded)",
        player_b_rank="#2 (Seeded)",
        market_favorite="Alexander Zverev",
        market_ml_favorite=0.752,    # -303 implied: 303/403 = 75.2%
        market_ml_favorite_odds="-303",
        market_ml_underdog_odds="+237",
        spread_fav_odds="-166",      # Zverev -1.5 sets
        spread_dog_odds="+122",      # Lehecka +1.5 sets
        games_ou_line=40.5,
        h2h_note=(
            "H2H 1-1 overall (both matches 2023) — no mental edge either direction. "
            "Lehecka won one of those meetings, demonstrating he CAN take sets off Zverev."
        ),
        notes=(
            "Zverev at -303 (75.2% market) is expensive. Spread at -166 (-1.5 sets) is the "
            "sharp play — allows Lehecka to steal a set via tiebreak while still cashing. "
            "Lehecka's serve (16 aces/match avg) virtually guarantees tiebreaks even in losing sets. "
            "Key: Zverev's elite backhand wins crunch tiebreak moments; his Grand Slam confidence "
            "post-FO 2026 makes him a different player than 2025 Wimbledon."
        ),
        sharp_consensus=(
            "Predictive models place Zverev ~75% win probability — market aligned. "
            "Sharp money NOT on the moneyline (-303 is too juiced). "
            "Sharps targeting: (1) Zverev -1.5 Sets (-166 / $1.60) — safety net bet; "
            "(2) Lehecka Aces OVER 12.5 — averaging 16/match, tiebreaks = more frames = more aces; "
            "(3) Over 40.5 Total Games — two elite serves + tiebreaks = game count explodes. "
            "Over 3.5 Total Sets at ~+120 offers solid value if Lehecka's serve stays elite. "
            "Best value ticket: Zverev -1.5 Sets (-166) avoids moneyline tax while staying safe."
        ),
        umpire_notes=(
            "CRITICAL: Zverev's deliberate, methodical service motion frequently pushes the "
            "25-second serve clock. Strict enforcement = disrupted rhythm + forced double faults — "
            "a historical liability Zverev has largely corrected but not eliminated. "
            "Lehecka plays at a faster, more natural rhythm — rarely bothered by clock enforcement. "
            "A strict chair umpire on this match BENEFITS Lehecka and flattens Zverev's serve edge. "
            "A lenient umpire allows Zverev to operate at his deliberate, devastating best. "
            "Monitor first service games — umpire style will be clear within 3 games."
        ),
        scout_intel=(
            "Zverev made R1 exit at Wimbledon 2025. His 2026 grass campaign has been the most "
            "dominant of his career on this surface. French Open title has unlocked a new level "
            "of Grand Slam composure — he believes he can win any surface now. "
            "Lehecka had early exits at AO and RG 2026 but has found his game on grass. "
            "His 48-ace haul across 3 rounds is elite-tier for any stage of Wimbledon. "
            "In their 2023 meetings, Lehecka pushed Zverev to competitive sets both times — "
            "his serve neutralizes Zverev's baseline dominance in individual sets. "
            "The step up in class (unseeded draw → World #2 post-Slam champion) is the key variable."
        ),
        exact_score_prediction="Zverev 3-1",
    )


# ---------------------------------------------------------------------------
# Player Props
# ---------------------------------------------------------------------------

def build_props(r: MatchOutput) -> dict:
    def rec(p):
        if p >= 0.60:
            return "✅ Strong"
        elif p >= 0.55:
            return "⚠️ Medium"
        return "❌ Pass"

    # Lehecka: 16 aces/match avg on grass — Over 12.5 is the SHARP play
    # Zverev: ~8-10 aces/match, elite serve
    # Both: high first-serve win rate on grass — service holds dominant

    lehecka_props = [
        {"prop": "Lehecka Aces", "choice": "Over", "line": 12.5,
         "prob": 0.68, "rec": rec(0.68),
         "note": "Averaging 16/match — sharps pounding this line"},
        {"prop": "Lehecka Service Holds", "choice": "Over 80%", "line": "80%",
         "prob": 0.64, "rec": rec(0.64),
         "note": "Big serve on grass holds at elite rate"},
        {"prop": "Lehecka to Win 1st Set", "choice": "Yes", "line": "+175",
         "prob": 0.36, "rec": rec(0.36),
         "note": "Crowd + serve burst; Zverev settling in"},
        {"prop": "Lehecka Break Points Saved", "choice": "Over 3.5", "line": 3.5,
         "prob": 0.59, "rec": rec(0.59),
         "note": "Strong serve bails him out under pressure"},
    ]

    zverev_props = [
        {"prop": "Zverev Aces", "choice": "Over", "line": 8.5,
         "prob": 0.61, "rec": rec(0.61),
         "note": "Elite serve, multiple tiebreaks expected"},
        {"prop": "Zverev Service Holds", "choice": "Over 85%", "line": "85%",
         "prob": 0.70, "rec": rec(0.70),
         "note": "One of tour's best at holding on grass"},
        {"prop": "Zverev to Win Match", "choice": "Yes", "line": "-303 ($1.33)",
         "prob": r.b_win_prob, "rec": rec(r.b_win_prob)},
        {"prop": "Zverev Double Faults", "choice": "Over 3.5", "line": 3.5,
         "prob": 0.55, "rec": rec(0.55),
         "note": "Strict clock vulnerability — historical issue"},
    ]

    match_props = [
        {"prop": f"Total Games O/U {r.games_ou_line}", "choice": "Over", "line": r.games_ou_line,
         "prob": 0.63, "rec": rec(0.63),
         "note": "Two elite serves + tiebreaks = games pile up"},
        {"prop": "Total Sets Over 3.5", "choice": "Over", "line": "+120",
         "prob": r.p_over_35, "rec": rec(r.p_over_35),
         "note": "Lehecka serve keeps sets alive; H2H shows he can steal one"},
        {"prop": f"Zverev -1.5 Sets", "choice": "Bet", "line": f"{r.spread_fav_odds} ({american_to_decimal(r.spread_fav_odds):.2f})",
         "prob": r.p_fav_spread, "rec": rec(r.p_fav_spread),
         "note": "Sharp pick — safety vs -303 ML tax"},
        {"prop": "1st Set Tiebreak", "choice": "Yes", "line": "+160",
         "prob": 0.38, "rec": rec(0.38),
         "note": "Both players hold at elite rates on grass"},
    ]

    return {"lehecka_props": lehecka_props, "zverev_props": zverev_props, "match_props": match_props}


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def print_result(r: MatchOutput) -> None:
    sep = "=" * 95
    dash = "-" * 95
    print(sep)
    print("  WIMBLEDON 2026 — R16 ANALYSIS | July 6, 2026")
    print(f"  {r.player_a} vs {r.player_b} | {r.court} | {r.start_time}")
    print(sep)
    print(f"\n{dash}")
    print(f"  {r.event}  [{r.round_name}]")
    print(f"  {r.player_a} ({r.player_a_rank}) vs {r.player_b} ({r.player_b_rank})")
    print(f"  H2H: {r.h2h_note}")
    print(dash)
    print(f"  Win Prob:    {r.player_a:30s} {r.a_win_prob:.1%}  |  {r.player_b:30s} {r.b_win_prob:.1%}")
    print(f"  Fair ML:     {r.player_a:30s} {r.a_fair_odds:>6s}  |  {r.player_b:30s} {r.b_fair_odds:>6s}")
    print(f"  Fair Dec:    {r.player_a:30s} ${r.a_fair_decimal:.2f}    |  {r.player_b:30s} ${r.b_fair_decimal:.2f}")
    print(f"  Market ML:   Fav: {r.market_ml_favorite_odds}  |  Dog: {r.market_ml_underdog_odds}")
    print(f"  Spread:      Fav -1.5: {r.spread_fav_odds}  |  Dog +1.5: {r.spread_dog_odds}")
    print(f"  Games O/U:   Line: {r.games_ou_line}")
    print(f"  DR:          {r.player_a:30s} {r.dominance_ratio_a:.4f}  |  {r.player_b:30s} {r.dominance_ratio_b:.4f}")
    print(f"  Edge vs Mkt: {r.model_edge_vs_market_pct:+.1f}%")
    print(f"  Rec ML:      {r.recommendation_ml}")
    print(f"  Rec O/U:     {r.recommendation_sets_ou}")
    print(f"  Rec Spread:  {r.recommendation_spread}")
    print(f"  Confidence:  {r.confidence_ml:.1f}%")
    print(f"  Exact Score: {r.exact_score_prediction}")
    print(f"  Stylistic:   {r.stylistic_edge}")
    print(f"\n  Analysis:")
    for line in r.analysis_summary.split("\n"):
        print(f"    {line}")
    print(f"\n  Scout Intel:")
    for s in r.scout_intel.replace("\n", " ").split(". "):
        if s.strip():
            print(f"    • {s.strip()}.")
    print(f"\n  Sharp Consensus:")
    for s in r.sharp_consensus.replace("\n", " ").split(". "):
        if s.strip():
            print(f"    • {s.strip()}.")
    print(f"\n  Umpire Watch:")
    for s in r.umpire_notes.replace("\n", " ").split(". "):
        if s.strip():
            print(f"    • {s.strip()}.")
    print(sep)


# ---------------------------------------------------------------------------
# Discord Push
# ---------------------------------------------------------------------------

def push_to_discord(r: MatchOutput) -> bool:
    if not DISCORD_WEBHOOK_URL:
        print("ERROR: DISCORD_WEBHOOK_URL not set in .env")
        return False

    def _t(s: str, n: int) -> str:
        return s[:n] + ("…" if len(s) > n else "")

    def _send(payload: dict, label: str) -> bool:
        try:
            resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
            if resp.status_code in (200, 204):
                print(f"[OK] {label} delivered.")
                return True
            print(f"[FAIL] {label} — Discord {resp.status_code}: {resp.text[:200]}")
            return False
        except Exception as e:
            print(f"[ERROR] {label} — {e}")
            return False

    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    props = build_props(r)

    # Color
    color = 3066993 if "BET" in r.recommendation_ml else (16776960 if "LEAN" in r.recommendation_ml else 9807270)

    # ---- MAIN ANALYSIS EMBED ----
    main_embed = {
        "title": _t(f"🎾 Wimbledon 2026 R16 — {r.player_a} vs {r.player_b}", 256),
        "description": _t(
            f"🏟️ **{r.court}** | {r.start_time} EDT | {r.round_name}\n"
            f"**{r.player_a}** ({r.player_a_rank}) vs **{r.player_b}** ({r.player_b_rank})\n"
            f"H2H: {r.h2h_note}", 350
        ),
        "color": color,
        "fields": [
            {
                "name": "📊 Probability & Odds",
                "value": _t(
                    f"**{r.player_a}:** {r.a_win_prob:.1%} | Fair {r.a_fair_odds} (${r.a_fair_decimal:.2f})\n"
                    f"**{r.player_b}:** {r.b_win_prob:.1%} | Fair {r.b_fair_odds} (${r.b_fair_decimal:.2f})\n"
                    f"Market ML: **{r.market_ml_favorite_odds}** / **{r.market_ml_underdog_odds}**\n"
                    f"Spread: **{r.spread_fav_odds}** / **{r.spread_dog_odds}** | Games O/U: **{r.games_ou_line}**",
                    400),
                "inline": True,
            },
            {
                "name": "📐 DR & Edge",
                "value": _t(
                    f"{r.player_a}: **{r.dominance_ratio_a:.3f}**\n"
                    f"{r.player_b}: **{r.dominance_ratio_b:.3f}**\n"
                    f"Model Edge: **{r.model_edge_vs_market_pct:+.1f}%** | Conf: **{r.confidence_ml:.0f}%**",
                    230),
                "inline": True,
            },
            {
                "name": "🏆 Recommendations",
                "value": _t(
                    f"{r.recommendation_ml} *(Conf: {r.confidence_ml:.0f}%)*\n"
                    f"{r.recommendation_sets_ou}\n"
                    f"{r.recommendation_spread}\n"
                    f"🎯 **Exact Score: {r.exact_score_prediction}**\n"
                    f"Set Dist: 3-0: {r.set_dist['3-0']:.0%} | 3-1: {r.set_dist['3-1']:.0%} | 3-2: {r.set_dist['3-2']:.0%}",
                    420),
                "inline": False,
            },
            {
                "name": "⚔️ Stylistic Edge",
                "value": _t(r.stylistic_edge, 350),
                "inline": False,
            },
            {
                "name": "🔍 Scout Intel",
                "value": _t(r.scout_intel, 500),
                "inline": False,
            },
            {
                "name": "🧠 Sharp Consensus",
                "value": _t(r.sharp_consensus, 500),
                "inline": False,
            },
            {
                "name": "⚖️ Umpire Watch",
                "value": _t(r.umpire_notes, 400),
                "inline": False,
            },
        ],
        "footer": {"text": "MultiSportPredict | Wimbledon 2026 R16 — July 6 | Bet Responsibly"},
        "timestamp": ts,
    }

    ok1 = _send({"embeds": [main_embed]}, "Main Analysis")

    # ---- PLAYER PROPS EMBED ----
    def fmt(prop_list):
        lines = []
        for p in prop_list:
            note = f" *({p['note']})*" if p.get("note") else ""
            lines.append(f"{p['rec']} **{p['prop']}** — {p['choice']} {p['line']} | P: {p['prob']:.0%}{note}")
        return "\n".join(lines)

    props_embed = {
        "title": _t(f"📋 Player Props — {r.player_a} vs {r.player_b}", 256),
        "color": 5793266,
        "fields": [
            {
                "name": f"🎾 {r.player_a} Props",
                "value": _t(fmt(props["lehecka_props"]), 900),
                "inline": False,
            },
            {
                "name": f"🎾 {r.player_b} Props",
                "value": _t(fmt(props["zverev_props"]), 900),
                "inline": False,
            },
            {
                "name": "🏟️ Match Props",
                "value": _t(fmt(props["match_props"]), 900),
                "inline": False,
            },
        ],
        "footer": {"text": "MultiSportPredict | Wimbledon 2026 Player Props"},
        "timestamp": ts,
    }

    ok2 = _send({"embeds": [props_embed]}, "Player Props")

    # ---- BETTING SLIP ----
    slip_embed = {
        "title": "🧾 BETTING SLIP — Lehecka vs Zverev | Wimbledon R16",
        "color": 15844367,
        "fields": [
            {
                "name": "🔥 Sharp Plays (Priority Order)",
                "value": (
                    "1️⃣ 🔥 **Zverev -1.5 Sets (-166 / $1.60)** — SHARP PICK; safety vs -303 ML\n"
                    "2️⃣ 🔥 **Lehecka Aces OVER 12.5** — Averaging 16/match, P ~68% | ✅ Strong\n"
                    "3️⃣ 📈 **Over 40.5 Total Games** — Two elite serves + tiebreaks | P ~63%\n"
                    "4️⃣ 💡 **Over 3.5 Sets (+120)** — Lehecka steal; value at plus-money\n"
                    "5️⃣ 👀 **Zverev ML (-303)** — Fair value only; expensive, skip ML for spread"
                ),
                "inline": False,
            },
            {
                "name": "📊 Model vs Market",
                "value": (
                    f"**{r.player_a}:** Model {r.a_win_prob:.0%} | Market {1 - r.market_fav_prob:.0%} | "
                    f"Fair ML {r.a_fair_odds}\n"
                    f"**{r.player_b}:** Model {r.b_win_prob:.0%} | Market {r.market_fav_prob:.0%} | "
                    f"Fair ML {r.b_fair_odds}\n"
                    f"Edge vs market: **{r.model_edge_vs_market_pct:+.1f}%**"
                ),
                "inline": False,
            },
            {
                "name": "⚠️ Risk Notes",
                "value": (
                    "• **Umpire factor:** Strict 25s clock = Zverev double faults; monitor early games\n"
                    "• **Lehecka serve:** If 1st-serve % drops below 60%, ace total thesis weakens\n"
                    "• **Zverev grand slam mode:** FO 2026 title = new composure ceiling; hard to fade\n"
                    f"• **P(Zverev sweeps 3-0):** {r.set_dist['3-0']:.0%} — significant straight-set risk\n"
                    "• H2H 1-1 (2023): Lehecka has beaten Zverev before — not a walkover"
                ),
                "inline": False,
            },
            {
                "name": "🎯 Exact Score",
                "value": f"**{r.exact_score_prediction}** | Zverev wins in 4, Lehecka steals one via tiebreak",
                "inline": False,
            },
        ],
        "footer": {"text": "MultiSportPredict | Wimbledon 2026 — July 6 | Sharp Analysis | Bet Responsibly 🎾"},
        "timestamp": ts,
    }

    ok3 = _send({"embeds": [slip_embed]}, "Betting Slip")

    return ok1 and ok2 and ok3


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    match_input = build_match()
    result = analyze_match(match_input)

    print_result(result)

    out_dir = Path("output")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "wimbledon_r16_lehecka_zverev_2026.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "event": "Wimbledon 2026 R16",
                "date": "2026-07-06",
                "match": asdict(result),
            },
            fh,
            indent=2,
        )
    print(f"\nSaved: {out_path}")

    print("\nPushing to Discord...")
    ok = push_to_discord(result)
    if ok:
        print("[OK] Discord push: SUCCESS — 3 embeds delivered")
    else:
        print("[FAIL] Discord push: FAILED")

    print("\nAnalysis complete.")


if __name__ == "__main__":
    main()
