"""Recorded ESPN fixture identity/date regressions and caller orientation tests."""
import copy
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

import fixture_guard as guard
import universal_runner as runner


FIXTURES = Path(__file__).parent / 'fixtures' / 'soccer'


def recorded(day='20261023'):
    return json.loads((FIXTURES / f'espn_bundesliga_{day}.json').read_text(encoding='utf-8'))


@pytest.fixture
def feed(monkeypatch):
    response = Mock()
    response.json.return_value = recorded()
    fetch = Mock(return_value=response)
    monkeypatch.setattr(guard.requests, 'get', fetch)
    return response, fetch


def verify(home='Stuttgart', away='Borussia Monchengladbach', day='2026-10-23', league='Bundesliga'):
    return guard.verify_fixture('soccer', home, away, day, league)


@pytest.mark.parametrize('away', ['Borussia Monchengladbach', 'Borussia Mönchengladbach', 'Borussia Moenchengladbach', 'Mgladbach', 'Gladbach'])
def test_recorded_stuttgart_card_and_explicit_names(feed, away):
    valid, message, orientation = verify(away=away)
    assert valid and orientation == 'correct'
    assert 'Home VfB Stuttgart' in message and 'Away Borussia Mönchengladbach' in message
    assert '2026-10-23' in message and '401884761' in message
    _, fetch = feed
    assert fetch.call_args.args[0].endswith('/ger.1/scoreboard')
    assert fetch.call_args.kwargs['params'] == {'dates': '20261023'}


def test_feed_competitor_array_order_does_not_define_home(feed):
    response, _ = feed
    data=recorded();data['events'][0]['competitions'][0]['competitors'].reverse()
    response.json.return_value=data
    assert verify()[2]=='correct'
    assert verify('Gladbach','Stuttgart')[2]=='reversed'


@pytest.mark.parametrize('league', ['Made Up League', '', None])
def test_unknown_or_missing_league_never_fetches_epl(feed, league):
    assert verify(league=league)[0] is False
    feed[1].assert_not_called()


@pytest.mark.parametrize('day', ['2026-10-24','2026-10-22'])
def test_feed_date_is_checked_even_when_board_returns_wrong_day(feed, day):
    assert verify(day=day)[0] is False


@pytest.mark.parametrize('day', ['20261023','2026-02-30','not-a-date',None])
def test_invalid_requested_date_does_not_fetch(feed, day):
    assert verify(day=day)[0] is False
    feed[1].assert_not_called()


@pytest.mark.parametrize('home,away', [('Stutt','Gladbach'),('Stuttgart','Borussia'),('Made Up FC','Gladbach'),('','Gladbach'),('Stuttgart','Stuttgart')])
def test_no_substring_guesses_or_made_up_fixtures(feed, home, away):
    assert verify(home,away)[0] is False


def test_two_matching_cards_are_refused(feed):
    data=recorded();other=copy.deepcopy(data['events'][0]);other['id']='second'
    other['competitions'][0]['id']='second';data['events'].append(other)
    feed[0].json.return_value=data
    valid,message,orientation=verify()
    assert not valid and 'Ambiguous' in message and orientation is None


@pytest.mark.parametrize('kickoff,expected', [('2026-10-24T01:30Z',True),('2026-10-23T01:30Z',False),('2026-10-23T18:30',False),('invalid',False)])
def test_kickoff_uses_eastern_day_not_utc_or_host_day(feed, kickoff, expected):
    data=recorded();e=data['events'][0];e['date']=kickoff;e['competitions'][0]['date']=kickoff
    feed[0].json.return_value=data
    assert verify()[0] is expected


def test_disagreeing_event_and_competition_kickoff_refused(feed):
    data=recorded();data['events'][0]['competitions'][0]['date']='2026-10-23T20:30Z'
    feed[0].json.return_value=data
    assert verify()[0] is False


@pytest.mark.parametrize('change', ['missing_homeAway','duplicate_home','missing_name','no_id','postponed','crossed_names'])
def test_unverified_feed_identity_or_postponement_is_refused(feed, change):
    data=recorded();e=data['events'][0];comp=e['competitions'][0];sides=comp['competitors']
    if change=='missing_homeAway':sides[0].pop('homeAway')
    if change=='duplicate_home':sides[1]['homeAway']='home'
    if change=='missing_name':sides[0]['team'].pop('displayName')
    if change=='no_id':e.pop('id');comp.pop('id')
    if change=='postponed':comp['status']={'type':{'name':'STATUS_POSTPONED'}}
    if change=='crossed_names':
        sides[0]['team']['shortDisplayName']='Borussia Monchengladbach'
        sides[1]['team']['shortDisplayName']='Stuttgart'
    feed[0].json.return_value=data
    assert verify()[0] is False


@pytest.mark.parametrize('body', [{},[],{'events':None},{'events':[None]}])
def test_malformed_scoreboard_fails_closed(feed, body):
    feed[0].json.return_value=body
    assert verify()[0] is False


def test_network_and_json_failures_are_clear_refusals(feed):
    feed[0].raise_for_status.side_effect=requests.HTTPError('untrusted detail')
    assert 'HTTPError' in verify()[1]
    assert 'untrusted detail' not in verify()[1]
    feed[0].raise_for_status.side_effect=None
    feed[0].json.side_effect=ValueError('bad JSON')
    assert verify()[0] is False


def test_second_recorded_board_matches_only_requested_pair(feed):
    feed[0].json.return_value=recorded('20261025')
    assert verify('SC Freiburg','Bayern Munich','2026-10-25')[2]=='correct'
    assert verify('SC Freiburg','Bayer Leverkusen','2026-10-25')[0] is False


