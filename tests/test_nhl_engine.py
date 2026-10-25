"""NHL source contracts, pregame leakage, OT settlement and workflow integration."""
import copy
import datetime as dt
import json
from types import SimpleNamespace
from unittest.mock import Mock,patch

import numpy as np
import pandas as pd
import pytest

from nhl_sources import parse_game,attach_advanced,TEAM_COLUMNS
from features.nhl_features import pregame_features,NHL_FEATURES,FEATURE_VERSION
from models.nhl_model import NHLModel,distribution,market_probabilities
from run_nhl import forecast,select_games
from score_odds import for_fixture
from sports_feed import atomic_json


NOW='2026-10-21T20:00:00+00:00'


def raw(phase='REG',h=3,a=2):
    def team(i,name):return dict(id=i,abbrev=name,placeName={'default':name},commonName={'default':'Club'},score=h if i==1 else a)
    return dict(id=2026020001,season=20262027,gameType=2,startTimeUTC='2026-10-20T23:00:00Z',
                gameState='OFF',gameOutcome={'lastPeriodType':phase},homeTeam=team(1,'AAA'),awayTeam=team(2,'BBB'))


def game(ident='future',day='2026-10-22'):
    r=parse_game(raw(),NOW,'https://api-web.nhle.com/test')
    r.update(game_id=ident,date=day,start_time=day+'T23:00:00+00:00',completed=False,status='FUT',season_type=2)
    return r


def history(n=12):
    out=[]
    for i in range(n):
        r=game(str(i),f'2026-10-{i+1:02d}');r.update(completed=True,status='OFF',regulation_home=3,regulation_away=2,home_score=3,away_score=2)
        stats=dict(xGoalsFor=2.2,xGoalsAgainst=2.0,iceTime=3000,shotAttemptsFor=50,shotAttemptsAgainst=45,
                   highDangerShotsFor=10,highDangerShotsAgainst=8,shotsOnGoalAgainst=25,goalsAgainst=2)
        power_play=dict(iceTime=240,goalsFor=1,goalsAgainst=0)
        penalty_kill=dict(iceTime=180,goalsFor=0,goalsAgainst=1)
        r['advanced_5on5']={'home':stats.copy(),'away':stats.copy()}
        r['special_teams']={s:{'pp':dict(power_play),'pk':dict(penalty_kill)} for s in ('home','away')}
        out.append(r)
    return out


@pytest.mark.parametrize('phase',['REG','OT','SO'])
def test_official_phase_and_regulation_scores(phase):
    r=parse_game(raw(phase),NOW,'official')
    assert r['date']=='2026-10-20' and r['season_start']==2026
    assert r['regulation_home']==(3 if phase=='REG' else 2)
    assert r['regulation_away']==2


def test_bad_final_and_playoff_shootout_refused():
    for value in [raw('OT',5,2),raw('REG',2,2),raw('UNKNOWN')]:
        with pytest.raises(ValueError):parse_game(value,NOW,'official')
    value=raw('SO');value['gameType']=3
    with pytest.raises(ValueError):parse_game(value,NOW,'official')
    value=raw();value['gameType']=1
    assert parse_game(value,NOW,'official') is None


def test_source_join_requires_id_team_season_date_and_two_unique_sides():
    g=parse_game(raw(),NOW,'official')
    base=[dict(gameId=2026020001,team=t,home_or_away=s,season=2026,gameDate=20261020)
          for t,s in [('AAA','HOME'),('BBB','AWAY')]]
    rows=[dict(r,situation=sit) for sit in ('5on5','5on4','4on5') for r in base]
    assert attach_advanced([g],rows)==1
    assert g['special_teams']['home']['pp']['situation']=='5on4'
    assert g['special_teams']['away']['pk']['situation']=='4on5'
    def replace(index,value):return rows[:index]+[value]+rows[index+1:]
    for broken in [replace(1,dict(rows[1],team='UNKNOWN')),replace(1,dict(rows[1],season=2025)),
                   replace(1,rows[0]),rows[:-1]]:
        with pytest.raises(ValueError):attach_advanced([g],broken)


def test_features_exclude_target_same_day_future_and_prior_season_not_current():
    rows=history();target=game()
    x,obs=pregame_features(target,rows)
    future=history(1)[0];future.update(game_id='leak',date=target['date'])
    future['advanced_5on5']['home']['xGoalsFor']=999
    future['special_teams']['home']['pp']['goalsFor']=99
    assert pregame_features(target,rows+[future])[0]==x
    assert obs['home']['season_games_played']==12
    old=copy.deepcopy(rows)
    for g in old:g.update(season=20252026,season_start=2025)
    assert pregame_features(target,old)[1]['home']['season_games_played']==0
    assert all(np.isfinite(list(x.values())))


