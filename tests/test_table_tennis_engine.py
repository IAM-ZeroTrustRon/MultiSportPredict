"""Independent mathematical oracles and isolated end-to-end acceptance tests."""
import copy
from datetime import datetime,timedelta,timezone
import json
import math
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import Mock,patch
from core.historical_storage import TableTennisStore
from table_tennis.contracts import validate_event,validate_quote,identifier,utcnow,timestamp
from table_tennis.scoring import ScoringModel,settle_distribution
from table_tennis.sources import BetsApiAdapter,OddsApiIoAdapter,betsapi_event,oddsio_event,oddsio_quotes,bet365_prematch_quotes,sanitize,FeedError
from table_tennis.training import train,make_rows,history_before,load_model,point_from_match,reference_quote_details
from table_tennis.markets import current_quotes,evaluate,outcome
from table_tennis.report import render,push
from run_table_tennis import select_event,forecast
from ingest_table_tennis import import_file
from grade_table_tennis import grade

NOW='2026-01-02T12:00:00+00:00'
def event(status='scheduled',eid='betsapi:e1'):
    return dict(event_id=eid,provider='betsapi',provider_event_id=eid.split(':')[-1],
        player_a='Alice Novak SR',player_b='Bob Novak JR',player_a_id='betsapi:a',player_b_id='betsapi:b',
        league='Czech Liga Pro',country='CZ',start_utc='2026-01-02T12:30:00+00:00',
        retrieved_utc=NOW,source_url='https://provider.example/events',status=status,
        best_of=5,game_scores=[],current_points=[0,0])

def quote(market='moneyline',line=None):
    return dict(event_id='betsapi:e1',market=market,line=line,price_a=2.15,price_b=1.65,
        bookmaker='Test Book',quoted_utc=NOW,retrieved_utc=NOW,is_live=False,source_url='https://provider.example/odds')

class ScoringTests(unittest.TestCase):
    def test_independent_exact_score_oracles(self):
        d,tail=ScoringModel(.5).game_scores()
        for k in range(10):self.assertAlmostEqual(d[11,k],math.comb(10+k,k)/2**(11+k),places=13)
        reach=math.comb(20,10)/2**20
        for k in range(10):self.assertAlmostEqual(d[12+k,10+k],reach*.5**k*.25,places=13)
        self.assertAlmostEqual(sum(d.values())+tail,1,places=12)

    def test_deuce_and_advantage_expectations(self):
        s=ScoringModel(.6);den=.6**2+.4**2
        self.assertAlmostEqual(s.win(16,16),.36/den)
        self.assertAlmostEqual(s.remaining(11,10),1+.4*2/den)
        self.assertAlmostEqual(s.remaining(10,11),1+.6*2/den)
        self.assertEqual(s.remaining(12,10),0)

    def test_match_expected_games_and_points_independent_oracle(self):
        s=ScoringModel(.5);d=s.match()
        # Even BO5: P(3 games)=1/4, P(4)=3/8, P(5)=3/8.
        expected=3*.25+4*.375+5*.375
        self.assertAlmostEqual(d['expected_games'],expected)
        self.assertAlmostEqual(d['expected_points'],expected*s.remaining(),places=10)
        self.assertAlmostEqual(d['p_match_a'],.5)
        self.assertAlmostEqual(sum(d['total_points'].values()),1,places=10)

    def test_live_played_margin_preserved(self):
        d=ScoringModel(.5).match([(11,0),(0,11)],(8,2))
        self.assertAlmostEqual(d['expected_point_margin'],6)
        self.assertGreater(d['p_match_a'],.5)
        self.assertTrue(all(k>=30 for k in d['total_points']))

    def test_symmetry(self):
        a=ScoringModel(.55).match();b=ScoringModel(.45).match()
        self.assertAlmostEqual(a['p_match_a']+b['p_match_a'],1)
        self.assertAlmostEqual(a['expected_point_margin'],-b['expected_point_margin'])
        self.assertAlmostEqual(a['expected_points'],b['expected_points'])

    def test_invalid_scores(self):
        for p in (0,1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):ScoringModel(p)
        for s in ((-1,0),(1.5,0),(12,0)):
            with self.assertRaises(ValueError):ScoringModel(.5).win(*s)
        with self.assertRaises(ValueError):ScoringModel(.5).match([(11,1)]*3)

    def test_push_and_signed_spread(self):
        self.assertEqual(settle_distribution({-1:.2,0:.3,1:.5},0),( .5,.2,.3))
        self.assertEqual(settle_distribution({-1:.2,0:.3,1:.5},-1,True),(0,.5,.5))

