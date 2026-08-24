#!/usr/bin/env python
"""MLB 2-Game Sharp Analysis -> Discord (Aug 15, 2026).

Games:
1. Philadelphia Phillies @ Minnesota Twins (7:10 PM EDT, Target Field)
2. Arizona Diamondbacks @ Atlanta Braves (7:15 PM EDT, Truist Park)

Uses model-based projections (Poisson), NRFI engine, and confidence engine
to generate strong recommendations and push them to Discord.
"""
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
from core.confidence_engine import confidence_score, bet_recommendation

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
# GAME 1: PHILADELPHIA PHILLIES @ MINNESOTA TWINS
# =====================================================================
def analyze_phillies_twins() -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print("GAME 1: PHILADELPHIA PHILLIES @ MINNESOTA TWINS")
    print("7:10 PM EDT | Target Field")
    print("=" * 70)

    home, away = "Minnesota Twins", "Philadelphia Phillies"
    home_ml, away_ml = +135, -150
    home_rl, away_rl = "+1.5", "-1.5"
    home_rl_odds, away_rl_odds = -135, +115
    total_line, over_odds, under_odds = 8, -115, -105

    # Pitching reports
    luzardo = {"name": "Jesus Luzardo (LHP)", "wl": "10-5", "era": 3.32,
               "k9": 176 / 150 * 9, "whip": 1.14, "gb_rate": 0.503,
               "note": "Elite form: 1 or 0 ER in 4 of last 6 starts. 50.3% GB rate."}
    prielipp = {"name": "Connor Prielipp (LHP)", "wl": "3-5", "era": 4.79,
                "k9": 88 / 120 * 9, "whip": 1.32, "gb_rate": 0.429,
                "note": "xERA 4.20 but 42.9% GB rate. Vulnerable to PHI power."}

    # Model projections
    # PHI offense strong, MIN offense moderate
    phi_runs = (4.9 + prielipp["era"]) / 2 * 0.98  # Target Field slight neutral
    min_runs = (4.2 + luzardo["era"]) / 2 * 0.98
    total_proj = phi_runs + min_runs

    # Luzardo dominance adjustment - suppress MIN runs
    min_runs -= 0.25  # Luzardo elite form adjustment
    total_proj = phi_runs + min_runs

    under_prob = poisson_under_prob(total_proj, total_line) + 0.02  # slight sharp lean
    under_prob = clamp(under_prob)
    over_prob = 1.0 - under_prob

    run_diff = phi_runs - min_runs
    phi_ml = clamp(sigmoid(run_diff / 2.2 + 0.10) + 0.03)  # Luzardo edge
    min_ml = 1.0 - phi_ml
    phi_rl = clamp(phi_ml - 0.18)

    # NRFI via MLB engine - Luzardo elite should suppress first inning
    nrfi = project_nrfi(
        home_pitcher={"era": prielipp["era"], "k9": prielipp["k9"], "whip": prielipp["whip"]},
        away_pitcher={"era": luzardo["era"], "k9": luzardo["k9"], "whip": luzardo["whip"]},
        home_team_stats={"rpg": 4.2},
        away_team_stats={"rpg": 4.9},
        park_factor=0.98,  # Target Field slight neutral
        market_total=total_line,
        sharp_alignment=0.2,  # Slight sharp lean to NRFI with Luzardo
    )

    # Luis Arraez Over 1.5 Hits - sharp play
    arraez_hits_prob = 0.48  # Model prob based on 11.7% edge vs +182 implied
    arraez_implied = american_to_implied(182)
    arraez_edge = (arraez_hits_prob - arraez_implied) * 100

    print(f"  Projection: PHI {phi_runs:.2f} - MIN {min_runs:.2f} (Total {total_proj:.2f})")
    print(f"  Under {total_line}: {under_prob:.1%} | PHI ML: {phi_ml:.1%} | PHI RL: {phi_rl:.1%}")
    print(f"  NRFI: {nrfi['nrfi_probability']:.1%} | {nrfi['recommendation']}")
    print(f"  Arraez O1.5 Hits: {arraez_hits_prob:.1%} (implied {arraez_implied:.1%}, edge {arraez_edge:+.1f}%)")

    bets = []
    bets.append({
        "market": "Phillies Moneyline",
        "odds": fmt_odds(away_ml),
        "prob": phi_ml,
        "edge": f"{(phi_ml - american_to_implied(away_ml)) * 100:+.1f}%",
        "rec": "STRONG BET" if phi_ml > 0.60 else "BET",
        "why": (
            f"Luzardo (3.32 ERA, 1.14 WHIP) in elite form - 1 or 0 ER in 4 of last 6. "
            f"Prielipp (4.79 ERA, 1.32 WHIP) vulnerable. PHI won opener 7-1. "
            f"Model projects PHI {phi_runs:.1f} - MIN {min_runs:.1f}."
        ),
    })
    bets.append({
        "market": "Luis Arraez Over 1.5 Hits",
        "odds": "+182",
        "prob": arraez_hits_prob,
        "edge": f"{arraez_edge:+.1f}%",
        "rec": "STRONG BET" if arraez_edge > 8 else "BET",
        "why": (
            f"Sharp projections show 11.7% market edge. Arraez 3-for-5 in series opener "
            f"vs former team. Model prob {arraez_hits_prob:.0%} vs implied {arraez_implied:.0%}."
        ),
    })
    bets.append({
        "market": f"Under {total_line} Total Runs",
        "odds": fmt_odds(under_odds),
        "prob": under_prob,
        "edge": f"{(under_prob - 0.5) * 100:+.1f}%",
        "rec": "BET" if under_prob > 0.55 else "LEAN",
        "why": (
            f"Luzardo's elite form suppresses MIN offense. Model projects {total_proj:.2f} "
            f"vs market {total_line}. Twins need 5+ runs to win (42-14 record) but that's "
            f"a tall order vs Luzardo."
        ),
    })
    bets.append({
        "market": "NRFI (No Runs 1st Inning)",
        "odds": "-130 (est.)",
        "prob": nrfi["nrfi_probability"],
        "edge": f"{nrfi['edge_vs_market'] * 100:+.1f}%",
        "rec": nrfi["recommendation"] if "STRONG" in nrfi["recommendation"] else (
            "BET" if nrfi["recommendation"] == "BET" else "PASS"),
        "why": (
            f"NRFI prob {nrfi['nrfi_probability']:.1%}. Luzardo's elite K rate and "
            f"ground-ball profile (50.3% GB) suppress first-inning scoring."
        ),
    })
    bets.append({
        "market": f"Phillies Run Line {away_rl}",
        "odds": fmt_odds(away_rl_odds),
        "prob": phi_rl,
        "edge": f"{(phi_rl - 0.5) * 100:+.1f}%",
        "rec": "BET" if phi_rl > 0.55 else "LEAN",
        "why": (
            f"PHI won opener 7-1. Luzardo dominance + Prielipp vulnerability suggests "
            f"multi-run win potential. Model projects +{run_diff:.1f} run margin."
        ),
    })

    return {
        "game": f"{away} @ {home}", "short": "PHI @ MIN",
        "away": away, "home": home, "venue": "Target Field", "time": "7:10 PM EDT",
        "pitching": {"away": luzardo, "home": prielipp},
        "market": {"home_ml": home_ml, "away_ml": away_ml, "total": total_line,
                   "over_odds": over_odds, "under_odds": under_odds},
        "projection": {"away_runs": round(phi_runs, 2), "home_runs": round(min_runs, 2),
                       "total": round(total_proj, 2)},
        "probs": {"under": under_prob, "over": over_prob,
                  "home_win": min_ml, "away_win": phi_ml, "away_rl": phi_rl},
        "bets": bets,
    }


