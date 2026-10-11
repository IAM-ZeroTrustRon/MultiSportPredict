"""Documented REST adapters with strict league filters and sanitized archives.

The providers are deliberately separate from The Odds API used by other sports.
Unknown table-tennis spread units are rejected rather than guessed.
"""
import hashlib
import json
import os
import re
import time
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import requests
from dotenv import load_dotenv
from .contracts import LEAGUE, scope, timestamp, utcnow, validate_event, validate_quote, legal_terminal,normalized_name

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

def sanitize(value):
    if isinstance(value, dict):
        return {k: ('[REDACTED]' if any(x in k.lower() for x in ('token','password','apikey','api_key','authorization','cookie')) else sanitize(v)) for k,v in value.items()}
    if isinstance(value,list):return [sanitize(v) for v in value]
    if isinstance(value,str) and value.startswith(('https://','wss://')):
        s=urlsplit(value)
        return urlunsplit((s.scheme,s.hostname or '',s.path,urlencode([(k,'[REDACTED]' if any(x in k.lower() for x in ('key','token','auth','password')) else v) for k,v in parse_qsl(s.query)]),''))
    return value

class FeedError(ValueError):
    pass

class JsonClient:
    def __init__(self, provider, key_name, base_url, session=None, archive=True):
        self.provider=provider;self.key_name=key_name;self.key=os.getenv(key_name)
        self.base_url=base_url;self.session=session or requests.Session()
        self.archive=archive
        self.last_request=0.

    def close(self):self.session.close()

    def get(self, path, **params):
        if not self.key:
            raise FeedError(f'Add {self.key_name} to C:/MultiSportPredict/.env; the existing ODDS_API_KEY belongs to a different provider')
        # Moderate polling avoids bursts during history backfill; retries are bounded.
        delay=0.25-(time.monotonic()-self.last_request)
        if delay>0:time.sleep(delay)
        auth={'token':self.key} if self.provider=='betsapi' else {'apiKey':self.key}
        url=self.base_url+path
        for attempt in range(3):
            try:
                response=self.session.get(url,params={**params,**auth},timeout=(10,30))
                self.last_request=time.monotonic()
            except requests.RequestException:
                raise FeedError(f'{self.provider}: connection failed; credentials and request URLs omitted') from None
            if response.status_code in (429,500,502,503,504) and attempt<2:
                time.sleep(min(4,2**attempt));continue
            if response.status_code!=200:
                raise FeedError(f'{self.provider}: HTTP {response.status_code} from {path}; check subscription coverage/key/quota')
            try:payload=response.json()
            except ValueError:raise FeedError(f'{self.provider}: invalid JSON response') from None
            if isinstance(payload,dict) and payload.get('success') in (0,False):
                raise FeedError(f'{self.provider}: provider refused request; check key and entitlement')
            if self.archive:
                safe=sanitize(payload)
                raw=json.dumps(dict(source_url=url,retrieved_utc=utcnow(),query=sanitize(params),payload=safe),sort_keys=True,allow_nan=False)
                folder=ROOT/'data/table_tennis/raw'/self.provider;folder.mkdir(parents=True,exist_ok=True)
                digest=hashlib.sha256(raw.encode()).hexdigest()
                (folder/(digest+'.json')).write_text(raw,encoding='utf-8')
            return payload
        raise FeedError(f'{self.provider}: retry budget exhausted')

def betsapi_event(raw, source_url, retrieved=None):
    league=raw.get('league') or {}
    if str(raw.get('sport_id'))!='92' or not scope(league.get('name'),league.get('cc')):
        raise ValueError('Out-of-scope provider event')
    status={'0':'scheduled','1':'live','3':'finished','4':'cancelled'}.get(str(raw.get('time_status')))
    if status is None:raise ValueError('Unsupported provider status')
    home=raw.get('home') or {};away=raw.get('away') or {}
    best_of=(raw.get('extra') or {}).get('bestofsets')
    if best_of is not None and str(best_of)!='5':
        raise ValueError('Provider reports an unsupported match length')
    scores=[];current=[0,0]
    native=raw.get('scores') or {}
    observed_current=False
    for key in sorted(native,key=lambda k:int(k)):
        score=[int(native[key]['home']),int(native[key]['away'])]
        if legal_terminal(score):scores.append(score)
        elif status=='live':current=score;observed_current=True
        else:raise ValueError('Incomplete finished point scores; retrieve event/view')
    if status=='live' and not observed_current:
        raise ValueError('No observed current-game points; refusing a guessed 0-0 live state')
    return validate_event(dict(event_id='betsapi:'+str(raw['id']),provider='betsapi',
        provider_event_id=str(raw['id']),league=LEAGUE,country='CZ',
        player_a=home.get('name'),player_b=away.get('name'),
        player_a_id='betsapi:'+str(home['id']),player_b_id='betsapi:'+str(away['id']),
        start_utc=timestamp(raw['time']).isoformat(),retrieved_utc=retrieved or utcnow(),
        source_url=source_url,status=status,best_of=5,game_scores=scores,current_points=current))

