"""Real MyStake label regression and independent paired historical oracles."""
import copy
import tempfile
import unittest
from pathlib import Path
from core.historical_storage import TableTennisStore,table_tennis_win_cover_gap
from table_tennis.browser_source import parse_capture,checked_url,capture_from_text

def snapshot():
    # Labels/prices observed on the public page; test data never imported live.
    return dict(url='https://mystake.com/us/sportsbook/prematch/match/77161115',
        captured_utc='2026-10-09T12:00:00Z',
        text='Table Tennis\nCzechia\nCzech Liga Pro\nPetr, Pavel\nVS\nSaturday, 10 October 02:00\nKubat, Vladimir',
        markets=[dict(title='2 Way',selections=[dict(name='1',price='1.70'),dict(name='2',price='2.04')]),
                 dict(title='Total',selections=[dict(name='Over (75.5)',price='1.79'),dict(name='Under (75.5)',price='1.92')]),
                 dict(title='Game Handicap',selections=[]),
                 dict(title='{!gamenr} game - total points',selections=[])])

class BrowserTests(unittest.TestCase):
    def parse(self,data=None,names='Pavel Petr vs Vladimir Kubat'):
        return parse_capture(data or snapshot(),names,'2026-10-10T02:00:00Z',5)

    def test_actual_labels_reverse_requested_names(self):
        e,q,notes=self.parse(names='Vladimir Kubat vs Pavel Petr')
        self.assertEqual(e['player_a'],'Petr, Pavel')
        self.assertEqual([(x['market'],x['line']) for x in q],[('moneyline',None),('points_total',75.5)])
        self.assertEqual(q[0]['price_a'],1.70)
        self.assertTrue(any('{!gamenr}' in x for x in notes))
        self.assertTrue(any('Game Handicap' in x for x in notes))

    def test_paired_signed_point_spreads(self):
        s=snapshot();s['markets'].append(dict(title='Point Handicap',selections=[dict(name='1 (-2.5)',price='1.91'),dict(name='2 (+2.5)',price='1.80')]))
        _,q,_=self.parse(s);self.assertEqual(q[-1]['line'],-2.5)
        self.assertEqual(q[-1]['price_b'],1.80)

    def test_copied_text_fallback(self):
        s=snapshot();text=s['text']+'\n2 Way\n1\n1.70\n2\n2.04\nTotal\nOver (75.5)\n1.79\nUnder (75.5)\n1.92'
        d=capture_from_text(text,s['url']);d['captured_utc']=s['captured_utc']
        self.assertEqual(len(self.parse(d)[1]),2)

    def test_joined_clipboard_labels_and_prices(self):
        s=snapshot()
        text=s['text'].replace('VS\nSaturday','VSSaturday')+'\n2 Way\n11.41\n22.71\nTotal\nOver (73.5)1.76\nUnder (73.5)1.95'
        d=capture_from_text(text,s['url']);d['captured_utc']=s['captured_utc']
        event,quotes,_=self.parse(d)
        self.assertEqual(event['player_a'],'Petr, Pavel')
        self.assertEqual([(q['price_a'],q['price_b']) for q in quotes],[(1.41,2.71),(1.76,1.95)])
        d['text']=text.replace('Czech Liga Pro','')
        with self.assertRaisesRegex(ValueError,'not verified Czech'):self.parse(d)

    def test_suspended_one_sided_and_invalid_prices(self):
        s=snapshot();s['markets'][1]['selections'][0]['suspended']=True
        self.assertEqual(len(self.parse(s)[1]),1)
        s['markets'][0]['selections'][0]['price']='0'
        with self.assertRaises(ValueError):self.parse(s)

    def test_reject_wrong_pair_wrong_league_past_start_and_urls(self):
        with self.assertRaises(ValueError):self.parse(names='Someone Else vs Vladimir Kubat')
        s=snapshot();s['text']=s['text'].replace('Czechia','Russia')
        with self.assertRaises(ValueError):self.parse(s)
        s=snapshot();s['captured_utc']='2026-10-11T12:00:00Z'
        with self.assertRaises(ValueError):self.parse(s)
        for url in ('https://evil.example/us/sportsbook/prematch/match/1','https://mystake.com/us/sportsbook/prematch/match/1?token=secret'):
            with self.assertRaises(ValueError):checked_url(url)

class GapTests(unittest.TestCase):
    def test_known_rates_threshold_and_push(self):
        rows=[dict(match_won=True,point_margin=4,point_handicap=-5.5)]*8
        rows+= [dict(match_won=False,point_margin=-3,point_handicap=5.5)]*2
        rows+= [dict(match_won=True,point_margin=5,point_handicap=-5)]
        out=table_tennis_win_cover_gap(rows,min_matches=10)
        self.assertEqual(out['match_win_percentage'],80)
        self.assertEqual(out['point_cover_percentage'],20)
        self.assertAlmostEqual(out['gap_percentage_points'],60)
        self.assertEqual(out['pushes'],1);self.assertTrue(out['flagged'])
        self.assertFalse(table_tennis_win_cover_gap(rows)['flagged'])

    def test_empty_invalid_and_no_large_gap(self):
        self.assertIsNone(table_tennis_win_cover_gap([])['gap_percentage_points'])
        self.assertFalse(table_tennis_win_cover_gap([dict(match_won=True,point_margin=9,point_handicap=-2.5)],min_matches=1)['flagged'])
        with self.assertRaises(ValueError):table_tennis_win_cover_gap([dict(match_won=1,point_margin=9,point_handicap=0)])

    def test_store_deduplicates_quotes_reverses_side_and_cutoff(self):
        with tempfile.TemporaryDirectory() as folder:
            store=TableTennisStore(Path(folder)/'test.db')
            e=dict(event_id='source:1',player_a='A',player_b='B',player_a_id='source:a',player_b_id='source:b',
                   league='Czech Liga Pro',country='CZ',best_of=5,status='finished',
                   start_utc='2026-01-01T12:00:00Z',end_utc='2026-01-01T12:30:00Z',
                   retrieved_utc='2026-01-01T13:00:00Z',source_url='https://source.example/match',
                   game_scores=[[11,9],[11,9],[11,9]],current_points=[0,0])
            store.upsert_event(e)
            q=dict(event_id='source:1',market='points_spread',line=-7.5,price_a=1.9,price_b=1.9,
                   bookmaker='Book',quoted_utc='2026-01-01T11:55:00Z',retrieved_utc='2026-01-01T11:55:00Z',
                   source_url='https://source.example/match',is_live=False)
            store.add_quote(q);q['quoted_utc']='2026-01-01T11:59:00Z';q['retrieved_utc']=q['quoted_utc'];store.add_quote(q)
            a=store.player_point_cover_gap('source:a',-7.5,'Book',as_of='2026-01-02T00:00:00Z',min_matches=1)
            b=store.player_point_cover_gap('source:b',7.5,'Book',as_of='2026-01-02T00:00:00Z',min_matches=1)
            self.assertEqual(a['settled_matches'],1);self.assertEqual(a['match_win_percentage'],100);self.assertEqual(a['point_cover_percentage'],0)
            self.assertEqual(b['match_win_percentage'],0);self.assertEqual(b['point_cover_percentage'],100)
            self.assertEqual(store.player_point_cover_gap('source:a',-7.5,'Book',as_of='2026-01-01T12:10:00Z')['settled_matches'],0)
            self.assertEqual(store.player_point_cover_gap('source:a',-6.5,'Book')['settled_matches'],0)

if __name__=='__main__':unittest.main()
