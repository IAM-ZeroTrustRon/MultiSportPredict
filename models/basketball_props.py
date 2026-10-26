"""Minutes and research stat projections for basketball player props.

Two rules shape this module:

1. Nothing that matters is hand-tuned. The only fitted object is a least-squares
   map from recent-rotation means to realised minutes, and its coefficients are
   reported verbatim so a reader can reject them. Back-to-backs, foul trouble,
   blowout risk, injuries and role changes are *not* given invented coefficients;
   where they cannot be measured they are reported as unavailable.
2. A projection is a research expectation, never a bet. No cover probability, no
   expected value, no stake and no recommendation is produced here.
"""

from __future__ import annotations

import math

from features.basketball_props import (
    APPEARED,
    COMBOS,
    DID_NOT_PLAY,
    STATS,
    appearance_windows,
    combo_means,
    has_minutes,
    mean_or_none,
    minutes_observation,
    to_float,
)

MIN_REGULATION_MINUTES = 48.0
MAX_MINUTES = 68.0
MIN_HISTORY_APPEARANCES = 3
MIN_RATE_APPEARANCES = 5
MIN_FIT_SAMPLES = 30
CANDIDATE_FEATURES = ("window5_minutes", "window10_minutes", "window20_minutes",
                      "season_minutes", "starter_freq_last10")

REFUSED_DESIGNATIONS = {"OUT", "DOUBTFUL", "SUSPENDED", "INJURED RESERVE", "IR", "INACTIVE", "NWT"}
CAUTION_DESIGNATIONS = {"QUESTIONABLE", "GAME TIME DECISION", "GTD", "PROBABLE", "DAY-TO-DAY"}
# Availability is a closed set, not an open one. A status only counts as cleared
# when it is published in exactly one of these forms; every other string - including
# plausible-looking prose such as "REPORT NOT SUBMITTED" - stays UNKNOWN.
ACTIONABLE_DESIGNATIONS = {"AVAILABLE", "ACTIVE", "CLEARED"}


def availability_decision(designation):
    """Classify a pregame availability designation.

    Only an explicitly recognised cleared status is actionable. REFUSED
designations get no projection at all; anything unrecognised - blank, null, prose,
or a status this module has never been taught - is unknown and therefore never
actionable. Missing information must never decay into permission.
    """
    text = (designation or "").strip().upper()
    if not text or text in {"UNKNOWN", "UNLISTED", "NOT LISTED"}:
        return {"designation": designation or "UNKNOWN", "level": "unknown", "actionable": False,
                "refuse": False, "note": "availability not verified; research output only"}
    # "SUSPENSION" does not contain "SUSPEND"; the stem is "SUSPENS".
    if text in REFUSED_DESIGNATIONS or any(k in text for k in ("OUT", "DOUBTFUL", "SUSPENS")):
        return {"designation": designation, "level": "unavailable", "actionable": False,
                "refuse": True, "note": "player is not available; no projection is issued"}
    if text in CAUTION_DESIGNATIONS:
        return {"designation": designation, "level": "uncertain", "actionable": False,
                "refuse": False, "note": "availability uncertain; research output only"}
    if text in ACTIONABLE_DESIGNATIONS:
        return {"designation": designation, "level": "available", "actionable": True,
                "refuse": False, "note": "explicitly cleared to play"}
    return {"designation": designation, "level": "unknown", "actionable": False,
            "refuse": False, "note": (f"unrecognised status {designation!r}; treated as unknown, "
                                       "not as clearance")}


