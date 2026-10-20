"""Names-only full Czech Liga Pro research, immutable saved runs and Discord."""
import argparse
import json
import math
from pathlib import Path
import re
import sys
import uuid
from scipy.special import expit
from core.historical_storage import TableTennisStore
from table_tennis.contracts import timestamp,utcnow,validate_quote,normalized_name
from table_tennis.scoring import ScoringModel
from table_tennis.training import history_before,reference_quote_details,point_from_match,load_model,probability
from table_tennis.markets import current_quotes,evaluate,references
from table_tennis.report import render,push
from table_tennis.sources import FeedError,provider
from ingest_table_tennis import collect

ROOT=Path(__file__).resolve().parent

def select_event(events,match=None,event_id=None,date=None,live=False,now=None):
    now=timestamp(now or utcnow())
    names=None
    if match:
        parts=re.split(r'\s+vs\s+',match,flags=re.I)
        if len(parts)!=2 or not all(x.strip() for x in parts):raise ValueError('Use --match "First Player vs Second Player"')
        names=[normalized_name(x) for x in parts]
    found=[]
    for e in events:
        if event_id and e['event_id']!=event_id:continue
        if e['status']!=('live' if live else 'scheduled'):continue
        start=timestamp(e['start_utc'])
        if not live and start<=now:continue
        if date and e['start_utc'][:10]!=date:continue
        if names and names not in ([normalized_name(e['player_a']),normalized_name(e['player_b'])],
                                   [normalized_name(e['player_b']),normalized_name(e['player_a'])]):continue
        found.append(e)
    if not found:raise ValueError('No verified matching upcoming/live Czech fixture. Run ingest_table_tennis.py; verify names, UTC date and event ID.')
    if len(found)>1:
        choices='; '.join(e['event_id']+' '+e['start_utc'] for e in found)
        raise ValueError('Multiple same-pair fixtures; specify --event-id: '+choices)
    # Provider order is authoritative and explicitly displayed. Never silently
    # reverse the participant handicap or reuse an event selected only by name.
    return found[0]

def forecast(store,event,now=None,model_path=None,reference_book=None,max_quote_age=300):
    now=now or utcnow()
    if event['status'] not in ('scheduled','live'):raise ValueError('Cannot forecast a completed/cancelled match')
    if event['status']=='scheduled' and timestamp(event['start_utc'])<=timestamp(now):raise ValueError('Kickoff already passed; refresh status')
    if (timestamp(now)-timestamp(event['retrieved_utc'])).total_seconds()> (30 if event['status']=='live' else 86400):
        raise ValueError('Fixture/live state is stale; refresh data before forecasting')
    history=store.events(finished_only=True)
    h=history_before(history,event['start_utc']);x,observations=h.features(event)
    quotes=store.quotes(event['event_id'])
    fresh,rejected=current_quotes(quotes,event,now,30 if event['status']=='live' else max_quote_age)
    anchor=reference_quote_details(quotes,event['start_utc'],reference_book)
    # Archived anchors must also be fresh at the time of a pre-match run.
    if event['status']=='scheduled':
        # Freshness is measured against NOW above. Historical closing-price
        # selection must not prevent a current forecast hours before kickoff.
        anchor=reference_quote_details(fresh,event['start_utc'],reference_book,max_lead_seconds=None)
    market=anchor['probability_a'] if anchor else None
    model=load_model(model_path or ROOT/'data/table_tennis/model.json',event['start_utc'])
    warnings=[]
    enough=min(observations['player_a_history'],observations['player_b_history'])>=8
    if model and enough:
        hybrid=market is not None and model['market_weights'] is not None
        p,_=probability({'x':x,'market':market},model['market_weights'] if hybrid else model['strength_weights'],hybrid)
        strategy='FITTED MARKET + STRENGTH + H2H' if hybrid else 'FITTED STRENGTH + H2H'
        warnings.append(model['status'])
    elif market is not None:
        p=point_from_match(market);strategy='MARKET-ANCHORED SCORING REFERENCE'
        warnings.append('Insufficient trained player coverage: this forecasts market-implied scores, not an independent betting edge.')
    elif enough:
        baseline=float(expit(math.log(10)*x[0]));p=point_from_match(baseline)
        strategy='UNFITTED ELO SCORING REFERENCE'
        warnings.append('Elo is an explicit starting model; H2H/workload observations are displayed but effects are not invented.')
    else:
        raise ValueError(f"No defensible probability: need fresh paired moneyline or at least 8 historical matches each. Current history A={observations['player_a_history']}, B={observations['player_b_history']}. Collect results/prices first.")
    for side in ('a','b'):
        last=observations['last_seen_'+side]
        if last and (timestamp(event['start_utc'])-timestamp(last)).days>30:
            warnings.append(f"Player {side.upper()} last observed more than 30 days ago; current form is uncertain.")
    d=ScoringModel(p).match(event['game_scores'],event['current_points'])
    priced=evaluate(d,fresh,event);reference=references(d)
    gaps=[]
    for book,line in sorted({(q['bookmaker'],q['line']) for q in fresh if q['market']=='points_spread'}):
        for side in ('a','b'):
            gap=store.player_point_cover_gap(event['player_'+side+'_id'],line if side=='a' else -line,
                                            book,as_of=event['start_utc'])
            gap['player']=event['player_'+side];gaps.append(gap)
    # Tuple score keys are internal numerical data, not JSON object keys.
    d.pop('first_game_scores')
    warnings.append('Injury, travel and motivation facts unavailable unless independently supplied; no numerical adjustment assumed.')
    if event['status']=='live':warnings.append('Point feed transport latency and serve-specific accuracy are unverified; live output is research only.')
    if rejected:warnings.append(f'{len(rejected)} stale/wrong-phase/unsynchronized quotes excluded.')
    return dict(run_id='tt_'+uuid.uuid4().hex,created_utc=now,event=event,strategy=strategy,
        implied_point_probability=p,market_reference_probability=market,
        market_reference_quote=anchor['quote'] if anchor else None,observations=observations,
        model_version=model.get('version',model['created_utc']) if model else None,forecast=d,
        priced_markets=priced,reference_markets=reference,win_cover_gaps=gaps,warnings=warnings,
        recommendation_status='RESEARCH ONLY: prospective validation required')