def oddsio_event(raw, source_url, retrieved=None):
    league=raw.get('league') or {};sport=raw.get('sport') or {}
    if sport.get('slug')!='table-tennis' or not scope(league.get('name'),'CZ') or 'czech' not in str(league.get('slug','')).lower():
        raise ValueError('Out-of-scope provider event')
    status={'pending':'scheduled','live':'live','settled':'finished','cancelled':'cancelled'}.get(raw.get('status'))
    native=(raw.get('scores') or {}).get('periods') or {}
    scores=[];current=[0,0];observed_current=False
    for key in sorted(native):
        pair=[int(native[key]['home']),int(native[key]['away'])]
        if legal_terminal(pair):scores.append(pair)
        elif status=='live':current=pair;observed_current=True
        else:raise ValueError('Incomplete finished point scores')
    if status=='live' and not observed_current:
        raise ValueError('No observed current-game points; refusing a guessed 0-0 live state')
    return validate_event(dict(event_id='oddsio:'+str(raw['id']),provider='oddsio',provider_event_id=str(raw['id']),
        league=LEAGUE,country='CZ',player_a=raw.get('home'),player_b=raw.get('away'),
        player_a_id='oddsio:'+str(raw['homeId']),player_b_id='oddsio:'+str(raw['awayId']),
        start_utc=raw.get('date'),retrieved_utc=retrieved or utcnow(),source_url=source_url,
        best_of=5,status=status,game_scores=scores,current_points=current))

def oddsio_quotes(raw, event):
    if str(raw.get('id'))!=event['provider_event_id']:
        raise ValueError('Quote event ID mismatch')
    if (str(raw.get('homeId')),str(raw.get('awayId'))) != (event['player_a_id'].split(':')[-1],event['player_b_id'].split(':')[-1]):
        raise ValueError('Provider quote player orientation mismatch')
    # Exact labels preserve units; generic Spread/Totals remain unpriced until
    # the vendor's table-tennis market settlement is explicitly established.
    mapping={'ML':'moneyline','Match Winner':'moneyline','Moneyline':'moneyline',
             'Total Games':'games_total','Game Handicap':'games_spread',
             'Total Sets':'games_total','Set Handicap':'games_spread',
             'Games Handicap':'games_spread','Sets Handicap':'games_spread',
             'Total Points':'points_total','Point Handicap':'points_spread',
             '1st Game Winner':'first_game_moneyline','1st Game Total Points':'first_game_total',
             '1st Game Point Handicap':'first_game_spread'}
    quotes=[];skipped=[]
    for bookmaker,markets in (raw.get('bookmakers') or {}).items():
        for m in markets:
            market=mapping.get(m.get('name'))
            if not market:
                skipped.append(f'{bookmaker}: unsupported/ambiguous market {m.get("name")}');continue
            for row in m.get('odds',[]):
                try:
                    total='total' in market
                    q=validate_quote(dict(event_id=event['event_id'],market=market,line=row.get('hdp'),
                        price_a=row.get('over' if total else 'home'),price_b=row.get('under' if total else 'away'),
                        bookmaker=bookmaker,quoted_utc=m.get('updatedAt'),retrieved_utc=utcnow(),
                        source_url='https://api.odds-api.io/v3/odds',is_live=event['status']=='live',
                        provider='oddsio',event_state={'scores':event['game_scores'],'points':event['current_points']}))
                    quotes.append(q)
                except (ValueError,TypeError):skipped.append(f'{bookmaker}: suspended, untimestamped or unsupported line')
    return quotes,skipped

