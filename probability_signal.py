"""Two separate signals: chance of winning, and value at the offered price.

A selection can be likely to win and still be a bad bet (a 78% shot at -450
loses money). Those are different questions and this module keeps them apart:

  * probability  -- the model's own chance the selection wins
  * value        -- model probability priced against the offered odds

The HIGH flag uses the model's selection probability, never the legacy
"confidence" heuristic (which is not a probability and is not calibrated).
Nothing here gates a bet, blends with the market, or invents a threshold for
"too much disagreement": a large model/market gap is reported as
MODEL/MARKET DISCREPANCY and left for a human to read.

Thresholds
----------
HIGH_PROBABILITY_THRESHOLD = 0.75 is the display cut for the probability flag.
VALUE_EV_THRESHOLD = 0.05 mirrors the existing LEAN gate in
models/score_ratings.price_market, so the "value verdict" here agrees with the
recommendation printed beside it instead of introducing a second policy.
"""
import math
from typing import Optional

HIGH_PROBABILITY_THRESHOLD = 0.75
VALUE_EV_THRESHOLD = 0.05

HIGH_COHORT = "HIGH_PROBABILITY"
EXPLORATORY_COHORT = "EXPLORATORY"


def format_probability(probability) -> str:
    if probability is None:
        return "unavailable"
    try:
        value = float(probability)
    except (TypeError, ValueError):
        return "unavailable"
    if not math.isfinite(value) or not 0 <= value <= 1:
        return "unavailable"
    return f"{value:.1%}"


def format_price(price) -> str:
    """American odds: -450, +130. Decimal prices (1 < p < 100) are converted.

    Most runners store American odds, but the table-tennis report stores
    decimal, and printing "1.20" under an "Odds" label beside -110 rows would
    invite the two to be compared as if they were the same scale.
    """
    if price is None:
        return "unavailable"
    try:
        value = float(price)
    except (TypeError, ValueError):
        return "unavailable"
    if not math.isfinite(value) or value == 0:
        return "unavailable"
    if abs(value) < 100:
        if value <= 1.0:
            return "unavailable"
        value = (value - 1.0) * 100.0 if value >= 2.0 else -100.0 / (value - 1.0)
    return f"{value:+.0f}" if value > 0 else f"{value:.0f}"


def format_ev(ev) -> str:
    if ev is None:
        return "unavailable"
    try:
        value = float(ev)
    except (TypeError, ValueError):
        return "unavailable"
    if not math.isfinite(value):
        return "unavailable"
    return f"{value:+.1%}"


def probability_flag(probability) -> str:
    if probability is None:
        return "UNAVAILABLE"
    try:
        value = float(probability)
    except (TypeError, ValueError):
        return "UNAVAILABLE"
    if not math.isfinite(value) or not 0 <= value <= 1:
        return "UNAVAILABLE"
    return "HIGH" if value >= HIGH_PROBABILITY_THRESHOLD else "NORMAL"


def value_verdict(ev) -> str:
    """'VALUE' only on a positive edge above the existing LEAN gate."""
    if ev is None:
        return "PASS"
    try:
        value = float(ev)
    except (TypeError, ValueError):
        return "PASS"
    if not math.isfinite(value):
        return "PASS"
    return "VALUE" if value >= VALUE_EV_THRESHOLD else "PASS"


def model_market_discrepancy(probability, market_probability) -> Optional[float]:
    """Signed model-vs-market probability gap, or None when unavailable.

    Descriptive only. The caller decides what to print; this module never
    converts it into a bet-suppression rule.
    """
    if probability is None or market_probability is None:
        return None
    try:
        model, market = float(probability), float(market_probability)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(model) and math.isfinite(market)):
        return None
    return model - market


def dual_signal(selection, probability, price=None, ev=None,
                market_probability=None) -> dict:
    return {
        "selection": selection,
        "probability": None if probability is None else float(probability),
        "probability_display": format_probability(probability),
        "flag": probability_flag(probability),
        "price": price,
        "price_display": format_price(price),
        "ev": None if ev is None else float(ev),
        "ev_display": format_ev(ev),
        "value_verdict": value_verdict(ev),
        "discrepancy": model_market_discrepancy(probability, market_probability),
    }


