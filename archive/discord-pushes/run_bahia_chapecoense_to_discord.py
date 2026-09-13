#!/usr/bin/env python
"""
Esporte Clube Bahia vs. Associação Chapecoense de Futebol — Brasileirão Série A
=================================================================================
Pushes rich multi-embed analysis to Discord based on deep-dive handicapping.

Kickoff: July 17, 2026, 6:30 PM EDT
Venue: Arena Fonte Nova, Salvador, Brazil
"""

import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# PRE-COMPUTED ANALYSIS DATA (from deep-dive handicapping)
# ---------------------------------------------------------------------------
ANALYSIS = {
    "home_team": "Bahia",
    "away_team": "Chapecoense",
    "competition": "Brasileirão Série A",
    "venue": "Arena Fonte Nova, Salvador, Brazil",
    "date": "July 17, 2026",
    "time": "6:30 PM EDT",
    "home_standing": "6th (26 pts)",
    "away_standing": "20th (9 pts)",
    "home_goals_per_game": 1.5,
    "home_shots_per_game": 12.6,
    "away_goals_conceded_per_game": 1.94,
    "away_total_goals_conceded": 33,
    "away_away_points": 2,
    "home_form_note": "Recent 2-1 win over Botafogo — broke poor run",
    "away_form_note": "Lost 10 of last 13 matches — severe road struggles",
    "home_win_odds": -237,
    "away_win_odds": 545,
    "over_25_odds": -174,
    "btts_home_pct": 71,
    "btts_away_pct": 65,
    "sharp_consensus": "Bahia win — value on -1 / -1.5 handicap",
    "injury_note": "Chapecoense backline severely depleted by injuries to key defenders",
}


