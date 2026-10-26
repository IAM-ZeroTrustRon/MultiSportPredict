"""NBA player-prop research: projected minutes and stat expectations.

This produces research projections only. It never writes a team-pick prediction,
never joins the value ledger, and never emits a cover probability, an expected
value, a stake or a recommendation. Those need real bookmaker prop prices and a
distribution assumption, neither of which this phase has.

Usage (Git Bash, from C:/MultiSportPredict):

    venv/Scripts/python.exe -u run_basketball_props.py --date 2026-10-28 \\
        --match "Miami Heat vs Atlanta Hawks"

    venv/Scripts/python.exe -u run_basketball_props.py --validate
"""

from __future__ import annotations

import argparse
import datetime as dt
import json

import basketball_availability as availability
from features.basketball_props import appearance_windows, dedupe, has_minutes, to_float
from models.basketball_props import (
    candidate_vector,
    fit_minutes_model,
    project_player,
    validate,
)
from sports_feed import EASTERN, ROOT, atomic_json, fetch_json, today

STORE = ROOT / "data/basketball_props/player_games.json"
LATEST = ROOT / "output/basketball_props/latest.json"
ROSTER = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team}/roster"
SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date}"
# Only a scheduled game can be projected. Anything in progress or finished is refused.
PROJECTABLE_STATUS = {"STATUS_SCHEDULED", "STATUS_PRE"}


def load_rows():
    if not STORE.exists():
        raise ValueError(f"No stored player games at {STORE.relative_to(ROOT)}; run ingest_basketball_props.py first")
    payload = json.loads(STORE.read_text(encoding="utf-8-sig"))
    rows = dedupe(payload.get("games") or [])
    if not rows:
        raise ValueError("Stored player games are empty")
    return payload, rows


def event_status(event):
    competition = (event.get("competitions") or [{}])[0]
    return (((competition.get("status") or {}).get("type") or {}).get("name") or "")


def event_kickoff(event):
    competition = (event.get("competitions") or [{}])[0]
    stamp = event.get("date") or competition.get("date")
    if not stamp:
        return None
    parsed = dt.datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def assert_projectable(event, date, now=None):
    """Enforce fixture date, kickoff and game status before anything is projected."""
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    status = event_status(event)
    if status not in PROJECTABLE_STATUS:
        raise ValueError(f"Fixture {event.get('id')} status is {status or 'unknown'}; "
                         "only a scheduled game can be projected")
    kickoff = event_kickoff(event)
    if kickoff is None:
        raise ValueError(f"Fixture {event.get('id')} has no kickoff timestamp")
    eastern = kickoff.astimezone(EASTERN).date().isoformat()
    if eastern != str(date)[:10]:
        raise ValueError(f"Fixture kickoff date {eastern} does not match requested date {date}")
    if kickoff <= now:
        raise ValueError(f"Fixture kicked off at {kickoff.isoformat()}Z; refusing a post-start projection")
    return kickoff


def resolve_fixture(date, match, now=None):
    """Find the scheduled game so teams, rosters and availability are the real ones."""
    events = fetch_json(SCOREBOARD.format(date=str(date).replace("-", "")), cache_hours=3).get("events") or []
    if not match:
        projectable = []
        for event in events:
            try:
                assert_projectable(event, date, now)
            except ValueError:
                continue
            projectable.append(event)
        if not projectable:
            raise ValueError(f"No scheduled NBA fixture on {date} is still open for projection")
        return projectable
    text = match.replace(" at ", " vs ").replace(" @ ", " vs ")
    if " vs " not in text:
        raise ValueError('Use "Away vs Home" (for example "Miami Heat vs Atlanta Hawks")')
    away, home = [part.strip() for part in text.split(" vs ", 1)]
    for event in events:
        competition = (event.get("competitions") or [{}])[0]
        sides = {s.get("homeAway"): s.get("team", {}).get("displayName")
                 for s in competition.get("competitors") or []}
        if sides.get("away") == away and sides.get("home") == home:
            assert_projectable(event, date, now)
            return [event]
    available = [e.get("name") for e in events]
    raise ValueError(f"No fixture {away!r} vs {home!r} on {date}. Scheduled: {available}")


def team_ids(event):
    competition = (event.get("competitions") or [{}])[0]
    ids = {}
    for side in competition.get("competitors") or []:
        ids[side.get("homeAway")] = str(side.get("team", {}).get("id"))
    return ids.get("home"), ids.get("away")


