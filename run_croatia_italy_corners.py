#!/usr/bin/env python
"""
Croatia U19 vs Italy U19 -- Corners Prediction
==============================================
Uses the existing SoccerPredictor corner strength model with the
user's provided recent corner data and style-of-play notes.
"""

import sys
import os
import json
import math
from pathlib import Path

# --- Force UTF-8 output for Windows terminal ---
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# --- Add project root to path ---
sys.path.insert(0, str(Path(__file__).resolve().parent))

from models.soccer_predictor import (
    team_corner_strength,
    estimate_corner_total,
    poisson_over_prob,
)
from core.confidence_engine import confidence_score

# ============================================================================
# USER-PROVIDED DATA
# ============================================================================

# Croatia U19 -- Last 5 tracked corner totals
croatia_corner_totals = [10, 7, 12, 16, 9]       # match totals
croatia_corners_for = [6, 4, 6, 14, 5]            # Croatia corners
croatia_corners_against = [4, 3, 6, 2, 4]         # opponent corners
avg_croatia_for = 7.0
avg_croatia_against = 3.8

# Italy U19 -- Limited data, key note: only 4 corners vs Georgia
# despite 21 total attempts. Style = central progression, low wing-play.
# We'll infer conservative corner generation.
italy_corners_for_vs_georgia = 4
italy_shots_vs_georgia = 21
avg_italy_for = 5.4
avg_italy_against = 5.0

# ============================================================================
# DERIVED METRICS
# ============================================================================

# Estimate shots, SOT, width/crossing, pressure based on corner data & style notes
# Croatia: average 7 corners/game suggests good attacking pressure, decent width
croatia_shots = 13.5          # higher corner count -> more shots
croatia_sot = 4.8
croatia_final_third_pressure = 0.70
croatia_width_crossing = 0.60  # modest width
croatia_tempo = 0.50

# Italy: only 4 corners from 21 shots = very low conversion, central play
# Style note: "relies heavily on central progression... suppresses corners"
italy_shots = 14.0            # lots of attempts, but central
italy_sot = 5.2
italy_final_third_pressure = 0.65  # still attack, but through middle
italy_width_crossing = 0.30        # LOW -- central progression kills corners
italy_tempo = 0.55

# ============================================================================
# GAME STATE CORRECTIONS (Youth tournament volatility)
# ============================================================================

must_win_home = 1  # Croatia at home
must_win_away = 1  # Italy in competitive fixture
weather_penalty = 0
referee_flow = 0

# ============================================================================
# CORNER STRENGTH CALCULATION
# ============================================================================

home_corner = team_corner_strength(
    shots=croatia_shots,
    sot=croatia_sot,
    final_third_pressure=croatia_final_third_pressure,
    width_crossing=croatia_width_crossing,
    tempo=croatia_tempo,
    home=1,
    missing_cb=0,
    missing_gk=0,
    missing_attacker=0,
)

away_corner = team_corner_strength(
    shots=italy_shots,
    sot=italy_sot,
    final_third_pressure=italy_final_third_pressure,
    width_crossing=italy_width_crossing,
    tempo=italy_tempo,
    home=0,
    missing_cb=0,
    missing_gk=0,
    missing_attacker=0,
)

corner_total = estimate_corner_total(
    home_corner_strength=home_corner,
    away_corner_strength=away_corner,
    weather_penalty=weather_penalty,
    referee_flow=referee_flow,
    must_win_home=must_win_home,
    must_win_away=must_win_away,
)

# ============================================================================
# CORNER PROBABILITIES (Poisson distribution)
# ============================================================================

p_over_85 = poisson_over_prob(corner_total, 8.5)
p_over_95 = poisson_over_prob(corner_total, 9.5)
p_over_105 = poisson_over_prob(corner_total, 10.5)
p_over_115 = poisson_over_prob(corner_total, 11.5)
p_under_85 = 1.0 - p_over_85
p_under_95 = 1.0 - p_over_95
p_under_105 = 1.0 - p_over_105

# Expected home vs away corners split
total_corner_strength = home_corner + away_corner
home_corner_share = home_corner / total_corner_strength if total_corner_strength > 0 else 0.55
home_corner_proj = corner_total * home_corner_share
away_corner_proj = corner_total * (1 - home_corner_share)

# ============================================================================
# CONFIDENCE SCORING
# ============================================================================

edge_85 = corner_total - 8.5
edge_95 = corner_total - 9.5
edge_105 = corner_total - 10.5

conf_85 = confidence_score(edge_85 * 10, volatility=0.55)
conf_95 = confidence_score(edge_95 * 10, volatility=0.55)
conf_105 = confidence_score(edge_105 * 10, volatility=0.55)

# ============================================================================
# OUTPUT
# ============================================================================

divider = "=" * 65
section = "-" * 65

print("=" * 65)
print("  CORNERS PREDICTION: Croatia U19 vs Italy U19")
print("  Youth International -- Live Match Analysis")
print("=" * 65)

