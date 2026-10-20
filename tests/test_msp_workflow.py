from contextlib import closing
import datetime as dt
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import msp_workflow as w
from core.historical_storage import init_db, TableTennisStore, workflow_cleanup, workflow_repair_dates, workflow_save_run, workflow_delivery
from ingest_nfl_schedule import resolve_fixture, parse_event


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.db=self.root/'history.db'
        init_db(self.db);TableTennisStore(self.db)

    def tearDown(self):self.tmp.cleanup()

    def row(self,ident,date,outcome=None):
        with closing(sqlite3.connect(self.db)) as c:
            c.execute("INSERT INTO predictions(id,sport,home_team,away_team,market_type,timestamp,game_date,recommendation,raw_json,result_outcome) VALUES(?,'nfl','A','B','total','2026-10-01',?,'OVER','{}',?)",(ident,date,outcome))
            c.commit()

    def test_cleanup_backup_manifest_and_only_explicit_unresolved(self):
        self.row(1,'2026-10-01');self.row(2,'2026-10-01','win');self.row(3,'2026-10-22')
        result=workflow_cleanup([1],[],'2026-10-19',self.root/'backup',self.db)
        with closing(sqlite3.connect(self.db)) as c:self.assertEqual([2,3],[r[0] for r in c.execute('SELECT id FROM predictions ORDER BY id')])
        with closing(sqlite3.connect(result['backup'])) as c:self.assertEqual(3,c.execute('SELECT count(*) FROM predictions').fetchone()[0])
        self.assertEqual(1,len(json.loads(Path(result['manifest']).read_text())['predictions']))

    def test_cleanup_refuses_graded_and_rolls_back(self):
        self.row(1,'2026-10-01');self.row(2,'2026-10-01','win')
        with self.assertRaises(ValueError):workflow_cleanup([1,2],[],'2026-10-19',self.root/'backup',self.db)
        with closing(sqlite3.connect(self.db)) as c:self.assertEqual(2,c.execute('SELECT count(*) FROM predictions').fetchone()[0])

    def test_cleanup_refuses_future(self):
        self.row(1,'2026-10-22')
        with self.assertRaises(ValueError):workflow_cleanup([1],[],'2026-10-19',self.root/'backup',self.db)

    def test_repair_preserves_grade(self):
        self.row(1,'2026-10-01','win');self.row(2,'2026-10-01')
        changes=[{'id':i,'date':'2026-10-04','fixture':{'game_id':'42'}} for i in [1,2]]
        workflow_repair_dates(changes,self.db)
        with closing(sqlite3.connect(self.db)) as c:
            self.assertEqual([('2026-10-01',),('2026-10-04',)],c.execute('SELECT game_date FROM predictions ORDER BY id').fetchall())

    def test_run_and_delivery_are_separate(self):
        workflow_save_run('msp_test','nfl','saved',{'x':1},self.db)
        workflow_delivery('msp_test','no_delivery',{'destinations':0},self.db)
        with closing(sqlite3.connect(self.db)) as c:
            self.assertEqual('saved',c.execute('SELECT status FROM workflow_runs').fetchone()[0])
            self.assertEqual('no_delivery',c.execute('SELECT status FROM workflow_deliveries').fetchone()[0])

    def test_refresh_has_all_groups_and_no_bare_python(self):
        plan=w.refresh_plan(date='2026-10-19')
        self.assertTrue(any(x[0]=='ingest_table_tennis_public.py' for x in plan))
        self.assertTrue(any(x[0]=='ingest_ncaaf_model.py' for x in plan))
        self.assertTrue(any(x[0]=='ingest_basketball_official.py' for x in plan))
        self.assertTrue(all(x[0].endswith('.py') for x in plan))

    def test_run_routes_root_table_tennis_and_dated_baseball(self):
        self.assertEqual('run_table_tennis.py',w.run_command('table-tennis',['A vs B'],'2026-10-20',None,{},[])[0])
        command=w.run_command('kbo',['KIA Tigers vs LG Twins'],'2026-10-20',None,{},[])
        self.assertIn('--no-discord',command);self.assertIn('--date',command)

    def test_saved_push_preserves_full_snapshot_and_never_runs_model(self):
        raw={'sport':'nfl','projection':{'home_points':24},'market_odds':{'home_ml':-150},'ev':.08}
        row={'sport':'nfl','league':'NFL','game_date':'2026-10-20','home_team':'A','away_team':'B','raw_json':json.dumps(raw)}
        saved={'run_id':'msp_saved','status':'saved','sport':'nfl','payload':{
            'predictions':[row,row],'table_tennis_runs':[],'research':None}}
        with patch.object(w,'saved_run',return_value=saved), \
             patch('discord_integration.push_prediction_to_all',return_value=1) as send, \
             patch('core.historical_storage.workflow_delivery') as receipt, \
             patch.object(w,'execute') as execute:
            self.assertEqual(1,w.push_saved('msp_saved'))
            send.assert_called_once_with('nfl',raw,dry_run=False)
            execute.assert_not_called()
            self.assertEqual('delivered_to_at_least_one_destination',receipt.call_args.args[1])

    def test_no_delivery_cannot_be_reported_as_success(self):
        saved={'run_id':'msp_saved','status':'saved','sport':'nfl','payload':{
            'predictions':[],'table_tennis_runs':[],'research':None}}
        with patch.object(w,'saved_run',return_value=saved),patch('core.historical_storage.workflow_delivery'):
            with self.assertRaisesRegex(ValueError,'No confirmed'):
                w.push_saved('msp_saved')

    def test_legacy_basketball_stats_lookup_does_not_use_cli_arguments(self):
        from universal_runner import get_team_stats
        with patch('team_stats_provider.get_basketball_team_stats',side_effect=[{'rating':1},{'rating':2}]) as lookup:
            self.assertEqual(({'rating':1},{'rating':2}),get_team_stats('basketball','A','B','KBL'))
            self.assertEqual(2,lookup.call_count)

    def test_no_child_delivery_flags_or_historical_forecasts(self):
        for flag in ['--push=1','--push-all','--no-fixture-check']:
            with self.assertRaises(ValueError):w.run('nfl',[],None,None,{},[flag])
        with self.assertRaisesRegex(ValueError,'future fixture'):
            w.run('nfl',[],'2000-01-01',None,{},[])

    def test_nfl_never_falls_back_season_or_completed(self):
        games=[{'game_id':'1','season':2025,'date':'2026-12-01','home_team':'A','away_team':'B','completed':False},
               {'game_id':'2','season':2026,'date':'2026-12-01','home_team':'A','away_team':'B','completed':True}]
        with patch('ingest_nfl_schedule.load_schedule',return_value=games):
            with self.assertRaises(ValueError):resolve_fixture('A','B',date='2026-12-01',season=2026)

    def test_nfl_unique_upcoming_fixture(self):
        games=[{'game_id':'3','season':2026,'date':'2026-12-01','home_team':'A','away_team':'B','completed':False}]
        with patch('ingest_nfl_schedule.load_schedule',return_value=games):
            self.assertEqual('3',resolve_fixture('A','B',date='2026-12-01',season=2026)['game_id'])

    def test_nfl_night_game_uses_eastern_date(self):
        side=lambda which:dict(homeAway=which,team={'displayName':which},score='7')
        event={'id':'99','date':'2026-10-20T00:15:00Z','competitions':[{'competitors':[side('home'),side('away')]}]}
        result=parse_event(event,2026,7)
        self.assertEqual('2026-10-19',result['date']);self.assertEqual(event['date'],result['start_time'])

    def test_two_way_nfl_tie_pushes_at_original_price(self):
        import grade_predictions as g
        row={'sport':'nfl','home_team':'A','away_team':'B','market_type':'moneyline','model_value':.6,'market_value':.5,'recommendation':'BET HOME','raw_json':json.dumps({'market_odds':{'home_ml':-130,'away_ml':110}})}
        self.assertEqual(('push','HOME',0.0,True,-130.0),g.grade_row(row,27,27))

    def test_kbo_final_requires_identity_date_and_status(self):
        from kbo_results import parse_final
        html='<div><h1>LG Twins</h1><div><div aria-label="LG 1, Kia 5"><span>1</span><span>:</span><span>5</span></div><p>Final</p></div><div>Kia Tigers</div></div>'
        result=parse_final(html,'https://mykbostats.com/games/14042-LG-vs-Kia-20261017','2026-10-17')
        self.assertEqual((5,1),(result['home_score'],result['away_score']))
        with self.assertRaises(ValueError):parse_final(html.replace('Final','Live'),'https://mykbostats.com/games/14042-LG-vs-Kia-20261017','2026-10-17')
        with self.assertRaises(ValueError):parse_final(html,'https://mykbostats.com/games/14042-LG-vs-Kia-20261017','2026-10-18')


if __name__=='__main__':unittest.main()
