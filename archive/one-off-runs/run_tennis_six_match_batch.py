#!/usr/bin/env python
"""
Tennis 6-Match Batch Analysis
=============================
Runs all requested matches through the DR-based tennis model.

Matches:
  1. Jakub Mensik vs Grigor Dimitrov  (Mensik ML)
  2. Karen Khachanov vs Yannick Hanfmann (Khachanov ML)
  3. Kamil Majchrzak vs Zachary Svajda (Majchrzak ML)
  4. Matteo Berrettini vs Arthur Fils  (Over 3.5 Sets)
  5. Jaume Munar vs Jacob Fearnley     (Munar ML)
  6. Alexander Bublik vs Kyrian Jacquet (Bublik ML)
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


# ---------------------------------------------------------------------------
# Model primitives
# ---------------------------------------------------------------------------

def clamp(x: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, x))


def prob_to_american(p: float) -> str:
    """Convert probability to American odds string."""
    p = clamp(p, 0.001, 0.999)
    if p >= 0.5:
        ml = -round((p / (1 - p)) * 100)
        return f"{ml}"
    else:
        ml = round(((1 - p) / p) * 100)
        return f"+{ml}"


# ---------------------------------------------------------------------------
# Player profiles & model
# ---------------------------------------------------------------------------

@dataclass
class PlayerProfile:
    name: str
    grass_skill: float        # 0-100
    serve_power: float        # 0-100
    return_quality: float     # 0-100
    form: float               # 0-100
    experience: float         # 0-100
    court_coverage: float = 60.0  # 0-100
    ball_striking_weight: float = 60.0  # 0-100
    home_boost: float = 0.0
    fatigue: float = 0.0


@dataclass
class MatchInput:
    event: str
    player_a: PlayerProfile
    player_b: PlayerProfile
    player_a_rank: str
    player_b_rank: str
    start_time_edt: str
    market_pick: str           # The user's suggested play
    market_favorite: str
    market_favorite_prob: float
    notes: str = ""
    sharp_consensus: str = ""
    umpire_notes: str = ""


@dataclass
class MatchOutput:
    event: str
    start_time: str
    player_a: str
    player_b: str
    player_a_rank: str
    player_b_rank: str
    a_win_prob: float
    b_win_prob: float
    a_fair_odds: str
    b_fair_odds: str
    model_favorite: str
    model_fav_prob: float
    model_edge_vs_market_pct: float
    dominance_ratio_a: float
    dominance_ratio_b: float
    recommendation_ml: str
    confidence_ml: float
    user_suggested_play: str
    market_favorite_prob: float
    analysis_summary: str
    sharp_consensus: str
    umpire_notes: str
    stylistic_edge: str


def _player_strength(p: PlayerProfile) -> float:
    """Weighted profile for grass tennis with expanded attributes."""
    base = (
        0.22 * p.grass_skill
        + 0.20 * p.serve_power
        + 0.14 * p.return_quality
        + 0.13 * p.form
        + 0.08 * p.experience
        + 0.13 * p.court_coverage
        + 0.10 * p.ball_striking_weight
    )
    base += p.home_boost
    base -= p.fatigue
    return base


def _dominance_ratio(p: PlayerProfile) -> float:
    """Dominance Ratio for grass: DR = ReturnPointsWon% / (1 - ServePointsWon%)"""
    serve_pct = 0.50 + (p.serve_power / 100.0) * 0.25 + (p.grass_skill / 100.0) * 0.10
    serve_pct = clamp(serve_pct, 0.55, 0.85)
    return_pct = 0.20 + (p.return_quality / 100.0) * 0.25 + (p.form / 100.0) * 0.08
    return_pct = clamp(return_pct, 0.20, 0.50)
    dr = return_pct / (1.0 - serve_pct) if serve_pct < 1.0 else 0.0
    return round(dr, 4)


def _win_prob(a_strength: float, b_strength: float) -> float:
    """Map strength delta to probability (logistic scale)."""
    delta = a_strength - b_strength
    p = 1.0 / (1.0 + math.exp(-(delta / 7.5)))
    return clamp(p, 0.05, 0.95)


def _confidence_from_prob(p: float) -> float:
    """Map win probability to confidence score (0-100)."""
    edge = abs(p - 0.5)
    return round(clamp(50 + edge * 120, 0, 98), 1)


def _stylistic_edge(a: PlayerProfile, b: PlayerProfile) -> str:
    """Generate stylistic matchup description."""
    parts = []
    if a.court_coverage > b.court_coverage + 10:
        parts.append(f"{a.name}'s court coverage neutralizes {b.name}'s power")
    elif b.court_coverage > a.court_coverage + 10:
        parts.append(f"{b.name}'s court coverage neutralizes {a.name}'s power")
    if a.serve_power > b.serve_power + 10:
        parts.append(f"{a.name}'s bigger serve ({a.serve_power:.0f}/100) dictates")
    elif b.serve_power > a.serve_power + 10:
        parts.append(f"{b.name}'s bigger serve ({b.serve_power:.0f}/100) dictates")
    if a.return_quality > b.return_quality + 8:
        parts.append(f"{a.name}'s return is the X-factor")
    elif b.return_quality > a.return_quality + 8:
        parts.append(f"{b.name}'s return is the X-factor")
    if not parts:
        parts.append("Stylistically even matchup")
    return " | ".join(parts)


def analyze_match(m: MatchInput) -> MatchOutput:
    a_s = _player_strength(m.player_a)
    b_s = _player_strength(m.player_b)
    a_prob = _win_prob(a_s, b_s)
    b_prob = 1.0 - a_prob

    dr_a = _dominance_ratio(m.player_a)
    dr_b = _dominance_ratio(m.player_b)

    if a_prob >= b_prob:
        model_favorite = m.player_a.name
        model_fav_prob = a_prob
    else:
        model_favorite = m.player_b.name
        model_fav_prob = b_prob

    market_prob = m.market_favorite_prob
    model_edge_vs_market = (model_fav_prob - market_prob) * 100

    conf_ml = _confidence_from_prob(model_fav_prob)
    edge_magnitude = model_edge_vs_market

    # Moneyline recommendation
    if edge_magnitude >= 4.0 and conf_ml >= 62:
        rec_ml = f"BET {model_favorite} ML"
    elif edge_magnitude >= 2.0 and conf_ml >= 57:
        rec_ml = f"LEAN {model_favorite} ML"
    elif edge_magnitude >= 0.5:
        rec_ml = f"SLIGHT LEAN {model_favorite} ML"
    else:
        rec_ml = "PASS — Market efficient"

    fair_odds_a = prob_to_american(a_prob)
    fair_odds_b = prob_to_american(b_prob)

    summary_parts = [
        f"**Probability:** {m.player_a.name} {a_prob:.1%} | {m.player_b.name} {b_prob:.1%}",
        f"**Fair ML:** {m.player_a.name} {fair_odds_a} | {m.player_b.name} {fair_odds_b}",
        f"**DR:** {m.player_a.name} {dr_a:.4f} | {m.player_b.name} {dr_b:.4f}",
        f"**Edge vs Market:** {model_edge_vs_market:+.1f}%",
        m.notes,
    ]
    analysis_summary = "\n".join(summary_parts)

    return MatchOutput(
        event=m.event,
        start_time=m.start_time_edt,
        player_a=m.player_a.name,
        player_b=m.player_b.name,
        player_a_rank=m.player_a_rank,
        player_b_rank=m.player_b_rank,
        a_win_prob=round(a_prob, 4),
        b_win_prob=round(b_prob, 4),
        a_fair_odds=fair_odds_a,
        b_fair_odds=fair_odds_b,
        model_favorite=model_favorite,
        model_fav_prob=round(model_fav_prob, 4),
        model_edge_vs_market_pct=round(model_edge_vs_market, 2),
        dominance_ratio_a=dr_a,
        dominance_ratio_b=dr_b,
        recommendation_ml=rec_ml,
        confidence_ml=conf_ml,
        user_suggested_play=m.market_pick,
        market_favorite_prob=m.market_favorite_prob,
        analysis_summary=analysis_summary,
        sharp_consensus=m.sharp_consensus,
        umpire_notes=m.umpire_notes,
        stylistic_edge=_stylistic_edge(m.player_a, m.player_b),
    )


# ---------------------------------------------------------------------------
# Build all 6 requested matches from user-provided narrative
# ---------------------------------------------------------------------------

def build_matches() -> List[MatchInput]:
    return [
        # ---- Match 1: Jakub Mensik vs Grigor Dimitrov ----
        MatchInput(
            event="Wimbledon 2026 — Men's Singles",
            start_time_edt="TBD",
            player_a=PlayerProfile(
                name="Jakub Mensik",
                grass_skill=68,          # developing on grass, big serve game
                serve_power=88,           # massive first serve — key weapon
                return_quality=58,        # return game still developing
                form=72,                  # strong form, confident
                experience=52,            # young, limited 5-set experience
                court_coverage=62,        # 6'3" frame — solid but not elite mover
                ball_striking_weight=78,  # explosive baseline power
                fatigue=0.0,
            ),
            player_b=PlayerProfile(
                name="Grigor Dimitrov",
                grass_skill=82,           # elite grass pedigree, veteran
                serve_power=74,           # solid serve, placement based
                return_quality=80,        # top-tier return rating on grass
                form=75,                  # strong recent form
                experience=92,            # immense experience
                court_coverage=76,        # excellent movement
                ball_striking_weight=70,  # all-court game, backhand slice weapon
                fatigue=0.0,
            ),
            player_a_rank="Rising",
            player_b_rank="Veteran (Top 15)",
            market_favorite="Grigor Dimitrov",
            market_favorite_prob=0.62,    # sharps back Dimitrov firmly
            market_pick="Mensik ML (Contrarian)",
            notes=(
                "Mensik must maintain 65%+ first-serve to neutralize Dimitrov's return. "
                "Dimitrov's backhand slice stays lower on grass than almost any shot — challenges Mensik's 6'3\" frame. "
                "Contrarian play: if Mensik's serve dominates, tiebreak variance favors underdog."
            ),
            sharp_consensus=(
                "Sharp money firmly backs Dimitrov on experience. Mensik ML is a heavy contrarian fade. "
                "If Mensik serves above 65% first-serve, he can force tiebreaks where variance favors the underdog."
            ),
            umpire_notes=(
                "Lenient chair (fast rhythm) favors Mensik's quick-strike ability. "
                "Strict clock enforcement could disrupt Mensik's service routine in high-pressure moments."
            ),
        ),
        # ---- Match 2: Karen Khachanov vs Yannick Hanfmann ----
        MatchInput(
            event="Wimbledon 2026 — Men's Singles",
            start_time_edt="TBD",
            player_a=PlayerProfile(
                name="Karen Khachanov",
                grass_skill=78,           # #19 seed, flat game penetrates grass
                serve_power=85,           # huge server, ~80% first-serve pts won on grass
                return_quality=68,        # solid return, good for surface
                form=76,                  # strong form as seed
                experience=82,            # veteran of big matches
                court_coverage=66,        # adequate mover, not elite
                ball_striking_weight=84,  # flat, heavy groundstrokes — perfect for grass
                fatigue=0.0,
            ),
            player_b=PlayerProfile(
                name="Yannick Hanfmann",
                grass_skill=62,           # clay-court tendencies
                serve_power=70,           # kick serve sits up on grass — disadvantage
                return_quality=60,        # BP conversion drops on fast surfaces
                form=64,                  # inconsistent form
                experience=68,            # solid but not elite level
                court_coverage=60,        # adequate movement
                ball_striking_weight=58,  # lacks flat finishing power for grass
                fatigue=0.0,
            ),
            player_a_rank="#19 (Seeded)",
            player_b_rank="#84",
            market_favorite="Karen Khachanov",
            market_favorite_prob=0.72,    # sharp consensus backs Khachanov
            market_pick="Khachanov ML",
            notes=(
                "Khachanov's flat groundstrokes penetrate grass perfectly. "
                "Hanfmann's kick serve sits up into Khachanov's strike zone. "
                "Khachanov 80% first-serve points won on grass. "
                "Hanfmann BP conversion drops significantly on faster surfaces."
            ),
            sharp_consensus=(
                "Sharp consensus heavily backs Khachanov. Hanfmann lacks flat finishing power "
                "to hit through Khachanov on grass. Solid favorite play."
            ),
            umpire_notes=(
                "Khachanov prefers steady, methodical rhythm. An umpire who doesn't rush "
                "his service routine helps him maintain high first-serve percentage."
            ),
        ),
        # ---- Match 3: Kamil Majchrzak vs Zachary Svajda ----
        MatchInput(
            event="Wimbledon 2026 — Men's Singles",
            start_time_edt="TBD",
            player_a=PlayerProfile(
                name="Kamil Majchrzak",
                grass_skill=74,           # flatter game suits low-bouncing courts
                serve_power=75,           # spot server — effective on grass
                return_quality=70,        # solid return, good BH DTL
                form=72,                  # good form
                experience=72,            # solid experience
                court_coverage=68,        # decent mover
                ball_striking_weight=72,  # versatile, flatter shots
                fatigue=0.0,
            ),
            player_b=PlayerProfile(
                name="Zachary Svajda",
                grass_skill=58,           # hard-court grinder, developing grass game
                serve_power=62,           # moderate serve, not a weapon on grass
                return_quality=66,        # stands far back — punished on grass
                form=66,                  # decent form
                experience=56,            # still developing grass movement
                court_coverage=72,        # excellent lateral movement (hard court style)
                ball_striking_weight=56,  # grinder, not power-based
                fatigue=0.0,
            ),
            player_a_rank="#72",
            player_b_rank="#89",
            market_favorite="Kamil Majchrzak",
            market_favorite_prob=0.59,    # value play
            market_pick="Majchrzak ML",
            notes=(
                "Majchrzak's backhand down the line is his most profitable shot on grass. "
                "Svajda stands far back to return — easily punished by spot serving. "
                "Svajda still developing reliable grass movement patterns."
            ),
            sharp_consensus=(
                "Sharps view Majchrzak's surface comfort as the deciding factor. "
                "Distinct value against Svajda who lacks grass-court reliability."
            ),
            umpire_notes=(
                "Strict 25-second clock heavily pressures Svajda who grinds long rallies "
                "and needs recovery time. Benefits Majchrzak's quicker pace."
            ),
        ),
        # ---- Match 4: Matteo Berrettini vs Arthur Fils (Over 3.5 Sets) ----
        MatchInput(
            event="Wimbledon 2026 — Men's Singles",
            start_time_edt="TBD",
            player_a=PlayerProfile(
                name="Matteo Berrettini",
                grass_skill=85,           # former Wimbledon finalist — elite on grass
                serve_power=92,           # unbreakable serve on grass when healthy
                return_quality=65,        # adequate return, relies on serve+FH
                form=74,                  # good form, comeback narrative
                experience=85,            # Grand Slam final experience
                court_coverage=60,        # not elite mover, but serve covers it
                ball_striking_weight=82,  # massive serve+forehand combo
                fatigue=0.0,
            ),
            player_b=PlayerProfile(
                name="Arthur Fils",
                grass_skill=74,           # #20 seed, rising star on grass
                serve_power=85,           # 130+ mph serves
                return_quality=68,        # solid return, athletic
                form=78,                  # excellent form, RG QF
                experience=57,            # 19yo, learning 5-set management
                court_coverage=72,        # athletic, covers court well
                ball_striking_weight=80,  # raw baseline power
                fatigue=0.0,
            ),
            player_a_rank="Former Finalist",
            player_b_rank="#20 (Seeded)",
            market_favorite="Matteo Berrettini",
            market_favorite_prob=0.65,    # Berrettini favorite
            market_pick="Over 3.5 Sets",
            notes=(
                "Both players serve 130+ mph — breaks are statistically rare. "
                "Berrettini's serve virtually impenetrable on grass when healthy. "
                "Fils has raw power to snatch a set via tiebreak or singular loose game. "
                "Match likely extends to 4 sets minimum."
            ),
            sharp_consensus=(
                "Over 3.5 Sets is highly backed by sharps. Both players hold serve at elite levels. "
                "Fils can take a set but lacks consistency to win 3."
            ),
            umpire_notes=(
                "Strict time violations could rattle younger Fils in high-pressure moments, "
                "potentially extending match if he drops focus."
            ),
        ),
        # ---- Match 5: Jaume Munar vs Jacob Fearnley ----
        MatchInput(
            event="Wimbledon 2026 — Men's Singles",
            start_time_edt="TBD",
            player_a=PlayerProfile(
                name="Jaume Munar",
                grass_skill=54,           # pure clay-courter — struggles on grass
                serve_power=58,           # moderate serve, not a grass weapon
                return_quality=72,        # excellent return, low UE rate
                form=68,                  # consistent form
                experience=76,            # seasoned on tour
                court_coverage=68,        # grinder — good coverage
                ball_striking_weight=52,  # heavy topspin, lacks flat penetration
                fatigue=0.0,
            ),
            player_b=PlayerProfile(
                name="Jacob Fearnley",
                grass_skill=66,           # developing grass game, crowd momentum
                serve_power=66,           # solid serve, home crowd boost
                return_quality=62,        # adequate return
                form=70,                  # riding wildcard momentum
                experience=54,            # less experienced, hype factor
                court_coverage=66,        # solid movement
                ball_striking_weight=64,  # grass-suited game style
                home_boost=5.0,           # British wildcard crowd factor
                fatigue=0.0,
            ),
            player_a_rank="#84",
            player_b_rank="Wildcard",
            market_favorite="Jacob Fearnley",
            market_favorite_prob=0.55,    # wildcard hype
            market_pick="Munar ML (Fade on hype)",
            notes=(
                "Munar is pure clay-courter with heavy topspin — counterintuitive fade. "
                "Low unforced error rate can force Fearnley into overhitting. "
                "Fearnley rides local crowd momentum but lacks experience closing big matches."
            ),
            sharp_consensus=(
                "Sharps note Fearnley wildcard hype is overpriced. "
                "Munar's baseline consistency and stamina can force less-experienced "
                "Fearnley into overhitting. Direct fade on British hype."
            ),
            umpire_notes=(
                "Munar notorious for max time between points. Strict umpire will penalize "
                "him with time violations, disrupting rhythm and aiding Fearnley. "
                "Lenient umpire favors Munar's grinding pace."
            ),
        ),
        # ---- Match 6: Alexander Bublik vs Kyrian Jacquet ----
        MatchInput(
            event="Wimbledon 2026 — Men's Singles",
            start_time_edt="TBD",
            player_a=PlayerProfile(
                name="Alexander Bublik",
                grass_skill=82,           # #10 seed, premier grass threat
                serve_power=90,           # elite serve, unreadable delivery
                return_quality=58,        # unorthodox return style
                form=74,                  # strong grass form
                experience=80,            # veteran on grass
                court_coverage=62,        # adequate mover
                ball_striking_weight=60,  # trick shots, underarm serves, drops
                fatigue=0.0,
            ),
            player_b=PlayerProfile(
                name="Kyrian Jacquet",
                grass_skill=56,           # qualifier, lacks grass weapons
                serve_power=62,           # moderate serve
                return_quality=54,        # lacks tools to threaten elite servers
                form=60,                  # qualifier run, but unproven at this level
                experience=50,            # limited big-match experience
                court_coverage=58,        # average movement
                ball_striking_weight=54,  # lacks firepower
                fatigue=3.0,              # qualifier fatigue
            ),
            player_a_rank="#10 (Seeded)",
            player_b_rank="Qualifier",
            market_favorite="Alexander Bublik",
            market_favorite_prob=0.82,    # heavy favorite
            market_pick="Bublik ML (Parlay piece)",
            notes=(
                "Bublik hits aces at elite rate, uses underarm serves and drops to disrupt. "
                "Jacquet lacks weapons to consistently threaten elite servers. "
                "Only risk: Bublik's notorious mid-match focus drops."
            ),
            sharp_consensus=(
                "Bublik ML is heavily juiced chalk — strictly a parlay piece. "
                "Raw talent gap over Jacquet on grass is immense."
            ),
            umpire_notes=(
                "Bublik thrives on chaos and rapid play. Umpire who lets match flow "
                "quickly and ignores crowd noise suits Bublik's quick-serve style."
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def print_results(results: List[MatchOutput]) -> None:
    sep = "=" * 100
    print(sep)
    print("  TENNIS 6-MATCH BATCH ANALYSIS")
    print(sep)

    for i, r in enumerate(results, 1):
        dash = "-" * 100
        print(f"\n{dash}")
        print(f"  MATCH {i}: {r.event}")
        print(f"  {r.start_time} | Suggested Play: {r.user_suggested_play}")
        print(dash)
        print(f"  {r.player_a} (Rank: {r.player_a_rank}) vs {r.player_b} (Rank: {r.player_b_rank})")
        print(dash)
        print(f"  Win Prob:      {r.player_a:25s} {r.a_win_prob:.1%}  |  {r.player_b:25s} {r.b_win_prob:.1%}")
        print(f"  Fair ML:       {r.player_a:25s} {r.a_fair_odds:>6s}  |  {r.player_b:25s} {r.b_fair_odds:>6s}")
        print(f"  DR:            {r.player_a:25s} {r.dominance_ratio_a:.4f}  |  {r.player_b:25s} {r.dominance_ratio_b:.4f}")
        print(f"  Model Fav:     {r.model_favorite} ({r.model_fav_prob:.1%})")
        print(f"  Edge vs Mkt:   {r.model_edge_vs_market_pct:+.1f}%")
        print(f"  Rec (ML):      {r.recommendation_ml}")
        print(f"  Confidence:    {r.confidence_ml:.1f}%")
        print(f"  User Play:     {r.user_suggested_play}")
        print(f"  Stylistic:     {r.stylistic_edge}")
        print()
        print(f"  Analysis:")
        for line in r.analysis_summary.split("\n"):
            print(f"    {line}")
        print(f"  Sharp Consensus:")
        for line in r.sharp_consensus.split(". "):
            print(f"    • {line.strip()}.")
        print(f"  Umpire Watch:")
        for line in r.umpire_notes.split(". "):
            print(f"    • {line.strip()}.")

    # Betting slip summary
    print(f"\n{sep}")
    print("  BETTING SLIP SUMMARY")
    print(sep)
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r.player_a} vs {r.player_b}")
        print(f"     Suggested: {r.user_suggested_play}")
        print(f"     Model: {r.recommendation_ml} (Conf: {r.confidence_ml:.1f}%, Edge: {r.model_edge_vs_market_pct:+.1f}%)")
    print(sep)

    # Play recommendations grid
    print("\n  PLAY RECOMMENDATIONS:")
    print(f"  {'#':>2} {'Match':<45} {'Suggested Play':<35} {'Model Rec':<30} {'Conf':>6} {'Edge':>6}")
    print(f"  {'-'*2} {'-'*45} {'-'*35} {'-'*30} {'-'*6} {'-'*6}")
    for i, r in enumerate(results, 1):
        matchup = f"{r.player_a[:18]} vs {r.player_b[:18]}"
        print(f"  {i:>2} {matchup:<45} {r.user_suggested_play:<35} {r.recommendation_ml:<30} {r.confidence_ml:>5.0f}% {r.model_edge_vs_market_pct:>+5.1f}%")


# ---------------------------------------------------------------------------
# Discord push
# ---------------------------------------------------------------------------

def push_to_discord(results: List[MatchOutput]) -> bool:
    """Push 6-match analysis to Discord (split into batches to avoid 6000-char limit)."""
    if not DISCORD_WEBHOOK_URL:
        print("ERROR: DISCORD_WEBHOOK_URL not set — skipping Discord push")
        return False

    def send_embeds(embeds_list: list) -> bool:
        try:
            resp = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": embeds_list}, timeout=15)
            if resp.status_code in (200, 204):
                return True
            print(f"[FAIL] Discord returned {resp.status_code}: {resp.text[:200]}")
            return False
        except Exception as exc:
            print(f"[ERROR] Discord request failed: {exc}")
            return False

    all_ok = True
    batch = []

    for i, r in enumerate(results, 1):
        if "BET" in r.recommendation_ml:
            color = 3066993  # Green
        elif "LEAN" in r.recommendation_ml:
            color = 16776960  # Yellow
        else:
            color = 9807270  # Gray

        align = "✅ Aligns" if (
            r.user_suggested_play.split(" ")[0].lower() in r.recommendation_ml.lower() or
            r.user_suggested_play.split(" (")[0].lower() in r.recommendation_ml.lower()
        ) else "⚠️ Diverges"

        embed = {
            "title": f"🎾 Match {i}: {r.player_a} vs {r.player_b}",
            "color": color,
            "fields": [
                {
                    "name": "📊 Market & Model",
                    "value": (
                        f"**Play:** {r.user_suggested_play}\n"
                        f"**Model:** {r.recommendation_ml}\n"
                        f"**Conf:** {r.confidence_ml:.0f}% | **Edge:** {r.model_edge_vs_market_pct:+.1f}%\n"
                        f"**{align}**"
                    ),
                    "inline": False,
                },
                {
                    "name": "🎯 Prob",
                    "value": f"{r.player_a}: {r.a_win_prob:.0%}\n{r.player_b}: {r.b_win_prob:.0%}",
                    "inline": True,
                },
                {
                    "name": "📐 DR",
                    "value": f"{r.player_a}: {r.dominance_ratio_a:.3f}\n{r.player_b}: {r.dominance_ratio_b:.3f}",
                    "inline": True,
                },
                {
                    "name": "💰 Fair ML",
                    "value": f"{r.player_a}: {r.a_fair_odds}\n{r.player_b}: {r.b_fair_odds}",
                    "inline": True,
                },
                {
                    "name": "🧠 Sharp",
                    "value": r.sharp_consensus[:300],
                    "inline": False,
                },
                {
                    "name": "⚖️ Umpire",
                    "value": r.umpire_notes[:300],
                    "inline": False,
                },
            ],
            "footer": {"text": f"MultiSportPredict | Wimbledon 2026"},
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        batch.append(embed)

        # Send in groups of 2 to keep under 6000 chars
        if len(batch) == 2:
            all_ok &= send_embeds(batch)
            batch = []

    if batch:
        all_ok &= send_embeds(batch)

    # ---- Betting Slip embed (sent separately) ----
    slip_embed = {
        "title": "🧾 TENNIS 6-MATCH BETTING SLIP",
        "color": 3066993,
        "fields": [
            {
                "name": "📋 Recommendations",
                "value": "\n".join(
                    f"{'✅' if 'BET' in r.recommendation_ml else '📌'} **{r.model_favorite if 'BET' in r.recommendation_ml else r.user_suggested_play}** — {r.confidence_ml:.0f}% conf, {r.model_edge_vs_market_pct:+.1f}% edge"
                    for r in results
                )[:1024],
                "inline": False,
            },
            {
                "name": "🎯 Parlay Legs",
                "value": "\n".join(
                    f"• **{r.model_favorite} ML** ({r.confidence_ml:.0f}%)"
                    for r in results if "BET" in r.recommendation_ml
                )[:1024],
                "inline": False,
            },
            {
                "name": "⚠️ Notes",
                "value": (
                    "• M1: Dimitrov strong fav — Mensik ML contrarian\n"
                    "• M4: Berrettini/Fils both 130mph serves — Over 3.5 sets sharp\n"
                    "• M5: Fearnley home +5.0 skews — Munar fade high-risk\n"
                    "• M6: Bublik safest anchor (98% conf)"
                )[:1024],
                "inline": False,
            },
        ],
        "footer": {"text": "MultiSportPredict | Tennis 6-Match | Bet Responsibly"},
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    all_ok &= send_embeds([slip_embed])

    if all_ok:
        print("[OK] All Discord embeds sent successfully")
    else:
        print("[WARNING] Some Discord embeds may have failed")

    return all_ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    matches = build_matches()
    results = [analyze_match(m) for m in matches]

    print_results(results)

    # Save output
    out_dir = Path("output")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "tennis_six_match_batch_2026_07_01.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_matches": len(results),
                "results": [asdict(r) for r in results],
            },
            f,
            indent=2,
        )
    print(f"\nSaved results to: {out_path}")

    # Push to Discord
    print("\nPushing to Discord...")
    pushed = push_to_discord(results)
    if pushed:
        print("[OK] Discord push: SUCCESS")
    else:
        print("[FAIL] Discord push: FAILED")

    print("Analysis complete.")


if __name__ == "__main__":
    main()
