#!/usr/bin/env python
"""
Run model on 3 upcoming matches and push results to Discord.

Matches:
  1. Estonia Meistriliiga: Flora Tallinn vs Nomme United
  2. Sweden Allsvenskan: Mjallby AIF vs Vasteras SK
  3. Sweden Allsvenskan: IFK Goteborg vs Brommapojkarna

Usage:
    python run_three_match_slate_to_discord.py
"""

import os
import sys
from datetime import datetime

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# MATCH DATA
# ---------------------------------------------------------------------------

matches = [
    {
        "league": "Estonia Meistriliiga",
        "home": "Flora Tallinn",
        "away": "Nomme United",
        "date": "2026-07-17",
        "id": "EST_FLO_NOM",
    },
    {
        "league": "Sweden Allsvenskan",
        "home": "Mjallby AIF",
        "away": "Vasteras SK",
        "date": "2026-07-17",
        "id": "SWE_MJA_VAS",
    },
    {
        "league": "Sweden Allsvenskan",
        "home": "IFK Goteborg",
        "away": "Brommapojkarna",
        "date": "2026-07-17",
        "id": "SWE_IFK_BRO",
    },
]

# ---------------------------------------------------------------------------
# MODEL INFERENCE (PLACEHOLDER)
# ---------------------------------------------------------------------------

def run_model(match_row):
    """
    Plug in your feature engineering + model inference here.
    match_row: dict with home/away/league/date/id
    Return a dict with your key outputs:
      - p_home, p_draw, p_away
      - p_over25, p_btts, etc.
    """
    # Example placeholder – replace with your actual model call
    # features = build_features(match_row)
    # preds = model.predict_proba(features)
    return {
        "p_home": 0.55,
        "p_draw": 0.20,
        "p_away": 0.25,
        "p_over25": 0.70,
        "p_btts": 0.68,
        "p_over15_1h": 0.45,
        "p_over85_corners": 0.72,
    }


def derive_angles(row):
    """Derive recommended betting angles from model outputs."""
    angles = []
    if row["p_over25"] > 0.65:
        angles.append("Over 2.5 goals")
    if row["p_btts"] > 0.65:
        angles.append("BTTS Yes")
    if row["p_over15_1h"] > 0.50:
        angles.append("1H Over 1.5 goals")
    if row["p_over85_corners"] > 0.65:
        angles.append("Over 8.5 corners")
    return angles


# ---------------------------------------------------------------------------
# RUN MODEL ON ALL MATCHES
# ---------------------------------------------------------------------------

results = []
for m in matches:
    preds = run_model(m)
    row = {**m, **preds}
    results.append(row)

df_results = pd.DataFrame(results)
df_results["model_angles"] = df_results.apply(derive_angles, axis=1)

# Console summary
print("=" * 60)
print("  MODEL PREDICTIONS — 3 Match Slate")
print("=" * 60)
for _, r in df_results.iterrows():
    print(f"\n  {r['league']}")
    print(f"  {r['home']} vs {r['away']}")
    print(f"  |-- Home Win:  {r['p_home']:.0%}")
    print(f"  |-- Draw:      {r['p_draw']:.0%}")
    print(f"  |-- Away Win:  {r['p_away']:.0%}")
    print(f"  |-- Over 2.5:  {r['p_over25']:.0%}")
    print(f"  |-- BTTS:      {r['p_btts']:.0%}")
    print(f"  |-- 1H O1.5:   {r['p_over15_1h']:.0%}")
    print(f"  |-- O8.5 Corn: {r['p_over85_corners']:.0%}")
    print(f"  '-- Angles:    {', '.join(r['model_angles']) if r['model_angles'] else 'None'}")
print()

# ---------------------------------------------------------------------------
# PUSH TO DISCORD
# ---------------------------------------------------------------------------

def push_slate_to_discord(df):
    """Push the 3-match slate to Discord as a single rich embed."""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url or webhook_url == "None":
        print("[FAIL] DISCORD_WEBHOOK_URL not set in environment. Skipping Discord push.")
        return False

    # Build embed fields — one per match
    fields = []
    for _, row in df.iterrows():
        league = row["league"]
        home = row["home"]
        away = row["away"]

        # Probabilities line
        probs_line = (
            f"Home {row['p_home']:.0%}  |  Draw {row['p_draw']:.0%}  |  "
            f"Away {row['p_away']:.0%}"
        )

        # Market probabilities
        markets_line = (
            f"O2.5: {row['p_over25']:.0%}  |  BTTS: {row['p_btts']:.0%}  |  "
            f"1H O1.5: {row['p_over15_1h']:.0%}  |  O8.5C: {row['p_over85_corners']:.0%}"
        )

        # Recommended angles
        angles = row["model_angles"]
        if angles:
            angles_line = "  ✅ " + "\n  ✅ ".join(angles)
        else:
            angles_line = "  No strong angles"

        value = (
            f"**Probabilities:**\n{probs_line}\n\n"
            f"**Market Projections:**\n{markets_line}\n\n"
            f"**Recommended Angles:**\n{angles_line}"
        )

        fields.append({
            "name": f"⚽ {league} — {home} vs {away}",
            "value": value,
            "inline": False,
        })

    # Overall color: green if any match has 2+ strong angles
    max_angles = df["model_angles"].apply(len).max()
    if max_angles >= 2:
        color = 3066993  # Green
    elif max_angles >= 1:
        color = 10181046  # Blue
    else:
        color = 9807270  # Gray

    embed = {
        "title": "📊 3-Match Slate — Model Predictions",
        "description": (
            f"**Date:** {matches[0]['date']}\n\n"
            f"Model-derived probabilities and recommended betting angles "
            f"for today's slate."
        ),
        "color": color,
        "fields": fields,
        "timestamp": datetime.now().isoformat() + "Z",
        "footer": {
            "text": "MultiSportPredict • Model-Driven Betting Guide"
        },
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
            print("[OK] Slate successfully pushed to Discord!")
            return True
        else:
            print(f"[FAIL] Discord push failed: status={response.status_code} body={response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"[FAIL] Discord webhook request failed: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] Unexpected error: {e}")
        return False


if __name__ == "__main__":
    success = push_slate_to_discord(df_results)
    if not success:
        sys.exit(1)
    sys.exit(0)