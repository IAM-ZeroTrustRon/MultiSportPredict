"""Sportsbook-neutral settlement and expected-return calculations."""

from __future__ import annotations

import math
from typing import Dict, Iterable, Optional, Tuple

from market_contract import american_to_decimal


def _single_settlement(adjusted_result: float) -> Tuple[float, float, float]:
    if adjusted_result > 1e-9:
        return 1.0, 0.0, 0.0
    if adjusted_result < -1e-9:
        return 0.0, 1.0, 0.0
    return 0.0, 0.0, 1.0


def settle_result(value: float, line: float, market: str, selection: str) -> Tuple[float, float, float]:
    """Return (win stake fraction, loss fraction, refund fraction).

    Quarter lines split the stake over adjacent half/whole lines. `value` is
    a score total for totals, or the selected team's margin for handicaps.
    """
    kind = market.lower()
    side = selection.lower()
    sign = 1.0 if side in {"over", "home", "draw_no_bet"} else -1.0
    if kind in {"total", "match_total", "team_total", "corner_total"}:
        if side not in {"over", "under"}:
            raise ValueError("Totals selection must be Over or Under")
        adjusted = sign * (float(value) - float(line))
    elif kind in {"spread", "handicap", "asian_handicap", "corner_handicap"}:
        if side not in {"home", "away"}:
            raise ValueError("Handicap selection must be Home or Away")
        adjusted = float(value) + float(line)
    elif kind in {"dnb", "draw_no_bet"}:
        if side not in {"home", "away"}:
            raise ValueError("Draw-no-bet selection must be Home or Away")
        if abs(float(value)) < 1e-9:
            return 0.0, 0.0, 1.0
        adjusted = float(value) if side == "home" else -float(value)
    else:
        raise ValueError(f"Unsupported market settlement type: {market}")

    doubled = round(adjusted * 2)
    if abs(adjusted * 2 - doubled) < 1e-8 and doubled % 2:
        return _single_settlement(adjusted)
    lower = math.floor(float(line) * 2) / 2.0
    upper = math.ceil(float(line) * 2) / 2.0
    if abs(upper - lower) < 1e-9:
        return _single_settlement(adjusted)

    # For totals, evaluate the two split lines using their own direction.
    if kind in {"total", "match_total", "team_total", "corner_total"}:
        a = _single_settlement(sign * (float(value) - lower))
        b = _single_settlement(sign * (float(value) - upper))
    else:
        a = _single_settlement(float(value) + (lower if side == "home" else -lower))
        b = _single_settlement(float(value) + (upper if side == "home" else -upper))
    return tuple((a[i] + b[i]) / 2.0 for i in range(3))


def evaluate_distribution(outcomes: Iterable[Tuple[float, float]], line: float,
                          market: str, selection: str,
                          american_price: Optional[float]) -> Dict[str, Optional[float]]:
    """Evaluate discrete outcome masses; a missing price yields no EV."""
    mass = win = lose = refund = 0.0
    for value, probability in outcomes:
        probability = float(probability)
        if not math.isfinite(probability) or probability < 0:
            raise ValueError("Outcome probabilities must be finite and non-negative")
        w, l, r = settle_result(float(value), line, market, selection)
        mass += probability
        win += probability * w
        lose += probability * l
        refund += probability * r
    if not math.isclose(mass, 1.0, abs_tol=1e-6):
        raise ValueError(f"Outcome mass sums to {mass:.8f}, not 1")
    decimal = american_to_decimal(american_price)
    ev = None if decimal is None else win * (decimal - 1.0) - lose
    return {"win_probability": win, "loss_probability": lose,
            "refund_probability": refund, "ev_per_unit": ev}


def three_way_probabilities(home: float, draw: float, away: float) -> Dict[str, float]:
    values = [float(home), float(draw), float(away)]
    if any(not math.isfinite(x) or x < 0 for x in values) or sum(values) <= 0:
        raise ValueError("Three-way probabilities must be finite, non-negative and nonzero")
    total = sum(values)
    return {"home": values[0] / total, "draw": values[1] / total,
            "away": values[2] / total}


def dnb_probabilities(home: float, draw: float, away: float) -> Dict[str, float]:
    p = three_way_probabilities(home, draw, away)
    decisive = p["home"] + p["away"]
    if decisive <= 0:
        raise ValueError("DNB cannot be evaluated when the draw is certain")
    return {"home_win": p["home"] / decisive, "away_win": p["away"] / decisive,
            "refund": p["draw"]}
