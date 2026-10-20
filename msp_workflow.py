"""Shared workflow orchestration. Models retain their own validation and settlement rules."""
import datetime as dt
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path
from zoneinfo import ZoneInfo
from contextlib import contextmanager, closing

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'multisport_history.db'
PYTHON = ROOT / 'venv/Scripts/python.exe'
ET = ZoneInfo('America/New_York')
SPORTS = ('mlb','kbo','soccer','tennis','tennis-research','nfl','ncaaf','basketball','table-tennis')


def today():
    return dt.datetime.now(ET).date().isoformat()


@contextmanager
def read_db(path=DB):
    conn=sqlite3.connect(f'file:{Path(path).as_posix()}?mode=ro',uri=True,timeout=30)
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA query_only=ON')
    try:
        yield conn
    finally:
        conn.close()


def refresh_plan(sport=None, date=None):
    date=dt.date.fromisoformat(date or today());y=date.year
    days=[(date-dt.timedelta(days=i)).isoformat() for i in reversed(range(8))]
    tasks=[
        ('mlb',['ingest_all_sports.py','--only','mlb','mlb-probables','mlb-lineups','mlb-players']),
        ('kbo',['ingest_all_sports.py','--only','kbo']),
        ('soccer',['ingest_soccer_espn.py','--all','--fixtures']),
        ('soccer',['ingest_soccer_fd.py','--countries','england','germany','spain','france','italy']),
        ('tennis',['ingest_tennis.py','--years',str(y-1),str(y),'--tours','atp','wta']),
        ('nfl',['ingest_nfl_schedule.py','--season',str(y)]),
        ('nfl',['ingest_nfl.py','--season',str(y)]),
        ('ncaaf',['ingest_ncaaf.py','--dates',*days]),
        ('ncaaf',['ingest_ncaaf_model.py','--seasons',str(y-1),str(y)]),
        ('basketball',['ingest_basketball_espn.py','--leagues','NBA','WNBA','NCAAB','NCAAW','--seasons',str(y-1),str(y),str(y+1)]),
        ('basketball',['ingest_basketball_official.py','--leagues','KBL','NZNBL','BBL']),
        ('basketball',['ingest_all_sports.py','--only','euroleague']),
        ('table-tennis',['ingest_table_tennis_public.py','--recent','--max-events','100','--auto-train']),
    ]
    return [command for group,command in tasks if not sport or group==sport or sport=='tennis-research' and group=='tennis']


def execute(command, folder, env=None, timeout=1200):
    if not PYTHON.is_file():raise ValueError('Missing venv/Scripts/python.exe; refusing to fall back to another interpreter')
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    logfile=folder/(Path(command[0]).stem+'_'+uuid.uuid4().hex[:8]+'.log')
    child_env={**os.environ,'PYTHONIOENCODING':'utf-8','PYTHONUNBUFFERED':'1',**(env or {})}
    with logfile.open('w',encoding='utf-8') as handle:
        try:
            result=subprocess.run([str(PYTHON),'-u',*command],cwd=ROOT,env=child_env,stdout=handle,stderr=subprocess.STDOUT,timeout=timeout)
            code=result.returncode
        except subprocess.TimeoutExpired:
            code=124;handle.write('\n[TIMEOUT] Stage did not finish; inspect retained data freshness.\n')
    print(f"{'OK' if code==0 else 'FAILED'}: {command[0]} (exit {code}); {logfile.relative_to(ROOT)}",flush=True)
    return {'command':command,'exit_code':code,'log':str(logfile)}


def refresh(sport=None):
    folder=ROOT/'output/workflow'/('refresh_'+dt.datetime.now().strftime('%Y%m%d_%H%M%S'))
    results=[execute(command,folder) for command in refresh_plan(sport)]
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'summary.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    return results


