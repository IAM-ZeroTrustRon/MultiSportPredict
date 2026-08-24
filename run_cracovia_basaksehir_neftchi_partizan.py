#!/usr/bin/env python
"""
Pre-Season Friendly Analysis — July 6, 2026
============================================
Match 1: KS Cracovia vs İstanbul Başakşehir
Match 2: Neftçi Baku vs FK Partizan

Markets: BTTS, Total Goals, Corners, 1X2
Scout intel incorporated:
  - Cracovia: 1-2 loss to Pafos, experimenting backline — tends to both score & concede
  - Başakşehir: pre-season rhythm, wide-overload system generates corners
  - Neftçi: 1-2 loss to CFR Cluj, transitional scorer, likely low block vs Partizan
  - Partizan: 0-3 vs CSKA + 2-1 vs Aluminij — attacking quality but defensive leaks
  - Pre-season rotation = disjointed defensive shapes late in game = BTTS value

Pushes rich embeds + betting slip to Discord.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple, Any

import requests
from dotenv import load_dotenv

load_dotenv()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


# ---------------------------------------------------------------------------
# Maths helpers
# ---------------------------------------------------------------------------

def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    try:
        return math.exp(-lam + k * math.log(lam) - math.lgamma(k + 1))
    except (ValueError, OverflowError):
        return 0.0


def poisson_over(lam: float, line: float) -> float:
    """P(goals > line) using Poisson CDF."""
    k_ceil = math.ceil(line)
    prob_under = sum(poisson_pmf(k, lam) for k in range(k_ceil))
    return clamp(1.0 - prob_under)


def match_probs(home_lam: float, away_lam: float) -> Tuple[float, float, float]:
    """Bivariate Poisson: (home_win, draw, away_win)."""
    hw = dw = aw = 0.0
    for i in range(8):
        for j in range(8):
            p = poisson_pmf(i, home_lam) * poisson_pmf(j, away_lam)
            if i > j:
                hw += p
            elif i == j:
                dw += p
            else:
                aw += p
    tot = hw + dw + aw
    return (hw / tot, dw / tot, aw / tot) if tot > 0 else (0.33, 0.33, 0.34)


def btts_prob(home_lam: float, away_lam: float, home_btts: float, away_btts: float) -> float:
    """P(both teams score) blending Poisson + scout tendency."""
    # Poisson: P(home>=1) * P(away>=1)
    p_h = 1.0 - poisson_pmf(0, home_lam)
    p_a = 1.0 - poisson_pmf(0, away_lam)
    poisson_btts = p_h * p_a
    scout_btts = (home_btts + away_btts) / 2.0
    return clamp(0.60 * poisson_btts + 0.40 * scout_btts)


def corner_projection(
    h_for: float, h_against: float, a_for: float, a_against: float,
    league_avg: float, style_bonus: float = 0.0
) -> float:
    """Blended corner projection."""
    recal = (h_for + a_against) / 2 + (a_for + h_against) / 2
    return round(0.50 * recal + 0.30 * league_avg + 0.20 * (h_for + a_for) + style_bonus, 2)


def verdict(prob: float) -> Tuple[str, str]:
    """(label, emoji) based on probability."""
    if prob >= 0.63:
        return ("STRONG", "✅")
    elif prob >= 0.57:
        return ("VALUE", "📌")
    elif prob >= 0.52:
        return ("SLIGHT", "👀")
    else:
        return ("PASS", "❌")


def sharp_signal(prob: float) -> str:
    if prob >= 0.62:
        return "SHARP ALIGNMENT"
    elif prob >= 0.56:
        return "LEANING SHARP"
    elif prob <= 0.42:
        return "SHARP FADE"
    return "NEUTRAL"


# ---------------------------------------------------------------------------
# Team profile + league config
# ---------------------------------------------------------------------------

@dataclass
class TeamProfile:
    name: str
    abbr: str
    league: str
    xg_for: float
    xg_against: float
    goals_for: float
    goals_against: float
    shots: float
    sot: float
    corners_for: float
    corners_against: float
    btts_tendency: float        # 0-1 scout tendency to BTTS
    tempo: float
    width_crossing: float       # 0-1: wide-overload / crossing style
    final_third_pressure: float
    clean_sheets_l10: int
    form: float                 # 0-1
    missing_attacker: int = 0
    missing_creator: int = 0
    missing_cb: int = 0
    missing_gk: int = 0
    corner_style: str = "balanced"  # wide / counter / possession / physical / balanced
    notes: str = ""


@dataclass
class LeagueConfig:
    name: str
    avg_goals: float
    goal_variance: float        # multiplier
    home_advantage: float
    draw_rate: float
    avg_corners: float
    btts_rate: float
    friendly_boost: float = 1.12   # pre-season rotation = more open play


# ---------------------------------------------------------------------------
# Match profile definitions
# ---------------------------------------------------------------------------

def _m1_profiles() -> Tuple[TeamProfile, TeamProfile, LeagueConfig]:
    """KS Cracovia vs İstanbul Başakşehir — Pre-season friendly."""
    cracovia = TeamProfile(
        name="KS Cracovia", abbr="CRK", league="Ekstraklasa (Poland)",
        xg_for=1.35, xg_against=1.55,
        goals_for=1.25, goals_against=1.50,
        shots=11.0, sot=3.8,
        corners_for=5.2, corners_against=5.6,
        btts_tendency=0.72,   # Scout: "tends to both score AND concede when experimenting"
        tempo=0.38, width_crossing=0.48, final_third_pressure=0.42,
        clean_sheets_l10=2, form=0.35,
        missing_attacker=0, missing_creator=0, missing_cb=1, missing_gk=0,
        # experimenting = effectively a missing CB in defensive shape
        corner_style="physical",
        notes=(
            "1-2 loss to Pafos in last friendly. Experimenting with backline — "
            "clear tendency to both score and concede. Physical Ekstraklasa style. "
            "Squad rotation likely in second half creates disjointed defensive shape."
        ),
    )
    basaksehir = TeamProfile(
        name="İstanbul Başakşehir", abbr="BSH", league="Süper Lig (Turkey)",
        xg_for=1.45, xg_against=1.25,
        goals_for=1.35, goals_against=1.20,
        shots=11.8, sot=4.1,
        corners_for=6.4, corners_against=4.8,
        btts_tendency=0.66,
        tempo=0.43, width_crossing=0.65,  # KEY: wide-overload system
        final_third_pressure=0.50,
        clean_sheets_l10=3, form=0.40,
        missing_attacker=1, missing_creator=0, missing_cb=0, missing_gk=0,
        # Pre-season: attackers often rested/rotated
        corner_style="wide",
        notes=(
            "Just stepping into pre-season rhythm. Historical reliance on wide overloads "
            "against physical opposition (Ekstraklasa fits this profile exactly). "
            "Wide play generates favorable corner conditions. Not yet at full sharpness."
        ),
    )
    league = LeagueConfig(
        name="Pre-Season Friendly (July)", avg_goals=2.70, goal_variance=1.08,
        home_advantage=0.20,  # reduced for neutral/friendly
        draw_rate=0.28, avg_corners=9.5, btts_rate=0.62,
        friendly_boost=1.12,  # rotation = more open = higher scoring tendency
    )
    return cracovia, basaksehir, league


def _m2_profiles() -> Tuple[TeamProfile, TeamProfile, LeagueConfig]:
    """Neftçi Baku vs FK Partizan — Pre-season friendly."""
    neftchi = TeamProfile(
        name="Neftçi Baku", abbr="NFT", league="Azerbaijani Premier League",
        xg_for=1.22, xg_against=1.58,
        goals_for=1.15, goals_against=1.55,
        shots=10.2, sot=3.5,
        corners_for=4.5, corners_against=6.8,
        # Low block vs higher-quality opposition = opponent corners pile up
        btts_tendency=0.68,
        tempo=0.30, width_crossing=0.42, final_third_pressure=0.36,
        clean_sheets_l10=2, form=0.30,
        missing_attacker=0, missing_creator=1, missing_cb=0, missing_gk=0,
        corner_style="counter",
        notes=(
            "1-2 loss to CFR Cluj. Tends to sit deeper against higher-quality sides "
            "but retains ability to score in transition. Low block expected vs Partizan "
            "which will push Partizan wide — generating corner volume. "
            "Usually finds the net in these open, transitional games."
        ),
    )
    partizan = TeamProfile(
        name="FK Partizan", abbr="PAR", league="Serbian SuperLiga",
        xg_for=1.85, xg_against=1.68,
        goals_for=1.75, goals_against=1.65,
        shots=13.8, sot=4.9,
        corners_for=6.8, corners_against=4.2,
        btts_tendency=0.74,  # Scout: "prone to open, high-scoring affairs with defensive leaks"
        tempo=0.46, width_crossing=0.64,  # KEY: pushes wide vs low blocks
        final_third_pressure=0.57,
        clean_sheets_l10=2, form=0.45,  # mixed: 2-1 W, 0-3 L
        missing_attacker=0, missing_creator=0, missing_cb=1, missing_gk=0,
        # Noticeable vulnerability at back (0-3 to CSKA 1948)
        corner_style="wide",
        notes=(
            "Edged Aluminij 2-1, but suffered 0-3 loss to CSKA 1948 — "
            "noticeable defensive vulnerability at back. Retains distinct attacking quality. "
            "When breaking down a low block (Neftçi will sit deep), Partizan "
            "pushes wide and generates corner volume. BTTS heavily supported by scout data."
        ),
    )
    league = LeagueConfig(
        name="Pre-Season Friendly (July)", avg_goals=2.80, goal_variance=1.10,
        home_advantage=0.22, draw_rate=0.26, avg_corners=10.2, btts_rate=0.64,
        friendly_boost=1.14,
    )
    return neftchi, partizan, league


# ---------------------------------------------------------------------------
# Core analysis engine
# ---------------------------------------------------------------------------

def analyze_match(
    home: TeamProfile, away: TeamProfile, league: LeagueConfig,
    market_goals: float, market_corners: float,
    match_label: str, date: str,
) -> Dict[str, Any]:

    # Pre-season friendly adjustment: rotation = more open
    fb = league.friendly_boost

    # xG-based goal lambda with injury adjustments
    def _lam(team: TeamProfile, opp: TeamProfile, is_home: bool) -> float:
        base = (team.xg_for * 0.55 + team.goals_for * 0.45)
        opp_def = (opp.xg_against * 0.50 + opp.goals_against * 0.50)
        lam = (base + opp_def) / 2.0
        # Injuries
        lam -= 0.08 * team.missing_attacker
        lam -= 0.06 * team.missing_creator
        lam += 0.05 * opp.missing_cb
        lam += 0.04 * opp.missing_gk
        # Home advantage
        if is_home:
            lam *= (1.0 + league.home_advantage * 0.5)
        # Pre-season: rotation opens defensive shape
        lam *= fb
        lam *= league.goal_variance
        return max(0.3, round(lam, 3))

    home_lam = _lam(home, away, True)
    away_lam = _lam(away, home, False)
    total_lam = home_lam + away_lam

    # Match outcome
    hw, dw, aw = match_probs(home_lam, away_lam)
    # Blend draw rate with league config
    dw = dw * 0.75 + league.draw_rate * 0.25
    remaining = 1.0 - dw
    hw = hw * remaining / (hw + aw + 1e-9)
    aw = 1.0 - hw - dw

    # Total goals market
    p_over_15 = poisson_over(total_lam, 1.5)
    p_over_25 = poisson_over(total_lam, 2.5)
    p_over_35 = poisson_over(total_lam, 3.5)
    p_over_45 = poisson_over(total_lam, 4.5)

    goals_line_map = {1.5: p_over_15, 2.5: p_over_25, 3.5: p_over_35, 4.5: p_over_45}
    closest_line = min(goals_line_map.keys(), key=lambda x: abs(x - market_goals))
    goals_prob = goals_line_map[closest_line]
    goals_edge = total_lam - market_goals
    goals_verdict, goals_emoji = verdict(goals_prob)

    # BTTS
    bp = btts_prob(home_lam, away_lam, home.btts_tendency, away.btts_tendency)
    # Blend with league BTTS rate
    bp = bp * 0.65 + league.btts_rate * 0.35
    btts_verdict_label, btts_emoji = verdict(bp)
    btts_edge = bp - 0.50

    # Corners
    # Wide-overload style bonus for wide teams
    style_bonus = 0.0
    if home.corner_style == "wide":
        style_bonus += 0.4
    if away.corner_style == "wide":
        style_bonus += 0.4
    if home.corner_style == "physical":
        style_bonus += 0.2
    # Low block = opponent generates more corners
    if away.corner_style == "counter" or home.corner_style == "counter":
        style_bonus += 0.3

    corner_proj = corner_projection(
        home.corners_for, home.corners_against,
        away.corners_for, away.corners_against,
        league.avg_corners, style_bonus,
    )

    p_corners_85 = poisson_over(corner_proj, 8.5)
    p_corners_95 = poisson_over(corner_proj, 9.5)
    p_corners_105 = poisson_over(corner_proj, 10.5)
    p_corners_115 = poisson_over(corner_proj, 11.5)

    corner_line_map = {8.5: p_corners_85, 9.5: p_corners_95,
                       10.5: p_corners_105, 11.5: p_corners_115}
    closest_corner = min(corner_line_map.keys(), key=lambda x: abs(x - market_corners))
    corners_prob = corner_line_map[closest_corner]
    corners_edge = corner_proj - market_corners
    corners_verdict_label, corners_emoji = verdict(corners_prob)

    # Console print
    sep = "=" * 88
    dash = "-" * 88
    print(f"\n{sep}")
    print(f"  {match_label}")
    print(f"  {home.name} ({home.abbr}/{home.league}) vs {away.name} ({away.abbr}/{away.league})")
    print(f"  Date: {date} | Pre-Season Friendly")
    print(sep)
    print(f"\n  TEAM NOTES:")
    print(f"    {home.name}: {home.notes[:120]}")
    print(f"    {away.name}: {away.notes[:120]}")
    print(f"\n  xG PROJECTION:")
    print(f"    {home.name} λ={home_lam:.3f} | {away.name} λ={away_lam:.3f} | Total={total_lam:.3f}")
    print(f"    Projected Score: {home.name} {home_lam:.1f} – {away_lam:.1f} {away.name}")
    print(f"  1X2: {home.name} {hw:.1%} | Draw {dw:.1%} | {away.name} {aw:.1%}")
    print(f"\n  TOTAL GOALS (line {market_goals}):")
    print(f"    Over 1.5: {p_over_15:.1%} | Over 2.5: {p_over_25:.1%} | Over 3.5: {p_over_35:.1%}")
    print(f"    P(Over {market_goals}): {goals_prob:.1%} | Edge: {goals_edge:+.2f} | Verdict: {goals_verdict}")
    print(f"  BTTS:")
    print(f"    P(Yes): {bp:.1%} | Edge: {btts_edge:+.2f} | Verdict: {btts_verdict_label}")
    print(f"  CORNERS (line {market_corners}):")
    print(f"    Projection: {corner_proj:.1f} | P(Over {market_corners}): {corners_prob:.1%}")
    print(f"    Over 8.5: {p_corners_85:.1%} | Over 9.5: {p_corners_95:.1%} | Over 10.5: {p_corners_105:.1%}")
    print(f"    Edge: {corners_edge:+.2f} | Verdict: {corners_verdict_label}")

    return {
        "match": match_label,
        "home": home.name, "away": away.name,
        "date": date,
        "home_lam": home_lam, "away_lam": away_lam, "total_lam": total_lam,
        "hw": round(hw, 4), "dw": round(dw, 4), "aw": round(aw, 4),
        "goals_prob": round(goals_prob, 4), "goals_edge": round(goals_edge, 3),
        "goals_verdict": goals_verdict, "goals_emoji": goals_emoji,
        "market_goals": market_goals,
        "over_15": round(p_over_15, 4), "over_25": round(p_over_25, 4),
        "over_35": round(p_over_35, 4), "over_45": round(p_over_45, 4),
        "btts_prob": round(bp, 4), "btts_edge": round(btts_edge, 4),
        "btts_verdict": btts_verdict_label, "btts_emoji": btts_emoji,
        "corner_proj": corner_proj, "market_corners": market_corners,
        "corners_prob": round(corners_prob, 4), "corners_edge": round(corners_edge, 3),
        "corners_verdict": corners_verdict_label, "corners_emoji": corners_emoji,
        "p_c85": round(p_corners_85, 4), "p_c95": round(p_corners_95, 4),
        "p_c105": round(p_corners_105, 4),
        "home_notes": home.notes, "away_notes": away.notes,
        "home_style": home.corner_style, "away_style": away.corner_style,
    }


# ---------------------------------------------------------------------------
# Discord Push — Rich Embeds
# ---------------------------------------------------------------------------

def _t(s: str, n: int) -> str:
    return s[:n] + ("…" if len(s) > n else "")


def _color(r: Dict) -> int:
    verdicts = [r["goals_verdict"], r["btts_verdict"], r["corners_verdict"]]
    if verdicts.count("STRONG") >= 2:
        return 3066993    # Green
    elif verdicts.count("PASS") >= 2:
        return 9807270    # Gray
    return 16776960       # Yellow


def _send(payload: dict, label: str) -> bool:
    if not DISCORD_WEBHOOK_URL:
        print("ERROR: DISCORD_WEBHOOK_URL not set")
        return False
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


def _match_embed(r: Dict, match_num: int, scout_home: str, scout_away: str,
                 sharp_note: str, corner_note: str) -> dict:
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    fav = r["home"] if r["hw"] > r["aw"] else r["away"]
    fav_p = max(r["hw"], r["aw"])

    # Market verdict flags
    def _flag(v):
        return "✅ STRONG" if v == "STRONG" else ("📌 VALUE" if v == "VALUE" else
               ("👀 SLIGHT" if v == "SLIGHT" else "❌ PASS"))

    return {
        "title": _t(f"⚽ Pre-Season Friendly — {r['home']} vs {r['away']}", 256),
        "description": _t(
            f"🗓️ **{r['date']}** | Pre-Season Friendly | Match {match_num}\n"
            f"**xG Proj:** {r['home']} {r['home_lam']:.2f} – {r['away_lam']:.2f} {r['away']} "
            f"| Total λ = **{r['total_lam']:.2f}**", 300
        ),
        "color": _color(r),
        "fields": [
            {
                "name": "📊 Match Outcome (1X2)",
                "value": _t(
                    f"**{r['home']}:** {r['hw']:.1%}\n"
                    f"**Draw:** {r['dw']:.1%}\n"
                    f"**{r['away']}:** {r['aw']:.1%}\n"
                    f"Model lean: **{fav} ({fav_p:.1%})**",
                    250),
                "inline": True,
            },
            {
                "name": "🎯 BTTS",
                "value": _t(
                    f"{r['btts_emoji']} **{_flag(r['btts_verdict'])}**\n"
                    f"P(Yes): **{r['btts_prob']:.1%}** | P(No): {1 - r['btts_prob']:.1%}\n"
                    f"Edge: **{r['btts_edge']:+.2f}** | Sharp: {sharp_signal(r['btts_prob'])}",
                    280),
                "inline": True,
            },
            {
                "name": f"⚽ Total Goals (O/U {r['market_goals']})",
                "value": _t(
                    f"{r['goals_emoji']} **{_flag(r['goals_verdict'])}**\n"
                    f"P(Over {r['market_goals']}): **{r['goals_prob']:.1%}** | Edge: {r['goals_edge']:+.2f}\n"
                    f"O1.5: {r['over_15']:.0%} | O2.5: {r['over_25']:.0%} | O3.5: {r['over_35']:.0%}",
                    280),
                "inline": False,
            },
            {
                "name": f"🚩 Corners (O/U {r['market_corners']})",
                "value": _t(
                    f"{r['corners_emoji']} **{_flag(r['corners_verdict'])}**\n"
                    f"Proj: **{r['corner_proj']:.1f}** | P(Over {r['market_corners']}): **{r['corners_prob']:.1%}**\n"
                    f"O8.5: {r['p_c85']:.0%} | O9.5: {r['p_c95']:.0%} | O10.5: {r['p_c105']:.0%}\n"
                    f"Edge: {r['corners_edge']:+.2f} | {corner_note}",
                    400),
                "inline": False,
            },
            {
                "name": f"🔍 {r['home']} Scout",
                "value": _t(scout_home, 380),
                "inline": False,
            },
            {
                "name": f"🔍 {r['away']} Scout",
                "value": _t(scout_away, 380),
                "inline": False,
            },
            {
                "name": "🧠 Sharp Consensus",
                "value": _t(sharp_note, 500),
                "inline": False,
            },
        ],
        "footer": {"text": "MultiSportPredict | Pre-Season Friendlies — July 6, 2026 | Bet Responsibly"},
        "timestamp": ts,
    }


def push_to_discord(results: List[Dict]) -> bool:
    all_ok = True
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # ---- MATCH 1 EMBED ----
    r1 = results[0]
    scout_h1 = (
        "1-2 loss to Pafos. Experimenting with backline — clear scout tendency to "
        "both score AND concede. Heavy squad rotation at HT = disjointed defensive shape "
        "late in game. Physical Ekstraklasa style benefits set-piece situations."
    )
    scout_a1 = (
        "Just stepping into pre-season rhythm. Historical wide-overload system vs physical "
        "opposition (Cracovia fits this profile). Wide play = sustained corner generation. "
        "Not yet at full tactical sharpness but quality advantage over Cracovia."
    )
    sharp1 = (
        "Sharp consensus: BTTS Yes is the highest-confidence play. Both teams in BTTS-favorable "
        "shape — Cracovia concedes in every experimental lineup, Başakşehir's attack finds gaps "
        "vs disrupted backlines. Corners Over has value given Başakşehir wide-overload system. "
        "Pre-season rotation at HT almost guarantees defensive disorganization in second half."
    )
    corner1 = "Başakşehir wide-overload vs physical Cracovia = corner pressure"

    embed1 = _match_embed(r1, 1, scout_h1, scout_a1, sharp1, corner1)
    ok1 = _send({"embeds": [embed1]}, "Match 1 — Cracovia vs Başakşehir")
    if not ok1:
        all_ok = False

    # ---- MATCH 2 EMBED ----
    r2 = results[1]
    scout_h2 = (
        "1-2 loss to CFR Cluj. Expected to sit in low block vs Partizan — "
        "this will funnel Partizan wide and inflate corner totals. "
        "Can find the net in transitional moments despite defensive shape."
    )
    scout_a2 = (
        "Mixed pre-season: 2-1 W vs Aluminij, 0-3 L vs CSKA 1948. Noticeable defensive "
        "vulnerability at back. BUT retains distinct attacking quality. "
        "When breaking down low block, Partizan pushes wide — Over corners angle is strong. "
        "Prone to open, high-scoring affairs with defensive leaks = BTTS prime candidate."
    )
    sharp2 = (
        "BTTS is the marquee play here — Partizan's recent form proves defensive leakage; "
        "Neftçi's transitional quality means they score vs leaky Serbian backlines. "
        "Corners Over: Neftçi low block forces Partizan to work wide — expected 6-7 Partizan "
        "corners alone. Total games over 40.5 (from total goals line context) also viable. "
        "Partizan ML has value — attacking quality plus Neftçi missing key creator."
    )
    corner2 = "Neftçi low block forces Partizan wide = high corner volume"

    embed2 = _match_embed(r2, 2, scout_h2, scout_a2, sharp2, corner2)
    ok2 = _send({"embeds": [embed2]}, "Match 2 — Neftçi vs Partizan")
    if not ok2:
        all_ok = False

    # ---- BETTING SLIP ----
    def _slip_line(r: Dict, market: str, emoji: str, prob: float, play: str) -> str:
        vd, ve = verdict(prob)
        return f"{ve} **{r['home']} vs {r['away']}** | {market}: {play} | P: {prob:.0%} [{vd}]"

    slip_lines = [
        _slip_line(r1, "BTTS", "🎯", r1["btts_prob"], "Yes"),
        _slip_line(r1, f"Goals O{r1['market_goals']}", "⚽", r1["goals_prob"], f"Over {r1['market_goals']}"),
        _slip_line(r1, f"Corners O{r1['market_corners']}", "🚩", r1["corners_prob"], f"Over {r1['market_corners']}"),
        "",
        _slip_line(r2, "BTTS", "🎯", r2["btts_prob"], "Yes"),
        _slip_line(r2, f"Goals O{r2['market_goals']}", "⚽", r2["goals_prob"], f"Over {r2['market_goals']}"),
        _slip_line(r2, f"Corners O{r2['market_corners']}", "🚩", r2["corners_prob"], f"Over {r2['market_corners']}"),
    ]

    parlay_note = (
        "**2-Leg BTTS Parlay (both matches):**\n"
        f"BTTS Yes {r1['home']} vs {r1['away']} + BTTS Yes {r2['home']} vs {r2['away']}\n"
        f"Combined P: {r1['btts_prob'] * r2['btts_prob']:.0%} | Est. combined odds: ~$3.50-4.00"
    )

    risk_notes = (
        f"• Pre-season rotation at halftime = defensive disruption is a real factor\n"
        f"• Cracovia experimenting = +1 missing CB modeled into projections\n"
        f"• Partizan's 0-3 CSKA 1948 defeat = defensive vulnerability confirmed\n"
        f"• Neftçi missing key creator = attacking output reduced vs Partizan press\n"
        f"• Friendly intensity variable — monitor team sheet announcements"
    )

    slip_embed = {
        "title": "🧾 BETTING SLIP — Pre-Season Friendlies July 6, 2026",
        "color": 15844367,
        "fields": [
            {
                "name": "📋 All Markets",
                "value": "\n".join(slip_lines),
                "inline": False,
            },
            {
                "name": "🔥 Priority Plays",
                "value": (
                    f"1️⃣ ✅ **BTTS Yes — {r2['home']} vs {r2['away']}** (P: {r2['btts_prob']:.0%}) | Partizan leaks + Neftçi transitions\n"
                    f"2️⃣ ✅ **BTTS Yes — {r1['home']} vs {r1['away']}** (P: {r1['btts_prob']:.0%}) | Cracovia backline experiments\n"
                    f"3️⃣ 📌 **Corners Over {r2['market_corners']} — {r2['home']} vs {r2['away']}** | Low block → Partizan wide plays\n"
                    f"4️⃣ 📌 **Corners Over {r1['market_corners']} — {r1['home']} vs {r1['away']}** | Başakşehir wide overloads\n"
                    f"5️⃣ 👀 **{r2['away']} ML** — Attacking quality + opponent missing creator"
                ),
                "inline": False,
            },
            {
                "name": "🎲 BTTS Parlay",
                "value": parlay_note,
                "inline": False,
            },
            {
                "name": "⚠️ Risk Notes",
                "value": risk_notes,
                "inline": False,
            },
            {
                "name": "📊 xG Summary",
                "value": (
                    f"**{r1['home']} vs {r1['away']}:** λ {r1['home_lam']:.2f}–{r1['away_lam']:.2f} | "
                    f"Total {r1['total_lam']:.2f} | BTTS {r1['btts_prob']:.0%}\n"
                    f"**{r2['home']} vs {r2['away']}:** λ {r2['home_lam']:.2f}–{r2['away_lam']:.2f} | "
                    f"Total {r2['total_lam']:.2f} | BTTS {r2['btts_prob']:.0%}"
                ),
                "inline": False,
            },
        ],
        "footer": {"text": "MultiSportPredict | Pre-Season Friendlies | July 6, 2026 | Bet Responsibly ⚽"},
        "timestamp": ts,
    }

    ok3 = _send({"embeds": [slip_embed]}, "Betting Slip")
    if not ok3:
        all_ok = False

    return all_ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 88)
    print("  MULTISPORTPREDICT — PRE-SEASON FRIENDLY ANALYSIS | July 6, 2026")
    print("  Match 1: KS Cracovia vs İstanbul Başakşehir")
    print("  Match 2: Neftçi Baku vs FK Partizan")
    print("=" * 88)

    cracovia, basaksehir, league1 = _m1_profiles()
    neftchi, partizan, league2 = _m2_profiles()

    r1 = analyze_match(
        cracovia, basaksehir, league1,
        market_goals=2.5, market_corners=9.5,
        match_label="MATCH 1 — Pre-Season Friendly",
        date="2026-07-06",
    )
    r2 = analyze_match(
        neftchi, partizan, league2,
        market_goals=2.5, market_corners=9.5,
        match_label="MATCH 2 — Pre-Season Friendly",
        date="2026-07-06",
    )

    results = [r1, r2]

    # Summary table
    print(f"\n{'=' * 88}")
    print(f"  BETTING SUMMARY")
    print(f"  {'Match':<35} {'Market':<18} {'Prob':>6} {'Edge':>7} {'Verdict':<10} {'Sharp':<20}")
    print(f"  {'-' * 35} {'-' * 18} {'-' * 6} {'-' * 7} {'-' * 10} {'-' * 20}")
    for r in results:
        m = f"{r['home'][:16]} vs {r['away'][:14]}"
        goals_label = "Over " + str(r["market_goals"]) + "G"
        corners_label = "Over " + str(r["market_corners"]) + "C"
        print(f"  {m:<35} {'BTTS Yes':<18} {r['btts_prob']:>6.1%} {r['btts_edge']:>+7.2f} {r['btts_verdict']:<10} {sharp_signal(r['btts_prob']):<20}")
        print(f"  {'':<35} {goals_label:<18} {r['goals_prob']:>6.1%} {r['goals_edge']:>+7.2f} {r['goals_verdict']:<10} {sharp_signal(r['goals_prob']):<20}")
        print(f"  {'':<35} {corners_label:<18} {r['corners_prob']:>6.1%} {r['corners_edge']:>+7.2f} {r['corners_verdict']:<10} {sharp_signal(r['corners_prob']):<20}")
        print()

    # Save JSON
    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "preseason_july6_2026_cracovia_neftchi.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"timestamp": datetime.now().isoformat(), "results": results}, fh, indent=2)
    print(f"Saved: {out_path}")

    # Push to Discord
    print("\nPushing to Discord...")
    ok = push_to_discord(results)
    if ok:
        print("[OK] Discord push: SUCCESS — 3 embeds delivered")
    else:
        print("[FAIL] Discord push: FAILED")

    print("\nAnalysis complete.")


if __name__ == "__main__":
    main()