def roster(team_id):
    payload = fetch_json(ROSTER.format(team=team_id), cache_hours=12)
    return payload.get("athletes") or []


def build_feature_rows(rows):
    by_player, by_team = {}, {}
    for row in rows:
        by_player.setdefault(str(row.get("player_id")), []).append(row)
        by_team.setdefault(str(row.get("team_id")), []).append(row)
    return by_player, by_team


def fit_from_store(rows, date, by_player, by_team):
    """Fit the candidate minutes model on stored history strictly before the date."""
    samples = []
    for row in rows:
        if str(row.get("game_date"))[:10] >= str(date)[:10] or not has_minutes(row):
            continue
        features = appearance_windows(by_player.get(str(row.get("player_id")), []),
                                      row.get("game_date"), by_team.get(str(row.get("team_id")), []))
        samples.append((candidate_vector(features), to_float(row.get("minutes"))))
    return fit_minutes_model(samples)


def research(date, match, player_filter, limit, json_only=False, minutes_model="baseline",
             dry_run=False, now=None):
    payload, rows = load_rows()
    events = resolve_fixture(date, match, now)
    if not events:
        raise ValueError(f"No NBA fixtures on {date}")
    by_player, by_team = build_feature_rows(rows)
    coefficients = None
    if minutes_model == "candidate":
        coefficients = fit_from_store(rows, date, by_player, by_team)
        if coefficients is None:
            raise ValueError("Not enough stored history to fit the candidate minutes model")

    results = []
    availability_reports = []
    for event in events[:1] if match else events:
        assert_projectable(event, date, now)
        home_id, away_id = team_ids(event)
        snapshot = availability.snapshot(event.get("id"), now=now)
        availability_reports.append(snapshot)
        target = snapshot.get("season") or {}
        target_label = target.get("label")
        for side, team_id in (("away", away_id), ("home", home_id)):
            for athlete in roster(team_id):
                player_id = str(athlete.get("id"))
                name = athlete.get("displayName") or athlete.get("fullName")
                if player_filter and not any(f.lower() in (name or "").lower() for f in player_filter):
                    continue
                features = appearance_windows(by_player.get(player_id, []), date,
                                              by_team.get(team_id, []), target_season=target_label)
                projection = project_player(features, coefficients,
                                            availability.designation_for(snapshot, player_id, now))
                results.append({
                    "date": date, "event_id": str(event.get("id")), "matchup": event.get("name"),
                    "kickoff": (event_kickoff(event) or "").isoformat() if event_kickoff(event) else None,
                    "status": event_status(event),
                    "side": side, "team": athlete.get("team", {}).get("displayName") or None,
                    "player_id": player_id, "player": name,
                    "position": (athlete.get("position") or {}).get("abbreviation"),
                    "season_label": target_label,
                    **projection,
                })
    results.sort(key=lambda r: (r.get("projected_minutes") is None, -(r.get("projected_minutes") or 0)))
    shown = results[:limit] if limit else results
    document = {
        "generated_at": today(),
        "mode": "research",
        "date": date,
        "minutes_model": minutes_model,
        "minutes_model_coefficients": coefficients,
        "store": str(STORE.relative_to(ROOT)),
        "store_updated": payload.get("updated"),
        "store_source": payload.get("source"),
        "store_rows": len(rows),
        "store_games": len({r.get("event_id") for r in rows}),
        "store_seasons": sorted({r.get("season_label") for r in rows if r.get("season_label")}),
        "cutoff_rule": "only games dated strictly before the forecast date are used",
        "availability": [{k: v for k, v in report.items() if k != "players"}
                         for report in availability_reports],
        "players_evaluated": len(results),
        "rows": shown,
        "research_only": True,
        "no_betting_output": ("No cover probability, expected value, stake, probability flag "
                             "or recommendation is produced in this phase."),
    }
    if not dry_run:
        atomic_json(LATEST, document)
    if json_only:
        print(json.dumps(document, indent=2, ensure_ascii=False))
    else:
        print(format_research(document))
    return document


def _num(value, width, decimals=1):
    """Render a missing projection as -- rather than a misleading 0.0."""
    if value is None:
        return f"{'--':>{width}}"
    return f"{value:>{width}.{decimals}f}"


