"""Public DOM parsing against independently checked real game-score targets."""
import copy
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
from core.historical_storage import TableTennisStore
from table_tennis.public_results import parse_match,checked_match_url,collect_public
from ingest_table_tennis_public import export_csv

def raw():
    # Real source: Urbaniec–Saleny 22 Sep 2026 18:00 UTC, 3–1, 71 points.
    return dict(url='https://www.sofascore.com/table-tennis/match/saleny-radim-urbaniec/gpRdsmyGg',
        captured_utc='2026-10-10T12:00:00Z',
        text='Table tennis Czechia Czech Liga Pro. Radim Urbaniec is playing against Saleny P. on Sep 22, 2026 at 6:00:00 PM UTC.',
        summary='Urbaniec R.\n3 - 1\nFinished\nSaleny P.',
        leagueLinks=[dict(href='/table-tennis/tournament/czech-republic/czech-liga-pro/19039#id:96742',name='Czech Liga Pro')],
        players=[dict(href='/table-tennis/player/urbaniec-radim/480756',name='Urbaniec R.',imageName='Radim Urbaniec'),
                 dict(href='/table-tennis/player/saleny-petr/828662',name='Saleny P.',imageName=None)],
        tables=[[['1st','2nd','3rd','4th','5th'],['11','5','11','11',''],['9','11','8','5','']]])

class PublicTests(unittest.TestCase):
    def test_progress_and_rejection_preserve_verified_result(self):
        event=parse_match(raw());messages=[];store=MagicMock()
        store.upsert_event.return_value='inserted'
        with patch('table_tennis.public_results.PublicResultsBrowser') as browser, patch('table_tennis.public_results.time.sleep'):
            source=browser.return_value.__enter__.return_value
            source.league_links.return_value=[raw()['url'],raw()['url']+'#id:123']
            source.match.side_effect=[(event,raw()),ValueError('Incomplete game points')]
            counts,notes=collect_public(store,recent_only=True,on_progress=messages.append)
        self.assertEqual(counts['inserted'],1)
        self.assertEqual(counts['rejected'],1)
        self.assertEqual(store.upsert_event.call_count,1)
        self.assertIn('Incomplete game points',notes)
        self.assertTrue(any('Checking match 2/2' in m for m in messages))
        self.assertIn('Rejected: Incomplete game points',messages)

    def test_real_match_oracle(self):
        e=parse_match(raw())
        self.assertEqual(e['start_utc'],'2026-09-22T18:00:00+00:00')
        self.assertEqual(e['player_a_id'],'sofascore:480756')
        self.assertEqual(e['player_b_id'],'sofascore:828662')
        self.assertEqual(e['game_scores'],[[11,9],[5,11],[11,8],[11,5]])
        self.assertEqual(sum(sum(s) for s in e['game_scores']),71)
        self.assertNotIn('end_utc',e)
        self.assertNotIn('odds',e)

    def test_same_pair_different_dates_do_not_overwrite(self):
        a=raw();b=copy.deepcopy(a);b['text']=b['text'].replace('Sep 22','Sep 23')
        self.assertNotEqual(parse_match(a)['event_id'],parse_match(b)['event_id'])
        b=raw();b['url']+='#id:17200000'
        self.assertEqual(parse_match(a)['event_id'],parse_match(b)['event_id'])

    def test_wrong_scope_partial_scores_future_example_rejected(self):
        bad=[]
        x=raw();x['leagueLinks'][0]['name']='TT Cup';bad.append(x)
        x=raw();x['text']=x['text'].replace('Czechia','Russia');bad.append(x)
        x=raw();x['summary']=x['summary'].replace('Finished','Live');bad.append(x)
        x=raw();x['tables'][0][2][3]='';bad.append(x)
        x=raw();x['tables'][0][1][0]='12';bad.append(x)
        x=raw();x['summary']=x['summary'].replace('3 - 1','3 - 0');bad.append(x)
        x=raw();x['text']=x['text'].replace(' UTC',' local');bad.append(x)
        x=raw();x['captured_utc']='2026-01-01T00:00:00Z';bad.append(x)
        x=raw();x['is_example']=True;bad.append(x)
        for x in bad:
            with self.subTest(x=x),self.assertRaises(ValueError):parse_match(x)

    def test_duplicate_table_and_unstable_player_id_rejected(self):
        x=raw();x['tables']*=2
        with self.assertRaises(ValueError):parse_match(x)
        x=raw();x['players'][0]['href']='/table-tennis/player/unknown'
        with self.assertRaises(ValueError):parse_match(x)
        with self.assertRaises(ValueError):checked_match_url('https://evil.example/table-tennis/match/a/b')

    def test_canonical_dedup_csv_and_correction(self):
        with tempfile.TemporaryDirectory() as folder:
            store=TableTennisStore(Path(folder)/'test.db');e=parse_match(raw())
            self.assertEqual(store.upsert_event(e),'inserted')
            self.assertEqual(store.upsert_event(e),'duplicate')
            e['game_scores'][0]=[11,8];self.assertEqual(store.upsert_event(e),'corrected')
            p=Path(folder)/'results.csv';self.assertEqual(export_csv(store,p),1)
            self.assertEqual(export_csv(store,p),1)
            with p.open(encoding='utf-8-sig',newline='') as handle:rows=list(csv.DictReader(handle))
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['points_b'],'32')

if __name__=='__main__':unittest.main()
