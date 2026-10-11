import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import universal_runner


class ExtendedSoccerMarketThreadingTests(unittest.TestCase):
    def run_market(self, market):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'output' / 'soccer' / 'Home_vs_Away.json'
            output.parent.mkdir(parents=True)
            output.write_text('{}', encoding='utf-8')
            with patch('universal_runner.Path', side_effect=lambda *args: root.joinpath(*args)), \
                 patch('universal_runner.get_soccer_team_stats', return_value={}), \
                 patch('predict_match.run_soccer_game', return_value={'game': {}}), \
                 patch('live_odds.get_soccer_odds', return_value=market), \
                 patch('extra_markets.enrich_result', side_effect=lambda result, **kwargs: result), \
                 patch('universal_runner._display_full_result') as display, \
                 patch('universal_runner._store_prediction') as store:
                result = universal_runner.run_soccer(
                    'Home', 'Away', 'Ligue 1', 0, 2.5, False, False)
                store.assert_not_called()
                self.assertEqual(display.call_args.args[0], result)
                saved = json.loads(output.read_text(encoding='utf-8'))
            return result, saved

    def test_quotes_reach_return_display_and_saved_output(self):
        quotes = {
            'h1_home_ml': 150, 'h1_draw_ml': 120, 'h1_away_ml': 180,
            'h1_spread_line': 0.0, 'h1_spread_home_price': -105,
            'h1_spread_away_price': -110, 'h1_total_line': 1.25,
            'h1_over_price': -115, 'h1_under_price': 105,
            'corner_total_line': 9.5, 'corner_over_price': -110,
            'corner_under_price': -105, 'corner_spread_line': 0,
            'team_total_home_line': 1.5, 'team_total_home_over_price': 110,
            'team_total_home_under_price': -120, 'team_total_away_line': .5,
            'team_total_away_over_price': -150, 'team_total_away_under_price': 130,
            'btts_yes_price': -110, 'btts_no_price': 100,
            'h1_btts_yes_price': 250, 'h1_btts_no_price': -300,
        }
        result, saved = self.run_market({'status': 'cached', **quotes})
        for key, value in quotes.items():
            self.assertEqual(result[key], value, key)
            self.assertEqual(saved[key], value, key)

    def test_missing_quotes_are_not_invented(self):
        result, saved = self.run_market({'status': 'live', 'h1_total_line': None})
        for data in (result, saved):
            self.assertNotIn('h1_total_line', data)
            self.assertNotIn('corner_over_price', data)
            self.assertNotIn('team_total_home_line', data)


if __name__ == '__main__':
    unittest.main()
