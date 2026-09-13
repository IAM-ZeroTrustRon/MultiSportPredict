#!/usr/bin/env python
"""Push 2026 FIFA World Cup quarterfinals rich analysis to Discord."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict

from dotenv import load_dotenv

load_dotenv()

import discord_integration
import multi_sport_engine


def _team_stats_for_worldcup(team: str) -> Dict[str, float]:
    WORLD_CUP_STATS = {
        "Norway": {"xg_for": 1.95, "xg_against": 1.20, "sot": 5.1},
        "England": {"xg_for": 2.10, "xg_against": 0.95, "sot": 5.8},
        "Argentina": {"xg_for": 2.25, "xg_against": 0.80, "sot": 6.2},
        "Switzerland": {"xg_for": 1.30, "xg_against": 1.10, "sot": 3.9},
    }
    return WORLD_CUP_STATS.get(team, {"xg_for": 1.65, "xg_against": 1.35, "sot": 4.5})


def _model_projection(home: str, away: str) -> Dict[str, Any]:
    h = _team_stats_for_worldcup(home)
    a = _team_stats_for_worldcup(away)

    return multi_sport_engine.predict_soccer(
        home,
        away,
        "World Cup",
        market_total=2.5,
        home_xg_for=h["xg_for"],
        home_sot=h["sot"],
        away_xg_for=a["xg_for"],
        away_sot=a["sot"],
        home_xg_against=h.get("xg_against", 1.20),
        away_xg_against=a.get("xg_against", 1.35),
    )


def _build_match_field(match: Dict[str, Any]) -> Dict[str, Any]:
    header = f"{match['heading']}\n*{match['time_meta']}*"

    stakes = "\n".join([f"• {s}" for s in match.get("stakes", [])])
    recent = "\n".join([f"• {s}" for s in match.get("recent_form", [])])
    boot = "\n".join([f"• {s}" for s in match.get("golden_boot", [])])
    indi = "\n".join([f"• {s}" for s in match.get("individual_brilliance", [])])
    xfac = "\n".join([f"• {s}" for s in match.get("x_factor", [])])
    sharp = "\n".join([f"• {s}" for s in match.get("sharp_bettor", [])])

    model_lines = "\n".join(
        [
            f"• {match['model']['projected']}",
            f"• {match['model']['btts']}",
            f"• {match['model']['corners']}",
            f"• {match['model']['rec']}",
            f"• {match['model']['edge']}",
        ]
    )

    value = (
        f"**🎯 Stakes**\n{stakes}\n\n"
        f"**📈 Recent Form**\n{recent}\n"
        + (f"\n**🏆 Golden Boot / Brilliance**\n{boot}\n" if boot else "")
        + (f"\n**✨ Individual Focus**\n{indi}\n" if indi else "")
        + f"\n**🌡️ X-Factor (Context)**\n{xfac}\n\n"
        + f"**🎯 Sharp Bettor Reports**\n{sharp}\n\n"
        + f"**🤖 Model Snapshot**\n{model_lines}"
    )

    return {"name": header, "value": value[:1024], "inline": False}


def build_worldcup_qf_embed() -> Dict[str, Any]:
    # Norway vs England
    home1, away1 = "Norway", "England"
    p1 = _model_projection(home1, away1)

    field1: Dict[str, Any] = {
        "heading": "🇳🇴 Norway vs. 🏴󠁧󠁢󠁥󠁮󠁧󠁿 England",
        "time_meta": "5:00 PM EDT • Miami Stadium",
        "stakes": [
            "Norway’s first-ever men’s World Cup quarterfinal appearance.",
            "England looking to return to the semifinals for the first time since 2018.",
        ],
        "recent_form": [
            "Norway: stunning 2-1 upset over Brazil in the Round of 16.",
            "England: survived an epic 3-2 battle against Mexico to advance.",
        ],
        "golden_boot": [
            "Haaland: 7 goals",
            "Kane: 6 goals",
            "Jude Bellingham: 4 goals",
        ],
        "x_factor": [
            "Extreme heat in Miami: temperatures in the 90s (heat index ~108°F).",
            "Mandatory hydration breaks could disrupt pressing tempo and transition speed.",
        ],
        "sharp_bettor": [
            "Sharp money likely tracks the **Over (Total Goals)**: both teams produced high-scoring R16 matches (2-1 & 3-2).",
            "Norway’s plan of feeding Haaland quickly out wide has looked hard to defend against.",
        ],
        "model": {
            "projected": (
                f"Projected Goals: {home1} {p1['projected']['home_goals']} — {away1} {p1['projected']['away_goals']} "
                f"(Total {p1['projected']['total_goals']})"
            ),
            "btts": f"BTTS Probability: {p1['btts_probability'] * 100:.1f}%",
            "corners": f"Corner Projection: ~{p1['corner_projection']}",
            "rec": f"Model Rec: {p1['recommendation']} • Confidence {p1['confidence']:.1f}%",
            "edge": f"Model Edge (vs 2.5): {p1['edge']:+.2f}",
        },
    }

    # Argentina vs Switzerland
    home2, away2 = "Argentina", "Switzerland"
    p2 = _model_projection(home2, away2)

    field2: Dict[str, Any] = {
        "heading": "🇦🇷 Argentina vs. 🇨🇭 Switzerland",
        "time_meta": "9:00 PM EDT • Kansas City Stadium",
        "stakes": [
            "Defending champions Argentina face a Swiss team making its first quarterfinal appearance in 70 years.",
        ],
        "recent_form": [
            "Argentina: dramatic comeback vs Egypt (down 2-0, finished 3-2).",
            "Switzerland: grueling 0-0 vs Colombia, won 4-3 on penalties.",
        ],
        "individual_brilliance": [
            "Lionel Messi continues to lead the Golden Boot race alongside Haaland and Kylian Mbappé.",
        ],
        "x_factor": [
            "Early-game discipline likely decides the tone: Switzerland’s resilience suggests a tighter early phase.",
        ],
        "sharp_bettor": [
            "Switzerland’s defensive resilience points to a tighter game early (watch first-half flow).",
            "Argentina’s late-game surge could tempt **Second-Half Goals** or a live-bet Argentina angle if they trail early.",
        ],
        "model": {
            "projected": (
                f"Projected Goals: {home2} {p2['projected']['home_goals']} — {away2} {p2['projected']['away_goals']} "
                f"(Total {p2['projected']['total_goals']})"
            ),
            "btts": f"BTTS Probability: {p2['btts_probability'] * 100:.1f}%",
            "corners": f"Corner Projection: ~{p2['corner_projection']}",
            "rec": f"Model Rec: {p2['recommendation']} • Confidence {p2['confidence']:.1f}%",
            "edge": f"Model Edge (vs 2.5): {p2['edge']:+.2f}",
        },
    }

    return {
        "title": "📊 Deep Dive Match Analysis — World Cup Quarterfinals (2026)",
        "description": "Two-match rich cards with stakes, form, sharp-bettor angles, and model goal projections.",
        "color": 3066993,
        "fields": [_build_match_field(field1), _build_match_field(field2)],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "footer": {"text": "MultiSportPredict • World Cup QF • Smart Betting Guide"},
    }


def push() -> bool:
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url or webhook_url == "None":
        print("❌ DISCORD_WEBHOOK_URL not set")
        return False

    try:
        import requests
    except ImportError:
        print("❌ requests not installed")
        return False

    embed = build_worldcup_qf_embed()
    payload = {"embeds": [embed]}

    try:
        r = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        if r.status_code in (200, 204):
            print("✅ World Cup QF rich embed pushed")
            return True
        print(f"❌ Discord push failed: {r.status_code} {r.text[:200]}")
        return False
    except Exception as e:
        print(f"❌ Discord push exception: {e}")
        return False


if __name__ == "__main__":
    raise SystemExit(0 if push() else 1)

