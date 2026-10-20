"""MyKBO completed-score adapter. Explicit date, slug identities and Final status required."""
import datetime as dt
import json
import re
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup


def parse_final(html, url, wanted_date):
    from run_mlb import KBO_SLUG_TEAMS
    match=re.search(r'/games/(\d+)-([a-z]+)-vs-([a-z]+)-(\d{8})(?:$|[?#])',url,re.I)
    if not match or match[4]!=wanted_date.replace('-',''):
        raise ValueError('KBO result URL date/identity not confirmed')
    away,home=KBO_SLUG_TEAMS.get(match[2].lower()),KBO_SLUG_TEAMS.get(match[3].lower())
    if not home or not away:raise ValueError('Unknown KBO team slug')
    soup=BeautifulSoup(html,'html.parser')
    final=soup.find(string=lambda t:t and t.strip()=='Final')
    if final is None:raise ValueError('KBO game has no confirmed Final status')
    board=final.parent.parent.parent
    scores=board.select_one('[aria-label]')
    if scores is None:raise ValueError('Missing KBO scoreboard')
    values=[s.get_text(strip=True) for s in scores.find_all('span',recursive=False)]
    if len(values)!=3 or values[1]!=':' or not values[0].isdigit() or not values[2].isdigit():
        raise ValueError('KBO scoreboard format changed')
    title=board.get_text(' ',strip=True).lower()
    if away.lower() not in title or home.lower() not in title:raise ValueError('KBO scoreboard identities differ from URL')
    return {'date':wanted_date,'home_team':home,'away_team':away,'home_score':int(values[2]),'away_score':int(values[0]),'game_id':match[1],'source':url}


def fetch_results(start,end):
    from grade_predictions import normalise_team
    day=dt.date.fromisoformat(start);last=dt.date.fromisoformat(end);out={};evidence=[]
    while day<=last:
        stamp=day.isoformat()
        response=requests.get('https://mykbostats.com/games',params={'start':stamp},timeout=25);response.raise_for_status()
        soup=BeautifulSoup(response.text,'html.parser')
        urls={urljoin('https://mykbostats.com',a['href']) for a in soup.select('a[id^="game-line-"][href]') if stamp.replace('-','') in a['href']}
        grouped={}
        for url in sorted(urls):
            response=requests.get(url,timeout=25);response.raise_for_status()
            try:game=parse_final(response.text,url,stamp)
            except ValueError:continue
            key=(stamp,normalise_team(game['home_team'],'kbo'),normalise_team(game['away_team'],'kbo'))
            grouped.setdefault(key,[]).append(game)
        # A date/team key cannot distinguish doubleheaders. Leave ambiguous rows unresolved.
        for key,games in grouped.items():
            if len(games)==1:
                out[key]=(games[0]['home_score'],games[0]['away_score']);evidence.extend(games)
        day+=dt.timedelta(days=1)
    folder=Path(__file__).resolve().parent/'output/workflow/result_evidence';folder.mkdir(parents=True,exist_ok=True)
    (folder/f'kbo_{start}_{end}.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    return out
