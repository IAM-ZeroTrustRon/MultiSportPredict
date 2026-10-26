"""Task 2 audit regressions: strict contracts, last reference, budget and linkage."""
import copy
import datetime as dt
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest

from core.historical_storage import init_db,save_odds_snapshot,get_odds_snapshots,capture_prediction_odds
from closing_collector import collect
from clv import compare_snapshots,clv_report

OPEN='2026-10-31T20:00:00+00:00'
NOW=dt.datetime(2026,10,31,22,50,tzinfo=dt.timezone.utc)
KICK='2026-10-31T23:00:00+00:00'
SCOPE='official_final_including_ot_so'


def quote(kind='prediction',**updates):
    row=dict(capture_kind=kind,sport='nhl',league='NHL',event_key='NHL:odds1:moneyline:0.5',
        source_event_id='odds1',game_date='2026-10-31',kickoff_utc=KICK,home_team='A Club',away_team='B Club',
        market_type='moneyline',line=.5,price_a=120,price_b=-140,bookmaker='book1',scope=SCOPE,
        observed_utc=OPEN if kind=='prediction' else NOW.isoformat(),
        quote_updated_utc=OPEN if kind=='prediction' else (NOW-dt.timedelta(seconds=30)).isoformat(),
        payload={'official_fixture_id':'1','run_id':'run1' if kind=='prediction' else None,'period':'full_game'})
    row.update(updates);return row


def fixture(**updates):
    row=dict(game_id='1',home_team='A Club',away_team='B Club',date='2026-10-31',start_time=KICK,status='FUT',completed=False)
    row.update(updates);return row


def event(**updates):
    row=dict(id='odds1',commence_time=KICK,home_team='A Club',away_team='B Club',bookmakers=[dict(key='book1',markets=[
        dict(key='h2h',last_update=(NOW-dt.timedelta(seconds=30)).isoformat(),outcomes=[dict(name='A Club',price=100),dict(name='B Club',price=-120)])])])
    row.update(updates);return row


@pytest.fixture
def db(tmp_path):
    p=tmp_path/'history.db';init_db(p);return p


@pytest.mark.parametrize('field,value',[('bookmaker','other'),('league','NBA'),('scope','regulation_only'),('home_team','B Club'),('source_event_id','other')])
def test_comparison_rejects_cross_book_event_scope_league_orientation(field,value):
    bad=quote('closing');bad[field]=value
    with pytest.raises(ValueError): compare_snapshots(quote(),bad)


def test_period_mismatch_is_not_full_game_clv():
    bad=quote('closing');bad['payload']['period']='h1'
    with pytest.raises(ValueError):compare_snapshots(quote(),bad)


def test_report_never_pairs_different_bookmakers(db):
    save_odds_snapshot(quote(),db);save_odds_snapshot(quote('closing',bookmaker='other'),db)
    r=clv_report(db);assert r['exact_line']['n']==0


def test_provider_update_is_required_at_storage_boundary(db):
    with pytest.raises(ValueError,match='update timestamp'):save_odds_snapshot(quote('closing',quote_updated_utc=None),db)
    assert get_odds_snapshots(db)==[]


def test_future_bookmaker_time_is_not_accepted(db):
    with pytest.raises(ValueError,match='future'):save_odds_snapshot(quote('closing',quote_updated_utc=(NOW+dt.timedelta(seconds=30)).isoformat()),db)


def test_collection_without_tracked_prediction_never_stores(db):
    result=collect([event()],'NHL',now=NOW,db_path=db,fixtures=[fixture()])
    assert not result['captured'] and result['tracked_events']==0


@pytest.mark.parametrize('broken',[None,[],[fixture(completed=True,status='OFF')],[fixture(start_time='2026-10-31T23:30:00Z')],[fixture(home_team='Different Club')]])
def test_collection_requires_current_official_identity_status_and_kickoff(db,broken):
    save_odds_snapshot(quote(),db)
    result=collect([event()],'NHL',now=NOW,db_path=db,fixtures=broken)
    assert not result['captured'] and result['refused']


def test_provider_kickoff_change_is_refused(db):
    save_odds_snapshot(quote(),db)
    result=collect([event(commence_time='2026-10-31T23:20:00Z')],'NHL',now=NOW,db_path=db,fixtures=[fixture()])
    assert not result['captured'] and 'kickoff' in str(result['refused'])


