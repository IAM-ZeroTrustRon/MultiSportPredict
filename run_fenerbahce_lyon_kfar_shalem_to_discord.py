#!/usr/bin/env python
"""
Run 2 Soccer Matches Through the Model and Push to Discord
===========================================================
1. Fenerbahce SK vs Olympique Lyonnais (UEFA Champions League - Play-off Round, 1st Leg)
2. Hapoel Kfar Shalem vs MS Kafr Qasim (Israeli Liga Leumit - Matchday 1)

Runs each match through the SoccerPredictor (Bivariate Poisson + Dixon-Coles xG model)
with seed data, then pushes a comprehensive rich embed to Discord highlighting
strong bets.

Usage:
    python run_fenerbahce_lyon_kfar_shalem_to_discord.py                # run + push
    python run_fenerbahce_lyon_kfar_shalem_to_discord.py --dry-run      # print payload only
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

# Ensure the project root is on sys.path for imports
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import requests
from dotenv import load_dotenv

from models.soccer_predictor import SoccerPredictor

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("run_two_matches_to_discord")

load_dotenv()

# ---------------------------------------------------------------------------
# MATCH DEFINITIONS - Seed data mapped to model coefficients
# ---------------------------------------------------------------------------
MATCHES = [
    {
        "name": "Fenerbahce SK vs Olympique Lyonnais",
        "home_team": "Fenerbahce",
        "away_team": "Lyon",
        "league": "Champions League",
        "competition": "UEFA Champions League - Play-off Round (1st Leg)",
        "venue": "Sukru Saracoglu Stadium, Istanbul, Turkey",
        "kickoff": "Tuesday, August 18, 2026 - 3:00 PM EDT",
        "referee": "Sven Jablonski (Germany)",
        "market_line": 0.0,
        "market_total": 2.5,
        "corner_line": 9.5,
        # Fenerbahce: intense home support, dictate tempo, wing-heavy build-up
        "home_xg_for": 1.85,
        "home_xg_against": 1.05,
        "home_shots": 14.5,
        "home_sot": 5.0,
        "home_goals_for": 1.90,
        "home_goals_against": 0.90,
        "home_clean_sheets": 4,
        "home_tempo": 0.65,
        "home_width_crossing": 0.75,
        "home_final_third_pressure": 0.65,
        # Lyon: high verticality, exploit transitional space
        "away_xg_for": 1.55,
        "away_xg_against": 1.35,
        "away_shots": 12.0,
        "away_sot": 4.2,
        "away_goals_for": 1.50,
        "away_goals_against": 1.25,
        "away_clean_sheets": 2,
        "away_tempo": 0.55,
        "away_width_crossing": 0.60,
        "away_final_third_pressure": 0.55,
    },
    {
        "name": "Hapoel Kfar Shalem vs MS Kafr Qasim",
        "home_team": "Hapoel Kfar Shalem",
        "away_team": "MS Kafr Qasim",
        "league": "Liga Leumit",
        "competition": "Israeli Liga Leumit - Matchday 1",
        "venue": "Hatikva Neighborhood Stadium, Tel Aviv, Israel",
        "kickoff": "Tuesday, August 18, 2026 - 12:30 PM EDT",
        "referee": "TBD",
        "market_line": 0.0,
        "market_total": 2.5,
        "corner_line": 8.5,
        # Hapoel Kfar Shalem: forward-pressing, BTTS in 14 of last 16
        "home_xg_for": 1.60,
        "home_xg_against": 1.45,
        "home_shots": 12.0,
        "home_sot": 4.2,
        "home_goals_for": 1.55,
        "home_goals_against": 1.40,
        "home_clean_sheets": 2,
        "home_tempo": 0.60,
        "home_width_crossing": 0.55,
        "home_final_third_pressure": 0.65,
        # MS Kafr Qasim: momentum from Toto Cup win, BTTS in 5 of last 6 H2H
        "away_xg_for": 1.35,
        "away_xg_against": 1.50,
        "away_shots": 10.5,
        "away_sot": 3.8,
        "away_goals_for": 1.30,
        "away_goals_against": 1.45,
        "away_clean_sheets": 2,
        "away_tempo": 0.45,
        "away_width_crossing": 0.50,
        "away_final_third_pressure": 0.50,
    },
]

# ---------------------------------------------------------------------------
# CONSENSUS ODDS (from the provided match data)
# ---------------------------------------------------------------------------
CONSENSUS_ODDS = {
    "Fenerbahce SK vs Olympique Lyonnais": {
        "home_ml": 2.00, "draw_ml": 3.50, "away_ml": 3.25,
        "over25": 1.85, "under25": 1.95,
        "btts_yes": 1.70, "btts_no": 2.05,
        "corners_over": 1.80, "corners_under": 1.95, "corner_line": 9.5,
    },
    "Hapoel Kfar Shalem vs MS Kafr Qasim": {
        "home_ml": 2.15, "draw_ml": 3.20, "away_ml": 3.10,
        "over25": 1.90, "under25": 1.85,
        "btts_yes": 1.75, "btts_no": 1.95,
        "corners_over": 1.85, "corners_under": 1.85, "corner_line": 8.5,
    },
}


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _parse_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _american(decimal: float) -> str:
    """Convert decimal odds to American odds string."""
    if decimal <= 0:
        return "N/A"
    if decimal >= 2.0:
        return f"+{round((decimal - 1.0) * 100)}"
    return str(-round(100.0 / (decimal - 1.0)))


def _ev_pct(prob: float, decimal_odds: float) -> float:
    """Calculate expected value: (prob * odds) - 1."""
    return (prob * decimal_odds) - 1.0


def _classify_bet(ev: float, prob: float) -> str:
    """Classify a bet as STRONG BET, BET, LEAN, or PASS based on EV and probability."""
    if ev >= 0.08 and prob >= 0.55:
        return "STRONG BET"
    elif ev >= 0.04 and prob >= 0.52:
        return "BET"
    elif ev >= 0.0:
        return "LEAN"
    else:
        return "PASS"


def build_analysis(match: dict, prediction: dict) -> dict:
    """Build a comprehensive analysis dict from model output + consensus odds."""
    game = prediction.get("game", {})
    preds = prediction.get("predictions", {})
    goals = prediction.get("goals_analysis", {})
    corners = prediction.get("corners_analysis", {})
    btts_prob = _parse_float(prediction.get("btts_probability", 0))
    corner_proj = _parse_float(prediction.get("corner_projection", 0))

    home_win = _parse_float(game.get("home_win_prob", 0))
    draw = _parse_float(game.get("draw_prob", 0))
    away_win = _parse_float(game.get("away_win_prob", 0))
    hg = _parse_float(game.get("projected_home_goals", 0))
    ag = _parse_float(game.get("projected_away_goals", 0))
    tg = _parse_float(game.get("projected_total_goals", 0))
    over_25 = _parse_float(goals.get("over_25_prob", 0))
    over_15 = _parse_float(goals.get("over_15_prob", 0))
    over_35 = _parse_float(goals.get("over_35_prob", 0))

    odds = CONSENSUS_ODDS.get(match["name"], {})
    bets = []

    # 1X2 Moneyline
    ml_probs = [
        ("Home", home_win, odds.get("home_ml", 2.0)),
        ("Draw", draw, odds.get("draw_ml", 3.5)),
        ("Away", away_win, odds.get("away_ml", 3.25)),
    ]
    ml_best = max(ml_probs, key=lambda x: x[1])
    ml_ev = _ev_pct(ml_best[1], ml_best[2])
    ml_label = _classify_bet(ml_ev, ml_best[1])
    ml_side = {"Home": match["home_team"], "Draw": "Draw", "Away": match["away_team"]}[ml_best[0]]
    bets.append({
        "market": "Moneyline",
        "selection": f"{ml_side} ({ml_best[1]*100:.1f}%)",
        "odds": f"{ml_best[2]:.2f} ({_american(ml_best[2])})",
        "prob": ml_best[1],
        "ev": ml_ev,
        "label": ml_label,
        "reason": f"Model projects {ml_side} at {ml_best[1]*100:.1f}% vs implied {100/ml_best[2]:.1f}%.",
    })

    # Over/Under 2.5
    ou_side = "Over 2.5" if over_25 >= 0.5 else "Under 2.5"
    ou_prob = max(over_25, 1 - over_25)
    ou_odds = odds.get("over25" if ou_side == "Over 2.5" else "under25", 1.9)
    ou_ev = _ev_pct(ou_prob, ou_odds)
    ou_label = _classify_bet(ou_ev, ou_prob)
    bets.append({
        "market": "Total Goals",
        "selection": f"{ou_side} ({ou_prob*100:.1f}%)",
        "odds": f"{ou_odds:.2f} ({_american(ou_odds)})",
        "prob": ou_prob,
        "ev": ou_ev,
        "label": ou_label,
        "reason": f"Model projects {tg:.2f} total goals; Over 2.5 at {over_25*100:.1f}%.",
    })

    # BTTS
    btts_side = "Yes" if btts_prob >= 0.5 else "No"
    btts_p = max(btts_prob, 1 - btts_prob)
    btts_odds = odds.get("btts_yes" if btts_side == "Yes" else "btts_no", 1.8)
    btts_ev = _ev_pct(btts_p, btts_odds)
    btts_label = _classify_bet(btts_ev, btts_p)
    bets.append({
        "market": "BTTS",
        "selection": f"BTTS {btts_side} ({btts_p*100:.1f}%)",
        "odds": f"{btts_odds:.2f} ({_american(btts_odds)})",
        "prob": btts_p,
        "ev": btts_ev,
        "label": btts_label,
        "reason": f"Model projects BTTS Yes at {btts_prob*100:.1f}%.",
    })

    # Corners
    corner_line = odds.get("corner_line", 9.5)
    corner_over_prob = _parse_float(corners.get("over_95_prob", 0))
    corner_side = "Over" if corner_over_prob >= 0.5 else "Under"
    corner_p = max(corner_over_prob, 1 - corner_over_prob)
    corner_odds = odds.get("corners_over" if corner_side == "Over" else "corners_under", 1.85)
    corner_ev = _ev_pct(corner_p, corner_odds)
    corner_label = _classify_bet(corner_ev, corner_p)
    bets.append({
        "market": "Total Corners",
        "selection": f"{corner_side} {corner_line} ({corner_p*100:.1f}%)",
        "odds": f"{corner_odds:.2f} ({_american(corner_odds)})",
        "prob": corner_p,
        "ev": corner_ev,
        "label": corner_label,
        "reason": f"Model projects {corner_proj:.1f} corners; Over {corner_line} at {corner_over_prob*100:.1f}%.",
    })

    # Sort bets: strong bets first, then by EV descending
    order = {"STRONG BET": 0, "BET": 1, "LEAN": 2, "PASS": 3}
    bets.sort(key=lambda b: (order.get(b["label"], 9), -b["ev"]))

    return {
        "game": game,
        "preds": preds,
        "goals": goals,
        "corners": corners,
        "btts_prob": btts_prob,
        "corner_proj": corner_proj,
        "home_win": home_win,
        "draw": draw,
        "away_win": away_win,
        "hg": hg,
        "ag": ag,
        "tg": tg,
        "over_15": over_15,
        "over_25": over_25,
        "over_35": over_35,
        "bets": bets,
    }


def build_embed(match: dict, prediction: dict) -> dict:
    """Build a rich Discord embed for a single match."""
    a = build_analysis(match, prediction)
    odds = CONSENSUS_ODDS.get(match["name"], {})

    # Determine embed color from strongest bet
    strong_bets = [b for b in a["bets"] if b["label"] == "STRONG BET"]
    bet_bets = [b for b in a["bets"] if b["label"] == "BET"]
    if strong_bets:
        embed_color = 3066993  # Green
    elif bet_bets:
        embed_color = 10181046  # Light blue
    else:
        embed_color = 16776960  # Yellow

    fields = []

    # Match Info
    fields.append({
        "name": "Match Info",
        "value": (
            f"**{match['competition']}**\n"
            f"Stadium: {match['venue']}\n"
            f"Kickoff: {match['kickoff']}\n"
            f"Referee: {match['referee']}"
        ),
        "inline": False,
    })

    # Model Projection
    fields.append({
        "name": "Model Projection",
        "value": (
            f"**{match['home_team']} {a['hg']:.2f} - {a['ag']:.2f} {match['away_team']}**\n"
            f"Total Goals: **{a['tg']:.2f}**\n"
            f"{match['home_team']}: {a['home_win']*100:.1f}% | "
            f"Draw: {a['draw']*100:.1f}% | "
            f"{match['away_team']}: {a['away_win']*100:.1f}%"
        ),
        "inline": False,
    })

    # Goals Analysis
    fields.append({
        "name": "Goals Analysis",
        "value": (
            f"Over 1.5: {a['over_15']*100:.1f}% | "
            f"Over 2.5: {a['over_25']*100:.1f}% | "
            f"Over 3.5: {a['over_35']*100:.1f}%\n"
            f"BTTS Yes: {a['btts_prob']*100:.1f}% | "
            f"Corners: {a['corner_proj']:.1f}"
        ),
        "inline": False,
    })

    # Betting Recommendations
    bet_lines = []
    for bet in a["bets"]:
        ev_pct = bet["ev"] * 100
        emoji = {"STRONG BET": "STRONG BET", "BET": "BET", "LEAN": "LEAN", "PASS": "PASS"}.get(bet["label"], "?")
        bet_lines.append(
            f"**{emoji}** {bet['selection']} @ {bet['odds']}\n"
            f"   EV: {ev_pct:+.1f}% | {bet['reason']}"
        )
    fields.append({
        "name": "Betting Recommendations",
        "value": "\n".join(bet_lines),
        "inline": False,
    })

    # Consensus Odds
    odds_lines = [
        f"**1X2:** {match['home_team']} {odds.get('home_ml', 'N/A')} | "
        f"Draw {odds.get('draw_ml', 'N/A')} | "
        f"{match['away_team']} {odds.get('away_ml', 'N/A')}",
        f"**O/U 2.5:** Over {odds.get('over25', 'N/A')} / Under {odds.get('under25', 'N/A')} | "
        f"**BTTS:** Yes {odds.get('btts_yes', 'N/A')} / No {odds.get('btts_no', 'N/A')}",
        f"**Corners O/U {odds.get('corner_line', 'N/A')}:** Over {odds.get('corners_over', 'N/A')} / "
        f"Under {odds.get('corners_under', 'N/A')}",
    ]
    fields.append({
        "name": "Consensus Odds",
        "value": "\n".join(odds_lines),
        "inline": False,
    })

    # Strong Bets Summary
    strong = [b for b in a["bets"] if b["label"] == "STRONG BET"]
    if strong:
        strong_lines = [f"- {b['selection']} @ {b['odds']}" for b in strong]
        fields.append({
            "name": "TOP STRONG BETS",
            "value": "\n".join(strong_lines),
            "inline": False,
        })

    return {
        "title": f"FOOTBALL {match['home_team'].upper()} vs {match['away_team'].upper()}",
        "description": f"**{match['competition']}**",
        "color": embed_color,
        "fields": fields,
        "footer": {"text": "MultiSportPredict - Model-Driven Betting Guide"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def push_to_discord(embeds: list, dry_run: bool = False) -> bool:
    """Push embeds to Discord webhook."""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url or webhook_url == "None":
        logger.error("DISCORD_WEBHOOK_URL not set in .env file")
        return False

    success = True
    for embed in embeds:
        payload = {"embeds": [embed]}
        if dry_run:
            print(f"\n[DRY RUN] Payload for {embed['title']}:")
            print(json.dumps(payload, indent=2, default=str))
            continue

        try:
            resp = requests.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            if resp.status_code in (200, 204):
                logger.info("Pushed to Discord: %s", embed["title"])
            else:
                logger.error("Discord push failed: HTTP %s - %s", resp.status_code, resp.text[:200])
                success = False
        except Exception as exc:
            logger.error("Error pushing to Discord: %s", exc)
            success = False

    return success


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run 2 soccer matches through the model and push to Discord."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the Discord payload instead of posting",
    )
    args = parser.parse_args()

    logger.info("Initializing SoccerPredictor...")
    predictor = SoccerPredictor(league="default")

    embeds = []

    for match in MATCHES:
        match_name = match["name"]
        logger.info("Running inference for %s...", match_name)
        print("=" * 70)
        print(f"MATCH: {match_name}")
        print("=" * 70)

        try:
            # Pass only the model-override kwargs (skip the metadata keys)
            override_kwargs = {
                k: v
                for k, v in match.items()
                if k.startswith(("home_", "away_"))
                and k not in ("home_team", "away_team")
            }

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

            # Print summary
            game = prediction.get("game", {})
            print(f"  Projected: {match['home_team']} {game.get('projected_home_goals', 0):.2f} - "
                  f"{game.get('projected_away_goals', 0):.2f} {match['away_team']}")
            print(f"  Home Win: {game.get('home_win_prob', 0)*100:.1f}% | "
                  f"Draw: {game.get('draw_prob', 0)*100:.1f}% | "
                  f"Away Win: {game.get('away_win_prob', 0)*100:.1f}%")

            # Build embed
            embed = build_embed(match, prediction)
            embeds.append(embed)

        except Exception as e:
            logger.error("Failed to process %s: %s", match_name, e, exc_info=True)
            print(f"[ERROR] {match_name}: {e}")

    # Push to Discord
    if embeds:
        ok = push_to_discord(embeds, dry_run=args.dry_run)
        if ok:
            logger.info("Successfully pushed %d match embed(s) to Discord.", len(embeds))
        else:
            logger.warning("Some embeds may not have been delivered.")
    else:
        logger.error("No embeds to push. Check errors above.")


if __name__ == "__main__":
    main()