def _minutes_triplet(row):
    windows = row.get("windows") or {}
    parts = []
    for size in (5, 10, 20):
        value = (windows.get(size) or {}).get("minutes_mean")
        parts.append("--" if value is None else f"{value:.1f}")
    return "/".join(parts)


def format_research(document):
    provenance = document.get("availability") or []
    lines = [
        "=" * 132,
        f"NBA PLAYER PROP RESEARCH - {document['date']}   (research only, not a betting recommendation)",
        "=" * 132,
        f"Stored games: {document['store_games']} | player rows: {document['store_rows']} | "
        f"seasons: {', '.join(document.get('store_seasons') or ['unknown'])} | "
        f"source: {document['store_source']} | updated {document['store_updated']}",
        f"Cutoff rule: {document['cutoff_rule']}",
        f"{availability.summary_line(provenance[0]) if provenance else 'availability: no report'}",
        "",
        f"{'PLAYER':<26}{'SIDE':<7}{'ROLE':<7}{'MIN':>6}{'RECENT MIN 5/10/20':>20}"
        f"{'PTS':>8}{'REB':>8}{'AST':>8}{'PRA':>8}{'APPS':>6}{'SEASON':>10}  FLAGS",
        "-" * 132,
    ]
    for row in document["rows"]:
        availability_block = row.get("availability") or {}
        flags = []
        if row.get("refused"):
            flags.append(row.get("status") or "REFUSED")
        if row.get("stale_rotation"):
            flags.append("STALE")
        if row.get("crosses_season"):
            flags.append("CROSS-SEASON")
        if availability_block.get("refuse"):
            flags.append("UNAVAILABLE")
        flag_text = ", ".join(flags) or "-"
        season = row.get("last_appearance_season") or "--"
        if row.get("refused"):
            lines.append(f"{(row['player'] or '?')[:25]:<26}{row['side']:<7}{'--':<7}"
                         f"{'--':>6}{'--':>20}{'--':>8}{'--':>8}{'--':>8}{'--':>8}"
                         f"{row.get('n_appearances', 0):>6}{season:>10}  {flag_text}")
            continue
        stats = row.get("projected_stats") or {}
        combos = row.get("projected_combos") or {}
        starter_freq = (row.get("windows", {}).get(10, {}) or {}).get("starter_freq") or 0
        role = "starter" if starter_freq >= 0.5 else "bench"
        lines.append(
            f"{(row['player'] or '?')[:25]:<26}{row['side']:<7}{role:<7}"
            f"{_num(row.get('projected_minutes'), 6)}{_minutes_triplet(row):>20}"
            f"{_num(stats.get('points'), 8)}{_num(stats.get('rebounds'), 8)}"
            f"{_num(stats.get('assists'), 8)}{_num(combos.get('pra'), 8)}"
            f"{row.get('n_appearances', 0):>6}{season:>10}  {flag_text}"
        )
    lines += [
        "-" * 132,
        "MIN = projected minutes. RECENT MIN = mean minutes over the last 5/10/20 appearances,",
        "strictly before the forecast date. APPS = usable appearances. '--' means the value is",
        "missing or refused; it is never rendered as 0.0.",
        "",
        "STALE = rotation history is older than the declared limit or from a previous season.",
        "CROSS-SEASON = the last appearance came from a different NBA season than this fixture.",
        "Availability is UNKNOWN unless the feed published a designation for that player.",
        "",
        f"NOTE: {document['no_betting_output']}",
        "Minutes include overtime and are not adjusted for it. Combo PRA is the sum of component",
        "means; no independence between components is assumed and no combo spread is reported.",
        "This record is kept outside the team-pick value ledger.",
    ]
    return "\n".join(lines)


