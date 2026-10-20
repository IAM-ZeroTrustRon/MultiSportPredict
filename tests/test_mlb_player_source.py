import copy
import pytest
from mlb_player_source import parse_metrics, splits, session
from predict_mlb_advanced import MLBAdvancedPredictor


def feeds():
    def block(group, stat):
        return {'stats': [{'group': {'displayName': group}, 'totalSplits': 1,
            'splits': [{'season': '2026', 'player': {'id': 42, 'fullName': 'Verified Player'}, 'stat': stat}]}]}
    pitching = block('pitching', {'outs': 31, 'battersFaced': 45, 'strikeOuts': 10, 'era': '2.61'})
    hitting = block('hitting', {'plateAppearances': 60, 'atBats': 50, 'hits': 15, 'totalBases': 25})
    return pitching, hitting, 'player_id,year,woba,est_woba\n42,2026,.345,.999\n'


def test_official_counts_rates_and_measured_woba_feed_actual_consumer():
    result = parse_metrics(*feeds(), 2026)
    pitcher = result['pitchers'][0]
    assert pitcher['ip'] == pytest.approx(31 / 3)
    assert pitcher['k_per_9'] == pytest.approx(270 / 31)
    assert pitcher['k_rate'] == pytest.approx(10 / 45)
    assert result['hitters'][0]['woba'] == .345
    assert result['hitters'][0]['iso'] == .2
    assert result['hitters'][0]['tb_per_pa'] == pytest.approx(25 / 60)
    model = MLBAdvancedPredictor(result)
    assert model._hitter('Verified Player')['player_id'] == 42


@pytest.mark.parametrize('fault', ['season', 'truncated', 'duplicate'])
def test_refuses_wrong_season_truncation_and_duplicate_ids(fault):
    pitching, hitting, csv = feeds()
    block = pitching['stats'][0]
    if fault == 'season': block['splits'][0]['season'] = '2025'
    elif fault == 'truncated': block['totalSplits'] = 2
    else:
        block['splits'].append(copy.deepcopy(block['splits'][0])); block['totalSplits'] = 2
    with pytest.raises(ValueError): parse_metrics(pitching, hitting, csv, 2026)


def test_missing_measured_woba_never_uses_expected_woba():
    pitching, hitting, csv = feeds()
    with pytest.raises(ValueError):
        parse_metrics(pitching, hitting, csv.replace('.345', ''), 2026)


def test_retries_transient_statuses_but_never_403():
    with session() as client:
        retry = client.get_adapter('https://').max_retries
        assert 503 in retry.status_forcelist
        assert 403 not in retry.status_forcelist
