"""Read-only prospective scoring of original NHL observations, never bet ROI."""
import json
import math
from nhl_sources import stamp
from sports_feed import ROOT


def report(data=None,rows=None):
    data=data or json.loads((ROOT/'data/nhl_games.json').read_text(encoding='utf-8'))
    if rows is None:
        from msp_workflow import read_db
        with read_db() as conn:rows=list(conn.execute("SELECT raw_json FROM predictions WHERE sport='nhl' ORDER BY id"))
    fixtures={g['game_id']:g for g in data['games']};original={};invalid=0
    for row in rows:
        try:
            raw=json.loads(row['raw_json']);ident=raw['game_id']
            for side in ['home','away']:
                if not raw['fixture'][side+'_id']:raise ValueError('Missing original team identity')
                value=raw['projection']['regulation_'+side]
                if isinstance(value,bool) or not math.isfinite(float(value)) or float(value)<0:
                    raise ValueError('Invalid original goal projection')
            if not isinstance(raw['markets'],list):raise ValueError('Missing original market list')
            for market in raw['markets']:
                if not isinstance(market,dict):raise ValueError('Invalid original market')
                if market.get('kind')=='moneyline' and market.get('prob_a') is not None:
                    p=float(market['prob_a'])
                    if not math.isfinite(p) or not 0<=p<=1:raise ValueError('Invalid original winner probability')
            if stamp(raw['created_utc'])>=stamp(raw['fixture']['start_time']):continue
            if ident not in original or stamp(raw['created_utc'])<stamp(original[ident]['created_utc']):original[ident]=raw
        except (TypeError,ValueError,KeyError):invalid+=1
    winners=[];goal_errors=[];pending=0
    for ident,raw in original.items():
        game=fixtures.get(ident)
        if not game or not game['completed']:pending+=1;continue
        if any(raw['fixture'][s+'_id']!=game[s+'_id'] for s in ['home','away']):invalid+=1;continue
        for side in ['home','away']:
            goal_errors.append(abs(float(raw['projection']['regulation_'+side])-game['regulation_'+side]))
        ml=next((m for m in raw['markets'] if m['kind']=='moneyline'),None)
        if ml and ml.get('prob_a') is not None:
            p=float(ml['prob_a'])
            if not math.isfinite(p) or not 0<=p<=1:invalid+=1;continue
            p=max(1e-9,min(1-1e-9,p));y=int(game['home_score']>game['away_score'])
            winners.append(((p-y)**2,-y*math.log(p)-(1-y)*math.log(1-p)))
    return dict(label='NHL prospective observations — not a betting record',
                unique_prematch_fixtures=len(original),awaiting_results=pending,
                scored_winner_observations=len(winners),
                scored_regulation_observations=len(goal_errors)//2,
                winner_brier=sum(v[0] for v in winners)/len(winners) if winners else None,
                winner_log_loss=sum(v[1] for v in winners)/len(winners) if winners else None,
                regulation_team_goal_mae=sum(goal_errors)/len(goal_errors) if goal_errors else None,
                invalid_rows=invalid,
                basis='Earliest saved pregame forecast per official event; correlated markets/reruns count once. No profit/ROI claim.')