print(f"\n{section}")
print("  CORNER STRENGTH METRICS (Model Inputs)")
print(section)
print(f"  {'Metric':<30} {'Croatia U19':<15} {'Italy U19':<15}")
print(f"  {'-'*28} {'-'*14} {'-'*14}")
print(f"  {'Avg Corners For':<30} {avg_croatia_for:<15.1f} {avg_italy_for:<15.1f}")
print(f"  {'Avg Corners Against':<30} {avg_croatia_against:<15.1f} {avg_italy_against:<15.1f}")
print(f"  {'Est. Shots/Game':<30} {croatia_shots:<15.1f} {italy_shots:<15.1f}")
print(f"  {'Width/Crossing (0-1)':<30} {croatia_width_crossing:<15.2f} {italy_width_crossing:<15.2f}")
print(f"  {'Final 3rd Pressure (0-1)':<30} {croatia_final_third_pressure:<15.2f} {italy_final_third_pressure:<15.2f}")
print(f"  {'Tempo (0-1)':<30} {croatia_tempo:<15.2f} {italy_tempo:<15.2f}")
print(f"  {'Corner Strength Score':<30} {home_corner:<15.2f} {away_corner:<15.2f}")

print(f"\n{section}")
print("  CORE PREDICTION")
print(section)
print(f"  Projected Total Corners:          {corner_total:.1f}")
print(f"  Projected Croatia U19 Corners:     {home_corner_proj:.1f}")
print(f"  Projected Italy U19 Corners:       {away_corner_proj:.1f}")
print(f"  Projected Corner Split (H/A):      {home_corner_share:.1%} / {(1-home_corner_share):.1%}")

print(f"\n{section}")
print("  MARKET PROBABILITIES (Poisson Model)")
print(section)
print(f"  {'Market':<16} {'Over':<20} {'Under':<20}")
print(f"  {'-'*14} {'-'*18} {'-'*18}")
print(f"  {'Over/Under 8.5':<16} {p_over_85:<20.1%} {p_under_85:<20.1%}")
print(f"  {'Over/Under 9.5':<16} {p_over_95:<20.1%} {p_under_95:<20.1%}")
print(f"  {'Over/Under 10.5':<16} {p_over_105:<20.1%} {p_under_105:<20.1%}")
print(f"  {'Over/Under 11.5':<16} {p_over_115:<20.1%} {1-p_over_115:<20.1%}")

print(f"\n{section}")
print("  BETTING EDGE ANALYSIS")
print(section)
print(f"  {'Market':<16} {'Edge':<15} {'Confidence':<15} {'Assessment':<15}")
print(f"  {'-'*14} {'-'*13} {'-'*13} {'-'*13}")
print(f"  {'Over 8.5':<16} {edge_85:<+15.2f} {conf_85:<15.1f} {'EDGE' if abs(edge_85) > 0.3 else 'NEUTRAL':<15}")
print(f"  {'Over 9.5':<16} {edge_95:<+15.2f} {conf_95:<15.1f} {'EDGE' if abs(edge_95) > 0.3 else 'NEUTRAL':<15}")
print(f"  {'Over 10.5':<16} {edge_105:<+15.2f} {conf_105:<15.1f} {'EDGE' if abs(edge_105) > 0.3 else 'NEUTRAL':<15}")

print(f"\n{section}")
print("  RECOMMENDATION & RATIONALE")
print(section)

# Determine recommendation
if corner_total >= 9.5:
    rec = f"OVER 9.5 TOTAL CORNERS (Projected: {corner_total:.1f})"
    rec_confidence = conf_95
elif corner_total >= 8.5:
    rec = f"OVER 8.5 TOTAL CORNERS (Projected: {corner_total:.1f})"
    rec_confidence = conf_85
else:
    rec = f"UNDER 8.5 TOTAL CORNERS (Projected: {corner_total:.1f})"
    rec_confidence = conf_85

print(f"  Recommendation:   {rec}")
print(f"  Confidence Level: {rec_confidence:.1f}%")
print()

# Key factors
print("  KEY FACTORS:")
print("  * Croatia U19 Corner Volume:   Croatia averages 7.0 corners FOR per game")
print("    (6, 4, 6, 14, 5) -- consistent volume even without Gibraltar outlier")
print("  * Italy U19 Corner Profile:    Italy's central playstyle suppresses corners")
print("    (only 4 corners from 21 shots vs Georgia). Their corner generation")
print("    is structurally low despite decent shot volume.")
print("  * Home Advantage:              Croatia at home adds ~0.3 to corner total")
print("    (home teams typically generate more attacking pressure)")
print("  * Youth Tournament Volatility: Youth U19 tournaments have high variance;")
print("    game state (who scores first) heavily impacts corner counts.")
print("    4 of Croatia's last 5 matches had 9+ total corners.")
print(f"  * Market Alignment:            Model projects {corner_total:.1f} corners")
if corner_total > 9.0:
    print(f"    value on OVER 9.5 if available at ~{p_over_95:.0%} implied probability")
else:
    print("    neutral to slightly under, monitor live game state")

print()
print("  DISCLAIMER: This is a statistical model based on limited data (5 tracked")
print("  matches for Croatia, 1 known match for Italy). Youth tournaments have")
print("  inherently high variance. Use as one input in your decision process.")
print("=" * 65)