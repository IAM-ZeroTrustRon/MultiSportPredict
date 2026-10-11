"""Privately configure a BetsAPI token after verifying real Czech result access."""
import argparse
from datetime import datetime,timedelta,timezone
from getpass import getpass,GetPassWarning
from pathlib import Path
import warnings
from dotenv import dotenv_values,set_key
from table_tennis.sources import BetsApiAdapter,betsapi_event,FeedError

ROOT=Path(__file__).resolve().parent

def verify_history(key):
    if not key or any(c.isspace() for c in key):raise ValueError('Enter the actual BetsAPI token, without spaces')
    feed=BetsApiAdapter(archive=False);feed.key=key
    try:
        for days in (1,2,3):
            day=(datetime.now(timezone.utc)-timedelta(days=days)).strftime('%Y%m%d')
            data=feed.get('/v3/events/ended',sport_id=92,league_id='22742',day=day,page=1)
            rows=data.get('results')
            if not isinstance(rows,list):raise FeedError('Provider returned an invalid result list')
            for native in feed.details(rows[:10]):
                try:e=betsapi_event(native,'https://api.b365api.com/v1/event/view')
                except (ValueError,KeyError,TypeError):continue
                if e['status']=='finished':
                    return dict(status='VERIFIED',league=e['league'],completed_games=len(e['game_scores']),
                                event_id=e['event_id'],start_utc=e['start_utc'])
        raise FeedError('No complete legal Czech Liga Pro game scores verified. Ask BetsAPI support to check Events and event/view coverage; key was not saved.')
    finally:feed.close()

def configure(key,path=ROOT/'.env'):
    existing=dotenv_values(path) if path.exists() else {}
    if key==existing.get('ODDS_API_KEY'):
        raise ValueError('That is your existing The Odds API key. Obtain the separate BetsAPI token; no settings changed.')
    result=verify_history(key)
    # dotenv updates just this entry and preserves the user's other sport keys.
    set_key(str(path),'BETSAPI_KEY',key,quote_mode='always')
    text=path.read_text(encoding='utf-8')
    path.write_bytes(text.replace('\r\n','\n').replace('\n','\r\n').encode('utf-8'))
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Verify stored token without changing .env')
    args=parser.parse_args()
    try:
        if args.check:
            key=dotenv_values(ROOT/'.env').get('BETSAPI_KEY')
            if not key:raise ValueError('BETSAPI_KEY is absent. Run configure_table_tennis.py after obtaining your BetsAPI token.')
            result=verify_history(key)
        else:
            print('Use a BetsAPI token with Czech Liga Pro Events history and event/view point-score access.')
            with warnings.catch_warnings():
                warnings.simplefilter('error',GetPassWarning)
                key=getpass('BetsAPI token (hidden): ').strip()
            result=configure(key)
            print('Saved BETSAPI_KEY to .env. Existing ODDS_API_KEY preserved.')
        print('Verified:',result['league'],'| completed game point scores:',result['completed_games'])
        print('Next (Git Bash): venv/Scripts/python.exe ingest_table_tennis.py --provider betsapi --days 90 --no-quotes --auto-train')
    except GetPassWarning:
        parser.exit(2,'Hidden input unavailable. In Git Bash run: winpty venv/Scripts/python.exe configure_table_tennis.py\n')
    except ValueError as exc:
        # The feed explicitly sanitizes failures; local validation never quotes
        # the submitted token. Preserve its actionable entitlement/HTTP reason.
        parser.exit(2,str(exc)+'\n')
    except (OSError,EOFError):
        parser.exit(2,'Setup could not complete; token omitted. Check terminal input and .env write access.\n')

if __name__=='__main__':main()
