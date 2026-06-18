"""
Shared Utility Functions for MultiSportPredict
==============================================

Consolidates all duplicated utility functions used across the codebase.
This eliminates code duplication and ensures consistent behavior.

Functions:
- sigmoid: Probability conversion
- clamp: Value bounding
- to_num: Safe numeric conversion
- to_bool: Safe boolean conversion
- color_score: Color rating to numeric score
- poisson_pmf: Poisson probability mass function
- poisson_over_prob: Poisson over probability
- poisson_at_least_one: Poisson at-least-one probability
"""

import math
from typing import Any, Union


def sigmoid(x: float) -> float:
    """Sigmoid function for probability conversion with overflow protection."""
    x = max(-500, min(500, x))
    return 1 / (1 + math.exp(-x))


def clamp(x: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clamp value between low and high bounds."""
    return max(low, min(high, x))


def to_num(v: Any, default: float = 0.0) -> float:
    """Convert value to number with default fallback.
    
    Handles:
    - None values
    - NaN floats
    - String values (with comma removal)
    - Empty strings
    - Any other non-convertible values
    
    Args:
        v: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Converted float value or default
    """
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return default
    try:
        if isinstance(v, str):
            v = v.strip().replace(",", "")
            if v == "":
                return default
        return float(v)
    except Exception:
        return default


def to_bool(v: Any) -> bool:
    """Convert value to boolean.
    
    Handles various string representations:
    - true, t, 1, y, yes → True
    - Everything else → False
    
    Args:
        v: Value to convert
        
    Returns:
        Boolean value
    """
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in {"true", "t", "1", "y", "yes"}


def color_score(x: Any) -> float:
    """Convert color rating to numeric score.
    
    Args:
        x: Color string ('green', 'yellow', 'red')
        
    Returns:
        Numeric score: green=1.0, yellow=0.0, red=-1.0, other=0.0
    """
    return {"green": 1.0, "yellow": 0.0, "red": -1.0}.get(str(x).strip().lower(), 0.0)


def poisson_pmf(k: int, lam: float) -> float:
    """Poisson probability mass function.
    
    Args:
        k: Number of events
        lam: Expected value (lambda)
        
    Returns:
        Probability of exactly k events
    """
    if lam <= 0:
        return 0.0 if k > 0 else 1.0
    if k < 0:
        return 0.0
    
    # Use logarithms to avoid overflow for large k
    try:
        log_pmf = -lam + k * math.log(lam) - math.lgamma(k + 1)
        return math.exp(log_pmf)
    except (ValueError, OverflowError):
        return 0.0


def poisson_over_prob(lam: float, line: float) -> float:
    """Calculate probability of over a given line using Poisson distribution.
    
    Args:
        lam: Expected value (lambda)
        line: Goal line (can be fractional, e.g., 2.5)
        
    Returns:
        Probability of over the line
    """
    n = int(math.floor(line))
    frac = line - n
    
    if abs(frac) < 1e-9:
        # Whole number line (push possible)
        return 1 - sum(poisson_pmf(k, lam) for k in range(0, n + 1))
    else:
        # Fractional line (no push)
        threshold = math.floor(line)
        return 1 - sum(poisson_pmf(k, lam) for k in range(0, threshold + 1))


def poisson_at_least_one(lam: float) -> float:
    """Probability of at least one event occurring.
    
    Args:
        lam: Expected value (lambda)
        
    Returns:
        Probability of at least one event
    """
    return 1 - math.exp(-lam)