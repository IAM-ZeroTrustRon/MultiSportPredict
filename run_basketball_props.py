"""NBA player-prop research: projected minutes, projected stats and offered prices.

This produces research projections and, when a real bookmaker price is available,
a MODEL ESTIMATE of the probability and expected value at that exact line. It never
writes a team-pick prediction, never enters the value ledger, and never stakes: prop
staking is not enabled, so ``stake_size`` is always null with the reason stated.

Two signals are kept apart on purpose:

* probability - the model's own chance the selection wins, from measured residuals
* value       - that probability priced against the offered odds

A selection can be likely to win and still be a losing bet. Neither signal is
blended with the market, and no threshold is tuned here: the EV pick uses the same
LEAN gate as the rest of the project (``models.score_ratings.price_market``).

Usage (Git Bash, from C:/MultiSportPredict):

    venv/Scripts/python.exe -u run_basketball_props.py --date 2026-10-26 \\
        --match "Phoenix Suns vs Oklahoma City Thunder"

    venv/Scripts/python.exe -u run_basketball_props.py --validate
"""

from __future__ import annotations

import argparse
import datetime as dt
import json

import basketball_availability as availability
import prop_odds
from features.basketball_props import appearance_windows, dedupe, has_minutes, to_float
from models.basketball_props import (
    candidate_vector,
    fit_minutes_model,
    project_player,
    validate,
)
from models.prop_probability import (
    MARKETS,
    build_residual_pool,
    pool_size,
    priceability,
    probability_for,
    residual_scale,
)
from models.score_ratings import price_market
from probability_signal import (
    format_price,
    format_probability,
    high_probability_lines,
    probability_flag,
    value_verdict,
)
from sports_feed import EASTERN, ROOT, atomic_json, fetch_json, today

STORE = ROOT / "data/basketball_props/player_games.json"
LATEST = ROOT / "output/basketball_props/latest.json"
ROSTER = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team}/roster"
SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date}"
# Only a scheduled game can be projected. Anything in progress or finished is refused.
PROJECTABLE_STATUS = {"STATUS_SCHEDULED", "STATUS_PRE"}
DEFAULT_MARKETS = ("points", "rebounds", "assists", "pra", "pa", "ra")
MARKET_LABEL = {"points": "PTS", "rebounds": "REB", "assists": "AST",
                "pra": "PRA", "pa": "PA", "ra": "RA"}

# A gap this large between the model's probability and the de-vigged market
# probability means the two disagree about the player's level, not about luck.
# With a short or cross-season history that is almost always the model's input
# being wrong, so the row is labelled neutrally and EV is withheld. This is a
# disclosure rule, not a tuned edge threshold: it can only remove edges.
DISCREPANCY_LIMIT = 0.25


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


def team_names(event):
    competition = (event.get("competitions") or [{}])[0]
    sides = {s.get("homeAway"): (s.get("team") or {}).get("displayName")
             for s in competition.get("competitors") or []}
    return sides.get("home"), sides.get("away")


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


