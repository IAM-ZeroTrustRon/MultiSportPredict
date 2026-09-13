#!/usr/bin/env python
"""
Live Match Deep Dive Analysis — Mexico vs South Korea
Date: June 18, 2026 — World Cup Group B
Live Stats Integrated
"""

from soccer.soccer_predict_game import run_soccer_game


def main():
    home_team = "Mexico"
    away_team = "South Korea"

    print(f"\n{'='*80}")
    print(f"LIVE MATCH DEEP DIVE: {home_team} vs {away_team}")
    print(f"World Cup Group B — June 18, 2026")
    print(f"{'='*80}\n")

    result = run_soccer_game(
        home_team=home_team,
        away_team=away_team,
        market_line=0.0,
        market_total=2.5,
        market_corners=9.5,
        store_to_db=False,
    )

    # Live match statistics provided by user
    live_stats = {
        "possession": {"home": 47, "away": 53},
        "total_shots": {"home": 3, "away": 2},
        "shots_off_target": {"home": 1, "away": 1},
        "shots_on_target": {"home": 0, "away": 0},
        "blocked_shots": {"home": 0, "away": 1},
        "penalties": {"home": 0, "away": 0},
        "offsides": {"home": 2, "away": 4},
        "fouls": {"home": 4, "away": 4},
        "yellow_cards": {"home": 0, "away": 1},
        "red_cards": {"home": 0, "away": 0},
        "total_passes": {"home": 265, "away": 300},
        "key_passes": {"home": 2, "away": 1},
        "accurate_passes": {"home": 224, "away": 256},
        "pass_accuracy": {"home": 84, "away": 85},
        "accurate_crosses": {"home": 2, "away": 0},
        "cross_accuracy": {"home": 50, "away": 0},
        "accurate_long_balls": {"home": 8, "away": 12},
        "long_ball_accuracy": {"home": 25, "away": 33},
        "tackles": {"home": 8, "away": 10},
        "interceptions": {"home": 2, "away": 2},
        "clearances": {"home": 4, "away": 7},
        "saves": {"home": 0, "away": 1},
    }

    print("\n" + "="*80)
    print("LIVE MATCH STATISTICS")
    print("="*80)

    print(f"\nBall Possession:")
    print(f"  {home_team}: {live_stats['possession']['home']}%")
    print(f"  {away_team}: {live_stats['possession']['away']}%")

    print(f"\nShooting:")
    print(f"  Total Shots: {live_stats['total_shots']['home']} - {live_stats['total_shots']['away']}")
    print(f"  Shots on Target: {live_stats['shots_on_target']['home']} - {live_stats['shots_on_target']['away']}")
    print(f"  Shots off Target: {live_stats['shots_off_target']['home']} - {live_stats['shots_off_target']['away']}")
    print(f"  Blocked Shots: {live_stats['blocked_shots']['home']} - {live_stats['blocked_shots']['away']}")

    print(f"\nDiscipline:")
    print(f"  Fouls: {live_stats['fouls']['home']} - {live_stats['fouls']['away']}")
    print(f"  Offsides: {live_stats['offsides']['home']} - {live_stats['offsides']['away']}")
    print(f"  Yellow Cards: {live_stats['yellow_cards']['home']} - {live_stats['yellow_cards']['away']}")
    print(f"  Red Cards: {live_stats['red_cards']['home']} - {live_stats['red_cards']['away']}")

    print(f"\nPassing:")
    print(f"  Total Passes: {live_stats['total_passes']['home']} - {live_stats['total_passes']['away']}")
    print(f"  Accurate Passes: {live_stats['accurate_passes']['home']} ({live_stats['pass_accuracy']['home']}%) - {live_stats['accurate_passes']['away']} ({live_stats['pass_accuracy']['away']}%)")
    print(f"  Key Passes: {live_stats['key_passes']['home']} - {live_stats['key_passes']['away']}")
    print(f"  Accurate Crosses: {live_stats['accurate_crosses']['home']} ({live_stats['cross_accuracy']['home']}%) - {live_stats['accurate_crosses']['away']} ({live_stats['cross_accuracy']['away']}%)")
    print(f"  Accurate Long Balls: {live_stats['accurate_long_balls']['home']} ({live_stats['long_ball_accuracy']['home']}%) - {live_stats['accurate_long_balls']['away']} ({live_stats['long_ball_accuracy']['away']}%)")

    print(f"\nDefensive:")
    print(f"  Tackles: {live_stats['tackles']['home']} - {live_stats['tackles']['away']}")
    print(f"  Interceptions: {live_stats['interceptions']['home']} - {live_stats['interceptions']['away']}")
    print(f"  Clearances: {live_stats['clearances']['home']} - {live_stats['clearances']['away']}")
    print(f"  Saves: {live_stats['saves']['home']} - {live_stats['saves']['away']}")

    print("\n" + "="*80)
    print("MATCH CONTEXT ANALYSIS")
    print("="*80)

    # Analyze patterns
    print("\n--- Possession & Style ---")
    if live_stats['possession']['away'] > live_stats['possession']['home']:
        print(f"  {away_team} dominating possession ({live_stats['possession']['away']}% vs {live_stats['possession']['home']}%)")
    else:
        print(f"  {home_team} controlling tempo ({live_stats['possession']['home']}% vs {live_stats['possession']['away']}%)")

    # Shooting efficiency
    print("\n--- Shooting Efficiency ---")
    total_shots = live_stats['total_shots']['home'] + live_stats['total_shots']['away']
    shots_on_target = live_stats['shots_on_target']['home'] + live_stats['shots_on_target']['away']
    if total_shots > 0:
        sot_pct = (shots_on_target / total_shots) * 100
        print(f"  Total Shots: {total_shots} | Shots on Target: {shots_on_target} ({sot_pct:.0f}%)")

    # Passing quality
    print("\n--- Passing Quality ---")
    pass_diff = live_stats['pass_accuracy']['away'] - live_stats['pass_accuracy']['home']
    if abs(pass_diff) < 2:
        print(f"  Even passing accuracy: {home_team} {live_stats['pass_accuracy']['home']}% vs {away_team} {live_stats['pass_accuracy']['away']}%")
    elif pass_diff > 0:
        print(f"  {away_team} more accurate in passing ({live_stats['pass_accuracy']['away']}% vs {live_stats['pass_accuracy']['home']}%)")
    else:
        print(f"  {home_team} more accurate in passing ({live_stats['pass_accuracy']['home']}% vs {live_stats['pass_accuracy']['away']}%)")

    # Tactical approach
    print("\n--- Tactical Approach ---")
    if live_stats['accurate_long_balls']['away'] > live_stats['accurate_long_balls']['home']:
        print(f"  {away_team} using more direct approach ({live_stats['accurate_long_balls']['away']} long balls vs {live_stats['accurate_long_balls']['home']})")
    if live_stats['accurate_crosses']['home'] > 0:
        print(f"  {home_team} using width with {live_stats['accurate_crosses']['home']} accurate crosses")

    # Defensive actions
    print("\n--- Defensive Activity ---")
    total_tackles = live_stats['tackles']['home'] + live_stats['tackles']['away']
    total_clearances = live_stats['clearances']['home'] + live_stats['clearances']['away']
    print(f"  Tackles: {total_tackles} total | Clearances: {total_clearances} total")
    if live_stats['tackles']['away'] > live_stats['tackles']['home']:
        print(f"  {away_team} more engaged defensively ({live_stats['tackles']['away']} tackles)")

    print("\n" + "="*80)
    print("MODEL RECOMMENDATIONS")
    print("="*80)

    corners = result["corners_analysis"]
    print(f"\nCorners Market:")
    print(f"  Projected Total: {corners['blended_total']:.1f}")
    print(f"  Over 9.5: {corners['over_95_prob']:.1%}")
    print(f"  Recommendation: {corners['recommendation']} (Confidence: {corners['confidence']:.1f}%)")

    print(f"\nGoals Market:")
    print(f"  Over 2.5: {result['goals_analysis']['over_25_prob']:.1%}")
    print(f"  Over 1.5: {result['goals_analysis']['over_15_prob']:.1%}")

    print(f"\nBTTS:")
    print(f"  Probability: {result['predictions']['btts']['yes_probability']:.1%}")
    print(f"  Recommendation: {result['predictions']['btts']['recommendation']}")

    print(f"\nDouble Chance (Home or Draw):")
    print(f"  Probability: {result['predictions']['double_chance']['home_or_draw']:.1%}")
    print(f"  Recommendation: {result['predictions']['double_chance']['confidence']['home_or_draw']:.1f}% confidence")


if __name__ == "__main__":
    main()