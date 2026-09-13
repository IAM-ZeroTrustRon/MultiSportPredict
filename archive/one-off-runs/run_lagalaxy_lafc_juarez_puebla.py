#!/usr/bin/env python
"""
Run Analysis: LA Galaxy vs Los Angeles FC + FC Juarez vs Puebla
================================================================
Runs comprehensive soccer predictions for both matches and pushes
strong bet recommendations to Discord using organized embeds.
"""

import sys
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
import pandas as pd

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Rich console for terminal output - avoid Unicode on legacy Windows
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    console = Console(force_terminal=True, color_system="standard")
except Exception:
    console = None

from models.soccer_predictor import SoccerPredictor
from discord_integration import (
    create_organized_prediction_embed,
    COLORS,
)


def run_prediction(home: str, away: str, league: str) -> Dict[str, Any]:
    """Run a soccer prediction and return the result dict."""
    predictor = SoccerPredictor(league=league)
    result = predictor.predict(
        features=pd.DataFrame(),
        model=None,
        home_team=home,
        away_team=away,
        market_line=0.0,
        market_total=2.5,
    )
    return result


def classify_bets(result: Dict[str, Any]) -> tuple:
    """
    Classify all betting markets into strong/medium/pass categories.
    
    Returns (strong_bets, medium_bets, pass_bets, projected_stats)
    """
    game = result.get("game", {})
    goals = result.get("goals_analysis", {})
    predictions = result.get("predictions", {})
    corners = result.get("corners_analysis", {})

    home_team = result.get("home_team", "Home")
    away_team = result.get("away_team", "Away")
    proj_home = game.get("projected_home_goals", 0)
    proj_away = game.get("projected_away_goals", 0)
    total_lambda = proj_home + proj_away

    strong_bets = []
    medium_bets = []
    pass_bets = []

    # ---- 1X2 Moneyline ----
    home_win = game.get("home_win_prob", 0)
    draw = game.get("draw_prob", 0)
    away_win = game.get("away_win_prob", 0)
    best_outcome = max([(home_win, f"{home_team} Win"), (draw, "Draw"), (away_win, f"{away_team} Win")], key=lambda x: x[0])
    ml_prob = best_outcome[0]
    ml_name = best_outcome[1]
    ml_item = {"name": f"Moneyline: {ml_name}", "prob": ml_prob * 100, "edge": f"{ml_prob*100:.0f}% implied"}
    if ml_prob >= 0.55:
        strong_bets.append(ml_item)
    elif ml_prob >= 0.48:
        medium_bets.append(ml_item)
    else:
        pass_bets.append(ml_item)

    # ---- Over/Under 2.5 ----
    over_25 = goals.get("over_25_prob", 0)
    under_25 = 1 - over_25
    if over_25 > under_25:
        ou_name = "Over 2.5 Goals"
        ou_prob = over_25
        ou_edge = f"+{total_lambda - 2.5:.2f} xG edge"
    else:
        ou_name = "Under 2.5 Goals"
        ou_prob = under_25
        ou_edge = f"+{2.5 - total_lambda:.2f} xG edge"
    ou_item = {"name": ou_name, "prob": ou_prob * 100, "edge": ou_edge}
    if ou_prob >= 0.60:
        strong_bets.append(ou_item)
    elif ou_prob >= 0.50:
        medium_bets.append(ou_item)
    else:
        pass_bets.append(ou_item)

    # ---- BTTS ----
    btts_prob = result.get("btts_probability", 0)
    btts_item = {"name": "Both Teams Score", "prob": btts_prob * 100, "edge": f"{btts_prob*100:.0f}% probability"}
    if btts_prob >= 0.60:
        strong_bets.append(btts_item)
    elif btts_prob >= 0.50:
        medium_bets.append(btts_item)
    else:
        pass_bets.append(btts_item)

    # ---- Corners Over 8.5 ----
    corners_85 = corners.get("over_85_prob", 0)
    corner_proj = corners.get("projection", 9.0)
    corner_item = {"name": "Corners Over 8.5", "prob": corners_85 * 100, "edge": f"Proj {corner_proj:.1f}"}
    if corners_85 >= 0.60:
        strong_bets.append(corner_item)
    elif corners_85 >= 0.50:
        medium_bets.append(corner_item)
    else:
        pass_bets.append(corner_item)

    # ---- Corners Over 9.5 ----
    corners_95 = corners.get("over_95_prob", 0)
    corner_item_95 = {"name": "Corners Over 9.5", "prob": corners_95 * 100, "edge": f"Proj {corner_proj:.1f}"}
    if corners_95 >= 0.60:
        strong_bets.append(corner_item_95)
    elif corners_95 >= 0.50:
        medium_bets.append(corner_item_95)
    else:
        pass_bets.append(corner_item_95)

    # ---- Team Totals (Over 1.5) ----
    from scipy.stats import poisson
    home_over_15 = 1 - poisson.cdf(1, proj_home)
    away_over_15 = 1 - poisson.cdf(1, proj_away)
    if home_over_15 >= 0.50:
        ht_item = {"name": f"{home_team} Over 1.5 Goals", "prob": home_over_15 * 100, "edge": f"xG {proj_home:.2f}"}
        if home_over_15 >= 0.55:
            strong_bets.append(ht_item)
        else:
            medium_bets.append(ht_item)
    if away_over_15 >= 0.50:
        at_item = {"name": f"{away_team} Over 1.5 Goals", "prob": away_over_15 * 100, "edge": f"xG {proj_away:.2f}"}
        if away_over_15 >= 0.55:
            strong_bets.append(at_item)
        else:
            medium_bets.append(at_item)

    # ---- Projected Stats ----
    projected_stats = {
        "Projected Score": f"{home_team} {proj_home:.1f} - {proj_away:.1f} {away_team}",
        "Expected Total": f"{total_lambda:.1f} Goals",
        f"{home_team} Win": f"{home_win*100:.1f}%",
        "Draw": f"{draw*100:.1f}%",
        f"{away_team} Win": f"{away_win*100:.1f}%",
        "BTTS Probability": f"{btts_prob*100:.0f}%",
        "Projected Corners": f"{corner_proj:.1f}",
    }

    return strong_bets, medium_bets, pass_bets, projected_stats


