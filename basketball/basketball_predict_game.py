"""
Basketball prediction module for MultiSportPredict
Enhanced with referee data hooks, consensus integration, and historical storage.
Maintains all sophisticated existing prediction logic.
"""

from typing import Any, Dict, Optional


def fetch_basketball_ref_data(home: str, away: str) -> Dict[str, Any]:
    """
    Fetch referee crew data for a basketball game.
    
    This is a placeholder that should be integrated with real data sources
    like RefMetrics, RefEye, or official league data.
    
    Returns:
        Dictionary with referee statistics
    """
    # TODO: Integrate with real referee data API
    # Real implementation would call:
    # - RefMetrics API for crew foul rates
    # - Official league data for crew tendencies
    # - Historical referee assignment data
    
    return {
        "crew_foul_rate": 1.02,          # Fouls per 48 min relative to average
        "home_bias": 0.03,               # Home team foul differential
        "pace_bias": 0.01,               # Pace adjustment factor
        "tech_fouls_per_game": 0.3,      # Technical fouls per game
        "over_rate_totals": 0.52,        # Rate of games going over
        "playoff_flag": 0,               # Playoff intensity flag
    }


def fetch_basketball_consensus(home: str, away: str) -> Dict[str, Any]:
    """
    Fetch sharp bettor consensus data for a basketball game.
    
    This is a placeholder that should be integrated with real data sources
    like Action Network, VegasInsider, or betting exchange data.
    
    Returns:
        Dictionary with consensus statistics
    """
    # TODO: Integrate with real consensus data API
    # Real implementation would call:
    # - Action Network for public betting percentages
    # - VegasInsider for line movement data
    # - Betting exchanges for sharp money indicators
    
    return {
        "public_pct_home": 0.62,         # Public betting on home team
        "public_pct_over": 0.58,         # Public betting on over
        "sharp_alignment": 0.15,         # Sharp money alignment with model (-1 to +1)
        "line_movement": -0.5,           # Line movement since open
        "ticket_pct_home": 0.55,         # Percentage of tickets on home
        "money_pct_home": 0.68,          # Percentage of money on home
    }


