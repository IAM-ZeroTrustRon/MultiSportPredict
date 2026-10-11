"""Chronological Czech-only point strength and optional market/H2H fitting.

Model priors are explicit, fitted weights are persisted, and equal-start-time
matches never learn each other's results. No post-match organizer rating is used.
"""
from collections import defaultdict
from datetime import timedelta
from functools import lru_cache
import json
import math
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from .contracts import timestamp, utcnow
from .scoring import ScoringModel

FEATURES=['elo_difference_400','h2h_residual_shrunk','recent_form_residual_difference',
          'same_day_games_load_difference']

def logit(p):
    p=max(1e-8,min(1-1e-8,float(p)))
    return math.log(p/(1-p))

@lru_cache(maxsize=4096)
def point_from_match(p):
    lo,hi=.01,.99
    for _ in range(45):
        mid=(lo+hi)/2
        g=ScoringModel(mid).win()
        match=g**3*(1+3*(1-g)+6*(1-g)**2)
        if match<p:lo=mid
        else:hi=mid
    return (lo+hi)/2

class History:
    def __init__(self):
        self.ratings=defaultdict(lambda:1500.)
        self.counts=defaultdict(int)
        self.recent=defaultdict(list)
        self.pairs=defaultdict(list)
        self.day_games=defaultdict(int)
        self.last_seen={}
        self.last_end={}

    def features(self,event):
        a,b=event['player_a_id'],event['player_b_id'];day=event['start_utc'][:10]
        elo=(self.ratings[a]-self.ratings[b])/400
        base=float(expit(math.log(10)*elo))
        meetings=self.pairs[tuple(sorted((a,b)))]
        residuals=[(win-prob if first==a else prob-win) for first,win,prob in meetings[-30:]]
        h2h=sum(residuals)/(len(residuals)+10)
        form=lambda p:sum(self.recent[p][-20:])/(len(self.recent[p][-20:])+10)
        load=(self.day_games[a,day]-self.day_games[b,day])/10
        rest={}
        for side,p in (('a',a),('b',b)):
            end=self.last_end.get(p)
            rest[side]=max(0,(timestamp(event['start_utc'])-timestamp(end)).total_seconds()/60) if end else None
        return [elo,h2h,form(a)-form(b),load],dict(
            player_a_history=self.counts[a],player_b_history=self.counts[b],
            h2h_matches=len(meetings),h2h_residual=h2h,
            h2h_match_win_rate_a=sum(win if first==a else 1-win for first,win,prob in meetings)/len(meetings) if meetings else None,
            last_seen_a=self.last_seen.get(a),last_seen_b=self.last_seen.get(b),
            rest_minutes=rest,rest_effect='Not fitted: actual end-time coverage is required',
            elo_a=self.ratings[a],elo_b=self.ratings[b],elo_prior=1500,
            same_day_games_a=self.day_games[a,day],same_day_games_b=self.day_games[b,day])

    def update(self,e):
        a,b=e['player_a_id'],e['player_b_id'];day=e['start_utc'][:10]
        won=sum(x>y for x,y in e['game_scores'])==3
        expected=float(expit(math.log(10)*(self.ratings[a]-self.ratings[b])/400))
        delta=20*(won-expected)
        self.ratings[a]+=delta;self.ratings[b]-=delta
        self.pairs[tuple(sorted((a,b)))].append((a,int(won),expected))
        for p,r in ((a,won-expected),(b,expected-won)):
            self.counts[p]+=1;self.recent[p].append(r)
            self.day_games[p,day]+=len(e['game_scores']);self.last_seen[p]=e['start_utc']
            if e.get('end_utc'):self.last_end[p]=e['end_utc']

def history_before(events, cutoff):
    h=History();cutoff=timestamp(cutoff)
    for e in sorted(events,key=lambda e:(e['start_utc'],e['event_id'])):
        # Without an observed end time, a completed result is only used on the
        # following UTC day. This avoids guessing same-session completion times.
        available=timestamp(e['end_utc']) if e.get('end_utc') else timestamp(e['start_utc'][:10]+'T00:00:00Z')+timedelta(days=1)
        if available<cutoff and not e.get('is_example',False):h.update(e)
    return h

def reference_quote_details(quotes,start,book=None,max_lead_seconds=3600):
    selected=[q for q in quotes if q['market']=='moneyline' and not q['is_live']
              and timestamp(q['quoted_utc'])<timestamp(start)
              and (max_lead_seconds is None or (timestamp(start)-timestamp(q['quoted_utc'])).total_seconds()<=max_lead_seconds)
              and (book is None or q['bookmaker'].lower()==book.lower())]
    if not selected:return None
    selected.sort(key=lambda q:q['quoted_utc'],reverse=True)
    q=selected[0];pa=1/q['price_a'];pb=1/q['price_b']
    return dict(probability_a=pa/(pa+pb),quote=q)

def reference_quote(quotes,start,book=None):
    details=reference_quote_details(quotes,start,book)
    return details['probability_a'] if details else None