def test_explicit_live_provider_flag_is_refused(db):
    save_odds_snapshot(quote(),db)
    result=collect([event(in_play=True)],'NHL',now=NOW,db_path=db,fixtures=[fixture()])
    assert not result['captured'] and 'in_play' in str(result['refused'])


def test_missing_tracked_bookmaker_does_not_substitute_another(db):
    save_odds_snapshot(quote(),db);e=event();e['bookmakers'][0]['key']='other'
    result=collect([e],'NHL',now=NOW,db_path=db,fixtures=[fixture()])
    assert not result['captured'] and 'bookmaker' in str(result['refused'])


def test_closing_retry_and_concurrent_capture_are_idempotent(db):
    save_odds_snapshot(quote(),db)
    rows=[quote('closing'),quote('closing',observed_utc=(NOW+dt.timedelta(seconds=1)).isoformat())]
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda q:save_odds_snapshot(q,db),rows))
    assert sum(r['inserted'] for r in results)==1
    assert len(get_odds_snapshots(db,capture_kind='closing'))==1


def test_captures_keep_run_official_id_selections_and_source_format(db):
    result=dict(sport='nhl',league='NHL',game_id='1',game_date='2026-10-31',_workflow_run_id='msp_test',
        home_team='A Club',away_team='B Club',fixture={'start_time':KICK},settlement={'scope':SCOPE},
        markets=[dict(kind='moneyline',line=.5,price_a=120,price_b=-140,quote={'bookmaker':'book1','updated':OPEN,'source_event_id':'odds1','scope':SCOPE})])
    saved=capture_prediction_odds(result,db,observed_utc=OPEN);assert not saved['refused']
    row=get_odds_snapshots(db)[0]
    assert row['payload']['run_id']=='msp_test' and row['payload']['official_fixture_id']=='1'
    assert row['payload']['selection_a']=='A Club' and row['payload']['odds_format']=='american'
    again=capture_prediction_odds(result,db,observed_utc='2026-10-31T20:00:01Z')
    assert not again['saved'][0]['inserted']


def test_clv_arithmetic_and_reference_label_are_explicit():
    c=quote('closing',price_a=100,price_b=-100)
    r=compare_snapshots(quote(),c)
    assert r['sides']['a']['price_clv']==pytest.approx(.1)
    assert r['sides']['a']['fair_price_clv']==pytest.approx(.1,abs=1e-6)
    assert r['closing_lead_minutes']==10
    assert 'not guaranteed' in r['closing_reference']


def test_report_preserves_distinct_run_observations(db):
    save_odds_snapshot(quote(),db)
    other=quote(observed_utc='2026-10-31T21:00:00Z');other['payload']['run_id']='run2'
    save_odds_snapshot(other,db);save_odds_snapshot(quote('closing'),db)
    r=clv_report(db);assert r['exact_line']['n']==2
    assert {c['run_id'] for c in r['comparisons']}=={'run1','run2'}


def test_no_tracked_window_means_no_official_or_paid_request(monkeypatch,tmp_path):
    import closing_collector as collector,score_odds
    monkeypatch.setattr(collector,'ROOT',tmp_path)
    monkeypatch.setattr(collector,'tracked_predictions',lambda *a:[])
    official=Mock(side_effect=AssertionError('unexpected official call'))
    paid=Mock(side_effect=AssertionError('unexpected paid call'))
    monkeypatch.setattr(collector,'load_official_fixtures',official);monkeypatch.setattr(score_odds,'fetch',paid)
    r=collector.main(['--league','NHL']);assert r['paid_odds_requests']==0
    official.assert_not_called();paid.assert_not_called()


def test_quota_reporting_only_exposes_allowlisted_headers(monkeypatch):
    import live_odds
    response=Mock(status_code=200,headers={'x-requests-last':'3','x-requests-used':'11','x-requests-remaining':'489','secret-header':'never-copy'})
    response.json.return_value=[]
    monkeypatch.setattr(live_odds,'_api_key',lambda:'unit-test-key')
    monkeypatch.setattr(live_odds.requests,'get',Mock(return_value=response))
    usage={};live_odds._fetch_odds_key('icehockey_nhl','us','h2h,spreads,totals',usage=usage)
    assert usage=={'x-requests-last':'3','x-requests-used':'11','x-requests-remaining':'489'}