def run_basketball_game(
    home_team: str, 
    away_team: str,
    market_spread: float = -2.5,
    market_total: float = 165.0,
    market_ml_prob: float = 0.61,
    store_to_db: bool = True,
):
    """
    Run basketball prediction for a matchup with enhanced features.
    
    Args:
        home_team: Home team name
        away_team: Away team name
        market_spread: Current market spread (home team perspective)
        market_total: Current market total
        market_ml_prob: Market implied moneyline probability
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
        schema_basketball,
    )
    
    print(f"\n=== BASKETBALL: {home_team} vs {away_team} ===\n")
    
    # Use the existing MultiSportModel for sophisticated predictions
    try:
        from MultiSportModel import (
            GameContext,
            TeamMetrics,
            eu_build_full_game,
            project_basketball_q1,
        )
    except ImportError:
        import sys
        legacy_dir = str(Path(__file__).resolve().parent.parent / "archive" / "legacy-modules")
        if legacy_dir not in sys.path:
            sys.path.insert(0, legacy_dir)
        from MultiSportModel import (
            GameContext,
            TeamMetrics,
            eu_build_full_game,
            project_basketball_q1,
        )
    
    # Fetch external data (referee and consensus)
    ref_data = fetch_basketball_ref_data(home_team, away_team)
    consensus_data = fetch_basketball_consensus(home_team, away_team)
    
    # Default team metrics (in production, these would come from your data pipeline)
    home_data = {
        'ortg': 110.0,
        'drtg': 105.0,
        'baseline_net': 5.0,
        'recent_net': 4.0,
        'pace': 95.0,
        'rest_days': 2,
        'travel_km': 0,
        'back_to_back': False,
        'three_in_six': False,
        'split_edge': 3.0,
        'rotation_depth': 9,
        'injury_status': 'green',
        'coach_stability': 'green',
        'motivation': 'green',
    }
    
    away_data = {
        'ortg': 108.0,
        'drtg': 107.0,
        'baseline_net': 1.0,
        'recent_net': 2.0,
        'pace': 93.0,
        'rest_days': 2,
        'travel_km': 500,
        'back_to_back': False,
        'three_in_six': False,
        'split_edge': 1.0,
        'rotation_depth': 8,
        'injury_status': 'yellow',
        'coach_stability': 'green',
        'motivation': 'green',
    }
    
    # Adjust model projections based on referee data
    model_spread_adjustment = ref_data["home_bias"] * 2.5  # Scale to spread impact
    model_total_adjustment = ref_data["pace_bias"] * 10    # Scale to total impact
    
    market_data = {
        'open_line': market_spread - 0.5,
        'current_line': market_spread,
        'spread': market_spread,
        'total': market_total,
    }
    
    ctx = GameContext(
        game_id=f"{home_team.replace(' ', '_')}_vs_{away_team.replace(' ', '_')}",
        date="2026-06-06",
        league="Basketball",
        record_type="full_game",
        home_team=home_team,
        away_team=away_team,
        market_line=market_data['spread'],
        current_line=market_data['current_line'],
        open_line=market_data['open_line'],
    )
    
    home_tm = TeamMetrics(
        ortg=home_data['ortg'],
        drtg=home_data['drtg'],
        baseline_net=home_data['baseline_net'],
        recent_net=home_data['recent_net'],
        pace=home_data['pace'],
        rest_days=home_data['rest_days'],
        travel_km=home_data['travel_km'],
        back_to_back=home_data['back_to_back'],
        three_in_six=home_data['three_in_six'],
        split_edge=home_data['split_edge'],
        rotation_depth=home_data['rotation_depth'],
        injury_status=home_data['injury_status'],
        coach_stability=home_data['coach_stability'],
        motivation=home_data['motivation'],
        open_line=market_data['open_line'],
        current_line=market_data['current_line'],
    )
    
    away_tm = TeamMetrics(
        ortg=away_data['ortg'],
        drtg=away_data['drtg'],
        baseline_net=away_data['baseline_net'],
        recent_net=away_data['recent_net'],
        pace=away_data['pace'],
        rest_days=away_data['rest_days'],
        travel_km=away_data['travel_km'],
        back_to_back=away_data['back_to_back'],
        three_in_six=away_data['three_in_six'],
        split_edge=away_data['split_edge'],
        rotation_depth=away_data['rotation_depth'],
        injury_status=away_data['injury_status'],
        coach_stability=away_data['coach_stability'],
        motivation=away_data['motivation'],
        open_line=-market_data['open_line'],
        current_line=-market_data['current_line'],
    )
    
    # Get base predictions from sophisticated model
    result = eu_build_full_game(home_tm, away_tm, ctx)
    q1_proj = project_basketball_q1(home_data, away_data)
    
    # Apply referee adjustments
    adjusted_spread = result['projected_home_score'] - result['projected_away_score'] + model_spread_adjustment
    adjusted_total = result['projected_total'] + model_total_adjustment
    
    # Calculate confidence scores with consensus alignment
    spread_edge = adjusted_spread - market_spread
    total_edge = adjusted_total - market_total
    ml_edge = (market_ml_prob - 0.5) * 100
    
    # Use confidence engine with market alignment from consensus
    spread_confidence = confidence_score(
        spread_edge, 
        volatility=0.35,  # Basketball spread volatility
        market_alignment=consensus_data["sharp_alignment"]
    )
    total_confidence = confidence_score(
        total_edge, 
        volatility=0.38,  # Basketball total volatility
        market_alignment=consensus_data["sharp_alignment"]
    )
    ml_confidence = confidence_score(
        ml_edge, 
        volatility=0.40,  # Basketball moneyline volatility
        market_alignment=consensus_data["sharp_alignment"]
    )
    
    spread_rec = bet_recommendation(spread_confidence)
    total_rec = bet_recommendation(total_confidence)
    ml_rec = bet_recommendation(ml_confidence)
    
    # Build comprehensive output using standard schema
    output = {
        "sport": "basketball",
        "game": {
            "home_team": home_team,
            "away_team": away_team,
            "projected_home_score": round(adjusted_spread / 2 + adjusted_total / 2, 1),
            "projected_away_score": round(adjusted_total / 2 - adjusted_spread / 2, 1),
            "projected_total": round(adjusted_total, 1),
            "win_probability": result['probability'],
            "model_edge": result['model_edge'],
            "lean": result['lean'],
        },
        "predictions": {
            "spread": {
                "model_spread": round(adjusted_spread, 2),
                "market_spread": market_spread,
                "edge": round(spread_edge, 2),
                "confidence": spread_confidence,
                "recommendation": spread_rec,
            },
            "total": {
                "model_total": round(adjusted_total, 2),
                "market_total": market_total,
                "edge": round(total_edge, 2),
                "confidence": total_confidence,
                "recommendation": total_rec,
            },
            "moneyline": {
                "model_prob": market_ml_prob,
                "edge": round(ml_edge, 2),
                "confidence": ml_confidence,
                "recommendation": ml_rec,
            },
        },
        "q1_projection": q1_proj,
        "meta": {
            "ref_data": ref_data,
            "consensus": consensus_data,
        }
    }
    
    # Store to database if enabled
    if store_to_db:
        try:
            # Store spread prediction
            store_prediction(
                sport="basketball",
                home_team=home_team,
                away_team=away_team,
                market_type="spread",
                model_value=adjusted_spread,
                market_value=market_spread,
                edge=spread_edge,
                confidence=spread_confidence,
                recommendation=spread_rec,
                raw_json=output
            )
            
            # Store total prediction
            store_prediction(
                sport="basketball",
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
            
            # Store moneyline prediction
            store_prediction(
                sport="basketball",
                home_team=home_team,
                away_team=away_team,
                market_type="moneyline",
                model_value=market_ml_prob,
                market_value=0.5,
                edge=ml_edge,
                confidence=ml_confidence,
                recommendation=ml_rec,
                raw_json=output
            )
        except Exception as e:
            print(f"Warning: Could not store to database: {e}")
    
    # Save to output file
    out_dir = Path("output/basketball")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{home_team.replace(' ', '_')}_vs_{away_team.replace(' ', '_')}.json"
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    # Print summary
    print(f"Projected Score: {home_team} {output['game']['projected_home_score']:.1f} - {away_team} {output['game']['projected_away_score']:.1f}")
    print(f"Projected Total: {output['game']['projected_total']:.1f}")
    print(f"Win Probability: {home_team} {result['probability']:.1%}")
    print(f"Model Edge: {result['model_edge']:+.2f}")
    print(f"Lean: {result['lean']}")
    print(f"\nSpread: {spread_rec} (Confidence: {spread_confidence:.1f}%)")
    print(f"Total: {total_rec} (Confidence: {total_confidence:.1f}%)")
    print(f"Moneyline: {ml_rec} (Confidence: {ml_confidence:.1f}%)")
    print(f"\nResults saved to: {out_path}")
    
    return output
