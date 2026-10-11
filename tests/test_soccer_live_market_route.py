import unittest
from unittest.mock import patch

from universal_runner import _fetch_live_soccer_market


class SoccerLiveMarketRouteTests(unittest.TestCase):
    def test_ligue_one_store_and_cli_names_are_covered(self):
        from live_odds import SOCCER_LEAGUES
        self.assertEqual(SOCCER_LEAGUES['ligue 1'], SOCCER_LEAGUES['ligue1'])
        self.assertEqual(SOCCER_LEAGUES['ligue 1']['key'], 'soccer_france_ligue_one')

    def test_shared_provider_keeps_captured_prices(self):
        with patch('live_odds.get_soccer_odds', return_value={
            'status': 'cached', 'captured_at': '2026-10-09T14:00:00Z',
            'home_ml': 167, 'away_ml': 163, 'total_line': 3.0,
        }) as fetch:
            result = _fetch_live_soccer_market('Lens', 'Lyon', 'Ligue 1')
        fetch.assert_called_once_with('Ligue 1', 'Lens', 'Lyon')
        self.assertEqual(result['market']['total_line'], 3.0)
        self.assertEqual(result['status'], 'cached')

    def test_missing_fixture_does_not_invent_market(self):
        with patch('live_odds.get_soccer_odds', return_value={
            'status': 'no_fixture', 'captured_at': None, 'reason': 'No match',
        }):
            result = _fetch_live_soccer_market('A', 'B', 'Ligue 1')
        self.assertNotIn('market', result)
        self.assertEqual(result['status'], 'no_fixture')


if __name__ == '__main__':
    unittest.main()