@pytest.fixture
def caller(monkeypatch,tmp_path):
    import predict_match,extra_markets,live_odds
    monkeypatch.chdir(tmp_path)
    stats=Mock(return_value={'verified_test_stats':True})
    model=Mock(side_effect=lambda home,away,**kw: {'game':{},'home_team':home,'away_team':away})
    display=Mock();store=Mock();push=Mock()
    monkeypatch.setattr(runner,'get_soccer_team_stats',stats)
    monkeypatch.setattr(predict_match,'run_soccer_game',model)
    monkeypatch.setattr(extra_markets,'enrich_result',lambda result,**kw:result)
    monkeypatch.setattr(runner,'_display_full_result',display)
    monkeypatch.setattr(runner,'_store_prediction',store)
    monkeypatch.setattr(runner,'_push_full_result',push)
    monkeypatch.setattr(guard,'verify_fixture',Mock(return_value=(True,'Verified feed fixture','reversed')))
    odds=Mock(return_value={'status':'live','home_ml':-180,'away_ml':150,'spread_line':-.5,'total_line':2.5})
    monkeypatch.setattr(live_odds,'get_soccer_odds',odds)
    return stats,model,display,store,push,odds


def test_reversed_caller_maps_manual_prices_and_handicap_to_actual_teams(caller):
    stats,model,display,store,push,_=caller
    result=runner.run_soccer('Gladbach','Stuttgart','Bundesliga',.5,2.5,False,False,
        auto_odds=False,market_line_given=True,market_total_given=True,
        home_ml=150,away_ml=-180,draw_ml=230,over_price=-112,under_price=100,
        spread_home_price=110,spread_away_price=-130,game_date='2026-10-23')
    assert [c.args[0] for c in stats.call_args_list]==['Stuttgart','Gladbach']
    assert model.call_args.args==('Stuttgart','Gladbach')
    assert model.call_args.kwargs['market_line']==-.5
    assert model.call_args.kwargs['market_total']==2.5
    assert result['market_moneyline']['home_ml']==-180
    assert result['market_moneyline']['away_ml']==150 and result['market_moneyline']['draw_ml']==230
    assert result['market_spread_prices']['spread_home_price']==-130
    assert result['market_spread_prices']['spread_away_price']==110
    assert result['market_totals_prices']['over_price']==-112
    assert result['market_totals_prices']['under_price']==100
    store.assert_not_called();push.assert_not_called();display.assert_called_once_with(result)


def test_reversed_caller_fetches_automatic_quotes_for_actual_orientation(caller):
    runner.run_soccer('Gladbach','Stuttgart','Bundesliga',0,2.5,False,False,game_date='2026-10-23')
    caller[-1].assert_called_once_with('Bundesliga','Stuttgart','Gladbach')


def test_correct_orientation_does_not_change_manual_line(caller,monkeypatch):
    monkeypatch.setattr(guard,'verify_fixture',lambda *args:(True,'verified','correct'))
    runner.run_soccer('Stuttgart','Gladbach','Bundesliga',-.5,2.5,False,False,auto_odds=False,game_date='2026-10-23')
    assert caller[1].call_args.args==('Stuttgart','Gladbach')
    assert caller[1].call_args.kwargs['market_line']==-.5


def test_unverified_fixture_never_reaches_stats_model_odds_or_storage(caller,monkeypatch):
    monkeypatch.setattr(guard,'verify_fixture',lambda *args:(False,'No unique fixture',None))
    with pytest.raises(ValueError,match='No unique fixture'):
        runner.run_soccer('Fake','Other','Bundesliga',0,2.5,True,False,game_date='2026-10-23')
    for mock in caller:mock.assert_not_called()


def test_one_requested_alias_shared_by_both_teams_is_ambiguous(feed):
    data=recorded()
    data['events'][0]['competitions'][0]['competitors'][1]['team']['shortDisplayName']='Stuttgart'
    feed[0].json.return_value=data
    assert verify()[0] is False


def test_reversed_orientation_reaches_storage_with_correct_teams(caller):
    runner.run_soccer('Gladbach','Stuttgart','Bundesliga',.5,2.5,True,False,
        auto_odds=False,home_ml=150,away_ml=-180,game_date='2026-10-23')
    stored=caller[3].call_args.kwargs
    assert stored['home']=='Stuttgart' and stored['away']=='Gladbach'
    assert stored['raw_json']['market_moneyline']['home_ml']==-180
    assert stored['raw_json']['market_moneyline']['away_ml']==150


def test_cli_five_arguments_print_card_under_windows_default_encoding():
    import os,subprocess,sys
    script = """import sys,runpy,json,requests
from unittest.mock import Mock
payload=json.loads(open('tests/fixtures/soccer/espn_bundesliga_20261023.json',encoding='utf-8').read())
response=Mock();response.json.return_value=payload
requests.get=Mock(return_value=response)
sys.argv=['fixture_guard.py','soccer','Stuttgart','Borussia Monchengladbach','2026-10-23','Bundesliga']
runpy.run_path('fixture_guard.py',run_name='__main__')
"""
    result=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[1],
        env={**os.environ,'PYTHONIOENCODING':'cp1252'},capture_output=True)
    assert result.returncode==0,result.stderr.decode('utf-8',errors='replace')
    output=result.stdout.decode('utf-8')
    assert 'Home VfB Stuttgart' in output and 'Borussia Mönchengladbach' in output
    assert 'Home orientation: correct' in output


def test_cli_missing_date_exits_with_usage_without_traceback():
    import subprocess,sys
    result=subprocess.run([sys.executable,str(Path(guard.__file__)),'soccer','Stuttgart','Gladbach'],capture_output=True)
    assert result.returncode==1
    assert 'Usage:' in result.stdout.decode('utf-8')
    assert b'Traceback' not in result.stderr
