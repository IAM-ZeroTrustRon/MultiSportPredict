#!/usr/bin/env python
"""
Batch Tennis Predictor for MultiSportPredict
=============================================
Runs Elo-based tennis match predictions and pushes results to Discord
via the shared discord_integration module's dedicated recommendations webhook.

Features:
- Surface-specific Elo ratings
- Moneyline / recommendation logic
- Dedicated Discord recommendations channel push
- Dry-run mode for testing

Usage:
    python batch_tennis.py                         # dry run (print predictions)
    python batch_tennis.py --push                  # live push to Discord
    python batch_tennis.py --push --dry-run        # print payload only, no post
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timezone

from dotenv import load_dotenv

# Ensure the project root is on sys.path for imports
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Load environment variables for local execution
load_dotenv('c:/MultiSportPredict/.env')

# MultiSportPredict local imports
from models.tennis_predictor import predict_tennis_match
from discord_integration import push_recommendation_to_discord

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("batch_tennis")


# ---------------------------------------------------------------------------
# MATCH DEFINITIONS
# ---------------------------------------------------------------------------
# Each match can include optional market odds; omit them to get raw model probs.
# ---------------------------------------------------------------------------
TENNIS_MATCHES = [
    {
        "home_player": "Terence Atmane",
        "away_player": "Alejandro Tabilo",
        "tournament": "Washington ATP",
        "surface": "hard",
        "best_of_5": False,
        "round_name": "R16",
        "market_home_odds": "-113",
        "market_away_odds": "-108",
    },
]


# ---------------------------------------------------------------------------
# UTILITY
# ---------------------------------------------------------------------------

def _american_to_decimal(odds: str) -> float:
    """Convert American odds string to decimal probability (implied)."""
    v = int(odds.replace("+", ""))
    if v < 0:
        return round(1 + (100 / abs(v)), 2)
    return round(1 + (v / 100), 2)


def _market_implied_prob(market_home_odds: str, market_away_odds: str) -> float:
    """Calculate market-implied win probability for the home player (no vig)."""
    home_dec = _american_to_decimal(market_home_odds)
    away_dec = _american_to_decimal(market_away_odds)
    # Remove vig: assume equal margin
    total_implied = (1 / home_dec) + (1 / away_dec)
    return (1 / home_dec) / total_implied if total_implied > 0 else 0.5


# ---------------------------------------------------------------------------
# FORMATTING
# ---------------------------------------------------------------------------

def format_tennis_prediction(result: dict) -> str:
    """Format a tennis prediction result into a human-readable string."""
    ml = result.get("moneyline", {})
    match_str = result.get("match", "N/A")
    parts = match_str.split(" vs ") if " vs " in match_str else [match_str, ""]

    lines = [
        f"Match: {match_str}",
        f"  Tournament: {result.get('tournament', 'N/A')}",
        f"  Surface: {result.get('surface', 'N/A')}",
        f"  Model Type: {result.get('model_type', 'N/A')}",
        f"  Home Win Prob: {ml.get('home_win_prob', 0):.1%}",
        f"  Away Win Prob: {ml.get('away_win_prob', 0):.1%}",
        f"  Confidence: {ml.get('confidence', 0):.1f}%",
        f"  Edge: {ml.get('edge_pct', 0):+.1f}%",
        f"  Recommendation: {ml.get('recommendation', 'PASS')}",
        f"  Lean: {ml.get('lean', 'N/A')}",
    ]

    # Add set distribution info if available
    sets = result.get("sets", {})
    if sets:
        lines.append(f"  Over 3.5 Sets Prob: {sets.get('over_35_prob', 0):.1%}")
        lines.append(f"  Fav Spread Prob: {sets.get('fav_spread_prob', 0):.1%}")

    # Add notes
    notes = result.get("notes", [])
    for note in notes:
        lines.append(f"  {note}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CORE FUNCTIONS
# ---------------------------------------------------------------------------


def push_rich_tennis_to_discord(
    result: dict,
    match: dict,
    dry_run: bool = False,
) -> bool:
    """
    Push a 4-embed rich tennis prediction to Discord.

    Embeds:
        1. Main Analysis  — overview, Elo ratings, win probs
        2. Match Props    — moneyline, sets O/U, spread, total games
        3. Player A Props — surface Elo, DR, market value
        4. Player B Props — same for away player
    """
    import requests as _requests
    import json

    webhook_url = os.getenv("DISCORD_RECOMMENDATIONS_WEBHOOK_URL") or os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url or webhook_url == "None":
        logger.warning("No Discord webhook URL configured; skipping rich push.")
        return False

    ml = result.get("moneyline", {})
    sets = result.get("sets", {})
    total_g = result.get("total_games", {})
    dom_ratio = result.get("dominance_ratio", {})
    elo_ratings = result.get("elo_ratings", {})
    match_counts = result.get("match_counts", {})

    home_player = match["home_player"]
    away_player = match["away_player"]
    tournament   = match.get("tournament", "Tennis")
    surface      = match.get("surface", "hard").capitalize()
    market_home  = match.get("market_home_odds", "N/A")
    market_away  = match.get("market_away_odds", "N/A")

    home_prob  = ml.get("home_win_prob", 0.5)
    away_prob  = ml.get("away_win_prob", 0.5)
    confidence = ml.get("confidence", 0.0)
    edge       = ml.get("edge_pct", 0.0)
    lean       = ml.get("lean", "N/A")
    rec_full   = ml.get("recommendation", "PASS")
    home_fair  = ml.get("home_fair_odds", "N/A")
    away_fair  = ml.get("away_fair_odds", "N/A")

    over35     = sets.get("over_35_prob", 0.0)
    sets_ou_rec = sets.get("recommendation_sets_ou", "N/A")
    fav_spread = sets.get("fav_spread_prob", 0.0)
    spread_rec  = sets.get("recommendation_spread", "N/A")
    tg_line     = total_g.get("line", 22.5)
    tg_over_p   = total_g.get("over_prob", 0.0)
    tg_rec      = total_g.get("recommendation", "N/A")

    home_elo  = elo_ratings.get(home_player, 1500)
    away_elo  = elo_ratings.get(away_player, 1500)
    home_mc   = match_counts.get(home_player, 0)
    away_mc   = match_counts.get(away_player, 0)
    home_dr   = dom_ratio.get(home_player, 1.0)
    away_dr   = dom_ratio.get(away_player, 1.0)

    # Colour logic
    GREEN  = 3066993
    BLUE   = 3447003
    PURPLE = 10181046
    ORANGE = 15105570
    GRAY   = 9807270

    def _rec_icon(r: str) -> str:
        r_up = r.upper()
        if "BET" in r_up:     return "✅"
        if "LEAN" in r_up:    return "⚠️"
        if "SLIGHT" in r_up:  return "⚠️"
        return "❌"

    def _conf_color(c: float) -> int:
        if c >= 65: return GREEN
        if c >= 57: return ORANGE
        return GRAY

    # ── Embed 1: Main Analysis ──────────────────────────────────────────
    e1 = {
        "title": f"🎾 {home_player} vs {away_player}",
        "description": f"**{tournament}** | Surface: **{surface}** | Format: Best of 3",
        "color": _conf_color(confidence),
        "fields": [
            {
                "name": "📊 Win Probability",
                "value": (
                    f"**{home_player}:** {home_prob:.1%} (Fair: {home_fair})\n"
                    f"**{away_player}:** {away_prob:.1%} (Fair: {away_fair})"
                ),
                "inline": False,
            },
            {
                "name": "🎯 Model Lean",
                "value": f"**{lean}**",
                "inline": True,
            },
            {
                "name": "📈 Confidence",
                "value": f"**{confidence:.0f}%**",
                "inline": True,
            },
            {
                "name": "💡 Edge vs Market",
                "value": f"**{edge:+.1f}%**",
                "inline": True,
            },
            {
                "name": "⚡ Elo Ratings (Surface)",
                "value": (
                    f"{home_player}: **{home_elo:.0f}** ({home_mc} matches)\n"
                    f"{away_player}: **{away_elo:.0f}** ({away_mc} matches)"
                ),
                "inline": False,
            },
            {
                "name": "📋 Recommendation",
                "value": f"{_rec_icon(rec_full)} {rec_full}",
                "inline": False,
            },
        ],
        "footer": {"text": "MultiSportPredict Tennis Engine | Elo Surface Model"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # ── Embed 2: Match Props ─────────────────────────────────────────────
    ml_bet_val = f"**{home_player}** {market_home} → fair {home_fair}"
    ml_dog_val = f"**{away_player}** {market_away} → fair {away_fair}"

    def _prop_icon(p: float, threshold: float = 0.55) -> str:
        return "✅" if p >= threshold else ("⚠️" if p >= 0.50 else "❌")

    e2 = {
        "title": "📋 Match Props — Betting Markets",
        "color": BLUE,
        "fields": [
            {
                "name": "💵 Moneyline",
                "value": (
                    f"{_prop_icon(home_prob)} {ml_bet_val} → {home_prob:.1%}\n"
                    f"{_prop_icon(away_prob)} {ml_dog_val} → {away_prob:.1%}"
                ),
                "inline": False,
            },
            {
                "name": f"📦 Sets O/U 1.5 (Best of 3)",
                "value": (
                    f"Over 1.5 Sets: **{over35:.1%}**\n"
                    f"{_prop_icon(over35, 0.55)} {sets_ou_rec}"
                ),
                "inline": True,
            },
            {
                "name": "🎯 Set Spread (-1.5)",
                "value": (
                    f"Fav covers -1.5: **{fav_spread:.1%}**\n"
                    f"{_prop_icon(fav_spread, 0.52)} {spread_rec}"
                ),
                "inline": True,
            },
            {
                "name": f"🔢 Total Games O/U {tg_line}",
                "value": (
                    f"Over prob: **{tg_over_p:.1%}**\n"
                    f"{_prop_icon(tg_over_p, 0.53)} Rec: **{tg_rec}** {tg_line}"
                ),
                "inline": False,
            },
            {
                "name": "🔥 Strong Plays",
                "value": "\n".join([
                    f"{_prop_icon(home_prob)} **ML {lean}** — {max(home_prob, away_prob):.1%} win prob",
                    f"{_prop_icon(over35, 0.55)} **Sets O/U** — {sets_ou_rec}",
                    f"{_prop_icon(fav_spread, 0.52)} **Spread** — {spread_rec}",
                ]),
                "inline": False,
            },
        ],
        "footer": {"text": f"Market odds: {home_player} {market_home} / {away_player} {market_away}"},
    }

    # ── Embed 3: Player A Props ──────────────────────────────────────────
    def _dr_label(dr: float) -> str:
        if dr >= 1.20: return "Elite (1.20+)"
        if dr >= 1.10: return "Strong (1.10-1.19)"
        if dr >= 1.00: return "Average (1.00-1.09)"
        return f"Below Avg (<1.00)"

    def _elo_tier(elo: float) -> str:
        if elo >= 2200: return "World Class"
        if elo >= 2000: return "Top 20"
        if elo >= 1800: return "Top 50"
        if elo >= 1600: return "Top 100"
        return "Challenger Level"

    e3 = {
        "title": f"🟢 {home_player} — Player Profile",
        "color": GREEN,
        "fields": [
            {
                "name": "📊 Surface Elo",
                "value": f"**{home_elo:.0f}** — {_elo_tier(home_elo)}\n({home_mc} recorded matches)",
                "inline": True,
            },
            {
                "name": "⚡ Dominance Ratio",
                "value": f"**{home_dr:.3f}** — {_dr_label(home_dr)}",
                "inline": True,
            },
            {
                "name": "🎯 Win Probability",
                "value": f"**{home_prob:.1%}** | Fair odds: {home_fair}",
                "inline": True,
            },
            {
                "name": "📈 Market Assessment",
                "value": (
                    f"Market: **{market_home}**\n"
                    f"Model fair: **{home_fair}**\n"
                    f"Edge: **{edge:+.1f}%** vs market"
                ),
                "inline": False,
            },
            {
                "name": "🎾 Projected Performance",
                "value": (
                    f"Expected sets won: **{home_prob * 2:.1f}**\n"
                    f"Set wins O1.5: **{_prop_icon(fav_spread if lean == home_player else 1 - fav_spread, 0.52)}** "
                    f"{(fav_spread if lean == home_player else 1 - fav_spread):.1%}\n"
                    f"Straight-sets win: **{(fav_spread if lean == home_player else 1 - fav_spread):.1%}**"
                ),
                "inline": False,
            },
        ],
        "footer": {"text": f"Surface: {surface} | {tournament}"},
    }

    # ── Embed 4: Player B Props ──────────────────────────────────────────
    e4 = {
        "title": f"🔵 {away_player} — Player Profile",
        "color": PURPLE,
        "fields": [
            {
                "name": "📊 Surface Elo",
                "value": f"**{away_elo:.0f}** — {_elo_tier(away_elo)}\n({away_mc} recorded matches)",
                "inline": True,
            },
            {
                "name": "⚡ Dominance Ratio",
                "value": f"**{away_dr:.3f}** — {_dr_label(away_dr)}",
                "inline": True,
            },
            {
                "name": "🎯 Win Probability",
                "value": f"**{away_prob:.1%}** | Fair odds: {away_fair}",
                "inline": True,
            },
            {
                "name": "📈 Market Assessment",
                "value": (
                    f"Market: **{market_away}**\n"
                    f"Model fair: **{away_fair}**\n"
                    f"Away edge: **{-edge:+.1f}%** vs market"
                ),
                "inline": False,
            },
            {
                "name": "🎾 Projected Performance",
                "value": (
                    f"Expected sets won: **{away_prob * 2:.1f}**\n"
                    f"Set wins O1.5: **{_prop_icon(fav_spread if lean == away_player else 1 - fav_spread, 0.52)}** "
                    f"{(fav_spread if lean == away_player else 1 - fav_spread):.1%}\n"
                    f"Straight-sets win: **{(fav_spread if lean == away_player else 1 - fav_spread):.1%}**"
                ),
                "inline": False,
            },
        ],
        "footer": {
            "text": f"MultiSportPredict | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        },
    }

    payload = {"embeds": [e1, e2, e3, e4]}

    if dry_run:
        print("[DRY RUN] Rich tennis Discord payload:")
        print(json.dumps(payload, indent=2, default=str))
        return True

    try:
        resp = _requests.post(webhook_url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
        if resp.status_code == 204:
            logger.info("✓ Rich tennis analysis pushed to Discord: %s vs %s", home_player, away_player)
            return True
        else:
            logger.error("Discord push failed (%d): %s", resp.status_code, resp.text)
            return False
    except Exception as exc:
        logger.error("Discord request error: %s", exc)
        return False


def run_tennis_batch(dry_run: bool = False, push: bool = False):
    """
    Run batch predictions for all defined tennis matches.

    Args:
        dry_run: If True, print payloads without actually posting to Discord
        push: If True, push results to Discord via recommendations webhook
    """
    # Check webhook availability if pushing
    recommendations_webhook = os.getenv("DISCORD_RECOMMENDATIONS_WEBHOOK_URL")
    if push and (not recommendations_webhook or recommendations_webhook == "None"):
        logger.warning(
            "DISCORD_RECOMMENDATIONS_WEBHOOK_URL not set. "
            "Falling back to dry-run mode."
        )
        dry_run = True
        push = False

    print("Starting tennis batch prediction run...")
    print("=" * 60)

    for match in TENNIS_MATCHES:
        home_player = match["home_player"]
        away_player = match["away_player"]
        match_name = f"{home_player} vs {away_player}"
        logger.info("Running inference for %s...", match_name)

        try:
            # Calculate market probability if odds are available
            market_prob = None
            if match.get("market_home_odds") and match.get("market_away_odds"):
                market_prob = _market_implied_prob(
                    match["market_home_odds"], match["market_away_odds"]
                )

            # Run prediction
            result = predict_tennis_match(
                home_player=home_player,
                away_player=away_player,
                surface=match.get("surface", "hard"),
                best_of_5=match.get("best_of_5", True),
                tournament=match.get("tournament"),
                round_name=match.get("round_name"),
                market_prob=market_prob,
                market_home_odds=match.get("market_home_odds"),
                market_away_odds=match.get("market_away_odds"),
            )

            # Print formatted output to console
            print(format_tennis_prediction(result))
            print("-" * 45)

            # Push to Discord (rich 4-embed format)
            if push and not dry_run:
                push_rich_tennis_to_discord(result=result, match=match, dry_run=False)
                logger.info("Pushed %s to Discord.", match_name)
            elif dry_run and push:
                push_rich_tennis_to_discord(result=result, match=match, dry_run=True)

        except Exception as e:
            logger.error("Inference failed for %s: %s", match_name, e, exc_info=True)
            print(f"[ERROR] Inference failed for {match_name}: {e}")

        print("-" * 45)

    print(
        f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}] "
        f"[INFO] Tennis batch run complete."
    )


# ---------------------------------------------------------------------------
# CLI ENTRY POINT
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Batch tennis prediction runner with Discord push."
    )
    parser.add_argument(
        "--push", "-p",
        action="store_true",
        help="Push predictions to Discord via recommendations webhook",
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        default=False,
        help="Run in dry-run mode (print payloads, no actual post).",
    )
    parser.add_argument(
        "--no-dry-run", "-nd",
        action="store_false",
        dest="dry_run",
        help="Disable dry-run mode (actually post to Discord when --push is set)",
    )
    args = parser.parse_args()

    dry_run = args.dry_run
    push = args.push

    if push and dry_run:
        logger.info(
            "DRY RUN MODE: Predictions computed and payloads printed, "
            "but NOT posted to Discord."
        )

    run_tennis_batch(dry_run=dry_run, push=push)


if __name__ == "__main__":
    main()