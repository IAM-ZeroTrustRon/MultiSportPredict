"""Presentation preserves every selection, signed handicaps and saved facts."""
import copy
import io
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from table_tennis.scoring import ScoringModel
from table_tennis.markets import references
from table_tennis.report import render,discord_embeds,push
from run_table_tennis import main

def report():
    d=ScoringModel(.51).match([], [0,0])
    return dict(run_id='tt_test',created_utc='2026-10-10T12:00:00Z',
        event=dict(player_a='Alice',player_b='Bob',event_id='test:1',start_utc='2026-10-10T14:00:00Z',status='scheduled'),
        strategy='MARKET-ANCHORED SCORING REFERENCE',forecast=d,
        observations=dict(player_a_history=0,player_b_history=0,h2h_matches=0,rest_minutes={'a':None,'b':None}),
        priced_markets=[dict(market='points_total',selection='Over',selection_line=73.5,price=2.,probability=.55,push_probability=0.,ev=.1,bookmaker='Book',quoted_utc='2026-10-10T12:00:00Z')],
        reference_markets=references(d),warnings=['Independent trained coverage unavailable.'])

class ReportTests(unittest.TestCase):
    def test_human_labels_signed_sides_and_ev_are_not_changed(self):
        r=report();before=copy.deepcopy(r);text=render(r)
        self.assertIn('Over 73.5 | Odds 2.00 | Win 55.0% | EV +10.0%',text)
        self.assertIn('A -5.5:',text);self.assertIn('B +5.5:',text)
        self.assertIn('unpriced projections; no EV',text)
        self.assertIn('Rest: A unknown | B unknown',text)
        self.assertIn('not a strong-bet designation',text)
        self.assertNotIn('points_total',text)
        self.assertEqual(r,before)

    def test_discord_omits_model_notes_but_retains_price_basis(self):
        r=report();pages=discord_embeds(r)
        fields=[f for page in pages for f in page['fields']]
        self.assertFalse(any('Model notes' in f['name'] for f in fields))
        self.assertTrue(any('PRICED' in f['name'] and 'EV +10.0%' in f['value'] for f in fields))
        self.assertTrue(any('NO PRICES / NO EV' in f['name'] for f in fields))
        self.assertIn('market-anchored',pages[0]['description'].lower())
        self.assertIn('Independent trained coverage unavailable.',render(r))

    def test_all_alternatives_paginate_within_discord_limits(self):
        r=report();base=r['priced_markets'][0]
        r['priced_markets']=[dict(base,selection='Selection_'+str(i),selection_line=60.5+i) for i in range(180)]
        pages=discord_embeds(r);self.assertGreater(len(pages),1)
        priced='\n'.join(f['value'] for page in pages for f in page['fields'] if 'PRICED' in f['name'])
        for i in range(180):self.assertIn(f"Selection_{i} {60.5+i:g} |",priced)
        for page in pages:
            self.assertLessEqual(len(page['title']),256)
            self.assertLessEqual(len(page['fields']),25)
            size=len(page['title'])+len(page['description'])+len(page['footer']['text'])
            for field in page['fields']:
                self.assertLessEqual(len(field['value']),1024)
                self.assertFalse(field['inline'])
                size+=len(field['name'])+len(field['value'])
            self.assertLessEqual(size,6000)
        with patch('discord_integration._broadcast_embed',return_value=1) as transport:
            self.assertEqual(push(r,dry_run=True),len(pages))
            keys=[call.kwargs['game_key'] for call in transport.call_args_list]
            self.assertEqual(keys[0],'table_tennis|test:1')
            self.assertEqual(len(set(keys)),len(pages))
            self.assertTrue(all(call.kwargs['dry_run'] for call in transport.call_args_list))

    def test_no_prices_and_negative_ev_do_not_make_a_pick(self):
        r=report();r['priced_markets']=[]
        self.assertIn('EV unavailable',render(r))
        r=report();r['priced_markets'][0]['ev']=-.05
        self.assertIn('No positive-EV priced selection',render(r))

    def test_show_prints_saved_prices_without_collection_or_forecast(self):
        r=report();stream=io.StringIO()
        with patch.object(sys,'argv',['run_table_tennis.py','--show','tt_test']), redirect_stdout(stream), patch('run_table_tennis.TableTennisStore') as store, patch('run_table_tennis.collect') as collect, patch('run_table_tennis.forecast') as forecast:
            store.return_value.run.return_value=r
            main()
            store.return_value.run.assert_called_once_with('tt_test')
            collect.assert_not_called();forecast.assert_not_called()
        self.assertIn('SAVED REPORT',stream.getvalue())
        self.assertIn('Win 55.0%',stream.getvalue())

    def test_latest_and_empty_saved_run_list(self):
        stream=io.StringIO()
        with patch.object(sys,'argv',['run_table_tennis.py','--show','latest']), redirect_stdout(stream), patch('run_table_tennis.TableTennisStore') as store:
            store.return_value.runs.return_value=[report()]
            main()
        self.assertIn('tt_test',stream.getvalue())
        with patch.object(sys,'argv',['run_table_tennis.py','--show','latest']), redirect_stdout(io.StringIO()), patch('run_table_tennis.TableTennisStore') as store:
            store.return_value.runs.return_value=[]
            with self.assertRaises(SystemExit) as exc:main()
        self.assertEqual(exc.exception.code,2)
