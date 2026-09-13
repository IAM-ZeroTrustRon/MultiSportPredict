#!/usr/bin/env python
"""
ATP Masters 1000 Cincinnati — Round of 32 — 2 Matches -> Discord
====================================================================
Runs two Round-of-32 hard-court matches through the real Elo-based tennis
model (models/tennis_predictor.py), computes model projections, and pushes
both results to Discord via the dedicated recommendations webhook.

Matches (Tue Aug 18, 2026, ATP Cincinnati, Outdoor Hard, Best-of-3):
    1. Michael Zheng vs Lorenzo Musetti
    2. Andrey Rublev vs Nuno Borges

Usage:
    python run_musetti_zheng_rublev_borges_to_discord.py            # run + push
    python run_musetti_zheng_rublev_borges_to_discord.py --dry-run  # print payloads only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# Ensure project root on sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv("c:/MultiSportPredict/.env")

from models.tennis_predictor import predict_tennis_match

# ---------------------------------------------------------------------------
# Webhook URL (from user-provided config)
# ---------------------------------------------------------------------------
WEBHOOK_URL = "https://discord.com/api/webhooks/1517422221939708015/YB3a-symNZ6vhtC5qRnC6BOP5Lulk3Mj9L4-Ov1PALv79kUWTvuD67Y9Dk8itNUn6F3U"

# ---------------------------------------------------------------------------
# Match context — ATP Cincinnati Open, hard court, best-of-3
# ---------------------------------------------------------------------------
SURFACE = "hard"
TOURNAMENT = "ATP Masters 1000 Cincinnati"
ROUND = "Round of 32"
BEST_OF_5 = False

# ---------------------------------------------------------------------------
# Match definitions
# ---------------------------------------------------------------------------
MATCHES = [
    {
        "home_player": "Michael Zheng",
        "away_player": "Lorenzo Musetti",
        "market_home_odds": "+450",   # Zheng (Qualifier, ATP #110)
        "market_away_odds": "-600",   # Musetti (Seed #10, ATP #15)
        "market_total": 19.5,
        "market_spread": -3.5,
        "p1_hold_pct": 0.885,   # Zheng hold % in main draw (21/24 service games)
        "p1_break_pct": 0.40,
        "p2_hold_pct": 0.81,    # Musetti hold %
        "p2_break_pct": 0.38,
        "sgp_price": -170,
        "sgp_implied": 0.6296,
        "projected_total": 22.4,
        "model_spread": -3.5,
        "key_variance": "Zheng's break-point conversion vs ATP Top 20",
        "correlated_risk": "A quick Musetti 6-3, 6-3 blowout kills Over 19.5",
        "value_plays": {
            "original_lean": "Musetti to win ≥ 1 set is heavy chalk (-600 to -750). "
                            "Zheng's high first-serve hold rate on fast Cincinnati courts "
                            "pushes projected game totals into the 21.5–23.0 range, "
                            "making Over 19.5 standard for any 7-5, 6-4 or three-set scenario.",
            "plays": {
                "Musetti to Win ≥ 1 Set": "-600 to -750",
                "Total Games (Over 19.5)": "-220 to -240",
                "SGP (Musetti ≥ 1 Set + Over 19.5)": "-170",
            },
            "deep_dive": {
                "Target": "Over 19.5 Total Games / SGP -170",
                "Angle": "Zheng's serve hold rate + fast court pace",
                "Rationale": "Zheng's 88.5% hold percentage in main draw (21/24 service "
                            "games held across R128 and R64) and 74%-83% 1st serve points "
                            "won over his last two main-draw rounds push projected totals "
                            "to 21.5-23.0. Any competitive set score (7-5, 6-4) or "
                            "three-set match clears 19.5 easily.",
            },
            "model_view": {
                "favorite": "Lorenzo Musetti",
                "notes": "Musetti is the clear favorite but Zheng's serve keeps games "
                        "competitive. The value is in the total, not the moneyline.",
            },
        },
    },
    {
        "home_player": "Andrey Rublev",
        "away_player": "Nuno Borges",
        "market_home_odds": "-350",   # Rublev (Seed #6 / Top 10)
        "market_away_odds": "+280",   # Borges (ATP #35-40)
        "market_total": 20.5,
        "market_spread": -3.5,
        "p1_hold_pct": 0.83,    # Rublev 1st serve won %
        "p1_break_pct": 0.41,   # Rublev break point conversion
        "p2_hold_pct": 0.86,    # Borges service games won % in Cincinnati
        "p2_break_pct": 0.30,
        "sgp_price": -181,
        "sgp_implied": 0.6441,
        "projected_total": 22.8,
        "model_spread": -3.5,
        "key_variance": "Borges tiebreak variance (serve-heavy)",
        "correlated_risk": "Rublev 6-4, 6-4 hits 20 (pushes under 20.5)",
        "value_plays": {
            "original_lean": "Rublev to win ≥ 1 set is extreme chalk (-900 to -1100). "
                            "H2H history demonstrates Borges consistently holds serve to "
                            "reach 4+ games per set against Rublev (average game count "
                            "in H2H is 23.4 per best-of-3 match).",
            "plays": {
                "Rublev to Win ≥ 1 Set": "-900 to -1100",
                "Total Games (Over 20.5)": "-200 to -225",
                "SGP (Rublev ≥ 1 Set + Over 20.5)": "-181",
            },
            "deep_dive": {
                "Target": "Over 20.5 Total Games / SGP -181",
                "Angle": "Borges serve volume + H2H game count",
                "Rationale": "Borges logged 18 aces in his R64 marathon against Kokkinakis "
                            "and holds 86% of service games in Cincinnati. H2H average is "
                            "23.4 games per best-of-3 match. Most recent meeting went to "
                            "3 close sets (7-5, 7-6, 7-6) with Borges pushing extended "
                            "tiebreaks.",
            },
            "model_view": {
                "favorite": "Andrey Rublev",
                "notes": "Rublev is the heavy favorite but Borges' serve keeps games "
                        "competitive. The value is in the total, not the moneyline.",
            },
        },
    },
]


def _american_to_prob(odds: str) -> float:
    """Convert American odds string to implied win probability."""
    if odds is None:
        return 0.5
    v = int(odds.replace("+", ""))
    if v < 0:
        dec = 1 + (100 / abs(v))
    else:
        dec = 1 + (v / 100)
    return 1.0 / dec if dec > 1 else 0.5


def _compute_model_metrics(cfg: dict) -> dict:
    """Compute model projections using the same logic as the PowerShell template."""
    p1_hold = cfg["p1_hold_pct"]
    p1_break = cfg["p1_break_pct"]
    p2_hold = cfg["p2_hold_pct"]
    p2_break = cfg["p2_break_pct"]

    # Expected hold percentages
    p1_exp_hold = (p1_hold + (1.0 - p2_break)) / 2.0
    p2_exp_hold = (p2_hold + (1.0 - p1_break)) / 2.0

    # Tiebreak probability
    tiebreak_prob = round((p1_exp_hold * p2_exp_hold) * 0.55, 3)

    # Projected total games
    projected_total = round(
        19.0 + (p1_exp_hold * 2.2) + (p2_exp_hold * 2.2) + (tiebreak_prob * 3.5), 1
    )

    # Model spread
    spread_diff = round((p1_exp_hold - p2_exp_hold) * 12.5, 1)
    if spread_diff >= 0:
        model_spread = f"{cfg['home_player']} -{spread_diff}"
    else:
        model_spread = f"{cfg['away_player']} -{abs(spread_diff)}"

    # Set win probabilities
    p1_set_prob = round(
        min(0.95, max(0.50, (p1_hold / (p1_hold + p2_hold)) + 0.32)), 3
    )
    p2_set_prob = round(
        min(0.95, max(0.50, (p2_hold / (p1_hold + p2_hold)) + 0.32)), 3
    )

    # Total edge
    total_edge = round(projected_total - cfg["market_total"], 2)
    edge_sign = f"+{total_edge}" if total_edge >= 0 else f"{total_edge}"

    return {
        "p1_exp_hold": p1_exp_hold,
        "p2_exp_hold": p2_exp_hold,
        "tiebreak_prob": tiebreak_prob,
        "projected_total": projected_total,
        "model_spread": model_spread,
        "p1_set_prob": p1_set_prob,
        "p2_set_prob": p2_set_prob,
        "total_edge": total_edge,
        "edge_sign": edge_sign,
    }


def _build_embed(cfg: dict, model_metrics: dict, engine_result: dict) -> dict:
    """Build Discord embed payload matching the PowerShell template format."""
    home = cfg["home_player"]
    away = cfg["away_player"]
    ml = engine_result.get("moneyline", {})
    model_prob = ml.get("home_win_prob", 0.5)

    # Determine favorite
    if model_prob >= 0.5:
        fav = home
        fav_prob = model_prob
    else:
        fav = away
        fav_prob = 1 - model_prob

    # SGP description
    sgp_desc = f"{fav} ≥ 1 Set + Over {cfg['market_total']} Games"

    embed = {
        "title": f"🎾 Match Model Analysis: {home} vs. {away}",
        "color": 3447003,
        "fields": [
            {
                "name": "Market Baseline",
                "value": (
                    f"**Surface:** Outdoor Hard (DecoTurf - fast index)\n"
                    f"**Tournament:** {TOURNAMENT} ({ROUND})\n"
                    f"**Moneyline:** {home} ({cfg['market_home_odds']}) | "
                    f"{away} ({cfg['market_away_odds']})\n"
                    f"**Market Total:** {cfg['market_total']} Games"
                ),
                "inline": False,
            },
            {
                "name": "Model Projections",
                "value": (
                    f"**Projected Total:** `{model_metrics['projected_total']}` Games "
                    f"(Edge: `{model_metrics['edge_sign']}`)\n"
                    f"**Model Spread:** `{model_metrics['model_spread']}`\n"
                    f"**Tiebreak Prob:** `{model_metrics['tiebreak_prob'] * 100:.1f}%`\n"
                    f"**Model Win Prob:** {home} {model_prob:.1%} | {away} {1-model_prob:.1%}"
                ),
                "inline": True,
            },
            {
                "name": "Derivative Odds & SGP",
                "value": (
                    f"**{home} ≥ 1 Set:** `{model_metrics['p1_set_prob'] * 100:.1f}%`\n"
                    f"**{away} ≥ 1 Set:** `{model_metrics['p2_set_prob'] * 100:.1f}%`\n"
                    f"**Optimal SGP:** {sgp_desc} ({cfg['sgp_price']})"
                ),
                "inline": True,
            },
            {
                "name": "🎯 Value Plays",
                "value": "\n".join(
                    f"`{name}` — {odds}" for name, odds in cfg["value_plays"]["plays"].items()
                ),
                "inline": False,
            },
            {
                "name": "📝 Original Lean",
                "value": cfg["value_plays"]["original_lean"],
                "inline": False,
            },
            {
                "name": "🔍 Deep-Dive Analysis",
                "value": (
                    f"• **Target:** {cfg['value_plays']['deep_dive']['Target']}\n"
                    f"• **Angle:** {cfg['value_plays']['deep_dive']['Angle']}\n"
                    f"• **Rationale:** {cfg['value_plays']['deep_dive']['Rationale']}"
                ),
                "inline": False,
            },
            {
                "name": "🤖 Model View",
                "value": (
                    f"• **Model favorite:** {cfg['value_plays']['model_view']['favorite']} "
                    f"— {fav_prob:.1%}\n"
                    f"• **Note:** {cfg['value_plays']['model_view']['notes']}"
                ),
                "inline": False,
            },
            {
                "name": "⚠️ Key Variance & Correlated Risk",
                "value": (
                    f"• **Key Variance:** {cfg['key_variance']}\n"
                    f"• **Correlated Risk:** {cfg['correlated_risk']}"
                ),
                "inline": False,
            },
        ],
        "footer": {
            "text": "MultiSportPredict Tennis Engine | "
                    f"{__import__('datetime').datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        },
    }
    return embed


def run_match(cfg: dict, dry_run: bool = False) -> dict:
    """Run a single match prediction and push to Discord."""
    home = cfg["home_player"]
    away = cfg["away_player"]
    market_prob = _american_to_prob(cfg["market_home_odds"])

    print("=" * 60)
    print(f"ATP CINCINNATI — {home} vs {away}")
    print("=" * 60)

    # 1) Real model prediction
    result = predict_tennis_match(
        home_player=home,
        away_player=away,
        surface=SURFACE,
        best_of_5=BEST_OF_5,
        tournament=TOURNAMENT,
        round_name=ROUND,
        market_prob=market_prob,
        market_home_odds=cfg["market_home_odds"],
        market_away_odds=cfg["market_away_odds"],
    )

    ml = result.get("moneyline", {})
    model_prob = ml.get("home_win_prob", 0.5)

    # 2) Compute model metrics
    model_metrics = _compute_model_metrics(cfg)

    # 3) Build Discord embed
    embed = _build_embed(cfg, model_metrics, result)
    payload = {
        "username": "MultiSportPredict Tennis Engine",
        "embeds": [embed],
    }

    # Console output
    print(f"Tournament: {TOURNAMENT} | Surface: {SURFACE.capitalize()} | Round: {ROUND}")
    print(f"Win Prob:   {home} {model_prob:.1%} | {away} {1-model_prob:.1%}")
    print(f"Lean:       {ml.get('lean','')}")
    print(f"Projected Total: {model_metrics['projected_total']} (Edge: {model_metrics['edge_sign']})")
    print(f"Model Spread: {model_metrics['model_spread']}")
    print(f"Tiebreak Prob: {model_metrics['tiebreak_prob'] * 100:.1f}%")
    print(f"Set Probs:  {home} {model_metrics['p1_set_prob'] * 100:.1f}% | "
          f"{away} {model_metrics['p2_set_prob'] * 100:.1f}%")

    elo = result.get("elo_ratings", {})
    if elo:
        print(f"Elo:        {home}={elo.get(home,'N/A'):.0f} | "
              f"{away}={elo.get(away,'N/A'):.0f}")

    # Save output
    out_dir = Path("output/tennis")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{home.replace(' ','_')}_vs_{away.replace(' ','_')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nResults saved to: {out_path}")

    # 4) Push to Discord
    print("\nPushing recommendation to Discord...")
    if dry_run:
        print("[DRY RUN] Payload:")
        print(json.dumps(payload, indent=2, default=str))
        return result

    try:
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        if response.status_code in (200, 204):
            print(f"[SUCCESS] {home} vs {away} pushed to Discord.")
        else:
            print(f"[ERROR] Discord push failed. Status: {response.status_code} "
                  f"Body: {response.text}")
    except Exception as e:
        print(f"[EXCEPTION] Discord webhook error: {e}")

    print()
    return result


def main():
    parser = argparse.ArgumentParser(
        description="ATP Cincinnati 2 matches -> Discord"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print payloads without posting")
    args = parser.parse_args()

    print(f"\n=== ATP CINCINNATI 2-MATCH REPORT ({len(MATCHES)} matches) ===")
    for cfg in MATCHES:
        run_match(cfg, dry_run=args.dry_run)

    print("=" * 60)
    print("ALL MATCHES PROCESSED.")
    print("=" * 60)


if __name__ == "__main__":
    main()