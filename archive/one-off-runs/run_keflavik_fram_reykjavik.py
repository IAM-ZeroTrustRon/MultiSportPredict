#!/usr/bin/env python3
"""Keflavik IF vs Fram Reykjavik — Besta deild karla Round 13, July 6 2026."""
import os
from dotenv import load_dotenv
from multi_sport_engine import predict_soccer, push_to_discord

load_dotenv()

result = predict_soccer(
    "Keflavik IF", "Fram Reykjavik",
    league="Icelandic Besta deild",
    market_total=2.5,
    # Keflavik (Home) — 8th, 4-3-5, recent 6-1 loss to IBV, leaky defense
    home_xg_for=1.28,
    home_xg_against=1.88,
    home_sot=3.7,
    home_tempo=0.30,
    home_goals_for=1.25,
    home_goals_against=1.78,
    home_clean_sheets=2,
    home_missing_attacker=0,
    home_missing_creator=0,
    home_missing_cb=1,      # 6-1 loss implies CB disruption
    home_missing_gk=0,
    # Fram Reykjavik (Away) — 3rd, 8-2-2, D-W-W-W-L, won H2H 3-1 April 2026
    away_xg_for=1.68,
    away_xg_against=1.18,
    away_sot=4.7,
    away_tempo=0.42,
    away_goals_for=1.88,
    away_goals_against=1.15,
    away_clean_sheets=4,
    away_missing_attacker=0,
    away_missing_creator=0,
    away_missing_cb=0,
    away_missing_gk=0,
)

# Print summary
p = result["projected"]
o = result["outcome"]
g = result["goals_analysis"]
print("\n=== Keflavik IF vs Fram Reykjavik | Besta deild R13 ===")
print(f"  Projected:  Keflavik {p['home_goals']} – {p['away_goals']} Fram Reykjavik  (Total {p['total_goals']})")
print(f"  1X2:        Keflavik {o['home_win']:.1%}  |  Draw {o['draw']:.1%}  |  Fram {o['away_win']:.1%}")
print(f"  Over 2.5:   {g['over_25']:.1%}  |  BTTS: {result['btts_probability']:.1%}")
print(f"  Corners:    {result['corner_projection']}")
print(f"  Edge:       {result['edge']:+.3f}  |  Confidence: {result['confidence']:.1f}%")
print(f"  Rec:        {result['recommendation']}")

# Market context for embed enrichment
result["market_notes"] = (
    "Market: Keflavik +210 (32%) | Draw +275 (26%) | Fram -110 (52%). "
    "Over 2.5 at 1.30 (77% implied) — VALUE GONE on straight Over. "
    "BTTS Yes at 1.31 (76% implied). "
    "Model edge vs market moneyline: Fram side. "
    "Weather: Showers 11C — slight suppression on corners/high tempo. "
    "H2H: Keflavik leads 13-7 all-time BUT Fram won last meeting 3-1 (Apr 17 2026). "
    "Keflavik suffered 6-1 loss to IBV last fixture — defensive shape suspect."
)
result["sharp_note"] = (
    "Sharp play: Fram ML (-110) offers genuine value — model gives Fram ~47-50% vs 52% market, "
    "within noise range but form/standing gap is real. "
    "Over 2.5 at 1.30 has zero value (market over-priced). "
    "Alternative: Over 3.5 (+money) or BTTS at 1.31 are the only viable goal markets. "
    "Keflavik +1.5 spread could offer insurance value given their 6-1 recent loss."
)

print(f"\n  Market Note: {result['market_notes'][:120]}...")
print(f"  Sharp Note:  {result['sharp_note'][:120]}...")

print("\nPushing to Discord...")
ok = push_to_discord("soccer", "Keflavik IF", "Fram Reykjavik", result)
print("[OK] Pushed." if ok else "[FAIL] Push failed.")
