#!/usr/bin/env python3
"""
FIBA World Cup 2027 Americas Qualifier
Mexico vs USA — July 6, 2026
Venue: Gimnasio Marcelino Gonzalez, Zacatecas City (8,010 ft / 2,440m altitude)

SHARP ANGLE: Mexico ATS in 1Q and 1H
- Altitude: 8,010 ft — nearly 3,000 ft higher than Denver
- USA fatigue: came back from -13 vs Dominican Republic on July 3 (max physical exertion)
- Mexico rest advantage: coasted vs Nicaragua, rested starters, fully acclimatized
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

from fiba_interactive_runner import analyze_fiba_game, print_results

# ============================================================================
# TEAM DATA
# ============================================================================

# Mexico — HOME | Zacatecas, fully acclimatized, rested
MEXICO_DATA = {
    'ortg': 108.0,          # Solid FIBA Americas offense
    'drtg': 106.0,          # Competent home defense
    'baseline_net': 2.0,    # Above average at FIBA Americas level
    'recent_net': 5.0,      # Boosted: coasted vs Nicaragua July 3, rested starters
    'pace': 69.5,            # Altitude naturally suppresses pace
    'rest_days': 3,
    'travel_km': 0,          # Playing at home
    'back_to_back': False,
    'three_in_six': False,
    'split_edge': 6.5,       # Home court + 8,010 ft altitude + crowd energy
    'rotation_depth': 9,
    'injury_status': 'green',
    'coach_stability': 'green',
    'motivation': 'green',
}

# USA — AWAY | Non-NBA overseas/G-League squad, unacclimatized, fatigued
USA_DATA = {
    'ortg': 116.5,           # Strong non-NBA talent
    'drtg': 98.5,            # Elite defensive efficiency
    'baseline_net': 18.0,    # Dominates FIBA Americas at full strength
    'recent_net': 10.0,      # Reduced: grueling comeback from -13 vs Dominican Rep July 3
    'pace': 73.5,             # Faster pace team, altitude will suppress this
    'rest_days': 3,
    'travel_km': 1900,        # Travel to Zacatecas, zero altitude acclimatization
    'back_to_back': False,
    'three_in_six': False,
    'split_edge': -6.0,       # Road team + altitude penalty (unacclimatized)
    'rotation_depth': 10,
    'injury_status': 'yellow',  # Physical + mental fatigue from comeback game
    'coach_stability': 'green',
    'motivation': 'green',
}

# Convention: negative spread = away team favored (USA -22 → spread = -22 from home perspective)
MARKET_DATA = {
    'spread': -22.0,
    'open_line': -20.0,
    'current_line': -22.0,
    'total': 147.0,
}

VENUE = 'Gimnasio Marcelino Gonzalez, Zacatecas City (8,010 ft / 2,440m)'
DATE = '2026-07-06'
LEAGUE = 'FIBA World Cup 2027 Americas Qualifier'

# ============================================================================
# PLAYER PROPS
# ============================================================================

USA_PROPS = [
    {'player': 'Mike James',    'prop': 'Points',   'line': 14.5, 'pick': 'Over', 'prob': 0.71,
     'note': 'EuroLeague star, 15pts/12ast debut vs DR — primary USA engine'},
    {'player': 'Mike James',    'prop': 'Assists',  'line': 8.5,  'pick': 'Over', 'prob': 0.68,
     'note': '12 assists in debut — elite playmaker at this level'},
    {'player': 'Mike James',    'prop': '3PT Made', 'line': 2.5,  'pick': 'Over', 'prob': 0.64,
     'note': 'High-volume EuroLeague shooter, active perimeter game'},
    {'player': 'Jay Huff',      'prop': 'Rebounds', 'line': 6.5,  'pick': 'Over', 'prob': 0.66,
     'note': 'Primary rim anchor — key matchup vs Yahir Bonilla in the paint'},
    {'player': 'Jay Huff',      'prop': 'Blocks',   'line': 1.5,  'pick': 'Over', 'prob': 0.65,
     'note': 'Rim protection critical vs Bonilla (1.4 blk/g for Mexico)'},
    {'player': 'Jay Huff',      'prop': 'Points',   'line': 8.5,  'pick': 'Over', 'prob': 0.62,
     'note': 'Active post scorer when not burdened defensively'},
]

MEXICO_PROPS = [
    {'player': 'Pako Cruz',     'prop': 'Points',   'line': 17.5, 'pick': 'Over', 'prob': 0.65,
     'note': '18.8 pts/game avg — primary scorer energized on home court'},
    {'player': 'Pako Cruz',     'prop': 'Assists',  'line': 5.5,  'pick': 'Over', 'prob': 0.68,
     'note': '6.2 ast/game — veteran guard, won\'t be rattled by USA pressure'},
    {'player': 'Pako Cruz',     'prop': '3PT Made', 'line': 2.5,  'pick': 'Over', 'prob': 0.62,
     'note': 'Volume perimeter shooter elevated by home crowd confidence'},
    {'player': 'Yahir Bonilla', 'prop': 'Points',   'line': 14.5, 'pick': 'Over', 'prob': 0.67,
     'note': '16.0 pts/game — emerging big man, energized by home altitude crowd'},
    {'player': 'Yahir Bonilla', 'prop': 'Rebounds', 'line': 7.0,  'pick': 'Over', 'prob': 0.66,
     'note': '7.4 reb/game avg — will challenge Jay Huff in the paint'},
    {'player': 'Yahir Bonilla', 'prop': 'Blocks',   'line': 1.0,  'pick': 'Over', 'prob': 0.65,
     'note': '1.4 blk/game — active shot-blocker at home altitude'},
    {'player': 'Paul Stoll',    'prop': 'Assists',  'line': 4.5,  'pick': 'Over', 'prob': 0.64,
     'note': '5.0 ast/game — veteran FIBA floor general'},
    {'player': 'Paul Stoll',    'prop': 'Steals',   'line': 1.5,  'pick': 'Over', 'prob': 0.62,
     'note': '1.8 stl/game — disruptive defensive hands'},
]

H2H_RECORDS = [
    ('Mar 1, 2026',  'WCQ 2027',  'USA 123 – MEX 88'),
    ('Sep 2, 2022',  'AmeriCup',  'MEX 73 – USA 67'),
    ('Feb 27, 2022', 'WCQ 2023',  'USA 89 – MEX 67'),
    ('Nov 29, 2021', 'WCQ 2023',  'MEX 97 – USA 88'),
]


# ============================================================================
# DISCORD PUSH — 3 EMBEDS
# ============================================================================

def _bet_emoji(decision: str) -> str:
    return {
        'BET':  ':green_circle:',
        'LEAN': ':yellow_circle:',
    }.get(decision, ':red_circle:')


def _prop_label(prob: float) -> tuple:
    if prob >= 0.60:
        return '✅', 'STRONG'
    if prob >= 0.55:
        return '⚠️', 'MEDIUM'
    return '❌', 'PASS'


def _fmt_props(props: list) -> str:
    lines = []
    for p in props:
        sym, tag = _prop_label(p['prob'])
        pct = p['prob'] * 100
        lines.append(
            f"{sym} **{p['player']} — {p['prop']} {p['pick']} {p['line']}** "
            f"| {pct:.0f}% [{tag}]"
        )
    return "\n".join(lines)


def push_usa_mexico_to_discord(results: dict) -> bool:
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("  [X] DISCORD_WEBHOOK_URL not set")
        return False

    fg   = results['fg']
    q1   = results['q1']
    h1   = results['h1']
    bets = results['bets']
    ts   = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    ok   = 0

    # ── EMBED 1: MODEL PROJECTION + BET DECISIONS ──────────────────────
    has_bet  = any(b['decision'] == 'BET'  for b in bets.values())
    has_lean = any(b['decision'] == 'LEAN' for b in bets.values())
    col1 = 3066993 if has_bet else (16776960 if has_lean else 15158332)

    bet_lines = "\n".join(
        f"{_bet_emoji(b['decision'])} **{k.upper().replace('_', ' ')}** — {b['decision']} "
        f"| Proj: {b['projected']:+.1f} | Mkt: {b['market']:+.1f} | Edge: {b['edge']:+.2f}"
        for k, b in bets.items()
    )

    e1 = {
        "title": "🏀 FIBA Americas: MEXICO vs USA | July 6, 2026",
        "description": (
            "**Gimnasio Marcelino Gonzalez, Zacatecas City (8,010 ft / 2,440m altitude)**\n"
            "FIBA World Cup 2027 Americas Qualifier\n"
            "⚠️ *Sharp angle: Mexico ATS — 1Q & 1H (altitude + USA fatigue)*"
        ),
        "color": col1,
        "fields": [
            {
                "name": "FULL GAME",
                "value": (
                    f"**Score:** Mexico {fg['projected_home']:.1f} – USA {fg['projected_away']:.1f}\n"
                    f"**Spread:** Model {fg['projected_spread']:+.1f} | Market: USA -22 (Away Fav)\n"
                    f"**Total:** {fg['projected_total']:.1f} (Market: 147.0)\n"
                    f"**Win Prob:** USA {fg['away_win_prob']:.1%} | Mexico {fg['home_win_prob']:.1%}"
                ),
                "inline": False,
            },
            {
                "name": "1ST HALF (1H) — KEY SHARP MARKET",
                "value": (
                    f"**Score:** Mexico {h1['projected_home']:.1f} – USA {h1['projected_away']:.1f}\n"
                    f"**Spread:** Model {h1['projected_spread']:+.1f} | Market: USA ~-11\n"
                    f"**Total:** {h1['projected_total']:.1f}\n"
                    f"{_bet_emoji(bets['h1_spread']['decision'])} **Mexico +11 1H ATS: "
                    f"{bets['h1_spread']['decision']}** | Edge: {bets['h1_spread']['edge']:+.2f}"
                ),
                "inline": True,
            },
            {
                "name": "1ST QUARTER (1Q) — KEY SHARP MARKET",
                "value": (
                    f"**Score:** Mexico {q1['projected_home']:.1f} – USA {q1['projected_away']:.1f}\n"
                    f"**Spread:** Model {q1['projected_spread']:+.1f} | Market: USA ~-5.5\n"
                    f"**Total:** {q1['projected_total']:.1f}\n"
                    f"{_bet_emoji(bets['q1_spread']['decision'])} **Mexico +5.5 1Q ATS: "
                    f"{bets['q1_spread']['decision']}** | Edge: {bets['q1_spread']['edge']:+.2f}"
                ),
                "inline": True,
            },
            {
                "name": "ALL BET DECISIONS",
                "value": bet_lines,
                "inline": False,
            },
        ],
        "timestamp": ts,
        "footer": {"text": "MultiSportPredict • FIBA Americas • 1Q | 1H | FG"},
    }

    try:
        resp = requests.post(
            webhook_url, json={"embeds": [e1]},
            headers={"Content-Type": "application/json"}, timeout=15,
        )
        if resp.status_code in (200, 204):
            print("  [OK] Embed 1 (Model Projection) pushed.")
            ok += 1
        else:
            print(f"  [X] Embed 1 failed: HTTP {resp.status_code}")
    except Exception as exc:
        print(f"  [X] Embed 1 error: {exc}")

    # ── EMBED 2: SHARP INTEL (ALTITUDE + FATIGUE + H2H) ────────────────
    h2h_txt = "\n".join(f"• {d} ({comp}): {res}" for d, comp, res in H2H_RECORDS)
    e2 = {
        "title": "⛰️ Sharp Intel: Altitude + Fatigue Analysis",
        "description": "Why Mexico covers early — factors only sharp bettors are pricing in",
        "color": 15844367,  # Orange
        "fields": [
            {
                "name": "ALTITUDE EDGE — ZACATECAS CITY (8,010 ft / 2,440m)",
                "value": (
                    "Zacatecas sits **nearly 3,000 ft above Denver**. The thin air significantly "
                    "impacts unacclimatized road teams — heavier legs, reduced VO2 max, and slower "
                    "early-game pace. Mexico is fully acclimatized, USA has had zero adjustment time."
                ),
                "inline": False,
            },
            {
                "name": "😤 USA — FATIGUE REPORT",
                "value": (
                    "Fell behind **-13 vs Dominican Republic (July 3)** — required maximum physical "
                    "and mental effort to stage a dramatic 1-point comeback. Physical drain + mental "
                    "exhaustion + unacclimatized altitude travel = textbook slow-start scenario."
                ),
                "inline": True,
            },
            {
                "name": "✅ MEXICO — REST ADVANTAGE",
                "value": (
                    "**Routed Nicaragua (July 3)**, took control in Q2 and coasted. Starters rested "
                    "in Q4. Fully acclimatized. Home crowd provides genuine energy boost at altitude "
                    "— visiting teams historically struggle in early frames at Zacatecas."
                ),
                "inline": True,
            },
            {
                "name": "🔑 THE SHARP PLAY",
                "value": (
                    "**Mexico ATS in 1Q and 1H** — textbook slow-start scenario for the heavily "
                    "favored road team. USA depth and talent will likely assert themselves in the 2H. "
                    "This is NOT a Mexico outright play — this is a situational 1Q/1H spread edge.\n\n"
                    "Avoid the USA FG spread (-22): too much number for an altitude road game. "
                    "The value is in **early-frame lines where altitude impact peaks**."
                ),
                "inline": False,
            },
            {
                "name": "🏀 KEY PERSONNEL MATCHUPS",
                "value": (
                    "**USA — Mike James (PG):** EuroLeague star, 15pts/12ast debut. Primary engine.\n"
                    "**USA — Jay Huff (C):** Rim protector — must contain Yahir Bonilla inside.\n"
                    "**Mexico — Pako Cruz (G):** 18.8pts/6.2ast avg. Veteran won't be rattled.\n"
                    "**Mexico — Paul Stoll (G):** 1.8stl/5.0ast. Disruptive defensive hands.\n"
                    "**Mexico — Yahir Bonilla (F/C):** 16.0pts/7.4reb/1.4blk. Emerging big at home."
                ),
                "inline": False,
            },
            {
                "name": "📊 HEAD-TO-HEAD",
                "value": h2h_txt + "\n*Mexico 2 wins in last 4 H2H vs non-NBA USA rosters*",
                "inline": False,
            },
        ],
        "timestamp": ts,
        "footer": {"text": "MultiSportPredict • Sharp Angle Analysis • FIBA Americas"},
    }

    try:
        resp = requests.post(
            webhook_url, json={"embeds": [e2]},
            headers={"Content-Type": "application/json"}, timeout=15,
        )
        if resp.status_code in (200, 204):
            print("  [OK] Embed 2 (Sharp Intel) pushed.")
            ok += 1
        else:
            print(f"  [X] Embed 2 failed: HTTP {resp.status_code}")
    except Exception as exc:
        print(f"  [X] Embed 2 error: {exc}")

    # ── EMBED 3: PLAYER PROPS ──────────────────────────────────────────
    e3 = {
        "title": "📋 Player Props — Mexico vs USA (FIBA Americas)",
        "description": "Model-estimated props | ✅ Strong ≥60% | ⚠️ Medium 55–59% | ❌ Pass <55%",
        "color": 10181046,  # Purple
        "fields": [
            {
                "name": "🇺🇸 USA PLAYER PROPS — Mike James & Jay Huff",
                "value": _fmt_props(USA_PROPS),
                "inline": False,
            },
            {
                "name": "🇲🇽 MEXICO PLAYER PROPS — Cruz / Bonilla / Stoll",
                "value": _fmt_props(MEXICO_PROPS),
                "inline": False,
            },
        ],
        "timestamp": ts,
        "footer": {"text": "MultiSportPredict • Player Props • FIBA Americas Qualifier"},
    }

    try:
        resp = requests.post(
            webhook_url, json={"embeds": [e3]},
            headers={"Content-Type": "application/json"}, timeout=15,
        )
        if resp.status_code in (200, 204):
            print("  [OK] Embed 3 (Player Props) pushed.")
            ok += 1
        else:
            print(f"  [X] Embed 3 failed: HTTP {resp.status_code}")
    except Exception as exc:
        print(f"  [X] Embed 3 error: {exc}")

    print(f"\n  Discord: {ok}/3 embeds sent.")
    return ok == 3


# ============================================================================
# TERMINAL OUTPUT HELPERS
# ============================================================================

def print_player_props(props: list, team: str):
    print(f"\n  {team} PLAYER PROPS")
    print(f"  {'Player':<18} {'Prop':<12} {'Pick':<6} {'Line':<6} {'Prob':>6}  {'Rec'}")
    print(f"  {'-'*18} {'-'*12} {'-'*6} {'-'*6} {'-'*6}  {'-'*8}")
    for p in props:
        sym, tag = _prop_label(p['prob'])
        print(
            f"  {p['player']:<18} {p['prop']:<12} {p['pick']:<6} {str(p['line']):<6} "
            f"{p['prob']*100:>5.0f}%  {sym} {tag}"
        )


# ============================================================================
# MAIN
# ============================================================================

def main():
    sep = "=" * 72
    print(f"\n{sep}")
    print("  FIBA AMERICAS QUALIFIER — MEXICO vs USA")
    print("  July 6, 2026 | Zacatecas City (8,010 ft / 2,440m altitude)")
    print("  SHARP ANGLE: Mexico ATS in 1Q and 1H")
    print(f"{sep}\n")

    print("  Analyzing...")
    results = analyze_fiba_game(
        'Mexico', 'USA',
        MEXICO_DATA, USA_DATA, MARKET_DATA,
        VENUE, DATE, LEAGUE,
    )

    print_results('Mexico', 'USA', results)
    print_player_props(USA_PROPS, 'USA')
    print_player_props(MEXICO_PROPS, 'MEXICO')

    out_dir = Path('output/fiba')
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / 'mexico_vs_usa_july6_2026.json'
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n  [i] Results saved to: {out_path}")

    print(f"\n--- DISCORD ---")
    push_usa_mexico_to_discord(results)

    print(f"\n{sep}")
    print("  Analysis Complete!")
    print(f"{sep}\n")


if __name__ == '__main__':
    main()