def test_kickoff_refusal_retains_paid_response_times_and_delta(db):
    save_odds_snapshot(quote(),db)
    r=collect([event(commence_time='2026-10-31T23:20:00Z')],'NHL',now=NOW,db_path=db,fixtures=[fixture()])
    detail=r['refused'][0]
    assert detail['provider_minus_official_seconds']==1200
    assert detail['official_kickoff_utc']==KICK
    assert detail['provider_kickoff_utc']=='2026-10-31T23:20:00Z'
    assert not r['captured']


def test_provider_late_within_tolerance_captures_on_the_league_deadline(db):
    # Measured live: the provider mirrored kickoff exactly 600s late. A late
    # mirror must not block the close; the league time stays the deadline.
    save_odds_snapshot(quote(),db)
    r=collect([event(commence_time='2026-10-31T23:10:00Z')],'NHL',now=NOW,db_path=db,fixtures=[fixture()])
    assert not r['refused'] and len(r['captured'])==1
    row=get_odds_snapshots(db,capture_kind='closing')[0]
    assert row['kickoff_utc']==KICK
    assert row['payload']['provider_minus_official_seconds']==600
    assert row['payload']['provider_kickoff_utc']=='2026-10-31T23:10:00+00:00'
    assert row['payload']['kickoff_deadline_utc']==KICK
    assert row['observed_utc']<KICK


def test_provider_early_kickoff_is_never_tolerated(db):
    save_odds_snapshot(quote(),db)
    r=collect([event(commence_time='2026-10-31T22:50:00Z')],'NHL',now=NOW,db_path=db,fixtures=[fixture()])
    assert not r['captured'] and 'earlier' in str(r['refused'])
    assert r['refused'][0]['provider_minus_official_seconds']==-600


def test_direct_store_and_quote_share_contemporaneous_identifier(db,monkeypatch):
    import core.historical_storage as storage
    from run_ncaaf import store
    monkeypatch.delenv('MSP_RUN_ID',raising=False)
    monkeypatch.setattr(storage,'DB_PATH',db)
    result=dict(sport='nhl',league='NHL',game_id='1',game_date='2026-10-31',home_team='A Club',away_team='B Club',
        fixture={'start_time':KICK},settlement={'scope':SCOPE},projection={'home_points':3.,'away_points':2.},
        markets=[dict(kind='moneyline',line=.5,price_a=120,price_b=-140,prob_a=.6,ev_a=.32,ev_b=-.3,
                      pick='HOME',recommendation='LEAN HOME',quote={'bookmaker':'book1','updated':OPEN,'source_event_id':'odds1','scope':SCOPE})])
    store(result)
    capture_prediction_odds(result,db,observed_utc=OPEN)
    import sqlite3,json
    with sqlite3.connect(db) as c:raw=json.loads(c.execute('select raw_json from predictions').fetchone()[0])
    archived=get_odds_snapshots(db)[0]
    assert raw['_odds_capture_run_id'].startswith('direct_')
    assert raw['_odds_capture_run_id']==archived['payload']['run_id']
    assert archived['payload']['run_id_basis']=='direct_forecast'


def test_workflow_run_id_reaches_the_nhl_snapshot(db,monkeypatch):
    # msp.py run --sport nhl passes MSP_RUN_ID to the child runner; the quote a
    # forecast used must point back at that workflow run, not a direct-run ID.
    import core.historical_storage as storage
    from run_ncaaf import store
    monkeypatch.setenv('MSP_RUN_ID','msp_nhltest0123')
    monkeypatch.setattr(storage,'DB_PATH',db)
    result=dict(sport='nhl',league='NHL',game_id='1',game_date='2026-10-31',home_team='A Club',away_team='B Club',
        fixture={'start_time':KICK},settlement={'scope':SCOPE},projection={'home_points':3.,'away_points':2.},
        markets=[dict(kind='moneyline',line=.5,price_a=120,price_b=-140,prob_a=.6,ev_a=.32,ev_b=-.3,
                      pick='HOME',recommendation='LEAN HOME',quote={'bookmaker':'book1','updated':OPEN,'source_event_id':'odds1','scope':SCOPE})])
    store(result)
    capture_prediction_odds(result,db,observed_utc=OPEN)
    import sqlite3,json
    with sqlite3.connect(db) as c:raw=json.loads(c.execute('select raw_json from predictions').fetchone()[0])
    archived=get_odds_snapshots(db)[0]
    assert raw['_odds_capture_run_id']=='msp_nhltest0123'
    assert archived['payload']['run_id']=='msp_nhltest0123'
    assert archived['payload']['run_id_basis']=='workflow'
    assert archived['event_key']=='NHL:1:moneyline:0.5'
