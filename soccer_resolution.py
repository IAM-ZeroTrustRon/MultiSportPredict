"""Three-tier soccer resolution, ported from the basketball engine.

Tier 1 - local:  both teams resolve from the competition-scoped stats store.
Tier 2 - refresh: one supported public refresh is attempted, then the store is
                 re-read. Never a guessed provider, never a paid odds call.
Tier 3 - exploratory: still missing, and the caller passed ``--exploratory``.
                 A disclosed league-baseline observation is produced. It is NOT a
                 model forecast, it is never written to the value ledger, and every
                 substituted input is listed. A side that *did* resolve keeps its
                 measured rate; only the missing side is substituted.

The tiers exist so a missing team never decays into a silent league-average
prediction. Tier 3 is permission for a labelled observation, not a substitute for
data, and no tier weakens fixture identity, price pairing or settlement rules.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys

from sports_feed import ROOT, atomic_json, today

TIER_LOCAL = 1
TIER_REFRESHED = 2
TIER_EXPLORATORY = 3
TIER_LABELS = {TIER_LOCAL: "LOCAL", TIER_REFRESHED: "REFRESHED", TIER_EXPLORATORY: "EXPLORATORY"}
REFRESH_TIMEOUT_SECONDS = 240


def _lookup(home, away, league):
    from team_stats_provider import get_soccer_team_stats
    return get_soccer_team_stats(home, league), get_soccer_team_stats(away, league)


def refresh_once():
    """One bounded supported refresh. Returns ``(ok, note)``.

    The command mirrors ``msp_workflow.refresh_plan`` for soccer: the same two
    publicly permitted ingesters, run once, with a timeout. Failure is reported,
    never retried in a loop and never replaced with invented numbers.
    """
    commands = [
        ["ingest_soccer_espn.py", "--all", "--fixtures"],
        ["ingest_soccer_fd.py", "--countries", "england", "germany", "spain", "france", "italy"],
    ]
    notes = []
    ok = False
    for command in commands:
        try:
            completed = subprocess.run([sys.executable, "-u", *command], cwd=str(ROOT),
                                       capture_output=True, text=True,
                                       timeout=REFRESH_TIMEOUT_SECONDS)
        except (OSError, subprocess.SubprocessError) as exc:
            notes.append(f"{command[0]}: refresh failed ({type(exc).__name__})")
            continue
        tail = (completed.stdout or completed.stderr or "").strip().splitlines()
        notes.append(f"{command[0]}: {'ok' if completed.returncode == 0 else 'failed'}"
                     + (f" ({tail[-1][:120]})" if tail else ""))
        ok = ok or completed.returncode == 0
    return ok, notes


def resolve_team_stats(home, away, league, refresh=True):
    """Return ``(home_stats, away_stats, tier, notes)``.

    ``tier == 3`` means at least one side is still missing and the caller must decide
    whether exploratory output is permitted. Any side that *did* resolve is returned
    as-is: discarding verified team data because its opponent is missing is a silent
    downgrade. Missing data is never replaced here.
    """
    home_stats, away_stats = _lookup(home, away, league)
    if home_stats is not None and away_stats is not None:
        return home_stats, away_stats, TIER_LOCAL, ["Competition-scoped local history in use"]

    notes = ["local miss: "
             + ", ".join(name for name, stats in ((home, home_stats), (away, away_stats))
                         if stats is None)]
    if not refresh:
        return home_stats, away_stats, TIER_EXPLORATORY, notes + [
            "public refresh disabled by caller"]

    ok, refresh_notes = refresh_once()
    notes += refresh_notes
    home_stats, away_stats = _lookup(home, away, league)
    if home_stats is not None and away_stats is not None:
        return home_stats, away_stats, TIER_REFRESHED, notes + [
            "one supported public refresh applied"]
    notes.append("still missing after the single supported refresh")
    return home_stats, away_stats, TIER_EXPLORATORY, notes


def _measured_scoring(stats):
    """Verified goals-per-game for one side, or ``None`` when it cannot be trusted."""
    if not isinstance(stats, dict):
        return None
    for key in ("goals_for", "xg_for"):
        value = stats.get(key)
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            return number
    return None


def _provenance(team, stats):
    """One line describing a side as measured or substituted."""
    scoring = _measured_scoring(stats)
    if scoring is None:
        return {"team": team, "status": "SUBSTITUTED", "scoring": None,
                "line": f"{team}: SUBSTITUTED - league baseline (no verified team metrics)"}
    games = stats.get("games")
    season = stats.get("season")
    source = stats.get("source") or "competition-scoped store"
    detail = f"{scoring:.2f} goals/match"
    if games:
        detail += f" over {games} games"
    if season:
        detail += f", {season}"
    return {"team": team, "status": "MEASURED", "scoring": scoring,
            "games": games, "season": season, "source": source,
            "line": f"{team}: MEASURED {detail} [{source}]"}


def exploratory_observation(home, away, league, game_date=None, home_stats=None,
                            away_stats=None):
    """Disclosed scenario for a fixture with missing data, keeping any verified side.

    ``exploratory.soccer_forecast`` supplies the league baseline; a side with real
    stats contributes its own measured scoring rate instead of the placeholder. Every
    remaining assumption is listed, and the artifact is written outside the value
    ledger. No price, EV or stake is attached.
    """
    from exploratory import soccer_forecast

    home_rate = _measured_scoring(home_stats)
    away_rate = _measured_scoring(away_stats)
    forecast = soccer_forecast(league, home, away, home_scoring=home_rate,
                              away_scoring=away_rate)
    date = game_date or today()
    home_info = _provenance(home, home_stats)
    away_info = _provenance(away, away_stats)
    substituted = [info["team"] for info in (home_info, away_info)
                   if info["status"] == "SUBSTITUTED"]

    lines = [
        "=" * 84,
        "EXPLORATORY SOCCER OBSERVATION — not a model forecast, excluded from the value record",
        "=" * 84,
        f"{date} | {home} (home) vs {away} (away) | competition: {league}",
        "",
        f"Scenario goals: {home} {forecast['projection']['home_goals']:.2f} | "
        f"{away} {forecast['projection']['away_goals']:.2f}",
        f"Scenario probabilities: home {forecast['probabilities']['home_win']:.1%} | "
        f"draw {forecast['probabilities']['draw']:.1%} | "
        f"away {forecast['probabilities']['away_win']:.1%}",
        "",
        "INPUTS — MEASURED DATA IS RETAINED, ONLY MISSING SIDES ARE SUBSTITUTED",
    ]
    lines += [f"  {info['line']}" for info in (home_info, away_info)]
    lines += ["", "SUBSTITUTIONS AND RETAINED MEASUREMENTS"]
    for item in forecast["substitutions"]:
        lines.append(f"  - {item['input']}: {item['value']} "
                     f"[source: {item['source']}] ({item['why']})")
    lines += [""]
    if substituted:
        lines.append(f"{', '.join(substituted)} had no verified team data, so this forecast "
                     "rests partly on league placeholders.")
    lines += [
        "Placeholder inputs cannot make an unsupported fixture reliably predictable, so this",
        "cannot support an actionable price. It is a scenario only.",
        "Grading: exploratory observations are graded separately (cohort EXPLORATORY).",
    ]
    card = "\n".join(lines)

    slug = "".join(ch if ch.isalnum() else "_" for ch in f"{home}_{away}")[:60]
    path = ROOT / "output/soccer" / f"exploratory_{date}_{slug}.json"
    document = {"date": date, "home": home, "away": away, "league": league,
                "tier": TIER_LABELS[TIER_EXPLORATORY], "cohort": "EXPLORATORY",
                "exploratory": True, "value_ledger": False,
                "partial": bool(substituted) and len(substituted) < 2,
                "verified_sides": [info["team"] for info in (home_info, away_info)
                                   if info["status"] == "MEASURED"],
                "substituted_sides": substituted,
                "inputs": {"home": home_info, "away": away_info},
                "projection": forecast["projection"],
                "probabilities": forecast["probabilities"],
                "substitutions": forecast["substitutions"], "card": card,
                "created_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    atomic_json(path, document)
    document["path"] = str(path.relative_to(ROOT))
    return document
