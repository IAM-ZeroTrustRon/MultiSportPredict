"""Grade saved Czech forecasts against corrected final results, one-unit research P/L."""
import argparse
import json
import math
from core.historical_storage import TableTennisStore
from table_tennis.markets import outcome
from table_tennis.contracts import timestamp

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

def main():
    p=argparse.ArgumentParser(description=__doc__);p.parse_args()
    print(json.dumps(grade(TableTennisStore()),indent=2))

if __name__=='__main__':main()
