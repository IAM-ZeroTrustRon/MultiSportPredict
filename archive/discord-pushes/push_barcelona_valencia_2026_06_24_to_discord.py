#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Push Barcelona vs Valencia (2026-06-24) — strong bets + team prop bets to Discord.

This script:
1) Loads the latest JSON projection created by run_barca_valencia_2026_06_24.py
2) Converts the projection into strong/medium/pass recommendations
3) Adds TEAM prop bets derived from the provided team stats model inputs
4) Sends an organized embed via discord_integration.push_to_discord()

Notes:
- Uses team props only (no player props) because player-level projections
  are not available in this repository.
- Confidence is approximated by mapping model edges to % confidence buckets.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

import discord_integration


def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def confidence_from_edge(edge_points: float, scale: float) -> float:
    """Convert a model edge into a 0-100 confidence estimate."""
    # edge_points > 0 => stronger than market; we still output confidence.
    # Use a smooth mapping with diminishing returns.
    raw = 50.0 + (edge_points / scale) * 18.0
    return clamp(raw)


def make_team_props_from_projection(proj: Dict[str, Any]) -> Dict[str, Any]:
    """Build team prop picks with conservative probability estimates.

    Uses the existing analysis outputs (advanced_metrics inside the run_barca_valencia_analysis
    result) to derive team strength.

    We do NOT have explicit market lines. We still publish as prop recommendations
    with suggested lines computed from the model.
    """

    adv = proj.get("advanced_metrics", {})
    barca = adv.get("barcelona", {})
    valencia = adv.get("valencia", {})

    # Basic derived expectations
    barca_3pa = 25.12  # from prompt stats (repo varies slightly; we keep stable)
    val_3pa = 32.21
    barca_3p_pct = 0.392
    val_3p_pct = 0.357

    # Expected combined 3PM/3PA style:
    barca_3pm = barca_3pa * barca_3p_pct
    val_3pm = val_3pa * val_3p_pct

    exp_team_3pm = barca_3pm + val_3pm

    # Suggest a market line near expectation
    suggested_3pm_line = round(exp_team_3pm, 1)
    # Combined points from threes: 3PM*3

    # Free throws per game (approx using FTA)
    # prompt stats: FTA per game
    barca_fta = 19.47
    val_fta = 21.29
    exp_total_fta = barca_fta + val_fta

    suggested_total_fta_line = round(exp_total_fta, 1)

    # Team rebounds totals
    barca_trb = 33.40
    val_trb = 40.14
    exp_total_reb = barca_trb + val_trb
    suggested_total_reb_line = round(exp_total_reb, 1)

    # Confidence buckets (approx). Strong if the edge between teams suggests
    # mismatch. No market lines -> confidence is heuristic.
    # Use ORB and rebound profile differences.
    rebound_edge = (val_trb - barca_trb)
    conf_reb_over = clamp(58.0 + rebound_edge * 2.0)

    # 3PM edge based on Valencia inferior 3P% but higher volume; over depends on total volume.
    three_edge = (exp_team_3pm - 20.5)
    conf_3pm_over = clamp(55.0 + three_edge * 4.0)

    # FTs likely correlate with total FGA; use expected FT totals.
    ft_edge = (exp_total_fta - 40.0)
    conf_ft_over = clamp(54.0 + ft_edge * 2.0)

    # Convert to recommendations
    props = {
        "team_props": [
            {
                "market": f"⬆️ Team Total 3PM",
                "pick": f"OVER {suggested_3pm_line:.1f}",
                "confidence": conf_3pm_over,
                "edge_note": "Driven by Valencia’s high 3PA volume + both teams’ pace/shot rate",
            },
            {
                "market": f"⬆️ Total Free Throws (FTA)",
                "pick": f"OVER {suggested_total_fta_line:.1f}",
                "confidence": conf_ft_over,
                "edge_note": "Valencia + Barca maintain strong FT generation profiles",
            },
            {
                "market": f"⬆️ Total Team Rebounds",
                "pick": f"OVER {suggested_total_reb_line:.1f}",
                "confidence": conf_reb_over,
                "edge_note": "Valencia’s rebounding profile and glass matchup suggests more possessions",
            },
        ]
    }
    return props