def high_probability_lines(selection, probability, price=None, ev=None,
                           market_probability=None) -> list:
    """The visible block, or an empty list below the threshold."""
    signal = dual_signal(selection, probability, price, ev, market_probability)
    if signal["flag"] != "HIGH":
        return []
    lines = [f"HIGH MODEL PROBABILITY - OVER {HIGH_PROBABILITY_THRESHOLD:.0%}", "",
             f"Selection: {selection}",
             f"Model probability: {signal['probability_display']}",
             f"Odds: {signal['price_display']}",
             f"Estimated EV: {signal['ev_display']}",
             f"Value verdict: {signal['value_verdict']}",
             f"Probability flag: {signal['flag']}"]
    if signal["discrepancy"] is not None and abs(signal["discrepancy"]) >= 0.10:
        # Neutral wording: a gap this size is a data/information signal (an
        # injury, a lineup, a stale quote), not a demonstrated edge.
        lines.append(f"MODEL/MARKET DISCREPANCY: {signal['discrepancy']:+.1%} "
                     f"(neither score is treated as correct)")
    lines.append("A likely winner can still be a losing bet: probability and "
                 "value are separate signals.")
    return lines


def cohort_for(probability, exploratory: bool = False) -> Optional[str]:
    """Persisted tag so these rows can be graded and reported separately."""
    if exploratory:
        return EXPLORATORY_COHORT
    if probability is None:
        return None
    try:
        value = float(probability)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or not 0 <= value <= 1:
        return None
    return HIGH_COHORT if value >= HIGH_PROBABILITY_THRESHOLD else None


def _side_from(text):
    text = (text or "").upper()
    for token in ("AWAY", "HOME", "UNDER", "OVER"):
        if token in text:
            return token
    return None


def _same_line(left, right, tolerance=1e-9):
    try:
        return abs(float(left) - float(right)) <= tolerance
    except (TypeError, ValueError):
        return False


def _from_markets(raw, market_type, line=None):
    """Picked-side probability from the EV engine, matching kind AND line.

    Matching kind alone is not enough: a spread row also stores a moneyline
    entry and alternate totals share a kind, so the line has to agree too or a
    selection gets priced off a different market than the one it settled on.
    """
    for market in raw.get("markets") or []:
        if not isinstance(market, dict):
            continue
        if str(market.get("kind") or "").lower() != (market_type or "").lower():
            continue
        if line is not None and market.get("line") is not None \
                and not _same_line(market.get("line"), line):
            continue
        pick = _side_from(market.get("pick"))
        if pick is None:
            continue
        if pick in ("HOME", "OVER"):
            p, price, ev, other = (market.get("prob_a"), market.get("price_a"),
                                   market.get("ev_a"), market.get("price_b"))
        else:
            p, price, ev, other = (market.get("prob_b"), market.get("price_b"),
                                   market.get("ev_b"), market.get("price_a"))
        if p is None:
            continue
        return dict(probability=float(p), price=price, ev=ev, pick=pick,
                    price_other=other, source="markets")
    return None


def _from_probability_fields(raw, market_type):
    """Fallbacks for engines that store a probability but no priced market list."""
    if market_type in ("moneyline", "ml"):
        blocks = [raw.get("moneyline"), raw.get("game")]
        for block in blocks:
            if not isinstance(block, dict):
                continue
            home = block.get("home_win_probability", block.get("home_win_prob"))
            away = block.get("away_win_probability", block.get("away_win_prob"))
            if home is None:
                continue
            pick = _side_from(raw.get("_pick"))
            if pick in ("HOME", "AWAY"):
                probability = float(home) if pick == "HOME" else 1.0 - float(home)
            else:
                pick = "HOME" if float(home) >= 0.5 else "AWAY"
                probability = float(home) if pick == "HOME" else 1.0 - float(home)
            odds = raw.get("market_odds") or {}
            price = odds.get("home_ml") if pick == "HOME" else odds.get("away_ml")
            return dict(probability=probability, price=price, ev=None, pick=pick,
                        price_other=odds.get("away_ml" if pick == "HOME" else "home_ml"),
                        source="probability_field")
    if market_type in ("total", "spread"):
        block = raw.get(market_type)
        if isinstance(block, dict):
            key = "prob" if "prob" in block else "cover_prob"
            probability = block.get(key)
            if probability is None:
                return None
            pick = _side_from(block.get("pick") or raw.get("_pick"))
            return dict(probability=float(probability), price=None, ev=None,
                        pick=pick, price_other=None, source="probability_field")
    return None


def picked_side_signal(market_type, raw, line=None, recommendation=None):
    """Best-effort picked-side probability for one stored row.

    Returns a dict with probability/price/ev/pick/source, or None when the row
    does not say which side it is on. Never guesses a side it cannot read.
    """
    if not isinstance(raw, dict):
        return None
    market_type = (market_type or "").strip().lower()
    signal = _from_markets(raw, market_type, line)
    if signal is None:
        signal = _from_probability_fields(raw, market_type)
    if signal is None:
        return None
    if signal.get("pick") is None:
        return None
    return signal


def highest_probability_selection(entries):
    """Pick the largest-probability entry from [(selection, p, price, ev)]."""
    usable = [e for e in entries if e[1] is not None]
    if not usable:
        return None
    return max(usable, key=lambda item: item[1])