def test_missing_advanced_and_zero_denominators_do_not_become_defaults():
    with pytest.raises(ValueError):pregame_features(game(),history(7))
    rows=history()
    for g in rows:g['advanced_5on5']['home']['iceTime']=0
    with pytest.raises(ValueError):pregame_features(game(),rows)


def test_special_teams_xg_share_exposure_and_workload_features():
    x,obs=pregame_features(game(),history())
    assert x['home_xg_share']==pytest.approx(2.2/4.2) and x['away_xg_share']==pytest.approx(2.2/4.2)
    assert x['home_pp_goals60']==pytest.approx(15.0)
    assert x['home_pk_goals_against60']==pytest.approx(20.0)
    assert x['home_exposure_minutes']==pytest.approx(600.0)
    assert x['home_back_to_back']==0 and x['away_back_to_back']==0
    assert x['home_games_last_7_days']==0 and x['rest_diff_days']==0
    assert obs['home']['pp_games']==12 and obs['home']['pk_games']==12


def test_back_to_back_and_recent_workload_are_pregame_only():
    rows=history();rows[-1]['start_time']='2026-10-22T02:00:00+00:00'
    x,_=pregame_features(game(),rows)
    assert x['home_back_to_back']==1 and x['away_back_to_back']==1
    assert x['home_games_last_7_days']==1 and x['away_games_last_7_days']==1
    later=copy.deepcopy(rows);later[-1]['start_time']='2026-10-22T23:30:00+00:00'
    with pytest.raises(ValueError):pregame_features(game(),later)


def test_zero_or_absent_special_teams_exposure_is_unavailable():
    rows=history()
    for g in rows:g['special_teams']['home']['pp']['iceTime']=0
    with pytest.raises(ValueError):pregame_features(game(),rows)
    rows=history()
    for g in rows:g['special_teams']['away']['pk']['iceTime']=0
    with pytest.raises(ValueError):pregame_features(game(),rows)
    rows=history()
    for g in rows:g.pop('special_teams')
    with pytest.raises(ValueError):pregame_features(game(),rows)


def test_feature_contract_requires_the_special_teams_keys():
    from models.nhl_model import vector
    x,_=pregame_features(game(),history())
    assert len(vector(x))==len(NHL_FEATURES)
    for key in ('home_xg_share','home_pp_goals60','away_pk_goals_against60','home_exposure_minutes'):
        broken=dict(x);broken.pop(key)
        with pytest.raises(ValueError):vector(broken)


def test_moneypuck_rows_reject_duplicates_and_negative_values(tmp_path):
    from nhl_sources import money_team_rows
    def row(**over):
        base=dict(team='AAA',season=2026,gameId=2026020001,gameDate=20261020,situation='5on5',home_or_away='HOME',
                  xGoalsFor=2.,xGoalsAgainst=1.8,iceTime=3000.,shotAttemptsFor=50.,shotAttemptsAgainst=45.,
                  highDangerShotsFor=8.,highDangerShotsAgainst=7.,shotsOnGoalAgainst=25.,goalsAgainst=2.,goalsFor=3.)
        base.update(over);return base
    good=tmp_path/'good.csv';pd.DataFrame([row(),row(team='BBB',home_or_away='AWAY')]).to_csv(good,index=False)
    assert [r['team'] for r in money_team_rows(good,2024)]==['AAA','BBB']
    duplicate=tmp_path/'duplicate.csv';pd.DataFrame([row(),row()]).to_csv(duplicate,index=False)
    with pytest.raises(ValueError):money_team_rows(duplicate,2024)
    negative=tmp_path/'negative.csv';pd.DataFrame([row(iceTime=-1.)]).to_csv(negative,index=False)
    with pytest.raises(ValueError):money_team_rows(negative,2024)


def test_probability_mass_symmetry_pushes_and_no_silent_renormalization():
    d=distribution(3,3,.5)
    assert sum(d['scores'].values())==pytest.approx(1,abs=1e-8)
    assert d['omitted_tail']>=0
    assert market_probabilities(d,'moneyline',.5)[0]==pytest.approx(.5,abs=1e-8)
    assert all(h!=a for h,a in d['scores'])
    assert market_probabilities(d,'total',6)[2]>0
    assert market_probabilities(d,'spread',-1)[2]>0
    with pytest.raises(ValueError):market_probabilities(d,'total',6.25)
    assert distribution(3,3,None) is None


def mock_model():
    return SimpleNamespace(trained_before='2026-10-21T18:00:00+00:00',created_utc='2026-10-21T18:00:00+00:00',
        data_hash='hash',version='test',validation=dict(games=200,winner_brier=.20,baseline_winner_brier=.25,
            goal_deviance=1.1,baseline_goal_deviance=1.2,goal_dispersion=[1.1,1.1]),
        predict=lambda f,p=False:dict(regulation_home=3.2,regulation_away=2.7,ot_home_probability=.55,
            distribution=distribution(3.2,2.7,.55)))


