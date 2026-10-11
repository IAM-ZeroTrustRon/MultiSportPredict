import unittest
from unittest.mock import patch

from live_odds import _extract_tennis_lines, get_tennis_odds


def fixture():
    return dict(id="event1", home_team="Player A", away_team="Player B",
                commence_time="2099-10-10T04:00:00Z", bookmakers=[dict(
                    key="book", title="Test Book", markets=[
                        dict(key="h2h", outcomes=[dict(name="Player A", price=-150), dict(name="Player B", price=130)]),
                        dict(key="spreads", outcomes=[dict(name="Player A", point=-3.5, price=-105), dict(name="Player B", point=3.5, price=-115)]),
                        dict(key="totals", outcomes=[dict(name="Over", point=22.5, price=-110), dict(name="Under", point=22.5, price=-120)])])])


class TennisLiveLinesTests(unittest.TestCase):
    def test_swapped_handicap_keeps_correct_prices(self):
        event = fixture()
        event["_swapped"] = True
        spread = _extract_tennis_lines(event)[0]
        self.assertEqual((spread["line"], spread["price_a"], spread["price_b"]), (3.5, -115, -105))

    def test_mismatched_lines_and_incomplete_prices_are_rejected(self):
        event = fixture()
        event["bookmakers"][0]["markets"][1]["outcomes"][1]["point"] = 4.5
        event["bookmakers"][0]["markets"][2]["outcomes"][1]["price"] = 0
        self.assertEqual(_extract_tennis_lines(event), [])

    def test_set_markets_use_sets_and_not_games(self):
        event = fixture()
        markets = event["bookmakers"][0]["markets"]
        markets[1]["key"] = "alternate_set_spreads"
        markets[2]["key"] = "alternate_set_totals"
        self.assertEqual({r["kind"] for r in _extract_tennis_lines(event)}, {"sets_spread", "sets_total"})

    def test_automatic_main_lines_survive_missing_additional_markets(self):
        with patch("live_odds._read_cache", return_value=None), patch("live_odds._write_cache", return_value="timestamp"), \
             patch("live_odds._discover_tennis_tournaments", return_value=(["tennis_atp_test"], None)), \
             patch("live_odds._find_tennis_event", return_value=fixture()), \
             patch("live_odds._fetch_odds_key", return_value=([fixture()], None)) as fetch, \
             patch("live_odds._fetch_tennis_extra", return_value=(None, "HTTP 422")):
            result = get_tennis_odds("atp", "Player A", "Player B")
        self.assertEqual(fetch.call_args.args[2], "h2h,spreads,totals")
        self.assertEqual(len(result["custom_markets"]), 2)
        self.assertEqual(result["additional_markets_error"], "HTTP 422")

    def test_started_fixture_has_no_automatic_prices(self):
        event = fixture()
        event["commence_time"] = "2000-01-01T00:00:00Z"
        with patch("live_odds._read_cache", return_value=None), patch("live_odds._write_cache", return_value="timestamp"), \
             patch("live_odds._discover_tennis_tournaments", return_value=(["tennis_atp_test"], None)), \
             patch("live_odds._find_tennis_event", return_value=event), \
             patch("live_odds._fetch_odds_key", return_value=([event], None)):
            result = get_tennis_odds("atp", "Player A", "Player B")
        self.assertEqual(result["status"], "in_play")
        self.assertNotIn("custom_markets", result)


if __name__ == "__main__":
    unittest.main()
