#!/usr/bin/env python
"""
Run two live slate matches through SoccerPredictor and push recommended
results to Discord in rich table format.

Match slate (Sunday, Aug 16, 2026):
  1. Pumas UNAM vs Querétaro FC  — Liga MX, 2:00 PM ET  (IN PROGRESS)
  2. Chicago Fire vs Portland Timbers — MLS, 7:00 PM ET / 23:00 UTC

Maps user-supplied seed data / market lean into the SoccerPredictor's
per-team override coefficients, then renders the model output as:

  - Console: rich prediction tables (terminal)
  - Discord: one rich embedded message per match with monospace
    table-formatted market rows (Moneyline / Total / BTTS / Corners)

Usage:
    python run_pumas_queretaro_chicago_discord.py                # console only
    python run_pumas_queretaro_chicago_discord.py --push-discord # + Discord
    python run_pumas_queretaro_chicago_discord.py --dry-run      # print payload
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on sys.path for imports
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv

from models.soccer_predictor import SoccerPredictor

load_dotenv()

# Fix Windows console encoding for emoji / unicode output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("run_pumas_queretaro_chicago")

# ---------------------------------------------------------------------------
# COLOR / EMBED CONSTANTS
# ---------------------------------------------------------------------------
COLOR_STRONG = 3066993   # Green
COLOR_BET    = 10181046  # Blue
COLOR_LEAN   = 15844367  # Gold
COLOR_NEUTRAL = 9807270  # Gray

# ---------------------------------------------------------------------------
# MATCH DEFINITIONS — Seed data mapped to model coefficients
# ---------------------------------------------------------------------------
# The SoccerPredictor.predict() method accepts per-team override kwargs:
#   home_xg_for, home_xg_against, home_shots, home_sot, home_goals_for,
#   home_goals_against, home_clean_sheets, home_tempo, home_width_crossing,
#   home_final_third_pressure, home_missing_*, etc. (same for away).
#
# Seed data is current as of Sun, Aug 16, 2026.
# ---------------------------------------------------------------------------

MATCHES = [
    {
        # ------------------------------------------------------------------
        # 1. PUMAS UNAM vs QUERÉTARO FC — Liga MX (LIVE / IN PROGRESS)
        # ------------------------------------------------------------------
        "name": "Pumas UNAM vs Querétaro FC",
        "home_team": "Pumas UNAM",
        "away_team": "Querétaro FC",
        "league": "Liga MX",
        "kickoff": "Sun, Aug 16 • 2:00 PM ET",
        "venue": "Estadio Olímpico Universitario, Mexico City",
        "status_tag": "🔴 LIVE — IN PROGRESS (elevated possession: Pumas ~65%)",
        "market_line": 0.0,
        "market_total": 2.5,
        # Pumas: strong home side at altitude, but missing José Macías
        # (attacker) and Sebastián Córdova (creator). Juninho clinical;
        # Morales distributes in a 3-4-2-1 look. Capped xG profile with
        # the two creative/attacking absences — supports a ~1-0 style
        # modal scoreline and a split total-goals market.
        "home_xg_for": 1.35,
        "home_xg_against": 1.10,
        "home_shots": 12.0,
        "home_sot": 3.8,
        "home_goals_for": 1.70,
        "home_goals_against": 0.95,
        "home_clean_sheets": 3,
        "home_missing_attacker": 1,
        "home_missing_creator": 1,
        "home_tempo": 0.60,
        "home_width_crossing": 0.55,
        "home_final_third_pressure": 0.58,
        # Querétaro: Ávila sharp (3 goals), but missing key pieces
        # (Coronel / Villanueva). Modest away xG profile — 1-0 Pumas is
        # the model modal score, with 1-1 a prominent draw result.
        "away_xg_for": 0.95,
        "away_xg_against": 1.45,
        "away_shots": 9.5,
        "away_sot": 2.9,
        "away_goals_for": 1.25,
        "away_goals_against": 1.45,
        "away_clean_sheets": 2,
        "away_missing_attacker": 1,
        "away_missing_creator": 1,
        "away_tempo": 0.40,
        "away_width_crossing": 0.48,
        "away_final_third_pressure": 0.44,
        # Market context (from the user's slate)
        "odds": {
            "moneyline": "Pumas -123/-125 | Draw +265 | Qro +305/+308",
            "total": "Over -143 / Under +107",
            "corners": "O8: 67.5% | O9: 56.1% | O10.5: 44.6%",
        },
        "recommendations": [
            {
                "market": "Moneyline",
                "selection": "Pumas UNAM ML",
                "prob_key": "home_win",
                "rec": "BET",
                "note": "Priced -123/-125 — lean but not a major bargain; Pumas close favorites at altitude.",
            },
            {
                "market": "Total 2.5",
                "selection": "Split (Modal 1-0)",
                "prob_key": "over_25",
                "rec": "PASS",
                "note": "Book juiced to Over (-143) but model score profile is low-scoring; don't combine O2.5 + BTTS.",
            },
            {
                "market": "BTTS",
                "selection": "Lean No / cautious pass",
                "prob_key": "btts",
                "rec": "PASS",
                "note": "Model modal 1-0 — top score does not support a strong BTTS Yes.",
            },
            {
                "market": "Corners",
                "selection": "Over 8.5",
                "prob_key": "corners_85",
                "rec": "BET",
                "note": "Model projects elevated combined corners (~10-11); O8.5 is the cleaner derivative prop.",
            },
        ],
    },
    {
        # ------------------------------------------------------------------
        # 2. CHICAGO FIRE vs PORTLAND TIMBERS — MLS, 7:00 PM ET / 23:00 UTC
        # ------------------------------------------------------------------
        "name": "Chicago Fire FC vs Portland Timbers",
        "home_team": "Chicago Fire FC",
        "away_team": "Portland Timbers",
        "league": "MLS",
        "kickoff": "Sun, Aug 16 • 7:00 PM ET (23:00 UTC)",
        "venue": "Soldier Field, Chicago, IL",
        "status_tag": "⏳ KICKOFF: 7:00 PM ET / 23:00 UTC",
        "market_line": 0.0,
        "market_total": 2.5,
        # Chicago: four-game winning streak across competitions, strong
        # at Soldier Field (6-3-0). Zinckernagel (5g/8a) runs the attack
        # and Cuypers (9g) converts — 2.3 goals per match pace.
        # Concede 1.8/match (leaky), which powers the BTTS Yes angle.
        # xG profile pushes the market's ~61% home-win estimate.
        "home_xg_for": 2.20,
        "home_xg_against": 1.35,
        "home_shots": 14.5,
        "home_sot": 5.4,
        "home_goals_for": 2.30,
        "home_goals_against": 1.75,
        "home_clean_sheets": 1,
        "home_tempo": 0.62,
        "home_width_crossing": 0.58,
        "home_final_third_pressure": 0.62,
        # Portland: Kevin Kelsy (9 goals) leads a dangerous counter, but
        # road form is weak (2-6-1). New tactical guidance under Cifuentes.
        "away_xg_for": 1.25,
        "away_xg_against": 1.70,
        "away_shots": 10.5,
        "away_sot": 3.5,
        "away_goals_for": 1.60,
        "away_goals_against": 1.95,
        "away_clean_sheets": 1,
        "away_tempo": 0.35,
        "away_width_crossing": 0.46,
        "away_final_third_pressure": 0.48,
        # Market context (from slate)
        "odds": {
            "moneyline": "Chicago ~1.53 / -190 | Draw 4.75 | Portland 5.25",
            "fair": "BTTS Yes 1.44 / No 2.80",
            "total": "O/U price not reliably surfaced — price-check before entry",
        },
        "recommendations": [
            {
                "market": "Moneyline",
                "selection": "Chicago Fire ML",
                "prob_key": "home_win",
                "rec": "BET",
                "note": "Home favorite at ~1.53 (-190); market-derived model win prob ~62-66%.",
            },
            {
                "market": "BTTS",
                "selection": "BTTS Yes",
                "prob_key": "btts",
                "rec": "BET",
                "note": "Priced at 1.44; Chicago concedes 1.8/match while both attacks are potent -> best-supported secondary angle.",
            },
            {
                "market": "Total 2.5",
                "selection": "Over 2.5",
                "prob_key": "over_25",
                "rec": "LEAN",
                "note": "Chicago avg 2.3 scored / tev 2.0 conceded; pre-match total lean Over, but verify live O/U line.",
            },
            {
                "market": "Corners",
                "selection": "Over 9.5 (if line ≤9.5)",
                "prob_key": "corners_95",
                "rec": "PASS",
                "note": "No trustworthy line surfaced — only play pre-match if 9.5 or lower is offered.",
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _parse_float(value, default: float = 0.0) -> float:
    """Safe float parse."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_bet_table(match: dict, prediction: dict) -> str:
    """
    Build a monospace table of recommended bets from the model output.

    Used both in the console printout and inside a Discord code-block so the
    table aligns on proportional-width devices.
    """
    game = prediction.get("game", {})
    goals = prediction.get("goals_analysis", {})
    corners = prediction.get("corners_analysis", {})
    btts_prob = _parse_float(prediction.get("btts_probability", 0)) * 100

    prob_lookup = {
        "home_win": _parse_float(game.get("home_win_prob", 0)) * 100,
        "draw": _parse_float(game.get("draw_prob", 0)) * 100,
        "away_win": _parse_float(game.get("away_win_prob", 0)) * 100,
        "over_25": _parse_float(goals.get("over_25_prob", 0)) * 100,
        "btts": btts_prob,
        "corners_85": _parse_float(corners.get("over_85_prob", 0)) * 100,
        "corners_95": _parse_float(corners.get("over_95_prob", 0)) * 100,
        "corners_105": _parse_float(corners.get("over_105_prob", 0)) * 100,
    }

    lines = ["```md", "| MARKET | SELECTION | PROB | REC |", "|--------|-----------|------|-----|"]
    for rec in match["recommendations"]:
        prob = prob_lookup.get(rec["prob_key"], 0.0)
        lines.append(
            f"| {rec['market']:<8} | {rec['selection']:<10} | {prob:5.1f}% | {rec['rec']:<4} |"
        )
    lines.append("```")

    # Notes appended underneath (not in the block table)
    notes = []
    for rec in match["recommendations"]:
        notes.append(f"**{rec['market']}** → {rec['note']}")
    return "\n".join(lines) + "\n\n" + "\n".join(notes)


