"""Competition identity, progressive lookup, hybrid preservation and quarantine."""
import json
import sqlite3
from unittest.mock import Mock

import pytest

import basketball_resolution as resolution
import basketball_runner as runner


DAY = '2026-10-26'


def history():
    return dict(league='NBL', updated=DAY, games=[dict(
        league='NBL', game_id='final', date='2026-10-24', season=2027,
        home_team='Sydney Kings', away_team='Perth Wildcats', home_score=100,
        away_score=80, completed=True, status='STATUS_FINAL', season_type=2)])


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(resolution, 'today', lambda: DAY)
    monkeypatch.setattr(runner, 'today', lambda: DAY)


@pytest.mark.parametrize('token,expected', [('NBL','NBL'), ('Australian NBL','NBL'),
    ('NZ_NBL','NZNBL'), ('NZ NBL','NZNBL'), ('NZNBL','NZNBL')])
def test_competitions_are_explicit(token, expected):
    assert resolution.canonical_league(token) == expected


def test_provider_key_is_verified_and_not_nz():
    from ingest_basketball_espn import LEAGUES
    assert LEAGUES['NBL'] == 'nbl'
    assert 'NZNBL' not in LEAGUES


def test_cross_competition_history_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(resolution, 'ROOT', tmp_path)
    (tmp_path / 'data').mkdir()
    (tmp_path / 'data/basketball_nbl_games.json').write_text(json.dumps(dict(league='NZNBL', games=[])))
    with pytest.raises(ValueError, match='Competition mismatch'):
        resolution.load_history('NBL')


def test_missing_local_refreshes_once_and_reloads_persisted_data(monkeypatch):
    source = history()
    lookup = Mock(side_effect=[dict(league='NBL',games=[]), source])
    fetch = Mock(return_value=source)
    monkeypatch.setattr(resolution, 'load_history', lookup)
    monkeypatch.setattr(resolution, 'refresh_history', fetch)
    data, _, notes = resolution.prepare('NBL','Sydney Kings','Unknown',DAY)
    assert data == source and lookup.call_count == 2
    fetch.assert_called_once_with('NBL', DAY)
    assert 'Supported public source refreshed' in notes


def test_sufficient_local_hit_has_zero_fetches(monkeypatch):
    source = history()
    source['games'] = [{**source['games'][0], 'game_id': str(i)} for i in range(80)]
    fixture = dict(home_team='Sydney Kings', away_team='Perth Wildcats')
    monkeypatch.setattr(resolution, 'load_history', lambda _: source)
    monkeypatch.setattr(resolution, 'find_fixture', lambda *a: fixture)
    fetch = Mock()
    monkeypatch.setattr(resolution, 'refresh_history', fetch)
    resolution.prepare('NBL','Sydney Kings','Perth Wildcats',DAY)
    fetch.assert_not_called()


def test_unknown_source_does_not_invent_provider(monkeypatch):
    assert resolution.refresh_history('Unregistered Competition', DAY) is None


def test_hybrid_keeps_known_scoring_and_only_replaces_missing_team():
    result = resolution.hybrid(history(),'Sydney Kings','Unknown',DAY)
    assert result['input_provenance']['home']['metrics']['points_for'] == 100
    assert result['input_provenance']['home']['metrics']['points_against'] == 80
    assert result['input_provenance']['home']['status'] == 'SOURCED'
    assert result['input_provenance']['away']['status'] == 'SUBSTITUTED'
    fields = {x['input'] for x in result['substitutions']}
    assert 'away.points_for' in fields and 'home.points_for' not in fields
    assert result['projection']['home_points'] != result['projection']['away_points']


def test_no_future_scores_or_other_season_in_hybrid():
    data = history()
    data['games'].append({**data['games'][0], 'game_id':'future', 'date':DAY, 'home_score':999})
    assert resolution.team_metrics(data,'Sydney Kings',DAY,2027)['points_for'] == 100
    assert resolution.team_metrics(data,'Sydney Kings',DAY,2026) == {}


def test_bad_final_is_not_promoted():
    data = history()
    data['games'][0]['home_score'] = float('nan')
    assert resolution.team_metrics(data,'Sydney Kings',DAY) == {}


