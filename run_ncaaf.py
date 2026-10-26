"""Guarded NCAAF predictions from verified FBS fixtures and score ratings."""
import argparse
import datetime as dt
import json
import math
from pathlib import Path
from sports_feed import ROOT, today, atomic_json
from models.score_ratings import ScoreRatings, market_probability, price_market


def resolve(name, names):
    normalize = lambda x: "".join(c for c in x.lower() if c.isalnum())
    exact = [n for n in names if normalize(n) == normalize(name)]
    hits = exact or [n for n in names if normalize(name) in normalize(n)]
    if len(hits) != 1:
        raise ValueError(f"Unknown or ambiguous team {name!r}: {', '.join(hits[:10])}")
    return hits[0]


def predict_fixture(game, model, specs, sport="ncaaf"):
    projection = model.predict(game["home_team"], game["away_team"], game.get("neutral_site", False))
    margin = projection["home_points"]-projection["away_points"]
    total = projection["home_points"]+projection["away_points"]
    markets = []
    for spec in specs:
        kind, line = spec["kind"], spec["line"]
        if kind == "moneyline":
            p = 0.5*(1+math.erf(margin/(projection["margin_sd"]*math.sqrt(2))))
            probabilities = (p, 1-p, 0)
        else:
            probabilities = market_probability(margin if kind == "spread" else total,
                projection["margin_sd"] if kind == "spread" else projection["total_sd"], line, kind == "spread")
        markets.append(price_market(kind, line, probabilities, spec.get("price_a"), spec.get("price_b")))
    segments = {}
    if sport == "basketball" and game["league"].upper() == "NBA":
        from models.basketball_periods import provisional_periods
        segments = provisional_periods(projection)
    if sport == "basketball":
        from models.basketball_readiness import readiness, observation_markets
        cutoff = getattr(model, "cutoff", None)
        gate = readiness(game, getattr(model, "games", []), cutoff if isinstance(cutoff, str) else game["date"])
        if gate is not None:
            segments["readiness"] = gate
            projection["season_games_played"] = dict(gate["season_games_played"])
            if not gate["eligible"]:
                markets = observation_markets(markets)
    return {**segments, "sport": sport, "league": game["league"], "home_team": game["home_team"],
            "away_team": game["away_team"], "game_date": game["date"], "game_id": game["game_id"],
            "projection": projection, "markets": markets, "fixture": game,
            "notes": [projection["note"], "Injuries, rosters and weather are not automatically included."]}


def show(result):
    from score_review import format_review
    print('\n' + format_review(result))


def push(result):
    from discord_integration import push_prediction_to_all
    return push_prediction_to_all(result['sport'], result, dry_run=False) > 0


def store(result):
    import os
    import uuid
    # Direct runners also need a contemporaneous forecast identifier shared by
    # their ledger rows and quotes. This is not a synthetic workflow_runs row.
    result.setdefault("_odds_capture_run_id", os.environ.get("MSP_RUN_ID") or
                      result.get("_workflow_run_id") or "direct_" + uuid.uuid4().hex)
    from core.historical_storage import init_db, store_prediction
    init_db()
    from models.basketball_readiness import projection_only, observation_markets
    if projection_only(result):
        # INFO rows preserve observation snapshots but are excluded by grading
        # and record filters. Never persist a stale LEAN from an earlier layer.
        result = {**result, "markets": observation_markets(result["markets"], result["readiness"]["status"])}
    p = result["projection"]
    for m in result["markets"]:
        kind = m["kind"]
        prices = ({"home_ml": m["price_a"], "away_ml": m["price_b"]} if kind == "moneyline" else
                  {"spread_home_price": m["price_a"], "spread_away_price": m["price_b"]} if kind == "spread" else
                  {"over": m["price_a"], "under": m["price_b"]})
        raw = {**result, "event_key": f"{result['league']}:{result['game_id']}:{kind}:{m['line']}",
               "_pick": m["pick"], "market_odds": {k:v for k,v in prices.items() if v is not None},
               "spread": {"market_spread": m["line"], "pick": m["pick"]}}
        store_prediction(result["sport"], result["home_team"], result["away_team"], kind,
            (p["home_points"]+p["away_points"]) if kind == "total" else m["prob_a"],
            m["line"] if kind != "moneyline" else 0.5,
            None if projection_only(result) else max(v for v in (m["ev_a"], m["ev_b"], 0) if v is not None)*100,
            None, m["recommendation"], raw, league=result["league"],
            stake_size=m.get("stake_size"))