def _prop_markets(projection, payload, pool, player_name, markets):
    """Price every requested market that has a real offered line for this player.

    Three outcomes are kept distinct: priced (``ok``), line known but withheld
    because the projection cannot resolve it (``withheld``), and no usable market
    (``unavailable`` with a reason). A missing price is never a zero.
    """
    stats_means = projection.get("projected_stats") or {}
    combo_means = projection.get("projected_combos") or {}
    minutes = projection.get("projected_minutes")
    entries = []
    for market in markets:
        label = MARKET_LABEL[market]
        mean = stats_means.get(market) if market in stats_means else combo_means.get(market)
        entry = {"market": market, "label": label, "status": "unavailable",
                 "reason": None, "line": None, "selection": None, "price": None,
                 "probability": None, "ev": None, "push": None, "recommendation": None,
                 "model_probability_over": None, "model_probability_under": None,
                 "de_vig_over": None, "bookmaker": None, "updated_at": None,
                 "projected": mean, "projection_gap": None, "error_scale": None}
        if payload is None:
            entry["reason"] = "no offered prices retrieved for this fixture"
            entries.append(entry)
            continue
        if mean is None:
            entry["reason"] = "projection unavailable"
            entries.append(entry)
            continue
        rows = prop_odds.player_lines(payload, player_name, prop_odds.PROP_MARKETS[market])
        if not rows:
            entry["reason"] = "bookmakers published no line for this player/market"
            entries.append(entry)
            continue
        line = prop_odds.consensus_line(rows)
        best = prop_odds.best_prices(rows, line)
        entry["line"] = line

        # Refuse to price a line the projection cannot resolve. Without this the
        # model happily reports a huge edge whenever its own projection is the
        # thing that is wrong.
        scale = residual_scale(pool, market, minutes)
        gate = priceability(mean, line, scale)
        entry["error_scale"] = gate.get("error_scale")
        entry["projection_gap"] = gate.get("gap")
        if not gate.get("priceable"):
            entry["status"] = "withheld"
            entry["reason"] = gate.get("reason")
            entries.append(entry)
            continue

        probabilities = probability_for(pool, market, mean, minutes, line)
        if probabilities.get("status") != "ok":
            entry["reason"] = probabilities.get("reason")
            entries.append(entry)
            continue
        over_price = (best.get("over") or {}).get("price")
        under_price = (best.get("under") or {}).get("price")
        if over_price is None and under_price is None:
            entry["reason"] = "line published without a usable price"
            entries.append(entry)
            continue
        entry.update({
            "model_probability_over": probabilities["over"],
            "model_probability_under": probabilities["under"],
            "push": probabilities["push"],
            "probability_samples": probabilities["samples"],
            "probability_scope": probabilities["scope"],
        })

        priced = price_market("total", line, (probabilities["over"], probabilities["under"],
                                              probabilities["push"]),
                              over_price, under_price)
        pick = priced.get("pick")
        if pick not in ("OVER", "UNDER"):
            # No side clears the LEAN gate; show the likelier priced side as a pass.
            options = [("OVER", probabilities["over"], over_price, priced["ev_a"], best.get("over")),
                       ("UNDER", probabilities["under"], under_price, priced["ev_b"], best.get("under"))]
            options = [o for o in options if o[2] is not None]
            pick, probability, price, ev, book = max(options, key=lambda o: o[1])
        else:
            if pick == "OVER":
                probability, price, ev = probabilities["over"], over_price, priced["ev_a"]
                book = best.get("over") or {}
            else:
                probability, price, ev = probabilities["under"], under_price, priced["ev_b"]
                book = best.get("under") or {}
            if price is None:
                # The recommended side has no price; report the other side instead of
                # an EV computed against nothing.
                pick = "UNDER" if pick == "OVER" else "OVER"
                probability = probabilities[pick.lower()]
                price = under_price if pick == "UNDER" else over_price
                ev = priced["ev_b"] if pick == "UNDER" else priced["ev_a"]
                book = best.get(pick.lower()) or {}

        fair_market = prop_odds.de_vig(over_price, under_price) if (
            over_price is not None and under_price is not None) else None
        market_probability = None
        if fair_market:
            market_probability = fair_market[0] if pick == "OVER" else fair_market[1]
        if (market_probability is not None and probability is not None
                and abs(float(probability) - float(market_probability)) > DISCREPANCY_LIMIT):
            entry.update({
                "status": "discrepancy",
                "selection": pick,
                "price": price,
                "probability": probability,
                "ev": None,
                "de_vig_over": fair_market[0],
                "bookmaker": book.get("bookmaker"),
                "updated_at": book.get("updated_at"),
                "model_estimate": True,
                "probability_flag": probability_flag(probability),
                "value_verdict": "MODEL/MARKET DISCREPANCY",
                "recommendation": "MODEL/MARKET DISCREPANCY - EV withheld",
                "reason": (f"model {float(probability):.1%} vs de-vigged market "
                           f"{float(market_probability):.1%} on {pick}; the disagreement is "
                           "about the player's level, so no EV is published"),
            })
            entries.append(entry)
            continue

        entry.update({
            "status": "ok",
            "selection": pick,
            "price": price,
            "probability": probability,
            "ev": ev,
            "bookmaker": book.get("bookmaker"),
            "updated_at": book.get("updated_at"),
            "recommendation": priced.get("recommendation"),
            "stake_size": None,
            "stake_basis": "unavailable: prop staking is not enabled",
            "model_estimate": True,
            "probability_flag": probability_flag(probability),
            "value_verdict": value_verdict(ev),
        })
        if over_price is not None and under_price is not None:
            fair = prop_odds.de_vig(over_price, under_price)
            if fair:
                entry["de_vig_over"] = fair[0]
        entries.append(entry)
    return entries


