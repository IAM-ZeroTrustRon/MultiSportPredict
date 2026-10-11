"""
core/market_handicapper.py - Top-Down (+EV) Market-Based Handicapping Engine.

Implements financial exchange models for sports betting:
1. Implied probability and overround conversion (American & Decimal).
2. De-vigging consensus (Proportional, Power, Shin).
3. Expected Value (+EV) calculation.
4. Position sizing via Fractional Kelly Criterion.
5. Order flow analytics (Reverse Line Movement).
6. Closing Line Value (CLV) performance tracking.

Stdlib only: math, dataclasses, typing.
"""

from dataclasses import dataclass
import math
from typing import List, Optional, Tuple


# =====================================================================
# 1. ODDS CONVERSION & OVERROUND
# =====================================================================

def american_to_decimal(american: float) -> float:
    """Converts American odds (e.g., -110, +150) to Decimal odds."""
    if american > 0:
        return (american / 100.0) + 1.0
    elif american < 0:
        return (100.0 / abs(american)) + 1.0
    else:
        raise ValueError("American odds cannot be 0.")


def decimal_to_american(decimal: float) -> float:
    """Converts Decimal odds (e.g., 1.909, 2.50) to American odds."""
    if decimal <= 1.0:
        raise ValueError("Decimal odds must be strictly greater than 1.0.")
    if decimal >= 2.0:
        return round((decimal - 1.0) * 100.0, 1)
    else:
        return round(-100.0 / (decimal - 1.0), 1)


def implied_probability(odds: float, odds_type: str = "american") -> float:
    """Computes raw implied probability including bookmaker vig."""
    if odds_type.lower() == "american":
        dec = american_to_decimal(odds)
    elif odds_type.lower() == "decimal":
        dec = odds
    else:
        raise ValueError("odds_type must be 'american' or 'decimal'")
    return 1.0 / dec


def market_overround(implied_probs: List[float]) -> float:
    """Total market overround S (e.g., 1.0476 = 4.76% vig market)."""
    return sum(implied_probs)

# =====================================================================
# 2. DE-VIGGING ALGORITHMS (TRUE PROBABILITY)
# =====================================================================

def devig_proportional(implied_probs: List[float]) -> List[float]:
    """Multiplicative method: normalize implied probs so they sum to 1.0."""
    total = sum(implied_probs)
    if total <= 0:
        raise ValueError("Sum of implied probabilities must be positive.")
    return [p / total for p in implied_probs]


def devig_power(implied_probs: List[float], tol: float = 1e-7,
                max_iter: int = 100) -> List[float]:
    """Power method: solve sum(p_i^k) = 1.0; P_true,i = p_i^k."""
    total = sum(implied_probs)
    if abs(total - 1.0) < tol:
        return list(implied_probs)
    low, high = 1.0, 10.0
    for _ in range(max_iter):
        mid = (low + high) / 2.0
        val = sum(math.pow(p, mid) for p in implied_probs)
        if abs(val - 1.0) < tol:
            break
        if val > 1.0:
            low = mid
        else:
            high = mid
    k = (low + high) / 2.0
    return [math.pow(p, k) for p in implied_probs]


def devig_shin(implied_probs: List[float], tol: float = 1e-7,
               max_iter: int = 100) -> Tuple[List[float], float]:
    """Shin model: separates informed capital fraction z from retail noise."""
    s = sum(implied_probs)
    if abs(s - 1.0) < tol:
        return list(implied_probs), 0.0
    low, high = 0.0, 0.4
    best_z = 0.0
    for _ in range(max_iter):
        z = (low + high) / 2.0
        p_raw = []
        for pi in implied_probs:
            term = math.sqrt(z * z + 4.0 * (1.0 - z) * (pi * pi / s))
            p_raw.append((term - z) / (2.0 * (1.0 - z)))
        sum_p = sum(p_raw)
        if abs(sum_p - 1.0) < tol:
            best_z = z
            break
        if sum_p < 1.0:
            high = z
        else:
            low = z
        best_z = z
    final_p = []
    for pi in implied_probs:
        term = math.sqrt(best_z * best_z + 4.0 * (1.0 - best_z) * (pi * pi / s))
        final_p.append((term - best_z) / (2.0 * (1.0 - best_z)))
    sum_final = sum(final_p)
    return [p / sum_final for p in final_p], round(best_z, 4)


def devig_market(odds: List[float], method: str = "power",
                 odds_type: str = "american") -> List[float]:
    """De-vig any market odds list. method: proportional | power | shin."""
    raw_probs = [implied_probability(o, odds_type=odds_type) for o in odds]
    if method == "proportional":
        return devig_proportional(raw_probs)
    elif method == "power":
        return devig_power(raw_probs)
    elif method == "shin":
        p_true, _ = devig_shin(raw_probs)
        return p_true
    raise ValueError(f"Unknown de-vig method: {method}")

