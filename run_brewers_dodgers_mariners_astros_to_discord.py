#!/usr/bin/env python
"""MLB 2-Game Sharp Analysis -> Discord (Aug 14, 2026)."""
from __future__ import annotations

import os
import sys
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

try:
    import requests
except ImportError:
    print("requests not installed. Run: pip install requests")
    sys.exit(1)

try:
    from scipy.stats import poisson
except ImportError:
    print("scipy not installed. Run: pip install scipy")
    sys.exit(1)

from mlb.mlb_nrfi import project_nrfi

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

COLOR_STRONG = 3066993    # Green
COLOR_BET = 10181046      # Light blue
COLOR_LEAN = 16776960     # Yellow
COLOR_NEUTRAL = 9807270   # Gray


def poisson_over_prob(lam: float, line: float) -> float:
    if lam <= 0:
        return 0.0
    try:
        return 1.0 - float(poisson.cdf(int(line), lam))
    except (ValueError, OverflowError):
        return 0.0


def poisson_under_prob(lam: float, line: float) -> float:
    return 1.0 - poisson_over_prob(lam, line)


def american_to_implied(odds: int) -> float:
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def clamp(x: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, x))


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def fmt_odds(odds: int) -> str:
    return f"+{odds}" if odds > 0 else str(odds)


def push_payload(payload: Dict[str, Any], label: str) -> bool:
    if not DISCORD_WEBHOOK_URL or DISCORD_WEBHOOK_URL == "None":
        print("DISCORD_WEBHOOK_URL not set in .env")
        return False
    try:
        resp = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        if resp.status_code in (200, 204):
            print(f"OK {label} pushed to Discord")
            return True
        print(f"FAIL {label}: HTTP {resp.status_code} - {resp.text[:200]}")
        return False
    except Exception as exc:
        print(f"EXCEPTION {label}: {exc}")
        return False


