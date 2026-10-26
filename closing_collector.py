"""Pre-match closing odds collector with strict kickoff cutoffs.

Purpose: archive the last verified pre-kickoff price pair for every fixture
inside a configurable window, so closing-line value can be measured against the
price a forecast actually used. This module is deliberately read-only with
respect to prices: it never re-prices a fixture and never overwrites a snapshot.

GUARDS
    * A fixture with no verified kickoff time is refused.
    * A fixture whose kickoff has passed is refused as in-play; its prices are
      not archived as a closing line.
    * A fixture closer than the minimum lead time is refused rather than being
      treated as a stale-but-valid close.
    * A provider kickoff EARLIER than the league's is always refused. A
      provider kickoff later than the league's by more than the tolerance is
      refused for review. The earlier of the two times is the binding deadline.
    * A quote with no bookmaker timestamp, or one published at/after kickoff,
      is refused. Storage re-checks both conditions.
    * Only complete two-sided pairs from one bookmaker are stored; a lone price
      is not a market.

USAGE
    python closing_collector.py --league NHL
    python closing_collector.py --league NBA --date 2026-10-25 --window-minutes 180
    python closing_collector.py --league NHL --events-file saved_events.json --dry-run

The scheduler proposal in docs/ODDS_CLV_SCHEDULER_PROPOSAL.md is NOT active:
nothing in this repository registers this collector to run on a timer.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from sports_feed import ROOT, atomic_json
from core.historical_storage import save_odds_snapshot, get_odds_snapshots, _snapshot_price
from score_odds import KEYS, for_fixture

ET = ZoneInfo("America/New_York")
SPORTS = {"NCAAF": "ncaaf", "NBA": "basketball", "WNBA": "basketball",
          "NCAAB": "basketball", "NCAAW": "basketball", "NHL": "nhl"}

DEFAULT_WINDOW_MINUTES = 30
DEFAULT_MIN_LEAD_MINUTES = 1
DEFAULT_MAX_QUOTE_AGE_MINUTES = 5
# The Odds API mirrors the league schedule. Measured on consecutive NHL games it
# ran exactly 600s late, which blocked every closing capture. A late mirror is
# tolerated up to this many minutes because the league time stays the earlier,
# therefore the binding, in-play deadline. An EARLIER provider time is never
# tolerated: it would mean the provider already treats the event as in-play.
KICKOFF_TOLERANCE_MINUTES = 15


def _utc(value, field):
    """Parse a timestamp that must carry a timezone. Naive values are refused."""
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        stamp = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            stamp = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"{field} is not an ISO-8601 timestamp")
    if stamp.tzinfo is None:
        raise ValueError(f"{field} has no timezone; refusing to guess one")
    return stamp.astimezone(dt.timezone.utc)


def _positive_int(value, field, minimum):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{field} must be an integer >= {minimum}")
    return value


def tracked_predictions(league, db_path=None):
    return [row for row in get_odds_snapshots(db_path, capture_kind="prediction")
            if row["league"].upper() == league.upper()]


def load_official_fixtures(league, day):
    """Fresh public fixture/status check, before spending odds-provider credits."""
    if league == "NHL":
        from nhl_sources import get_json, parse_game, NHL
        url = NHL + "/schedule/" + day
        payload, retrieved = get_json(url, hours=0)
        return [row for week in payload.get("gameWeek", []) for item in week.get("games", [])
                if (row := parse_game(item, retrieved, url)) is not None]
    from sports_feed import fetch_json, parse_game
    slugs = {"NBA": "basketball/nba", "WNBA": "basketball/wnba",
             "NCAAB": "basketball/mens-college-basketball", "NCAAW": "basketball/womens-college-basketball",
             "NCAAF": "football/college-football"}
    url = "https://site.web.api.espn.com/apis/site/v2/sports/" + slugs[league] + "/scoreboard?dates=" + day.replace("-", "")
    payload = fetch_json(url, cache_hours=0)
    return [row for event in payload.get("events", []) if (row := parse_game(event, league)) is not None]


def collect(events, league, now=None, window_minutes=DEFAULT_WINDOW_MINUTES,
            min_lead_minutes=DEFAULT_MIN_LEAD_MINUTES,
            max_quote_age_minutes=DEFAULT_MAX_QUOTE_AGE_MINUTES,
            db_path=None, only_date=None, dry_run=False, only_event_id=None,
            fixtures=None, tracked=None):
    """Collect tracked markets only, after fresh official fixture verification.

    'closing' is a legacy storage category. Every report calls this a last
    observed prematch reference; a single run cannot prove a market close.
    """
    league = str(league or "").upper()
    if league not in SPORTS: raise ValueError(f"No collector mapping for {league!r}")
    for val, name, lower in ((window_minutes,"window_minutes",1),(min_lead_minutes,"min_lead_minutes",0),(max_quote_age_minutes,"max_quote_age_minutes",1)):
        _positive_int(val,name,lower)
    if min_lead_minutes >= window_minutes: raise ValueError("min_lead_minutes must be smaller than window_minutes")
    now = _utc(now,"now") or dt.datetime.now(dt.timezone.utc)
    if only_date is not None: dt.date.fromisoformat(only_date)
    tracks = tracked_predictions(league,db_path) if tracked is None else tracked
    report = dict(league=league,sport=SPORTS[league],as_of=now.isoformat(),dry_run=bool(dry_run),
                  window_minutes=window_minutes,min_lead_minutes=min_lead_minutes,
                  max_quote_age_minutes=max_quote_age_minutes,kickoff_tolerance_minutes=KICKOFF_TOLERANCE_MINUTES,
                  considered=0,captured=[],refused=[],outside_window=[],other_date=0,
                  reference_label="Last observed eligible prematch quote; not guaranteed sportsbook close",
                  note="No scheduler activated. No predictions or wagers are created.")
    official = {str(g.get("game_id")):g for g in fixtures or []}
    wanted = {}
    for row in tracks:
        ident = str(row.get("source_event_id") or "")
        if only_event_id is not None and ident != str(only_event_id): continue
        payload = row.get("payload") if isinstance(row.get("payload"),dict) else {}
        try:
            kickoff = _utc(row.get("kickoff_utc"),"tracked kickoff")
            if kickoff is None: raise ValueError("tracked kickoff unavailable")
            if only_date and kickoff.astimezone(ET).date().isoformat()!=only_date:
                report["other_date"]+=1;continue
            lead=(kickoff-now).total_seconds()/60
            if lead<=0: raise ValueError("in_play")
            if lead<min_lead_minutes: raise ValueError("inside_min_lead")
            if lead>window_minutes:
                report["outside_window"].append(dict(event_id=ident,minutes_to_kickoff=lead));continue
            if not ident or not row.get("bookmaker") or not row.get("scope") or not payload.get("official_fixture_id"):
                raise ValueError("tracked prediction lacks verified provider/bookmaker/official identity")
            if fixtures is None: raise ValueError("fresh_official_fixture_verification_required")
            g=official.get(str(payload["official_fixture_id"]))
            if not g or g.get("completed") or g.get("status") not in {"FUT","PRE","STATUS_SCHEDULED"}:
                raise ValueError("official fixture unavailable, started or not scheduled")
            if _utc(g.get("start_time"),"official kickoff") != kickoff:
                raise ValueError("official kickoff changed; reschedule review required")
            from grade_predictions import normalise_team
            if any(normalise_team(g.get(side+"_team",""),league.lower()) != normalise_team(row.get(side+"_team",""),league.lower()) for side in ("home","away")):
                raise ValueError("official team orientation mismatch")
            wanted.setdefault(ident,[]).append((row,g,kickoff))
        except (ValueError,TypeError) as exc:
            report["refused"].append(dict(event_id=ident,reason=str(exc)))
    seen=set()
    for event in events or []:
        if not isinstance(event,dict):
            report["refused"].append(dict(event_id=None,reason="event is not an object"));continue
        ident=str(event.get("id") or "")
        if ident not in wanted: continue
        report["considered"]+=1
        for row,g,kickoff in wanted[ident]:
            try:
                commence=_utc(event.get("commence_time"),"provider kickoff")
                if commence is None: raise ValueError("provider kickoff unavailable")
                skew=(commence-kickoff).total_seconds()
                # Measured, never assumed: record the provider-vs-league mirror
                # offset on every considered event, including refused ones, so a
                # tolerance decision rests on observed deltas rather than a
                # remembered 600s anecdote. No extra request is made for this.
                report.setdefault("kickoff_skew_seconds",[]).append(
                    dict(event_id=ident,sport=SPORTS[league],provider_minus_official_seconds=skew))
                if skew<0: raise ValueError("provider kickoff earlier than official fixture")
                if skew>KICKOFF_TOLERANCE_MINUTES*60:
                    raise ValueError("provider kickoff changed/mismatches official fixture")
                # Never later than the league's own kickoff, whatever the mirror says.
                deadline=min(kickoff,commence)
                if event.get("live") is True or event.get("in_play") is True or event.get("completed") is True:
                    raise ValueError("provider marks event in_play/completed")
                books=[b for b in event.get("bookmakers",[]) if b.get("key")==row["bookmaker"]]
                if not books: raise ValueError("tracked bookmaker unavailable")
                game={**g,"league":league,"date":kickoff.astimezone(ET).date().isoformat()}
                specs,note=for_fixture([{**event,"bookmakers":books}],game,now=now)
                specs=[q for q in specs if q["kind"]==row["market_type"] and not q.get("period")]
                if not specs: raise ValueError("no_verified_price_pair")
                for spec in specs:
                    if spec.get("scope")!=row["scope"]: raise ValueError("settlement scope mismatch")
                    quoted=_utc(spec.get("updated"),"bookmaker timestamp")
                    if quoted is None: raise ValueError("unverified_quote_time")
                    if quoted>=deadline: raise ValueError("quote_after_kickoff")
                    age=(now-quoted).total_seconds()/60
                    if age < -5/60: raise ValueError("quote_timestamp_in_future")
                    if age>max_quote_age_minutes: raise ValueError("stale_quote")
                    _snapshot_price(spec.get("price_a"),"price_a");_snapshot_price(spec.get("price_b"),"price_b")
                    signature=(ident,row["bookmaker"],spec["kind"],spec["line"],spec["updated"])
                    if signature in seen: continue
                    seen.add(signature)
                    quote=dict(capture_kind="closing",sport=SPORTS[league],league=league,
                        event_key=f"{league}:{ident}:{spec['kind']}:{spec['line']}",source_event_id=ident,
                        game_date=game["date"],kickoff_utc=deadline,home_team=g["home_team"],away_team=g["away_team"],
                        market_type=spec["kind"],line=spec["line"],price_a=spec["price_a"],price_b=spec["price_b"],
                        bookmaker=row["bookmaker"],observed_utc=now,quote_updated_utc=quoted,source="odds_api",scope=spec["scope"],
                        payload=dict(spec=spec,official_fixture_id=str(g["game_id"]),official_status=g["status"],
                                     period="full_game",odds_format="american",minutes_to_kickoff=(deadline-now).total_seconds()/60,
                                     official_kickoff_utc=kickoff.isoformat(),provider_kickoff_utc=commence.isoformat(),
                                     provider_minus_official_seconds=skew,kickoff_deadline_utc=deadline.isoformat(),
                                     reference_label=report["reference_label"],note=note))
                    saved=dict(dry_run=True,event_key=quote["event_key"]) if dry_run else save_odds_snapshot(quote,db_path)
                    report["captured"].append({**saved,"market_type":spec["kind"],"line":spec["line"],"bookmaker":row["bookmaker"]})
            except (ValueError,TypeError,KeyError) as exc:
                # Preserve the already-paid evidence; never spend another API
                # request merely to discover the size of a kickoff discrepancy.
                try:
                    provider_start=_utc(event.get("commence_time"),"provider kickoff")
                    delta=(provider_start-kickoff).total_seconds() if provider_start else None
                except (ValueError,TypeError):
                    delta=None
                report["refused"].append(dict(event_id=ident,market=row["market_type"],reason=str(exc),
                    official_kickoff_utc=kickoff.isoformat(),tracked_kickoff_utc=row.get("kickoff_utc"),
                    provider_kickoff_utc=event.get("commence_time"),provider_minus_official_seconds=delta,
                    official_fixture_id=str(g.get("game_id")),official_status=g.get("status")))
    report["tracked_events"]=len(wanted)
    report["missing_provider_events"]=sorted(set(wanted)-{str(e.get("id")) for e in events or [] if isinstance(e,dict)})
    return report


def main(argv=None):
    import sys
    if hasattr(sys.stdout,"reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser(description="Tracked last-observed prematch quotes; no scheduler")
    parser.add_argument("--league",required=True,choices=sorted(KEYS))
    parser.add_argument("--date")
    parser.add_argument("--event-id",help="One tracked provider event ID; no whole-slate capture")
    parser.add_argument("--window-minutes",type=int,default=DEFAULT_WINDOW_MINUTES)
    parser.add_argument("--min-lead-minutes",type=int,default=DEFAULT_MIN_LEAD_MINUTES)
    parser.add_argument("--max-quote-age-minutes",type=int,default=DEFAULT_MAX_QUOTE_AGE_MINUTES)
    parser.add_argument("--events-file",type=Path,help="Replay saved provider events, no odds API request")
    parser.add_argument("--fixtures-file",type=Path,help="Replay official fixtures with --events-file only")
    parser.add_argument("--db",type=Path)
    parser.add_argument("--dry-run",action="store_true")
    args=parser.parse_args(argv)
    if args.fixtures_file and not args.events_file: parser.error("--fixtures-file is only for offline replay with --events-file")
    try:
        day=args.date or dt.datetime.now(ET).date().isoformat();dt.date.fromisoformat(day)
        tracks=tracked_predictions(args.league,args.db)
        # Gate locally before any paid odds request. No tracked window = zero credits.
        now=dt.datetime.now(dt.timezone.utc)
        candidates=[r for r in tracks if (not args.event_id or str(r.get("source_event_id"))==args.event_id)
                    and r.get("kickoff_utc") and r.get("game_date")==day
                    and args.min_lead_minutes <= (_utc(r["kickoff_utc"],"kickoff")-now).total_seconds()/60 <= args.window_minutes]
        if not candidates:
            report=dict(captured=[],refused=[],outside_window=[],other_date=0,note="No tracked prediction in window; no API request made",paid_odds_requests=0)
        else:
            fixtures=json.loads(args.fixtures_file.read_text(encoding="utf-8-sig")) if args.fixtures_file else load_official_fixtures(args.league,day)
            fixtures=fixtures.get("games",[]) if isinstance(fixtures,dict) else fixtures
            preflight=collect([],args.league,now=now,window_minutes=args.window_minutes,min_lead_minutes=args.min_lead_minutes,
                max_quote_age_minutes=args.max_quote_age_minutes,db_path=args.db,only_date=day,only_event_id=args.event_id,
                dry_run=True,fixtures=fixtures,tracked=candidates)
            if not preflight["tracked_events"]:
                report={**preflight,"paid_odds_requests":0}
            else:
                if args.events_file: events=json.loads(args.events_file.read_text(encoding="utf-8-sig"))
                else:
                    from score_odds import fetch
                    usage={}
                    events=fetch(args.league,usage=usage)
                report=collect(events,args.league,now=dt.datetime.now(dt.timezone.utc),window_minutes=args.window_minutes,
                    min_lead_minutes=args.min_lead_minutes,max_quote_age_minutes=args.max_quote_age_minutes,
                    db_path=args.db,only_date=day,dry_run=args.dry_run,only_event_id=args.event_id,fixtures=fixtures,tracked=candidates)
                report["paid_odds_requests"]=0 if args.events_file else 1
                report["api_usage"]={} if args.events_file else usage
                report["api_credit_note"]="One league request for three markets/us; credits are provider-billed, not one credit per request. No additional odds request is made."
    except (ValueError,OSError,KeyError) as exc: parser.exit(2,"Collection failed: "+str(exc)+"\n")
    folder=ROOT/"output/odds_closing";folder.mkdir(parents=True,exist_ok=True)
    path=folder/(args.league+"_"+dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+".json")
    atomic_json(path,report)
    print(json.dumps(dict(captured=len(report["captured"]),new_rows=sum(bool(r.get("inserted")) for r in report["captured"]),
                         refused=len(report["refused"]),paid_odds_requests=report["paid_odds_requests"],report=str(path)),indent=2))
    return report


if __name__=="__main__": main()