class ContractTests(unittest.TestCase):
    def test_league_isolation_and_missing_identity(self):
        for league,country in [('Russian Liga Pro','RU'),('Setka Cup','UA'),('Czech TT Cup','CZ'),('Czech Liga Pro',None)]:
            e=event();e.update(league=league,country=country)
            with self.assertRaises(ValueError):validate_event(e)
        for value in (None,'../secret','betsapi:None',''):
            with self.assertRaises(ValueError):identifier(value)

    def test_finished_legal_scores(self):
        e=event('finished');e['retrieved_utc']='2026-01-02T14:00:00Z';e['game_scores']=[[11,8],[9,11],[13,11],[11,4]]
        self.assertEqual(len(validate_event(e)['game_scores']),4)
        e['game_scores'].append([11,5])
        with self.assertRaises(ValueError):validate_event(e)

    def test_quotes_reject_fake_or_ambiguous_inputs(self):
        for change in ({'price_a':None},{'price_a':float('nan')},{'price_a':1},{'market':'Spread'},{'line':3.25,'market':'games_total'},{'is_live':None}):
            q=quote();q.update(change)
            with self.assertRaises((ValueError,TypeError)):validate_quote(q)

    def test_stale_and_future_quotes_excluded(self):
        q=quote();q['quoted_utc']='2025-12-31T12:00:00Z'
        future=quote();future['quoted_utc']='2026-01-02T13:00:00Z'
        fresh,rejected=current_quotes([q,future],event(),NOW)
        self.assertEqual(fresh,[]);self.assertEqual(len(rejected),2)

    def test_ambiguous_pair_requires_id_and_generations_preserved(self):
        a=event();b=event(eid='betsapi:e2')
        with self.assertRaises(ValueError):select_event([a,b],'Alice Novak SR vs Bob Novak JR',now=NOW)
        self.assertEqual(select_event([a,b],event_id=a['event_id'],now=NOW)['event_id'],a['event_id'])
        with self.assertRaises(ValueError):select_event([a],'Alice Novak vs Bob Novak',now=NOW)

class SourceTests(unittest.TestCase):
    def test_real_request_paths_and_credentials_not_crossed(self):
        for cls,path in ((BetsApiAdapter,'/v3/events/upcoming'),(OddsApiIoAdapter,'/events')):
            session=Mock();response=Mock(status_code=200);response.json.return_value={'success':1,'results':[]}
            session.get.return_value=response
            adapter=cls(session=session,archive=False);adapter.key='test-only'
            adapter.get(path,sport_id=92)
            self.assertTrue(session.get.called)
            self.assertEqual(session.get.call_args.args[0],adapter.base_url+path)
            adapter.close();session.close.assert_called_once()

    def test_missing_key_and_http_error_redacted(self):
        adapter=BetsApiAdapter(archive=False);adapter.key=None
        with self.assertRaises(FeedError):adapter.get('/test')
        session=Mock();session.get.return_value=Mock(status_code=403)
        adapter=BetsApiAdapter(session=session,archive=False);adapter.key='secret-never-print'
        try:adapter.get('/test')
        except FeedError as exc:self.assertNotIn('secret-never-print',str(exc))
        else:self.fail('403 not rejected')

    def test_sanitization(self):
        safe=sanitize({'token':'secret','url':'https://example.com/api?apiKey=secret','nested':{'Authorization':'Bearer secret'}})
        self.assertNotIn('secret',json.dumps(safe))
        q=quote();q['source_url']='https://provider.example/odds?apiKey=secret'
        self.assertNotIn('secret',json.dumps(validate_quote(q)))

    def test_native_betsapi_parse_and_scope(self):
        raw=dict(id='1',sport_id='92',time='1701855000',time_status='3',
            league={'name':'Czech Liga Pro','cc':'cz'},home={'id':'a','name':'Alice'},away={'id':'b','name':'Bob'},
            scores={str(i+1):{'home':a,'away':b} for i,(a,b) in enumerate([(11,7),(9,11),(11,5),(9,11),(13,11)])})
        e=betsapi_event(raw,'https://api.b365api.com/v1/event/view')
        self.assertEqual(sum(a for a,b in e['game_scores']),53)
        raw['league']['cc']='ru'
        with self.assertRaises(ValueError):betsapi_event(raw,'https://provider.example')

    def test_live_does_not_invent_zero_points(self):
        raw=dict(id='1',sport_id='92',time='1701855000',time_status='1',league={'name':'Czech Liga Pro','cc':'cz'},home={'id':'a','name':'Alice'},away={'id':'b','name':'Bob'},scores={})
        with self.assertRaises(ValueError):betsapi_event(raw,'https://provider.example')

    def test_oddsio_unit_mapping_and_all_alternative_lines(self):
        e=event(eid='oddsio:e1');e['player_a_id']='oddsio:a';e['player_b_id']='oddsio:b';e['provider_event_id']='e1'
        raw=dict(id='e1',homeId='a',awayId='b',bookmakers={'Book':[
            {'name':'Total Games','updatedAt':NOW,'odds':[{'hdp':3.5,'over':1.5,'under':2.7},{'hdp':4.5,'over':2.8,'under':1.4}]},
            {'name':'Spread','updatedAt':NOW,'odds':[{'hdp':-1.5,'home':2,'away':2}]}]})
        quotes,notes=oddsio_quotes(raw,e)
        self.assertEqual([q['line'] for q in quotes],[3.5,4.5]);self.assertEqual(len(notes),1)
        raw['homeId']='b'
        with self.assertRaises(ValueError):oddsio_quotes(raw,e)

    def test_full_bet365_alternatives_and_reversal(self):
        raw={'main':{'updated_at':NOW,'sp':{
            'points':{'name':'Alternative Total Points','odds':[
                {'header':'Over','name':'74.5','odds':'1.9'}, {'header':'Under','name':'74.5','odds':'1.9'},
                {'header':'Over','name':'76.5','odds':'2.1'}, {'header':'Under','name':'76.5','odds':'1.7'}]},
            'games':{'name':'Alternative Set Handicap','odds':[
                {'header':'1','name':'-1.5','odds':'2.4'}, {'header':'2','name':'+1.5','odds':'1.5'}]}}}}
        qs,notes=bet365_prematch_quotes(raw,event(),True)
        self.assertEqual(len(qs),3)
        spread=[q for q in qs if q['market']=='games_spread'][0]
        self.assertEqual((spread['line'],spread['price_a'],spread['price_b']),(1.5,1.5,2.4))
        self.assertEqual([q['line'] for q in qs if q['market']=='points_total'],[74.5,76.5])

    def test_full_bet365_event_id_confirmed(self):
        adapter=BetsApiAdapter(archive=False)
        e=event();e['player_a']='Alice';e['player_b']='Bob'
        adapter._book_events[e['start_utc'][:10]]=[dict(id='book123',time=str(int(timestamp(e['start_utc']).timestamp())),
            league={'name':'Czech Liga Pro'},home={'name':'Alice'},away={'name':'Bob'})]
        with patch.object(adapter,'get',return_value={'results':[{'event_id':'wrong'}]}) as request:
            qs,notes=adapter.full_prematch_quotes(e)
            self.assertEqual(qs,[])
            self.assertIn('canonical',notes[0])
            self.assertEqual(request.call_args.args[0],'/v4/bet365/prematch')

class StoreAndPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'multisport_history.db'
        self.store=TableTennisStore(self.path)
    def tearDown(self):self.temp.cleanup()

    def test_restart_dedup_and_status_correction(self):
        e=event();self.assertEqual(self.store.upsert_event(e),'inserted')
        self.assertEqual(TableTennisStore(self.path).upsert_event(e),'duplicate')
        e['status']='cancelled';self.assertEqual(self.store.upsert_event(e),'corrected')
        self.assertEqual(self.store.event(e['event_id'])['store_version'],2)

    def test_immutable_runs_and_end_to_end_market_report(self):
        e=event();self.store.upsert_event(e);self.store.add_quote(quote())
        for market,line in [('games_total',3.5),('games_spread',-1.5),('points_total',74),('points_spread',-3),('first_game_total',19.5)]:
            self.store.add_quote(quote(market,line))
        report=forecast(self.store,e,now=NOW,model_path=Path(self.temp.name)/'missing.json')
        self.assertEqual(len(report['priced_markets']),12)
        self.assertIn('MODEL REFERENCE',render(report))
        self.assertIn('Point handicap',render(report))
        self.assertAlmostEqual(report['forecast']['p_match_a'],(1/2.15)/(1/2.15+1/1.65),places=8)
        self.assertEqual(report['strategy'],'MARKET-ANCHORED SCORING REFERENCE')
        self.store.save_run(report)
        with self.assertRaises(Exception):self.store.save_run(report)
        self.assertEqual(self.store.run(report['run_id'])['run_id'],report['run_id'])

    def test_unknown_player_without_odds_refused(self):
        e=event();self.store.upsert_event(e)
        with self.assertRaises(ValueError):forecast(self.store,e,now=NOW,model_path=Path(self.temp.name)/'missing.json')

    def test_quote_event_mismatch(self):
        with self.assertRaises(ValueError):self.store.add_quote(quote())

    def test_import_examples_and_invalid_exports_refused(self):
        f=Path(self.temp.name)/'export.json';f.write_text(json.dumps({'example':True,'events':[event()]}))
        with self.assertRaises(ValueError):import_file(self.store,f)
        self.assertEqual(self.store.stats()['tt_events'],0)

    def test_real_discord_transport_called_without_network(self):
        e=event();self.store.upsert_event(e);self.store.add_quote(quote())
        report=forecast(self.store,e,now=NOW,model_path=Path(self.temp.name)/'missing.json')
        with patch('discord_integration._broadcast_embed',return_value=1) as transport:
            self.assertEqual(push(report),1)
            self.assertEqual(transport.call_args.kwargs['game_key'],'table_tennis|betsapi:e1')

    def test_grading_push_and_correction(self):
        e=event();self.store.upsert_event(e);self.store.add_quote(quote('points_total',72))
        self.store.add_quote(quote())
        run=forecast(self.store,e,now=NOW,model_path=Path(self.temp.name)/'missing.json');self.store.save_run(run)
        e.update(status='finished',game_scores=[[11,8],[11,8],[11,8]],retrieved_utc='2026-01-02T14:00:00Z',end_utc='2026-01-02T13:00:00Z')
        self.store.upsert_event(e)
        result=grade(self.store)
        self.assertEqual(result['graded_selections'],4)
        self.assertEqual(grade(self.store)['graded_selections'],4)
        self.assertEqual(self.store.stats()['tt_grades'],4)