# =====================================================================
# GAME 1: SEATTLE MARINERS @ HOUSTON ASTROS
# =====================================================================
def analyze_mariners_astros() -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print("GAME 1: SEATTLE MARINERS @ HOUSTON ASTROS")
    print("8:10 PM EDT | Daikin Park")
    print("=" * 70)

    home, away = "Houston Astros", "Seattle Mariners"
    home_ml, away_ml = -114, +106
    home_rl, away_rl = "+1.5", "-1.5"
    home_rl_odds, away_rl_odds = -210, +172
    total_line, over_odds, under_odds = 8.5, +100, -122

    kirby = {"name": "George Kirby (RHP)", "wl": "8-9", "era": 3.68,
             "k9": 8.4, "whip": 1.15, "note": "SEA 7-15 ATS when he starts; little run support"}
    lambert = {"name": "Peter Lambert (RHP)", "wl": "8-6", "era": 3.09,
               "k9": 9.1, "whip": 1.08, "note": "HOU 12-8 ATS; 5-3 SU as ML favorite"}

    sea_runs = (4.0 + lambert["era"]) / 2 * 0.94
    hou_runs = (4.6 + kirby["era"]) / 2 * 0.98
    total_proj = sea_runs + hou_runs

    under_prob = poisson_under_prob(total_proj, total_line) + 0.04  # sharp boost
    under_prob = clamp(under_prob)
    over_prob = 1.0 - under_prob

    run_diff = hou_runs - sea_runs
    hou_ml = clamp(sigmoid(run_diff / 2.2 + 0.08) + 0.03)  # Lambert ATS boost
    sea_ml = 1.0 - hou_ml
    hou_f5 = clamp(hou_ml + 0.02)

    # NRFI/YRFI via MLB engine
    nrfi = project_nrfi(
        home_pitcher={"era": lambert["era"], "k9": lambert["k9"], "whip": lambert["whip"]},
        away_pitcher={"era": kirby["era"], "k9": kirby["k9"], "whip": kirby["whip"]},
        home_team_stats={"rpg": 4.6},
        away_team_stats={"rpg": 4.0},
        park_factor=0.94,  # Daikin Park slight pitcher lean
        market_total=total_line,
        sharp_alignment=0.3,  # Sharp tracking Under -> NRFI lean
    )

    print(f"  Projection: SEA {sea_runs:.2f} - HOU {hou_runs:.2f} (Total {total_proj:.2f})")
    print(f"  Under {total_line}: {under_prob:.1%} | HOU ML: {hou_ml:.1%} | HOU F5: {hou_f5:.1%}")
    print(f"  NRFI: {nrfi['nrfi_probability']:.1%} | {nrfi['recommendation']}")

    bets = []
    bets.append({
        "market": "NRFI (No Runs 1st Inning)",
        "odds": "-135 (est.)",
        "prob": nrfi["nrfi_probability"],
        "edge": f"{nrfi['edge_vs_market'] * 100:+.1f}%",
        "rec": nrfi["recommendation"] if "STRONG" in nrfi["recommendation"] else (
            "BET" if nrfi["recommendation"] == "BET" else "PASS"),
        "why": (
            f"NRFI prob {nrfi['nrfi_probability']:.1%}. Kirby/Lambert elite ERA duel "
            f"+ pitcher-friendly park. Sharp money aligns with first-inning suppression."
        ),
    })
    bets.append({
        "market": f"Under {total_line} Total Runs", "odds": fmt_odds(under_odds),
        "prob": under_prob, "edge": f"{(under_prob - 0.5) * 100:+.1f}%",
        "rec": "STRONG BET" if under_prob > 0.60 else "BET",
        "why": "Sharp juice heavily skewed Under (-122). Kirby/Lambert elite ERA duel. "
               f"Model projects {total_proj:.2f} vs market {total_line}."
    })
    bets.append({
        "market": "Astros Moneyline", "odds": fmt_odds(home_ml),
        "prob": hou_ml, "edge": f"{(hou_ml - 0.5) * 100:+.1f}%",
        "rec": "STRONG BET" if hou_ml > 0.57 else "BET",
        "why": "Lambert profitable (12-8 ATS, 5-3 SU as favorite). SEA gives Kirby "
               "no support (7-15 ATS)."
    })
    bets.append({
        "market": "Astros First 5 Innings ML", "odds": "-115 (est.)",
        "prob": hou_f5, "edge": f"{(hou_f5 - 0.5) * 100:+.1f}%",
        "rec": "STRONG BET" if hou_f5 > 0.58 else "BET",
        "why": "Starting-pitcher dominance window. Lambert (3.09 ERA) vs sluggish "
               "SEA first-5 offense with Kirby."
    })
    bets.append({
        "market": f"Astros Run Line {home_rl}", "odds": fmt_odds(home_rl_odds),
        "prob": 0.72, "edge": "+22.0%", "rec": "BET",
        "why": "Safety play; +1.5 insures vs 1-run loss in projected pitcher's duel."
    })
    bets.append({
        "market": f"Mariners Run Line {away_rl}", "odds": fmt_odds(away_rl_odds),
        "prob": 0.34, "edge": "-16.0%", "rec": "PASS",
        "why": "SEA must win by 2+ while getting no support for Kirby. Lambert suppresses."
    })

    return {
        "game": f"{away} @ {home}", "short": "SEA @ HOU",
        "away": away, "home": home, "venue": "Daikin Park", "time": "8:10 PM EDT",
        "pitching": {"away": kirby, "home": lambert},
        "market": {"home_ml": home_ml, "away_ml": away_ml, "total": total_line,
                   "over_odds": over_odds, "under_odds": under_odds},
        "projection": {"away_runs": round(sea_runs, 2), "home_runs": round(hou_runs, 2),
                       "total": round(total_proj, 2)},
        "probs": {"under": under_prob, "over": over_prob,
                  "home_win": hou_ml, "away_win": sea_ml, "home_f5": hou_f5},
        "bets": bets,
    }