def main(sport="ncaaf", argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--league", default="NCAAF" if sport == "ncaaf" else "NBA")
    ap.add_argument("--match", action="append")
    ap.add_argument("--date", default=None)
    ap.add_argument("--list-teams", action="store_true")
    ap.add_argument("--moneyline", action="append", nargs=2, metavar=("HOME_ODDS", "AWAY_ODDS"))
    ap.add_argument("--spread", action="append", nargs=3, metavar=("HOME_LINE", "HOME_ODDS", "AWAY_ODDS"))
    ap.add_argument("--total", action="append", nargs=3, metavar=("LINE", "OVER_ODDS", "UNDER_ODDS"))
    ap.add_argument("--odds", action="store_true", help="Fetch matched live moneyline, spread and total pairs")
    ap.add_argument("--dry-run", action="store_true", help="Predict without database writes")
    ap.add_argument("--push", nargs="+", type=int)
    args = ap.parse_args(argv)
    league = args.league.upper()
    league = {"NZ NBL": "NZNBL", "NEW ZEALAND NBL": "NZNBL", "BUNDESLIGA": "BBL", "GERMAN BBL": "BBL"}.get(league, league)
    if league not in ({"NCAAF"} if sport == "ncaaf" else {"NBA", "WNBA", "NCAAB", "NCAAW", "KBL", "NZNBL", "BBL"}):
        ap.error("Unsupported league for score ratings")
    if args.date:
        try:
            dt.date.fromisoformat(args.date)
        except ValueError:
            ap.error("--date must be YYYY-MM-DD")
    review = ROOT / "data" / f"{sport}_{league.lower()}_review.json"
    if args.push:
        saved = json.loads(review.read_text(encoding="utf-8"))
        for n in args.push:
            if not 1 <= n <= len(saved["rows"]):
                ap.error("Push row outside latest review")
            if not push(saved["rows"][n-1]):
                raise SystemExit("Discord send failed; inspect configured destinations")
        return
    path = ROOT / "data" / ("ncaaf_model.json" if sport == "ncaaf" else f"basketball_{league.lower()}_games.json")
    if not path.exists():
        ap.error(f"Missing {path.name}; run ingest_ncaaf_model.py or ingest_basketball_espn.py first")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (dt.date.fromisoformat(today())-dt.date.fromisoformat(data["updated"])).days > 7:
        ap.error("Fixture feed is stale; refresh before predicting")
    names = sorted({g[s+"_team"] for g in data["games"] for s in ("home", "away")})
    if args.list_teams:
        print("\n".join(names)); return
    requested = []
    try:
        for match in args.match or []:
            first, second = match.split(" vs ", 1)
            requested.append({resolve(first, names), resolve(second, names)})
        fixtures = [g for g in data["games"] if not g["completed"] and g["date"] >= today()
                    and g.get("status") not in {"STATUS_IN_PROGRESS", "STATUS_HALFTIME", "STATUS_POSTPONED", "STATUS_CANCELED"}
                    and (not args.date or g["date"] == args.date)
                    and (not requested or {g["home_team"], g["away_team"]} in requested)]
        if not requested and not args.date:
            ap.error("Supply --match or --date")
        if requested:
            selected = []
            for pair in requested:
                hits = sorted([g for g in fixtures if {g["home_team"], g["away_team"]} == pair], key=lambda g:g["date"])
                if not hits:
                    raise ValueError(f"No verified upcoming fixture: {sorted(pair)}")
                selected.append(hits[0])
            fixtures = selected
        if not fixtures:
            raise ValueError("No verified upcoming games for these inputs")
        def number(s):
            return None if s.lower() == "none" else float(s)
        specs = []
        for kind in ("moneyline", "spread", "total"):
            for values in getattr(args, kind) or []:
                line = 0.5 if kind == "moneyline" else float(values[0])
                specs.append({"kind": kind, "line": line, "price_a": number(values[-2]), "price_b": number(values[-1])})
        if len(fixtures) > 1 and specs:
            raise ValueError("Priced custom lines require one match per run; do not apply one game's prices to a slate")
        if args.odds and specs:
            raise ValueError("Choose --odds or manually priced flags for this run")
        events = []
        if args.odds:
            from score_odds import fetch
            events = fetch(league)
        if not specs:
            specs = [{"kind": "moneyline", "line": 0.5}]
        models, rows = {}, []
        for game in fixtures:
            cutoff = min(today(), game["date"])
            if cutoff not in models:
                models[cutoff] = ScoreRatings(data["games"], cutoff, min_games=4 if sport == "ncaaf" else 5)
            game_specs, odds_note = specs, "No live odds requested"
            if args.odds:
                from score_odds import for_fixture
                fetched, odds_note = for_fixture(events, game, include_periods=(league == "NBA"))
                game_specs = [s for s in fetched if not s.get("period")] or specs
            try:
                result = predict_fixture(game, models[cutoff], game_specs, sport)
            except ValueError as exc:
                if requested:
                    raise
                print(f"[SKIPPED] {game['away_team']} @ {game['home_team']}: {exc}")
                continue
            result["odds_source"] = {"note": odds_note, "markets": game_specs}
            result["period_market_quotes"] = {period: [s for s in fetched if s.get("period") == period]
                for period in ("h1", "q1")} if args.odds and league == "NBA" else {}
            from score_review import format_review
            result["formatted_review"] = format_review(result)
            print(odds_note)
            show(result)
            rows.append(result)
        if not rows:
            raise ValueError("No fixtures passed the history requirements")
        if not args.dry_run:
            from core.historical_storage import capture_prediction_odds
            for row in rows:
                store(row)
                # Archive the exact pairs this forecast used; the archive is
                # append-only, so a later closing capture cannot rewrite it.
                capture = capture_prediction_odds(row)
                if capture["refused"]:
                    print(f"Odds snapshot refused: {capture['refused']}")
            atomic_json(review, {"generated": today(), "rows": rows})
            print(f"Saved {len(rows)} matches to {review.name}; Discord OFF")
    except (ValueError, KeyError) as exc:
        ap.error(str(exc))
    return rows


if __name__ == "__main__":
    main()
