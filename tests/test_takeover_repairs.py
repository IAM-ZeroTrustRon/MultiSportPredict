"""Regression cases reproduced during the October 24 takeover audit."""
import math

import pytest

from core.market_handicapper import devig_power
from models.score_ratings import fair_probabilities
import msp_workflow as workflow
import grade_predictions as grading
import json

def row(ident, stake_size=None, raw=None, **updates):
    value=dict(id=ident,sport="tennis",league=None,home_team=f"Home {ident}",away_team=f"Away {ident}",game_date="2026-10-20",market_type="moneyline",recommendation="BET HOME",result_outcome="win",profit_loss=1.5,stake_size=stake_size,raw_json=json.dumps(raw if raw is not None else {"_settled_at_recorded_price":True,"_settled_odds":150}))
    value.update(updates)
    return value


@pytest.mark.parametrize("probabilities", [
    [.5, .5], [1/2.2, 1/2.2], [.7, .4], [.999, .999], [.2, .3, .2],
])
def test_power_solver_handles_underround_overround_and_large_exponent(probabilities):
    fair = devig_power(probabilities)
    assert sum(fair) == pytest.approx(1, abs=1e-7)
    assert all(0 < p < 1 for p in fair)
    assert sorted(range(len(fair)), key=fair.__getitem__) == sorted(range(len(probabilities)), key=probabilities.__getitem__)
    exponents = [math.log(p)/math.log(q) for p, q in zip(fair, probabilities)]
    assert max(exponents)-min(exponents) < 1e-8


@pytest.mark.parametrize("probabilities", [[], [.5], [0,.5], [1,.5], [-.1,.5], [float('nan'),.5], [float('inf'),.5], [True,.5]])
def test_power_solver_refuses_invalid_market_probabilities(probabilities):
    with pytest.raises(ValueError):
        devig_power(probabilities)


def test_underround_prices_remain_a_complete_binary_probability_pair():
    assert fair_probabilities(120,120) == pytest.approx((.5,.5), abs=1e-7)
    with pytest.raises(ValueError):
        devig_power([.7,.4], max_iter=1)


@pytest.mark.parametrize("sport,league", [("basketball","NBA"),("ncaaf",None)])
@pytest.mark.parametrize("manual", [["--moneyline","-142","120"], ["--spread","-2.5","-110","-110"], ["--total","221.5","-110","-110"], ["--total=221.5","-110","-110"]])
def test_manual_score_prices_do_not_add_automatic_odds(sport,league,manual):
    command=workflow.run_command(sport,["Boston Celtics vs New York Knicks"],"2026-10-23",league,{},manual)
    assert '--odds' not in command
    assert command[-len(manual):] == manual


@pytest.mark.parametrize("sport,league", [("basketball","NBA"),("ncaaf",None)])
def test_automatic_score_prices_still_requested_exactly_once(sport,league):
    for extra in ([],['--odds']):
        command=workflow.run_command(sport,[],"2026-10-23",league,{},extra)
        assert command.count('--odds') == 1


@pytest.mark.parametrize("raw", [{}, {'_settled_at_recorded_price':False,'_settled_odds':150}, {'_settled_at_recorded_price':True,'_settled_odds':0}])
def test_weighted_report_cannot_count_assumed_or_missing_prices(raw):
    report=grading.stake_weighted_breakdown([row(1,stake_size=.025,raw=raw)])
    assert report['n']==0 and report['roi'] is None
    assert report['excluded_unverified_settlement']==1
    assert report['excluded_without_stake']==0
    assert report['excluded_total']==1


def test_newer_unverified_stake_does_not_resurrect_old_verified_row():
    old=row(1,stake_size=.025)
    newer=row(2,stake_size=.025,home_team=old['home_team'],away_team=old['away_team'],raw={})
    report=grading.stake_weighted_breakdown([old,newer])
    assert report['n']==0 and report['excluded_unverified_settlement']==1
