"""Prop probabilities from measured projection residuals, not an invented spread.

Why this method
---------------
A projected average is not a probability. Turning "24.1 points" into
"P(over 22.5)" needs a distribution, and there are only two honest ways to get
one: measure it, or assume it. This module measures it.

Every stored player-game is re-projected using exactly the same cutoff rule the
live run uses (only games strictly before that game, same minutes baseline, same
per-minute rates). The difference between the realised stat and that projection is
a residual. The empirical distribution of those residuals is the uncertainty the
model has actually demonstrated, so ``P(over L)`` is the share of measured
residuals that would have cleared ``L``.

Combos are **not** built by multiplying component probabilities. PRA, PA and RA
are counted from the joint residual of the same historical game, so a player who
rebounds and assists together keeps that dependence. No combo variance is
invented and no independence is assumed.

Known limits, disclosed in every output
---------------------------------------
* Residuals are pooled across players, optionally within a minutes band. A
  player's own role-specific variance is not modelled.
* The pool says nothing about the market's opinion. Cover probabilities here are
  unvalidated against prices; they are MODEL ESTIMATES until a line-level
  calibration exists.
* Stat counts are integers, so an integral line can push. The reconstruction is
  rounded before settling, which is why ``push`` can be non-zero and why an
  integer line is never treated as a free win.
"""

from __future__ import annotations

import math
import statistics

from features.basketball_props import STATS, appearance_windows, has_minutes, to_float
from models.basketball_props import MIN_HISTORY_APPEARANCES, project_player

COMBO_PARTS = {
    "pra": ("points", "rebounds", "assists"),
    "pa": ("points", "assists"),
    "ra": ("rebounds", "assists"),
}
MARKETS = {stat: (stat,) for stat in STATS} | COMBO_PARTS
BAND_WIDTH = 8.0
MIN_BAND_SAMPLES = 80
MIN_POOL_SAMPLES = 40