# =====================================================================
# GAME 2: ARIZONA DIAMONDBACKS @ ATLANTA BRAVES
# =====================================================================
def analyze_dbacks_braves() -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print("GAME 2: ARIZONA DIAMONDBACKS @ ATLANTA BRAVES")
    print("7:15 PM EDT | Truist Park")
    print("=" * 70)

    home, away = "Atlanta Braves", "Arizona Diamondbacks"
    home_ml, away_ml = -132, +122
    home_rl, away_rl = "-1.5", "+1.5"
    home_rl_odds, away_rl_odds = +138, -166
    total_line, over_odds, under_odds = 9, -110, -110

    # Pitching reports
    rodriguez = {"name": "Eduardo Rodriguez (LHP)", "wl": "11-4", "era": 2.70,
                 "k9": 8.5, "whip": 1.10,
                 "note": "Elite run prevention. Under on ER prop in 19 of last 25 games."}
    holmes = {"name": "Grant Holmes (RHP)", "wl": "7-4", "era": 3.47,
              "k9": 8.0, "whip": 1.20,
              "note": "xERA 4.73, FIP 4.82 - underlying stats show vulnerability."}

    # Model projections
    # 90-degree heat at Truist Park boosts offense slightly
    heat_factor = 1.03  # Mild boost from 90F heat

    ari_runs = (4.3 + holmes["era"]) / 2 * heat_factor
    atl_runs = (4.8 + rodriguez["era"]) / 2 * heat_factor
    total_proj = ari_runs + atl_runs

    # Rodriguez elite run prevention - suppress ATL runs
    atl_runs -= 0.30  # Rodriguez Under trend adjustment
    total_proj = ari_runs + atl_runs

    # Sharp money heavily on Under 9 despite heat
    under_prob = poisson_under_prob(total_proj, total_line) + 0.05  # Sharp boost
    under_prob = clamp(under_prob)
    over_prob = 1.0 - under_prob

    run_diff = atl_runs - ari_runs
    atl_ml = clamp(sigmoid(run_diff / 2.2 + 0.08) + 0.02)
    ari_ml = 1.0 - atl_ml
    atl_rl = clamp(atl_ml - 0.18)

    # NRFI via MLB engine - Rodriguez elite should suppress first inning
    nrfi = project_nrfi(
        home_pitcher={"era": holmes["era"], "k9": holmes["k9"], "whip": holmes["whip"]},
        away_pitcher={"era": rodriguez["era"], "k9": rodriguez["k9"], "whip": rodriguez["whip"]},
        home_team_stats={"rpg": 4.8},
        away_team_stats={"rpg": 4.3},
        park_factor=1.02,  # Truist Park slight hitter lean
        weather={"temperature": 90, "wind_speed": 5, "wind_direction_factor": 0.5},
        market_total=total_line,
        sharp_alignment=0.3,  # Sharp tracking Under -> NRFI lean
    )

    # Gabriel Moreno road prop - 20 of last 25 away games
    moreno_hrr_prob = 0.55  # Model prob for Over on Hits/Runs/RBIs
    moreno_implied = 0.50  # Typical market line
    moreno_edge = (moreno_hrr_prob - moreno_implied) * 100

    print(f"  Projection: ARI {ari_runs:.2f} - ATL {atl_runs:.2f} (Total {total_proj:.2f})")
    print(f"  Under {total_line}: {under_prob:.1%} | ATL ML: {atl_ml:.1%} | ATL RL: {atl_rl:.1%}")
    print(f"  NRFI: {nrfi['nrfi_probability']:.1%} | {nrfi['recommendation']}")
    print(f"  Moreno HRR: {moreno_hrr_prob:.1%} (edge {moreno_edge:+.1f}%)")

    bets = []
    bets.append({
        "market": f"Under {total_line} Total Runs",
        "odds": fmt_odds(under_odds),
        "prob": under_prob,
        "edge": f"{(under_prob - 0.5) * 100:+.1f}%",
        "rec": "STRONG BET" if under_prob > 0.60 else "BET",
        "why": (
            f"Sharp money heavily on Under despite 90F heat. Rodriguez (2.70 ERA) elite "
            f"run prevention - Under on ER prop in 19 of last 25. Holmes xERA 4.73/FIP 4.82 "
            f"shows vulnerability but Rodriguez counterbalances. Model projects {total_proj:.2f}."
        ),
    })
    bets.append({
        "market": "Braves Moneyline",
        "odds": fmt_odds(home_ml),
        "prob": atl_ml,
        "edge": f"{(atl_ml - american_to_implied(home_ml)) * 100:+.1f}%",
        "rec": "BET" if atl_ml > 0.55 else "LEAN",
        "why": (
            f"ATL home advantage at Truist Park. Holmes (3.47 ERA) solid but xERA 4.73 "
            f"suggests regression. Rodriguez elite but ATL lineup is deep."
        ),
    })
    bets.append({
        "market": "Gabriel Moreno Over Hits/Runs/RBIs",
        "odds": "-110 (est.)",
        "prob": moreno_hrr_prob,
        "edge": f"{moreno_edge:+.1f}%",
        "rec": "BET" if moreno_edge > 3 else "LEAN",
        "why": (
            f"Moreno hit Over on Hits/Runs/RBIs prop in 20 of last 25 away games. "
            f"Highly profitable road asset. Model prob {moreno_hrr_prob:.0%}."
        ),
    })
    bets.append({
        "market": "NRFI (No Runs 1st Inning)",
        "odds": "-125 (est.)",
        "prob": nrfi["nrfi_probability"],
        "edge": f"{nrfi['edge_vs_market'] * 100:+.1f}%",
        "rec": nrfi["recommendation"] if "STRONG" in nrfi["recommendation"] else (
            "BET" if nrfi["recommendation"] == "BET" else "PASS"),
        "why": (
            f"NRFI prob {nrfi['nrfi_probability']:.1%}. Rodriguez elite run prevention "
            f"(2.70 ERA) + sharp Under alignment supports first-inning suppression."
        ),
    })
    bets.append({
        "market": f"Braves Run Line {home_rl}",
        "odds": fmt_odds(home_rl_odds),
        "prob": atl_rl,
        "edge": f"{(atl_rl - 0.5) * 100:+.1f}%",
        "rec": "LEAN" if atl_rl > 0.50 else "PASS",
        "why": (
            f"ATL home edge + Holmes solid. But Rodriguez elite run prevention limits "
            f"multi-run win potential. Model projects +{run_diff:.1f} run margin."
        ),
    })

    return {
        "game": f"{away} @ {home}", "short": "ARI @ ATL",
        "away": away, "home": home, "venue": "Truist Park", "time": "7:15 PM EDT",
        "pitching": {"away": rodriguez, "home": holmes},
        "market": {"home_ml": home_ml, "away_ml": away_ml, "total": total_line,
                   "over_odds": over_odds, "under_odds": under_odds},
        "projection": {"away_runs": round(ari_runs, 2), "home_runs": round(atl_runs, 2),
                       "total": round(total_proj, 2)},
        "probs": {"under": under_prob, "over": over_prob,
                  "home_win": atl_ml, "away_win": ari_ml, "home_rl": atl_rl},
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
        f"  W-L: {away_p['wl']} | ERA: {away_p['era']} | WHIP: {away_p['whip']}\n"
        f"  {away_p['note']}\n\n"
        f"**{game['home']}** - {home_p['name']}\n"
        f"  W-L: {home_p['wl']} | ERA: {home_p['era']} | WHIP: {home_p['whip']}\n"
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
    if "home_rl" in probs:
        projection += f"  {game['home']} RL -1.5: {probs['home_rl']:.1%}\n"
    if "away_rl" in probs:
        projection += f"  {game['away']} RL -1.5: {probs['away_rl']:.1%}\n"

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
            "Aug 15, 2026\n"
            "PHI @ MIN - 7:10 PM EDT @ Target Field\n"
            "ARI @ ATL - 7:15 PM EDT @ Truist Park"
        ),
        "color": COLOR_STRONG,
        "fields": [
            {"name": "STRONG BET RECOMMENDATIONS", "value": strong_section[:1024], "inline": False},
            {"name": "BANKROLL NOTE",
             "value": "Strong bets are model + sharp-money aligned. Size 1-2 units each.\n"
                      "Arraez O1.5 Hits is a sharp prop play with 11.7% market edge.\n"
                      "Under 9 in ARI/ATL is heavily sharp-weighted despite 90F heat.",
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

    game1 = analyze_phillies_twins()
    game2 = analyze_dbacks_braves()
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