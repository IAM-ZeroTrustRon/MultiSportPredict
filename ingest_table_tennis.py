"""Collect verified Czech Liga Pro fixtures, completed games and quote history."""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time
from core.historical_storage import TableTennisStore
from table_tennis.contracts import validate_event, validate_quote, timestamp, utcnow
from table_tennis.sources import provider, betsapi_event, oddsio_event, FeedError

def collect(store, name='auto', days=0, include_quotes=True, event_id=None):
    feed=provider(name);counts=Counter();warnings=[]
    try:
        raw=[]
        for kind in ('upcoming','inplay'):
            raw.extend(feed.events(kind))
        today=datetime.now(timezone.utc).date()
        for offset in range(days):
            raw.extend(feed.events('ended',(today-timedelta(days=offset)).isoformat()))
        # Deduplicate IDs across endpoints before requesting detailed scores.
        raw=list({str(r['id']):r for r in raw}.values())
        if feed.provider=='betsapi':raw=feed.details(raw)
        parse=betsapi_event if feed.provider=='betsapi' else oddsio_event
        for native in raw:
            try:
                event=parse(native,feed.base_url+('/v1/event/view' if feed.provider=='betsapi' else '/events'))
                counts[store.upsert_event(event)]+=1
            except (ValueError,KeyError,TypeError) as exc:
                counts['rejected']+=1
                if len(warnings)<25:warnings.append('Rejected provider event '+str(native.get('id'))+': '+str(exc))
                continue
            # Backfilling results must not silently issue thousands of historical
            # odds requests. Live collection archives prices before completion.
            if include_quotes and event['status']!='finished' and (event_id is None or event_id==event['event_id']):
                try:
                    quotes,notes=feed.quotes(event)
                    warnings.extend(notes)
                    for q in quotes:store.add_quote(q);counts['quotes']+=1
                except FeedError as exc:warnings.append(str(exc))
    finally:feed.close()
    return dict(counts),sorted(set(warnings))

def import_file(store,path):
    data=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    events=data.get('events',[]);quotes=data.get('quotes',[])
    # Prevalidate all input before writing any part of an invalid export.
    events=[validate_event(e) for e in events]
    quotes=[validate_quote(q) for q in quotes]
    if not events and not quotes:raise ValueError('Export contains no events or quotes')
    if data.get('example') or any(e.get('is_example') for e in events):
        raise ValueError('Examples are excluded from the production training store')
    ids={e['event_id'] for e in events}|{e['event_id'] for e in store.events()}
    if any(q['event_id'] not in ids for q in quotes):raise ValueError('Quote references an unknown event')
    counts=Counter(store.upsert_event(e) for e in events)
    for q in quotes:store.add_quote(q)
    counts['quotes']=len(quotes)
    return dict(counts)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--provider',choices=['auto','betsapi','oddsio'],default='auto')
    p.add_argument('--days',type=int,default=7,help='History days ending today (UTC)')
    p.add_argument('--import-file',type=Path,help='Verified normalized events/quotes JSON')
    p.add_argument('--stats',action='store_true')
    p.add_argument('--no-quotes',action='store_true',help='Results/fixtures only; save API credits')
    p.add_argument('--watch',action='store_true',help='Poll and persist; Ctrl+C stops')
    p.add_argument('--auto-train',action='store_true',help='Fit when completed history changes and enough eligible matches exist')
    p.add_argument('--interval',type=int,default=60)
    args=p.parse_args()
    if not 0<=args.days<=366 or args.interval<30:p.error('Days must be 0..366; polling interval must be at least 30 seconds')
    store=TableTennisStore()
    try:
        if args.stats:
            print(json.dumps(store.stats(),indent=2));return
        if args.import_file:
            print(json.dumps(import_file(store,args.import_file),indent=2));return
        first=True;trained_signature=None
        while True:
            counts,warnings=collect(store,args.provider,args.days if first else 1,not args.no_quotes)
            print(utcnow(),json.dumps(counts),flush=True)
            for warning in warnings:print('NOTE:',warning)
            if args.auto_train:
                from table_tennis.training import train
                completed=store.events(finished_only=True)
                signature=tuple((e['event_id'],e['store_version']) for e in completed)
                if signature!=trained_signature:
                    try:
                        model=train(completed,store.quotes_by_event(),Path(__file__).resolve().parent/'data/table_tennis/model.json')
                        print('Model fitted:',model['training_matches'],'eligible matches; chronological holdout:',model['strength_holdout'])
                    except ValueError as exc:print('Training status:',exc)
                    trained_signature=signature
            first=False
            if not args.watch:break
            time.sleep(args.interval)
    except (ValueError,OSError) as exc:
        p.exit(2,str(exc)+'\n')
    except KeyboardInterrupt:print('Collection stopped; committed records retained.')

if __name__=='__main__':main()