def research(date, match, player_filter, limit, json_only=False, minutes_model="baseline",
             dry_run=False, now=None, use_odds=True, markets=DEFAULT_MARKETS, regions="us"):
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

    pool = build_residual_pool(rows, date)
    sizes = pool_size(pool)

    odds_events, odds_meta = [], None
    odds_notes = []
    if use_odds:
        try:
            odds_events, odds_meta = prop_odds.list_events("basketball_nba")
        except (RuntimeError, ValueError) as exc:
            odds_notes.append(f"prices unavailable: {exc}")
            odds_events = []

    quota_metas = [odds_meta] if odds_meta else []
    results = []
    availability_reports = []
    price_reports = []
    for event in events[:1] if match else events:
        assert_projectable(event, date, now)
        home_id, away_id = team_ids(event)
        home_name, away_name = team_names(event)
        snapshot = availability.snapshot(event.get("id"), now=now)
        availability_reports.append(snapshot)
        target = snapshot.get("season") or {}
        target_label = target.get("label")

        odds_payload = None
        if use_odds and odds_events:
            try:
                priced_event = prop_odds.match_event(odds_events, away_name, home_name)
            except ValueError as exc:
                odds_notes.append(str(exc))
                priced_event = None
            if priced_event is None:
                odds_notes.append(f"{away_name} @ {home_name}: no priced event for this fixture")
            else:
                market_keys = ",".join(prop_odds.PROP_MARKETS[m] for m in markets)
                odds_payload, meta = prop_odds.event_odds(
                    "basketball_nba", priced_event["id"], market_keys, regions=regions)
                if meta:
                    quota_metas.append(meta)
                    price_reports.append({"event_id": priced_event["id"],
                                          "commence_time": priced_event.get("commence_time"),
                                          **{k: meta.get(k) for k in
                                             ("cached", "credit_cost", "remaining", "markets_unavailable")}})
                    for key in meta.get("markets_unavailable") or []:
                        odds_notes.append(f"{key}: not published by any bookmaker")
                if odds_payload is None:
                    odds_notes.append(f"{away_name} @ {home_name}: {meta.get('reason')}")

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
                entry = {
                    "date": date, "event_id": str(event.get("id")), "matchup": event.get("name"),
                    "kickoff": (event_kickoff(event) or "").isoformat() if event_kickoff(event) else None,
                    "status": event_status(event),
                    "side": side, "team": athlete.get("team", {}).get("displayName") or None,
                    "player_id": player_id, "player": name,
                    "position": (athlete.get("position") or {}).get("abbreviation"),
                    "season_label": target_label,
                    **projection,
                }
                if projection.get("refused"):
                    entry["prop_markets"] = []
                else:
                    entry["prop_markets"] = _prop_markets(projection, odds_payload, pool,
                                                          name, markets)
                entry["recommendation"] = _player_recommendation(entry)
                results.append(entry)

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
        "residual_pool": {**sizes, "games_used": pool["games_used"],
                          "assumptions": pool["assumptions"]},
        "odds": {
            "enabled": bool(use_odds),
            "markets_requested": list(markets),
            "regions": regions,
            "fixtures": price_reports,
            "quota": prop_odds.quota_note(quota_metas),
            "notes": odds_notes,
        },
        "players_evaluated": len(results),
        "rows": shown,
        "research_only": True,
        "model_estimates": ("Probabilities are empirical residual frequencies and EV is the model "
                            "probability priced at the offered line; both are MODEL ESTIMATES, "
                            "unvalidated against market prices."),
        "no_betting_output": ("No stake is produced. Prop staking is not enabled; recommendations "
                             "use the project's existing LEAN threshold unchanged."),
    }
    if not dry_run:
        atomic_json(LATEST, document)
    if json_only:
        print(json.dumps(document, indent=2, ensure_ascii=False))
    else:
        print(format_research(document))
    return document