def repair_nfl_dates(path=DB):
    """Recover only a unique pregame candidate within seven days of the saved forecast."""
    import grade_predictions as g
    from core.historical_storage import workflow_repair_dates
    schedule=json.loads((ROOT/'data/nfl_schedule.json').read_text(encoding='utf-8-sig')).get('games',[])
    repairs=[];unresolved=[]
    with read_db(path) as conn:
        rows=list(conn.execute("SELECT * FROM predictions WHERE sport='nfl' AND result_outcome IS NULL"))
    for row in rows:
        if g.is_excluded_tier(row['recommendation']):continue
        try:
            raw=json.loads(row['raw_json'] or '{}')
            stamp=dt.datetime.fromisoformat(row['timestamp'])
            if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=ET)
            saved=stamp.astimezone(ET).date()
            fixture=raw.get('fixture') or {}
            event_id=fixture.get('game_id')
            candidates=[]
            for game in schedule:
                if game.get('season')!=saved.year:continue
                if {g.normalise_team(game['home_team'],'nfl'),g.normalise_team(game['away_team'],'nfl')}!={g.normalise_team(row['home_team'],'nfl'),g.normalise_team(row['away_team'],'nfl')}:continue
                # Reversed stored home/away needs its own validated market-side repair.
                if g.normalise_team(game['home_team'],'nfl')!=g.normalise_team(row['home_team'],'nfl'):continue
                day=dt.date.fromisoformat(game['date'])
                if event_id:
                    if str(game.get('game_id'))!=str(event_id):continue
                elif not 0 <= (day-saved).days <= 7:continue
                kickoff=game.get('start_time')
                if kickoff and stamp>=dt.datetime.fromisoformat(kickoff.replace('Z','+00:00')):continue
                candidates.append(game)
            if len(candidates)!=1:
                unresolved.append({'id':row['id'],'reason':f'{len(candidates)} eligible event candidates; no date inferred'})
                continue
            game=candidates[0]
            if not game.get('game_id'):continue
            repairs.append({'id':row['id'],'old_date':row['game_date'],'date':game['date'],'fixture':game,
                            'basis':'Same home/away, season and unique event ID, or one upcoming fixture within seven days of saved forecast. Naive legacy timestamps interpreted in project timezone America/New_York.',
                            'source':'data/nfl_schedule.json (ESPN feed)'})
        except (ValueError,TypeError,KeyError) as exc:
            unresolved.append({'id':row['id'],'reason':type(exc).__name__})
    workflow_repair_dates(repairs,path)
    return {'verified_identities':len(repairs),'unresolved':unresolved}


def pending(path=DB):
    import grade_predictions as g
    with read_db(path) as conn:
        active,dupes=g.split_duplicates(conn,g.ungraded(conn))
        ordinary=[{'id':r['id'],'sport':r['sport'],'date':r['game_date'],'home':r['home_team'],'away':r['away_team'],'market':r['market_type'],'note':r['grade_note']} for r in active]
        tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        tt=[dict(r) for r in conn.execute("SELECT r.run_id,r.event_id,e.start_utc,e.status FROM tt_runs r JOIN tt_events e ON e.event_id=r.event_id WHERE e.status!='finished'")] if 'tt_runs' in tables else []
    return {'ordinary':ordinary,'excluded_duplicates':[r['id'] for r in dupes],'table_tennis':tt}


def grade_all(collect_table_tennis=True):
    from core.historical_storage import workflow_backup, TableTennisStore
    import grade_predictions as g
    folder=ROOT/'output/workflow'/('grade_'+dt.datetime.now().strftime('%Y%m%d_%H%M%S'))
    print('Backup:',workflow_backup(folder),flush=True)
    repair=repair_nfl_dates()
    print('NFL fixture identity repair:',json.dumps(repair),flush=True)
    with closing(sqlite3.connect(DB,timeout=30)) as conn:
        conn.row_factory=sqlite3.Row
        g.ensure_schema(conn)
        g.cmd_auto(conn,None,10000)
        conn.commit()
    stages=[]
    if collect_table_tennis:
        # Collect before grading. Cross-provider finals remain separate unless identity is proven.
        if os.environ.get('BETSAPI_KEY') or os.environ.get('ODDS_API_IO_KEY'):
            stages.append(execute(['ingest_table_tennis.py','--days','14','--no-quotes'],folder,timeout=240))
        else:
            stages.append(execute(['ingest_table_tennis_public.py','--recent','--max-events','100','--auto-train'],folder,timeout=240))
    from grade_table_tennis import grade
    result=grade(TableTennisStore(DB))
    state=pending()
    output={'repair':repair,'table_tennis':result,'collection':stages,'pending':state}
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'summary.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(f"Remaining: {len(state['ordinary'])} ordinary selections, {len(state['table_tennis'])} table-tennis runs; no Discord sent.")
    return output


