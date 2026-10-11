"""Strict provenance and scoring contracts shared by every entry point."""
import math
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode

LEAGUE = 'Czech Liga Pro'
MARKETS = ('moneyline', 'games_total', 'games_spread', 'points_total',
           'points_spread', 'first_game_moneyline', 'first_game_total', 'first_game_spread')

def normalized_name(name):
    name=unicodedata.normalize('NFKD',str(name).casefold())
    name=''.join(c for c in name if not unicodedata.combining(c))
    return tuple(sorted(re.findall(r'\w+',name)))

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def timestamp(value):
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        value = datetime.fromtimestamp(float(value), timezone.utc)
    elif isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError('A timezone-aware UTC timestamp is required')
    return value.astimezone(timezone.utc)

def identifier(value):
    if value is None or str(value).split(':')[-1].lower() in ('none','null','') or not re.fullmatch(r'[A-Za-z0-9_:.-]{1,160}', str(value)) or '..' in str(value):
        raise ValueError('Missing or unsafe provider identifier')
    return str(value)

def number(value):
    if isinstance(value, bool):
        raise ValueError('A finite number is required')
    try:
        out = float(value)
    except (TypeError, ValueError):
        raise ValueError('A finite number is required') from None
    if not math.isfinite(out):
        raise ValueError('A finite number is required')
    return out

def scope(name, country):
    normalized = re.sub(r'[^a-z0-9]+', ' ', str(name).lower()).strip()
    return normalized in ('czech liga pro', 'czech republic czech liga pro',
                          'liga pro cz', 'czech republic liga pro') and str(country).lower() in (
                              'cz', 'czechia', 'czech republic')

def source_url(value):
    if not isinstance(value,str):raise ValueError('HTTPS source URL is required')
    parsed=urlsplit(value)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('HTTPS source URL without credentials is required')
    query=[(k,'[REDACTED]' if any(s in k.lower() for s in ('key','token','password','auth')) else v) for k,v in parse_qsl(parsed.query)]
    return urlunsplit((parsed.scheme,parsed.netloc,parsed.path,urlencode(query),''))

def score_pair(pair):
    if not isinstance(pair,(tuple,list)) or len(pair) != 2:
        raise ValueError('Point scores require two integers')
    if any(isinstance(x, bool) or int(x) != number(x) or int(x) < 0 for x in pair):
        raise ValueError('Point scores require nonnegative integers')
    return tuple(int(x) for x in pair)

def terminal(pair):
    a, b = score_pair(pair)
    return max(a, b) >= 11 and abs(a-b) >= 2

def legal_terminal(pair):
    a, b = score_pair(pair)
    return (max(a, b) == 11 and min(a, b) <= 9) or (min(a, b) >= 10 and abs(a-b) == 2)

def validate_event(event):
    e = dict(event)
    if not scope(e.get('league'), e.get('country')):
        raise ValueError('Rejected: this engine accepts verified Czech Liga Pro (CZ) only')
    e['event_id'] = identifier(e.get('event_id'))
    for side in ('a', 'b'):
        e['player_'+side+'_id'] = identifier(e.get('player_'+side+'_id'))
        if not isinstance(e.get('player_'+side), str) or not e['player_'+side].strip():
            raise ValueError('Player name and provider player ID are required')
    if e['player_a_id'] == e['player_b_id']:
        raise ValueError('A player cannot play themselves')
    e['start_utc'] = timestamp(e.get('start_utc')).isoformat()
    e['retrieved_utc'] = timestamp(e.get('retrieved_utc')).isoformat()
    if e.get('end_utc') is not None:
        e['end_utc'] = timestamp(e['end_utc']).isoformat()
        if e['end_utc'] < e['start_utc']:
            raise ValueError('End time precedes start time')
        if e['end_utc'] > e['retrieved_utc']:
            raise ValueError('Observed end time is after its capture')
    if e.get('best_of') != 5:
        raise ValueError('Only verified best-of-five matches are supported')
    if e.get('status') not in ('scheduled', 'live', 'finished', 'cancelled'):
        raise ValueError('Unknown event status')
    if e['status'] == 'finished' and e['start_utc'] > e['retrieved_utc']:
        raise ValueError('Finished event starts after its capture time')
    e['source_url']=source_url(e.get('source_url'))
    if not isinstance(e.get('game_scores',[]),list):raise ValueError('Completed game scores must be a list')
    if e['status']=='live' and 'current_points' not in e:raise ValueError('Live point snapshot is required')
    scores = [score_pair(x) for x in e.get('game_scores', [])]
    wins = [0, 0]
    for pair in scores:
        if max(wins) == 3 or not legal_terminal(pair):
            raise ValueError('Illegal game score or points played after match completion')
        wins[0 if pair[0] > pair[1] else 1] += 1
    if e['status'] == 'finished' and max(wins) != 3:
        raise ValueError('Finished match requires all legal game scores, ending at three wins')
    if e['status'] in ('scheduled', 'live') and max(wins) == 3:
        raise ValueError('Completed match cannot be scheduled or live')
    current = score_pair(e.get('current_points', [0, 0]))
    if terminal(current):
        raise ValueError('Terminal current game must be moved into completed game scores')
    if e['status'] == 'scheduled' and (scores or current != (0, 0)):
        raise ValueError('Scheduled match has played scores')
    e['game_scores'] = [list(x) for x in scores]
    e['current_points'] = list(current)
    return e

def validate_quote(quote):
    q = dict(quote)
    q['event_id'] = identifier(q.get('event_id'))
    if q.get('market') not in MARKETS:
        raise ValueError('Unsupported market or ambiguous game/point units')
    for side in ('a', 'b'):
        q['price_'+side] = number(q.get('price_'+side))
        if q['price_'+side] <= 1:
            raise ValueError('Decimal prices must exceed 1; assumed prices are forbidden')
    if 'moneyline' in q['market']:
        q['line'] = None
    else:
        q['line'] = number(q.get('line'))
        if q['line']*2 != round(q['line']*2):
            raise ValueError('Only integer and half lines are supported; quarter settlement is not assumed')
        if 'total' in q['market'] and q['line'] <= 0:
            raise ValueError('Total line must be positive')
    if not q.get('bookmaker'):
        raise ValueError('Bookmaker and source URL are required')
    q['source_url']=source_url(q.get('source_url'))
    q['quoted_utc'] = timestamp(q.get('quoted_utc')).isoformat()
    q['retrieved_utc'] = timestamp(q.get('retrieved_utc')).isoformat()
    if (timestamp(q['quoted_utc'])-timestamp(q['retrieved_utc'])).total_seconds()>5:
        raise ValueError('Quote timestamp is after its capture')
    if not isinstance(q.get('is_live'), bool):
        raise ValueError('Quote phase is required: is_live must be true or false')
    return q
