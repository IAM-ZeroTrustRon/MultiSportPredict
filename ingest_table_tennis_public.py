"""Free Czech Liga Pro browser results to canonical DB plus deduplicated CSV."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import time
from core.historical_storage import TableTennisStore
from table_tennis.contracts import utcnow,validate_event
from table_tennis.public_results import collect_public,parse_match

ROOT=Path(__file__).resolve().parent

def export_csv(store,path):
    fields=['event_id','provider','start_utc','player_a_id','player_a','player_b_id','player_b',
            'games_a','games_b','points_a','points_b','game_scores','source_url','retrieved_utc']
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    events=store.events(finished_only=True)
    with temporary.open('w',newline='',encoding='utf-8-sig') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader()
        for e in events:
            e=validate_event(e);games=e['game_scores']
            row={f:e[f] for f in fields if f in e}
            row.update(games_a=sum(a>b for a,b in games),games_b=sum(b>a for a,b in games),
                points_a=sum(a for a,b in games),points_b=sum(b for a,b in games),game_scores=json.dumps(games))
            writer.writerow(row)
    temporary.replace(path)
    return len(events)

def archive(event,raw):
    folder=ROOT/'data/table_tennis/public_raw';folder.mkdir(parents=True,exist_ok=True)
    text=json.dumps(raw,sort_keys=True,ensure_ascii=False,allow_nan=False)
    key=hashlib.sha256(text.encode()).hexdigest()
    (folder/(key+'.json')).write_text(text,encoding='utf-8')

def import_snapshot(store,path):
    data=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if isinstance(data,dict) and data.get('example'):raise ValueError('Example snapshots cannot enter training history')
    snapshots=data if isinstance(data,list) else [data]
    events=[parse_match(raw) for raw in snapshots]
    if not events:raise ValueError('No match snapshots supplied')
    counts={'inserted':0,'corrected':0,'duplicate':0,'rejected':0}
    for e,raw in zip(events,snapshots):counts[store.upsert_event(e)]+=1;archive(e,raw)
    return counts

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--days',type=int,default=1,help='UTC schedule days, including today')
    p.add_argument('--max-events',type=int,default=100,help='Bound browser requests per collection cycle')
    p.add_argument('--recent',action='store_true',help='Use league recent results directly; skip unavailable date pages')
    p.add_argument('--match-url',action='append',help='Collect a specific completed Sofascore match; repeatable')
    p.add_argument('--snapshot-file',type=Path,help='Import verified public DOM snapshot JSON if browser is inaccessible')
    p.add_argument('--csv',type=Path,default=ROOT/'data/table_tennis/results.csv')
    p.add_argument('--export-only',action='store_true',help='Export existing completed DB results without browser access')
    p.add_argument('--headed',action='store_true',help='Show browser; headless is default')
    p.add_argument('--watch',action='store_true',help='Keep terminal open; Ctrl+C stops, no Windows scheduled task created')
    p.add_argument('--interval',type=int,default=1800,help='Watch interval in seconds; default 30 minutes')
    p.add_argument('--auto-train',action='store_true')
    args=p.parse_args()
    if not 1<=args.days<=90 or not 1<=args.max_events<=2000 or args.interval<300:
        p.error('days must be 1..90, max-events 1..2000, interval at least 300 seconds')
    if args.snapshot_file and args.match_url:p.error('Use either --snapshot-file or --match-url')
    if args.watch and (args.snapshot_file or args.export_only):p.error('--watch needs browser collection')
    print('CZECH LIGA PRO | Starting results collector',flush=True)
    print('Mode:', 'watch' if args.watch else 'one collection', '| Ctrl+C stops',flush=True)
    store=TableTennisStore()
    if args.export_only:
        print('CSV rows:',export_csv(store,args.csv));return
    try:
        first=True
        while True:
            try:
                if args.snapshot_file:counts=import_snapshot(store,args.snapshot_file);notes=[]
                else:counts,notes=collect_public(store,args.days if first else 1,args.max_events,not args.headed,args.match_url,archive,args.recent,on_progress=lambda message: print(message,flush=True))
                print(utcnow(),json.dumps(counts),flush=True)
                for note in notes:print('NOTE:',note,flush=True)
                print('CSV:',args.csv,'| rows:',export_csv(store,args.csv),flush=True)
                if args.auto_train and (first or counts['inserted'] or counts['corrected']):
                    from table_tennis.training import train
                    try:
                        model=train(store.events(finished_only=True),store.quotes_by_event(),ROOT/'data/table_tennis/model.json')
                        print('Model fitted:',model['training_matches'],'eligible matches',flush=True)
                    except ValueError as exc:print('Training status:',exc,flush=True)
            except (ValueError,OSError) as exc:
                if not args.watch:p.exit(2,str(exc)+'\n')
                print('Collection failed; retained previous results. Retry next cycle:',exc,flush=True)
            first=False
            if not args.watch:break
            # Interruptible bounded sleeps keep stop/resume responsive.
            print(f'Waiting {args.interval} seconds before the next collection. Ctrl+C stops.',flush=True)
            end=time.monotonic()+args.interval
            while time.monotonic()<end:time.sleep(max(0,min(30,end-time.monotonic())))
    except KeyboardInterrupt:print('Stopped; saved results retained.')

if __name__=='__main__':main()
