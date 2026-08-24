from __future__ import annotations

from typing import Dict


# Mock database of umpire tendencies (In production, load this from a CSV or API)
UMPIRE_DB: Dict[str, Dict[str, float]] = {
    "Angel Hernandez": {"k_boost": -0.05, "run_boost": 0.10, "nrfi_adj": -0.04},  # Hitter friendly / erratic
    "Pat Hoberg": {"k_boost": 0.02, "run_boost": -0.05, "nrfi_adj": 0.03},       # Pitcher friendly / accurate
    "CB Bucknor": {"k_boost": -0.03, "run_boost": 0.08, "nrfi_adj": -0.02},      # Hitter friendly
}


def apply_umpire_tendencies(
    base_nrfi_prob: float,
    base_k_proj: float,
    umpire_name: str,
) -> Dict[str, float]:
    """
    Adjust match projections based on the assigned home plate umpire.

    Returns:
      - adj_nrfi_prob: adjusted NRFI probability (clamped)
      - adj_k_proj: adjusted K projection (scaled)
    """
    umpire_stats = UMPIRE_DB.get(umpire_name)

    if not umpire_stats:
        # Return baseline if umpire is unknown or unassigned
        return {"adj_nrfi_prob": base_nrfi_prob, "adj_k_proj": base_k_proj}

    # Apply the mathematical modifiers
    adjusted_nrfi = base_nrfi_prob + float(umpire_stats["nrfi_adj"])
    adjusted_k = base_k_proj * (1 + float(umpire_stats["k_boost"]))

    # Cap probabilities to realistic bounds
    adjusted_nrfi = max(0.10, min(0.90, adjusted_nrfi))

    return {
        "adj_nrfi_prob": round(adjusted_nrfi, 3),
        "adj_k_proj": round(adjusted_k, 1),
    }