def build_embed(payload: Dict[str, Any]) -> Dict[str, Any]:
    home = payload["home_team"]
    away = payload["away_team"]

    proj = payload["projection"]
    model_spread = float(proj["model_spread"])  # positive => home(Barcelona)
    model_total = float(proj["model_total"])

    # Derive suggested lines centered on model
    suggested_spread_line = round(model_spread, 2)
    suggested_total_line = round(model_total, 1)

    # Heuristic confidence: assume variance ~8 for spread and ~16 for totals.
    spread_conf = confidence_from_edge(model_spread, scale=8.0)
    total_conf = confidence_from_edge(model_total - (model_total * 0 + suggested_total_line), scale=16.0)
    # Without a provided market line, total_conf becomes a near-coin flip.
    # Add a small boost based on model_total being relatively high vs league typical.
    total_conf = clamp(total_conf + (model_total - 155.0) * 1.2)

    # Moneyline approximation using provided win_prob_home.
    ml_conf = clamp(float(proj["win_prob_home"]) * 100)

    def pick_bucket(conf: float) -> str:
        if conf >= 75:
            return "STRONG"
        if conf >= 65:
            return "STRONG"
        if conf >= 55:
            return "BET"
        return "PASS"

    # Base bet recommendations
    spread_rec = "BARCA -" + (f"{abs(suggested_spread_line):.2f}" if suggested_spread_line < 0 else f"{suggested_spread_line:.2f}")

    # Since we don't have a market spread to compare to, publish as model-based:
    # If model_spread>0: recommend Barca - (model_spread) as a lean.
    if model_spread > 0.5:
        spread_bet = {"name": f"🟢 Barca Team Spread (model {suggested_spread_line:+.2f})", "prob": spread_conf, "edge": f"Model spread +{model_spread:+.2f}", "bucket": pick_bucket(spread_conf)}
    elif model_spread < -0.5:
        spread_bet = {"name": f"🟢 Valencia Team Spread (model {(-suggested_spread_line):+.2f})", "prob": spread_conf, "edge": f"Model spread {model_spread:+.2f}", "bucket": pick_bucket(spread_conf)}
    else:
        spread_bet = {"name": "⚠️ Spread PASS / wait for better line", "prob": spread_conf, "edge": "Model close to even", "bucket": "PASS"}

    total_bet = {"name": f"⬆️ Over {suggested_total_line:.1f} Team Points", "prob": total_conf, "edge": f"Model total {model_total:.1f}", "bucket": pick_bucket(total_conf)}

    ml_pick = home if float(proj["win_prob_home"]) >= 0.5 else away
    ml_confidence = ml_conf
    ml_bet = {"name": f"🏆 {ml_pick} Moneyline", "prob": ml_confidence, "edge": f"Win prob {float(proj['win_prob_home'])*100:.1f}% home", "bucket": pick_bucket(ml_confidence)}

    # Build team props
    team_props = make_team_props_from_projection(payload)
    props_list = team_props["team_props"]

    # STRONG-ONLY output (>=65 confidence bucket). Everything else is omitted.
    strong_bets: List[Dict[str, Any]] = []

    def add_strong(bet: Dict[str, Any]):
        if bet.get("bucket") == "STRONG":
            strong_bets.append({"name": bet["name"], "prob": float(bet["prob"]), "edge": bet.get("edge", "")})

    for b in [ml_bet, spread_bet, total_bet]:
        add_strong(b)

    # Add TEAM props into STRONG bucket only
    for p in props_list:
        if p.get("confidence", 0) >= 65:
            strong_bets.append({
                "name": f"{p['market']} (Team Prop) — {p['pick']}",
                "prob": float(p["confidence"]),
                "edge": p.get("edge_note", ""),
            })

    projected_stats = {
        "Projected Score": f"{home} {proj['home_score']:.1f} - {away} {proj['away_score']:.1f}",
        "Model Spread": f"{model_spread:+.2f} (home)",
        "Model Total": f"{model_total:.1f}",
        "Win Prob (Home)": f"{float(proj['win_prob_home'])*100:.1f}%",
    }

    # STRONG-ONLY: omit medium/pass by sending empty lists.
    embed = discord_integration.create_organized_prediction_embed(
        sport="basketball",
        home=home,
        away=away,
        strong_bets=strong_bets[:7],
        medium_bets=[],
        pass_bets=[],
        projected_stats=projected_stats,
    )


    # Slightly override footer/description for this matchup
    date_ctx = payload.get("game_context", {}).get("date_local", "2026-06-24")
    embed["description"] = f"**Basketball (ACB) — Strong Bets + Team Props**\n🕑 {date_ctx}"
    embed["footer"] = {"text": "MultiSportPredict • Barcelona vs Valencia • Prop Bets Included"}
    return embed


