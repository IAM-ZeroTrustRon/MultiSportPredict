"""Player appearance features for basketball prop research.

Every function here is pure: no network, no disk, no clock. That is deliberate.
The only rule that really matters for a prop model is that a forecast may never
see the game it is forecasting, so the cutoff logic lives in one place and can be
tested directly instead of being buried inside a runner.

A "row" is one player-game record produced by ``ingest_basketball_props``:

    player_id, player_name, team_id, team, opponent, event_id, game_date,
    game_datetime, season, competition, status, starter, did_not_play, reason,
    minutes, points, rebounds, assists, overtime, periods, source, retrieved_at

``status`` is ``played`` or ``dnp``. A ``played`` row with zero minutes is a real
listed appearance; it is not the same thing as a DNP and not the same thing as
missing data. Those three cases are kept distinct throughout.
"""

from __future__ import annotations

import statistics
from collections import Counter

COMPETITION = "NBA"
STATS = ("points", "rebounds", "assists")
COMBOS = {
    "pra": ("points", "rebounds", "assists"),
    "pa": ("points", "assists"),
    "ra": ("rebounds", "assists"),
}
APPEARANCE_WINDOWS = (5, 10, 20)
# Declared, not fitted: a rotation older than this is flagged rather than trusted.
STALE_ROTATION_DAYS = 30
# Regulation is 48 minutes; a multi-overtime game can exceed it. Anything past
# this is a source error rather than a very long shift.
MAX_PHYSICAL_MINUTES = 68.0
MIN_WINDOW_SAMPLE = 3