class TrainingTests(unittest.TestCase):
    def test_current_anchor_hours_before_start_keeps_historical_closing_filter(self):
        q=quote();e=event();e['start_utc']='2026-01-02T16:00:00+00:00'
        self.assertIsNone(reference_quote_details([q],e['start_utc']))
        self.assertIsNotNone(reference_quote_details([q],e['start_utc'],max_lead_seconds=None))
        with tempfile.TemporaryDirectory() as folder:
            store=TableTennisStore(Path(folder)/'test.db');store.upsert_event(e);store.add_quote(q)
            self.assertEqual(forecast(store,e,now=NOW)['strategy'],'MARKET-ANCHORED SCORING REFERENCE')
            with self.assertRaises(ValueError):forecast(store,e,now='2026-01-02T12:10:00+00:00')

    def dataset(self,n=230):
        rng=random.Random(812);out=[];start=datetime(2025,1,1,tzinfo=timezone.utc)
        for i in range(n):
            e=event('finished','betsapi:'+str(i));time=start+timedelta(days=i)
            games=[];ga=gb=0
            while max(ga,gb)<3:
                a=b=0
                while max(a,b)<11 or abs(a-b)<2:
                    if rng.random()<.53:a+=1
                    else:b+=1
                games.append([a,b]);ga+=a>b;gb+=b>a
            e.update(start_utc=time.isoformat(),end_utc=(time+timedelta(minutes=25)).isoformat(),game_scores=games,retrieved_utc=utcnow())
            out.append(validate_event(e))
        return out

    def test_no_same_time_or_future_leakage(self):
        events=self.dataset(12);last=events[-1]
        h=history_before(events,last['start_utc'])
        self.assertEqual(h.counts['betsapi:a'],11)
        future=copy.deepcopy(last);future['event_id']='betsapi:future';future['start_utc']='2027-01-01T00:00:00Z';future['end_utc']='2027-01-01T01:00:00Z'
        h2=history_before(events+[future],last['start_utc'])
        self.assertEqual(h.ratings['betsapi:a'],h2.ratings['betsapi:a'])

    def test_fit_chronological_holdout_and_artifact(self):
        events=self.dataset()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'model.json';model=train(events,{},path)
            self.assertEqual(model['training_matches'],222)
            self.assertGreaterEqual(model['strength_holdout']['matches'],30)
            self.assertIsNone(model['market_weights'])
            self.assertEqual(load_model(path,'2026-01-01T00:00:00Z')['schema'],1)
            with self.assertRaises(ValueError):load_model(path,'2025-01-01T00:00:00Z')

    def test_market_model_fits_only_preevent_quotes(self):
        events=self.dataset();quotes={}
        for e in events:
            q=quote();q['event_id']=e['event_id']
            q['quoted_utc']=(timestamp(e['start_utc'])-timedelta(minutes=10)).isoformat()
            q['retrieved_utc']=q['quoted_utc'];quotes[e['event_id']]=[q]
        with tempfile.TemporaryDirectory() as folder:
            model=train(events,quotes,Path(folder)/'model.json')
            self.assertIsNotNone(model['market_weights'])
            self.assertGreaterEqual(model['market_holdout']['matches'],30)
        for e in events:quotes[e['event_id']][0]['quoted_utc']=e['end_utc']
        self.assertTrue(all(r['market'] is None for r in make_rows(events,quotes)))

    def test_too_little_data_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):train(self.dataset(10),{},Path(folder)/'model.json')

    def test_match_to_point_inversion(self):
        for probability in (.05,.25,.5,.8,.95):
            s=ScoringModel(point_from_match(probability));g=s.win()
            self.assertAlmostEqual(g**3*(1+3*(1-g)+6*(1-g)**2),probability,places=10)

if __name__=='__main__':unittest.main()
