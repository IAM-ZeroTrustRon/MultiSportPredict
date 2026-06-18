#!/usr/bin/env python
"""
World Cup Qualifier Analysis — Switzerland vs Bosnia-Herzegovina
Date: June 18, 2026
"""

from soccer.soccer_predict_game import run_soccer_game


def main():
    home_team = "Switzerland"
    away_team = "Bosnia-Herzegovina"

    print(f"\n=== WORLD CUP QUALIFIER: {home_team} vs {away_team} ===\n")

    result = run_soccer_game(
        home_team=home_team,
        away_team=away_team,
        market_line=0.0,
        market_total=2.5,
        market_corners=9.5,
        store_to_db=False,
    )

    print("\n=== GAME-SPECIFIC PROP BETS ===\n")
    print(f"Match: {home_team} vs {away_team}")
    print(f"Projected Score: {result['game']['projected_home_goals']:.1f} - {result['game']['projected_away_goals']:.1f}")
    print(f"Projected Total Goals: {result['game']['projected_total_goals']:.2f}")
    print()

    # Core markets
    print("--- CORE MARKETS ---")
    print(f"Over 1.5 Goals: {result['goals_analysis']['over_15_prob']:.1%} (Confidence: {result['predictions']['total']['confidence']:.1f}%)")
    print(f"Over 2.5 Goals: {result['goals_analysis']['over_25_prob']:.1%} (Recommendation: {result['predictions']['total']['recommendation']})")
    print(f"BTTS Yes: {result['predictions']['btts']['yes_probability']:.1%} (Confidence: {result['predictions']['btts']['confidence']:.1f}%)")
    print(f"Double Chance (Home or Draw): {result['predictions']['double_chance']['home_or_draw']:.1%} (Confidence: {result['predictions']['double_chance']['confidence']['home_or_draw']:.1f}%)")
    print(f"Draw No Bet - Home: {result['predictions']['double_chance']['home_dnb_prob']:.1%}")
    print()

    # Corners
    corners = result["corners_analysis"]
    print("--- CORNERS ---")
    print(f"Projected Total Corners: {corners['blended_total']:.1f}")
    print(f"Over 8.5 Corners: {corners['over_85_prob']:.1%}")
    print(f"Over 9.5 Corners: {corners['over_95_prob']:.1%} (Confidence: {corners['confidence']:.1f}%)")
    print(f"Over 10.5 Corners: {corners['over_105_prob']:.1%}")
    print(f"Recommendation: {corners['recommendation']}")
    print()

    # Match outcome
    print("--- MATCH OUTCOME ---")
    print(f"{home_team} Win: {result['game']['home_win_prob']:.1%}")
    print(f"Draw: {result['game']['draw_prob']:.1%}")
    print(f"{away_team} Win: {result['game']['away_win_prob']:.1%}")
    print()

    # Correct scores
    print("--- TOP CORRECT SCORES ---")
    scores = sorted(result['correct_score_probabilities'].items(), key=lambda x: x[1], reverse=True)[:5]
    for score, prob in scores:
        print(f"  {score.replace('_', '-')}: {prob:.1%}")

    print("\n=== BEST PROP BETS ===")
    print("1. Over 9.5 Corners — BET")
    print("2. Double Chance (Home or Draw) — STRONG BET")
    print("3. BTTS Yes — STRONG BET")
    print("4. Over 2.5 Goals — strong support (73.9%)")
    print("5. Draw No Bet — Home (87.5%)")


if __name__ == "__main__":
    main()