def rec_emoji(prob_pct: float, threshold_strong: float = 65.0, threshold_value: float = 50.0) -> str:
    if prob_pct >= threshold_strong:
        return "✅"
    if prob_pct >= threshold_value:
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
    # EMBED 1 — Team Analysis & Form
    # -----------------------------------------------------------------------
    embed1 = {
        "title": "⚽ BRASILEIRÃO SÉRIE A — MATCHDAY 18",
        "description": (
            f"**{d['home_team']} vs {d['away_team']}**\n"
            f"📅 {d['date']} | 🕐 {d['time']}\n"
            f"🏟️ {d['venue']}"
        ),
        "color": 1752220,  # Green
        "fields": [
            {
                "name": "🔵 BAHIA — Team Profile",
                "value": (
                    f"**Standing:** {d['home_standing']} — Pushing for Libertadores\n"
                    f"**Goals/Game:** {d['home_goals_per_game']} | **Shots/Game:** {d['home_shots_per_game']}\n"
                    f"**Style:** Efficient attack — strong at home, sustained pressure\n"
                    f"**Form:** {d['home_form_note']}\n"
                    f"**Home Advantage:** Arena Fonte Nova — historically difficult for visitors"
                ),
                "inline": False,
            },
            {
                "name": "🟢 CHAPECOENSE — Team Profile",
                "value": (
                    f"**Standing:** {d['away_standing']} — Severe relegation battle\n"
                    f"**Goals Conceded/Game:** {d['away_goals_conceded_per_game']} ({d['away_total_goals_conceded']} total)\n"
                    f"**Away Points:** {d['away_away_points']} all season\n"
                    f"**Form:** {d['away_form_note']}\n"
                    f"**Injury Crisis:** Backline severely depleted — missing key defenders"
                ),
                "inline": False,
            },
            {
                "name": "⚔️ KEY MATCHUP",
                "value": (
                    "**Bahia attack vs Chapecoense injury-ravaged defense**\n"
                    "Bahia's efficient home attack faces a Chapecoense backline "
                    "that has conceded 33 goals in 17 rounds. With key defenders "
                    "missing, expect Bahia to exploit set pieces and sustained pressure.\n\n"
                    "**Transition danger for Bahia:** Chapecoense relies heavily on "
                    "counter-attacks — Bahia's high line must stay disciplined."
                ),
                "inline": False,
            },
        ],
        "footer": {"text": "MultiSportPredict • Brasileirão Série A Analytics"},
        "timestamp": timestamp,
    }

    # -----------------------------------------------------------------------
    # EMBED 2 — Match Props & Markets
    # -----------------------------------------------------------------------
    embed2 = {
        "title": "📊 MATCH PROPS — Bahia vs Chapecoense",
        "color": 15844367,  # Gold
        "fields": [
            {
                "name": "🎯 MONEYLINE",
                "value": (
                    f"🔵 **Bahia:** **-{abs(d['home_win_odds'])}** ({(1/abs(d['home_win_odds']/100+1))*100:.1f}% implied)\n"
                    f"🤝 **Draw:** N/A\n"
                    f"🟢 **Chapecoense:** **+{d['away_win_odds']}** ({(1/(d['away_win_odds']/100+1))*100:.1f}% implied)\n"
                    f"**→ Strong lean: BAHIA WIN** — market heavily favors home side"
                ),
                "inline": False,
            },
            {
                "name": "📈 TOTAL GOALS (O/U 2.5)",
                "value": (
                    f"Over 2.5 Goals: **-{abs(d['over_25_odds'])}** ({(1/(d['over_25_odds']/100+1))*100:.1f}% implied)\n"
                    f"Heavily juiced to the OVER — market expects Bahia to capitalize\n"
                    f"**→ OVER 2.5** — sharp consensus on goals from Bahia attack"
                ),
                "inline": True,
            },
            {
                "name": "🏁 HANDICAP",
                "value": (
                    "**Bahia -1 / -1.5** — value identified by sharp bettors\n"
                    "Chapecoense's 1.94 GA/game and injury-depleted backline\n"
                    "make covering the handicap highly probable at home."
                ),
                "inline": True,
            },
            {
                "name": "🤝 BOTH TEAMS TO SCORE (BTTS)",
                "value": (
                    f"Historically: **{d['btts_home_pct']}%** of Bahia matches hit BTTS\n"
                    f"Historically: **{d['btts_away_pct']}%** of Chapecoense matches hit BTTS\n"
                    f"**⚠️ Cautious on BTTS YES** — Chapecoense's mounting injury list\n"
                    f"and dismal away form suggest they may fail to contribute.\n"
                    f"Focus instead on **Bahia team total**."
                ),
                "inline": False,
            },
        ],
        "footer": {"text": "MultiSportPredict • Brasileirão Série A Analytics"},
        "timestamp": timestamp,
    }

    # -----------------------------------------------------------------------
    # EMBED 3 — Sharp Consensus & Value Plays
    # -----------------------------------------------------------------------
    embed3 = {
        "title": "💡 SHARP CONSENSUS & VALUE ANGLES",
        "color": 15105570,  # Orange
        "fields": [
            {
                "name": "🎯 SHARP MONEY ALIGNMENT",
                "value": (
                    "• **Bahia Moneyline (-237):** Heavy sharp action on home win\n"
                    "• **Bahia -1 / -1.5 Handicap:** Value identified — visitor defense in shambles\n"
                    "• **Over 2.5 Goals (-174):** Sharps loading on Bahia attack to drive total\n"
                    "• **Bahia Team Total:** Better angle than BTTS given visitor injury woes"
                ),
                "inline": False,
            },
            {
                "name": "🔥 TOP PLAYS",
                "value": (
                    "1️⃣ **Bahia ML** — Strongest sharp consensus play ❌\n"
                    "2️⃣ **Bahia -1 / -1.5** — Handicap value with depleted defense ✅\n"
                    "3️⃣ **Over 2.5 Goals** — Bahia attack projection ✅\n"
                    "4️⃣ **Bahia Team Total Over** — Better than BTTS given visitor injuries ⚠️"
                ),
                "inline": False,
            },
            {
                "name": "📊 STANDINGS CONTEXT",
                "value": (
                    f"**Bahia (6th, 26 pts)** — Every point crucial for top-eight\n"
                    f"Libertadores qualification. Must win at home vs bottom side.\n\n"
                    f"**Chapecoense (20th, 9 pts)** — Already 8 points from safety.\n"
                    f"Survival hopes hanging by a thread. Road form is catastrophic\n"
                    f"with only {d['away_away_points']} away points all season."
                ),
                "inline": False,
            },
            {
                "name": "⚠️ RISK FACTORS",
                "value": (
                    "• Chapecoense transition attacks — Bahia high line vulnerable\n"
                    "• Chapecoense historically fight hard in relegation battles\n"
                    "• Bahia inconsistent form despite recent Botafogo win\n"
                    "• -237 ML is expensive — handicap or team total may offer better ROI"
                ),
                "inline": False,
            },
        ],
        "footer": {"text": "MultiSportPredict • Brasileirão Série A Analytics"},
        "timestamp": timestamp,
    }

    # -----------------------------------------------------------------------
    # Send all embeds
    # -----------------------------------------------------------------------
    all_embeds = [embed1, embed2, embed3]
    success_count = 0
    total = len(all_embeds)

    for i, embed in enumerate(all_embeds, start=1):
        payload = {"embeds": [embed]}
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            if resp.status_code in (200, 204):
                print(f"  [OK] Embed {i}/{total} sent successfully.")
                success_count += 1
            else:
                print(f"  [FAIL] Embed {i}/{total} failed: HTTP {resp.status_code} -- {resp.text[:200]}")
        except Exception as exc:
            print(f"  [ERROR] Embed {i}/{total} error: {exc}")

    if success_count == total:
        print(f"\n[SUCCESS] All {total} embeds pushed to Discord successfully.")
        return True
    else:
        print(f"\n[WARNING] {success_count}/{total} embeds sent.")
        return False


def main():
    print("=" * 70)
    print("BRASILEIRÃO SÉRIE A — Bahia vs Chapecoense | Discord Push")
    print("=" * 70)
    print(f"Kickoff: {ANALYSIS['date']} @ {ANALYSIS['time']}")
    print(f"Venue: {ANALYSIS['venue']}")
    print("=" * 70)
    push_to_discord()


if __name__ == "__main__":
    main()