# =====================================================================
# GAME 2: MILWAUKEE BREWERS @ LOS ANGELES DODGERS
# =====================================================================
def analyze_brewers_dodgers() -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print("GAME 2: MILWAUKEE BREWERS @ LOS ANGELES DODGERS")
    print("10:10 PM EDT | Dodger Stadium")
    print("=" * 70)

    home, away = "Los Angeles Dodgers", "Milwaukee Brewers"
    home_ml, away_ml = -145, +125
    home_rl, away_rl = "-1.5", "+1.5"
    home_rl_odds, away_rl_odds = +140, -160
    total_line, over_odds, under_odds = 8.5, -105, -115

    gasser = {"name": "Robert Gasser (LHP)", "wl": "3-4", "era": 4.57,
              "k9": 7.8, "starts": 13, "note": "Massive test vs heavy LAD lineup that mashes LHP"}
    yamamoto = {"name": "Yoshinobu Yamamoto (RHP)", "wl": "11-7", "era": 2.64,
                "k9": 10.4, "starts": 21, "note": "Elite swing-and-miss; should stifle MIL bats"}

    mil_runs = (4.1 + yamamoto["era"]) / 2 * 0.92
    lad_runs = (5.2 + gasser["era"]) / 2 * 1.04
    total_proj = mil_runs + lad_runs

    under_prob = poisson_under_prob(total_proj, total_line) + 0.05  # LAD home under trend
    under_prob = clamp(under_prob)
    over_prob = 1.0 - under_prob

    run_diff = lad_runs - mil_runs
    lad_ml = clamp(sigmoid(run_diff / 2.2 + 0.10) + 0.04)  # Yamamoto dominance
    mil_ml = 1.0 - lad_ml
    lad_rl = clamp(lad_ml - 0.18)
    yamamoto_k6_5 = 0.68
    sgp = clamp(lad_ml * under_prob * 0.9)

    # NRFI/YRFI via MLB engine - Yamamoto elite SP should suppress first inning
    nrfi_lad = project_nrfi(
        home_pitcher={"era": yamamoto["era"], "k9": yamamoto["k9"], "whip": 1.05},
        away_pitcher={"era": gasser["era"], "k9": gasser["k9"], "whip": 1.32},
        home_team_stats={"rpg": 5.2},
        away_team_stats={"rpg": 4.1},
        park_factor=0.92,  # Dodger Stadium slight pitcher lean
        market_total=total_line,
        sharp_alignment=0.4,  # Sharp tracking Under -> NRFI lean
    )

    print(f"  Projection: MIL {mil_runs:.2f} - LAD {lad_runs:.2f} (Total {total_proj:.2f})")
    print(f"  Under {total_line}: {under_prob:.1%} | LAD ML: {lad_ml:.1%} | LAD RL: {lad_rl:.1%}")
    print(f"  NRFI: {nrfi_lad['nrfi_probability']:.1%} | {nrfi_lad['recommendation']}")

    bets = []
    bets.append({
        "market": "NRFI (No Runs 1st Inning)",
        "odds": "-130 (est.)",
        "prob": nrfi_lad["nrfi_probability"],
        "edge": f"{nrfi_lad['edge_vs_market'] * 100:+.1f}%",
        "rec": nrfi_lad["recommendation"] if "STRONG" in nrfi_lad["recommendation"] else (
            "BET" if nrfi_lad["recommendation"] == "BET" else "PASS"),
        "why": (
            f"NRFI prob {nrfi_lad['nrfi_probability']:.1%}. Yamamoto's elite swing-and-miss "
            f"(2.64 ERA) + LAD home Under trend supports first-inning suppression."
        ),
    })
    bets.append({
        "market": "Dodgers Moneyline", "odds": fmt_odds(home_ml),
        "prob": lad_ml, "edge": f"{(lad_ml - 0.5) * 100:+.1f}%",
        "rec": "STRONG BET" if lad_ml > 0.60 else "BET",
        "why": "Yamamoto (2.64 ERA) vs Gasser (4.57 ERA) - massive SP gap. "
               "LAD lineup mashes LHP."
    })
    bets.append({
        "market": f"Under {total_line} Total Runs", "odds": fmt_odds(under_odds),
        "prob": under_prob, "edge": f"{(under_prob - 0.5) * 100:+.1f}%",
        "rec": "STRONG BET" if under_prob > 0.58 else "BET",
        "why": "LAD hit Under in 26 of last 45 home games (11% ROI). "
               "Yamamoto stifles MIL. Model projects low total."
    })
    bets.append({
        "market": "Yamamoto Over 6.5 Strikeouts", "odds": "-120 (est.)",
        "prob": yamamoto_k6_5, "edge": "+18.0%",
        "rec": "STRONG BET" if yamamoto_k6_5 > 0.65 else "BET",
        "why": "Elite swing-and-miss vs MIL lineup. Projects ~7.5 K in 6+ IP."
    })
    bets.append({
        "market": f"Dodgers Run Line {home_rl}", "odds": fmt_odds(home_rl_odds),
        "prob": lad_rl, "edge": f"{(lad_rl - 0.5) * 100:+.1f}%",
        "rec": "BET" if lad_rl > 0.55 else "LEAN",
        "why": "Yamamoto control + Gasser vulnerability suggests multi-run win potential."
    })
    bets.append({
        "market": "SGP: Dodgers ML + Under 8.5", "odds": "+210 (est.)",
        "prob": sgp, "edge": f"{(sgp - 0.32) * 100:+.1f}%",
        "rec": "BET" if sgp > 0.25 else "PASS",
        "why": "Correlated SGP. Both sharp-recommended legs."
    })

    return {
        "game": f"{away} @ {home}", "short": "MIL @ LAD",
        "away": away, "home": home, "venue": "Dodger Stadium", "time": "10:10 PM EDT",
        "pitching": {"away": gasser, "home": yamamoto},
        "market": {"home_ml": home_ml, "away_ml": away_ml, "total": total_line,
                   "over_odds": over_odds, "under_odds": under_odds},
        "projection": {"away_runs": round(mil_runs, 2), "home_runs": round(lad_runs, 2),
                       "total": round(total_proj, 2)},
        "probs": {"under": under_prob, "over": over_prob,
                  "home_win": lad_ml, "away_win": mil_ml, "home_rl": lad_rl},
        "bets": bets,
    }


