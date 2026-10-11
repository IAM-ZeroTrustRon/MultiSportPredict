"""Fit and validate Czech Liga Pro strength/H2H and optional market models."""
import argparse
import json
from pathlib import Path
from core.historical_storage import TableTennisStore
from table_tennis.training import train,make_rows
from table_tennis.poisson import losing_points_diagnostic

ROOT=Path(__file__).resolve().parent
MODEL=ROOT/'data/table_tennis/model.json'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--export',type=Path,help='Export chronological feature rows as JSON without fitting')
    p.add_argument('--diagnostic',action='store_true',help='Observed losing-point Poisson diagnostic only')
    args=p.parse_args();store=TableTennisStore()
    events=store.events(finished_only=True)
    quotes=store.quotes_by_event()
    try:
        if args.diagnostic:
            print(json.dumps(losing_points_diagnostic(events),indent=2));return
        if args.export:
            rows=make_rows(events,quotes);args.export.parent.mkdir(parents=True,exist_ok=True)
            args.export.write_text(json.dumps(rows,indent=2,allow_nan=False),encoding='utf-8')
            print(f'Exported {len(rows)} eligible rows to {args.export.resolve()}');return
        result=train(events,quotes,MODEL)
        print(json.dumps({k:result[k] for k in ('training_matches','strength_holdout','market_holdout','status')},indent=2))
        print('Model:',MODEL)
    except (ValueError,OSError) as exc:p.exit(2,str(exc)+'\n')

if __name__=='__main__':main()