def _player_recommendation(entry):
    """One verdict per player, never a value claim the data cannot support."""
    availability_block = entry.get("availability") or {}
    if entry.get("refused"):
        return "REFUSED - " + str(entry.get("status") or "unavailable")
    if not availability_block.get("actionable"):
        return "RESEARCH ONLY - availability unverified"
    priced = [m for m in entry.get("prop_markets") or [] if m.get("status") == "ok"]
    leans = [m for m in priced if m.get("value_verdict") == "VALUE"]
    if leans:
        best = max(leans, key=lambda m: m.get("ev") or 0)
        return f"LEAN {best['selection']} {best['label']} {best['line']} (MODEL ESTIMATE)"
    return "PASS - no priced model edge"


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


def _odds_price(value):
    if value is None:
        return "--"
    return format_price(value)


def _probability(value):
    if value is None:
        return "--"
    return format_probability(value)


def _ev(value):
    if value is None:
        return "--"
    return f"{value:+.2%}"


def format_research(document):
    provenance = document.get("availability") or []
    lines = [
        "=" * 138,
        f"NBA PLAYER PROP RESEARCH - {document['date']}   (research only, not a betting recommendation)",
        "=" * 138,
        f"Stored games: {document['store_games']} | player rows: {document['store_rows']} | "
        f"seasons: {', '.join(document.get('store_seasons') or ['unknown'])} | "
        f"source: {document['store_source']} | updated {document['store_updated']}",
        f"Cutoff rule: {document['cutoff_rule']}",
        f"{availability.summary_line(provenance[0]) if provenance else 'availability: no report'}",
        "",
        f"{'PLAYER':<26}{'SIDE':<7}{'ROLE':<7}{'MIN':>6}{'RECENT MIN 5/10/20':>20}"
        f"{'PTS':>8}{'REB':>8}{'AST':>8}{'PRA':>8}{'APPS':>6}{'SEASON':>10}  FLAGS",
        "-" * 138,
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
        if row.get("window_scope") == "prior_season_carryover":
            flags.append("PRIOR-SEASON ROTATION")
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
            f"{row.get('n_window_appearances', row.get('n_appearances', 0)):>6}{season:>10}  {flag_text}"
        )
    lines += [
        "-" * 138,
        "MIN = projected minutes. RECENT MIN = mean minutes over the last 5/10/20 appearances,",
        "strictly before the forecast date, using only this season once 3+ games exist.",
        "APPS = appearances in the window that produced the projection. '--' means the value is",
        "missing or refused; it is never rendered as 0.0.",
        "",
        "STALE = rotation history is older than the declared limit or from a previous season.",
        "CROSS-SEASON = the last appearance came from a different NBA season than this fixture.",
        "Availability is UNKNOWN unless the feed published a designation for that player.",
    ]

    priced_rows = [(row, market) for row in document["rows"]
                   for market in row.get("prop_markets") or [] if market.get("status") == "ok"]
    withheld_rows = [(row, market) for row in document["rows"]
                     for market in row.get("prop_markets") or [] if market.get("status") == "withheld"]
    discrepancy_rows = [(row, market) for row in document["rows"]
                        for market in row.get("prop_markets") or []
                        if market.get("status") == "discrepancy"]
    odds_block = document.get("odds") or {}
    lines += ["", "-" * 138,
              "PROP MARKETS - offered price, MODEL ESTIMATE (unvalidated), '--' when withheld or unpriced",
              "-" * 138]
    if not odds_block.get("enabled"):
        lines.append("  Prices not requested for this run (--no-odds).")
    elif not priced_rows and not withheld_rows and not discrepancy_rows:
        lines.append("  No offered prop market matched a projected player for this fixture.")
        for note in odds_block.get("notes") or []:
            lines.append(f"  note: {note}")
    else:
        lines.append(f"{'PLAYER':<26}{'MARKET':<7}{'LINE':>6}{'PROJ':>7}{'SIDE':<7}{'ODDS':>7}"
                     f"{'PROB':>8}{'EV':>9}{'HIGH':>6}  VERDICT / BOOK")
        for row, market in priced_rows:
            verdict = market.get("value_verdict") or "--"
            if not (row.get("availability") or {}).get("actionable"):
                verdict = "RESEARCH ONLY"
            lines.append(
                f"{(row['player'] or '?')[:25]:<26}{market['label']:<7}{market['line']:>6.1f}"
                f"{_num(market.get('projected'), 7)}{market['selection']:<7}"
                f"{_odds_price(market.get('price')):>7}"
                f"{_probability(market.get('probability')):>8}{_ev(market.get('ev')):>9}"
                f"{('HIGH' if market.get('probability_flag') == 'HIGH' else '-'):>6}"
                f"  {verdict} / {market.get('bookmaker') or '--'}")
        for row, market in withheld_rows:
            lines.append(
                f"{(row['player'] or '?')[:25]:<26}{market['label']:<7}{market['line']:>6.1f}"
                f"{_num(market.get('projected'), 7)}{'--':<7}{'--':>7}{'--':>8}{'--':>9}"
                f"{'--':>6}  WITHHELD: gap {_num(market.get('projection_gap'), 4, 1).strip()}"
                f" vs measured error {_num(market.get('error_scale'), 4, 1).strip()}")
        for row, market in discrepancy_rows:
            fair = market.get('de_vig_over')
            if fair is not None and market.get('selection') == 'UNDER':
                fair = 1 - fair
            lines.append(
                f"{(row['player'] or '?')[:25]:<26}{market['label']:<7}{market['line']:>6.1f}"
                f"{_num(market.get('projected'), 7)}{market['selection']:<7}"
                f"{_odds_price(market.get('price')):>7}"
                f"{_probability(market.get('probability')):>8}{'--':>9}{'--':>6}"
                f"  MODEL/MARKET DISCREPANCY: model "
                f"{_probability(market.get('probability')).strip()} vs market "
                f"{_probability(fair).strip()}; EV withheld")
        notes = odds_block.get("notes") or []
        if notes:
            lines.append("")
            for note in notes:
                lines.append(f"  note: {note}")

    high_lines = []
    for row, market in priced_rows:
        selection = f"{row['player']} {market['label']} {market['selection']} {market['line']}"
        high_lines.extend(high_probability_lines(selection, market.get("probability"),
                                                market.get("price"), market.get("ev"),
                                                market.get("de_vig_over")
                                                if market["selection"] == "OVER"
                                                else (1 - market["de_vig_over"]
                                                      if market.get("de_vig_over") is not None else None)))
    if high_lines:
        lines += ["", "-" * 138]
        lines += high_lines

    quota = odds_block.get("quota") or {}
    lines += [
        "",
        "-" * 138,
        f"Odds credits: {quota.get('credits_spent', 0)} spent this run | "
        f"{quota.get('requests', 0)} request(s), {quota.get('cache_hits', 0)} cached | "
        f"provider remaining: {quota.get('credits_remaining') if quota.get('credits_remaining') is not None else '--'}",
        "Market labels: PTS/REB/AST are single stats, PRA/PA/RA are combined counts.",
        "Probabilities are empirical residual frequencies within a rotation-minutes band; combos",
        "use the joint residual of the same historical game (no independence is assumed).",
        "EV = model probability priced at the offered line. LEAN uses the project's existing 5%",
        "gate. De-vig is a benchmark only and never replaces the model probability. No stake is",
        "produced: prop staking is not enabled and no profit is claimed.",
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
    parser.add_argument("--markets", default=",".join(DEFAULT_MARKETS),
                        help="Comma-separated: " + ", ".join(DEFAULT_MARKETS))
    parser.add_argument("--regions", default="us")
    parser.add_argument("--no-odds", action="store_true",
                        help="Do not request prices (avoids any provider credit)")
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
    markets = tuple(m.strip().lower() for m in args.markets.split(",") if m.strip())
    unknown = [m for m in markets if m not in MARKETS]
    if unknown:
        raise ValueError(f"Unsupported market(s): {', '.join(unknown)}; choose from {', '.join(MARKETS)}")
    research(args.date, args.match, args.player, args.limit, args.json, args.minutes_model,
             args.dry_run, use_odds=not args.no_odds, markets=markets, regions=args.regions)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