def clamp_minutes(value, allow_overtime=False):
    """Force a projection into physically possible minutes."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    ceiling = MAX_MINUTES if allow_overtime else MIN_REGULATION_MINUTES
    return max(0.0, min(number, ceiling))


def baseline_minutes(features):
    """Transparent recent-rotation baseline: the most recent usable window mean.

    Preference order is pre-declared (10, then 5, then 20, then season mean). No
    weighting is applied, so this is reproducible by hand from the printed window
    means.
    """
    windows = features.get("windows") or {}
    for size in (10, 5, 20):
        value = (windows.get(size) or {}).get("minutes_mean")
        if value is not None:
            return value
    return features.get("minutes_season_mean")


def candidate_vector(features):
    windows = features.get("windows") or {}
    return [
        (windows.get(5) or {}).get("minutes_mean"),
        (windows.get(10) or {}).get("minutes_mean"),
        (windows.get(20) or {}).get("minutes_mean"),
        features.get("minutes_season_mean"),
        features.get("starter_freq_last10"),
    ]


def fit_minutes_model(samples, ridge=1e-8):
    """Least-squares fit of recent-rotation means onto realised minutes.

    ``samples`` is a list of ``(feature_vector, realised_minutes)`` built only from
    the training period. Coefficients are fitted, never chosen, and are returned
    for disclosure. Returns ``None`` when the sample cannot support a fit.
    """
    usable = [(vec, float(target)) for vec, target in samples
              if len(vec) == len(CANDIDATE_FEATURES) and all(v is not None for v in vec)
              and target is not None]
    if len(usable) < MIN_FIT_SAMPLES:
        return None
    import numpy as np
    matrix = np.array([[1.0, *[float(v) for v in vec]] for vec, _ in usable], dtype=float)
    target = np.array([t for _, t in usable], dtype=float)
    # A tiny ridge keeps collinear window means (5/10/20 are nested) from blowing
    # up; it is a numerical guard, not a tuning choice.
    penalty = ridge * np.eye(matrix.shape[1])
    penalty[0, 0] = 0.0
    solution = np.linalg.solve(matrix.T @ matrix + penalty, matrix.T @ target)
    return {
        "intercept": float(solution[0]),
        "weights": [float(w) for w in solution[1:]],
        "features": list(CANDIDATE_FEATURES),
        "n_train": len(usable),
        "ridge": ridge,
        "note": ("Fitted on the training period only. Nested window means are "
                 "collinear, so individual weights are not interpretable in isolation."),
    }


def candidate_minutes(features, coefficients):
    if not coefficients:
        return None
    vector = candidate_vector(features)
    if any(v is None for v in vector):
        return None
    value = coefficients["intercept"] + sum(w * float(v) for w, v in zip(coefficients["weights"], vector))
    return value


def project_player(features, minutes_model=None, designation=None, allow_overtime=False,
                   minutes_restriction=None):
    """Turn appearance features into a research projection for one player.

    The projection refuses outright when a player is OUT or DOUBTFUL, and refuses
    when there is not enough appearance history to project from.
    """
    availability = availability_decision(designation)
    warnings = list(features.get("stale_reasons") or [])
    if availability["level"] != "available":
        warnings.append(f"availability {availability['level']}: {availability['note']}")
    base = {
        "availability": availability,
        "research_only": True,
        "n_appearances": features.get("n_appearances", 0),
        "last_appearance_date": features.get("last_appearance_date"),
        "rest_days": features.get("rest_days"),
        "missed_team_games": features.get("missed_team_games"),
        "team_changes_20": features.get("team_changes_20"),
        "overtime_share": features.get("overtime_share"),
        "windows": features.get("windows"),
        "season_labels": features.get("season_labels"),
        "last_appearance_season": features.get("last_appearance_season"),
        "target_season": features.get("target_season"),
        "crosses_season": features.get("crosses_season"),
        "stale_rotation": features.get("stale_rotation"),
        "warnings": warnings,
    }
    if availability["refuse"]:
        return {**base, "refused": True, "status": "REFUSED",
                "reason": "player is unavailable; no projection is issued"}
    if features.get("n_appearances", 0) < MIN_HISTORY_APPEARANCES:
        return {**base, "refused": True, "status": "INSUFFICIENT_HISTORY",
                "reason": (f"only {features.get('n_appearances', 0)} usable appearance(s); "
                           f"{MIN_HISTORY_APPEARANCES} required")}

    baseline = clamp_minutes(baseline_minutes(features), allow_overtime)
    candidate = clamp_minutes(candidate_minutes(features, minutes_model), allow_overtime)
    projected = candidate if candidate is not None else baseline
    basis = "fitted_recent_rotation" if candidate is not None else "recent_rotation_baseline"
    if minutes_restriction is not None:
        cap = clamp_minutes(minutes_restriction, allow_overtime=True)
        if cap is not None and projected is not None and projected > cap:
            projected = cap
            basis = basis + "+minutes_restriction_cap"

    rates = features.get("rates_last10") or {}
    if (rates.get("_appearances") or 0) < MIN_RATE_APPEARANCES:
        rates = features.get("rates_all") or {}
        rate_window = "all_appearances"
    else:
        rate_window = "last10_appearances"

    means = {}
    for stat in STATS:
        rate = rates.get(stat)
        means[stat] = (projected * rate) if (projected is not None and rate is not None) else None

    return {
        **base,
        "refused": False,
        "status": "RESEARCH",
        "projected_minutes": projected,
        "baseline_minutes": baseline,
        "candidate_minutes": candidate,
        "minutes_basis": basis,
        "minutes_restriction": minutes_restriction,
        "rate_window": rate_window,
        "rate_sample_appearances": rates.get("_appearances"),
        "per_minute": {stat: rates.get(stat) for stat in STATS},
        "projected_stats": means,
        "projected_combos": combo_means(means),
        "overtime_assumption": ("minutes include overtime; projections are not "
                                "adjusted for it"),
    }


def _index_rows(rows):
    by_player, by_team = {}, {}
    for row in rows:
        by_player.setdefault(str(row.get("player_id")), []).append(row)
        if row.get("team_id") is not None:
            by_team.setdefault(str(row.get("team_id")), []).append(row)
    return by_player, by_team


def chronological_split(rows, train_fraction=0.6):
    """Split on whole game dates so no fixture can straddle train and test."""
    dates = sorted({str(r.get("game_date"))[:10] for r in rows if r.get("game_date")})
    if len(dates) < 4:
        return [], [], None
    index = int(round(len(dates) * train_fraction))
    index = max(1, min(len(dates) - 1, index))
    cut = dates[index]
    train = [r for r in rows if str(r.get("game_date"))[:10] < cut]
    test = [r for r in rows if str(r.get("game_date"))[:10] >= cut]
    return train, test, cut


def _features_for(row, by_player, by_team):
    player_rows = by_player.get(str(row.get("player_id")), [])
    team_rows = by_team.get(str(row.get("team_id")), [])
    return appearance_windows(player_rows, row.get("game_date"), team_rows)


def _error_summary(errors):
    if not errors:
        return {"n": 0, "mae": None, "bias": None, "rmse": None}
    n = len(errors)
    return {
        "n": n,
        "mae": sum(abs(e) for e, _ in errors) / n,
        "bias": sum(e for e, _ in errors) / n,
        "rmse": math.sqrt(sum(e * e for e, _ in errors) / n),
    }


def validate(rows, train_fraction=0.6, allow_overtime=False):
    """Chronological comparison reported on two separate questions.

    * **Played-game accuracy** - given that the player appeared, how close were the
      minutes and stats? This is the conventional MAE and it silently conditions on
      participation.
    * **Participation** - how often did a projectable player actually appear? A
      projection that nails minutes on the games a player played while missing the
      ones they sat out is not accurate, it is selectively accurate.

    These are reported side by side and never merged into a single score. Baseline
    and candidate statistics are also reported separately, because a variant that
    wins on minutes can lose on every stat.

    Features for every row are built only from that row's own past, so the test
    period never sees its own outcomes. Role segmentation uses the target game's
    actual starter flag for *reporting only*; it is never an input to a projection.
    """
    all_rows = [r for r in rows if r.get("game_date")]
    train, test, cut = chronological_split(all_rows, train_fraction)
    if not test:
        return {"status": "insufficient_dates", "n_train": len(train), "n_test": len(test)}
    by_player, by_team = _index_rows(all_rows)

    samples = []
    for row in train:
        if not has_minutes(row):
            continue
        features = _features_for(row, by_player, by_team)
        samples.append((candidate_vector(features), to_float(row.get("minutes"))))
    model = fit_minutes_model(samples)

    played_errors = {"baseline": [], "candidate": []}
    inclusive_errors = {"baseline": [], "candidate": []}
    stat_errors = {"baseline": {k: [] for k in (*STATS, *COMBOS)},
                   "candidate": {k: [] for k in (*STATS, *COMBOS)}}
    role_errors = {}
    participation = {"projectable_rows": 0, "appeared": 0, "did_not_play": 0,
                     "listed_zero_minutes": 0, "unverified": 0, "excluded_from_error": 0}

    for row in test:
        features = _features_for(row, by_player, by_team)
        if features.get("n_appearances", 0) < MIN_HISTORY_APPEARANCES:
            continue
        participation["projectable_rows"] += 1
        kind, observed = minutes_observation(row)
        if kind == APPEARED:
            participation["appeared"] += 1
            if observed == 0.0:
                participation["listed_zero_minutes"] += 1
        elif kind == DID_NOT_PLAY:
            participation["did_not_play"] += 1
        else:
            # An unobserved player is not a zero-minute player. Excluding the row
            # keeps the error statistics honest instead of inventing a miss.
            participation["unverified"] += 1
            participation["excluded_from_error"] += 1
            continue

        predictions = {
            "baseline": clamp_minutes(baseline_minutes(features), allow_overtime),
            "candidate": clamp_minutes(candidate_minutes(features, model), allow_overtime),
        }
        for variant, predicted in predictions.items():
            if predicted is None:
                continue
            inclusive_errors[variant].append((predicted - observed, row))
            if kind == APPEARED:
                played_errors[variant].append((predicted - observed, row))
                role = "starter" if row.get("starter") else "bench"
                role_errors.setdefault(role, {"baseline": [], "candidate": []})
                role_errors[role][variant].append((predicted - observed, row))

        if kind != APPEARED:
            continue
        for variant, minutes_model in (("baseline", None), ("candidate", model)):
            if variant == "candidate" and minutes_model is None:
                continue
            projection = project_player(features, minutes_model, allow_overtime=allow_overtime)
            if projection.get("refused"):
                continue
            for stat in STATS:
                predicted = (projection["projected_stats"] or {}).get(stat)
                observed_stat = to_float(row.get(stat))
                if predicted is not None and observed_stat is not None:
                    stat_errors[variant][stat].append((predicted - observed_stat, row))
            for combo in COMBOS:
                predicted = (projection["projected_combos"] or {}).get(combo)
                if predicted is None:
                    continue
                parts = [to_float(row.get(p)) for p in COMBOS[combo]]
                if any(v is None for v in parts):
                    continue
                stat_errors[variant][combo].append((predicted - sum(parts), row))

    rows_with_participation = participation["appeared"] + participation["did_not_play"]
    rate = (participation["appeared"] / rows_with_participation) if rows_with_participation else None

    return {
        "status": "ok",
        "cutoff_date": cut,
        "train_fraction": train_fraction,
        "n_train_rows": len(train),
        "n_test_rows": len(test),
        "n_train_dates": len({str(r.get("game_date"))[:10] for r in train}),
        "n_test_dates": len({str(r.get("game_date"))[:10] for r in test}),
        "minutes_model": model,
        "played_game_accuracy": {variant: _error_summary(errors)
                                 for variant, errors in played_errors.items()},
        "participation_inclusive": {variant: _error_summary(errors)
                                    for variant, errors in inclusive_errors.items()},
        "participation": {**participation, "confirmed_rows": rows_with_participation,
                          "appearance_rate": rate},
        "by_role_played_games": {role: {"baseline": _error_summary(v["baseline"]),
                                        "candidate": _error_summary(v["candidate"])}
                                 for role, v in role_errors.items()},
        "stat_projection_error": {variant: {k: _error_summary(v) for k, v in blocks.items()}
                                  for variant, blocks in stat_errors.items()},
        "notes": [
            "played_game_accuracy conditions on the player appearing; it is not a "
            "statement about games the player sat out.",
            "participation_inclusive counts a did-not-play as zero minutes and is the "
            "harder, less flattering number.",
            "Unverified rows (no confirmed appearance and no confirmed did-not-play) are "
            "excluded from every error block. They are counted in participation only.",
            "Errors are absolute projection misses in the sport's own units, not "
            "betting returns. A lower number here does not imply profit.",
        ],
    }