# =====================================================================
# 3. EXPECTED VALUE (+EV) & POSITION SIZING (KELLY)
# =====================================================================

def calculate_ev(p_true: float, decimal_odds_soft: float) -> float:
    """EV = (P_true * D_soft) - 1.0. e.g. 0.035 = +3.5% EV."""
    return (p_true * decimal_odds_soft) - 1.0


def kelly_stake_fraction(p_true: float, decimal_odds_soft: float,
                         multiplier: float = 0.25,
                         max_bankroll_pct: float = 0.05) -> float:
    """Fractional Kelly: f* = EV/(D-1); f = c*f*, capped at max pct."""
    b = decimal_odds_soft - 1.0
    if b <= 0:
        return 0.0
    ev = calculate_ev(p_true, decimal_odds_soft)
    if ev <= 0:
        return 0.0
    return min((ev / b) * multiplier, max_bankroll_pct)

# =====================================================================
# 4. ORDER FLOW & REVERSE LINE MOVEMENT (RLM)
# =====================================================================

@dataclass
class RLMAnalysis:
    is_rlm: bool
    action_divergence: float
    sharp_side: Optional[str]
    confidence_reason: str


def detect_reverse_line_movement(team_a: str, team_b: str, ticket_pct_a: float,
                                 handle_pct_a: float, opening_spread_a: float,
                                 current_spread_a: float) -> RLMAnalysis:
    """Ticket vs handle divergence + line move. Returns sharp side if RLM."""
    delta_action_a = handle_pct_a - ticket_pct_a
    line_move_a = current_spread_a - opening_spread_a
    if ticket_pct_a >= 0.60 and line_move_a > 0:
        return RLMAnalysis(True, round(-delta_action_a, 3), team_b,
            f"Public on {team_a} ({ticket_pct_a*100:.0f}% bets), "
            f"but line moved {line_move_a:+.1f} toward {team_b}")
    if ticket_pct_a <= 0.40 and line_move_a < 0:
        return RLMAnalysis(True, round(delta_action_a, 3), team_a,
            f"Public on {team_b} ({(1-ticket_pct_a)*100:.0f}% bets), "
            f"but line moved {abs(line_move_a):+.1f} toward {team_a}")
    return RLMAnalysis(False, round(delta_action_a, 3), None,
        "Line moved with tickets or stayed neutral.")


# =====================================================================
# 5. CLOSING LINE VALUE (CLV)
# =====================================================================

def calculate_clv(placed_decimal_odds: float,
                  closing_fair_decimal_odds: float) -> float:
    """CLV = (D_placed / D_closing_fair) - 1.0. Positive = beating close."""
    if closing_fair_decimal_odds <= 0:
        return 0.0
    return (placed_decimal_odds / closing_fair_decimal_odds) - 1.0


# =====================================================================
# CLI VERIFICATION & SMOKE TEST
# =====================================================================

if __name__ == "__main__":
    print("=" * 65)
    print("TOP-DOWN (+EV) MARKET HANDICAPPER SMOKE TEST")
    print("=" * 65)
    sharp_american = [-125, 115]
    sharp_raw = [implied_probability(o) for o in sharp_american]
    overround = market_overround(sharp_raw)
    print(f"Sharp Overround: {overround*100:.2f}% "
          f"(Vig: {(overround-1.0)*100:.2f}%)")
    p_prop = devig_proportional(sharp_raw)
    p_power = devig_power(sharp_raw)
    p_shin, z = devig_shin(sharp_raw)
    print("\n--- De-Vigging (Yankees / Rays) ---")
    print(f"Proportional: Yankees {p_prop[0]*100:.2f}% | Rays {p_prop[1]*100:.2f}%")
    print(f"Power:        Yankees {p_power[0]*100:.2f}% | Rays {p_power[1]*100:.2f}%")
    print(f"Shin(z={z:.3f}): Yankees {p_shin[0]*100:.2f}% | Rays {p_shin[1]*100:.2f}%")
    soft_rays, p_true_rays = 2.25, p_power[1]
    ev_rays = calculate_ev(p_true_rays, soft_rays)
    kelly_q = kelly_stake_fraction(p_true_rays, soft_rays, multiplier=0.25)
    print("\n--- Soft Book (+125 = 2.25) ---")
    print(f"Rays True: {p_true_rays*100:.2f}% | EV: {ev_rays*100:+.2f}% | "
          f"Q-Kelly: {kelly_q*100:.2f}% bankroll")
    print(f"\nCLV (2.25 vs 2.10 fair): {calculate_clv(2.25, 2.10)*100:+.2f}%")
    rlm = detect_reverse_line_movement("Browns", "Steelers", 0.72, 0.48, -3.5, -2.5)
    print(f"\nRLM: {rlm.is_rlm} -> Back {rlm.sharp_side} ({rlm.confidence_reason})")
    print("=" * 65)
