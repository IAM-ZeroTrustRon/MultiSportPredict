#!/usr/bin/env python
"""
Push France vs Morocco — FIFA World Cup 2026 Knockout Stage to Discord
=======================================================================
Sends 4 embeds:
  1. Team Analysis Embed       — form, tactics, goal strength, xG
  2. Match Props Embed         — outcome, O/U goals, BTTS, corners
  3. France Player Props Embed — anytime goalscorer props
  4. Morocco Player Props Embed — anytime goalscorer props
"""

import os
import json
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Hard-coded analysis results (from run_france_vs_morocco_analysis.py output)
# ---------------------------------------------------------------------------
ANALYSIS = {
    "home_team": "France",
    "away_team": "Morocco",
    "competition": "FIFA World Cup 2026",
    "stage": "Knockout Stage",
    "date": "July 2026",
    "france_xg": 2.22,
    "morocco_xg": 1.34,
    "total_xg": 3.57,
    "france_goal_strength": 2.61,
    "morocco_goal_strength": 0.08,
    "france_win_prob": 0.476,
    "draw_prob": 0.220,
    "morocco_win_prob": 0.304,
    "over_15_prob": 0.871,
    "over_25_prob": 0.691,
    "over_35_prob": 0.477,
    "btts_prob": 0.508,
    "btts_conf": 40.3,
    "btts_rec": "BTTS NO",
    "goals_conf": 79.3,
    "corners_expected": 10.5,
    "corners_over_95": 0.580,
    "corners_over_105": 0.440,
    "france_scorers": [
        {"name": "Kylian Mbappé",     "xg": 0.68, "odds": "-140", "prob": 0.493, "role": "CF / Captain"},
        {"name": "Antoine Griezmann", "xg": 0.32, "odds": "+190", "prob": 0.274, "role": "SS / 10"},
        {"name": "Ousmane Dembélé",   "xg": 0.28, "odds": "+220", "prob": 0.244, "role": "RW"},
        {"name": "Marcus Thuram",     "xg": 0.25, "odds": "+250", "prob": 0.221, "role": "CF (rotation)"},
    ],
    "morocco_scorers": [
        {"name": "Youssef En-Nesyri", "xg": 0.38, "odds": "+280", "prob": 0.316, "role": "ST"},
        {"name": "Hakim Ziyech",      "xg": 0.22, "odds": "+380", "prob": 0.197, "role": "AM / wide"},
        {"name": "Achraf Hakimi",     "xg": 0.18, "odds": "+420", "prob": 0.165, "role": "RB (set pieces)"},
        {"name": "Azzedine Ounahi",   "xg": 0.12, "odds": "+550", "prob": 0.113, "role": "CM, long shots"},
    ],
}


def rec_emoji(prob: float, threshold_strong: float = 0.45, threshold_value: float = 0.28) -> str:
    if prob >= threshold_strong:
        return "✅"
    if prob >= threshold_value:
        return "⚠️"
    return "❌"


