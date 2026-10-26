"""One entry point for refresh, predictions, saved reviews, grading and records."""
import argparse
import sys
import json
from pathlib import Path
import msp_workflow as workflow


def main(argv=None):
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='action',required=True)
    for name in ['refresh','grade','daily']:
        ap=sub.add_parser(name)
        ap.add_argument('--all',action='store_true',help='All supported sports (default)')
        if name=='refresh':ap.add_argument('--sport',choices=workflow.SPORTS)
        if name in ['grade','daily']:ap.add_argument('--no-collect',action='store_true',help='Grade available results without provider refresh')
    for name in ['run','slate']:
        ap=sub.add_parser(name)
        ap.add_argument('--sport',choices=workflow.SPORTS)
        ap.add_argument('--match',action='append',default=[])
        ap.add_argument('--date')
        ap.add_argument('--league')
        ap.add_argument('--tournament')
        ap.add_argument('--surface',choices=['hard','clay','grass','carpet'])
        ap.add_argument('--best-of',type=int,choices=[3,5])
        ap.add_argument('--file',type=Path,help='JSON matches list with sport, match, date and optional league/tournament/args')
        ap.add_argument('--props',action='store_true',help='Basketball player-prop research instead of a team pick (NBA)')
        ap.add_argument('--player',action='append',default=[],help='Player-prop filter (repeatable)')
    sub.add_parser('pending')
    ap=sub.add_parser('record');ap.add_argument('--all-time',action='store_true');ap.add_argument('--cohort',choices=['value','exploratory','high-probability'],default='value')
    for name in ['show','push']:
        ap=sub.add_parser(name)
        if name=='show':ap.add_argument('--json',action='store_true',help='Show full-precision saved JSON instead of the formatted score review')
        choice=ap.add_mutually_exclusive_group(required=True)
        choice.add_argument('--run-id');choice.add_argument('--latest',action='store_true')
    ap=sub.add_parser('cleanup');ap.add_argument('--before',required=True);ap.add_argument('--apply',action='store_true')
    ap=sub.add_parser('period');ap.add_argument('--start',required=True)
    args,extra=p.parse_known_args(argv)
    if extra and args.action not in ['run','slate']:p.error('Unrecognized arguments: '+' '.join(extra))
    try:
        if args.action in ['refresh','daily']:
            results=workflow.refresh(getattr(args,'sport',None))
            failed=any(x['exit_code'] for x in results)
            if args.action=='refresh':return 1 if failed else 0
        if args.action in ['grade','daily']:
            graded=workflow.grade_all(not args.no_collect)
            collection_failed=any(stage['exit_code'] for stage in graded['collection'])
            return 1 if collection_failed or (args.action=='daily' and failed) else 0
        if args.action in ['run','slate']:
            if args.file:
                data=json.loads(args.file.read_text(encoding='utf-8-sig'))
                matches=data.get('matches') if isinstance(data,dict) else data
                if not isinstance(matches,list) or not matches:raise ValueError('Slate needs a nonempty matches list')
                failures=[]
                for item in matches:
                    try:
                        if not isinstance(item,dict):raise ValueError('Each slate item must be an object')
                        item_args=item.get('args',[])
                        if not isinstance(item_args,list) or any(not isinstance(x,str) for x in item_args):
                            raise ValueError('Slate args must be a list of strings')
                        options={'tournament':item.get('tournament',args.tournament),'surface':item.get('surface',args.surface),'best_of':item.get('best_of',args.best_of)}
                        workflow.run(item.get('sport',args.sport),[item['match']],item.get('date',args.date),item.get('league',args.league),options,item_args+extra)
                    except (ValueError,KeyError) as exc:failures.append(str(exc));print('FAILED:',exc)
                return 1 if failures else 0
            if not args.sport:raise ValueError('--sport is required')
            workflow.run(args.sport,args.match,args.date,args.league,vars(args),extra)
            return 0
        if args.action=='pending':result=workflow.pending()
        elif args.action=='record':result=workflow.record(args.all_time, cohort=args.cohort)
        elif args.action=='show':
            result=workflow.saved_run(args.run_id)
            if not args.json and workflow.show_saved_score_review(result):return 0
        elif args.action=='push':result={'confirmed_destinations':workflow.push_saved(args.run_id)}
        elif args.action=='cleanup':result=workflow.cleanup(args.before,args.apply)
        elif args.action=='period':
            import datetime
            datetime.date.fromisoformat(args.start)
            from core.historical_storage import workflow_set_meta
            workflow_set_meta('report_start',args.start);result={'report_start':args.start,'history_preserved':True}
        print(json.dumps(result,indent=2,ensure_ascii=False))
        return 0
    except (ValueError,OSError,KeyError) as exc:
        print('FAILED:',exc);return 1


if __name__=='__main__':
    raise SystemExit(main())
