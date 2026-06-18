"""
Soccer prediction module for MultiSportPredict
Enhanced with referee data hooks and historical storage.
Maintains all sophisticated existing prediction logic.
"""

from typing import Any, Dict, Optional


def fetch_soccer_ref_data(home: str, away: str) -> Dict[str, Any]:
    """
    Fetch referee data for a soccer match.
    
    This is a placeholder that should be integrated with real data sources
    like Transfermarkt, PlayerStats, Flashscore, or official league data.
    
    Returns:
        Dictionary with referee statistics
    """
    # TODO: Integrate with real referee data API
    # Real implementation would call:
    # - Transfermarkt for referee assignment and history
    # - Official league data for card tendencies
    # - Flashscore for real-time referee stats
    
    return {
        "yellow_cards_per_game": 4.2,     # Average yellow cards per game
        "red_cards_per_game": 0.25,       # Average red cards per game
        "penalties_per_game": 0.18,       # Average penalties awarded per game
        "home_card_diff": -0.3,           # Home vs away card differential
        "fouls_per_game": 22.5,           # Average fouls per game
        "strictness_rating": 0.65,        # Referee strictness (0-1)
    }


def run_soccer_game(
    home_team: str, 
    away_team: str,
    market_line: float = 0.25,
    market_total: float = 2.5,
    market_corners: float = 9.5,
    store_to_db: bool = True,
):
    """
    Run soccer prediction for a matchup with enhanced features.
    
    Args:
        home_team: Home team name
        away_team: Away team name
        market_line: Current market Asian handicap line
        market_total: Current market total goals line
        market_corners: Current market total corners line
        store_to_db: Whether to store prediction to database
        
    Returns:
        Dictionary with comprehensive prediction results
    """
    from pathlib import Path
    import json
    from core import (
        confidence_score,
        bet_recommendation,
        store_prediction,
        schema_soccer,
    )
    
    print(f"\n=== SOCCER: {home_team} vs {away_team} ===\n")
    
    # Use the existing MultiSportModel for sophisticated predictions
    from MultiSportModel import (
        estimate_team_goals,
        estimate_btts_prob,
        poisson_over_prob,
        team_corner_strength,
        estimate_corner_total,
    )
    from core.utils import poisson_pmf
    
    # Fetch external data (referee)
    ref_data = fetch_soccer_ref_data(home_team, away_team)
    
    # Default team data (in production, these would come from your data pipeline)
    # Includes corner-specific metrics for recalibrated projection
    # DINAMO TBILISI (HOME) vs SAMGURALI TSKALTUBO (AWAY)
    home_data = {
        'xg_for': 1.35,  # Lower due to home struggles (1.00 goals/game)
        'xg_against': 1.25,
        'shots': 14.5,  # High volume but low quality
        'sot': 3.8,  # Severely lack finishing quality
        'goals_for': 1.0,  # Home scoring drought
        'goals_against': 1.2,
        'clean_sheets': 2,
        'missing_attacker': 0,
        'missing_creator': 0,
        'missing_cb': 0,
        'missing_gk': 0,
        'tempo': 0.2,  # Slow, sterile possession
        'width_crossing': 0.60,  # Low-percentage crosses inflating corners
        'final_third_pressure': 2.84,  # Attacking pressure rating (non-threatening)
        'corners_for': 5.7,
        'corners_against': 4.2,
        'possession_pct': 51.0,
        'corner_gen_style': 'possession',  # Holds ball, frustrated crossing
    }
    
    away_data = {
        'xg_for': 1.55,  # Efficient in transition
        'xg_against': 1.50,  # Porous defense (1.59 goals/game)
        'shots': 12.0,
        'sot': 4.2,
        'goals_for': 1.6,  # Hot form, efficient offense
        'goals_against': 1.6,
        'clean_sheets': 1,
        'missing_attacker': 0,
        'missing_creator': 0,
        'missing_cb': 0,
        'missing_gk': 0,
        'tempo': 0.35,  # Fast transitions
        'width_crossing': 0.55,
        'final_third_pressure': 0.50,
        'corners_for': 5.7,
        'corners_against': 4.8,
        'possession_pct': 49.0,
        'corner_gen_style': 'counter',  # Fast-break corner generation
    }
    
    # Calculate expected goals using sophisticated model
    home_lam = estimate_team_goals(
        home_data['xg_for'], home_data['sot'], home_data['tempo'], 1,
        home_data['missing_attacker'], home_data['missing_creator'],
        away_data['xg_against'], away_data['missing_cb'], away_data['missing_gk']
    )
    away_lam = estimate_team_goals(
        away_data['xg_for'], away_data['sot'], away_data['tempo'], 0,
        away_data['missing_attacker'], away_data['missing_creator'],
        home_data['xg_against'], home_data['missing_cb'], home_data['missing_gk']
    )
    total_lam = home_lam + away_lam
    
    # Adjust total based on referee penalty tendency
    penalty_adjustment = ref_data["penalties_per_game"] * 0.4  # Each penalty ~0.4 expected goals
    adjusted_total = total_lam + penalty_adjustment
    
    # BTTS probability
    btts_prob = estimate_btts_prob(home_data['xg_for'], away_data['xg_for'], 0, 0)
    
    # Corners analysis - RECALIBRATED MATHEMATICAL PROJECTION
    # Cross-calculate: team offense vs opponent defense
    home_corner_strength = team_corner_strength(
        home_data['shots'], home_data['sot'], home_data['final_third_pressure'],
        home_data['width_crossing'], home_data['tempo'], 1,
        home_data['missing_cb'], home_data['missing_gk'], home_data['missing_attacker']
    )
    away_corner_strength = team_corner_strength(
        away_data['shots'], away_data['sot'], away_data['final_third_pressure'],
        away_data['width_crossing'], away_data['tempo'], 0,
        away_data['missing_cb'], away_data['missing_gk'], away_data['missing_attacker']
    )
    corner_total = estimate_corner_total(
        home_corner_strength, away_corner_strength,
        0, 0, 0, 0  # weather_penalty, referee_flow, must_win_home, must_win_away
    )
    
    # Recalibrated projection: offense vs opponent defense
    home_corners_recal = (home_data['corners_for'] + away_data['corners_against']) / 2
    away_corners_recal = (away_data['corners_for'] + home_data['corners_against']) / 2
    recalibrated_total = home_corners_recal + away_corners_recal
    
    # Blend model and recalibrated (60% recalibrated, 40% model)
    blended_corner_total = 0.6 * recalibrated_total + 0.4 * corner_total
    
    # Use blended total for probabilities
    p_corners_85 = poisson_over_prob(blended_corner_total, 8.5)
    p_corners_95 = poisson_over_prob(blended_corner_total, 9.5)
    p_corners_105 = poisson_over_prob(blended_corner_total, 10.5)
    
    if market_corners <= 8.5:
        corners_prob = p_corners_85
    elif market_corners <= 9.5:
        corners_prob = p_corners_95
    else:
        corners_prob = p_corners_105
    corners_edge = corner_total - market_corners
    corners_confidence = confidence_score(corners_edge, volatility=0.60)
    corners_rec = bet_recommendation(corners_confidence)
    
    # Goal probabilities with adjusted total
    p_over_15 = poisson_over_prob(adjusted_total, 1.5)
    p_over_25 = poisson_over_prob(adjusted_total, 2.5)
    p_over_35 = poisson_over_prob(adjusted_total, 3.5)
    
    # Match outcome probabilities (1X2)
    home_win_prob = home_lam / (home_lam + away_lam) * 0.85 + 0.10
    away_win_prob = away_lam / (home_lam + away_lam) * 0.05 + 0.05
    draw_prob = 1 - home_win_prob - away_win_prob
    
    # Double Chance
    home_or_draw = home_win_prob + draw_prob
    draw_or_away = draw_prob + away_win_prob
    
    # Draw No Bet
    home_dnb_prob = home_win_prob / (home_win_prob + away_win_prob) if (home_win_prob + away_win_prob) > 0 else 0.5
    away_dnb_prob = 1 - home_dnb_prob
    
    # Both Teams to Score - Yes/No
    btts_yes_prob = btts_prob
    btts_no_prob = 1 - btts_prob
    
    # Calculate confidence scores for betting markets
    side_edge = (home_lam - away_lam) - market_line
    total_edge = adjusted_total - market_total
    btts_edge = btts_prob - 0.5
    
    # Use confidence engine with sport-specific volatilities
    side_confidence = confidence_score(
        side_edge, 
        volatility=0.50,  # Soccer sides volatility
        market_alignment=0.0
    )
    total_confidence = confidence_score(
        total_edge, 
        volatility=0.55,  # Soccer totals volatility
        market_alignment=0.0
    )
    btts_confidence = confidence_score(
        btts_edge * 100,  # Scale probability edge
        volatility=0.48,  # BTTS volatility
        market_alignment=0.0
    )
    
    # Double Chance confidence
    dc_home_edge = home_or_draw - 0.75
    dc_away_edge = draw_or_away - 0.75
    dc_home_confidence = confidence_score(dc_home_edge * 100, volatility=0.52)
    dc_away_confidence = confidence_score(dc_away_edge * 100, volatility=0.52)
    
    side_rec = bet_recommendation(side_confidence)
    total_rec = bet_recommendation(total_confidence)
    btts_rec = bet_recommendation(btts_confidence)
    dc_home_rec = bet_recommendation(dc_home_confidence)
    dc_away_rec = bet_recommendation(dc_away_confidence)
    
    # Build comprehensive output
    output = {
        "sport": "soccer",
        "game": {
            "home_team": home_team,
            "away_team": away_team,
            "projected_home_goals": round(home_lam, 2),
            "projected_away_goals": round(away_lam, 2),
            "projected_total_goals": round(adjusted_total, 2),
            "home_win_prob": round(home_win_prob, 3),
            "draw_prob": round(draw_prob, 3),
            "away_win_prob": round(away_win_prob, 3),
        },
        "predictions": {
            "side": {
                "model_xg_diff": round(home_lam - away_lam, 3),
                "market_line": market_line,
                "edge": round(side_edge, 3),
                "confidence": side_confidence,
                "recommendation": side_rec,
            },
            "double_chance": {
                "home_or_draw": round(home_or_draw, 3),
                "draw_or_away": round(draw_or_away, 3),
                "home_dnb_prob": round(home_dnb_prob, 3),
                "away_dnb_prob": round(away_dnb_prob, 3),
                "confidence": {
                    "home_or_draw": dc_home_confidence,
                    "draw_or_away": dc_away_confidence,
                },
                "recommendation": {
                    "home_or_draw": dc_home_rec,
                    "draw_or_away": dc_away_rec,
                },
            },
            "total": {
                "model_total_xg": round(adjusted_total, 3),
                "market_total": market_total,
                "edge": round(total_edge, 3),
                "confidence": total_confidence,
                "recommendation": total_rec,
            },
            "btts": {
                "yes_probability": round(btts_yes_prob, 3),
                "no_probability": round(btts_no_prob, 3),
                "confidence": btts_confidence,
                "recommendation": btts_rec,
            },
        },
        "goals_analysis": {
            "over_05_prob": round(poisson_over_prob(adjusted_total, 0.5), 3),
            "over_15_prob": round(p_over_15, 3),
            "over_25_prob": round(p_over_25, 3),
            "over_35_prob": round(p_over_35, 3),
            "over_45_prob": round(poisson_over_prob(adjusted_total, 4.5), 3),
        },
        "correct_score_probabilities": {
            "0_0": round(poisson_pmf(k=0, lam=home_lam) * poisson_pmf(k=0, lam=away_lam), 3),
            "1_0": round(poisson_pmf(k=1, lam=home_lam) * poisson_pmf(k=0, lam=away_lam), 3),
            "0_1": round(poisson_pmf(k=0, lam=home_lam) * poisson_pmf(k=1, lam=away_lam), 3),
            "1_1": round(poisson_pmf(k=1, lam=home_lam) * poisson_pmf(k=1, lam=away_lam), 3),
            "2_0": round(poisson_pmf(k=2, lam=home_lam) * poisson_pmf(k=0, lam=away_lam), 3),
            "0_2": round(poisson_pmf(k=0, lam=home_lam) * poisson_pmf(k=2, lam=away_lam), 3),
            "2_1": round(poisson_pmf(k=2, lam=home_lam) * poisson_pmf(k=1, lam=away_lam), 3),
            "1_2": round(poisson_pmf(k=1, lam=home_lam) * poisson_pmf(k=2, lam=away_lam), 3),
            "2_2": round(poisson_pmf(k=2, lam=home_lam) * poisson_pmf(k=2, lam=away_lam), 3),
            "3_0": round(poisson_pmf(k=3, lam=home_lam) * poisson_pmf(k=0, lam=away_lam), 3),
            "0_3": round(poisson_pmf(k=0, lam=home_lam) * poisson_pmf(k=3, lam=away_lam), 3),
        },
        "match_outcome": {
            "home_win": round(home_win_prob, 3),
            "draw": round(draw_prob, 3),
            "away_win": round(away_win_prob, 3),
        },
        "corners_analysis": {
            "home_corner_strength": round(home_corner_strength, 2),
            "away_corner_strength": round(away_corner_strength, 2),
            "projected_total": round(corner_total, 1),
            "recalibrated_total": round(recalibrated_total, 1),
            "blended_total": round(blended_corner_total, 1),
            "over_85_prob": round(p_corners_85, 3),
            "over_95_prob": round(p_corners_95, 3),
            "over_105_prob": round(p_corners_105, 3),
            "market_line": market_corners,
            "edge": round(corners_edge, 2),
            "confidence": corners_confidence,
            "recommendation": corners_rec,
            "tactical_context": {
                "home_possession_pct": home_data['possession_pct'],
                "away_possession_pct": away_data['possession_pct'],
                "home_corner_gen_style": home_data['corner_gen_style'],
                "away_corner_gen_style": away_data['corner_gen_style'],
                "sharp_angle": f"{home_team} ({home_data['corner_gen_style']}) vs {away_data['corner_gen_style']} style",
            },
        },
        "btts_probability": round(btts_prob, 3),
        "meta": {
            "ref_data": ref_data,
        }
    }
    
    # Store to database if enabled
    if store_to_db:
        try:
            # Store side prediction
            store_prediction(
                sport="soccer",
                home_team=home_team,
                away_team=away_team,
                market_type="side",
                model_value=home_lam - away_lam,
                market_value=market_line,
                edge=side_edge,
                confidence=side_confidence,
                recommendation=side_rec,
                raw_json=output
            )
            
            # Store total prediction
            store_prediction(
                sport="soccer",
                home_team=home_team,
                away_team=away_team,
                market_type="total",
                model_value=adjusted_total,
                market_value=market_total,
                edge=total_edge,
                confidence=total_confidence,
                recommendation=total_rec,
                raw_json=output
            )
            
            # Store BTTS prediction
            store_prediction(
                sport="soccer",
                home_team=home_team,
                away_team=away_team,
                market_type="btts",
                model_value=btts_prob,
                market_value=0.5,
                edge=btts_edge,
                confidence=btts_confidence,
                recommendation=btts_rec,
                raw_json=output
            )
        except Exception as e:
            print(f"Warning: Could not store to database: {e}")
    
    # Save to output file
    out_dir = Path("output/soccer")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{home_team.replace(' ', '_')}_vs_{away_team.replace(' ', '_')}.json"
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    # Print summary
    print(f"Projected Score: {home_team} {home_lam:.1f} - {away_team} {away_lam:.1f}")
    print(f"Projected Total Goals: {adjusted_total:.2f}")
    print(f"\nGoal Probabilities:")
    print(f"  Over 1.5: {p_over_15:.1%}")
    print(f"  Over 2.5: {p_over_25:.1%}")
    print(f"  Over 3.5: {p_over_35:.1%}")
    print(f"\nBTTS Probability: {btts_prob:.1%}")
    print(f"\nMatch Outcome:")
    print(f"  {home_team} Win: {home_win_prob:.1%}")
    print(f"  Draw: {draw_prob:.1%}")
    print(f"  {away_team} Win: {away_win_prob:.1%}")
    print(f"\nCorner Analysis:")
    print(f"  {home_team} Corner Strength: {home_corner_strength:+.2f}")
    print(f"  {away_team} Corner Strength: {away_corner_strength:+.2f}")
    print(f"  Model Projection: {corner_total:.1f}")
    print(f"  Recalibrated (Off vs Def): {recalibrated_total:.1f}")
    print(f"  Blended Projection: {blended_corner_total:.1f}")
    print(f"  Over 8.5: {p_corners_85:.1%} | Over 9.5: {p_corners_95:.1%} | Over 10.5: {p_corners_105:.1%}")
    print(f"  Corners Recommendation: {corners_rec} (Confidence: {corners_confidence:.1f}%)")
    print(f"  Tactical Context: {home_data['corner_gen_style'].capitalize()} vs {away_data['corner_gen_style'].capitalize()} style")
    print(f"\nBetting Predictions:")
    print(f"  1X2: Home: {side_rec} (Confidence: {side_confidence:.1f}%)")
    print(f"  Double Chance: 1X: {dc_home_rec} (Confidence: {dc_home_confidence:.1f}%), X2: {dc_away_rec} (Confidence: {dc_away_confidence:.1f}%)")
    print(f"  Draw No Bet: Home: {home_dnb_prob:.1%}, Away: {away_dnb_prob:.1%}")
    print(f"  Total: {total_rec} (Confidence: {total_confidence:.1f}%)")
    print(f"  BTTS: {btts_rec} (Confidence: {btts_confidence:.1f}%)")
    print(f"\nCorrect Score Probabilities (Top 5):")
    scores = sorted(output['correct_score_probabilities'].items(), key=lambda x: x[1], reverse=True)[:5]
    for score, prob in scores:
        print(f"  {score.replace('_', '-')}: {prob:.1%}")
    print(f"\nResults saved to: {out_path}")
    
    return output