def build_prob_board(match: dict, prediction: dict) -> str:
    """Build a table of the raw model probabilities for 1X2 / goals / BTTS / corners."""
    game = prediction.get("game", {})
    goals = prediction.get("goals_analysis", {})
    corners = prediction.get("corners_analysis", {})
    btts_prob = _parse_float(prediction.get("btts_probability", 0)) * 100

    home_win = _parse_float(game.get("home_win_prob", 0)) * 100
    draw = _parse_float(game.get("draw_prob", 0)) * 100
    away_win = _parse_float(game.get("away_win_prob", 0)) * 100
    hg = _parse_float(game.get("projected_home_goals", 0))
    ag = _parse_float(game.get("projected_away_goals", 0))
    total = _parse_float(game.get("projected_total_goals", 0))

    over_15 = _parse_float(goals.get("over_15_prob", 0)) * 100
    over_25 = _parse_float(goals.get("over_25_prob", 0)) * 100
    over_35 = _parse_float(goals.get("over_35_prob", 0)) * 100
    corners_proj = _parse_float(corners.get("projection", 0))
    corners_85 = _parse_float(corners.get("over_85_prob", 0)) * 100

    board = (
        "```md\n"
        "### MATCH MODEL BOARD ###\n"
        f"{match['home_team']:<16} vs {match['away_team']}\n"
        "------------------------------\n"
        f"Home Win   : {home_win:5.1f}%\n"
        f"Draw       : {draw:5.1f}%\n"
        f"Away Win   : {away_win:5.1f}%\n"
        f"Projected  : {hg:.2f} - {ag:.2f}  (Total {total:.2f})\n"
        "------------------------------\n"
        f"Over 1.5   : {over_15:5.1f}%\n"
        f"Over 2.5   : {over_25:5.1f}%\n"
        f"Over 3.5   : {over_35:5.1f}%\n"
        f"BTTS Yes   : {btts_prob:5.1f}%\n"
        "------------------------------\n"
        f"Corners    : {corners_proj:.1f} total\n"
        f"Over 8.5   : {corners_85:5.1f}%\n"
        "```"
    )
    return board


