"""Clipboard variants and manual result imports with isolated storage."""
import copy
import io
import json
import os
import sys
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch
import pytest
from core.historical_storage import TableTennisStore
from table_tennis.browser_source import capture_from_text, parse_capture
from table_tennis.contracts import normalized_name, timestamp
from run_table_tennis import forecast, save, main
from grade_table_tennis import manual_final, import_final_file, grade

NOW='2026-10-11T18:00:00Z'
START='2026-10-12T02:00:00Z'
URL='https://mystake.com/us/sportsbook/prematch/match/77200433'
RAW='Czechia, Czech Liga Pro\n\n\nTrefny, Jan\n\nVSSunday, 11 October 22:00\n\nKrejci, Richard\n\n    All\n    Results\n    Totals\n\n2 Way\n12.92\n21.36\nTotal\nOver (72.5)1.74\nUnder (72.5)1.97\nOver (73.5)1.82\nUnder (73.5)1.88\nOver (74.5)1.91\nUnder (74.5)1.80'


def parsed(text=RAW):
    data=capture_from_text(text,URL)
    data['captured_utc']=NOW
    return parse_capture(data,'Jan Trefny vs Richard Krejci',START,5)


def test_real_paste_prices_and_missing_navigation_heading():
    event,quotes,_=parsed()
    assert event['player_a']=='Trefny, Jan'
    assert event['player_b']=='Krejci, Richard'
    assert [(q['market'],q['line'],q['price_a'],q['price_b']) for q in quotes]==[
        ('moneyline',None,2.92,1.36),('points_total',72.5,1.74,1.97),
        ('points_total',73.5,1.82,1.88),('points_total',74.5,1.91,1.80)]
    assert normalized_name('Briza, Frantisek')==normalized_name('František Bříza')
    changed=RAW.replace('Trefny, Jan','Jan Trefny').replace('VSSunday','vs\n\nSunday').replace('Czechia, Czech Liga Pro','CZECH REPUBLIC, CZECH   LIGA PRO')
    assert len(parsed(changed)[1])==4


def test_scope_wrong_pair_and_one_sided_moneyline_refused():
    for text in (RAW.replace('Czechia','Russia'),RAW.replace('Czech Liga Pro','Setka Cup'),
                 RAW.replace('Trefny, Jan','Someone Else'),RAW.replace('21.36',''),
                 RAW.replace('2 Way','Trefny, Jan\n2 Way')):
        with pytest.raises(ValueError):parsed(text)


@pytest.mark.parametrize('bare',[False,True])
def test_cli_saves_run_and_prints_id(tmp_path,bare):
    store=TableTennisStore(tmp_path/'isolated.db')
    folder=tmp_path/'data/table_tennis';folder.mkdir(parents=True)
    paste=folder/'current_match.txt';paste.write_text(RAW,encoding='utf-8')
    (folder/'current_match_config.json').write_text(json.dumps({'match':'Jan Trefny vs Richard Krejci','mystake_url':URL,'start_utc':START,'best_of':5}))
    os.utime(paste,(timestamp(NOW).timestamp(),timestamp(NOW).timestamp()))
    args=['run_table_tennis.py','--match','Jan Trefny vs Richard Krejci',
          '--mystake-url',URL,'--mystake-text-file',str(paste),
          '--start-utc',START,'--best-of','5']
    if bare:args=['run_table_tennis.py']
    out=io.StringIO()
    with patch('run_table_tennis.TableTennisStore',return_value=store),patch('run_table_tennis.ROOT',tmp_path),patch('run_table_tennis.utcnow',return_value=NOW),patch.object(sys,'argv',args),redirect_stdout(out):
        main()
    runs=store.runs();assert len(runs)==1
    run=runs[0]
    assert 'RUN_ID='+run['run_id'] in out.getvalue()
    assert run['run_id'].startswith('tt_')
    assert len(run['priced_markets'])==8
    assert 0<run['forecast']['p_match_a']<1
    for extension in ('json','md'):
        assert (tmp_path/'output/table_tennis'/f"{run['run_id']}.{extension}").exists()


def test_final_import_grades_original_identity_idempotently(tmp_path):
    store=TableTennisStore(tmp_path/'isolated.db')
    event,quotes,_=parsed()
    store.upsert_event(event)
    for q in quotes:store.add_quote(q)
    report=forecast(store,event,now=NOW,model_path=tmp_path/'absent.json')
    store.save_run(report)
    assert grade(store)['unfinished_or_invalid_runs']==1
    with patch('grade_table_tennis.utcnow',return_value='2026-10-12T03:00:00Z'):
        final=manual_final(store,report['run_id'],[[11,9],[8,11],[11,7],[11,6]],URL)
    assert final['player_a_id']==event['player_a_id']
    path=tmp_path/'final.json';path.write_text(json.dumps({'events':[final]}))
    assert import_final_file(store,path)==['corrected']
    result=grade(store)
    assert result['graded_selections']==8
    assert result['unfinished_or_invalid_runs']==0
    assert grade(store)['graded_selections']==8
    with store._connection() as connection:
        assert connection.execute('select count(*) from tt_grades').fetchone()[0]==8
    bad=copy.deepcopy(final);bad['player_a_id']='different:a'
    path.write_text(json.dumps({'events':[bad]}))
    with pytest.raises(ValueError):import_final_file(store,path)


def test_invalid_final_points_are_rejected(tmp_path):
    store=TableTennisStore(tmp_path/'isolated.db')
    event,quotes,_=parsed();store.upsert_event(event)
    for q in quotes:store.add_quote(q)
    report=forecast(store,event,now=NOW,model_path=tmp_path/'absent.json');store.save_run(report)
    with patch('grade_table_tennis.utcnow',return_value='2026-10-12T03:00:00Z'):
        for scores in ([[11,10],[11,9],[11,9]],[[11,9],[8,11]],[[11,9]]*4):
            with pytest.raises(ValueError):manual_final(store,report['run_id'],scores,URL)
    assert store.event(event['event_id'])['status']=='scheduled'
