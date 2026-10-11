"""Custom tennis lines from an Elo-anchored scoring approximation.

Game markets use measured surface serve/return inputs when supplied, otherwise
a labelled 75% baseline hold rate. Independent standard tiebreak sets remain
model assumptions.
No betting recommendation is issued before this model is calibrated.
"""
import math
from collections import defaultdict
from functools import lru_cache


def _match_probability(p, needed):
    return sum(math.comb(needed + losses - 1, losses) * p ** needed *
               (1 - p) ** losses for losses in range(needed))


def set_probability(match_prob, needed):
    low, high = 0.0, 1.0
    for _ in range(50):
        mid = (low + high) / 2
        if _match_probability(mid, needed) < match_prob:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def _set_scores(delta, home_hold=0.75, away_hold=0.75):
    scores = defaultdict(float)
    for first_server in (0, 1):
        active = {(0, 0): 0.5}
        while active:
            following = defaultdict(float)
            for (a, b), weight in active.items():
                if (a >= 6 or b >= 6) and abs(a - b) >= 2:
                    scores[a, b] += weight
                elif a == b == 6:
                    # Tiebreak strength is an explicit approximation.
                    p = max(0.01, min(0.99, 0.5 + 2 * delta))
                    scores[7, 6] += weight * p
                    scores[6, 7] += weight * (1 - p)
                else:
                    home_serves = (first_server + a + b) % 2 == 0
                    p = (home_hold if home_serves else 1-away_hold) + delta
                    following[a + 1, b] += weight * p
                    following[a, b + 1] += weight * (1 - p)
            active = following
    return dict(scores)


@lru_cache(maxsize=128)
def score_distribution(match_prob, best_of_5, home_hold=0.75, away_hold=0.75):
    if not all(math.isfinite(v) and 0 < v < 1 for v in (match_prob, home_hold, away_hold)):
        raise ValueError("Match and hold probabilities must be finite and inside (0, 1)")
    needed = 3 if best_of_5 else 2
    target = set_probability(match_prob, needed)
    low = max(-home_hold, -(1-away_hold))+0.001
    high = min(1-home_hold, away_hold)-0.001
    for _ in range(40):
        mid = (low + high) / 2
        scores = _set_scores(mid, home_hold, away_hold)
        p = sum(w for (a, b), w in scores.items() if a > b)
        if p < target:
            low = mid
        else:
            high = mid
    scores = _set_scores((low + high) / 2, home_hold, away_hold)
    achieved = sum(w for (a, b), w in scores.items() if a > b)
    if abs(achieved-target) > 1e-6:
        raise ValueError("Hold inputs cannot support the Elo probability under this scoring approximation")
    active = {(0, 0, 0, 0): 1.0}
    final = defaultdict(float)
    while active:
        following = defaultdict(float)
        for (sa, sb, ga, gb), weight in active.items():
            if sa == needed or sb == needed:
                final[sa, sb, ga, gb] += weight
                continue
            for (a, b), probability in scores.items():
                following[sa + (a > b), sb + (b > a), ga + a, gb + b] += weight * probability
        active = following
    return dict(final)


def evaluate_markets(match_prob, best_of_5, specs, holds=None):
    if not specs:
        return []
    distribution = score_distribution(float(match_prob), bool(best_of_5),
        holds["home_hold"] if holds else 0.75, holds["away_hold"] if holds else 0.75)
    results = []
    for spec in specs:
        kind = spec["kind"]
        if kind not in {"games_total", "sets_total", "games_spread", "sets_spread"}:
            raise ValueError(f"Unknown tennis market: {kind}")
        line = float(spec["line"])
        if not math.isfinite(line) or abs(line * 2 - round(line * 2)) > 1e-8:
            raise ValueError("Tennis lines must be finite whole or half numbers")
        if kind.endswith("total") and line < 0:
            raise ValueError("Totals cannot be negative")
        win = lose = push = 0.0
        for (sa, sb, ga, gb), weight in distribution.items():
            value = {"games_total": ga + gb - line, "sets_total": sa + sb - line,
                     "games_spread": ga - gb + line, "sets_spread": sa - sb + line}[kind]
            if value > 0:
                win += weight
            elif value < 0:
                lose += weight
            else:
                push += weight
        prices = [spec.get("price_a"), spec.get("price_b")]
        ev = []
        for probability, loss, price in ((win, lose, prices[0]), (lose, win, prices[1])):
            if price is None:
                ev.append(None)
                continue
            price = float(price)
            if not math.isfinite(price) or abs(price) < 100:
                raise ValueError("American odds must be <= -100 or >= +100")
            profit = price / 100 if price > 0 else 100 / -price
            ev.append(probability * profit - loss)
        results.append({**spec, "prob_a": round(win, 6), "prob_b": round(lose, 6),
                        "push_prob": round(push, 6), "ev_a": ev[0], "ev_b": ev[1],
                        "recommendation": "MODEL ONLY — uncalibrated", "confidence": None,
                        "note": holds["source"] if holds else "Elo-derived sets; game scores assume 75% baseline hold. No measured player serve/return inputs."})
    return results
