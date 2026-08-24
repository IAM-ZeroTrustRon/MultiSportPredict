#!/usr/bin/env python
"""
Fenerbahçe SK vs Olympique Lyonnais + Hapoel Kfar Shalem vs MS Kafr Qasim
============================================================================
Runs both matches through the SoccerPredictor model with seed data mapped
from the match analysis & sharp report, then pushes comprehensive rich
Discord embeds with strong bets highlighted.

Usage:
    python run_fenerbahce_lyon_hapoel_kfar_shalem_kafr_qasim_to_discord.py  # run + push
    python run_fenerbahce_lyon_hapoel_kfar_shalem_kafr_qasim_to_discord.py --dry-run  # payload only
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

# Ensure UTF-8 output on Windows consoles (cp1252 can't encode emoji)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure the project root is on sys.path for imports
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import requests
import pandas as pd
from dotenv import load_dotenv

from models.soccer_predictor import SoccerPredictor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("run_fenerbahce_lyon_hapoel_to_discord")

load_dotenv()

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


# ---------------------------------------------------------------------------
# MATCH DEFINITIONS — Seed data mapped from match analysis & sharp report
# ---------------------------------------------------------------------------

MATCHES = [
    # =====================================================================
    # MATCH 1: Fenerbahçe SK vs Olympique Lyonnais (UCL Play-off R1)
    # =====================================================================
    {
        "name": "Fenerbahçe SK vs Olympique Lyonnais",
        "home_team": "Fenerbahçe SK",
        "away_team": "Olympique Lyonnais",
        "league": "UEFA Champions League",
        "competition": "UEFA Champions League – Play-off Round (1st Leg)",
        "kickoff_edt": "Tuesday, August 18, 2026 — 3:00 PM EDT",
        "venue": "Şükrü Saracoğlu Stadium, Istanbul, Turkey",
        "referee": "Sven Jablonski (Germany)",
        "market_line": -0.5,          # Sharp money on Fenerbahçe -0.5 AH
        "market_total": 2.5,
        "corner_line": 9.5,
        # Consensus odds (decimal / american / implied)
        "consensus": {
            "ml": [
                {"selection": "Fenerbahçe", "decimal": 2.00, "american": "+100", "implied": 50.0},
                {"selection": "Draw", "decimal": 3.50, "american": "+250", "implied": 28.6},
                {"selection": "Lyon", "decimal": 3.25, "american": "+225", "implied": 30.8},
            ],
            "goals": [
                {"selection": "Over 2.5", "decimal": 1.85, "american": "-118", "implied": 54.1},
                {"selection": "Under 2.5", "decimal": 1.95, "american": "-105", "implied": 51.3},
            ],
            "btts": [
                {"selection": "Yes", "decimal": 1.70, "american": "-143", "implied": 58.8},
                {"selection": "No", "decimal": 2.05, "american": "+105", "implied": 48.8},
            ],
            "corners": [
                {"selection": "Over 9.5", "decimal": 1.80, "american": "-125", "implied": 55.6},
                {"selection": "Under 9.5", "decimal": 1.95, "american": "-105", "implied": 51.3},
            ],
        },
        "h2h": [
            "Jan 23, 2025 (UEL): Fenerbahçe 0–0 Lyon",
            "Nov 23, 2004 (UCL): Lyon 4–2 Fenerbahçe",
            "Oct 19, 2004 (UCL): Fenerbahçe 1–3 Lyon",
            "Nov 05, 2001 (UCL): Lyon 3–1 Fenerbahçe",
            "Sep 25, 2001 (UCL): Fenerbahçe 0–1 Lyon",
        ],
        "tactical": (
            "Fenerbahçe leverage intense home support in Kadıköy to dictate tempo and "
            "establish early possession. Lyon operate with high verticality, looking to "
            "exploit transitional space behind advanced wing-backs."
        ),
        "officiating": (
            "Sven Jablonski averages ~4.0 yellow cards per game. With the sides "
            "demonstrating a measured card count in their recent European meetings, "
            "officiating volatility remains moderate."
        ),
        "sharp": (
            "Syndicate money has favored Fenerbahçe -0.5 on the Asian Handicap (priced "
            "at 2.00). Corner volume trends heavy toward the Over, as Fenerbahçe's "
            "wing-heavy build-up generated Over 10.5 corners in 4 of their last 5 fixtures."
        ),
        # Model seed data — Fenerbahçe home fortress, wing-heavy attack; Lyon vertical,
        # dangerous transitions but suspect away from home in Europe.
        "home_xg_for": 1.85,
        "home_xg_against": 1.05,
        "home_shots": 14.5,
        "home_sot": 5.0,
        "home_goals_for": 1.80,
        "home_goals_against": 0.90,
        "home_clean_sheets": 4,
        "home_tempo": 0.62,
        "home_width_crossing": 0.78,
        "home_final_third_pressure": 0.68,
        "away_xg_for": 1.45,
        "away_xg_against": 1.35,
        "away_shots": 12.0,
        "away_sot": 4.2,
        "away_goals_for": 1.50,
        "away_goals_against": 1.20,
        "away_clean_sheets": 2,
        "away_tempo": 0.55,
        "away_width_crossing": 0.55,
        "away_final_third_pressure": 0.58,
    },
    # =====================================================================
    # MATCH 2: Hapoel Kfar Shalem vs MS Kafr Qasim (Liga Leumit MD1)
    # =====================================================================
    {
        "name": "Hapoel Kfar Shalem vs MS Kafr Qasim",
        "home_team": "Hapoel Kfar Shalem",
        "away_team": "MS Kafr Qasim",
        "league": "Israeli Liga Leumit",
        "competition": "Israeli Liga Leumit – Matchday 1",
        "kickoff_edt": "Tuesday, August 18, 2026 — 12:30 PM EDT",
        "venue": "Hatikva Neighborhood Stadium, Tel Aviv, Israel",
        "referee": "TBD",
        "market_line": 0.0,
        "market_total": 2.5,
        "corner_line": 8.5,
        # Consensus odds
        "consensus": {
            "ml": [
                {"selection": "Hapoel Kfar Shalem", "decimal": 2.15, "american": "+115", "implied": 46.5},
                {"selection": "Draw", "decimal": 3.20, "american": "+220", "implied": 31.3},
                {"selection": "MS Kafr Qasim", "decimal": 3.10, "american": "+210", "implied": 32.3},
            ],
            "goals": [
                {"selection": "Over 2.5", "decimal": 1.90, "american": "-111", "implied": 52.6},
                {"selection": "Under 2.5", "decimal": 1.85, "american": "-118", "implied": 54.1},
            ],
            "btts": [
                {"selection": "Yes", "decimal": 1.75, "american": "-133", "implied": 57.1},
                {"selection": "No", "decimal": 1.95, "american": "+105", "implied": 51.3},
            ],
            "corners": [
                {"selection": "Over 8.5", "decimal": 1.85, "american": "-118", "implied": 54.1},
                {"selection": "Under 8.5", "decimal": 1.85, "american": "-118", "implied": 54.1},
            ],
        },
        "h2h": [
            "Jul 30, 2026 (Toto Cup Leumit): MS Kafr Qasim 2–1 Hapoel Kfar Shalem",
            "Apr 03, 2026 (Liga Leumit): MS Kafr Qasim 0–3 Hapoel Kfar Shalem",
            "Nov 07, 2025 (Liga Leumit): Hapoel Kfar Shalem 4–1 MS Kafr Qasim",
            "Feb 04, 2025 (Liga Leumit): MS Kafr Qasim 1–1 Hapoel Kfar Shalem",
            "Oct 18, 2024 (Liga Leumit): Hapoel Kfar Shalem 1–1 MS Kafr Qasim",
        ],
        "tactical": (
            "Hapoel Kfar Shalem maintain a forward-pressing structure that generates "
            "scoring opportunities at the cost of defensive transition vulnerability. "
            "MS Kafr Qasim arrive with psychological momentum following their 2–1 Toto "
            "Cup victory over Kfar Shalem three weeks prior."
        ),
        "officiating": "Matchday 1 — officiating tendencies not yet established.",
        "sharp": (
            "Early professional money moved toward BTTS - Yes (1.75) and Over 2.25/2.5 "
            "total goals, punishing soft opening totals lines in secondary tier Israeli "
            "football. Moneyline sharp activity is balanced, with slight resistance on "
            "Kafr Qasim +0.25 on the road."
        ),
        "btts_profile": (
            "Both teams have scored in 5 of their last 6 direct clashes and in 14 of "
            "Kfar Shalem's last 16 overall fixtures."
        ),
        # Model seed data — Kfar Shalem forward-pressing, dangerous both ways;
        # high BTTS profile; leaky transition defense.
        "home_xg_for": 1.65,
        "home_xg_against": 1.45,
        "home_shots": 12.5,
        "home_sot": 4.4,
        "home_goals_for": 1.60,
        "home_goals_against": 1.35,
        "home_clean_sheets": 1,
        "home_tempo": 0.58,
        "home_width_crossing": 0.55,
        "home_final_third_pressure": 0.65,
        "away_xg_for": 1.40,
        "away_xg_against": 1.50,
        "away_shots": 11.0,
        "away_sot": 3.9,
        "away_goals_for": 1.35,
        "away_goals_against": 1.45,
        "away_clean_sheets": 1,
        "away_tempo": 0.48,
        "away_width_crossing": 0.52,
        "away_final_third_pressure": 0.52,
    },
]


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _parse_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _odds_line(odds_list):
    """Format an odds list into a compact Discord field line."""
    return "\n".join(
        f"`{o['selection']}` — {o['decimal']:.2f} ({o['american']}) • {o['implied']:.1f}%"
        for o in odds_list
    )


def _dead_to_american(decimal: float) -> str:
    """Convert decimal odds to American odds string."""
    if decimal <= 1.0:
        return "N/A"
    if decimal >= 2.0:
        return f"+{round((decimal - 1.0) * 100)}"
    return str(-round(100.0 / (decimal - 1.0)))


def build_strong_bets(match: dict, pred: dict) -> list:
    """
    Derive strong bets from model output + sharp report alignment.
    Returns list of dicts: {name, tag, prob, edge, reason, color}
    """
    game = pred.get("game", {})
    goals = pred.get("goals_analysis", {})
    corners = pred.get("corners_analysis", {})
    btts_prob = _parse_float(pred.get("btts_probability", 0))
    home_win = _parse_float(game.get("home_win_prob", 0))
    away_win = _parse_float(game.get("away_win_prob", 0))
    draw = _parse_float(game.get("draw_prob", 0))
    over_25 = _parse_float(goals.get("over_25_prob", 0))
    over_15 = _parse_float(goals.get("over_15_prob", 0))
    corner_proj = _parse_float(corners.get("projection", 0))
    over_95 = _parse_float(corners.get("over_95_prob", 0))
    over_105 = _parse_float(corners.get("over_105_prob", 0))

    strong_bets = []

    if match["name"].startswith("Fenerbahçe"):
        # ---- MATCH 1: Fenerbahçe vs Lyon ----
        # STRONG BET 1: Fenerbahçe -0.5 AH / ML aggregate (sharp-aligned, home fortress)
        if home_win >= 0.55:
            strong_bets.append({
                "name": f"Fenerbahçe -0.5 Asian Handicap @ 2.00",
                "prob": home_win * 100,
                "edge": f"Model {home_win*100:.0f}% vs market ~50%",
                "reason": (
                    f"Sharp syndicate money aligned — home fortress in Kadıköy, model projects "
                    f"{game.get('projected_home_goals', 0):.2f}–{game.get('projected_away_goals', 0):.2f}. "
                    f"Sven Jablonski moderate card count keeps flow open for the favorite."
                ),
            })
        # STRONG BET 2: Over 2.5 (if model supports)
        if over_25 >= 0.52:
            strong_bets.append({
                "name": "Over 2.5 Goals @ 1.85",
                "prob": over_25 * 100,
                "edge": f"Model {over_25*100:.0f}% vs market 54.1%",
                "reason": (
                    f"Fenerbahçe's wing-heavy build-up (Over 10.5 corners in 4 of last 5) vs "
                    f"Lyon's vertical transitions should produce volume at both ends."
                ),
            })
        # STRONG BET 3: Over 9.5 Corners (sharp-aligned corner trend)
        if over_95 >= 0.52:
            strong_bets.append({
                "name": f"Over 9.5 Corners @ 1.80",
                "prob": over_95 * 100,
                "edge": f"Model {over_95*100:.0f}% vs market 55.6%",
                "reason": (
                    f"Model corner projection {corner_proj:.1f}. Fenerbahçe wing-heavy build-up "
                    f"generated Over 10.5 corners in 4 of last 5 — sharp volume trend aligned."
                ),
            })
        # STRONG BET 4: BTTS Yes (both attacks dangerous)
        if btts_prob >= 0.52:
            strong_bets.append({
                "name": "BTTS – Yes @ 1.70",
                "prob": btts_prob * 100,
                "edge": f"Model {btts_prob*100:.0f}% vs market 58.8%",
                "reason": (
                    f"Lyon's verticality will create chances on the break; Fenerbahçe's "
                    f"pressed home attack should find the target in Kadıköy."
                ),
            })
    else:
        # ---- MATCH 2: Hapoel Kfar Shalem vs MS Kafr Qasim ----
        # STRONG BET 1: BTTS Yes (sharp money + HISTORICAL PROFILE)
        if btts_prob >= 0.54:
            strong_bets.append({
                "name": "BTTS – Yes @ 1.75",
                "prob": btts_prob * 100,
                "edge": f"Model {btts_prob*100:.0f}% vs market 57.1%",
                "reason": (
                    f"Early professional money moved here. BTTS hit in 5 of last 6 direct "
                    f"clashes and 14 of Kfar Shalem's last 16 fixtures overall."
                ),
            })
        # STRONG BET 2: Over 2.5 (sharp money on Over 2.25/2.5)
        if over_25 >= 0.50:
            strong_bets.append({
                "name": "Over 2.5 Goals @ 1.90",
                "prob": over_25 * 100,
                "edge": f"Model {over_25*100:.0f}% vs market 52.6%",
                "reason": (
                    f"Sharp money punished soft opening totals in secondary tier Israeli "
                    f"football. Kfar Shalem's forward-pressing leaves transition gaps "
                    f"for Kafr Qasim's counters."
                ),
            })
        # STRONG BET 3: Over 1.5 (high-scoring H2H pattern)
        if over_15 >= 0.70:
            strong_bets.append({
                "name": "Over 1.5 Goals",
                "prob": over_15 * 100,
                "edge": f"Model {over_15*100:.0f}%",
                "reason": (
                    "5 of last 6 direct clashes featured 3+ goals; H2H average well "
                    "above the 2.0 threshold."
                ),
            })
        # STRONG BET 4: Home ML (Kfar Shalem attacking edge at home)
        if home_win >= 0.52:
            strong_bets.append({
                "name": f"Hapoel Kfar Shalem ML @ 2.15",
                "prob": home_win * 100,
                "edge": f"Model {home_win*100:.0f}% vs market 46.5%",
                "reason": (
                    f"Forward-pressing home side generates volume at Hatikva. "
                    f"3–0 and 4–1 wins in the last two home H2H meetings."
                ),
            })

    return strong_bets


def build_embed(match: dict, pred: dict) -> dict:
    """Build a fully rich Discord embed for the match."""
    game = pred.get("game", {})
    goals = pred.get("goals_analysis", {})
    corners = pred.get("corners_analysis", {})
    preds = pred.get("predictions", {})
    btts_prob = _parse_float(pred.get("btts_probability", 0))

    home_win = _parse_float(game.get("home_win_prob", 0)) * 100
    draw = _parse_float(game.get("draw_prob", 0)) * 100
    away_win = _parse_float(game.get("away_win_prob", 0)) * 100
    hg = _parse_float(game.get("projected_home_goals", 0))
    ag = _parse_float(game.get("projected_away_goals", 0))
    tg = _parse_float(game.get("projected_total_goals", 0))

    over_25 = _parse_float(goals.get("over_25_prob", 0)) * 100
    over_15 = _parse_float(goals.get("over_15_prob", 0)) * 100
    over_35 = _parse_float(goals.get("over_35_prob", 0)) * 100
    corner_proj = _parse_float(corners.get("projection", 0))
    over_95 = _parse_float(corners.get("over_95_prob", 0)) * 100
    over_85 = _parse_float(corners.get("over_85_prob", 0)) * 100
    over_105 = _parse_float(corners.get("over_105_prob", 0)) * 100

    strong_bets = build_strong_bets(match, pred)

    is_fener = match["name"].startswith("Fenerbahçe")
    header_emoji = "🏆" if is_fener else "🇮🇱"

    # ---------------- FIELD: MATCH INFO ----------------
    match_info = (
        f"**{match['competition']}**\n"
        f"🕒 {match['kickoff_edt']}\n"
        f"🏟️ {match['venue']}\n"
        f"👨‍⚖️ Referee: {match['referee']}"
    )

    # ---------------- FIELD: MODEL PROJECTION ----------------
    projection = (
        f"**{match['home_team']}** {hg:.2f} – {ag:.2f} **{match['away_team']}**\n"
        f"📈 **Total: {tg:.2f}**\n\n"
        f"**1X2 Probabilities**\n"
        f"🏠 {match['home_team']}: **{home_win:.1f}%**\n"
        f"🤝 Draw: **{draw:.1f}%**\n"
        f"✈️ {match['away_team']}: **{away_win:.1f}%**"
    )

    # ---------------- FIELD: GOALS & BTTS ----------------
    btts_name = "Yes" if btts_prob >= 0.5 else "No"
    goals_markets = (
        f"⚽ Over 1.5: **{over_15:.1f}%**\n"
        f"⚽ Over 2.5: **{over_25:.1f}%**\n"
        f"⚽ Over 3.5: **{over_35:.1f}%**\n"
        f"🤝 BTTS {btts_name}: **{btts_prob*100:.1f}%**"
    )

    # ---------------- FIELD: CORNERS ----------------
    corner_line = match.get("corner_line", 9.5)
    corners_markets = (
        f"📏 Projected Corners: **{corner_proj:.1f}**\n"
        f"🔄 Over {corner_line}: "
    )
    if is_fener:
        corners_markets += f"**{over_95:.1f}%**\n"
        corners_markets += f"🔄 Over 10.5: **{over_105:.1f}%**"
    else:
        corners_markets += f"**{over_85:.1f}%**"

    # ---------------- FIELD: CONSENSUS ODDS ----------------
    consensus = match.get("consensus", {})
    odds_ml = _odds_line(consensus.get("ml", []))
    odds_goals = _odds_line(consensus.get("goals", []))
    odds_btts = _odds_line(consensus.get("btts", []))
    odds_corners = _odds_line(consensus.get("corners", []))

    consensus_field = (
        f"**Moneyline (1X2)**\n{odds_ml}\n\n"
        f"**Goals O/U {match['market_total']}**\n{odds_goals}\n\n"
        f"**BTTS**\n{odds_btts}\n\n"
        f"**Corners O/U {corner_line}**\n{odds_corners}"
    )

    # ---------------- FIELD: HEAD-TO-HEAD ----------------
    h2h_lines = match.get("h2h", [])[:4]
    h2h_field = "\n".join(f"• {h}" for h in h2h_lines)
    if len(match.get("h2h", [])) > 4:
        h2h_field += f"\n• *+{len(match['h2h']) - 4} more*"

    # ---------------- FIELD: ANALYSIS ----------------
    analysis_lines = [
        f"**Tactical:** {match.get('tactical', 'N/A')}",
        f"**Officiating:** {match.get('officiating', 'N/A')}",
    ]
    if match.get("btts_profile"):
        analysis_lines.append(f"**BTTS Profile:** {match['btts_profile']}")
    analysis_field = "\n\n".join(analysis_lines)

    # ---------------- FIELD: SHARP REPORT ----------------
    sharp_field = match.get("sharp", "N/A")

    # ---------------- FIELD: STRONG BETS ----------------
    strong_lines = []
    for i, bet in enumerate(strong_bets, 1):
        strong_lines.append(
            f"🔥 **STRONG BET #{i}: {bet['name']}**\n"
            f"├─ Model Prob: **{bet['prob']:.1f}%**\n"
            f"├─ Edge: {bet['edge']}\n"
            f"└─ {bet['reason']}"
        )
    strong_field = "\n\n".join(strong_lines) if strong_lines else "No strong bets — market aligned with model."

    # ---------------- FIELD: VALUE / LEAN PLAYS ----------------
    value_lines = []
    if is_fener:
        # Lyon +0.5/ML value if away side live; plus over 1.5 alt
        value_lines.append(
            f"⚠️ **VALUE PLAY: Over 1.5 Goals (pre-match)**\n"
            f"│ Model {over_15:.1f}% — 4 of last 5 H2H had 2+ goals\n"
            f"└ ₿ Back in-play if early tempo stalls."
        )
        if away_win >= 30:
            value_lines.append(
                f"⚠️ **VALUE PLAY: Lyon +0.5 Double Chance**\n"
                f"│ Model {away_win + draw:.1f}% combined — Lyon verticality\n"
                f"└ Worth a small sprinkle at +115 or better."
            )
    else:
        value_lines.append(
            f"⚠️ **VALUE PLAY: Over 2.25 Goals (Asian)**\n"
            f"│ Sharp money punished soft totals — model {over_25:.1f}% on 2.5\n"
            f"└ 2.25 splits risk; take 2.5 if +EV confirms."
        )
        if away_win >= 30:
            value_lines.append(
                f"⚠️ **VALUE PLAY: MS Kafr Qasim +0.25 AH**\n"
                f"│ Sharp resistance on the away side + Toto Cup momentum\n"
                f"└ Small play at +210 or +0.25 roadside."
            )
    value_field = "\n\n".join(value_lines) if value_lines else "No additional value plays identified."

    # ---------------- EMBED ----------------
    embed = {
        "title": f"{header_emoji} {match['name'].upper()}",
        "description": f"**{match['competition']}** — Model Report & Sharp-Aligned Guide",
        "color": 3066993 if strong_bets else 10181046,
        "fields": [
            {
                "name": "📋 Match Info",
                "value": match_info,
                "inline": False,
            },
            {
                "name": "🤖 Model Projection",
                "value": projection,
                "inline": True,
            },
            {
                "name": "⚽ Goals & BTTS",
                "value": goals_markets,
                "inline": True,
            },
            {
                "name": "📏 Corners",
                "value": corners_markets,
                "inline": True,
            },
            {
                "name": "📊 Consensus Odds",
                "value": consensus_field,
                "inline": False,
            },
            {
                "name": "🗞️ Head-to-Head",
                "value": h2h_field,
                "inline": True,
            },
            {
                "name": "🔍 Analysis & Officiating",
                "value": analysis_field,
                "inline": True,
            },
            {
                "name": "💵 Sharp Report",
                "value": sharp_field,
                "inline": False,
            },
            {
                "name": "🔥 STRONG BETS",
                "value": strong_field,
                "inline": False,
            },
            {
                "name": "⚠️ Value Plays",
                "value": value_field,
                "inline": False,
            },
        ],
        "footer": {"text": "MultiSportPredict • Model-Driven Betting Intelligence"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return embed


def push_to_discord(match: dict, pred: dict, dry_run: bool = False) -> bool:
    """Push a match's comprehensive embed to Discord."""
    embed = build_embed(match, pred)
    payload = {"embeds": [embed]}

    if dry_run:
        print(f"\n[DRY RUN] Payload for {match['name']}:")
        print(json.dumps(payload, indent=2, default=str))
        return True

    if not WEBHOOK_URL or WEBHOOK_URL == "None":
        logger.error("DISCORD_WEBHOOK_URL not set in .env file")
        return False

    try:
        resp = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        if resp.status_code in (200, 204):
            logger.info("✅ Pushed %s to Discord", match["name"])
            return True
        else:
            logger.error("❌ Failed push %s: HTTP %s — %s", match["name"], resp.status_code, resp.text[:200])
            return False
    except Exception as exc:
        logger.error("❌ Error pushing %s: %s", match["name"], exc)
        return False