def record(all_time=False):
    import grade_predictions as g
    with read_db() as conn:
        tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        start=None
        if not all_time and 'workflow_meta' in tables:
            found=conn.execute("SELECT value FROM workflow_meta WHERE key='report_start'").fetchone()
            start=json.loads(found[0]) if found else None
        rows=list(conn.execute('SELECT * FROM predictions'+(' WHERE game_date>=?' if start else ''),(start,) if start else ()))
        active,dupes=g.split_duplicates(conn,[r for r in rows if r['result_outcome'] is None and not g.is_excluded_tier(r['recommendation'])])
        settled,_=g.newest_per_fixture([r for r in rows if r['result_outcome'] is not None])
        bets=[r for r in settled if not g.is_excluded_tier(r['recommendation'])]
        counts=g._tally(bets)
        # Unknown-price historical unit calculations cannot substantiate realised ROI.
        counts.pop('units',None);counts.pop('roi',None)
        recorded=[]
        price_counts={'recorded':0,'default_or_unknown':0}
        for r in bets:
            try:raw=json.loads(r['raw_json'] or '{}')
            except ValueError:raw={}
            priced=isinstance(raw,dict) and raw.get('_settled_at_recorded_price')
            price_counts['recorded' if priced else 'default_or_unknown']+=1
            if priced:recorded.append(r)
        tt_count=conn.execute('SELECT count(*) FROM tt_grades').fetchone()[0] if 'tt_grades' in tables else 0
    priced_stats=g._tally(recorded)
    priced_stats['roi']=priced_stats['units']/priced_stats['n']*100 if priced_stats['n'] else None
    priced_stats['stake_basis']='One unit risked per recorded-price selection, including pushes; simulated model record, not confirmed wagers.'
    return {'period_start':start or 'all time','ordinary_decisions':counts,'recorded_price_model_decisions':priced_stats,'settlement_prices':price_counts,
            'awaiting_results':len(active),'excluded_duplicate_rows':len(dupes),'table_tennis_historical_research_grades':tt_count,
            'note':'New-period view does not erase settled history. Research selections and ordinary decisions are not combined as independent bets.'}


def cleanup(before, apply=False):
    import grade_predictions as g
    from core.historical_storage import workflow_cleanup
    dt.date.fromisoformat(before)
    if before>today():raise ValueError('Cleanup cutoff cannot be in the future')
    ids=[];runs=[]
    with read_db() as conn:
        for r in conn.execute('SELECT * FROM predictions WHERE result_outcome IS NULL AND game_date<?',(before,)):
            if not g.is_excluded_tier(r['recommendation']):ids.append(r['id'])
        for r in conn.execute("SELECT r.run_id,e.start_utc FROM tt_runs r JOIN tt_events e ON e.event_id=r.event_id WHERE e.status!='finished' AND NOT EXISTS (SELECT 1 FROM tt_grades g WHERE g.run_id=r.run_id)"):
            if dt.datetime.fromisoformat(r['start_utc']).astimezone(ET).date().isoformat()<before:runs.append(r['run_id'])
    if not apply:return {'preview_only':True,'before':before,'prediction_ids':ids,'table_tennis_run_ids':runs}
    return workflow_cleanup(ids,runs,before,ROOT/'output/backups/workflow')


def run_command(sport, matches, date, league, options, extra):
    args=[]
    for match in matches:args+=['--match',match]
    date=date or today()
    if sport=='nfl':return ['run_nfl.py',*args,'--date',date,'--odds',*extra]
    if sport in ('mlb','kbo'):return ['run_mlb.py','--league',sport.upper(),*(args or ['--today']),'--date',date,'--odds','--no-discord',*extra]
    if sport=='ncaaf':return ['run_ncaaf.py',*args,'--date',date,'--odds',*extra]
    if sport=='basketball':
        if not league:raise ValueError('Basketball requires --league (for example KBL)')
        if league.upper() in ('NBL','EUROLEAGUE'):
            if len(matches)!=1:raise ValueError('International basketball needs one matchup per slate item')
            a,b=split_match(matches[0]);return ['run_basketball.py','--home',a,'--away',b,'--league',league,'--game-date',date,'--store-to-db',*extra]
        return ['run_basketball.py',*args,'--league',league,'--date',date,'--odds',*extra]
    if sport=='soccer':
        if len(matches)!=1 or not league:raise ValueError('Soccer requires one matchup and --league per slate item')
        a,b=split_match(matches[0]);return ['universal_runner.py','--sport','soccer','--home',a,'--away',b,'--league',league,'--game-date',date,'--live-odds','--store-to-db',*extra]
    if sport=='tennis-research':
        if len(matches)!=1:raise ValueError('Use one research match per slate item')
        return ['run_tennis_full.py',*args,'--refresh',*extra]
    if sport=='tennis':
        if not matches or not options.get('tournament'):raise ValueError('Tennis requires --match and --tournament')
        return ['run_tennis.py',*args,'--game-date',date,'--tournament',options['tournament'],'--surface',options.get('surface') or 'hard','--best-of',str(options.get('best_of') or 3),*extra]
    if sport=='table-tennis':return ['run_table_tennis.py',*args,'--date',date,*extra]
    raise ValueError('Unsupported sport')