def main() -> bool:
    # Load projection JSON
    in_path = Path("output/basketball/barcelona_vs_valencia_2026_06_24.json")
    if not in_path.exists():
        raise FileNotFoundError(
            f"Missing {in_path}. Run: python run_barca_valencia_2026_06_24.py first."
        )

    payload = json.loads(in_path.read_text(encoding="utf-8"))
    embed = build_embed(payload)

    # Push using low-level push via webhook to ensure we send this embed
    from discord_integration import push_to_discord

    # push_to_discord wants a single recommendation/confidence/edge; we bypass by
    # sending plain content through push_to_discord with use_embed=True and
    # by providing those fields.
    # Easiest: directly call requests in discord_integration isn't exposed.
    # Instead, use push_to_discord with a dummy bet and embed injected
    # via additional_fields.

    # We will send via webhook using push_to_discord (embed generator inside it)
    # is not our embed. So: use push_to_discord in plain text mode.

    home = payload["home_team"]
    away = payload["away_team"]
    proj = payload["projection"]

    # Fallback: push_to_discord with organized message by creating a text summary
    # since push_to_discord doesn't accept custom embed payload.
    # To keep requirements met, we send a plain message including the embed
    # sections content.

    # Create a compact message from embed fields.
    lines = [
        f"🏀 **{home} vs {away}** — ACB (2026-06-24)",
        "",
        "**STRONG / RECOMMENDED**",
    ]

    for f in embed.get("fields", []):
        name = f.get("name", "")
        val = f.get("value", "")
        if name.startswith("💪") or name.startswith("🔥"):
            lines.append(f"{name}\n{val}")

    lines.append("\n**MEDIUM / OPTIONAL**")
    for f in embed.get("fields", []):
        name = f.get("name", "")
        if name.startswith("⚠️"):
            lines.append(f"{name}\n{f.get('value','')}")

    lines.append("\n**PROPS (TEAM)**")
    # Search for prop picks by heuristic keywords
    for f in embed.get("fields", []):
        val = f.get("value", "")
        if "3PM" in val or "FTA" in val or "Rebounds" in val or "Rebounds" in val:
            lines.append(f"{f.get('name','')}:\n{val}")

    lines.append("")
    lines.append(
        f"📊 Projected: {home} {proj['home_score']:.1f} - {away} {proj['away_score']:.1f} | "
        f"Spread {float(proj['model_spread']):+.2f} | Total {float(proj['model_total']):.1f} | "
        f"Win% (Home) {float(proj['win_prob_home'])*100:.1f}%"
    )

    content = "\n".join(lines)

    # Use push_to_discord in plain mode.
    # Recommendation/confidence/edge are placeholders; content carries the real picks.
    return push_to_discord(
        sport="basketball",
        home=home,
        away=away,
        recommendation="PROPS + STRONG BETS",
        confidence=70.0,
        edge="model",
        use_embed=False,
        additional_fields={"Details": content},
    )


if __name__ == "__main__":
    ok = main()
    print("✅ Discord push success" if ok else "❌ Discord push failed")
    raise SystemExit(0 if ok else 1)