def minutes_band(minutes):
    """Coarse rotation band. Wider than a role, narrower than the whole league."""
    if minutes is None or not math.isfinite(float(minutes)):
        return None
    return int(float(minutes) // BAND_WIDTH)


def _features(row, by_player, by_team):
    return appearance_windows(by_player.get(str(row.get("player_id")), []),
                              row.get("game_date"),
                              by_team.get(str(row.get("team_id")), []))


def build_residual_pool(rows, cutoff_date, minutes_model=None, verbose=False):
    """Measured residuals for every stored player-game strictly before the cutoff.

    ``rows`` are stored player-game records; ``cutoff_date`` is the fixture being
    projected, so nothing on or after it can enter the pool.
    """
    cutoff = str(cutoff_date)[:10]
    by_player, by_team = {}, {}
    for row in rows:
        by_player.setdefault(str(row.get("player_id")), []).append(row)
        if row.get("team_id") is not None:
            by_team.setdefault(str(row.get("team_id")), []).append(row)

    singles = {stat: {} for stat in STATS}
    combos = {name: {} for name in COMBO_PARTS}
    used = skipped = 0
    for row in rows:
        if str(row.get("game_date") or "")[:10] >= cutoff:
            continue
        if not has_minutes(row):
            continue
        features = _features(row, by_player, by_team)
        if features.get("n_appearances", 0) < MIN_HISTORY_APPEARANCES:
            continue
        projection = project_player(features, minutes_model)
        if projection.get("refused"):
            continue
        projected_minutes = projection.get("projected_minutes")
        band = minutes_band(projected_minutes)
        if band is None:
            skipped += 1
            continue
        means = projection.get("projected_stats") or {}
        residuals = {}
        for stat in STATS:
            actual = to_float(row.get(stat))
            mean = means.get(stat)
            if actual is None or mean is None:
                continue
            residuals[stat] = actual - float(mean)
            singles[stat].setdefault(band, []).append(actual - float(mean))
        if len(residuals) == len(STATS):
            for name, parts in COMBO_PARTS.items():
                combos[name].setdefault(band, []).append(tuple(residuals[p] for p in parts))
        used += 1
    if verbose:
        print(f"  residual pool: {used} games used, {skipped} skipped")
    return {
        "cutoff_date": cutoff,
        "games_used": used,
        "games_skipped": skipped,
        "singles": singles,
        "combos": combos,
        "band_width_minutes": BAND_WIDTH,
        "assumptions": [
            "Residuals are measured out-of-sample per game: each stored game is re-projected "
            "from only the games before it.",
            "Residuals are pooled across players, optionally within a rotation-minutes band.",
            "Combos use the joint residual of the same historical game; component "
            "probabilities are never multiplied.",
            "No distribution is assumed: probabilities are empirical frequencies.",
        ],
    }


def _band_samples(pool, market, band):
    table = pool["singles"][market] if market in STATS else pool["combos"][market]
    if band is not None and len(table.get(band) or []) >= MIN_BAND_SAMPLES:
        return table[band], f"minutes band {band * BAND_WIDTH:.0f}-{(band + 1) * BAND_WIDTH:.0f}"
    pooled = [item for values in table.values() for item in values]
    return pooled, "all rotation bands (band sample too small)"


def pool_size(pool):
    return {market: len([x for values in
                         (pool["singles"][market] if market in STATS else pool["combos"][market]).values()
                         for x in values]) for market in MARKETS}


def residual_scale(pool, market, projected_minutes):
    """Measured mean absolute residual for this market and rotation band.

    This is the model's demonstrated error, in the market's own units. It is the
    yardstick for deciding whether a projection is precise enough to price a line
    at all.
    """
    if market not in MARKETS:
        return None
    samples, _ = _band_samples(pool, market, minutes_band(projected_minutes))
    if len(samples) < MIN_POOL_SAMPLES:
        return None
    parts = MARKETS[market]
    values = [item if len(parts) == 1 else sum(item) for item in samples]
    return sum(abs(value) for value in values) / len(values)


def priceability(projected_mean, line, error_scale):
    """Refuse to price a line the projection cannot resolve.

    A model claiming a 6-point edge while its own typical miss is 5 points has not
    demonstrated an edge; it has demonstrated noise. When the gap between the
    projection and the offered line exceeds the measured absolute error, EV is
    withheld with that reason rather than printed as a large fake edge. This is a
    refusal rule, not a tuned betting threshold: the yardstick is the model's own
    measured error.
    """
    if projected_mean is None or line is None or error_scale is None:
        return {"priceable": False, "reason": "projection, line or error scale missing"}
    gap = abs(float(projected_mean) - float(line))
    if gap > float(error_scale):
        return {"priceable": False, "gap": gap, "error_scale": float(error_scale),
                "reason": (f"projection {float(projected_mean):.1f} is {gap:.1f} from the line, "
                           f"beyond the measured mean absolute error {float(error_scale):.1f}; "
                           "EV would not be distinguishable from projection error")}
    return {"priceable": True, "gap": gap, "error_scale": float(error_scale)}


def probability_for(pool, market, projected_mean, projected_minutes, line):
    """Empirical over/under/push probabilities for one exact line.

    Returns a dict with probabilities or ``status='unavailable'`` and the specific
    reason, so a caller can print ``--`` instead of a fabricated number.
    """
    if market not in MARKETS:
        return {"status": "unavailable", "reason": f"unsupported market {market!r}"}
    if projected_mean is None or line is None:
        return {"status": "unavailable", "reason": "projection or line is missing"}
    samples, scope = _band_samples(pool, market, minutes_band(projected_minutes))
    if len(samples) < MIN_POOL_SAMPLES:
        return {"status": "unavailable",
                "reason": f"only {len(samples)} measured residuals (need {MIN_POOL_SAMPLES})",
                "samples": len(samples)}
    parts = MARKETS[market]
    actuals = []
    for item in samples:
        offset = item if len(parts) == 1 else sum(item)
        value = float(projected_mean) + float(offset)
        # Points/rebounds/assists are counts. On an integral line the settled value
        # must be an integer, otherwise a genuine push could never be observed.
        if float(line).is_integer():
            value = float(round(value))
        actuals.append(value)
    n = len(actuals)
    over = sum(1 for value in actuals if value > line) / n
    under = sum(1 for value in actuals if value < line) / n
    push = sum(1 for value in actuals if value == line) / n
    total = over + under + push
    return {
        "status": "ok",
        "market": market,
        "line": float(line),
        "over": over / total,
        "under": under / total,
        "push": push / total,
        "samples": n,
        "scope": scope,
        "projected_mean": float(projected_mean),
        "residual_median": statistics.median(
            [item if len(parts) == 1 else sum(item) for item in samples]),
        "method": "empirical residual frequency; unvalidated against market prices",
    }


def probability_block(pool, markets, projections, minutes, lines):
    """Convenience wrapper: {market: probability_for(...)} for priced markets only."""
    out = {}
    for market, line in lines.items():
        if market not in markets:
            continue
        out[market] = probability_for(pool, market, projections.get(market), minutes, line)
    return out