def build_embed(match: dict, prediction: dict) -> dict:
    """
    Build a rich Discord embed for a single match with table-formatted
    market board and recommended-bets section.
    """
    color = COLOR_STRONG if any(r["rec"] == "BET" for r in match["recommendations"]) else COLOR_NEUTRAL
    if not any(r["rec"] == "BET" for r in match["recommendations"]) and any(r["rec"] == "LEAN" for r in match["recommendations"]):
        color = COLOR_LEAN

    embed = {
        "title": f"⚽ {match['home_team'].upper()} vs {match['away_team'].upper()}",
        "description": (
            f"**{match['league']}** • {match['kickoff']}\n"
            f"{match['status_tag']}\n"
            f":stadium: {match['venue']}"
        ),
        "color": color,
        "fields": [
            {
                "name": "📊 Model Board",
                "value": build_prob_board(match, prediction),
                "inline": True,
            },
            {
                "name": "🏆 Recommended Bets",
                "value": build_bet_table(match, prediction),
                "inline": True,
            },
            {
                "name": "💱 Market Context",
                "value": (
                    f"**ML:** {match['odds']['moneyline']}\n"
                    f"**Total 2.5:** {match['odds'].get('fair', match['odds'].get('total', 'N/A'))}\n"
                    f"**Corners:** {match['odds'].get('corners', 'N/A')}"
                ),
                "inline": False,
            },
        ],
        "footer": {
            "text": "MultiSportPredict • Live Slate — Aug 16, 2026"
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return embed


def build_discord_payload(embed: dict) -> dict:
    """Wrap an embed dict into a Discord webhook payload."""
    return {"embeds": [embed]}


def push_payload_to_discord(payload: dict, dry_run: bool = False) -> bool:
    """POST a payload to the webhook (or print it in dry-run mode)."""
    import requests as requests_lib

    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url or webhook_url == "None":
        logger.error("DISCORD_WEBHOOK_URL not set in .env")
        return False

    if dry_run:
        print(json.dumps(payload, indent=2, default=str))
        return True

    try:
        resp = requests_lib.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        if resp.status_code in (200, 204):
            logger.info("✓ Discord embed pushed successfully.")
            return True
        logger.error("Discord push failed: status=%s body=%s", resp.status_code, resp.text)
        return False
    except Exception as exc:  # noqa: BLE001
        logger.error("Discord push error: %s", exc)
        return False


# ---------------------------------------------------------------------------
# CONSOLE FORMATTING
# ---------------------------------------------------------------------------

def format_prediction_console(match: dict, prediction: dict) -> str:
    """Pretty console output for a single match."""
    game = prediction.get("game", {})
    goals = prediction.get("goals_analysis", {})
    corners = prediction.get("corners_analysis", {})
    btts_prob = _parse_float(prediction.get("btts_probability", 0)) * 100

    home_win = _parse_float(game.get("home_win_prob", 0)) * 100
    draw = _parse_float(game.get("draw_prob", 0)) * 100
    away_win = _parse_float(game.get("away_win_prob", 0)) * 100
    hg = _parse_float(game.get("projected_home_goals", 0))
    ag = _parse_float(game.get("projected_away_goals", 0))
    total = _parse_float(game.get("projected_total_goals", 0))

    lines = [
        "=" * 70,
        f"MATCH: {match['name']} ({match['league']}) — {match['status_tag']}",
        "-" * 70,
        f"  Kickoff: {match['kickoff']}",
        f"  Venue:   {match['venue']}",
        f"  Projected Score: {match['home_team']} {hg:.2f} - {ag:.2f} {match['away_team']}",
        f"  Projected Total: {total:.2f}",
        "",
        "  1X2 Probabilities:",
        f"    Home: {home_win:.1f}% | Draw: {draw:.1f}% | Away: {away_win:.1f}%",
        "",
        "  Goals Analysis:",
        f"    Over 1.5: {goals.get('over_15_prob', 0) * 100:.1f}%",
        f"    Over 2.5: {goals.get('over_25_prob', 0) * 100:.1f}%",
        f"    Over 3.5: {goals.get('over_35_prob', 0) * 100:.1f}%",
        f"    BTTS Yes: {btts_prob:.1f}%",
        f"    Corners:  {corners.get('projection', 0):.1f} (O8.5: {corners.get('over_85_prob', 0) * 100:.1f}%)",
        "",
        "  🏆 Recommended Bets:",
    ]
    for rec in match["recommendations"]:
        lines.append(f"    - {rec['market']}: {rec['selection']} — {rec['rec']}")
    lines.append("=" * 72)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run Pumas-Querétaro (Liga MX) and Chicago-Portland (MLS) "
                    "through the model and push rich tables to Discord."
    )
    parser.add_argument(
        "--push-discord",
        action="store_true",
        help="Push each rich embed to Discord via webhook",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the Discord payload instead of posting",
    )
    args = parser.parse_args()

    predictor = SoccerPredictor(league="default")

    results = []
    pushed_count = 0

    for match in MATCHES:
        match_name = match["name"]
        logger.info("Running inference for %s...", match_name)

        # Pass only the model-override kwargs (skip metadata keys)
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
            out_path = out_dir / (
                f"{match['home_team'].replace(' ', '_').lower()}_vs_"
                f"{match['away_team'].replace(' ', '_').lower()}.json"
            )
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(prediction, f, indent=2, default=str)
            logger.info("Saved JSON to %s", out_path)

            # Console output
            print(format_prediction_console(match, prediction))
            print()
            result_json = json.dumps(prediction, indent=2, default=str)
            print(result_json)
            print("=" * 72)
            print()

            results.append({"match": match, "prediction": prediction})

            # Discord push
            if args.push_discord or args.dry_run:
                embed = build_embed(match, prediction)
                payload = build_discord_payload(embed)
                ok = push_payload_to_discord(payload, dry_run=args.dry_run)
                if ok:
                    pushed_count += 1
                tag = "DRY-RUN PRINT" if args.dry_run else "PUSH"
                logger.info("[%s] %s", tag, match_name)

        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to process %s: %s", match_name, exc, exc_info=True)
            print(f"[ERROR] {match_name}: {exc}")

    # Wrap-up summary
    print()
    print("=" * 100)
    print("SLATE SUMMARY — RECOMMENDED RESULTS")
    print("=" * 100)
    for item in results:
        match = item["match"]
        best = next(
            (r for r in match["recommendations"] if r["rec"] == "BET"),
            match["recommendations"][-1],
        )
        print(
            f"  {match['name']:<30} -> "
            f"{best['market']}: {best['selection']} [{best['rec']}]"
        )
    print("=" * 100)

    logger.info(
        "Batch complete. %d/2 matches processed, %d Discord pushes.",
        len(results),
        pushed_count,
    )


if __name__ == "__main__":
    main()