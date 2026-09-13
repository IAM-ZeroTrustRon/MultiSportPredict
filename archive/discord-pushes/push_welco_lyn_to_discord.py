#!/usr/bin/env python
"""
Push JK Welco Elekter vs Vimsi JK & Lyn vs Asane analysis to Discord
===================================================================
Pushes the comprehensive two-match soccer analysis to Discord webhook.
"""

import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def load_analysis_results() -> list:
    """Load the saved JSON analysis results."""
    path = Path("output/welco_lyn_analysis_2026_07_02.json")
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []


def push_to_discord():
    """Push both match analyses to Discord."""
    
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("ERROR: DISCORD_WEBHOOK_URL not set in .env file")
        return False

    results = load_analysis_results()
    if not results:
        print("ERROR: No analysis results found. Run run_welco_lyn_soccer_analysis.py first.")
        return False

    r1 = results[0]  # JK Welco Elekter vs Vimsi JK
    r2 = results[1]  # Lyn vs Asane

    # ---- MATCH 1 EMBED ----
    t1 = r1['totals_market']
    b1 = r1['btts_market']
    c1 = r1['corners_market']
    p1 = r1['projection']

    # Build match 1 description
    totals_verdict = "STRONG BET" if t1['verdict'] in ("STRONG", "VALUE") else "PASS"
    btts_verdict = "STRONG BET" if b1['verdict'] in ("STRONG", "VALUE") else "PASS"
    corners_verdict = "STRONG BET" if c1['verdict'] in ("STRONG", "VALUE") else "PASS"

    match1_value = (
        f"**{r1['home_team']} vs {r1['away_team']}**\n"
        f"League: {r1['league']} | Liquidity: {r1['liquidity']}\n"
        f"Projected: {p1['projected_score']} (Total xG: {p1['total_goals']:.2f})\n"
        f"1X2: {r1['home_team']} {p1['home_win_prob']:.1%} | Draw {p1['draw_prob']:.1%} | {r1['away_team']} {p1['away_win_prob']:.1%}\n\n"
        f"**TOTAL GOALS (Over {t1['market_line']:.1f})**\n"
        f"Prob: {t1['over_prob']:.1%} | Edge: {t1['edge']:+.2f} | Conf: {t1['confidence']:.1f}/100\n"
        f"Verdict: **{totals_verdict}** ({t1['sharp_consensus']['sharp_alignment']})\n\n"
        f"**BTTS YES**\n"
        f"Prob: {b1['yes_prob']:.1%} | Edge: {b1['edge']:+.2f} | Conf: {b1['confidence']:.1f}/100\n"
        f"Verdict: **{btts_verdict}** ({b1['sharp_consensus']['sharp_alignment']})\n\n"
        f"**CORNERS (Over {c1['market_line']:.1f})**\n"
        f"Blended Proj: {c1['blended_projection']:.2f} (Model: {c1['model_total']:.2f}, Recal: {c1['recalibrated_total']:.2f})\n"
        f"Prob: {c1['over_prob']:.1%} | Edge: {c1['edge']:+.2f} | Conf: {c1['confidence']:.1f}/100\n"
        f"Verdict: **{corners_verdict}** ({c1['sharp_consensus']['sharp_alignment']})"
    )

    # ---- MATCH 2 EMBED ----
    t2 = r2['totals_market']
    b2 = r2['btts_market']
    c2 = r2['corners_market']
    p2 = r2['projection']

    totals_verdict2 = "STRONG BET" if t2['verdict'] in ("STRONG", "VALUE") else "PASS"
    btts_verdict2 = "STRONG BET" if b2['verdict'] in ("STRONG", "VALUE") else "PASS"
    corners_verdict2 = "STRONG BET" if c2['verdict'] in ("STRONG", "VALUE") else "PASS"

    match2_value = (
        f"**{r2['home_team']} vs {r2['away_team']}**\n"
        f"League: {r2['league']} | Liquidity: {r2['liquidity']}\n"
        f"Projected: {p2['projected_score']} (Total xG: {p2['total_goals']:.2f})\n"
        f"1X2: {r2['home_team']} {p2['home_win_prob']:.1%} | Draw {p2['draw_prob']:.1%} | {r2['away_team']} {p2['away_win_prob']:.1%}\n\n"
        f"**TOTAL GOALS (Over {t2['market_line']:.1f})**\n"
        f"Prob: {t2['over_prob']:.1%} | Edge: {t2['edge']:+.2f} | Conf: {t2['confidence']:.1f}/100\n"
        f"Verdict: **{totals_verdict2}** ({t2['sharp_consensus']['sharp_alignment']})\n\n"
        f"**BTTS YES**\n"
        f"Prob: {b2['yes_prob']:.1%} | Edge: {b2['edge']:+.2f} | Conf: {b2['confidence']:.1f}/100\n"
        f"Verdict: **{btts_verdict2}** ({b2['sharp_consensus']['sharp_alignment']})\n\n"
        f"**CORNERS (Over {c2['market_line']:.1f})**\n"
        f"Blended Proj: {c2['blended_projection']:.2f} (Model: {c2['model_total']:.2f}, Recal: {c2['recalibrated_total']:.2f})\n"
        f"Prob: {c2['over_prob']:.1%} | Edge: {c2['edge']:+.2f} | Conf: {c2['confidence']:.1f}/100\n"
        f"Verdict: **{corners_verdict2}** ({c2['sharp_consensus']['sharp_alignment']})"
    )

    # ---- TOP PICKS SUMMARY ----
    top_picks = []
    
    # Evaluate each market for both matches
    evaluations = [
        ("Match 1", "Over 2.5G", t1['verdict'], t1['confidence']),
        ("Match 1", "BTTS Yes", b1['verdict'], b1['confidence']),
        ("Match 1", "Over 9.5 Cor", c1['verdict'], c1['confidence']),
        ("Match 2", "Over 2.5G", t2['verdict'], t2['confidence']),
        ("Match 2", "BTTS Yes", b2['verdict'], b2['confidence']),
        ("Match 2", "Over 10.5 Cor", c2['verdict'], c2['confidence']),
    ]
    
    # Sort: STRONG first, then VALUE, then SLIGHT, then PASS
    priority = {"STRONG": 0, "VALUE": 1, "SLIGHT": 2, "PASS": 3}
    evaluations.sort(key=lambda x: (priority.get(x[2], 4), -x[3]))
    
    picks_lines = []
    for match_name, market, verdict, conf in evaluations:
        if verdict in ("STRONG", "VALUE"):
            emoji = "🟢" if verdict == "STRONG" else "🟡"
            picks_lines.append(f"{emoji} **{match_name}** - {market} ({verdict}, {conf:.0f}/100)")
    
    summary_value = "\n".join(picks_lines) if picks_lines else "No strong picks identified."
    
    picks_value = (
        f"{summary_value}\n\n"
        f"*Data from MultiSportPredict xG/Poisson pipeline*\n"
        f"*Generated: {r1['generated']}*"
    )

    embeds = [
        {
            "title": "⚽ SOCCER ANALYSIS - July 2, 2026",
            "description": "Two-match comprehensive analysis using MultiSportPredict xG/Poisson modeling",
            "color": 3066993,  # Green
            "fields": [
                {
                    "name": "🇪🇪 MATCH 1: JK Welco Elekter vs Vimsi JK (Estonian Esiliiga)",
                    "value": match1_value,
                    "inline": False
                },
                {
                    "name": "🇳🇴 MATCH 2: Lyn vs Asane (Norwegian OBOS-ligaen)",
                    "value": match2_value,
                    "inline": False
                },
                {
                    "name": "🏆 TOP PICKS (Ranked)",
                    "value": picks_value,
                    "inline": False
                }
            ],
            "footer": {
                "text": "MultiSportPredict • Smart Betting Engine"
            }
        }
    ]

    # ---- WARNING EMBED for low liquidity ----
    if r1['liquidity'] == "LOW":
        embeds.append({
            "title": "⚠️ LIQUIDITY WARNING",
            "description": (
                "The Estonian Esiliiga has **LOW liquidity** - lines may be less efficient. "
                "Sharp data is estimated based on model probabilities, not actual market movement. "
                "Consider reduced stake sizes for Match 1 markets."
            ),
            "color": 16776960,  # Yellow
        })

    payload = {
        "username": "MultiSportPredict",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/2867/2867903.png",
        "embeds": embeds
    }

    # Send to Discord
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code in (200, 204):
            print("[OK] Analysis pushed to Discord successfully!")
            return True
        else:
            print(f"[FAIL] Discord returned status {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"[FAIL] Failed to push to Discord: {e}")
        return False


def main():
    print("=" * 60)
    print("PUSHING SOCCER ANALYSIS TO DISCORD")
    print("=" * 60)
    push_to_discord()


if __name__ == "__main__":
    main()