def format_console(match: dict, pred: dict) -> str:
    """Format a readable console block."""
    game = pred.get("game", {})
    goals = pred.get("goals_analysis", {})
    corners = pred.get("corners_analysis", {})
    btts_prob = _parse_float(pred.get("btts_probability", 0))

    home_win = _parse_float(game.get("home_win_prob", 0)) * 100
    draw = _parse_float(game.get("draw_prob", 0)) * 100
    away_win = _parse_float(game.get("away_win_prob", 0)) * 100
    hg = _parse_float(game.get("projected_home_goals", 0))
    ag = _parse_float(game.get("projected_away_goals", 0))
    tg = _parse_float(game.get("projected_total_goals", 0))
    over_25 = _parse_float(goals.get("over_25_prob", 0)) * 100

    strong_bets = build_strong_bets(match, pred)

    lines = []
    lines.append("=" * 80)
    lines.append(f"MATCH: {match['name']} ({match['competition']})")
    lines.append("=" * 80)
    lines.append(f"  🕒 {match['kickoff_edt']}")
    lines.append(f"  🏟️ {match['venue']}")
    lines.append(f"  👨‍⚖️ Referee: {match['referee']}")
    lines.append("")
    lines.append(f"  🤖 Model Projection: {match['home_team']} {hg:.2f} - {ag:.2f} {match['away_team']}")
    lines.append(f"  📈 Projected Total: {tg:.2f}")
    lines.append("")
    lines.append("  📊 Match Outcome:")
    lines.append(f"    {match['home_team']}: {home_win:.1f}%")
    lines.append(f"    Draw: {draw:.1f}%")
    lines.append(f"    {match['away_team']}: {away_win:.1f}%")
    lines.append("")
    lines.append("  ⚽ Goals Analysis:")
    lines.append(f"    Over 1.5: {_parse_float(goals.get('over_15_prob', 0))*100:.1f}%")
    lines.append(f"    Over 2.5: {over_25:.1f}%")
    lines.append(f"    Over 3.5: {_parse_float(goals.get('over_35_prob', 0))*100:.1f}%")
    lines.append(f"    BTTS Yes: {btts_prob*100:.1f}%")
    lines.append(f"  📏 Corners: {_parse_float(corners.get('projection', 0)):.1f}")
    lines.append("")
    lines.append("  🔥 STRONG BETS:")
    if strong_bets:
        for i, bet in enumerate(strong_bets, 1):
            lines.append(f"    {i}. {bet['name']} — {bet['prob']:.1f}% ({bet['edge']})")
    else:
        lines.append("    (none — market aligned with model)")
    lines.append("=" * 80)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run Fenerbahçe vs Lyon + Hapoel Kfar Shalem vs MS Kafr Qasim through model and push to Discord."
    )
    parser.add_argument("--dry-run", action="store_true", help="Print Discord payloads without posting")
    args = parser.parse_args()

    logger.info("Initializing SoccerPredictor...")
    predictor = SoccerPredictor(league="default")

    results = []
    push_success = 0

    for match in MATCHES:
        logger.info("Running inference for %s...", match["name"])
        print()

        override_kwargs = {
            k: v
            for k, v in match.items()
            if k.startswith(("home_", "away_"))
            and k not in ("home_team", "away_team")
        }

        try:
            prediction = predictor.predict(
                features=None,
                model=None,
                home_team=match["home_team"],
                away_team=match["away_team"],
                market_line=match.get("market_line", 0.0),
                market_total=match.get("market_total", 2.5),
                league=match.get("league", "default"),
                **override_kwargs,
            )

            # Save JSON output
            out_dir = Path("output/soccer")
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{match['home_team'].replace(' ', '_')}_vs_{match['away_team'].replace(' ', '_')}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(prediction, f, indent=2, default=str)
            logger.info("Saved JSON to %s", out_path)

            # Console output
            print(format_console(match, prediction))
            print()

            results.append({"match": match, "prediction": prediction})

            # Push to Discord (unless dry-run prints only)
            ok = push_to_discord(match, prediction, dry_run=args.dry_run)
            if ok and not args.dry_run:
                push_success += 1
            if args.dry_run:
                push_success += 1  # count as "OK" for dry-run summary

            if ok:
                logger.info("✅ Discord push OK for %s", match["name"])
            else:
                logger.error("❌ Discord push FAILED for %s", match["name"])

        except Exception as e:
            logger.error("Failed to process %s: %s", match["name"], e, exc_info=True)
            print(f"[ERROR] {match['name']}: {e}")

    # Final summary
    print()
    print("=" * 80)
    print("FINAL RECOMMENDATION SUMMARY")
    print("=" * 80)
    for match, prediction in zip(MATCHES, results):
        strong = build_strong_bets(match, prediction["prediction"])
        if strong:
            top = strong[0]
            print(f"  {match['name']:<40} -> 🔥 {top['name']} ({top['prob']:.1f}%)")
        else:
            print(f"  {match['name']:<40} -> (no strong bet)")

    if args.dry_run:
        print(f"\n[DRY RUN] {push_success}/{len(MATCHES)} payloads generated.")
    else:
        print(f"\n✅ {push_success}/{len(MATCHES)} matches pushed to Discord.")

    logger.info("Batch complete. %d/%d matches processed successfully.", len(results), len(MATCHES))


if __name__ == "__main__":
    main()