class BetsApiAdapter(JsonClient):
    def __init__(self, **kwargs):
        super().__init__('betsapi','BETSAPI_KEY','https://api.b365api.com',**kwargs)
        # This ID is corroborated by the vendor's actual table-tennis response
        # example. Every returned event still requires league and CZ checks.
        self.league_id='22742'
        self._book_events={}

    def events(self, kind, day=None):
        if kind not in ('upcoming','inplay','ended'):raise ValueError('Unknown feed kind')
        rows=[]
        for page in range(1,101):
            params=dict(sport_id=92,league_id=self.league_id)
            if day:params['day']=day.replace('-','')
            if kind!='inplay':params['page']=page
            p=self.get('/v3/events/'+kind,**params)
            batch=p.get('results',[]);rows.extend(batch)
            pager=p.get('pager') or {}
            if kind=='inplay' or not batch or page*int(pager.get('per_page',len(batch)))>=int(pager.get('total',len(batch))):break
        else:raise FeedError('BetsAPI pagination exceeds 100 pages; narrow collection to a day')
        return rows

    def details(self, rows):
        ids=[str(r['id']) for r in rows]
        out=[]
        for i in range(0,len(ids),10):out.extend(self.get('/v1/event/view',event_id=','.join(ids[i:i+10])).get('results',[]))
        return out

    def quotes(self, event):
        p=self.get('/v2/event/odds',event_id=event['provider_event_id'],source='bet365')
        result=p.get('results') or {};stats=result.get('stats') or {}
        reverse=stats.get('matching_dir') == -1
        rows=(result.get('odds') or {}).get('92_1',[])
        out=[];skipped=[]
        for row in rows:
            try:
                # The archive can contain pre-match and in-play prices. Score
                # presence is evidence of in-play; unknown phase is not an anchor.
                score=str(row.get('ss') or '').strip()
                live=timestamp(row['add_time'])>=timestamp(event['start_utc']) or score not in ('','0-0')
                a=float(row['home_od']);b=float(row['away_od'])
                if reverse:a,b=b,a
                out.append(validate_quote(dict(event_id=event['event_id'],market='moneyline',line=None,
                    price_a=a,price_b=b,bookmaker='Bet365',quoted_utc=timestamp(row['add_time']).isoformat(),
                    retrieved_utc=utcnow(),source_url='https://api.b365api.com/v2/event/odds',provider='betsapi',is_live=live)))
            except (ValueError,KeyError,TypeError):continue
        other=[k for k in (result.get('odds') or {}) if k!='92_1']
        if other:skipped.append('BetsAPI generic market units unverified: '+','.join(other))
        if event['status']=='scheduled':
            try:
                full,notes=self.full_prematch_quotes(event)
                out.extend(full);skipped.extend(notes)
            except FeedError as exc:
                skipped.append('Full Bet365 markets: '+str(exc))
        return out,skipped

    def full_prematch_quotes(self,event):
        day=event['start_utc'][:10]
        if day not in self._book_events:
            rows=[]
            for page in range(1,101):
                p=self.get('/v1/bet365/upcoming',sport_id=92,day=day.replace('-',''),page=page)
                rows.extend(p.get('results',[]));pager=p.get('pager') or {}
                if not p.get('results') or page*int(pager.get('per_page',50))>=int(pager.get('total',0)):break
            else:raise FeedError('Full Bet365 fixture pagination exceeded budget')
            self._book_events[day]=rows
        name=normalized_name
        found=[]
        for row in self._book_events[day]:
            if not scope((row.get('league') or {}).get('name'),'CZ'):continue
            if timestamp(row['time'])!=timestamp(event['start_utc']):continue
            names=[name((row.get('home') or {}).get('name')),name((row.get('away') or {}).get('name'))]
            target=[name(event['player_a']),name(event['player_b'])]
            if names==target:found.append((row,False))
            elif names==target[::-1]:found.append((row,True))
        if len(found)!=1:
            return [],['No unique full Bet365 event mapping by Czech league, exact start and full player names']
        row,reverse=found[0]
        payload=self.get('/v4/bet365/prematch',FI=row['id'])
        results=payload.get('results',[])
        if len(results)!=1 or str(results[0].get('event_id'))!=event['provider_event_id']:
            return [],['Full Bet365 response does not confirm the canonical provider event ID']
        return bet365_prematch_quotes(results[0],event,reverse)