def save(store,report):
    folder=ROOT/'output/table_tennis';folder.mkdir(parents=True,exist_ok=True)
    store.save_run(report)
    (folder/(report['run_id']+'.json')).write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    (folder/(report['run_id']+'.md')).write_text(render(report),encoding='utf-8')
    return folder/(report['run_id']+'.md')

def main():
    # Windows terminals/pipes can default to a legacy code page. Emit UTF-8
    # consistently so the report's symbols never abort a successful forecast.
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='replace',line_buffering=True)
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--match');p.add_argument('--event-id');p.add_argument('--date',help='UTC YYYY-MM-DD')
    p.add_argument('--config',type=Path,help='Match settings JSON; defaults to data/table_tennis/current_match_config.json when no match/event is supplied')
    p.add_argument('--provider',choices=['auto','betsapi','oddsio'],default='auto')
    p.add_argument('--reference-book',help='Anchor bookmaker; default latest eligible paired moneyline')
    p.add_argument('--no-refresh',action='store_true',help='Use verified local data only')
    p.add_argument('--live',action='store_true',help='Use actual collected live score; never guessed/manual scores')
    p.add_argument('--quotes-file',type=Path,help='Verified normalized quote list JSON, decimal prices')
    p.add_argument('--mystake-url',help='Public MyStake prematch match URL; uses browser, no API key')
    p.add_argument('--mystake-text-file',type=Path,help='Fallback: freshly copied match-page text, no automated browser')
    p.add_argument('--start-utc',help='Confirmed match start with timezone offset; MyStake display omits timezone')
    p.add_argument('--best-of',type=int,choices=[5],help='Confirm actual match format for browser collection')
    p.add_argument('--headless',action='store_true',help='Hide collection browser; default visible')
    p.add_argument('--win-cover-player-id',help='Calculate historical win versus point-cover gap for stored player ID')
    p.add_argument('--point-handicap',type=float,help='Signed player point spread for historical comparison')
    p.add_argument('--bookmaker',help='Single bookmaker for historical win/cover comparison')
    actions=p.add_mutually_exclusive_group()
    actions.add_argument('--push',help='Immutable saved run ID, not event ID')
    actions.add_argument('--show',help='Print saved report by run ID, or latest; no refresh or new forecast')
    actions.add_argument('--list-runs',action='store_true',help='List ten most recent saved reports and their IDs')
    p.add_argument('--dry-run',action='store_true',help='Preview Discord without sending')
    args=p.parse_args()
    if args.config or not any((args.match,args.event_id,args.push,args.show,args.list_runs,args.win_cover_player_id)):
        config_path=args.config or ROOT/'data/table_tennis/current_match_config.json'
        if config_path.exists():
            try:
                settings=json.loads(config_path.read_text(encoding='utf-8-sig'))
                if not isinstance(settings,dict):raise ValueError('Match config must be a JSON object')
                for key in ('match','mystake_url','start_utc','best_of'):
                    if getattr(args,key) is None:setattr(args,key,settings.get(key))
                if args.mystake_text_file is None:
                    args.mystake_text_file=ROOT/'data/table_tennis/current_match.txt'
            except (OSError,ValueError) as exc:p.exit(2,'Invalid match config: '+str(exc)+'\n')
        elif args.config:p.error('Match config file does not exist: '+str(config_path))
    print('CZECH LIGA PRO | Loading saved report...' if args.show or args.list_runs or args.push else 'CZECH LIGA PRO | Starting match run...',flush=True)
    store=TableTennisStore()
    try:
        if args.list_runs:
            runs=store.runs()[-10:]
            if not runs:print('No saved reports. Run an upcoming match first.')
            for report in reversed(runs):
                e=report['event']
                print(f"{report['run_id']} | {e['player_a']} vs {e['player_b']} | Saved UTC {report['created_utc']}")
            return
        if args.show:
            if args.show=='latest':
                runs=store.runs()
                if not runs:raise ValueError('No saved reports. Run an upcoming match first.')
                report=runs[-1]
            else:report=store.run(args.show)
            print('SAVED REPORT — original captured prices; no fresh forecast.\n')
            print(render(report))
            print('Discord (Git Bash): venv/Scripts/python.exe -u run_table_tennis.py --push "'+report['run_id']+'"')
            return
        if args.push:
            count=push(store.run(args.push),args.dry_run)
            if not count:raise ValueError('No Discord delivery: check configured destinations or duplicate suppression')
            print('Discord preview destinations:' if args.dry_run else 'Discord deliveries:',count);return
        if args.win_cover_player_id:
            if args.point_handicap is None or not args.bookmaker:p.error('Supply --point-handicap and --bookmaker')
            print(json.dumps(store.player_point_cover_gap(args.win_cover_player_id,args.point_handicap,args.bookmaker),indent=2));return
        if not args.match and not args.event_id:p.error('--match or --event-id is required')
        if args.date:timestamp(args.date+'T00:00:00Z')
        if args.mystake_text_file and not args.mystake_url:p.error('--mystake-text-file also requires --mystake-url')
        browser_notes=[]
        if args.mystake_url:
            if not args.match or not args.start_utc or not args.best_of:
                p.error('--mystake-url requires --match, --start-utc and --best-of 5')
            if args.live or args.no_refresh:p.error('MyStake collection is prematch only; omit --live and --no-refresh')
            from table_tennis.browser_source import capture,parse_capture,capture_from_text
            if args.mystake_text_file:
                raw=capture_from_text(args.mystake_text_file.read_text(encoding='utf-8-sig'),args.mystake_url)
                raw['captured_utc']=timestamp(args.mystake_text_file.stat().st_mtime).isoformat()
                age=(timestamp(utcnow())-timestamp(raw['captured_utc'])).total_seconds()
                if age<0 or age>300:raise ValueError('Copied sportsbook text must have been saved within five minutes; copy fresh prices again')
            else:raw=capture(args.mystake_url,args.headless)
            event,quotes,browser_notes=parse_capture(raw,args.match,args.start_utc,args.best_of)
            folder=ROOT/'output/table_tennis/browser';folder.mkdir(parents=True,exist_ok=True)
            (folder/(uuid.uuid4().hex+'.json')).write_text(json.dumps(raw,indent=2),encoding='utf-8')
            store.upsert_event(event)
            for q in quotes:store.add_quote(q)
            if args.event_id and args.event_id!=event['event_id']:raise ValueError('Requested event ID differs from MyStake URL')
            print('Browser capture:',len(quotes),'paired markets')
        elif not args.no_refresh:
            counts,notes=collect(store,args.provider,0,False)
            print('Fixture refresh:',json.dumps(counts))
            for note in notes:print('NOTE:',note)
        if not args.mystake_url:event=select_event(store.events(),args.match,args.event_id,args.date,args.live)
        if not args.no_refresh and not args.mystake_url:
            feed=provider(event['provider'])
            try:
                quotes,notes=feed.quotes(event)
                for q in quotes:store.add_quote(q)
                for note in notes:print('NOTE:',note)
            finally:feed.close()
        if args.quotes_file:
            quotes=json.loads(args.quotes_file.read_text(encoding='utf-8-sig'))
            quotes=quotes.get('quotes',[]) if isinstance(quotes,dict) else quotes
            valid=[validate_quote(q) for q in quotes]
            if any(q['event_id']!=event['event_id'] for q in valid):raise ValueError('Manual quote event ID mismatch')
            for q in valid:store.add_quote(q)
        report=forecast(store,event,reference_book=args.reference_book)
        report['warnings'].extend(browser_notes)
        print(render(report));print('Saved report:',save(store,report))
        print('RUN_ID='+report['run_id'],flush=True)
        print('Discord (Git Bash): venv/Scripts/python.exe run_table_tennis.py --push "'+report['run_id']+'"')
    except (ValueError,OSError) as exc:p.exit(2,str(exc)+'\n')

if __name__=='__main__':main()