def split_match(text):
    parts=text.split(' vs ')
    if len(parts)!=2 or not all(x.strip() for x in parts):raise ValueError('Use full names separated by " vs "')
    return tuple(x.strip() for x in parts)


def run(sport,matches,date,league,options,extra):
    from core.historical_storage import workflow_save_run
    if not isinstance(extra,list) or any(not isinstance(x,str) for x in extra):
        raise ValueError('Extra runner arguments must be a list of strings')
    if any(x.split('=',1)[0] in ('--push','--push-all','--push-discord','--no-discord','--no-fixture-check','--allow-placeholder') for x in extra):
        raise ValueError('Use the separate push command; fixture guards cannot be bypassed through this interface')
    if date and dt.date.fromisoformat(date)<dt.date.fromisoformat(today()):
        raise ValueError('New workflow forecasts require today or a future fixture date')
    command=run_command(sport,matches,date,league,options,extra)
    ident='msp_'+uuid.uuid4().hex
    folder=ROOT/'output/workflow/runs'/ident
    stage=execute(command,folder,{'MSP_RUN_ID':ident})
    with read_db() as conn:
        predictions=[]
        for r in conn.execute('SELECT * FROM predictions WHERE raw_json LIKE ?',('%'+ident+'%',)):
            raw=json.loads(r['raw_json'])
            if isinstance(raw,dict) and raw.get('_workflow_run_id')==ident:predictions.append(dict(r))
        tt=[r[0] for r in conn.execute('SELECT run_id FROM tt_runs WHERE payload LIKE ?',('%'+ident+'%',))]
    review=None
    if sport=='tennis-research' and stage['exit_code']==0:
        p=ROOT/'data/tennis/full_review.json'
        if p.exists() and p.stat().st_mtime>=Path(stage['log']).stat().st_ctime:review=json.loads(p.read_text(encoding='utf-8'))
    success=stage['exit_code']==0 and bool(predictions or tt or review)
    payload={'command':command,'stage':stage,'predictions':predictions,'table_tennis_runs':tt,'research':review}
    workflow_save_run(ident,sport,'saved' if success else 'failed',payload)
    (folder/'snapshot.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
    print('RUN_ID='+ident)
    print(Path(stage['log']).read_text(encoding='utf-8'))
    if not success:raise ValueError('Runner saved no forecast, or failed. Read the stage log; no successful run claimed.')
    return ident


def saved_run(ident=None):
    with read_db() as conn:
        if ident is None:
            latest=conn.execute("SELECT run_id FROM workflow_runs WHERE status='saved' ORDER BY created_utc DESC LIMIT 1").fetchone()
            if latest is None:raise ValueError("No successful saved workflow run yet")
            ident=latest[0]
        row=conn.execute('SELECT * FROM workflow_runs WHERE run_id=?',(ident,)).fetchone()
    if row is None:raise ValueError('Unknown workflow run ID')
    result=dict(row);result['payload']=json.loads(result['payload']);return result


def push_saved(ident=None):
    from core.historical_storage import workflow_delivery
    from discord_integration import push_prediction_to_all
    saved=saved_run(ident)
    if saved['status']!='saved':raise ValueError('Cannot push a failed run')
    ident=saved['run_id']
    payload=saved['payload']
    rows=payload['predictions']
    parts=1
    if payload['table_tennis_runs']:
        from table_tennis.report import push
        from core.historical_storage import TableTennisStore
        parts=len(payload['table_tennis_runs'])
        delivered=[push(TableTennisStore(DB).run(t),False) for t in payload['table_tennis_runs']]
        count=min(delivered) if delivered else 0
    elif payload['research']:
        # Research's own renderer sends the captured snapshot, never reruns the model.
        from run_tennis_full import push
        try:push(payload['research']);count=1
        except Exception:
            workflow_delivery(ident,'failed',{'kind':'research'});raise
    else:
        # Render the captured full forecast so prices, projections and EV are preserved.
        fixtures={}
        for row in rows:
            raw=json.loads(row['raw_json'])
            key=(row['sport'],row['league'],row['game_date'],row['home_team'],row['away_team'])
            fixtures.setdefault(key,raw)
        parts=len(fixtures)
        delivered=[push_prediction_to_all(key[0],raw,dry_run=False) for key,raw in fixtures.items()]
        count=min(delivered) if delivered else 0
    workflow_delivery(ident,'delivered_to_at_least_one_destination' if count else 'no_delivery',{'minimum_successful_destinations_per_part':count,'parts':parts})
    if not count:raise ValueError('No confirmed Discord delivery')
    return count
