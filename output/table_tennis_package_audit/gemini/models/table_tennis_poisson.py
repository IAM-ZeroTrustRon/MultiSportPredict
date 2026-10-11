"""
Auxiliary Poisson Distribution Utility (Experimental)
Section 4 of Czech Liga Pro Handoff Specification.

NOTE: This is strictly an auxiliary count-model diagnostic tool (e.g. for completed-game
losing-point counts) and is NOT used as an exact table-tennis final-score distribution.
Table tennis games end on legal absorbing terminal states (11+ points, win by 2).
"""

import math
from typing import Dict, Any, List

def poisson_distribution(rate: float, tolerance: float = 1e-10,
                         max_count: int = 10000) -> dict:
    """
    Numerically stable count-distribution utility.
    Exposes omitted tail mass and strictly validates inputs.
    """
    if not math.isfinite(rate) or rate < 0:
        raise ValueError("rate must be finite and nonnegative")
    if not math.isfinite(tolerance) or not 0 < tolerance < 1:
        raise ValueError("tolerance must be between zero and one")
    if isinstance(max_count, bool) or not isinstance(max_count, int) or max_count < 0:
        raise ValueError("max_count must be a nonnegative integer")
    probabilities = []
    mass = 0.0
    for count in range(max_count + 1):
        probability = (1.0 if count == 0 else 0.0) if rate == 0 else math.exp(
            count * math.log(rate) - rate - math.lgamma(count + 1)
        )
        probabilities.append(probability)
        mass = math.fsum(probabilities)
        if count >= rate and mass >= 1 - tolerance:
            return {"probabilities": probabilities,
                    "tail_mass": max(0.0, 1 - mass)}
    raise ValueError("Increase max_count; tail tolerance was not reached")

def evaluate_poisson_losing_points_diagnostic(observed_losing_points: List[int],
                                             candidate_rate: float) -> Dict[str, Any]:
    """
    Diagnostic comparison of empirical losing-point distribution vs Poisson.
    Losing points in an 11-point game have support on [0, 9] (or higher in deuce).
    """
    if not observed_losing_points:
        return {"status": "no_observations"}
    
    n = len(observed_losing_points)
    mean_val = sum(observed_losing_points) / n
    variance_val = sum((x - mean_val) ** 2 for x in observed_losing_points) / max(1, n - 1)
    
    # Overdispersion ratio: var / mean (Poisson expectation is 1.0)
    dispersion_ratio = variance_val / mean_val if mean_val > 0 else 1.0
    
    poisson_model = poisson_distribution(rate=candidate_rate, tolerance=1e-8, max_count=30)
    
    return {
        "sample_size": n,
        "sample_mean": round(mean_val, 4),
        "sample_variance": round(variance_val, 4),
        "dispersion_ratio": round(dispersion_ratio, 4),
        "is_overdispersed": dispersion_ratio > 1.15,
        "poisson_theoretical_probabilities": poisson_model["probabilities"][:15],
        "poisson_tail_mass": poisson_model["tail_mass"],
        "diagnostic_note": "Rule-dependent support invalidates unconstrained Poisson for terminal table tennis scoring."
    }