def test_missing_fixture_without_opt_in_fails_without_write(monkeypatch):
    monkeypatch.setattr(runner, 'prepare', lambda *a,**k: (history(),None,[]))
    store = Mock()
    monkeypatch.setattr('run_ncaaf.store', store)
    with pytest.raises(SystemExit):
        runner.main(['--league','NBL','--match','Sydney Kings vs Unknown','--date',DAY])
    store.assert_not_called()


def test_opt_in_unknown_works_through_normal_runner_with_no_paid_fetch(monkeypatch):
    monkeypatch.setattr(runner, 'prepare', lambda *a,**k: (dict(league='UNLISTED', games=[]),None,[]))
    fetch = Mock()
    monkeypatch.setattr('score_odds.fetch', fetch)
    rows = runner.main(['--league','UNLISTED','--match','First Club vs Second Club',
                        '--date',DAY,'--exploratory','--dry-run','--odds'])
    assert rows[0]['exploratory'] and not rows[0]['fixture_verified']
    assert rows[0]['markets'][0]['stake_size'] is None
    fetch.assert_not_called()


def test_side_prices_and_spread_remap_but_total_does_not():
    from argparse import Namespace
    args = Namespace(moneyline=[['120','-140']], spread=[['2.5','-110','-120']],
                     total=[['175.5','-105','-115']])
    specs, _ = runner.market_specs(args, True)
    assert (specs[0]['price_a'], specs[0]['price_b']) == (-140,120)
    assert (specs[1]['line'], specs[1]['price_a'],specs[1]['price_b']) == (-2.5,-120,-110)
    assert specs[2]['line'] == 175.5 and specs[2]['price_a'] == -105


def test_scenario_pricing_disclosed_no_kelly_or_pick():
    result = resolution.hybrid(history(),'Sydney Kings','Unknown',DAY)
    result['markets'] = runner.scenario_markets(result,[dict(kind='moneyline',line=.5,price_a=-110,price_b=-110)])
    item = result['markets'][0]
    assert item['ev_a'] is not None
    assert item['pick'] in {'HOME','AWAY'} and item['stake_size'] is None
    from score_review import format_review
    text = format_review(result)
    assert 'EXPLORATORY COHORT' in text and 'assumption-based scenarios' in text
    assert 'Unknown' in text and 'SUBSTITUTED' in text


def test_exploratory_cannot_overwrite_verified_row_and_is_separately_graded(tmp_path):
    from core.historical_storage import init_db, store_prediction
    from grade_predictions import cohort_record
    db = tmp_path / 'history.db'
    init_db(db)
    shared = dict(game_date=DAY, event_key='NBL:one:moneyline',
                  markets=[dict(kind='moneyline',line=.5,pick='HOME',prob_a=.8,prob_b=.2,price_a=-110,price_b=-110)])
    for exploratory in (False,True):
        store_prediction('basketball','Sydney Kings','Unknown','moneyline',.8,.5,None,None,
            'INFO - EXPLORATORY' if exploratory else 'LEAN HOME',
            {**shared,'exploratory':exploratory},db,'NBL')
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute('SELECT cohort,is_exploratory FROM predictions ORDER BY id').fetchall()
        assert len(rows) == 2 and [r['is_exploratory'] for r in rows] == [0,1]
        conn.execute("UPDATE predictions SET result_outcome='win' WHERE is_exploratory=1")
        report = cohort_record(conn,'EXPLORATORY')
        assert report['overall']['n'] == 1


def test_msp_uses_nbl_score_route_and_accepts_aliases():
    from msp_workflow import run_command
    command = run_command('basketball',['Sydney Kings vs Perth Wildcats'],DAY,'Australian NBL',{},['--exploratory'])
    assert '--home' not in command and '--match' in command
    assert command[command.index('--league')+1] == 'NBL'
    # Prices are discovered automatically by default (2026-10-26 operational pass),
    # and manual lines still suppress the automatic quote fetch.
    assert '--odds' in command and '--exploratory' in command
    manual = run_command('basketball',['Sydney Kings vs Perth Wildcats'],DAY,'Australian NBL',{},
                         ['--moneyline','-104','-121'])
    assert '--odds' not in manual