def to_float(value):
    """Parse a box-score number. ``--`` and empty mean unavailable, never zero."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text in {"--", "-", "N/A"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def is_appearance(row):
    """Listed and played. Zero minutes still counts as an appearance."""
    return row.get("status") == "played" and row.get("minutes") is not None


def has_minutes(row):
    """Appearance that actually produced floor time, used for rotation windows."""
    return is_appearance(row) and to_float(row.get("minutes")) > 0


APPEARED = "appeared"
DID_NOT_PLAY = "did_not_play"
UNVERIFIED = "unverified"


def minutes_observation(row):
    """Classify one stored row into the three postgame states.

    Returns ``(kind, minutes)``. ``kind`` is one of:

    * ``appeared`` - confirmed appearance, including a listed zero-minute one. A
      zero-minute appearance is real data: the player dressed and did not play.
    * ``did_not_play`` - confirmed did-not-play. Observed minutes are ``0.0``.
    * ``unverified`` - the row cannot support a score, and ``minutes`` is ``None``.

    The distinction matters because a missing observation is not a zero. Scoring an
    unobserved player as 0.0 minutes manufactures an error the model never made, so
    unverified rows are excluded from error calculations rather than zero-filled.
    """
    minutes = to_float(row.get("minutes"))
    status = row.get("status")
    dnp_flag = row.get("did_not_play") is True

    if dnp_flag or status == "dnp":
        # A did-not-play that records floor time contradicts itself; refuse to guess.
        return (DID_NOT_PLAY, 0.0) if minutes in (None, 0.0) else (UNVERIFIED, None)
    if status == "played" and minutes is not None:
        return APPEARED, minutes
    return UNVERIFIED, None


def validate_row(row):
    """Return a list of reasons a stored row cannot be projected from."""
    problems = []
    if not row.get("player_id"):
        problems.append("missing player_id")
    if not row.get("event_id"):
        problems.append("missing event_id")
    if not row.get("game_date"):
        problems.append("missing game_date")
    competition = row.get("competition")
    if competition not in (None, "", COMPETITION):
        problems.append(f"competition mismatch: {competition!r}")
    minutes = to_float(row.get("minutes"))
    if minutes is not None and (minutes < 0 or minutes > MAX_PHYSICAL_MINUTES):
        problems.append(f"impossible minutes: {minutes}")
    for stat in STATS:
        value = to_float(row.get(stat))
        if value is not None and value < 0:
            problems.append(f"negative {stat}: {value}")
    if row.get("status") not in ("played", "dnp"):
        problems.append(f"unknown status: {row.get('status')!r}")
    if row.get("status") == "dnp" and minutes not in (None, 0.0):
        problems.append("DNP row carries minutes")
    return problems


def _row_rank(row):
    """Prefer the most complete record when the same player-game is duplicated."""
    played = 1 if row.get("status") == "played" else 0
    has_min = 1 if to_float(row.get("minutes")) is not None else 0
    return (played, has_min)


def dedupe(rows):
    """Collapse duplicate (player, event) rows, preferring the played record."""
    best = {}
    for row in rows:
        key = (str(row.get("player_id")), str(row.get("event_id")))
        previous = best.get(key)
        if previous is None or _row_rank(row) > _row_rank(previous):
            best[key] = row
    return [best[key] for key in sorted(best)]


def sort_rows(rows):
    return sorted(rows, key=lambda r: (str(r.get("game_date")), str(r.get("game_datetime") or ""),
                                       str(r.get("event_id"))))


def history_before(rows, cutoff_date, target_event_id=None):
    """Rows strictly earlier than the cutoff, with the target game always removed.

    The comparison is on the *date*, so a same-day doubleheader or a slate can
    never leak into its own feature row.
    """
    cutoff = str(cutoff_date)[:10]
    kept = []
    for row in rows:
        if target_event_id is not None and str(row.get("event_id")) == str(target_event_id):
            continue
        if str(row.get("game_date"))[:10] >= cutoff:
            continue
        kept.append(row)
    return sort_rows(kept)


def _minutes(row):
    return to_float(row.get("minutes"))


def _starter(row):
    return 1.0 if row.get("starter") else 0.0


def per_minute_rates(appearances, stats=STATS, exclude_overtime=False):
    """Minutes-weighted rates. Appearances missing a stat are skipped, not zeroed."""
    pool = [r for r in appearances if not (exclude_overtime and r.get("overtime"))]
    rates = {}
    for stat in stats:
        usable = [r for r in pool if to_float(r.get(stat)) is not None and _minutes(r)]
        total_minutes = sum(_minutes(r) for r in usable)
        if not usable or total_minutes <= 0:
            rates[stat] = None
            continue
        rates[stat] = sum(to_float(r.get(stat)) for r in usable) / total_minutes
    rates["_appearances"] = len(usable)
    rates["_minutes"] = sum(_minutes(r) for r in usable)
    return rates


def mean_or_none(values):
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def team_schedule_dates(team_rows):
    """Distinct game dates for a team, used for missed-game and rest information."""
    return sorted({str(r.get("game_date"))[:10] for r in team_rows if r.get("game_date")})


def appearance_windows(player_rows, cutoff_date, team_rows=None, windows=APPEARANCE_WINDOWS,
                       target_season=None, stale_days=STALE_ROTATION_DAYS,
                       season_scope_min=MIN_WINDOW_SAMPLE):
    """Everything a prop projection may know about a player before a cutoff date.

    ``player_rows`` is every stored row for one player; ``team_rows`` is every
    stored row for the player's current team so that missed games and rest can be
    measured against a real schedule rather than guessed.

    Rotation windows are **season-scoped** whenever the player has at least
    ``season_scope_min`` appearances in the forecast season. Pooling April games
    (rest days, different roster) with October games is what produced projections
    far below a player's current role, so a same-season sample is preferred and the
    choice is disclosed in ``window_scope``. With too few same-season appearances
    the most recent appearances are used instead, which is disclosed as
    ``prior_season_carryover`` rather than passed off as current form.
    """
    history = history_before(player_rows, cutoff_date)
    appearances = [r for r in history if has_minutes(r)]
    listed = [r for r in history if is_appearance(r)]
    zero_minute = [r for r in listed if not has_minutes(r)]
    dnps = [r for r in history if r.get("status") == "dnp"]

    same_season = ([r for r in appearances if r.get("season_label") == target_season]
                   if target_season else [])
    if target_season and len(same_season) >= season_scope_min:
        scoped, scope = same_season, "current_season"
    elif target_season and same_season:
        scoped, scope = appearances, "prior_season_carryover"
    else:
        scoped, scope = appearances, ("prior_season_only" if target_season else "all_appearances")

    window_stats = {}
    for size in windows:
        slice_ = scoped[-size:]
        minutes = [_minutes(r) for r in slice_]
        window_stats[size] = {
            "n": len(slice_),
            "minutes_mean": mean_or_none(minutes),
            "starter_freq": mean_or_none([_starter(r) for r in slice_]),
        }

    all_minutes = [_minutes(r) for r in scoped]
    last10 = scoped[-10:]
    last_ten_minutes = [_minutes(r) for r in last10]
    stability = None
    if len(last_ten_minutes) >= MIN_WINDOW_SAMPLE:
        stability = statistics.pstdev(last_ten_minutes)

    rest_days = None
    if appearances:
        from datetime import date
        try:
            last = date.fromisoformat(str(appearances[-1]["game_date"])[:10])
            target = date.fromisoformat(str(cutoff_date)[:10])
            rest_days = (target - last).days
        except ValueError:
            rest_days = None

    season_teams = {str(r.get("team_id")) for r in scoped[-20:] if r.get("team_id")}
    missed_games = None
    scheduled = None
    if team_rows:
        dates = [d for d in team_schedule_dates(team_rows) if d < str(cutoff_date)[:10]]
        scheduled = len(dates)
        listed_dates = {str(r.get("game_date"))[:10] for r in listed}
        missed_games = len([d for d in dates if d not in listed_dates])

    overtime_games = [r for r in appearances if r.get("overtime")]

    # Season identity is the feed's season label, never a calendar year, so an
    # off-season gap and a stale rotation are distinguishable from a real one.
    labels = sorted({r.get("season_label") for r in appearances if r.get("season_label")})
    last_label = appearances[-1].get("season_label") if appearances else None
    crosses_season = bool(target_season and last_label and last_label != target_season)
    stale_reasons = []
    if crosses_season:
        stale_reasons.append(f"last appearance is {last_label}, forecast season is {target_season}")
    if rest_days is not None and rest_days > stale_days:
        stale_reasons.append(f"{rest_days} days since last appearance (limit {stale_days})")
    if not appearances:
        stale_reasons.append("no recorded appearances")
    if scope == "prior_season_carryover":
        stale_reasons.append(
            f"only {len(same_season)} appearance(s) in {target_season} "
            f"(minimum {season_scope_min}); rotation is carried over from {labels[-1] if labels else 'an earlier season'}")

    return {
        "cutoff_date": str(cutoff_date)[:10],
        "windows": window_stats,
        "window_scope": scope,
        "window_season": target_season,
        "n_window_appearances": len(scoped),
        "same_season_appearances": len(same_season),
        "n_appearances": len(appearances),
        "n_listed": len(listed),
        "n_zero_minute_appearances": len(zero_minute),
        "n_dnp": len(dnps),
        "dnp_reason_counts": dict(Counter((r.get("reason") or "UNSPECIFIED").upper() for r in dnps)),
        "minutes_season_mean": mean_or_none(all_minutes),
        "minutes_last10_mean": mean_or_none(last_ten_minutes),
        "starter_freq_last10": mean_or_none([_starter(r) for r in last10]),
        "starter_freq_all": mean_or_none([_starter(r) for r in appearances]),
        "rotation_stability_stdev": stability,
        "rest_days": rest_days,
        "team_games_scheduled": scheduled,
        "missed_team_games": missed_games,
        "team_changes_20": len(season_teams),
        "team_ids_20": sorted(season_teams),
        "overtime_appearances": len(overtime_games),
        "overtime_share": (len(overtime_games) / len(appearances)) if appearances else None,
        "rates_last10": per_minute_rates(last10),
        # Minutes are role and are scoped by season; per-minute production is a
        # skill and is deliberately pooled over a larger recent sample. When the
        # same-season rate sample is thin, ``rates_all`` is the only supported
        # estimate, so it spans the season boundary on purpose.
        "rates_all": per_minute_rates(appearances),
        "last_appearance_date": str(appearances[-1]["game_date"])[:10] if appearances else None,
        "season_labels": labels,
        "last_appearance_season": last_label,
        "target_season": target_season,
        "crosses_season": crosses_season,
        "stale_rotation_days": stale_days,
        "stale_reasons": stale_reasons,
        "stale_rotation": bool(stale_reasons),
    }


def combo_means(stat_means):
    """Combo expectations as sums of component means.

    Summing *means* is exact. It says nothing about the spread of a combo, which
    would need the joint distribution; nothing here assumes the components are
    independent and no combo uncertainty is reported.
    """
    return {name: (sum(stat_means[s] for s in parts)
                   if all(stat_means.get(s) is not None for s in parts) else None)
            for name, parts in COMBOS.items()}