def print_match_summary(home: str, away: str, league: str, result: Dict[str, Any]):
    """Print a rich terminal summary for a match."""
    game = result.get("game", {})
    proj_home = game.get("projected_home_goals", 0)
    proj_away = game.get("projected_away_goals", 0)
    btts = result.get("btts_probability", 0)
    corners = result.get("corner_projection", 0)

    if console:
        table = Table(title=f"{home.upper()} vs {away.upper()} ({league})", style="cyan")
        table.add_column("Market", style="bold white")
        table.add_column("Value", style="green")
        table.add_row("Projected Score", f"{home} {proj_home:.1f} - {proj_away:.1f} {away}")
        table.add_row("Total Goals", f"{proj_home + proj_away:.1f}")
        table.add_row("BTTS", f"{btts:.1%}")
        table.add_row("Corners", f"{corners:.1f}")
        table.add_row("Home Win", f"{game.get('home_win_prob', 0):.1%}")
        table.add_row("Draw", f"{game.get('draw_prob', 0):.1%}")
        table.add_row("Away Win", f"{game.get('away_win_prob', 0):.1%}")
        console.print(table)
    else:
        print(f"\n{'='*60}")
        print(f"  {home} vs {away} ({league})")
        print(f"{'='*60}")
        print(f"  Projected Score: {home} {proj_home:.1f} - {proj_away:.1f} {away}")
        print(f"  Total Goals: {proj_home + proj_away:.1f}")
        print(f"  BTTS: {btts:.1%}")
        print(f"  Corners: {corners:.1f}")
        print(f"  Home Win: {game.get('home_win_prob', 0):.1%}")
        print(f"  Draw: {game.get('draw_prob', 0):.1%}")
        print(f"  Away Win: {game.get('away_win_prob', 0):.1%}")


def push_match_to_discord(home: str, away: str, league: str, result: Dict[str, Any]) -> bool:
    """Push a single match's organized prediction to Discord."""
    strong_bets, medium_bets, pass_bets, projected_stats = classify_bets(result)

    embed = create_organized_prediction_embed(
        sport="soccer",
        home=home,
        away=away,
        strong_bets=strong_bets,
        medium_bets=medium_bets,
        pass_bets=pass_bets,
        projected_stats=projected_stats,
    )

    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        logger.error("DISCORD_WEBHOOK_URL not set. Cannot push to Discord.")
        return False

    try:
        import requests
        payload = {"embeds": [embed]}
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        if response.status_code in (200, 204):
            logger.info(f"Pushed {home} vs {away} to Discord successfully.")
            return True
        else:
            logger.error(f"Discord push failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Discord push error: {e}")
        return False