def test_unknown_goalies_projection_only_saved_info_and_discord_clean():
    from run_ncaaf import store
    from grade_predictions import is_excluded_tier
    from embed_builder import build_embed
    data=dict(retrieved_utc=NOW,data_hash='hash',games=history(),sources={})
    spec=dict(kind='moneyline',line=.5,price_a=110,price_b=-130,scope='official_final_including_ot_so')
    r=forecast(game(),data,mock_model(),[spec],now=NOW)
    assert not r['readiness']['eligible'] and r['markets'][0]['ev_a'] is None
    assert 'Starting goalies' in str(r['readiness']['reasons'])
    json.dumps(r,allow_nan=False)
    with patch('core.historical_storage.init_db'),patch('core.historical_storage.store_prediction') as save:
        store(r)
    assert is_excluded_tier(save.call_args.args[8])
    assert save.call_args.args[6] is None
    assert save.call_args.kwargs['stake_size'] is None
    embed=json.dumps(build_embed('nhl',r),ensure_ascii=False)
    assert 'NHL' in embed and 'Starting goalies' in embed


def test_started_stale_model_and_mismatched_scope_are_refused():
    data=dict(retrieved_utc=NOW,data_hash='hash',games=history(),sources={})
    with pytest.raises(ValueError):forecast(game(day='2026-10-20'),data,mock_model(),[],now=NOW)
    with pytest.raises(ValueError):forecast(game(),{**data,'data_hash':'other'},mock_model(),[],now=NOW)
    with pytest.raises(ValueError):forecast(game(),data,mock_model(),[dict(kind='moneyline',line=.5,price_a=100,price_b=-110)],now=NOW)
    with pytest.raises(ValueError):select_games([game(day='2026-10-20')],'2026-10-20',now=NOW)


def test_nhl_prices_reject_three_way_stale_or_wrong_handicap():
    now=dt.datetime.now(dt.timezone.utc)
    g=game(day=now.astimezone(dt.timezone.utc).date().isoformat())
    # The odds date must be the fixture's Eastern date.
    from sports_feed import EASTERN
    g['date']=now.astimezone(EASTERN).date().isoformat()
    m=dict(key='h2h',last_update=now.isoformat(),outcomes=[dict(name=g['home_team'],price=110),dict(name=g['away_team'],price=-130)])
    event=dict(home_team=g['home_team'],away_team=g['away_team'],id='odds1',commence_time=now.isoformat(),bookmakers=[dict(key='book',markets=[m])])
    assert len(for_fixture([event],g)[0])==1
    m['outcomes'].append(dict(name='Draw',price=300));assert for_fixture([event],g)[0]==[]
    m['outcomes'].pop();m['last_update']=(now-dt.timedelta(hours=1)).isoformat()
    assert for_fixture([event],g)[0]==[]


def test_grading_official_final_scopes_and_pushes():
    from grade_predictions import grade_row,Ungradable
    row=dict(sport='nhl',market_type='spread',model_value=.6,market_value=-1,home_team='A',away_team='B',recommendation='LEAN HOME',
             raw_json=json.dumps(dict(settlement={'scope':'official_final_including_ot_so'},_pick='HOME',spread={'market_spread':-1,'pick':'HOME'},market_odds={'spread_home_price':-110,'spread_away_price':-110})))
    assert grade_row(row,3,2)[0]=='push'
    row['raw_json']='{}'
    with pytest.raises(Ungradable):grade_row(row,3,2)


def test_workflow_root_routes_and_no_implicit_delivery():
    import msp_workflow as w
    assert 'nhl' in w.SPORTS
    assert ['ingest_nhl.py'] in w.refresh_plan('nhl')
    command=w.run_command('nhl',[],'2026-10-22',None,{},[])
    assert command[0]=='run_nhl.py' and '--odds' in command and '--push' not in command


def test_summary_save_percentage_is_derived_and_missing_download_preserves_cache(monkeypatch,tmp_path):
    from ingest.nhl_api_fetcher import NHLAPIFetcher
    import ingest.nhl_api_fetcher as fetcher
    p=tmp_path/'teams.csv'
    pd.DataFrame([dict(team='AAA',situation='5on5',xGoalsPercentage=.52,corsiPercentage=.51,
        highDangerShotsFor=10,highDangerShotsAgainst=10,shotsOnGoalAgainst=100,goalsAgainst=8)]).to_csv(p,index=False)
    monkeypatch.setattr(fetcher,'download_csv',lambda *a:(p,{'retrieved_utc':NOW}))
    out=NHLAPIFetcher().fetch_advanced_metrics(2026)
    assert out.iloc[0].team_save_pct==.92 and out.iloc[0].high_danger_shot_share==.5


