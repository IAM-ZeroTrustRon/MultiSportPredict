#!/usr/bin/env python3
"""
ITF M15 Wuning — July 6, 2026 | Hard Court
Match 1: James Van Herzeele (BEL) vs Thanaphat Boosarawongse (THA) — R16
Match 2: Sheng Tang (CHN) vs Azuma Visaya (USA) — R16

SHARP ANGLES:
- Match 1: Boosarawongse ML despite lower ranking (Van Herzeele ~25% 2026 win rate, brutal slump)
- Match 2: AVOID Visaya -450 ML (zero value) — pivot to Straight Sets / -4.5 game handicap
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()


# ============================================================================
# HARD-COURT ITF MODEL
# Hard court weights: more return emphasis than grass, less pure serve dominance
# ============================================================================

def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _american_to_prob(odds: int) -> float:
    if odds < 0:
        return abs(odds) / (abs(odds) + 100.0)
    return 100.0 / (odds + 100.0)


@dataclass
class PlayerProfile:
    name: str
    hard_skill: float       # 0-100: hard court specific competency
    serve_power: float      # 0-100: serve effectiveness
    return_quality: float   # 0-100: return game quality
    form: float             # 0-100: recent form and match sharpness
    experience: float       # 0-100: match experience at this level
    home_boost: float = 0.0  # crowd/familiarity boost
    fatigue: float = 0.0     # penalty for fatigue/injury


@dataclass
class MatchInput:
    event: str
    player_a: PlayerProfile
    player_b: PlayerProfile
    market_favorite: str
    market_favorite_prob: float
    target_total_games_line: Optional[float] = None
    notes: str = ""


@dataclass
class MatchOutput:
    event: str
    player_a: str
    player_b: str
    a_win_prob: float
    b_win_prob: float
    model_favorite: str
    strength_delta: float
    model_edge_vs_market_pct: float
    recommendation_ml: str
    confidence_ml: float
    over_games_prob: Optional[float] = None
    over_games_line: Optional[float] = None
    recommendation_total: Optional[str] = None
    confidence_total: Optional[float] = None
    straight_sets_prob: float = 0.0
    game_handicap_prob: float = 0.0
    strong_bets: Optional[List[Dict]] = None


def _player_strength(p: PlayerProfile) -> float:
    """Weighted composite for hard court ITF tennis."""
    base = (
        0.30 * p.hard_skill
        + 0.25 * p.serve_power      # Slightly less than grass (0.28 on grass)
        + 0.20 * p.return_quality   # Slightly more than grass (0.17 on grass)
        + 0.15 * p.form
        + 0.10 * p.experience
    )
    base += p.home_boost
    base -= p.fatigue
    return base


def _win_prob(a_str: float, b_str: float) -> float:
    delta = a_str - b_str
    p = 1.0 / (1.0 + pow(2.718281828, -(delta / 8.5)))
    return _clamp(p, 0.05, 0.95)


def _confidence_from_prob(p: float) -> float:
    edge = abs(p - 0.5)
    return round(_clamp(50 + edge * 120, 0, 98), 1)


def _total_games_over_prob(a: PlayerProfile, b: PlayerProfile, line: float) -> float:
    hold_env  = (a.serve_power + b.serve_power) / 200.0
    delta     = abs(_player_strength(a) - _player_strength(b))
    closeness = _clamp(1.0 - delta / 40.0, 0.1, 1.0)
    # Hard court baseline (slightly lower hold-heavy than grass)
    base      = 0.45 + 0.18 * hold_env + 0.20 * closeness
    line_adj  = (line - 22.5) * 0.03
    return _clamp(base - line_adj, 0.10, 0.90)


def _straight_sets_prob(fav_win_prob: float, strength_delta: float) -> float:
    """Probability that the favorite wins in straight sets (2-0)."""
    base        = fav_win_prob * 0.85
    delta_boost = _clamp((strength_delta - 8.0) / 40.0, 0, 0.15)
    return _clamp(base + delta_boost, 0.10, 0.92)


def _game_handicap_prob(fav_win_prob: float, strength_delta: float, handicap: float) -> float:
    """Probability that the favorite covers a games handicap (e.g., -4.5)."""
    base        = fav_win_prob * 0.90
    delta_boost = _clamp((strength_delta - 10.0) / 50.0, 0, 0.15)
    line_pen    = handicap * 0.025
    return _clamp(base + delta_boost - line_pen, 0.10, 0.90)


def analyze_match(m: MatchInput) -> MatchOutput:
    a_s = _player_strength(m.player_a)
    b_s = _player_strength(m.player_b)
    a_prob = _win_prob(a_s, b_s)
    b_prob = 1.0 - a_prob

    if a_prob >= b_prob:
        model_fav      = m.player_a.name
        model_fav_prob = a_prob
        str_delta      = a_s - b_s
    else:
        model_fav      = m.player_b.name
        model_fav_prob = b_prob
        str_delta      = b_s - a_s

    edge    = (model_fav_prob - m.market_favorite_prob) * 100
    conf_ml = _confidence_from_prob(model_fav_prob)

    if edge >= 5.0 and conf_ml >= 62:
        rec_ml = f"BET {model_fav} ML"
    elif edge >= 2.0 and conf_ml >= 57:
        rec_ml = f"LEAN {model_fav} ML"
    else:
        rec_ml = "PASS ML"

    # Total games
    over_prob = rec_total = conf_total = None
    if m.target_total_games_line is not None:
        over_prob  = _total_games_over_prob(m.player_a, m.player_b, m.target_total_games_line)
        conf_total = _confidence_from_prob(over_prob)
        if over_prob >= 0.58:
            rec_total = f"BET OVER {m.target_total_games_line} games"
        elif over_prob >= 0.54:
            rec_total = f"LEAN OVER {m.target_total_games_line} games"
        else:
            rec_total = f"PASS totals ({m.target_total_games_line})"

    ss_prob = _straight_sets_prob(model_fav_prob, str_delta)
    gh_prob = _game_handicap_prob(model_fav_prob, str_delta, 4.5)

    strong_bets: List[Dict] = []
    if rec_ml.startswith("BET"):
        strong_bets.append({
            "market": "Moneyline", "pick": model_fav,
            "prob": round(model_fav_prob * 100, 1),
            "confidence": conf_ml,
            "edge_vs_market": round(edge, 1),
        })
    if rec_total and rec_total.startswith("BET") and over_prob is not None:
        strong_bets.append({
            "market": f"Total O{m.target_total_games_line}", "pick": f"Over {m.target_total_games_line}",
            "prob": round(over_prob * 100, 1),
            "confidence": conf_total,
            "edge_vs_market": None,
        })
    if ss_prob >= 0.60:
        strong_bets.append({
            "market": "Set Betting (2-0)", "pick": f"{model_fav} Straight Sets",
            "prob": round(ss_prob * 100, 1),
            "confidence": _confidence_from_prob(ss_prob),
            "edge_vs_market": None,
        })
    if gh_prob >= 0.60:
        strong_bets.append({
            "market": f"{model_fav} -4.5 Games Handicap", "pick": f"{model_fav} -4.5",
            "prob": round(gh_prob * 100, 1),
            "confidence": _confidence_from_prob(gh_prob),
            "edge_vs_market": None,
        })

    return MatchOutput(
        event=m.event,
        player_a=m.player_a.name, player_b=m.player_b.name,
        a_win_prob=round(a_prob, 4), b_win_prob=round(b_prob, 4),
        model_favorite=model_fav,
        strength_delta=round(str_delta, 2),
        model_edge_vs_market_pct=round(edge, 2),
        recommendation_ml=rec_ml,
        confidence_ml=conf_ml,
        over_games_prob=round(over_prob, 4) if over_prob is not None else None,
        over_games_line=m.target_total_games_line,
        recommendation_total=rec_total,
        confidence_total=conf_total,
        straight_sets_prob=round(ss_prob, 4),
        game_handicap_prob=round(gh_prob, 4),
        strong_bets=strong_bets,
    )


# ============================================================================
# MATCH DEFINITIONS
# ============================================================================

MATCHES = [
    MatchInput(
        event="ITF M15 Wuning — R16 | Match 1",
        player_a=PlayerProfile(
            name="James Van Herzeele",
            hard_skill=52,
            serve_power=58,
            return_quality=50,
            form=32,            # Brutal 2026 slump — ~25% main draw win rate
            experience=65,
        ),
        player_b=PlayerProfile(
            name="Thanaphat Boosarawongse",
            hard_skill=65,
            serve_power=60,
            return_quality=62,
            form=72,            # In form — 72% 1st serve in, beat Arseneault in qualifiers
            experience=50,
        ),
        market_favorite="Thanaphat Boosarawongse",
        market_favorite_prob=_american_to_prob(-250),   # ~71.4%
        target_total_games_line=19.5,
        notes=(
            "Van Herzeele (~1098 ATP) in catastrophic 2026 form — 25% main draw win rate, "
            "relies on qualifiers vs weak opponents. Boosarawongse (~1778 ATP) ranked lower but "
            "playing far better tennis: 72% first serve in, 12 wins including strong qualifier run. "
            "Market correctly ignores the ranking gap."
        ),
    ),
    MatchInput(
        event="ITF M15 Wuning — R16 | Match 2",
        player_a=PlayerProfile(
            name="Sheng Tang",
            hard_skill=52,
            serve_power=55,
            return_quality=48,
            form=38,            # Doubles specialist — 90%+ of career is doubles (170+ matches)
            experience=58,
            home_boost=2.0,     # Playing in China
        ),
        player_b=PlayerProfile(
            name="Azuma Visaya",
            hard_skill=68,
            serve_power=62,
            return_quality=63,
            form=80,            # 8-3 singles 2026, dominant qualifiers: 6-2 6-0, 6-4 6-2
            experience=55,
        ),
        market_favorite="Azuma Visaya",
        market_favorite_prob=_american_to_prob(-450),   # ~81.8%
        target_total_games_line=17.5,
        notes=(
            "Tang (~1889 ATP) spends ~90% of career on doubles circuit (170+ doubles matches w/ "
            "Zijiang Yang). Lacks singles match-rhythm and baseline endurance for extended rallies. "
            "Visaya (~1495 ATP) in peak form — 8-3 singles 2026, demolished qualifier opponents. "
            "AVOID -450 ML. Target: Visaya Straight Sets / -4.5 game handicap for value."
        ),
    ),
]

# Player prop definitions per match
MATCH1_PROPS = [
    {'player': 'Boosarawongse', 'prop': 'Set 1 Winner',         'line': '-230', 'prob': 0.76,
     'note': 'Van Herzeele notoriously poor match-starter in 2026'},
    {'player': 'Boosarawongse', 'prop': 'Games Won Over 11.5',  'line': '-115', 'prob': 0.73,
     'note': 'Projected 6-3 6-3 type scoreline = 12+ games for Boosarawongse'},
    {'player': 'Boosarawongse', 'prop': 'Total Games Under 20.5','line': '-110', 'prob': 0.66,
     'note': 'Dominant server suppresses set length — no extended rallies'},
    {'player': 'Van Herzeele',  'prop': 'Total Games Over 17.5', 'line': '-110', 'prob': 0.63,
     'note': 'Van Herzeele holds serve at moderate rate even in losses'},
]

MATCH2_PROPS = [
    {'player': 'Azuma Visaya',  'prop': 'Set 1 Winner',         'line': '-400', 'prob': 0.83,
     'note': 'Tang has no singles rhythm — Visaya dominates from game 1'},
    {'player': 'Azuma Visaya',  'prop': 'Straight Sets (2-0)',  'line': '-110', 'prob': 0.0,   # filled at runtime
     'note': 'Tang mentally pivots to doubles prep after dropping Set 1'},
    {'player': 'Azuma Visaya',  'prop': 'Game Handicap -4.5',   'line': '-110', 'prob': 0.0,   # filled at runtime
     'note': 'Qualifier dominance (6-2 6-0, 6-4 6-2) suggests clean shutout pace'},
    {'player': 'Sheng Tang',    'prop': 'Total Games Under 16.5','line': '-110', 'prob': 0.63,
     'note': 'Blowout risk: Tang lacks singles endurance for extended match'},
]


# ============================================================================
# TERMINAL OUTPUT
# ============================================================================

def print_match_result(r: MatchOutput, notes: str = ""):
    sep = "-" * 64
    print(f"\n{sep}")
    print(f"  {r.player_a.upper()} vs {r.player_b.upper()}")
    print(f"  {r.event}")
    print(sep)
    print(f"  Win Prob:      {r.player_a}: {r.a_win_prob:.1%}  |  {r.player_b}: {r.b_win_prob:.1%}")
    print(f"  Model Fav:     {r.model_favorite}  (strength delta: {r.strength_delta:+.1f})")
    print(f"  Market Edge:   {r.model_edge_vs_market_pct:+.1f}%  |  ML Rec: {r.recommendation_ml}")
    print(f"  Confidence:    {r.confidence_ml:.1f}%")
    if r.over_games_prob is not None:
        print(f"  Total O{r.over_games_line}: {r.over_games_prob:.1%}  — {r.recommendation_total}")
    print(f"  Straight Sets: {r.straight_sets_prob:.1%}  "
          f"[{'✅ BET' if r.straight_sets_prob >= 0.60 else '⚠️ LEAN' if r.straight_sets_prob >= 0.54 else 'PASS'}]")
    print(f"  -4.5 Handicap: {r.game_handicap_prob:.1%}  "
          f"[{'✅ BET' if r.game_handicap_prob >= 0.60 else '⚠️ LEAN' if r.game_handicap_prob >= 0.54 else 'PASS'}]")
    print(f"  Strong Bets:   {len(r.strong_bets or [])}")
    for b in (r.strong_bets or []):
        edge_txt = f"  | mkt edge +{b['edge_vs_market']:.1f}%" if isinstance(b.get("edge_vs_market"), (int, float)) else ""
        print(f"    → {b['pick']} ({b['market']}) — {b['prob']:.1f}% conf={b['confidence']:.1f}%{edge_txt}")
    if notes:
        print(f"\n  Notes: {notes[:120]}...")


def _prop_label(prob: float):
    if prob >= 0.60:
        return '✅', 'STRONG'
    if prob >= 0.55:
        return '⚠️', 'MEDIUM'
    return '❌', 'PASS'


def print_props(props: list, label: str):
    print(f"\n  {label}")
    print(f"  {'Player':<20} {'Prop':<26} {'Line':<7} {'Prob':>6}  Rec")
    print(f"  {'-'*20} {'-'*26} {'-'*7} {'-'*6}  {'-'*8}")
    for p in props:
        if p['prob'] == 0.0:
            continue
        sym, tag = _prop_label(p['prob'])
        print(f"  {p['player']:<20} {p['prop']:<26} {str(p['line']):<7} {p['prob']*100:>5.0f}%  {sym} {tag}")


# ============================================================================
# DISCORD PUSH — 3 EMBEDS
# ============================================================================

def _fmt_props_discord(props: list) -> str:
    lines = []
    for p in props:
        if p['prob'] == 0.0:
            continue
        sym, tag = _prop_label(p['prob'])
        lines.append(
            f"{sym} **{p['player']} — {p['prop']}** ({p['line']}) | {p['prob']*100:.0f}% [{tag}]"
        )
    return "\n".join(lines) if lines else "No qualified props."


def push_itf_wuning_to_discord(results: List[MatchOutput]) -> bool:
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("  [X] DISCORD_WEBHOOK_URL not set")
        return False

    r1, r2 = results[0], results[1]
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _sym(rec: str) -> str:
        if rec.startswith("BET"):  return "🟢"
        if rec.startswith("LEAN"): return "🟡"
        return "🔴"

    all_strong = [b for r in results for b in (r.strong_bets or [])]
    ok = 0

    # ── EMBED 1: BOTH MATCH MODEL ANALYSIS ─────────────────────────────
    has_bets = any(b["prob"] >= 60.0 for b in all_strong)
    col1 = 3066993 if has_bets else 16776960

    e1 = {
        "title": "🎾 ITF M15 Wuning — July 6, 2026 | Match Analysis",
        "description": "Hard court ITF Futures • Two sharp-angle matches • ATP ranking is NOT the story",
        "color": col1,
        "fields": [
            {
                "name": f"MATCH 1 — {r1.player_a} vs {r1.player_b}",
                "value": (
                    f"**Win Prob:** {r1.player_a} {r1.a_win_prob:.1%} | {r1.player_b} {r1.b_win_prob:.1%}\n"
                    f"**Model Fav:** {r1.model_favorite} | Edge vs Market: {r1.model_edge_vs_market_pct:+.1f}%\n"
                    f"{_sym(r1.recommendation_ml)} **ML:** {r1.recommendation_ml} "
                    f"(Conf: {r1.confidence_ml:.1f}%)\n"
                    f"**Sharp Context:** Van Herzeele (~1098 ATP) in brutal 2026 slump — ~25% main "
                    f"draw win rate. Boosarawongse (~1778 ATP) ranked lower but playing elite tennis: "
                    f"72% first serve in, beat Arseneault. Market correctly discards the ranking gap."
                ),
                "inline": False,
            },
            {
                "name": f"MATCH 2 — {r2.player_a} vs {r2.player_b}",
                "value": (
                    f"**Win Prob:** {r2.player_a} {r2.a_win_prob:.1%} | {r2.player_b} {r2.b_win_prob:.1%}\n"
                    f"**Model Fav:** {r2.model_favorite} | Edge vs Market: {r2.model_edge_vs_market_pct:+.1f}%\n"
                    f"{_sym(r2.recommendation_ml)} **ML:** {r2.recommendation_ml} "
                    f"(Conf: {r2.confidence_ml:.1f}%)\n"
                    f"**Sharp Context:** Tang (~1889 ATP) spends ~90% of career on doubles circuit "
                    f"(170+ doubles, rarely plays singles). Lacks match-rhythm and baseline endurance. "
                    f"Visaya (USA, 22, 8-3 singles 2026) dominated qualifiers: 6-2 6-0 and 6-4 6-2.\n"
                    f"⚠️ **AVOID Visaya ML at -450 — zero value.** Target derivative markets instead."
                ),
                "inline": False,
            },
        ],
        "timestamp": ts,
        "footer": {"text": "MultiSportPredict • ITF M15 Wuning • Hard Court Model"},
    }

    try:
        resp = requests.post(
            webhook_url, json={"embeds": [e1]},
            headers={"Content-Type": "application/json"}, timeout=15,
        )
        if resp.status_code in (200, 204):
            print("  [OK] Embed 1 (Match Analysis) pushed.")
            ok += 1
        else:
            print(f"  [X] Embed 1 failed: HTTP {resp.status_code}")
    except Exception as exc:
        print(f"  [X] Embed 1 error: {exc}")

    # ── EMBED 2: STRONG BETS TICKET ─────────────────────────────────────
    bet_lines = []
    for i, b in enumerate(all_strong, 1):
        edge_txt = f" | +{b['edge_vs_market']:.1f}% vs mkt" if isinstance(b.get("edge_vs_market"), (int, float)) else ""
        sym = "✅" if b["prob"] >= 60.0 else "⚠️"
        bet_lines.append(
            f"{i}. {sym} **{b['pick']}** ({b['market']})\n"
            f"   p={b['prob']:.1f}% | conf={b['confidence']:.1f}%{edge_txt}"
        )

    # Always include Visaya derivative plays
    ss_p  = r2.straight_sets_prob * 100
    gh_p  = r2.game_handicap_prob * 100
    ss_sym = "✅" if r2.straight_sets_prob >= 0.60 else "⚠️"
    gh_sym = "✅" if r2.game_handicap_prob >= 0.60 else "⚠️"
    idx = len(all_strong) + 1
    bet_lines.append(
        f"{idx}. {ss_sym} **Azuma Visaya — Straight Sets (2-0)**\n"
        f"   p={ss_p:.1f}% | Better value than -450 ML | Tang lacks singles conditioning"
    )
    idx += 1
    bet_lines.append(
        f"{idx}. {gh_sym} **Azuma Visaya — Game Handicap -4.5**\n"
        f"   p={gh_p:.1f}% | Exploit Tang's lack of singles match-rhythm | Qualifier dominance pattern"
    )

    e2 = {
        "title": "🎯 ITF M15 Wuning — Strong Bets Ticket",
        "description": "Qualified plays + sharp derivative value markets",
        "color": 3066993,
        "fields": [
            {
                "name": f"PLAYS ({len(bet_lines)} total)",
                "value": "\n".join(bet_lines)[:1020],
                "inline": False,
            },
            {
                "name": "⚠️ SHARP NOTE — MATCH 2 (Tang vs Visaya)",
                "value": (
                    "Sharp bettors **never lay -450 juice** on ITF Futures — variance is too high. "
                    "**Visaya Straight Sets** provides the same directional play at far better odds. "
                    "Tang's 90%+ doubles career means zero singles match-rhythm — he simply cannot "
                    "sustain baseline exchanges over 3 sets. Visaya has dismantled his last two "
                    "opponents (6-2 6-0, 6-4 6-2) and is in peak physical condition."
                ),
                "inline": False,
            },
        ],
        "timestamp": ts,
        "footer": {"text": "MultiSportPredict • ITF M15 Wuning • Strong Bets Only"},
    }

    try:
        resp = requests.post(
            webhook_url, json={"embeds": [e2]},
            headers={"Content-Type": "application/json"}, timeout=15,
        )
        if resp.status_code in (200, 204):
            print("  [OK] Embed 2 (Strong Bets) pushed.")
            ok += 1
        else:
            print(f"  [X] Embed 2 failed: HTTP {resp.status_code}")
    except Exception as exc:
        print(f"  [X] Embed 2 error: {exc}")

    # ── EMBED 3: PROPS & DERIVATIVES ────────────────────────────────────
    # Fill runtime-computed probs for match 2 props
    m2_props = []
    for p in MATCH2_PROPS:
        p2 = dict(p)
        if p2['player'] == 'Azuma Visaya' and p2['prop'] == 'Straight Sets (2-0)':
            p2['prob'] = r2.straight_sets_prob
        elif p2['player'] == 'Azuma Visaya' and p2['prop'] == 'Game Handicap -4.5':
            p2['prob'] = r2.game_handicap_prob
        m2_props.append(p2)

    e3 = {
        "title": "📋 Props & Derivatives — ITF M15 Wuning",
        "description": "Set betting, game handicap, service props | ✅ Strong ≥60% | ⚠️ Medium 55–59% | ❌ Pass <55%",
        "color": 10181046,  # Purple
        "fields": [
            {
                "name": "🎾 MATCH 1 — Van Herzeele vs Boosarawongse",
                "value": _fmt_props_discord(MATCH1_PROPS),
                "inline": False,
            },
            {
                "name": "🎾 MATCH 2 — Sheng Tang vs Azuma Visaya (Derivative Focus)",
                "value": _fmt_props_discord(m2_props),
                "inline": False,
            },
            {
                "name": "📊 PLAYER CONTEXT",
                "value": (
                    "**Van Herzeele (BEL, ~1098):** 2026 main draw win rate ~25% — "
                    "ranking does NOT reflect current form. Relies on weak qualifier opponents.\n"
                    "**Boosarawongse (THA, 20, ~1778):** 72% first serve in. "
                    "Consistent baseline on hard courts. Sharp momentum in this event.\n"
                    "**Tang (CHN, 26, ~1889):** 170+ ITF doubles matches with Zijiang Yang. "
                    "Singles is a secondary concern — mental pivot risk mid-match.\n"
                    "**Visaya (USA, 22, ~1495):** 8-3 singles 2026. Peak form. "
                    "Fully acclimatized to hard courts."
                ),
                "inline": False,
            },
        ],
        "timestamp": ts,
        "footer": {"text": "MultiSportPredict • Player Props & Derivatives • ITF M15 Wuning"},
    }

    try:
        resp = requests.post(
            webhook_url, json={"embeds": [e3]},
            headers={"Content-Type": "application/json"}, timeout=15,
        )
        if resp.status_code in (200, 204):
            print("  [OK] Embed 3 (Props & Derivatives) pushed.")
            ok += 1
        else:
            print(f"  [X] Embed 3 failed: HTTP {resp.status_code}")
    except Exception as exc:
        print(f"  [X] Embed 3 error: {exc}")

    print(f"\n  Discord: {ok}/3 embeds sent.")
    return ok == 3


# ============================================================================
# MAIN
# ============================================================================

def main():
    sep = "=" * 72
    print(f"\n{sep}")
    print("  ITF M15 WUNING — TENNIS ANALYSIS")
    print("  Match 1: Van Herzeele vs Boosarawongse")
    print("  Match 2: Sheng Tang vs Azuma Visaya")
    print("  July 6, 2026 | Hard Court | ITF Futures")
    print(f"{sep}\n")

    results = [analyze_match(m) for m in MATCHES]

    for i, (r, m) in enumerate(zip(results, MATCHES), 1):
        print_match_result(r, m.notes)

    print_props(MATCH1_PROPS, "MATCH 1 PROPS — Van Herzeele vs Boosarawongse")

    # Fill runtime probs for match 2 display
    m2_display = []
    for p in MATCH2_PROPS:
        p2 = dict(p)
        if p2['player'] == 'Azuma Visaya' and p2['prop'] == 'Straight Sets (2-0)':
            p2['prob'] = results[1].straight_sets_prob
        elif p2['player'] == 'Azuma Visaya' and p2['prop'] == 'Game Handicap -4.5':
            p2['prob'] = results[1].game_handicap_prob
        m2_display.append(p2)

    print_props(m2_display, "MATCH 2 PROPS — Sheng Tang vs Azuma Visaya")

    all_strong = [b for r in results for b in (r.strong_bets or [])]
    print(f"\n{'='*72}")
    print(f"  TOTAL STRONG BETS QUALIFIED: {len(all_strong)}")
    for b in all_strong:
        edge_txt = f"  +{b['edge_vs_market']:.1f}% vs market" if isinstance(b.get("edge_vs_market"), (int, float)) else ""
        print(f"  → {b['pick']} ({b['market']}) — {b['prob']:.1f}%{edge_txt}")
    print(f"  + Visaya Straight Sets: {results[1].straight_sets_prob:.1%}  (derivative — avoid -450 ML)")
    print(f"  + Visaya -4.5 Handicap: {results[1].game_handicap_prob:.1%}  (derivative)")

    print(f"\n--- DISCORD ---")
    push_itf_wuning_to_discord(results)

    print(f"\n{sep}")
    print("  Analysis Complete!")
    print(f"{sep}\n")


if __name__ == '__main__':
    main()
