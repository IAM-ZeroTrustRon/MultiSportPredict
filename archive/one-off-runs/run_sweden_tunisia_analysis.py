#!/usr/bin/env python
"""
Sweden vs. Tunisia - World Cup Group F Analysis
================================================
Based on pre-match metrics:
- Sweden: vulnerable favorite, counter-attacking style, turbulent qualifying
- Tunisia: flawless defensive record in CAF qualifying, 0 goals conceded in 10 matches
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from models.soccer_predictor import SoccerPredictor

def analyze_match():
    """Run Sweden vs. Tunisia through the soccer model with tailored inputs."""
    
    print("=" * 70)
    print("FIFA WORLD CUP - GROUP F ANALYSIS")
    print("Sweden vs. Tunisia")
    print(f"Kickoff: 10:00 PM EDT | Venue: Monterrey Stadium")
    print("=" * 70)
    print()
    
    # Create predictor with World Cup configuration
    predictor = SoccerPredictor(league="World Cup")
    
    # Based on pre-match analysis:
    # Sweden - counter-attacking style, poor qualifying form
    # Tunisia - defensive wall, 0 GA in 10 CAF qualifiers, low-block
    
    result = predictor.predict(
        features=None,
        model=None,
        home_team="Sweden",
        away_team="Tunisia",
        market_line=0.0,        # PK (pick'em)
        market_total=2.5,       # Standard total line
        league="World Cup",
        
        # ---- SWEDEN METRICS ----
        # Counter-attacking team, poor qualifying form
        home_xg_for=1.35,           # Below average attack (turbulent qualifying)
        home_xg_against=1.55,       # Poor defensively in qualifying
        home_shots=10.5,            # Lower shot volume (counter-attack)
        home_sot=3.5,               # Fewer shots on target
        home_goals_for=1.1,         # Low scoring in qualifying
        home_goals_against=1.5,     # Conceded frequently
        home_clean_sheets=3,        # Few clean sheets
        home_missing_attacker=0,
        home_missing_creator=0,
        home_missing_cb=0,
        home_missing_gk=0,
        home_tempo=0.35,            # Moderate tempo (counter-attack)
        home_width_crossing=0.40,
        home_final_third_pressure=0.35,  # Less pressure (counter-attacking)
        
        # ---- TUNISIA METRICS ----
        # Defensive wall, flawless qualifying
        away_xg_for=1.15,           # Low attacking output
        away_xg_against=0.45,       # ELITE defense (0 GA in 10 matches)
        away_shots=9.0,             # Lower shot volume
        away_sot=3.0,               # Few shots on target
        away_goals_for=1.0,         # Low scoring
        away_goals_against=0.3,     # Almost nothing conceded
        away_clean_sheets=8,        # Dominant clean sheet record
        away_missing_attacker=0,
        away_missing_creator=0,
        away_missing_cb=0,
        away_missing_gk=0,
        away_tempo=0.20,            # Low tempo (low-block, patient)
        away_width_crossing=0.35,
        away_final_third_pressure=0.30,  # Low attacking pressure
    )
    
    # ---- PRINT RESULTS ----
    game = result.get("game", {})
    predictions = result.get("predictions", {})
    goals = result.get("goals_analysis", {})
    btts = result.get("btts_probability", 0)
    
    sep = "-" * 60
    
    print(f"\n{sep}")
    print("MODEL PROJECTIONS")
    print(sep)
    print(f"  Projected Score:         Sweden {game.get('projected_home_goals', 0):.2f} - {game.get('projected_away_goals', 0):.2f} Tunisia")
    print(f"  Projected Total Goals:   {game.get('projected_total_goals', 0):.2f}")
    print()
    
    print(sep)
    print("MATCH OUTCOME PROBABILITIES")
    print(sep)
    print(f"  Sweden Win:              {game.get('home_win_prob', 0):.1%}")
    print(f"  Draw:                    {game.get('draw_prob', 0):.1%}")
    print(f"  Tunisia Win:             {game.get('away_win_prob', 0):.1%}")
    print(f"  Tunisia Double Chance:   {game.get('draw_prob', 0) + game.get('away_win_prob', 0):.1%}")
    print()
    
    print(sep)
    print("GOAL LINE ANALYSIS")
    print(sep)
    print(f"  Over 1.5:                {goals.get('over_15_prob', 0):.1%}")
    print(f"  Over 2.5:                {goals.get('over_25_prob', 0):.1%}")
    print(f"  Over 3.5:                {goals.get('over_35_prob', 0):.1%}")
    print(f"  Under 2.5:               {1 - goals.get('over_25_prob', 0):.1%}")
    print()
    
    print(sep)
    print("BETTING MARKETS")
    print(sep)
    side = predictions.get("side", {})
    total = predictions.get("total", {})
    btts_pred = predictions.get("btts", {})
    
    print(f"  Side (ML/Asian):")
    print(f"    Edge:                  {side.get('edge', 0):+.3f}")
    print(f"    Confidence:            {side.get('confidence', 0):.1f}%")
    print(f"    Recommendation:        {side.get('recommendation', 'N/A')}")
    print()
    print(f"  Total Goals (O/U 2.5):")
    print(f"    Edge:                  {total.get('edge', 0):+.3f}")
    print(f"    Confidence:            {total.get('confidence', 0):.1f}%")
    print(f"    Recommendation:        {total.get('recommendation', 'N/A')}")
    print()
    print(f"  Both Teams To Score:")
    print(f"    Probability:           {btts:.1%}")
    print(f"    Confidence:            {btts_pred.get('confidence', 0):.1f}%")
    print(f"    Recommendation:        {btts_pred.get('recommendation', 'N/A')}")
    print()
    
    print(sep)
    print("TEAM METRICS (used in model)")
    print(sep)
    tm = result.get("team_metrics", {})
    for side_name, metrics in tm.items():
        print(f"  {side_name.upper()}:")
        for key, val in metrics.items():
            print(f"    {key}: {val}")
        print()
    
    print(sep)
    print("VALUE ANALYSIS")
    print(sep)
    
    # Tunisia Double Chance assessment
    tun_dc_prob = game.get('draw_prob', 0) + game.get('away_win_prob', 0)
    print(f"  Tunisia Double Chance (Win or Draw): {tun_dc_prob:.1%}")
    if tun_dc_prob > 0.55:
        print(f"    [+] VALUE DETECTED - Tunisia DC at implied >55%")
    else:
        print(f"    [-] No significant edge on Tunisia DC")
    
    # Under assessment
    under_prob = 1 - goals.get('over_25_prob', 0)
    print(f"  Under 2.5 Goals: {under_prob:.1%}")
    if under_prob > 0.60:
        print(f"    [+] VALUE DETECTED - Under 2.5 at implied >60%")
    else:
        print(f"    [-] No significant edge on Under 2.5")
    
    print()
    print(sep)
    print(f"Model: Bivariate Poisson with Dixon-Coles adjustments")
    print(f"League Config: World Cup")
    print(f"Timestamp: {result.get('timestamp', 'N/A')}")
    print(sep)
    
    # Save output
    output_dir = Path("output/soccer")
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "sweden_vs_tunisia_worldcup.json"
    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nFull results saved to: {out_path}")
    
    return result


if __name__ == "__main__":
    analyze_match()