def push_slate_to_discord(all_results: List[Dict[str, Any]]) -> bool:
    """
    Push a consolidated slate message with all match results.
    """
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        logger.error("DISCORD_WEBHOOK_URL not set.")
        return False

    lines = ["[SOCCER SLATE - 2 Matches]", ""]
    for result in all_results:
        home = result.get("home_team", "Home")
        away = result.get("away_team", "Away")
        league = result.get("league", "Unknown")
        game = result.get("game", {})
        proj_home = game.get("projected_home_goals", 0)
        proj_away = game.get("projected_away_goals", 0)
        btts = result.get("btts_probability", 0)
        corners = result.get("corner_projection", 0)

        lines.append(f"**{home} vs {away}** ({league})")
        lines.append(f"   |- Projected: {home} {proj_home:.1f} - {proj_away:.1f} {away}")
        lines.append(f"   |- BTTS: {btts:.0%}")
        lines.append(f"   |- Corners: {corners:.1f}")

        strong_bets, medium_bets, pass_bets, _ = classify_bets(result)
        if strong_bets:
            recs = " | ".join([f"{b['name']}: {b['prob']:.0f}%" for b in strong_bets])
            lines.append(f"   |- STRONG: {recs}")
        lines.append("")

    lines.append("MultiSportPredict - Smart Betting Guide")
    content = "\n".join(lines)

    try:
        import requests
        payload = {"content": content}
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        if response.status_code in (200, 204):
            logger.info("Slate pushed to Discord successfully.")
            return True
        else:
            logger.error(f"Slate push failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Slate push error: {e}")
        return False


def main():
    """Main execution: run predictions and push to Discord."""
    
    print("[MATCH 1] LA Galaxy vs Los Angeles FC (MLS)")
    result1 = run_prediction("LA Galaxy", "Los Angeles FC", "MLS")

    if not result1:
        logger.error("Failed to get prediction for LA Galaxy vs LAFC")
        return

    print_match_summary("LA Galaxy", "Los Angeles FC", "MLS", result1)

    print("[MATCH 2] FC Juarez vs Puebla (Liga MX)")
    result2 = run_prediction("FC Juarez", "Puebla", "Liga MX")

    if not result2:
        logger.error("Failed to get prediction for FC Juarez vs Puebla")
        return

    print_match_summary("FC Juarez", "Puebla", "Liga MX", result2)

    # Print Strong Bets Summary
    print("\n[STRONG BETS SUMMARY]")

    for label, result in [("LA Galaxy vs LAFC", result1), ("FC Juarez vs Puebla", result2)]:
        strong_bets, medium_bets, pass_bets, _ = classify_bets(result)
        print(f"\n  {label}:")
        if strong_bets:
            print(f"    STRONG BETS:")
            for b in strong_bets:
                print(f"      - {b['name']}: {b['prob']:.0f}% ({b['edge']})")
        if medium_bets:
            print(f"    MEDIUM BETS:")
            for b in medium_bets:
                print(f"      - {b['name']}: {b['prob']:.0f}% ({b['edge']})")
        if pass_bets:
            print(f"    PASS:")
            for b in pass_bets:
                print(f"      - {b['name']}: {b['prob']:.0f}%")

    # Push to Discord
    print("\nPushing to Discord...")

    all_results = [result1, result2]
    
    slate_ok = push_slate_to_discord(all_results)
    
    match_results = []
    for result in all_results:
        home = result.get("home_team", "")
        away = result.get("away_team", "")
        league = result.get("league", "")
        ok = push_match_to_discord(home, away, league, result)
        match_results.append(ok)

    # Summary
    print("\nComplete!")
    print(f"   Slate push: {'OK' if slate_ok else 'FAIL'}")
    for i, ok in enumerate(match_results):
        label = f"{all_results[i]['home_team']} vs {all_results[i]['away_team']}"
        print(f"   {label}: {'OK' if ok else 'FAIL'}")

    print("\nAnalysis complete!")
    print(f"   LA Galaxy vs LAFC: {'OK' if match_results[0] else 'FAILED'}")
    print(f"   FC Juarez vs Puebla: {'OK' if match_results[1] else 'FAILED'}")


if __name__ == "__main__":
    main()