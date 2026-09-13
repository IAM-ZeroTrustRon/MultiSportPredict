#!/usr/bin/env python
"""
Live Match Analysis: San Martin Tucuman vs Quilmes
===================================================
Current Score: 0-0 (19th minute)
League: Primera Nacional (Argentina)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from models.soccer_predictor import SoccerPredictor
from core import store_prediction
import json
from datetime import datetime

def analyze_live_match():
    """Analyze the live match between San Martin Tucuman and Quilmes"""
    
    print("="*60)
    print("LIVE MATCH ANALYSIS")
    print("San Martin Tucuman vs Quilmes")
    print("Current Score: 0-0 (19th minute)")
    print("League: Primera Nacional (Argentina)")
    print("="*60)
    
    # Create predictor with Argentina league config
    predictor = SoccerPredictor(league="Primera Nacional")
    
    # Since this is a live match, we'll use placeholder team metrics
    # In a real scenario, these would come from live data feeds
    # or pre-match analysis adjusted for current game state
    
    # Estimated team metrics (would normally come from database/API)
    result = predictor.predict(
        features=None,
        model=None,
        home_team="San Martin Tucuman",
        away_team="Quilmes",
        market_line=0.0,  # Draw no bet line
        market_total=2.25,  # Lower total for Argentine second division
        # Home team metrics (estimated)
        home_xg_for=1.35,
        home_xg_against=1.15,
        home_shots=11.0,
        home_sot=3.5,
        home_goals_for=1.2,
        home_goals_against=1.0,
        home_clean_sheets=3,
        home_missing_attacker=0,
        home_missing_creator=0,
        home_missing_cb=0,
        home_missing_gk=0,
        home_tempo=0.3,
        home_width_crossing=0.45,
        home_final_third_pressure=0.50,
        # Away team metrics (estimated)
        away_xg_for=1.25,
        away_xg_against=1.30,
        away_shots=10.0,
        away_sot=3.2,
        away_goals_for=1.1,
        away_goals_against=1.2,
        away_clean_sheets=2,
        away_missing_attacker=0,
        away_missing_creator=1,  # Estimated missing creator
        away_missing_cb=0,
        away_missing_gk=0,
        away_tempo=0.25,
        away_width_crossing=0.40,
        away_final_third_pressure=0.45,
    )
    
    # Adjust for live game state (19 minutes played, 0-0)
    # Time decay factor for remaining time
    minutes_played = 19
    remaining_factor = (90 - minutes_played) / 90.0
    
    print(f"\n--- LIVE ADJUSTMENTS (After {minutes_played} minutes) ---")
    print(f"Time remaining: {remaining_factor:.1%}")
    
    # Adjust projections based on time remaining
    adjusted_home_goals = result['game']['projected_home_goals'] * remaining_factor
    adjusted_away_goals = result['game']['projected_away_goals'] * remaining_factor
    adjusted_total = adjusted_home_goals + adjusted_away_goals
    
    print(f"\n--- ADJUSTED PROJECTIONS (Remaining Time) ---")
    print(f"San Martin Tucuman: {adjusted_home_goals:.2f} expected goals")
    print(f"Quilmes: {adjusted_away_goals:.2f} expected goals")
    print(f"Total expected goals (remaining): {adjusted_total:.2f}")
    
    # Calculate live win probabilities
    # With 0-0 at 19 minutes, draw probability increases
    home_win_prob = result['game']['home_win_prob'] * remaining_factor * 0.9
    away_win_prob = result['game']['away_win_prob'] * remaining_factor * 0.9
    draw_prob = 1 - (home_win_prob + away_win_prob)
    
    # Normalize
    total_prob = home_win_prob + away_win_prob + draw_prob
    home_win_prob /= total_prob
    away_win_prob /= total_prob
    draw_prob /= total_prob
    
    print(f"\n--- LIVE MATCH PROBABILITIES ---")
    print(f"San Martin Tucuman Win: {home_win_prob:.1%}")
    print(f"Draw: {draw_prob:.1%}")
    print(f"Quilmes Win: {away_win_prob:.1%}")
    
    # Betting recommendations
    print(f"\n--- LIVE BETTING RECOMMENDATIONS ---")
    
    # Under is more likely given low-scoring nature and time elapsed
    if adjusted_total < 1.5:
        print("UNDER 2.25 - Strong lean (only ~1.3 goals expected in remaining time)")
    elif adjusted_total < 2.0:
        print("UNDER 2.25 - Moderate lean")
    else:
        print("No strong total recommendation")
    
    # Home advantage still relevant
    if home_win_prob > 0.40:
        print(f"San Martin Tucuman DNB - Moderate confidence ({home_win_prob:.1%})")
    
    # Draw is most likely single outcome
    if draw_prob > 0.35:
        print(f"DRAW - Highest single outcome probability ({draw_prob:.1%})")
    
    # Store prediction
    live_result = {
        "match": "San Martin Tucuman vs Quilmes",
        "league": "Primera Nacional",
        "status": "LIVE",
        "minute": minutes_played,
        "current_score": "0-0",
        "timestamp": datetime.now().isoformat(),
        "original_projections": result,
        "live_adjustments": {
            "remaining_factor": round(remaining_factor, 3),
            "adjusted_home_goals": round(adjusted_home_goals, 2),
            "adjusted_away_goals": round(adjusted_away_goals, 2),
            "adjusted_total": round(adjusted_total, 2),
            "live_win_probabilities": {
                "home": round(home_win_prob, 3),
                "draw": round(draw_prob, 3),
                "away": round(away_win_prob, 3),
            }
        }
    }
    
    # Save to output
    output_dir = Path("output/soccer")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "sanmartin_vs_quilmes_live.json"
    with open(output_path, 'w') as f:
        json.dump(live_result, f, indent=2, default=str)
    
    print(f"\nResults saved to: {output_path}")
    
    # Try to store in database
    try:
        store_prediction("soccer", live_result)
        print("Prediction stored in database")
    except Exception as e:
        print(f"Could not store in database: {e}")
    
    return live_result

if __name__ == "__main__":
    result = analyze_live_match()