def make_rows(events,quotes_by_event):
    rows=[]
    clean=[e for e in events if e['status']=='finished' and not e.get('is_example',False)]
    # One chronological pass instead of rescanning all history per match.
    available = sorted(clean, key=lambda e: timestamp(e['end_utc']) if e.get('end_utc') else timestamp(e['start_utc'][:10]+'T00:00:00Z')+timedelta(days=1))
    h=History();cursor=0
    clean=sorted(clean,key=lambda e:(e['start_utc'],e['event_id']))
    for e in clean:
        while cursor<len(available):
            prior=available[cursor]
            known=timestamp(prior['end_utc']) if prior.get('end_utc') else timestamp(prior['start_utc'][:10]+'T00:00:00Z')+timedelta(days=1)
            if known>=timestamp(e['start_utc']):break
            h.update(prior);cursor+=1
        x,metrics=h.features(e)
        if min(metrics['player_a_history'],metrics['player_b_history'])<8:continue
        points_a=sum(a for a,b in e['game_scores']);points_b=sum(b for a,b in e['game_scores'])
        market=reference_quote(quotes_by_event.get(e['event_id'],[]),e['start_utc'])
        rows.append(dict(event_id=e['event_id'],start=e['start_utc'],x=x,
            successes=points_a,trials=points_a+points_b,
            won=int(sum(a>b for a,b in e['game_scores'])==3),games=len(e['game_scores']),
            market=market))
    return sorted(rows,key=lambda r:(r['start'],r['event_id']))

def fit_points(rows,market=False):
    x=np.asarray([r['x']+([logit(point_from_match(r['market']))] if market else []) for r in rows],dtype=float)
    a=np.asarray([r['successes'] for r in rows],dtype=float)
    n=np.asarray([r['trials'] for r in rows],dtype=float)
    def objective(w):
        z=x@w
        # Per-match weighting limits dependence from repeated points and avoids
        # long deuce games dominating coefficients. No orientation intercept.
        loss=np.mean(np.logaddexp(0,z)-a/n*z)+.01*np.sum(w*w)
        gradient=x.T@(expit(z)-a/n)/len(rows)+.02*w
        return loss,gradient
    fitted=minimize(objective,np.zeros(x.shape[1]),jac=True,method='L-BFGS-B')
    if not fitted.success:raise ValueError('Model fit failed to converge')
    return fitted.x.tolist()

def probability(row,coefficients,market=False):
    x=row['x']+([logit(point_from_match(row['market']))] if market else [])
    point=float(expit(np.dot(x,coefficients)))
    point=max(.05,min(.95,point))
    g=ScoringModel(point).win()
    return point,g**3*(1+3*(1-g)+6*(1-g)**2)

def metrics(rows,weights,market=False):
    probs=[probability(r,weights,market)[1] for r in rows]
    ys=np.array([r['won'] for r in rows]);p=np.array(probs)
    baseline=np.array([r['market'] if market else float(expit(math.log(10)*r['x'][0])) for r in rows])
    return dict(matches=len(rows),brier=float(np.mean((p-ys)**2)),
        baseline_brier=float(np.mean((baseline-ys)**2)),
        log_loss=float(np.mean(-ys*np.log(np.maximum(p,1e-9))-(1-ys)*np.log(np.maximum(1-p,1e-9)))),
        mean_prediction=float(p.mean()),actual_win_rate=float(ys.mean()))

def train(events,quotes_by_event,path):
    rows=make_rows(events,quotes_by_event)
    if len(rows)<150:raise ValueError(f'Training needs 150 eligible completed matches after each player has 8 prior matches; found {len(rows)}. Keep collecting.')
    split=int(len(rows)*.8)
    boundary=rows[split]['start']
    train_rows=[r for r in rows if r['start']<boundary];test_rows=[r for r in rows if r['start']>=boundary]
    if len(train_rows)<100 or len(test_rows)<30:raise ValueError('Insufficient chronological train/holdout split')
    weights=fit_points(train_rows)
    evaluation=metrics(test_rows,weights)
    artifact=dict(schema=1,league='Czech Liga Pro',created_utc=utcnow(),features=FEATURES,
        fit='iid point strength with regularized chronological features',
        cutoff_utc=max(r['start'] for r in rows),strength_weights=fit_points(rows),
        strength_holdout=evaluation,training_matches=len(rows),
        holdout_start=boundary,training_event_ids=[r['event_id'] for r in rows],
        market_weights=None,market_holdout=None,
        status='EXPERIMENTAL: prospective market calibration still required')
    market_train=[r for r in train_rows if r['market'] is not None]
    market_test=[r for r in test_rows if r['market'] is not None]
    if len(market_train)>=100 and len(market_test)>=30:
        mw=fit_points(market_train,True)
        artifact['market_holdout']=metrics(market_test,mw,True)
        artifact['market_weights']=fit_points([r for r in rows if r['market'] is not None],True)
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    import hashlib
    version=hashlib.sha256(json.dumps(artifact,sort_keys=True,allow_nan=False).encode()).hexdigest()[:20]
    artifact['version']=version
    versions=path.parent/'model_versions';versions.mkdir(exist_ok=True)
    (versions/(version+'.json')).write_text(json.dumps(artifact,indent=2,allow_nan=False),encoding='utf-8')
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(artifact,indent=2,allow_nan=False),encoding='utf-8');temporary.replace(path)
    return artifact

def load_model(path, cutoff):
    if not Path(path).exists():return None
    model=json.loads(Path(path).read_text(encoding='utf-8'))
    if model.get('schema')!=1 or model.get('league')!='Czech Liga Pro' or model.get('features')!=FEATURES:
        raise ValueError('Model artifact is incompatible; retrain')
    for key,size in (('strength_weights',4),('market_weights',5)):
        weights=model.get(key)
        if weights is None and key=='market_weights':continue
        if not isinstance(weights,list) or len(weights)!=size or not all(isinstance(w,(int,float)) and math.isfinite(w) for w in weights):
            raise ValueError('Invalid fitted weights; retrain')
    if not model.get('created_utc') or not model.get('cutoff_utc'):
        raise ValueError('Model timestamps are missing; retrain')
    if timestamp(model['cutoff_utc'])>=timestamp(cutoff):
        raise ValueError('Model includes this event or future results; train only earlier matches')
    return model
