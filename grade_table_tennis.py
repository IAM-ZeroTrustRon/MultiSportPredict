"""Grade saved Czech forecasts against corrected final results, one-unit research P/L."""
import argparse
import json
import math
from core.historical_storage import TableTennisStore
from table_tennis.markets import outcome
from table_tennis.contracts import timestamp, validate_event, utcnow, source_url
from pathlib import Path
import sqlite3

def grade(store):
    settled=[];skipped=0;cohorts={};counted=set()
    for run in store.runs():
        event=store.event(run['event']['event_id'])
        if event['status']!='finished':skipped+=1;continue
        # Do not score predictions created after the match's known completion;
        # runs on actual live states are reported separately by phase.
        if event.get('end_utc') and timestamp(run['created_utc'])>=timestamp(event['end_utc']):
            skipped+=1;continue
        # Evaluate unpriced forecasts too, once per event using its earliest
        # saved pre-match run. Reruns/alternative selections must not inflate n.
        if run['event']['status']=='scheduled' and timestamp(run['created_utc'])<timestamp(event['start_utc']) and event['event_id'] not in counted:
            counted.add(event['event_id'])
            won=int(sum(a>b for a,b in event['game_scores'])==3)
            p=max(1e-9,min(1-1e-9,run['forecast']['p_match_a']))
            actual_points=sum(a+b for a,b in event['game_scores'])
            group=cohorts.setdefault(run['strategy'],[])
            group.append(dict(brier=(p-won)**2,log_loss=-won*math.log(p)-(1-won)*math.log(1-p),
                point_absolute_error=abs(run['forecast']['expected_points']-actual_points)))
        for index,row in enumerate(run['priced_markets']):
            result=outcome(event,row['market'],row['line'],row['selection_side'])
            profit=row['price']-1 if result=='win' else -1 if result=='loss' else 0.
            record=dict(run_id=run['run_id'],event_id=event['event_id'],market=row['market'],
                selection=row['selection'],outcome=result,research_profit=profit,
                probability=row['probability'],phase=run['event']['status'],
                label='Hypothetical one-unit return; no bet was recorded')
            store.save_grade(run['run_id'],str(index),event['store_version'],record)
            settled.append(record)
    metrics={name:dict(matches=len(rows),**{k:sum(r[k] for r in rows)/len(rows) for k in ('brier','log_loss','point_absolute_error')}) for name,rows in cohorts.items()}
    return dict(graded_selections=len(settled),unfinished_or_invalid_runs=skipped,
                research_profit=sum(x['research_profit'] for x in settled),
                prospective_prematch_metrics=metrics,
                warning='Correlated selections/reruns are not independent bets; no strategy ROI claim',
                selections=settled)

def manual_final(store, run_id, scores, result_source, end_utc=None):
    """Use the saved event identity and A/B order; never merge provider IDs."""
    run=store.run(run_id)
    event=dict(store.event(run['event']['event_id']))
    event.pop('store_version',None)
    event.update(status='finished',game_scores=scores,current_points=[0,0],retrieved_utc=utcnow(),
                 result_source_url=source_url(result_source),
                 result_verification='User-confirmed per-game points in saved player A/B order')
    if end_utc:event['end_utc']=end_utc
    return validate_event(event)


def import_final_file(store, path):
    data=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if data.get('example') or data.get('quotes'):
        raise ValueError('Final-result file must contain verified final events only, no examples or quotes')
    events=[validate_event(e) for e in data.get('events',[])]
    if not events:raise ValueError('Final-result file has no events')
    for event in events:
        if event['status']!='finished' or event.get('is_example'):
            raise ValueError('Only confirmed finished matches can be imported')
        old=store.event(event['event_id'])
        if any(event[k]!=old[k] for k in ('player_a_id','player_b_id','start_utc')):
            raise ValueError('Result identity/start differs from the saved fixture; retain its original provider IDs and player order')
    return [store.upsert_event(event) for event in events]


def backup_database(store):
    # SQLite backup includes committed WAL state, unlike copying a live DB file.
    target=store.path.with_name(store.path.name+'.bak-tt-grade-'+utcnow().replace(':','').replace('.',''))
    with sqlite3.connect(str(store.path)) as original:
        with sqlite3.connect(str(target)) as backup:
            original.backup(backup)
    return target


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-id',help='Saved tt_ run to register a confirmed final result for')
    p.add_argument('--scores',nargs='+',help='Per-game A-B points, e.g. 11-9 8-11 11-7 11-6; always saved report order')
    p.add_argument('--source-url',help='HTTPS page where the final scores were confirmed')
    p.add_argument('--end-utc',help='Actual confirmed finish time with timezone, optional')
    p.add_argument('--result-file',type=Path,default=Path(__file__).resolve().parent/'data/table_tennis/verified_final_result.json')
    p.add_argument('--import-file',type=Path,help='Import a previously prepared verified final-result JSON')
    p.add_argument('--pending',action='store_true',help='List saved runs without a finished result; read only')
    args=p.parse_args()
    if args.import_file and args.run_id:p.error('Use --import-file OR --run-id')
    if args.run_id and (not args.scores or not args.source_url):p.error('--run-id requires --scores and --source-url')
    if not args.run_id and any((args.scores,args.source_url,args.end_utc)):p.error('Result details require --run-id')
    if args.pending and (args.run_id or args.import_file):p.error('--pending cannot import results')
    store=TableTennisStore()
    try:
        if args.pending:
            for run in store.runs():
                event=store.event(run['event']['event_id'])
                if event['status']!='finished':
                    print(f"{run['run_id']} | {event['event_id']} | A: {event['player_a']} | B: {event['player_b']} | {event['status']}")
            return
        if args.run_id:
            scores=[]
            for token in args.scores:
                import re
                match=re.fullmatch(r'(\d+)-(\d+)',token)
                if not match:raise ValueError('Scores must be A-B integer points, e.g. 11-9')
                scores.append([int(x) for x in match.groups()])
            event=manual_final(store,args.run_id,scores,args.source_url,args.end_utc)
            args.result_file.parent.mkdir(parents=True,exist_ok=True)
            args.result_file.write_text(json.dumps({'events':[event]},indent=2)+'\n',encoding='utf-8')
            args.import_file=args.result_file
        print('Database backup:',backup_database(store))
        if args.import_file:
            print('Final results imported:',import_final_file(store,args.import_file))
        print(json.dumps(grade(store),indent=2))
    except (ValueError,OSError) as exc:p.exit(2,str(exc)+'\n')

if __name__=='__main__':main()