def test_model_fits_chronological_artifact_and_refuses_schema_mismatch():
    rng=np.random.default_rng(3);rows=[]
    for i in range(650):
        h=int(rng.poisson(3));a=int(rng.poisson(2.7))
        if i%5==0:h=a=2
        date=(dt.date(2024,1,1)+dt.timedelta(days=i)).isoformat()
        rows.append(dict(game_id=str(i),date=date,regulation_home=h,regulation_away=a,
                         home_won=int(h>a) if h!=a else i%2,**{k:float(rng.uniform(.1,2)) for k in NHL_FEATURES}))
    m=NHLModel().fit(rows,'test','2026-01-01T00:00:00+00:00')
    assert m.validation['games']>=100 and m.ot is not None
    assert m.predict(rows[0])['distribution'] is not None
    m.feature_schema=[]
    with pytest.raises(ValueError):m.predict(rows[0])


def test_auto_grading_verifies_exact_official_event_id(monkeypatch,tmp_path):
    import sqlite3
    import grade_predictions as g
    import nhl_sources
    from core.historical_storage import init_db,store_prediction
    path=tmp_path/'test.db';init_db(path)
    official=parse_game(raw('SO'),NOW,'official')
    monkeypatch.setattr(nhl_sources,'schedule',lambda day:[official])
    for kind,ident in [('moneyline',official['game_id']),('spread','wrong-id')]:
        raw_pick=dict(game_date=official['date'],fixture={'game_id':ident},
                      event_key=f'NHL:{ident}:{kind}',_pick='HOME',
                      settlement={'scope':'official_final_including_ot_so'},
                      spread={'market_spread':-1.5,'pick':'HOME'},
                      market_odds={'home_ml':110,'away_ml':-130})
        store_prediction('nhl',official['home_team'],official['away_team'],kind,.6,.5,5,None,'LEAN HOME',raw_pick,path,'NHL')
    with sqlite3.connect(path) as conn:
        conn.row_factory=sqlite3.Row;g.ensure_schema(conn);g.cmd_auto(conn,'nhl',10000)
        outcomes={r['market_type']:r['result_outcome'] for r in conn.execute('select * from predictions')}
    assert outcomes=={'moneyline':'win','spread':None}


def test_failed_download_preserves_last_good_csv(monkeypatch,tmp_path):
    import nhl_sources as source
    import requests
    monkeypatch.setattr(source,'CACHE',tmp_path)
    good=tmp_path/'test.csv';good.write_text('old_good_cache')
    response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
    response.raise_for_status.side_effect=requests.HTTPError('Unavailable')
    monkeypatch.setattr(source.requests,'get',lambda *a,**kw:response)
    with pytest.raises(requests.HTTPError):source.download_csv('https://example.invalid/published.csv','test.csv',['team'])
    assert good.read_text()=='old_good_cache'
    assert not (tmp_path/'test.download').exists()


def test_real_goalie_context_removes_only_identity_gap_and_future_is_refused():
    data=dict(retrieved_utc=NOW,data_hash='hash',games=history(),sources={})
    context=dict(game_id='future',observed_utc=NOW,
                 home=dict(team_id='1',player_id=8470001,confirmed=True,source_url='https://example.invalid/home-lineup'),
                 away=dict(team_id='2',player_id=8470002,confirmed=True,source_url='https://example.invalid/away-lineup'))
    spec=dict(kind='moneyline',line=.5,price_a=110,price_b=-130,scope='official_final_including_ot_so')
    r=forecast(game(),data,mock_model(),[spec],now=NOW,goalies=context)
    assert r['readiness']['eligible'] and r['markets'][0]['ev_a'] is not None
    context['observed_utc']='2026-10-21T21:00:00+00:00'
    with pytest.raises(ValueError):forecast(game(),data,mock_model(),[spec],now=NOW,goalies=context)
    with pytest.raises(ValueError):forecast(game(),data,mock_model(),[spec],now=NOW,goalies=[])


def test_prospective_observations_count_event_once_without_bet_grades():
    from nhl_observations import report
    event=history(1)[0]
    raw=dict(game_id=event['game_id'],created_utc='2026-09-30T20:00:00+00:00',fixture=event,
             projection=dict(regulation_home=3.2,regulation_away=2.7),markets=[dict(kind='moneyline',prob_a=.6)])
    rows=[dict(raw_json=json.dumps(raw))]*3
    r=report(dict(games=[event]),rows)
    assert r['unique_prematch_fixtures']==1 and r['scored_winner_observations']==1
    assert r['winner_brier']==pytest.approx(.16) and r['regulation_team_goal_mae']==pytest.approx(.45)
    assert 'roi' not in r