def format_validation(report):
    lines = ["=" * 104,
             "NBA PLAYER PROP VALIDATION - chronological, whole-game holdout",
             "=" * 104]
    if report.get("status") != "ok":
        lines.append(f"Not enough dated history to validate: {report}")
        return "\n".join(lines)
    lines += [
        f"Cutoff date: {report['cutoff_date']}  (train {report['train_fraction']:.0%} / test remainder)",
        f"Train: {report['n_train_dates']} dates, {report['n_train_rows']} player-games | "
        f"Test: {report['n_test_dates']} dates, {report['n_test_rows']} player-games",
        "",
        "PLAYED-GAME ACCURACY (conditional on the player appearing)",
        f"{'MINUTES':<26}{'n':>6}{'MAE':>9}{'BIAS':>9}{'RMSE':>9}",
        "-" * 104,
    ]
    for label, key in (("recent-rotation baseline", "baseline"), ("fitted candidate", "candidate")):
        block = report["played_game_accuracy"][key]
        lines.append(f"{label:<26}{block['n']:>6}{_num(block['mae'], 9, 2)}{_num(block['bias'], 9, 2)}{_num(block['rmse'], 9, 2)}")

    participation = report["participation"]
    lines += [
        "",
        "PARTICIPATION (did a projectable player actually appear?)",
        "-" * 104,
        f"  projectable player-games     {participation['projectable_rows']}",
        f"  appeared                     {participation['appeared']}"
        f"   (incl. {participation.get('listed_zero_minutes', 0)} listed with zero minutes)",
        f"  did not play                 {participation['did_not_play']}",
        f"  unverified (excluded)        {participation.get('unverified', 0)}",
        f"  confirmed for scoring        {participation.get('confirmed_rows', 0)}",
        f"  appearance rate              "
        f"{_num((participation['appearance_rate'] or 0) * 100, 6, 1) if participation['appearance_rate'] is not None else '    --'}%",
        "",
        "PARTICIPATION-INCLUSIVE (confirmed did-not-play counted as zero minutes)",
        f"{'MINUTES':<26}{'n':>6}{'MAE':>9}{'BIAS':>9}{'RMSE':>9}",
        "-" * 104,
    ]
    for label, key in (("recent-rotation baseline", "baseline"), ("fitted candidate", "candidate")):
        block = report["participation_inclusive"][key]
        lines.append(f"{label:<26}{block['n']:>6}{_num(block['mae'], 9, 2)}{_num(block['bias'], 9, 2)}{_num(block['rmse'], 9, 2)}")

    model = report.get("minutes_model")
    lines += [""]
    if model:
        lines += [
            f"Fitted on {model['n_train']} training player-games; coefficients disclosed:",
            f"  intercept {model['intercept']:+.4f}",
        ]
        for name, weight in zip(model["features"], model["weights"]):
            lines.append(f"  {name:<24}{weight:+.4f}")
        lines.append("  Nested 5/10/20 window means are collinear; individual weights are not")
        lines.append("  interpretable alone.")
    else:
        lines.append("No fitted candidate: insufficient training sample.")

    lines += ["", "BY ROLE (played games only, reporting only)",
              f"{'ROLE':<26}{'n':>6}{'MAE':>9}{'BIAS':>9}"]
    lines.append("-" * 104)
    for role, blocks in (report.get("by_role_played_games") or {}).items():
        for label, key in (("baseline", "baseline"), ("candidate", "candidate")):
            block = blocks[key]
            lines.append(f"{role + ' ' + label:<26}{block['n']:>6}"
                         f"{_num(block['mae'], 9, 2)}{_num(block['bias'], 9, 2)}")

    for variant in ("baseline", "candidate"):
        lines += ["", f"STAT PROJECTION MISS - {variant.upper()} minutes",
                  f"{'STAT':<26}{'n':>6}{'MAE':>9}{'BIAS':>9}"]
        lines.append("-" * 104)
        for name, block in (report["stat_projection_error"][variant] or {}).items():
            if not block["n"]:
                continue
            lines.append(f"{name:<26}{block['n']:>6}{_num(block['mae'], 9, 2)}{_num(block['bias'], 9, 2)}")

    lines += ["", "NOTES"]
    lines += [f"  - {note}" for note in report.get("notes") or []]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=today())
    parser.add_argument("--match")
    parser.add_argument("--league", default="NBA")
    parser.add_argument("--player", action="append", default=[])
    parser.add_argument("--limit", type=int, default=18)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--minutes-model", choices=["baseline", "candidate"], default="baseline",
                        help="baseline is the transparent recent-rotation mean; candidate is the fitted model")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the projection and write nothing")
    args = parser.parse_args(argv)
    if (args.league or "").upper() != "NBA":
        raise ValueError("Player props are NBA-only in this phase; reusable interfaces exist but no other league is verified")
    if args.validate:
        _, rows = load_rows()
        # Every row is passed in, including DNPs, so participation can be measured.
        report = validate(rows)
        print(json.dumps(report, indent=2) if args.json else format_validation(report))
        return 0
    research(args.date, args.match, args.player, args.limit, args.json, args.minutes_model,
             args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
