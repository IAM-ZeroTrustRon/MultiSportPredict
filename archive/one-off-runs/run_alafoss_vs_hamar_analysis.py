#!/usr/bin/env python
"""
Corners Market Analysis — Alafoss vs Hamar
Date: June 18, 2026
"""

from soccer.soccer_predict_game import run_soccer_game


def main():
    home_team = "Alafoss"
    away_team = "Hamar"

    print(f"=== CORNERS MARKET ANALYSIS: {home_team} vs {away_team} ===\n")

    result = run_soccer_game(
        home_team=home_team,
        away_team=away_team,
        market_line=2.5,
        market_total=2.5,
        market_corners=9.5,
        store_to_db=False,
    )

    corners = result.get("corners_analysis", {})
    print("\n=== CORNERS MARKET RESULT ===")
    print(f"Projected Total Corners: {corners.get('projected_total', 'N/A')}")
    print(f"Blended Total: {corners.get('blended_total', 'N/A')}")
    print(f"Edge vs 9.5: {corners.get('edge', 'N/A')}")
    print(f"Over 8.5 Probability: {corners.get('over_85_prob', 'N/A'):.1%}")
    print(f"Over 9.5 Probability: {corners.get('over_95_prob', 'N/A'):.1%}")
    print(f"Over 10.5 Probability: {corners.get('over_105_prob', 'N/A'):.1%}")
    print(f"Confidence: {corners.get('confidence', 'N/A'):.1f}%")
    print(f"Recommendation: {corners.get('recommendation', 'N/A')}")


if __name__ == "__main__":
    main()