#!/usr/bin/env python
"""
Wimbledon 2026 — Two-Match Analysis (July 2, 2026)
==================================================
Match 1: Jiri Lehecka vs Alex Molcan   — Men's Singles, ~8:00 AM EDT
Match 2: Jakub Mensik vs Grigor Dimitrov  — Men's Singles, ~10:00 AM EDT

Pushes full analysis + betting recommendations to Discord with rich formatting.
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
    market_favorite: str
    market_favorite_prob: float
    market_favorite_odds: str
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
    recommendation_over_under: str
    confidence_ml: float
    market_favorite_prob: float
    market_favorite_odds: str
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
    """
    Dominance Ratio approximation for grass:
    DR = ReturnPointsWon% / (1 - ServePointsWon%)
    """
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


def _stylistic_edge_description(a: PlayerProfile, b: PlayerProfile) -> str:
    """Generate a description of the stylistic matchup."""
    parts = []
    if a.court_coverage > b.court_coverage + 10:
        parts.append(f"{a.name}'s elite court coverage neutralizes {b.name}'s power")
    elif b.court_coverage > a.court_coverage + 10:
        parts.append(f"{b.name}'s elite court coverage neutralizes {a.name}'s power")
    if a.serve_power > b.serve_power + 10:
        parts.append(f"{a.name}'s bigger serve ({a.serve_power:.0f}/100) dictates on grass")
    elif b.serve_power > a.serve_power + 10:
        parts.append(f"{b.name}'s bigger serve ({b.serve_power:.0f}/100) dictates on grass")
    if a.return_quality > b.return_quality + 8:
        parts.append(f"{a.name}'s return game is the X-factor")
    elif b.return_quality > a.return_quality + 8:
        parts.append(f"{b.name}'s return game is the X-factor")
    if not parts:
        parts.append("Stylistically even — near coin-flip matchup")
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
    prob_ratio = model_fav_prob / market_prob if market_prob > 0 else 1.0

    # Moneyline recommendation
    if edge_magnitude >= 4.0 and conf_ml >= 62 and prob_ratio >= 1.06:
        rec_ml = f"BET {model_favorite} ML"
    elif edge_magnitude >= 2.0 and conf_ml >= 57:
        rec_ml = f"LEAN {model_favorite} ML"
    elif edge_magnitude >= 0.5:
        rec_ml = f"SLIGHT LEAN {model_favorite} ML"
    else:
        rec_ml = f"PASS — Market efficient"

    # Over/Under recommendation based on DR profiles and style
    dr_sum = dr_a + dr_b
    if dr_sum > 1.8:
        rec_ou = "OVER — High DR match suggests extended rallies, break chances"
    elif dr_sum < 1.2:
        rec_ou = "UNDER — Low DR suggests serve-dominant, quick holds"
    else:
        rec_ou = "LEAN OVER — Moderate DR, expect competitive sets"

    dr_diff = dr_a - dr_b
    if dr_diff > 0.02:
        dr_advantage = f"{m.player_a.name} holds DR edge ({dr_a:.3f} vs {dr_b:.3f})"
    elif dr_diff < -0.02:
        dr_advantage = f"{m.player_b.name} holds DR edge ({dr_b:.3f} vs {dr_a:.3f})"
    else:
        dr_advantage = f"DR near-identical ({dr_a:.3f} vs {dr_b:.3f}) — coin flip"

    fair_odds_a = prob_to_american(a_prob)
    fair_odds_b = prob_to_american(b_prob)

    summary_parts = [
        f"**Probability:** {m.player_a.name} {a_prob:.1%} | {m.player_b.name} {b_prob:.1%}",
        f"**Fair ML:** {m.player_a.name} {fair_odds_a} | {m.player_b.name} {fair_odds_b}",
        f"**DR:** {dr_advantage}",
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
        recommendation_over_under=rec_ou,
        confidence_ml=conf_ml,
        market_favorite_prob=m.market_favorite_prob,
        market_favorite_odds=m.market_favorite_odds,
        analysis_summary=analysis_summary,
        sharp_consensus=m.sharp_consensus,
        umpire_notes=m.umpire_notes,
        stylistic_edge=_stylistic_edge_description(m.player_a, m.player_b),
    )


# ---------------------------------------------------------------------------
# Build requested matches
# ---------------------------------------------------------------------------

def build_matches() -> List[MatchInput]:
    return [
        # ---- Match 1: Jiri Lehecka vs Alex Molcan ----
        MatchInput(
            event="Wimbledon 2026 — Men's Singles 2nd Round",
            start_time_edt="~8:00 AM EDT",
            player_a=PlayerProfile(
                name="Jiri Lehecka",
                grass_skill=78,          # excellent grass mover, QF at AO 2023, fast surfaces suit him
                serve_power=82,           # big flat serve — major weapon on grass
                return_quality=70,        # solid return game, aggressive on 2nd serves
                form=74,                  # strong Wimbledon build-up, confident
                experience=68,            # still developing at Grand Slam level but QF experience
                court_coverage=72,        # excellent lateral movement, slides well on grass
                ball_striking_weight=80,  # flat, heavy groundstrokes — ideal for grass
                fatigue=0.0,
            ),
            player_b=PlayerProfile(
                name="Alex Molcan",
                grass_skill=54,           # clay-court specialist — grass is his weakest surface
                serve_power=62,           # moderate serve, not a grass weapon
                return_quality=64,        # decent return but struggles on fast surfaces
                form=62,                  # inconsistent form, better on clay
                experience=66,            # tour experience but limited grass success
                court_coverage=60,        # adequate mover, not elite on grass
                ball_striking_weight=56,  # heavy topspin game — sits up on grass, easy to attack
                fatigue=0.0,
            ),
            player_a_rank="#35",
            player_b_rank="#82",
            market_favorite="Jiri Lehecka",
            market_favorite_prob=0.70,    # ~70% implied (-230 est.)
            market_favorite_odds="-240",
            notes=(
                "Lehecka's flat ball-striking and big serve are perfectly suited to grass. "
                "Molcan's heavy topspin game (clay-court style) sits up on the low grass bounce, "
                "making it easy for Lehecka to attack off both wings. "
                "The surface contrast is extreme — this is a stylistic nightmare for Molcan."
            ),
            sharp_consensus=(
                "Sharps heavily favor Lehecka given the extreme surface contrast. "
                "Molcan is a clay-courter whose heavy topspin game is neutralized by low grass bounce. "
                "Lehecka's flat, penetrating groundstrokes and big serve are perfectly suited. "
                "The market price (~-240) is efficient but there may be value on Lehecka -2.5 or -3.5 game spread."
            ),
            umpire_notes=(
                "Lenient chair (fast rhythm) favors Lehecka's quick-strike ability. "
                "Strict serve clock could disrupt Molcan's deliberate pre-serve routine, "
                "especially if he falls behind early and feels rushed."
            ),
        ),
        # ---- Match 2: Jakub Mensik vs Grigor Dimitrov ----
        MatchInput(
            event="Wimbledon 2026 — Men's Singles 2nd Round",
            start_time_edt="~10:00 AM EDT",
            player_a=PlayerProfile(
                name="Jakub Mensik",
                grass_skill=68,          # developing on grass, big serve game
                serve_power=88,           # massive first serve — key weapon on grass
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
                court_coverage=76,        # excellent movement — one of best on tour
                ball_striking_weight=70,  # all-court game, backhand slice weapon
                fatigue=0.0,
            ),
            player_a_rank="#58",
            player_b_rank="#10 (Seeded)",
            market_favorite="Grigor Dimitrov",
            market_favorite_prob=0.62,    # ~62% implied (-163 est.)
            market_favorite_odds="-165",
            notes=(
                "Mensik must maintain 65%+ first-serve to neutralize Dimitrov's elite return game. "
                "Dimitrov's backhand slice stays lower on grass than almost any shot — it challenges Mensik's 6'3\" frame. "
                "If Mensik's serve dominates, tiebreak variance favors the young underdog. "
                "Dimitrov's movement and court coverage give him a massive edge in extended rallies."
            ),
            sharp_consensus=(
                "Sharp money firmly backs Dimitrov on experience and grass pedigree. "
                "Dimitrov's return quality (80/100) is elite — he reads big servers well on grass. "
                "Mensik ML is a contrarian fade play; his path to victory requires 65%+ first serves "
                "and tiebreak variance. If Dimitrov gets an early break, he'll close efficiently."
            ),
            umpire_notes=(
                "Strict clock enforcement could disrupt Mensik's service routine in high-pressure moments. "
                "Dimitrov thrives under any rhythm — his experience means umpire style affects him minimally. "
                "Watch for potential time violations on Mensik's serve at crucial break points."
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def print_results(results: List[MatchOutput]) -> None:
    separator = "=" * 90
    print(separator)
    print("  WIMBLEDON 2026 — JULY 2 TWO-MATCH ANALYSIS")
    print("  Lehecka vs Molcan (~8:00 AM) | Mensik vs Dimitrov (~10:00 AM)")
    print(separator)

    for i, r in enumerate(results, 1):
        dash = "-" * 90
        print(f"\n{dash}")
        print(f"  MATCH {i}: {r.event}")
        print(f"  {r.start_time}")
        print(dash)
        print(f"  {r.player_a} (Rank: {r.player_a_rank}) vs {r.player_b} (Rank: {r.player_b_rank})")
        print(dash)
        print(f"  Win Prob:     {r.player_a:25s} {r.a_win_prob:.1%}  |  {r.player_b:25s} {r.b_win_prob:.1%}")
        print(f"  Fair ML:      {r.player_a:25s} {r.a_fair_odds:>6s}  |  {r.player_b:25s} {r.b_fair_odds:>6s}")
        print(f"  DR:           {r.player_a:25s} {r.dominance_ratio_a:.4f}  |  {r.player_b:25s} {r.dominance_ratio_b:.4f}")
        print(f"  Edge vs Mkt:  {r.model_edge_vs_market_pct:+.1f}%")
        print(f"  Rec (ML):     {r.recommendation_ml}")
        print(f"  Rec (O/U):    {r.recommendation_over_under}")
        print(f"  Confidence:   {r.confidence_ml:.1f}%")
        print(f"  Stylistic:    {r.stylistic_edge}")
        print(f"  Analysis:")
        for line in r.analysis_summary.split("\n"):
            print(f"    {line}")
        print(f"  Sharp Consensus:")
        for line in r.sharp_consensus.split(". "):
            print(f"    • {line.strip()}.")
        print(f"  Umpire Watch:")
        for line in r.umpire_notes.split(". "):
            print(f"    • {line.strip()}.")

    print(f"\n{separator}")
    print("  SHARP BETTING SUMMARY")
    print(separator)
    for r in results:
        print(f"  {r.player_a} vs {r.player_b}:")
        if "BET" in r.recommendation_ml:
            print(f"    [BET] {r.recommendation_ml} (conf: {r.confidence_ml:.1f}%)")
        elif "LEAN" in r.recommendation_ml:
            print(f"    [LEAN] {r.recommendation_ml} (conf: {r.confidence_ml:.1f}%)")
        else:
            print(f"    [PASS] {r.recommendation_ml} (conf: {r.confidence_ml:.1f}%)")
    print(separator)


# ---------------------------------------------------------------------------
# Push to Discord (enhanced with rich formatting for analysis/umpire/sharps)
# ---------------------------------------------------------------------------

def push_to_discord(results: List[MatchOutput]) -> bool:
    if not DISCORD_WEBHOOK_URL:
        print("ERROR: DISCORD_WEBHOOK_URL not set")
        return False

    embeds = []

    for i, r in enumerate(results, 1):
        # Color coding
        if "BET" in r.recommendation_ml:
            color = 3066993  # Green
        elif "LEAN" in r.recommendation_ml:
            color = 16776960  # Yellow
        else:
            color = 9807270  # Gray

        # Determine match time emoji
        time_emoji = "🌅" if "Lehecka" in r.player_a else "☀️"

        sharp_short = r.sharp_consensus[:250] + ("..." if len(r.sharp_consensus) > 250 else "")
        umpire_short = r.umpire_notes[:200] + ("..." if len(r.umpire_notes) > 200 else "")

        embed = {
            "title": f"🎾 Wimbledon 2026 — {r.player_a} vs {r.player_b}",
            "color": color,
            "fields": [
                {
                    "name": f"{time_emoji} Match Info",
                    "value": f"**{r.start_time}** EDT | **2nd Round**\n{r.player_a} (#{r.player_a_rank}) vs {r.player_b} (#{r.player_b_rank})",
                    "inline": False,
                },
                {
                    "name": "📊 Market",
                    "value": f"**{r.player_a}** {r.a_fair_odds} | **{r.player_b}** {r.b_fair_odds}\nImplied: {r.market_favorite_prob:.0%} | Edge: {r.model_edge_vs_market_pct:+.1f}%",
                    "inline": True,
                },
                {
                    "name": "📐 DR",
                    "value": f"{r.player_a}: {r.dominance_ratio_a:.3f}\n{r.player_b}: {r.dominance_ratio_b:.3f}",
                    "inline": True,
                },
                {
                    "name": "🎯 Win Prob",
                    "value": f"{r.player_a}: **{r.a_win_prob:.0%}**\n{r.player_b}: **{r.b_win_prob:.0%}**",
                    "inline": True,
                },
                {
                    "name": "⚔️ Style",
                    "value": r.stylistic_edge[:256],
                    "inline": False,
                },
                {
                    "name": "🏆 Rec (ML)",
                    "value": f"**{r.recommendation_ml}** (Conf: {r.confidence_ml:.0f}%)\n📌 {r.recommendation_over_under}",
                    "inline": False,
                },
                {
                    "name": "🧠 Sharp Consensus",
                    "value": sharp_short,
                    "inline": False,
                },
                {
                    "name": "⚖️ Umpire",
                    "value": umpire_short,
                    "inline": False,
                },
            ],
            "footer": {"text": f"MultiSportPredict | Wimbledon 2026 — July 2"},
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        embeds.append(embed)

    # ---- BETTING SLIP SUMMARY ----
    strong_bets = []
    sharp_tips = []
    over_under_recs = []

    for r in results:
        if "BET" in r.recommendation_ml:
            strong_bets.append(
                f"✅ **{r.model_favorite} ML** — Conf: {r.confidence_ml:.1f}% | "
                f"Edge: {r.model_edge_vs_market_pct:+.1f}%"
            )
        elif "LEAN" in r.recommendation_ml:
            sharp_tips.append(
                f"📌 **{r.model_favorite} ML** — Conf: {r.confidence_ml:.1f}% | "
                f"Edge: {r.model_edge_vs_market_pct:+.1f}%"
            )
        else:
            sharp_tips.append(
                f"👀 **{r.model_favorite} ML** (marginal) — Conf: {r.confidence_ml:.1f}% | "
                f"Edge: {r.model_edge_vs_market_pct:+.1f}%"
            )

        if "OVER" in r.recommendation_over_under:
            over_under_recs.append(f"📈 **{r.player_a} vs {r.player_b}** — {r.recommendation_over_under}")

    # Build sharp play recommendations
    sharp_plays = []

    # Match 1 sharp plays
    sharp_plays.append(
        "**Match 1: Lehecka vs Molcan**\n"
        "   🎯 Sharp Play: **Lehecka -2.5 Games** — surface contrast extreme\n"
        "   🎯 Alt Play: **Lehecka to win 1st Set & Match** — strong starter"
    )

    # Match 2 sharp plays
    sharp_plays.append(
        "**Match 2: Mensik vs Dimitrov**\n"
        "   🎯 Sharp Play: **Dimitrov ML** (-165) — experience edge on grass\n"
        "   🎯 Alt Play: **Dimitrov 3-1 Set Betting** — Mensik likely steals a set via serve"
    )

    sharp_field_value = "\n\n".join(sharp_plays)

    slip_embed = {
        "title": "🧾 WIMBLEDON JULY 2 — BETTING SLIP & SHARP PLAYS",
        "color": 3066993,
        "fields": [
            {
                "name": "📋 Model Recommendations",
                "value": (
                    (("\n".join(strong_bets) + "\n") if strong_bets else "") +
                    ("\n".join(sharp_tips) if sharp_tips else "No strong model edges identified")
                )[:1024],
                "inline": False,
            },
            {
                "name": "🎯 Sharp Money Consensus",
                "value": sharp_field_value[:1024],
                "inline": False,
            },
            {
                "name": "📈 Over/Under Direction",
                "value": (
                    "\n".join(over_under_recs) if over_under_recs
                    else "No strong O/U lean — monitor in-play"
                )[:1024],
                "inline": False,
            },
            {
                "name": "⚠️ Risk Notes",
                "value": (
                    "• Lehecka/Molcan: Extreme surface contrast — Lehecka's flat game dominates low grass bounce\n"
                    "• Mensik/Dimitrov: Mensik needs 65%+ 1st serves to stay competitive\n"
                    "• Dimitrov's return quality (80/100) is elite vs big servers\n"
                    "• Consider live-betting Mensik if he holds serve early — line may shift\n"
                    "• Umpire strictness critical for Mensik's service rhythm"
                ),
                "inline": False,
            },
        ],
        "footer": {"text": "MultiSportPredict | Wimbledon July 2 | Sharp Consensus | Bet Responsibly"},
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    embeds.append(slip_embed)

    payload = {"embeds": embeds}

    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
        if resp.status_code in (200, 204):
            print("[OK] Analysis pushed to Discord successfully")
            return True
        print(f"[FAIL] Discord returned {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as exc:
        print(f"[ERROR] Discord request failed: {exc}")
        return False


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
    out_path = out_dir / "wimbledon_july2_two_matches_2026.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "results": [asdict(r) for r in results],
            },
            f,
            indent=2,
        )
    print(f"\nSaved: {out_path}")

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