import copy
import io
import json
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

import pytest
from models.basketball_periods import provisional_periods
from run_ncaaf import predict_fixture, store
from score_review import format_review, market_rows
from models.score_ratings import price_market


def result():
    return {'sport':'basketball','league':'NBA','game_id':'123','game_date':'2026-10-20',
            'home_team':'New York Knicks','away_team':'Philadelphia 76ers',
            'projection':{'home_points':117.3,'away_points':107.0,
                          'validation':{'games':527,'margin_rmse':16.51972035226045}},
            'markets':[
                price_market('moneyline',.5,(.734,.266,0),-188,155),
                price_market('spread',-4.5,(.638,.362,0),-110,-110),
                price_market('total',232.5,(.333,.667,0),-110,-110)]}


def test_period_arithmetic_and_no_invented_distribution():
    segments=provisional_periods(result()['projection'])
    assert (segments['h1_projection']['home_points'],segments['h1_projection']['away_points'])==(58.1,53.0)
    assert segments['h1_projection']['total_points']==111.1
    assert segments['q1_projection']['total_points']==54.9
    for s in segments.values():
        assert s['total_points']==round(s['home_points']+s['away_points'],1)
        assert s['home_margin']==round(s['home_points']-s['away_points'],1)
        assert s['home_fair_spread']==-s['home_margin']
        assert s['probability'] is None and s['ev'] is None
        assert 'margin_sd' not in s and 'pick' not in s


@pytest.mark.parametrize('value',[None,float('nan'),float('inf'),-1,True])
def test_bad_full_game_scores_refused(value):
    with pytest.raises((ValueError,TypeError)):
        provisional_periods({'home_points':value,'away_points':100})


def test_home_away_over_under_odds_and_ev_formatting():
    r=result();before=copy.deepcopy(r)
    r['markets'][0]['ev_a']=.12493846764590494
    r['markets'][0]['ev_b']=-.3198971725993789
    text=format_review(r)
    assert 'Home: New York Knicks' in text and 'Away: Philadelphia 76ers' in text
    assert '+12.49%' in text and '-31.99%' in text
    assert '16.52' in text and '16.519720' not in text
    assert 'Under 232.5' in text and 'Over 232.5' in text
    assert ' A ' not in text and ' B ' not in text
    sides=market_rows(r,r['markets'][1])
    assert sides[0]['selection']=='Home: New York Knicks -4.5'
    assert sides[1]['selection']=='Away: Philadelphia 76ers +4.5'
    assert '1ST HALF - PROVISIONAL' in text
    assert r['projection']==before['projection']
    assert 'h1_projection' not in r  # historical snapshots are never rewritten by review
    assert r['markets'][0]['ev_a']==.12493846764590494


def test_unpriced_and_zero_ev_are_distinguished():
    r=result();r['markets'][0]['ev_a']=0;r['markets'][0]['ev_b']=None
    text=format_review(r)
    assert '+0.00%' in text and 'Unavailable - no price' in text
    assert 'None' not in text


def test_display_total_sums_displayed_points_without_modifying_raw_projection():
    r=result();r['projection'].update(home_points=117.26,away_points=106.97)
    text=format_review(r)
    assert '(Total: 224.3)' in text
    assert r['projection']['home_points']==117.26


def test_discord_uses_same_labels_without_sending():
    from embed_builder import build_embed
    r=result();r['markets'][0]['ev_a']=.12493846764590494
    embed=build_embed('basketball',r)
    text=json.dumps(embed)
    assert 'Home: New York Knicks' in text and '+12.49%' in text
    assert '1ST QUARTER - PROVISIONAL' in text
    assert all('EV unavailable' in f['value'] for f in embed['fields'] if 'PROVISIONAL' in f['name'])
    assert not any('LEAN' in f['value'] for f in embed['fields'] if 'PROVISIONAL' in f['name'])


def test_nba_segments_do_not_add_graded_bets_or_change_other_sports():
    r=result();game={k:r[k] for k in ['home_team','away_team','game_id','league']};game['date']=r['game_date']
    model=Mock();model.predict.return_value={**r['projection'],'margin_sd':16,'total_sd':20,'note':'test'}
    specs=[{'kind':'moneyline','line':.5,'price_a':-188,'price_b':155}]
    prediction=predict_fixture(game,model,specs,'basketball')
    assert 'h1_projection' in prediction and len(prediction['markets'])==1
    with patch('core.historical_storage.init_db'),patch('core.historical_storage.store_prediction') as save:
        store(prediction)
        assert save.call_count==1
        assert save.call_args.args[3]=='moneyline'
        assert save.call_args.args[9]['h1_projection']['ev'] is None
    other=predict_fixture({**game,'league':'WNBA'},model,specs,'basketball')
    assert 'h1_projection' not in other and '1ST HALF' not in format_review(other)


def test_saved_review_is_read_only_and_deduplicates_market_copies():
    from msp_workflow import show_saved_score_review
    r=result();row={**{k:r[k] for k in ['sport','league','game_date','home_team','away_team']},'raw_json':json.dumps(r)}
    saved={'run_id':'msp_test','payload':{'predictions':[row,row]}}
    before=copy.deepcopy(saved)
    with redirect_stdout(io.StringIO()) as out:
        assert show_saved_score_review(saved)
    assert out.getvalue().count('1ST QUARTER - PROVISIONAL')==1
    assert saved==before


def test_period_bookmaker_lines_are_quotes_not_probabilities():
    from score_odds import for_fixture
    game=dict(league='NBA',home_team='New York Knicks',away_team='Philadelphia 76ers',date='2026-10-20')
    def outcomes(line):return [dict(name=game['home_team'],price=-110,point=line),dict(name=game['away_team'],price=-110,point=-line)]
    event={**game,'id':'1','commence_time':'2026-10-20T23:00:00Z','bookmakers':[
        dict(key='book',markets=[dict(key='spreads',outcomes=outcomes(-4.5)),dict(key='spreads_h1',outcomes=outcomes(-2.5))])]}
    quotes,_=for_fixture([event],game,include_periods=True)
    assert len(quotes)==2
    assert quotes[1]['period']=='h1' and quotes[1]['line']==-2.5
    assert 'ev_a' not in quotes[1] and 'prob_a' not in quotes[1]
    assert len(for_fixture([event],game)[0])==1
    event['bookmakers'][0]['markets'][1]['outcomes'][1]['point']=3.5
    assert len(for_fixture([event],game,include_periods=True)[0])==1
