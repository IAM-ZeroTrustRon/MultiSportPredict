"""
Universal Confidence Engine for MultiSportPredict
==================================================
Provides sport-agnostic confidence scoring and bet recommendations.

Scoring Components:
- Model Edge Score (55% weight): Bigger edge = higher confidence
- Volatility Penalty (25% weight): Lower volatility = higher confidence
- Market Alignment (20% weight): Sharp agreement boosts confidence

Output: 0-100 confidence rating with Bet/Pass thresholds
"""

import numpy as np
from typing import Dict, Any


# Sport-specific volatility coefficients
VOLATILITY_COEFFICIENTS = {
    # Basketball
    "nba_spread": 0.35,
    "nba_total": 0.38,
    "nba_props": 0.45,
    "euroleague_spread": 0.40,
    "euroleague_total": 0.42,
    
    # Soccer
    "soccer_sides": 0.50,
    "soccer_totals": 0.55,
    "soccer_btts": 0.48,
    "soccer_corners": 0.60,
    "soccer_props": 0.58,
    
    # MLB
    "mlb_totals": 0.65,
    "mlb_sides": 0.55,
    "mlb_k_props": 0.55,
    "mlb_hr_props": 0.70,
    "mlb_hits": 0.52,
    "mlb_tb": 0.55,
    "mlb_walks": 0.60,
    "mlb_rbis": 0.62,
    "mlb_nrfi": 0.48,

    # Tennis
    "tennis_moneyline": 0.45,
    "tennis_totals": 0.50,
    "tennis_sets": 0.52,
}

# Bet thresholds by sport/market type
BET_THRESHOLDS = {
    # Basketball
    "nba_spread": {"bet": 60, "strong": 75},
    "nba_total": {"bet": 60, "strong": 74},
    "nba_props": {"bet": 62, "strong": 78},
    "euroleague_spread": {"bet": 58, "strong": 72},
    "euroleague_total": {"bet": 58, "strong": 72},
    
    # Soccer
    "soccer_sides": {"bet": 58, "strong": 72},
    "soccer_totals": {"bet": 60, "strong": 74},
    "soccer_btts": {"bet": 60, "strong": 74},
    "soccer_corners": {"bet": 62, "strong": 76},
    "soccer_props": {"bet": 62, "strong": 76},
    
    # MLB
    "mlb_totals": {"bet": 60, "strong": 76},
    "mlb_sides": {"bet": 58, "strong": 74},
    "mlb_k_props": {"bet": 62, "strong": 78},
    "mlb_hr_props": {"bet": 65, "strong": 80},
    "mlb_hits": {"bet": 60, "strong": 75},
    "mlb_tb": {"bet": 60, "strong": 75},
    "mlb_walks": {"bet": 62, "strong": 78},
    "mlb_rbis": {"bet": 62, "strong": 78},
    "mlb_nrfi": {"bet": 60, "strong": 76},

    # Tennis
    "tennis_moneyline": {"bet": 58, "strong": 72},
    "tennis_totals": {"bet": 60, "strong": 74},
    "tennis_sets": {"bet": 60, "strong": 74},
}

# Default thresholds for unknown market types
DEFAULT_BET_THRESHOLD = {"bet": 60, "strong": 75}
DEFAULT_VOLATILITY = 0.55


def confidence_score(
    model_edge: float,
    volatility: float = 0.55,
    market_alignment: float = 0.0
) -> float:
    """
    Calculate confidence score for a betting opportunity.
    
    Args:
        model_edge: Difference between model projection and market line
        volatility: Sport-specific variance coefficient (lower = more confidence)
        market_alignment: Sharp/public alignment score (-1 to +1, positive = sharp agreement)
    
    Returns:
        Confidence score from 0-100
    """
    # Normalize edge using tanh for smooth scaling
    # tanh compresses large edges while preserving small differences.
    # Use the magnitude of the edge: confidence scales with how far the
    # model projection is from the market line, regardless of direction
    # (a large Under edge is just as confident as a large Over edge).
    edge_component = np.tanh(abs(model_edge) / 3.0)
    
    # Volatility penalty using exponential decay
    # Lower volatility = higher score
    vol_component = np.exp(-volatility)
    
    # Market alignment component
    # Convert -1..1 range to 0..1
    market_component = (market_alignment + 1.0) / 2.0
    
    # Weighted final score
    score = (
        0.55 * edge_component +
        0.25 * vol_component +
        0.20 * market_component
    )
    
    # Scale to 0-100 and clamp
    final_score = max(0.0, min(100.0, score * 100.0))
    
    return round(float(final_score), 1)


def bet_recommendation(
    confidence: float,
    market_type: str = None
) -> str:
    """
    Generate bet recommendation based on confidence score.
    
    Args:
        confidence: Confidence score (0-100)
        market_type: Optional market type for specific thresholds
    
    Returns:
        Recommendation string: "STRONG BET", "BET", or "PASS"
    """
    if market_type and market_type in BET_THRESHOLDS:
        thresholds = BET_THRESHOLDS[market_type]
    else:
        thresholds = DEFAULT_BET_THRESHOLD
    
    if confidence >= thresholds["strong"]:
        return "STRONG BET"
    elif confidence >= thresholds["bet"]:
        return "BET"
    else:
        return "PASS"


def get_volatility(market_type: str) -> float:
    """Get volatility coefficient for a market type."""
    return VOLATILITY_COEFFICIENTS.get(market_type, DEFAULT_VOLATILITY)


def get_thresholds(market_type: str) -> Dict[str, int]:
    """Get bet thresholds for a market type."""
    return BET_THRESHOLDS.get(market_type, DEFAULT_BET_THRESHOLD)


def analyze_bet(
    model_projection: float,
    market_line: float,
    market_type: str,
    market_alignment: float = 0.0
) -> Dict[str, Any]:
    """
    Complete bet analysis with confidence and recommendation.
    
    Args:
        model_projection: Model's projected value
        market_line: Current market line
        market_type: Type of market (e.g., "nba_spread", "mlb_totals")
        market_alignment: Sharp/public alignment (-1 to +1)
    
    Returns:
        Dictionary with edge, confidence, recommendation, and thresholds
    """
    model_edge = model_projection - market_line
    volatility = get_volatility(market_type)
    confidence = confidence_score(model_edge, volatility, market_alignment)
    recommendation = bet_recommendation(confidence, market_type)
    thresholds = get_thresholds(market_type)
    
    # Determine lean direction
    if model_edge > 0:
        lean = f"Over {market_line}" if "total" in market_type or "over" in market_type.lower() else f"+{model_edge:+.2f}"
    else:
        lean = f"Under {market_line}" if "total" in market_type or "over" in market_type.lower() else f"{model_edge:+.2f}"
    
    return {
        "model_projection": round(model_projection, 2),
        "market_line": market_line,
        "edge": round(model_edge, 2),
        "volatility": volatility,
        "confidence": confidence,
        "recommendation": recommendation,
        "lean": lean,
        "thresholds": thresholds,
    }