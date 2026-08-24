#!/usr/bin/env python
"""
Push VPS vs FC Inter Turku (Finnish Cup Semi-Final) to Discord
===============================================================
Pushes the comprehensive live match analytics to Discord webhook.
"""

import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def load_analysis_results() -> dict:
    """Load the saved JSON analysis results."""
    path = Path("output/soccer/VPS_vs_FC_Inter_Turku_finnish_cup_2026_06_30.json")
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def push_to_discord():
    """Push the VPS vs FC Inter Turku analysis to Discord."""
    
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("ERROR: DISCORD_WEBHOOK_URL not set in .env file")
        return False

    result = load_analysis_results()
    if not result:
        print("ERROR: No analysis results found. Run run_vps_inter_turku_finnish_cup_2026_06_30.py first.")
        return False

    model = result["model_output"]
    
    # Build edge comparisons
    side_edges = (
        f"VPS ML (+225):  {model['home_win_prob']*100:.1f}% (edge: {model['home_edge']*100:+.1f}%)\n"
        f"Draw (+210):    {model['draw_prob']*100:.1f}% (edge: {model['draw_edge']*100:+.1f}%)\n"
        f"Inter (+100):   {model['away_win_prob']*100:.1f}% (edge: {model['away_edge']*100:+.1f}%)"
    )

    # Determine color based on best edge
    best_edge = model['home_edge']
    if best_edge > 0.05:
        color = 3066993  # Green
    elif best_edge > 0:
        color = 10181046  # Blue
    else:
        color = 15158332  # Red

    fields = [
        {
            "name": "MATCH INFO",
            "value": (
                f"**VPS vs FC Inter Turku**\n"
                f"2026 Finnish Cup Semi-Final\n"
                f"Lemonsoft Stadion, Vaasa\n"
                f"Live: 27' | Score: 0-0"
            ),
            "inline": False,
        },
        {
            "name": "PROJECTED GOALS",
            "value": (
                f"VPS Expected: {model['home_lambda']:.3f}\n"
                f"Inter Turku Expected: {model['away_lambda']:.3f}\n"
                f"Match Total: {model['total_lambda']:.3f}\n"
                f"(Adj: H2H x0.70, Cup KO x0.85)"
            ),
            "inline": True,
        },
        {
            "name": "MATCH OUTCOME",
            "value": (
                f"VPS Win: {model['home_win_prob']*100:.1f}%\n"
                f"Draw:    {model['draw_prob']*100:.1f}%\n"
                f"Inter:   {model['away_win_prob']*100:.1f}%"
            ),
            "inline": True,
        },
        {
            "name": "EDGE VS MARKET",
            "value": side_edges,
            "inline": False,
        },
        {
            "name": "TOTAL GOALS",
            "value": (
                f"Over 1.5: {model['over_25_prob']*100:.1f}% (no)\n"
                f"Under 2.5: {model['under_25_prob']*100:.1f}%\n"
                f"Line: 2.5 → **PASS** (2.511 proj)"
            ),
            "inline": True,
        },
        {
            "name": "BTTS & CORNERS",
            "value": (
                f"BTTS Yes: {model['btts_prob']*100:.1f}% (edge: +{model['btts_prob']*100-50:.1f}%)\n"
                f"Corners: {model['corner_projection']} proj\n"
                f"Over 8.5: 85.1% | Over 9.5: 76.6%"
            ),
            "inline": True,
        },
        {
            "name": "LIVE STATE (27TH MINUTE)",
            "value": (
                f"VPS remaining xG: {model['home_lambda']*0.7:.3f}\n"
                f"Inter remaining xG: {model['away_lambda']*0.7:.3f}\n"
                f"0-0 final prob: {model['scoreless_rest_prob']*100:.1f}%\n"
                f"At least 1 goal: {(1-model['scoreless_rest_prob'])*100:.1f}%"
            ),
            "inline": False,
        },
        {
            "name": "RECOMMENDATIONS",
            "value": (
                f"**SIDE:** VPS ML (+225) — {model['home_edge']*100:+.1f}% edge\n"
                f"**TOTAL:** PASS — Projected 2.511 vs 2.5 line\n"
                f"**BTTS:** Yes — {model['btts_prob']*100:.1f}% probability\n"
                f"**Sharp Consensus:** {result['recommendations']['sharp_consensus']}"
            ),
            "inline": False,
        },
    ]

    embed = {
        "title": "FINNISH CUP SEMI-FINAL - LIVE MATCH ANALYTICS",
        "description": (
            f":soccer: **VPS vs FC Inter Turku**\n"
            f"27th Minute | 0-0 | H2H x0.70 | Cup KO x0.85"
        ),
        "color": color,
        "fields": fields,
        "footer": {
            "text": "MultiSportPredict • Live Match Analytics Feed"
        },
        "timestamp": "2026-06-30T15:00:00Z",
    }

    payload = {"embeds": [embed]}

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        if response.status_code in (200, 204):
            print("SUCCESS: VPS vs Inter Turku analysis pushed to Discord!")
            return True
        else:
            print(f"ERROR: Discord returned status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"ERROR: Failed to push to Discord: {e}")
        return False


if __name__ == "__main__":
    if push_to_discord():
        print("Done.")
    else:
        print("Failed to push to Discord.")
        exit(1)