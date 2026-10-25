import datetime as dt
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from models.score_ratings import ScoreRatings, market_probability, price_market
from core.historical_storage import init_db, store_prediction
from grade_predictions import newest_per_fixture
from score_odds import for_fixture
from tennis_context import apply_context, hold_probability
from sports_feed import parse_game
from ingest_basketball_official import parse_nz_schedule


class ScoreEngineTests(unittest.TestCase):
    def history(self):
        start = dt.date(2026, 1, 1)
        return [dict(game_id=str(i), date=(start+dt.timedelta(days=i)).isoformat(),
                     completed=True, home_team='A' if i%2 else 'B',
                     away_team='B' if i%2 else 'A', home_score=80+(i*7)%21,
                     away_score=70+(i*11)%23) for i in range(120)]

    def test_future_results_do_not_change_model(self):
        history = self.history()
        base = ScoreRatings(history, '2026-05-01')
        future = dict(history[0], game_id='future', date='2026-05-01', home_score=999)
        other = ScoreRatings(history+[future], '2026-05-01')
        self.assertEqual(base.predict('A', 'B'), other.predict('A', 'B'))
        self.assertGreater(base.validation['games'], 20)

    def test_home_signed_spread_and_push(self):
        self.assertAlmostEqual(market_probability(7, 10, -7, True)[0],
                               market_probability(-7, 10, 7, True)[1])
        win, lose, push = market_probability(7, 10, -7, True)
        self.assertGreater(push, 0)
        self.assertAlmostEqual(win+lose+push, 1)
        self.assertEqual(market_probability(7, 10, -7.5, True)[2], 0)
        with self.assertRaises(ValueError):
            market_probability(7, 10, -7.25, True)

    def test_unpriced_market_passes_and_ev_includes_push(self):
        self.assertIsNone(price_market('total', 150, (.55, .4, .05))['pick'])
        priced = price_market('total', 150, (.55, .4, .05), 100, -110)
        self.assertAlmostEqual(priced['ev_a'], .15)
        self.assertEqual(priced['pick'], 'OVER')

    def test_devig_fair_probabilities_and_quarter_kelly_stake(self):
        market = price_market('moneyline', .5, (.60, .40, 0), 120, -140)
        self.assertAlmostEqual(market['fair_prob_a'] + market['fair_prob_b'], 1.0, places=6)
        self.assertLess(market['fair_prob_a'], .60)
        # EV stays on the model probability against the offered price.
        self.assertAlmostEqual(market['ev_a'], .60*1.20 - .40)
        fair_ev = market['fair_prob_a']*1.20 - market['fair_prob_b']
        self.assertLess(fair_ev, 0)
        self.assertLess(fair_ev, market['ev_a'])
        # f* = EV/(D-1); quarter of it, capped at 5% of bankroll.
        expected = min(((.60*1.20-.40)/(2.20-1))*.25, .05)
        self.assertAlmostEqual(market['stake_size'], expected)
        self.assertEqual(market['pick'], 'HOME')
        self.assertIn('quarter-Kelly', market['stake_basis'])

    def test_small_edge_stake_is_not_capped(self):
        market = price_market('moneyline', .5, (.55, .45, 0), 105, -125)
        ev = .55*1.05 - .45
        self.assertGreaterEqual(ev, .05)
        self.assertAlmostEqual(market['stake_size'], (ev/1.05)*.25)
        self.assertLess(market['stake_size'], .05)

    def test_stake_is_unavailable_without_a_binary_price_pair(self):
        push = price_market('total', 6, (.5, .40, .10), -110, -110)
        self.assertEqual(push['pick'], 'OVER')
        self.assertIsNone(push['stake_size'])
        self.assertIsNone(push['fair_prob_a'])
        self.assertIn('push', push['stake_basis'])
        self.assertIsNone(price_market('moneyline', .5, (.55, .45, 0))['stake_size'])
        below = price_market('moneyline', .5, (.51, .49, 0), -110, -110)
        self.assertIsNone(below['pick'])
        self.assertIsNone(below['stake_size'])

    def test_stake_size_persists_and_defaults_to_null(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'history.db'
            init_db(path)
            store_prediction('nhl', 'A', 'B', 'moneyline', .6, .5, 10, None, 'LEAN HOME',
                             dict(event_key='NHL:1:moneyline'), path, 'NHL', stake_size=.025)
            store_prediction('nhl', 'C', 'D', 'moneyline', .6, .5, 10, None, 'LEAN HOME',
                             dict(event_key='NHL:2:moneyline'), path, 'NHL')
            with sqlite3.connect(path) as conn:
                rows = dict(conn.execute('SELECT event_key, stake_size FROM predictions'))
            conn.close()
            self.assertEqual(rows['NHL:1:moneyline'], .025)
            self.assertIsNone(rows['NHL:2:moneyline'])
            with self.assertRaises(ValueError):
                store_prediction('nhl', 'E', 'F', 'moneyline', .6, .5, 10, None, 'LEAN HOME',
                                 dict(event_key='NHL:3:moneyline'), path, 'NHL', stake_size=1.5)

    def test_store_forwards_the_quarter_kelly_stake(self):
        import run_ncaaf
        result = dict(sport='ncaaf', league='NCAAF', home_team='A', away_team='B',
                      game_date='2026-10-24', game_id='1',
                      projection=dict(home_points=28.0, away_points=20.0, note='x'),
                      markets=[price_market('moneyline', .5, (.62, .38, 0), 120, -140)],
                      notes=[], fixture={})
        with patch('core.historical_storage.init_db'), \
             patch('core.historical_storage.store_prediction') as save:
            run_ncaaf.store(result)
        self.assertEqual(save.call_args.kwargs['stake_size'],
                         min((.62*1.20-.38)/(2.20-1)*.25, .05))
        self.assertEqual(save.call_args.args[8], 'LEAN HOME')

    def test_alternative_lines_survive_storage_and_grading(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'history.db'
            init_db(path)
            ids = []
            for line in (-3.5, -4.5, -3.5):
                raw = dict(game_date='2026-10-10', event_key=f'NCAAF:123:spread:{line}')
                ids.append(store_prediction('ncaaf', 'A', 'B', 'spread', .6, line,
                                           10, None, 'LEAN HOME', raw, path, 'NCAAF'))
            self.assertEqual(ids[0], ids[2])
            self.assertNotEqual(ids[0], ids[1])
            with sqlite3.connect(path) as conn:
                conn.row_factory = sqlite3.Row
                rows = list(conn.execute('SELECT * FROM predictions'))
                self.assertEqual({r['game_date'] for r in rows}, {'2026-10-10'})
                kept, dropped = newest_per_fixture(rows)
                self.assertEqual((len(kept), len(dropped)), (2, 0))
            conn.close()

    def test_odds_pairs_require_matching_date_and_opposite_handicap(self):
        game = dict(league='NBA', home_team='Boston Celtics', away_team='New York Knicks', date='2026-10-10')
        event = dict(id='1', home_team=game['home_team'], away_team=game['away_team'],
                     commence_time='2026-10-11T00:00:00Z', bookmakers=[dict(key='book', markets=[
                         dict(key='spreads', outcomes=[dict(name=game['home_team'], point=-3.5, price=-110),
                                                      dict(name=game['away_team'], point=3.5, price=-110)])])])
        rows, _ = for_fixture([event], game)
        self.assertEqual(rows[0]['line'], -3.5)
        event['bookmakers'][0]['markets'][0]['outcomes'][1]['point'] = 4.5
        self.assertEqual(for_fixture([event], game)[0], [])
        event['commence_time'] = '2026-10-12T00:00:00Z'
        self.assertEqual(for_fixture([event], game)[0], [])

    def test_context_is_sourced_fresh_and_explicit_scenario(self):
        item = dict(source='https://example.org/report', as_of='2026-10-09',
                    elo_adjustment=-50, adjustment_reason='Scenario sensitivity')
        with patch('tennis_context.today', return_value='2026-10-09'):
            probability, audit = apply_context('A', 'B', .6, {'players': {'A': item}})
            self.assertLess(probability, .6)
            self.assertTrue(audit['scenario'])
            for change in (dict(as_of='2026-10-01'), dict(injury_status='out'), dict(source='')):
                with self.assertRaises(ValueError):
                    apply_context('A', 'B', .6, {'players': {'A': {**item, **change}}})
        self.assertAlmostEqual(hold_probability(.5), .5)

    def test_feed_uses_homeaway_fields_and_keeps_zero_scores(self):
        event = dict(id='1', date='2026-10-11T00:00:00Z', competitions=[dict(
            status=dict(type=dict(completed=True)), competitors=[
                dict(homeAway='away', team=dict(id='2', displayName='B'), score=dict(value=0)),
                dict(homeAway='home', team=dict(id='1', displayName='A'), score=dict(value=3))])])
        result = parse_game(event, 'NCAAF')
        self.assertEqual((result['home_team'], result['away_score'], result['date']), ('A', 0, '2026-10-10'))

    def test_nz_schedule_uses_local_time_and_completed_status(self):
        text = '''<div class="match-wrap STATUS_COMPLETE" id="extfix_1">
          <div class="match-time"><span>9 Aug 2026, 3:00 pm</span></div>
          <div class="home-team"><span class="team-name-full">Southland Sharks</span></div>
          <div class="away-team"><span class="team-name-full">Wellington Saints</span></div>
          <div class="homescore"><div class="fake-cell">104</div></div>
          <div class="awayscore"><div class="fake-cell">101</div></div></div>'''
        row = parse_nz_schedule(text, 2026)[0]
        self.assertEqual((row['date'], row['home_score'], row['away_score']), ('2026-08-08', 104, 101))
        with self.assertRaises(ValueError):
            parse_nz_schedule(text, 2025)

    def test_international_spread_and_discord_alternatives(self):
        from euroleague_engine import EuroleaguePredictor
        from embed_builder import normalise
        metrics = dict(ortg=110, drtg=110, pace=72)
        result = EuroleaguePredictor('A', 'B', metrics, metrics,
            market_lines=dict(spread=-3.5, total=160,
                alternatives=[dict(kind='spread', line=-4.5, price_a=-110, price_b=-110)])).predict()
        self.assertAlmostEqual(result['full_game']['spread_edge'], 0)
        self.assertEqual(len(result['markets']), 3)
        rows = normalise('basketball', result)['markets']
        self.assertTrue(any('Spread -4.5' in r['name'] for r in rows))

    def test_default_tennis_card_contains_games_and_set_markets(self):
        from models.tennis_predictor import predict_tennis_match
        from embed_builder import normalise
        result = predict_tennis_match('Frances Tiafoe', 'Yannick Hanfmann', surface='hard', best_of_5=False)
        kinds = {r['kind'] for r in result['alternative_markets']}
        self.assertEqual(kinds, {'games_total', 'sets_total', 'games_spread', 'sets_spread'})
        self.assertGreater(len(normalise('tennis', result)['markets']), 1)
        self.assertTrue(all(r['ev_a'] is None for r in result['alternative_markets']))

    def test_college_men_and_women_results_are_league_scoped(self):
        from grade_predictions import fetch_basketball_results
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'data').mkdir()
            for league, scores in [('ncaab', (80, 70)), ('ncaaw', (60, 50))]:
                game = dict(date='2026-10-09', completed=True, home_team='A', away_team='B',
                            home_score=scores[0], away_score=scores[1])
                (root/f'data/basketball_{league}_games.json').write_text(json.dumps({'games':[game]}))
            with patch('sports_feed.ROOT', root), patch('sports_feed.fetch_json', return_value={'events':[]}):
                scores = fetch_basketball_results('2026-10-09', '2026-10-09')
            self.assertEqual(scores[('NCAAB', '2026-10-09', 'a', 'b')], (80, 70))
            self.assertEqual(scores[('NCAAW', '2026-10-09', 'a', 'b')], (60, 50))


if __name__ == '__main__':
    unittest.main()
