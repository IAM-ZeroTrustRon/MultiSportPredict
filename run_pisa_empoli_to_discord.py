#!/usr/bin/env python
"""
Pisa vs Empoli — Coppa Italia Round of 64
==========================================
Runs the SoccerPredictor model for Pisa (home) vs Empoli (away) and pushes
a rich multi-embed analysis to Discord.

Kickoff: Aug 17, 2026, 16:00 UTC / noon ET
Venue: Arena Garibaldi – Stadio Romeo Anconetani, Pisa

Usage:
    python run_pisa_empoli_to_discord.py           # run + push
    python run_pisa_empoli_to_discord.py --dry-run # print payload only
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# Ensure project root on sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv("c:/MultiSportPredict/.env")

import requests

from models.soccer_predictor import SoccerPredictor
from discord_integration import test_webhook

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MATCH CONFIG
# ---------------------------------------------------------------------------
HOME_TEAM = "Pisa"
AWAY_TEAM = "Empoli"
LEAGUE = "Coppa Italia"
COMPETITION = "Coppa Italia Round of 64"
VENUE = "Arena Garibaldi – Stadio Romeo Anconetani, Pisa"
KICKOFF = "Aug 17, 2026, 16:00 UTC / noon ET"
WEATHER = "Approximately 28 C"
MARKET_TOTAL = 2.5
MARKET_LINE = 0.0

# ---------------------------------------------------------------------------
# TEAM METRICS (derived from the provided analysis)
# ---------------------------------------------------------------------------
# Pisa: 0W-1D-4L, 3 scored, 11 conceded in last 5 → very poor defensive form
HOME_METRICS = {
    "home_xg_for": 0.70,
    "home_xg_against": 2.00,
    "home_shots": 10.0,
    "home_sot": 3.0,
    "home_goals_for": 0.60,
    "home_goals_against": 2.20,
    "home_clean_sheets": 0,
    "home_missing_attacker": 0,
    "home_missing_creator": 0,
    "home_missing_cb": 0,
    "home_missing_gk": 0,
    "home_tempo": 0.30,
    "home_width_crossing": 0.55,
    "home_final_third_pressure": 0.40,
}

# Empoli: 1W-3D-1L, 5 scored, 6 conceded in last 5 → lower-event, resilient
AWAY_METRICS = {
    "away_xg_for": 1.10,
    "away_xg_against": 1.20,
    "away_shots": 11.0,
    "away_sot": 3.5,
    "away_goals_for": 1.00,
    "away_goals_against": 1.20,
    "away_clean_sheets": 1,
    "away_missing_attacker": 0,
    "away_missing_creator": 0,
    "away_missing_cb": 0,
    "away_missing_gk": 0,
    "away_tempo": 0.20,
    "away_width_crossing": 0.50,
    "away_final_third_pressure": 0.45,
}

# ---------------------------------------------------------------------------
# MARKET SNAPSHOT (from ESPN)
# ---------------------------------------------------------------------------
MARKET = {
    "pisa_ml": "-120",
    "pisa_ml_implied": 54.5,
    "draw": "+255",
    "draw_implied": 28.2,
    "empoli_ml": "+340",
    "empoli_ml_implied": 22.7,
    "over_25": "+100",
    "over_25_implied": 50.0,
    "under_25": "-130",
    "under_25_implied": 56.5,
    "pisa_minus_05": "-135",
    "empoli_plus_05": "-105",
}

# ---------------------------------------------------------------------------
# FORM / H2H DATA
# ---------------------------------------------------------------------------
PISA_FORM = "D 1-1 Bologna; L 1-2 Lazio; L 0-3 Napoli; L 0-3 Cremonese; L 1-2 Lecce"
PISA_RECORD = "0W-1D-4L, 3 scored, 11 conceded"
EMPOLI_FORM = "D 1-1 Livorno; D 2-2 Monza; W 1-0 Avellino; L 0-2 Venezia; D 1-1 Virtus Entella"
EMPOLI_RECORD = "1W-3D-1L, 5 scored, 6 conceded"
H2H_NOTE = "Empoli unbeaten in last five vs Pisa: 4W-1D. Includes 3-1 and 3-2 Empoli home wins and a 1-1 draw in Pisa from 2019-21 Serie B meetings."


def run_model() -> dict:
    """Run the SoccerPredictor model for Pisa vs Empoli."""
    logger.info("Running prediction for: %s vs %s (%s)", HOME_TEAM, AWAY_TEAM, LEAGUE)

    predictor = SoccerPredictor(league=LEAGUE)
    prediction_data = predictor.predict(
        features=pd.DataFrame(),
        model=None,
        home_team=HOME_TEAM,
        away_team=AWAY_TEAM,
        market_line=MARKET_LINE,
        market_total=MARKET_TOTAL,
        league=LEAGUE,
        **HOME_METRICS,
        **AWAY_METRICS,
    )

    game = prediction_data.get("game", {})
    logger.info(
        "Projected: %s %.2f - %.2f %s | Total: %.2f",
        HOME_TEAM,
        game.get("projected_home_goals", 0),
        game.get("projected_away_goals", 0),
        AWAY_TEAM,
        game.get("projected_total_goals", 0),
    )
    return prediction_data


def build_embeds(prediction_data: dict) -> list:
    """Build the Discord embeds for the match analysis."""
    game = prediction_data.get("game", {})
    goals_analysis = prediction_data.get("goals_analysis", {})
    btts_prob = prediction_data.get("btts_probability", 0)
    corner_proj = prediction_data.get("corner_projection", 0)

    home_win_pct = game.get("home_win_prob", 0) * 100
    draw_pct = game.get("draw_prob", 0) * 100
    away_win_pct = game.get("away_win_prob", 0) * 100
    proj_home = game.get("projected_home_goals", 0)
    proj_away = game.get("projected_away_goals", 0)
    proj_total = game.get("projected_total_goals", 0)
    over_25_pct = goals_analysis.get("over_25_prob", 0) * 100
    under_25_pct = 100 - over_25_pct
    btts_pct = btts_prob * 100

    timestamp = datetime.now(timezone.utc).isoformat()

    # -----------------------------------------------------------------------
    # EMBED 1 — Match Overview & Form
    # -----------------------------------------------------------------------
    embed1 = {
        "title": "⚽ COPPA ITALIA ROUND OF 64 — PISA vs EMPOLI",
        "description": (
            f"**{HOME_TEAM} vs {AWAY_TEAM}**\n"
            f"📅 {KICKOFF}\n"
            f"🏟️ {VENUE}\n"
            f"🌡️ {WEATHER}"
        ),
        "color": 1752220,  # Green
        "fields": [
            {
                "name": "🔵 PISA — Team Profile",
                "value": (
                    f"**Recent Five:** {PISA_FORM}\n"
                    f"**Record:** {PISA_RECORD}\n"
                    f"**Context:** Finished 2025-26 in Serie A\n"
                    f"**Warning Flag:** Conceded 11 goals in 5 matches, incl. 0-3 defeats to Napoli and Cremonese"
                ),
                "inline": False,
            },
            {
                "name": "🔴 EMPOLI — Team Profile",
                "value": (
                    f"**Recent Five:** {EMPOLI_FORM}\n"
                    f"**Record:** {EMPOLI_RECORD}\n"
                    f"**Context:** Finished 2025-26 in Serie B\n"
                    f"**Profile:** Lower-event and resilient — 4 of 5 matches at 2 total goals or fewer"
                ),
                "inline": False,
            },
            {
                "name": "⚔️ HEAD-TO-HEAD",
                "value": (
                    f"{H2H_NOTE}\n\n"
                    f"**Key takeaway:** Market prices Pisa primarily on home field, "
                    f"but matchup history and current form favor the away side's handicap."
                ),
                "inline": False,
            },
        ],
        "footer": {"text": "MultiSportPredict • Coppa Italia Analytics"},
        "timestamp": timestamp,
    }

    # -----------------------------------------------------------------------
    # EMBED 2 — Market Snapshot & Model Projection
    # -----------------------------------------------------------------------
    embed2 = {
        "title": "📊 MARKET SNAPSHOT & MODEL PROJECTION",
        "color": 15844367,  # Gold
        "fields": [
            {
                "name": "🎯 MONEYLINE",
                "value": (
                    f"🔵 **Pisa ML:** {MARKET['pisa_ml']} ({MARKET['pisa_ml_implied']:.1f}% implied)\n"
                    f"🤝 **Draw:** {MARKET['draw']} ({MARKET['draw_implied']:.1f}% implied)\n"
                    f"🔴 **Empoli ML:** {MARKET['empoli_ml']} ({MARKET['empoli_ml_implied']:.1f}% implied)\n"
                    f"Pisa opened -105 and moved to ~-120; Empoli listed at +340."
                ),
                "inline": False,
            },
            {
                "name": "📈 TOTAL GOALS (O/U 2.5)",
                "value": (
                    f"Over 2.5: {MARKET['over_25']} ({MARKET['over_25_implied']:.1f}% implied)\n"
                    f"Under 2.5: {MARKET['under_25']} ({MARKET['under_25_implied']:.1f}% implied)\n"
                    f"Line is shaded toward the under."
                ),
                "inline": True,
            },
            {
                "name": "🏁 HANDICAP",
                "value": (
                    f"Pisa -0.5: {MARKET['pisa_minus_05']} (must win in 90 min)\n"
                    f"Empoli +0.5: {MARKET['empoli_plus_05']} (win or draw in 90 min)"
                ),
                "inline": True,
            },
            {
                "name": "🤖 MODEL PROJECTION",
                "value": (
                    f"**Projected Score:** {HOME_TEAM} {proj_home:.2f} – {proj_away:.2f} {AWAY_TEAM}\n"
                    f"**Projected Total:** {proj_total:.2f}\n"
                    f"**Win Prob:** {HOME_TEAM} {home_win_pct:.1f}% | Draw {draw_pct:.1f}% | {AWAY_TEAM} {away_win_pct:.1f}%\n"
                    f"**Over 2.5:** {over_25_pct:.1f}% | **Under 2.5:** {under_25_pct:.1f}%\n"
                    f"**BTTS Yes:** {btts_pct:.1f}% | **Corners:** {corner_proj:.1f}\n\n"
                    f"Base total projection: 1-1 or 0-1 after 90 minutes."
                ),
                "inline": False,
            },
        ],
        "footer": {"text": "MultiSportPredict • Market & Model"},
        "timestamp": timestamp,
    }

    # -----------------------------------------------------------------------
    # EMBED 3 — Betting Interpretation
    # -----------------------------------------------------------------------
    embed3 = {
        "title": "💡 BETTING INTERPRETATION",
        "color": 15105570,  # Orange
        "fields": [
            {
                "name": "✅ BEST RISK-ADJUSTED ANGLE",
                "value": (
                    "**Empoli +0.5 / Empoli double chance**\n"
                    "Captures the current-form edge, Empoli's five-match H2H unbeaten record, "
                    "and the plausible 1-1 draw outcome."
                ),
                "inline": False,
            },
            {
                "name": "⚠️ SECONDARY ANGLE",
                "value": (
                    "**Under 2.5 goals**\n"
                    "Supported by current pricing and Empoli's lower-event recent profile. "
                    "Pisa's defensive weakness prevents this from being a maximal-confidence position."
                ),
                "inline": False,
            },
            {
                "name": "🎯 HIGHER-VARIANCE VALUE PLAY",
                "value": (
                    "**Empoli ML (+340)**\n"
                    "Low raw probability, but more defensible than Pisa ML if the market is "
                    "over-weighting home advantage."
                ),
                "inline": False,
            },
            {
                "name": "❌ AVOID",
                "value": (
                    "**Pisa -0.5 at the current price**\n"
                    "A Pisa win requires fading Empoli's superior latest form and the recent "
                    "H2H trend, with no draw protection."
                ),
                "inline": False,
            },
            {
                "name": "📋 PRE-KICKOFF VALIDATION",
                "value": (
                    "1. Pisa's starting goalkeeper and center-back availability\n"
                    "2. Whether Empoli field a first-choice striker\n"
                    "3. Whether either side rotates heavily for the cup\n\n"
                    "These inputs should move the goal projection more than small moneyline fluctuations."
                ),
                "inline": False,
            },
        ],
        "footer": {"text": "MultiSportPredict • Betting Guide • Aug 17, 2026"},
        "timestamp": timestamp,
    }

    return [embed1, embed2, embed3]


def push_to_discord(embeds: list, dry_run: bool = False) -> bool:
    """Push embeds to Discord."""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url or webhook_url == "None":
        logger.error("DISCORD_WEBHOOK_URL not set in .env file")
        return False

    if dry_run:
        print("[DRY RUN] Payloads:")
        for i, embed in enumerate(embeds, 1):
            print(f"\n--- Embed {i}/{len(embeds)} ---")
            print(json.dumps({"embeds": [embed]}, indent=2, default=str))
        return True

    success_count = 0
    total = len(embeds)

    for i, embed in enumerate(embeds, 1):
        payload = {"embeds": [embed]}
        try:
            resp = requests.post(webhook_url, json=payload, timeout=15)
            if resp.status_code in (200, 204):
                logger.info("Embed %d/%d pushed to Discord", i, total)
                success_count += 1
            else:
                logger.error("Embed %d/%d failed: HTTP %s -- %s", i, total, resp.status_code, resp.text[:200])
        except Exception as exc:
            logger.error("Embed %d/%d error: %s", i, total, exc)

    if success_count == total:
        logger.info("ALL %d EMBEDS SUCCESSFULLY PUSHED TO DISCORD!", total)
        return True
    else:
        logger.warning("%d/%d embeds pushed successfully", success_count, total)
        return False


def main():
    parser = argparse.ArgumentParser(description="Pisa vs Empoli — Coppa Italia -> Discord")
    parser.add_argument("--dry-run", action="store_true", help="Print payload without posting")
    args = parser.parse_args()

    print("=" * 70)
    print(f"COPPA ITALIA ROUND OF 64 — {HOME_TEAM} vs {AWAY_TEAM}")
    print("=" * 70)
    print(f"Kickoff: {KICKOFF}")
    print(f"Venue: {VENUE}")
    print("=" * 70)

    if not args.dry_run and not test_webhook():
        logger.error("Discord webhook not configured or failed test. Check DISCORD_WEBHOOK_URL in your .env file.")
        return

    # 1) Run the model
    prediction_data = run_model()

    # 2) Build embeds
    embeds = build_embeds(prediction_data)

    # 3) Push to Discord
    success = push_to_discord(embeds, dry_run=args.dry_run)

    if success:
        logger.info("Successfully pushed Pisa vs Empoli analysis to Discord (or dry-run).")
    else:
        logger.error("Failed to push Pisa vs Empoli analysis to Discord.")


if __name__ == "__main__":
    main()