def bet365_prematch_quotes(payload,event,reverse=False):
    """Documented named-market structure; exact units and paired lines only."""
    mapping={'match winner':'moneyline','money line':'moneyline',
        'total games':'games_total','total sets':'games_total',
        'game handicap':'games_spread','games handicap':'games_spread',
        'set handicap':'games_spread','sets handicap':'games_spread',
        'total points':'points_total','point handicap':'points_spread',
        'points handicap':'points_spread','point spread':'points_spread',
        '1st game winner':'first_game_moneyline','1st set winner':'first_game_moneyline',
        '1st game total points':'first_game_total','1st set total points':'first_game_total',
        '1st game point handicap':'first_game_spread','1st set point handicap':'first_game_spread'}
    markets=[]
    def walk(node,updated=None):
        if isinstance(node,list):
            for x in node:walk(x,updated)
        elif isinstance(node,dict):
            updated=node.get('updated_at',updated)
            if isinstance(node.get('odds'),list) and node.get('name'):markets.append((node,updated))
            else:
                for value in node.values():
                    if isinstance(value,(list,dict)):walk(value,updated)
    walk(payload)
    out=[];skipped=[]
    for m,updated in markets:
        normalized=m['name'].casefold().replace('alternative ','').strip()
        kind=mapping.get(normalized)
        if not kind:
            skipped.append('Full Bet365 unsupported/ambiguous market: '+m['name']);continue
        pairs={}
        for row in m['odds']:
            try:
                header=str(row.get('header',row.get('name',''))).casefold()
                total='total' in kind
                side=0 if header==('over' if total else '1') else 1 if header==('under' if total else '2') else None
                if side is None:continue
                if 'moneyline' in kind:line=None
                else:
                    rawline=str(row.get('handicap',row.get('name',''))).strip()
                    if not re.fullmatch(r'[+-]?\d+(?:\.\d+)?',rawline):continue
                    line=float(rawline)
                    if 'spread' in kind and side==1:line=-line
                pairs.setdefault(line,{})[side]=float(row['odds'])
            except (ValueError,TypeError,KeyError):continue
        for line,sides in pairs.items():
            if set(sides)!={0,1}:continue
            a,b=sides[0],sides[1]
            if reverse and 'total' not in kind:
                a,b=b,a
                if line is not None:line=-line
            try:
                out.append(validate_quote(dict(event_id=event['event_id'],market=kind,line=line,
                    price_a=a,price_b=b,bookmaker='Bet365',quoted_utc=timestamp(updated).isoformat(),
                    retrieved_utc=utcnow(),is_live=False,provider='betsapi',source_url='https://api.b365api.com/v4/bet365/prematch')))
            except ValueError:skipped.append('Full Bet365 suspended or unsupported line: '+m['name'])
    return out,skipped

class OddsApiIoAdapter(JsonClient):
    def __init__(self, **kwargs):
        super().__init__('oddsio','ODDS_API_IO_KEY','https://api.odds-api.io/v3',**kwargs)
        self.bookmakers=os.getenv('TABLE_TENNIS_BOOKMAKERS','Bet365')
        self._leagues=None

    def events(self, kind, day=None):
        start=timestamp(day+'T00:00:00Z') if day else timestamp(utcnow())
        end=start+timedelta(days=1 if day else 2)
        if self._leagues is None:self._leagues=self.get('/leagues',sport='table-tennis',all='true')
        leagues=self._leagues
        verified=[r for r in leagues if scope(r.get('name'),'CZ') and 'czech' in r.get('slug','').lower()]
        if not verified:raise FeedError('Account returned no verified Czech Liga Pro coverage')
        out=[]
        for league in verified:
            if kind=='ended':
                out.extend(self.get('/historical/events',sport='table-tennis',league=league['slug'],**{'from':start.isoformat(),'to':end.isoformat()}))
            else:
                for skip in range(0,10000,500):
                    rows=self.get('/events',sport='table-tennis',league=league['slug'],status='live' if kind=='inplay' else 'pending',limit=500,skip=skip,**{'from':start.isoformat(),'to':end.isoformat()})
                    out.extend(rows)
                    if len(rows)<500:break
                else:raise FeedError('OddsAPI pagination exceeded budget')
        return out

    def details(self, rows):return rows

    def quotes(self, event):
        endpoint='/historical/odds' if event['status']=='finished' else '/odds'
        p=self.get(endpoint,eventId=event['provider_event_id'],bookmakers=self.bookmakers)
        return oddsio_quotes(p,event)

def provider(name='auto'):
    if name=='auto':
        name='betsapi' if os.getenv('BETSAPI_KEY') else ('oddsio' if os.getenv('ODDS_API_IO_KEY') else '')
    if name=='betsapi':return BetsApiAdapter()
    if name=='oddsio':return OddsApiIoAdapter()
    raise FeedError('Live collection needs BETSAPI_KEY or ODDS_API_IO_KEY in .env. Use --import-file for verified exports meanwhile')