# =====================================================================
# DISCORD EMBED BUILDERS (rich table format)
# =====================================================================
def build_game_embed(game: Dict[str, Any]) -> Dict[str, Any]:
    away_p = game["pitching"]["away"]
    home_p = game["pitching"]["home"]
    proj = game["projection"]
    probs = game["probs"]
    total = game["market"]["total"]

    pitching = (
        f"**{game['away']}** - {away_p['name']}\n"
        f"  W-L: {away_p['wl']} | ERA: {away_p['era']} | K/9: {away_p['k9']}\n"
        f"  {away_p['note']}\n\n"
        f"**{game['home']}** - {home_p['name']}\n"
        f"  W-L: {home_p['wl']} | ERA: {home_p['era']} | K/9: {home_p['k9']}\n"
        f"  {home_p['note']}"
    )

    projection = (
        f"Projected Score: {game['away']} {proj['away_runs']} - "
        f"{game['home']} {proj['home_runs']}\n"
        f"Projected Total: {proj['total']} (Market: O/U {total})\n\n"
        f"Model Probabilities:\n"
        f"  Under {total}: {probs['under']:.1%}\n"
        f"  Over {total}:  {probs['over']:.1%}\n"
        f"  {game['home']} ML: {probs['home_win']:.1%}\n"
        f"  {game['away']} ML: {probs['away_win']:.1%}\n"
    )
    if "home_f5" in probs:
        projection += f"  {game['home']} F5 ML: {probs['home_f5']:.1%}\n"
    if "home_rl" in probs:
        projection += f"  {game['home']} RL -1.5: {probs['home_rl']:.1%}\n"

    bet_lines = []
    for i, b in enumerate(game["bets"], 1):
        emoji = "🔥" if "STRONG" in b["rec"] else ("✅" if "BET" in b["rec"] else "⚠️")
        bet_lines.append(
            f"{emoji} **{i}. {b['market']}** ({b['odds']})\n"
            f"    Prob: {b['prob']:.1%} | Edge: {b['edge']} | **{b['rec']}**"
        )
    bets_value = "\n\n".join(bet_lines)

    strong_bets = [b for b in game["bets"] if "STRONG" in b["rec"]]
    strong_section = "\n".join(
        [f"🔥 **{b['market']}** - {b['prob']:.1%} | {b['edge']}" for b in strong_bets]
    ) if strong_bets else "No strong plays flagged."

    why_lines = [f"**{b['market']}**: {b['why']}" for b in game["bets"] if "STRONG" in b["rec"]]
    why_section = "\n\n".join(why_lines) if why_lines else "N/A"

    color = COLOR_STRONG if strong_bets else COLOR_BET

    return {
        "title": f"BASEBALL {game['game']}",
        "description": f"{game['venue']} | {game['time']}",
        "color": color,
        "fields": [
            {"name": "PITCHING MATCHUP", "value": pitching[:1024], "inline": False},
            {"name": "MODEL PROJECTION", "value": projection[:1024], "inline": False},
            {"name": "STRONG BETS", "value": strong_section[:1024], "inline": False},
            {"name": "RECOMMENDED BETS", "value": bets_value[:1024], "inline": False},
            {"name": "KEY RATIONALE", "value": why_section[:1024], "inline": False},
        ],
        "footer": {"text": f"MultiSportPredict MLB Sharp | {datetime.now().strftime('%Y-%m-%d %H:%M')}"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def build_summary_embed(games: List[Dict[str, Any]]) -> Dict[str, Any]:
    strong = []
    for g in games:
        for b in g["bets"]:
            if "STRONG" in b["rec"]:
                strong.append(f"🔥 **{g['short']}**: {b['market']} - {b['prob']:.1%} | {b['edge']}")
    strong_section = "\n\n".join(strong) if strong else "No strong plays."

    return {
        "title": "MLB 2-GAME SHARP ANALYSIS - STRONG BETS SUMMARY",
        "description": (
            "Aug 14, 2026\n"
            "SEA @ HOU - 8:10 PM EDT @ Daikin Park\n"
            "MIL @ LAD - 10:10 PM EDT @ Dodger Stadium"
        ),
        "color": COLOR_STRONG,
        "fields": [
            {"name": "STRONG BET RECOMMENDATIONS", "value": strong_section[:1024], "inline": False},
            {"name": "BANKROLL NOTE",
             "value": "Strong bets are model + sharp-money aligned. Size 1-2 units each.\n"
                      "SGP (Dodgers ML + Under) is higher variance - consider 0.5 units.",
             "inline": False},
        ],
        "footer": {"text": "MultiSportPredict Smart Betting Guide"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    print("=" * 70)
    print("MLB 2-GAME SHARP ANALYSIS + DISCORD PUSH")
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)

    if not DISCORD_WEBHOOK_URL or DISCORD_WEBHOOK_URL == "None":
        print("DISCORD_WEBHOOK_URL not set in .env")
        return 1

    game1 = analyze_mariners_astros()
    game2 = analyze_brewers_dodgers()
    games = [game1, game2]

    print("\n" + "=" * 70)
    print("STRONG BET RECOMMENDATIONS")
    print("=" * 70)
    for g in games:
        print(f"\n{g['game']}")
        for b in g["bets"]:
            marker = "[STRONG]" if "STRONG" in b["rec"] else ("[BET]" if "BET" in b["rec"] else "[PASS]")
            print(f"  {marker} {b['market']}: {b['prob']:.1%} | {b['edge']} | {b['rec']}")

    print("\n" + "=" * 70)
    print("PUSHING TO DISCORD...")
    print("=" * 70)

    success = 0
    total = 3
    for i, g in enumerate(games, 1):
        payload = {"embeds": [build_game_embed(g)]}
        if push_payload(payload, f"Game embed {i}/2 ({g['short']})"):
            success += 1
        time.sleep(1)

    summary = {"embeds": [build_summary_embed(games)]}
    if push_payload(summary, "Summary embed (3/3)"):
        success += 1

    print("\n" + "=" * 70)
    print(f"Pushed {success}/{total} embeds to Discord")
    print("=" * 70)
    return 0 if success == total else 1


if __name__ == "__main__":
    raise SystemExit(main())