def push_to_discord() -> bool:
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("ERROR: DISCORD_WEBHOOK_URL not set in .env file")
        return False

    d = ANALYSIS
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # -----------------------------------------------------------------------
    # EMBED 1 — Team Analysis
    # -----------------------------------------------------------------------
    embed1 = {
        "title": "⚽ FIFA WORLD CUP 2026 — KNOCKOUT STAGE",
        "description": (
            "**🇫🇷 France vs Morocco 🇲🇦**\n"
            "July 2026 | Neutral Venue\n"
            "Historical: France won 2022 WC SF 2-0 • Morocco never scored vs France"
        ),
        "color": 1752220,  # Dark green
        "fields": [
            {
                "name": "🔵 FRANCE — Team Profile",
                "value": (
                    "**Formation:** 4-3-3 / 4-2-3-1\n"
                    "**Style:** High press, vertical transitions, elite individual quality\n"
                    "**Key Players:** Mbappé (CF), Griezmann (10), Dembélé (RW), Maignan (GK)\n"
                    "**Strengths:** Mbappé pace in behind, superior squad depth\n"
                    "**xG For:** 2.15 | **xG Against:** 0.90\n"
                    f"**Goal Strength:** +{d['france_goal_strength']:.2f}"
                ),
                "inline": False,
            },
            {
                "name": "🔴 MOROCCO — Team Profile",
                "value": (
                    "**Formation:** 4-3-3 / 5-4-1 (defensive shape)\n"
                    "**Style:** Ultra-compact low block, deadly counter-attacks\n"
                    "**Key Players:** En-Nesyri (ST), Ziyech (AM), Hakimi (RB), Bono (GK)\n"
                    "**Strengths:** Back-5 wall, elite set piece discipline, Bono world-class\n"
                    "**xG For:** 1.20 | **xG Against:** 0.78\n"
                    f"**Goal Strength:** +{d['morocco_goal_strength']:.2f}"
                ),
                "inline": False,
            },
            {
                "name": "⚔️ KEY MATCHUP",
                "value": (
                    "**Mbappé vs Hakimi** (PSG club-mates, polar opposite roles today)\n"
                    "France must unlock Morocco's disciplined low block.\n"
                    "Morocco need Hakimi bursts or Ziyech magic to threaten."
                ),
                "inline": False,
            },
        ],
        "footer": {"text": "MultiSportPredict • FIFA World Cup 2026 Analytics"},
        "timestamp": timestamp,
    }

    # -----------------------------------------------------------------------
    # EMBED 2 — Match Props
    # -----------------------------------------------------------------------
    outcome_recs = (
        f"🇫🇷 France Win:   {d['france_win_prob']*100:.1f}%\n"
        f"🤝 Draw (ET/Pens): {d['draw_prob']*100:.1f}%\n"
        f"🇲🇦 Morocco Win:  {d['morocco_win_prob']*100:.1f}%\n"
        f"**→ LEAN: France Win (47.6%)**"
    )
    goals_rec = "OVER" if d['over_25_prob'] > 0.50 else "UNDER"
    goals_emoji = "✅" if d['goals_conf'] >= 60 else "⚠️"

    embed2 = {
        "title": "📊 MATCH PROPS — France vs Morocco",
        "color": 15844367,  # Gold/yellow
        "fields": [
            {
                "name": "🎯 EXPECTED GOALS",
                "value": (
                    f"🇫🇷 France xG:    **{d['france_xg']:.2f}**\n"
                    f"🇲🇦 Morocco xG:   **{d['morocco_xg']:.2f}**\n"
                    f"Total xG:         **{d['total_xg']:.2f}**\n"
                    f"Projected Score:  **France 2.2 – 1.3 Morocco**"
                ),
                "inline": True,
            },
            {
                "name": "📈 GOALS O/U",
                "value": (
                    f"Over 1.5: **{d['over_15_prob']*100:.1f}%**\n"
                    f"Over 2.5: **{d['over_25_prob']*100:.1f}%** {goals_emoji}\n"
                    f"Over 3.5: **{d['over_35_prob']*100:.1f}%**\n"
                    f"**→ {goals_rec} 2.5 (Conf: {d['goals_conf']:.1f}%)**"
                ),
                "inline": True,
            },
            {
                "name": "🤝 BTTS",
                "value": (
                    f"BTTS Probability: **{d['btts_prob']*100:.1f}%**\n"
                    f"Confidence: **{d['btts_conf']:.1f}%**\n"
                    f"**→ {d['btts_rec']} ❌** (Morocco rarely concedes)"
                ),
                "inline": True,
            },
            {
                "name": "🏁 CORNER KICKS",
                "value": (
                    f"France avg corners: ~6.0/game\n"
                    f"Morocco avg corners: ~4.5/game\n"
                    f"Total Expected: **{d['corners_expected']}**\n"
                    f"Over 9.5: **{d['corners_over_95']*100:.1f}%** ⚠️\n"
                    f"Over 10.5: **{d['corners_over_105']*100:.1f}%**\n"
                    f"**→ OVER 9.5 CORNERS**"
                ),
                "inline": True,
            },
            {
                "name": "📋 MATCH OUTCOME",
                "value": outcome_recs,
                "inline": True,
            },
            {
                "name": "💡 SHARP VALUE NOTES",
                "value": (
                    "• **Mbappé anytime scorer** (-140): best single-market play ✅\n"
                    "• **Morocco to qualify** (+290+): upset value is real ⚠️\n"
                    "• **Under 2.5 goals**: Morocco defense = live option ⚠️\n"
                    "• **France win both halves**: value if press dominates early\n"
                    "• **BTTS NO**: Morocco clean sheet in 7 of last 10 matches"
                ),
                "inline": False,
            },
        ],
        "footer": {"text": "MultiSportPredict • FIFA World Cup 2026 Analytics"},
        "timestamp": timestamp,
    }

    # -----------------------------------------------------------------------
    # EMBED 3 — France Player Props (Anytime Goalscorer)
    # -----------------------------------------------------------------------
    france_props_lines = []
    for p in d["france_scorers"]:
        emoji = rec_emoji(p["prob"])
        rec_label = "STRONG" if p["prob"] >= 0.45 else ("VALUE" if p["prob"] >= 0.28 else "PASS")
        france_props_lines.append(
            f"{emoji} **{p['name']}** ({p['role']})\n"
            f"   xG: {p['xg']:.2f} | Odds: {p['odds']} | Prob: {p['prob']*100:.1f}% — *{rec_label}*"
        )

    embed3 = {
        "title": "🇫🇷 FRANCE — Anytime Goalscorer Props",
        "color": 3447003,  # Blue
        "fields": [
            {
                "name": "Goalscorer Probabilities",
                "value": "\n".join(france_props_lines),
                "inline": False,
            },
            {
                "name": "📌 Top Pick",
                "value": (
                    "✅ **Kylian Mbappé — Anytime Scorer (-140)**\n"
                    "49.3% model probability. Captain, primary finisher, faces a Morocco "
                    "back-line he already beat in 2022 WC SF. Best value on the board."
                ),
                "inline": False,
            },
        ],
        "footer": {"text": "MultiSportPredict • FIFA World Cup 2026 Analytics"},
        "timestamp": timestamp,
    }

    # -----------------------------------------------------------------------
    # EMBED 4 — Morocco Player Props (Anytime Goalscorer)
    # -----------------------------------------------------------------------
    morocco_props_lines = []
    for p in d["morocco_scorers"]:
        emoji = rec_emoji(p["prob"], threshold_strong=0.35, threshold_value=0.18)
        rec_label = "STRONG" if p["prob"] >= 0.35 else ("VALUE" if p["prob"] >= 0.18 else "PASS")
        morocco_props_lines.append(
            f"{emoji} **{p['name']}** ({p['role']})\n"
            f"   xG: {p['xg']:.2f} | Odds: {p['odds']} | Prob: {p['prob']*100:.1f}% — *{rec_label}*"
        )

    embed4 = {
        "title": "🇲🇦 MOROCCO — Anytime Goalscorer Props",
        "color": 15105570,  # Orange/red
        "fields": [
            {
                "name": "Goalscorer Probabilities",
                "value": "\n".join(morocco_props_lines),
                "inline": False,
            },
            {
                "name": "📌 Top Pick",
                "value": (
                    "⚠️ **Youssef En-Nesyri — Anytime Scorer (+280)**\n"
                    "31.6% model probability. Morocco's lone striker, aerial threat, "
                    "scored in 2022 WC run. Strong upset value at these odds."
                ),
                "inline": False,
            },
            {
                "name": "🔑 Tactical Note",
                "value": (
                    "Morocco will rely on **set pieces & Hakimi runs** as primary scoring routes. "
                    "Ziyech's creativity from wide areas is the unlock key. "
                    "Watch for Hakimi arriving late into the box on counter-attacks."
                ),
                "inline": False,
            },
        ],
        "footer": {"text": "MultiSportPredict • FIFA World Cup 2026 Analytics"},
        "timestamp": timestamp,
    }

    # -----------------------------------------------------------------------
    # Send all 4 embeds
    # -----------------------------------------------------------------------
    all_embeds = [embed1, embed2, embed3, embed4]
    success_count = 0

    for i, embed in enumerate(all_embeds, start=1):
        payload = {"embeds": [embed]}
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            if resp.status_code in (200, 204):
                print(f"  ✅ Embed {i}/4 sent successfully.")
                success_count += 1
            else:
                print(f"  ❌ Embed {i}/4 failed: HTTP {resp.status_code} — {resp.text[:200]}")
        except Exception as exc:
            print(f"  ❌ Embed {i}/4 error: {exc}")

    if success_count == 4:
        print("\n✅ All 4 embeds pushed to Discord successfully.")
        return True
    else:
        print(f"\n⚠️  {success_count}/4 embeds sent.")
        return False


def main():
    print("=" * 70)
    print("FIFA WORLD CUP 2026 — France vs Morocco | Discord Push")
    print("=" * 70)
    push_to_discord()


if __name__ == "__main__":
    main()