def test_measured_partial_efficiency_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(resolution, 'ROOT', tmp_path)
    folder = tmp_path / 'data'
    folder.mkdir()
    (folder / 'basketball_stats.json').write_text(json.dumps({'Sydney Kings': dict(
        league='NBL', season=2027, updated=DAY, games=8, source='official box scores',
        pace=81, ortg=119)}))
    result = resolution.hybrid(history(), 'Sydney Kings', 'Unknown', DAY)
    home = result['input_provenance']['home']
    assert home['metrics']['pace'] == 81 and home['metrics']['ortg'] == 119
    assert home['metrics']['drtg'] == pytest.approx(80/81*100)
    assumed = {x['input'] for x in result['substitutions']}
    assert 'home.pace' not in assumed and 'home.ortg' not in assumed
    assert 'home.drtg' in assumed


def test_namesake_wrong_competition_or_undated_template_cannot_supply_rates(tmp_path, monkeypatch):
    monkeypatch.setattr(resolution, 'ROOT', tmp_path)
    (tmp_path/'data').mkdir()
    path = tmp_path/'data/basketball_stats.json'
    for record in [dict(league='NZNBL',season=2027,games=8,updated=DAY,source='official',pace=99),
                   dict(league='NBL',season=2027,games=8,source='template',pace=99)]:
        path.write_text(json.dumps({'Sydney Kings':record}))
        assert resolution.measured_rates('NBL','Sydney Kings',DAY,2027) == {}


def test_quarantine_dedup_does_not_hide_real_pick_or_block_observation_grading(tmp_path):
    from core.historical_storage import init_db, store_prediction
    import grade_predictions as grade
    db = tmp_path/'history.db'
    init_db(db)
    for exploratory in (False,True,False,True):
        store_prediction('basketball','Home','Away','moneyline',.8,.5,None,None,
            'INFO - EXPLORATORY' if exploratory else 'LEAN HOME',
            dict(game_date=DAY,event_key='same',exploratory=exploratory,
                 markets=[dict(kind='moneyline',line=.5,pick='HOME',prob_a=.8,prob_b=.2)]),db,'NBL')
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = list(conn.execute('SELECT * FROM predictions'))
        assert len(rows) == 2
        kept, _ = grade.newest_per_fixture(rows)
        assert len(kept) == 2
        conn.execute("UPDATE predictions SET result_outcome='win' WHERE is_exploratory=0")
        pending = list(conn.execute('SELECT * FROM predictions WHERE result_outcome IS NULL'))
        live, _ = grade.split_duplicates(conn,pending)
        assert len(live) == 1 and live[0]['cohort'] == 'EXPLORATORY'
        observation = dict(rows[1],result_outcome='win',profit_loss=1,
            recommendation='LEAN HOME', raw_json=json.dumps(dict(exploratory=True,
                _settled_at_recorded_price=True,_settled_odds=100)))
        assert grade.recorded_price_breakdown([observation])['overall']['n'] == 0
        assert grade.stake_weighted_breakdown([observation])['n'] == 0


def test_refreshed_data_promotes_to_existing_verified_engine(monkeypatch):
    fixture = dict(home_team='Perth Wildcats',away_team='Sydney Kings',start_time='2026-10-28T10:30:00Z')
    monkeypatch.setattr(runner, 'prepare', lambda *a,**k: (history(),fixture,['Supported public source refreshed']))
    model = Mock()
    monkeypatch.setattr('models.score_ratings.ScoreRatings', Mock(return_value=model))
    main = Mock(return_value=[{'verified':True}])
    monkeypatch.setattr('run_ncaaf.main',main)
    result = runner.main(['--league','NBL','--match','Sydney Kings vs Perth Wildcats',
                          '--date','2026-10-28','--dry-run','--moneyline','120','-140'])
    assert result == [{'verified':True}]
    argv = main.call_args.args[1]
    assert argv[argv.index('--moneyline')+1:] == ['-140.0','120.0']
    assert main.call_args.kwargs['prepared_models'][DAY] is model
