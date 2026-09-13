#!/usr/bin/env python
"""
Player Prop Analysis: San Francisco Giants vs Chicago Cubs
===========================================================
Using the BaseballPredictor's prop projection methods
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from models.baseball_predictor import BaseballPredictor, get_league_config
import json
from datetime import datetime

def analyze_player_props():
    """Generate player prop recommendations for Giants vs Cubs"""
    
    print("="*60)
    print("PLAYER PROP ANALYSIS")
    print("San Francisco Giants vs Chicago Cubs")
    print("="*60)
    
    predictor = BaseballPredictor()
    league_config = get_league_config("MLB")
    
    # Define sample pitcher matchups (would normally come from lineups)
    # Giants probable starter (estimated stats)
    giants_pitcher = {
        "name": "Giants SP",
        "handedness": "R",
        "k_rate": 0.24,
        "era": 3.85,
        "hr_per_9": 1.1,
        "bb_per_9": 2.8,
        "innings_proj": 5.5,
        "prop_line": 6.5,  # K line
    }
    
    # Cubs probable starter (estimated stats)
    cubs_pitcher = {
        "name": "Cubs SP",
        "handedness": "L",
        "k_rate": 0.22,
        "era": 4.20,
        "hr_per_9": 1.3,
        "bb_per_9": 3.2,
        "innings_proj": 5.0,
        "prop_line": 5.5,  # K line
    }
    
    # Team stats for opponent analysis
    giants_vs_L = {"k_rate_vs_L": 0.23, "hr_rate_vs_L": 0.035}
    cubs_vs_R = {"k_rate_vs_R": 0.25, "hr_rate_vs_R": 0.030}
    
    # Umpire factors (neutral)
    umpire = {"k_rate": 0.23}
    
    # Park factor (Oracle Park - pitcher friendly)
    oracle_park_factor = 0.92  # Suppresses offense
    
    print("\n--- PITCHER STRIKEOUT PROPS ---")
    
    # Giants pitcher K prop
    giants_k_prop = predictor.project_k_prop(
        pitcher_stats=giants_pitcher,
        opponent_stats=cubs_vs_R,
        umpire_stats=umpire,
        park_factor=oracle_park_factor
    )
    print(f"\nGiants SP Strikeouts (Line: {giants_pitcher['prop_line']}):")
    print(f"  Projection: {giants_k_prop['projection']}")
    print(f"  Edge: {giants_k_prop['edge']}")
    print(f"  Lean: {giants_k_prop['lean']}")
    
    # Cubs pitcher K prop
    cubs_k_prop = predictor.project_k_prop(
        pitcher_stats=cubs_pitcher,
        opponent_stats=giants_vs_L,
        umpire_stats=umpire,
        park_factor=oracle_park_factor
    )
    print(f"\nCubs SP Strikeouts (Line: {cubs_pitcher['prop_line']}):")
    print(f"  Projection: {cubs_k_prop['projection']}")
    print(f"  Edge: {cubs_k_prop['edge']}")
    print(f"  Lean: {cubs_k_prop['lean']}")
    
    print("\n--- HITTER HOME RUN PROPS ---")
    
    # Sample Giants hitters
    giants_hitters = [
        {
            "name": "Matt Chapman",
            "handedness": "R",
            "hr_rate_vs_L": 0.045,
            "barrel_rate": 0.08,
            "hard_hit_rate": 0.42,
            "prop_line": 0.5,  # HR Yes/No
        },
        {
            "name": "Jung Hoo Lee",
            "handedness": "L",
            "hr_rate_vs_L": 0.025,
            "barrel_rate": 0.05,
            "hard_hit_rate": 0.35,
            "prop_line": 0.5,
        },
    ]
    
    # Sample Cubs hitters
    cubs_hitters = [
        {
            "name": "Seiya Suzuki",
            "handedness": "R",
            "hr_rate_vs_R": 0.040,
            "barrel_rate": 0.07,
            "hard_hit_rate": 0.40,
            "prop_line": 0.5,
        },
        {
            "name": "Ian Happ",
            "handedness": "S",
            "hr_rate_vs_R": 0.038,
            "barrel_rate": 0.06,
            "hard_hit_rate": 0.38,
            "prop_line": 0.5,
        },
    ]
    
    # Weather conditions (assuming dome/indoor or good weather)
    weather = {
        "wind_speed": 5,
        "temperature": 72,
        "wind_direction_factor": 0.0,  # Neutral
    }
    
    print("\n--- TOP HR CANDIDATES ---")
    
    hr_recommendations = []
    
    for hitter in giants_hitters:
        hr_prop = predictor.project_hr_prop(
            hitter_stats=hitter,
            pitcher_stats=cubs_pitcher,
            park_factor=oracle_park_factor,
            weather=weather
        )
        print(f"\n{hitter['name']} HR (vs LHP):")
        print(f"  Probability: {hr_prop['hr_probability']:.1%}")
        print(f"  Lean: {hr_prop['lean']}")
        hr_recommendations.append({
            "player": hitter['name'],
            "team": "Giants",
            "hr_probability": hr_prop['hr_probability'],
            "lean": hr_prop['lean']
        })
    
    for hitter in cubs_hitters:
        hr_prop = predictor.project_hr_prop(
            hitter_stats=hitter,
            pitcher_stats=giants_pitcher,
            park_factor=oracle_park_factor,
            weather=weather
        )
        print(f"\n{hitter['name']} HR (vs RHP):")
        print(f"  Probability: {hr_prop['hr_probability']:.1%}")
        print(f"  Lean: {hr_prop['lean']}")
        hr_recommendations.append({
            "player": hitter['name'],
            "team": "Cubs",
            "hr_probability": hr_prop['hr_probability'],
            "lean": hr_prop['lean']
        })
    
    # Summary recommendations
    print("\n" + "="*60)
    print("TOP PROP RECOMMENDATIONS")
    print("="*60)
    
    # Best K prop
    best_k_prop = giants_k_prop if abs(giants_k_prop['edge']) > abs(cubs_k_prop['edge']) else cubs_k_prop
    print(f"\nBest K Prop: {best_k_prop['lean']} {best_k_prop['projection']:.1f} (Edge: {best_k_prop['edge']:+.2f})")
    
    # Best HR candidate
    best_hr = max(hr_recommendations, key=lambda x: x['hr_probability'])
    print(f"Best HR Candidate: {best_hr['player']} ({best_hr['team']}) - {best_hr['hr_probability']:.1%} probability")
    
    # Overall lean
    print(f"\nOverall Game Lean: Under 8.5 (Oracle Park suppresses offense)")
    
    # Save results
    prop_analysis = {
        "match": "San Francisco Giants vs Chicago Cubs",
        "timestamp": datetime.now().isoformat(),
        "league": "MLB",
        "park": "Oracle Park",
        "park_factor": oracle_park_factor,
        "pitcher_props": {
            "giants_sp": giants_k_prop,
            "cubs_sp": cubs_k_prop,
        },
        "hitter_props": hr_recommendations,
        "top_recommendations": {
            "best_k_prop": {
                "lean": best_k_prop['lean'],
                "projection": best_k_prop['projection'],
                "edge": best_k_prop['edge']
            },
            "best_hr_candidate": best_hr,
            "game_lean": "Under 8.5"
        }
    }
    
    output_dir = Path("output/baseball")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "giants_cubs_props.json"
    with open(output_path, 'w') as f:
        json.dump(prop_analysis, f, indent=2)
    
    print(f"\nDetailed prop analysis saved to: {output_path}")
    
    return prop_analysis

if __name__ == "__main__":
    result = analyze_player_props()