"""Paired priced lines, push-aware EV and complete reference market coverage."""
from .contracts import timestamp, validate_quote, MARKETS
from .scoring import settle_distribution

def current_quotes(quotes, event, now, max_age=300):
    selected={};rejected=[]
    for raw in sorted(quotes,key=lambda q:q['quoted_utc'],reverse=True):
        try:q=validate_quote(raw)
        except ValueError:
            rejected.append(dict(market=raw.get('market'),bookmaker=raw.get('bookmaker'),reason='Invalid quote schema or timestamp'));continue
        if q['event_id']!=event['event_id']:raise ValueError('Quote event mismatch')
        age=(timestamp(now)-timestamp(q['quoted_utc'])).total_seconds()
        key=(q['bookmaker'],q['market'],q['line'])
        if key in selected:continue
        if age< -5 or age>max_age or q['is_live']!=(event['status']=='live'):
            rejected.append(dict(market=q['market'],bookmaker=q['bookmaker'],reason='stale, future or wrong-phase quote'));continue
        if event['status']=='live' and q.get('event_state')!={'scores':event['game_scores'],'points':event['current_points']}:
            rejected.append(dict(market=q['market'],bookmaker=q['bookmaker'],reason='Live quote has no matching score snapshot'));continue
        selected[key]=q
    return list(selected.values()),rejected

def probabilities(distribution,market,line):
    if market=='moneyline':return distribution['p_match_a'],1-distribution['p_match_a'],0.
    if market=='first_game_moneyline':
        p=distribution['p_first_game_a']
        return None if p is None else (p,1-p,0.)
    if market.startswith('first_game_'):
        scores=distribution['first_game_scores']
        if not scores:return None
        d={}
        for (a,b),p in scores.items():
            v=a+b if market=='first_game_total' else a-b
            d[v]=d.get(v,0)+p
    else:
        mapping={'games_total':'total_games','games_spread':'game_margin',
                 'points_total':'total_points','points_spread':'point_margin'}
        d=distribution[mapping[market]]
    return settle_distribution(d,line,'spread' in market)

def evaluate(distribution,quotes,event):
    rows=[]
    for q in quotes:
        p=probabilities(distribution,q['market'],q['line'])
        if p is None:continue
        win,loss,push=p
        for side,prob,other,price in (('a',win,loss,q['price_a']),('b',loss,win,q['price_b'])):
            missing=max(0,1-win-loss-push)
            total='total' in q['market']
            label=('Over' if side=='a' else 'Under') if total else event['player_'+side]
            signed=(q['line'] if side=='a' else -q['line']) if 'spread' in q['market'] else q['line']
            ev=prob*(price-1)-other
            rows.append(dict(market=q['market'],line=q['line'],selection=label,selection_side=side,
                selection_line=signed,price=price,bookmaker=q['bookmaker'],quoted_utc=q['quoted_utc'],
                probability=prob,loss_probability=other,push_probability=push,
                fair_decimal=1+other/prob if prob else None,ev=ev,
                ev_lower=ev-missing,ev_upper=ev+missing*(price-1),
                status='RESEARCH: unvalidated edge',source_url=q['source_url']))
    return sorted(rows,key=lambda r:r['ev'],reverse=True)

def references(distribution):
    lines={'moneyline':[None],'games_total':[3.5,4.5],'games_spread':[-1.5,1.5],
        'points_total':[65.5,69.5,73.5,77.5,81.5], 'points_spread':[-5.5,-2.5,2.5,5.5],
        'first_game_moneyline':[None], 'first_game_total':[17.5,18.5,19.5,20.5],
        'first_game_spread':[-3.5,-1.5,1.5,3.5]}
    rows=[]
    for market in MARKETS:
        for line in lines[market]:
            p=probabilities(distribution,market,line)
            if p is not None:rows.append(dict(market=market,line=line,probability_a=p[0],probability_b=p[1],push_probability=p[2],status='MODEL REFERENCE ONLY: no sportsbook price'))
    return rows

def outcome(event,market,line,side):
    scores=event['game_scores']
    ga=sum(a>b for a,b in scores);gb=len(scores)-ga
    pa=sum(a for a,b in scores);pb=sum(b for a,b in scores)
    if market=='moneyline':value=1 if ga>gb else -1
    elif market=='games_total':value=ga+gb-line
    elif market=='games_spread':value=ga-gb+line
    elif market=='points_total':value=pa+pb-line
    elif market=='points_spread':value=pa-pb+line
    elif market=='first_game_moneyline':value=scores[0][0]-scores[0][1]
    elif market=='first_game_total':value=sum(scores[0])-line
    elif market=='first_game_spread':value=scores[0][0]-scores[0][1]+line
    else:raise ValueError('Unsupported settlement market')
    value=value if side=='a' else -value
    return 'win' if value>0 else 'loss' if value<0 else 'push'
