import unittest

import prop_odds as po
from models.prop_probability import MIN_POOL_SAMPLES, priceability, probability_for, residual_scale


def book(key, markets):
    return {"key": key, "title": key.title(), "markets": markets}


def totals_market(line, over, under, updated="2026-10-26T21:00:00Z"):
    return {"key": "totals", "last_update": updated, "outcomes": [
        {"name": "Over", "point": line, "price": over},
        {"name": "Under", "point": line, "price": under}]}


def player_market(player, line, over, under, key="player_points"):
    return {"key": key, "last_update": "2026-10-26T21:00:00Z", "outcomes": [
        {"name": "Over", "description": player, "point": line, "price": over},
        {"name": "Under", "description": player, "point": line, "price": under}]}


class IdentityTests(unittest.TestCase):
    def test_club_suffixes_and_provider_spellings_still_match(self):
        events = [{"id": "1", "away_team": "FC Barcelona Bàsquet",
                   "home_team": "FC Bayern München", "commence_time": "2026-10-27T19:00:00Z"}]
        hit = po.match_event(events, "FC Barcelona", "FC Bayern Munich")
        self.assertEqual("1", hit["id"])

    def test_wrong_orientation_is_refused(self):
        events = [{"id": "1", "away_team": "A Team", "home_team": "B Team"}]
        with self.assertRaises(ValueError):
            po.match_event(events, "B Team", "A Team")

    def test_missing_fixture_returns_none_not_a_guess(self):
        events = [{"id": "1", "away_team": "A Team", "home_team": "B Team"}]
        self.assertIsNone(po.match_event(events, "C Team", "D Team"))

    def test_two_matching_events_are_ambiguous(self):
        events = [{"id": "1", "away_team": "A Team", "home_team": "B Team"},
                  {"id": "2", "away_team": "A Team", "home_team": "B Team"}]
        with self.assertRaises(ValueError):
            po.match_event(events, "A Team", "B Team")


class LineTests(unittest.TestCase):
    def payload(self):
        return {"bookmakers": [
            book("fanduel", [player_market("Test Player", 24.5, -115, -105),
                             player_market("Other Player", 18.5, -110, -110)]),
            book("draftkings", [player_market("Test Player", 24.5, -105, -115)]),
            book("betmgm", [player_market("Test Player", 23.5, -110, -110)]),
        ]}

    def test_only_the_named_player_is_returned(self):
        rows = po.player_lines(self.payload(), "Test Player", "player_points")
        self.assertEqual({24.5, 23.5}, {row["line"] for row in rows})

    def test_modal_line_wins(self):
        rows = po.player_lines(self.payload(), "Test Player", "player_points")
        self.assertEqual(24.5, po.consensus_line(rows))

    def test_best_price_prefers_the_higher_payout(self):
        rows = po.player_lines(self.payload(), "Test Player", "player_points")
        best = po.best_prices(rows, 24.5)
        self.assertEqual(-105, best["over"]["price"])
        self.assertEqual("draftkings", best["over"]["bookmaker"])
        self.assertEqual(-105, best["under"]["price"])

    def test_missing_side_is_absent_not_zero(self):
        payload = {"bookmakers": [book("betmgm", [{
            "key": "player_points", "outcomes": [
                {"name": "Over", "description": "Test Player", "point": 23.5, "price": -110}]}])]}
        rows = po.player_lines(payload, "Test Player", "player_points")
        best = po.best_prices(rows, 23.5)
        self.assertEqual(-110, best["over"]["price"])
        self.assertNotIn("under", best)

    def test_de_vig_is_normalised(self):
        over, under = po.de_vig(-115, -105)
        self.assertAlmostEqual(1.0, over + under, places=9)
        self.assertGreater(under, over)

    def test_de_vig_rejects_nonsense_prices(self):
        with self.assertRaises(ValueError):
            po.de_vig(-50, -105)


class TeamFlagTests(unittest.TestCase):
    def test_flags_carry_only_priced_markets(self):
        payload = {"bookmakers": [book("fanduel", [
            totals_market(176.5, -110, -105),
            {"key": "h2h", "outcomes": [
                {"name": "FC Bayern München", "price": -105},
                {"name": "FC Barcelona Bàsquet", "price": 102}]},
            {"key": "spreads", "outcomes": [
                {"name": "FC Bayern München", "point": -1.5, "price": -102},
                {"name": "FC Barcelona Bàsquet", "point": 1.5, "price": -114}]},
        ])]}
        flags = po.team_price_flags(payload, "FC Barcelona", "FC Bayern Munich")
        joined = " ".join(flags)
        self.assertIn("--market-total 176.5", joined)
        self.assertIn("--market-spread -1.5", joined)
        self.assertIn("--home-ml -105.0", joined)
        self.assertIn("--away-ml 102.0", joined)

    def test_empty_payload_produces_no_flags(self):
        self.assertEqual([], po.team_price_flags({}, "A", "B"))


class ProbabilityTests(unittest.TestCase):
    def pool(self, points):
        return {"singles": {"points": {3: list(points)}},
                "combos": {"pra": {3: [(p, 0.0, 0.0) for p in points]}},
                "band_width_minutes": 8.0}

    def test_empirical_probabilities_sum_to_one(self):
        pool = self.pool([-3, -2, -1, 0, 1, 2, 3] * 20)
        result = probability_for(pool, "points", 25.0, 28.0, 24.5)
        self.assertEqual("ok", result["status"])
        self.assertAlmostEqual(1.0, result["over"] + result["under"] + result["push"], places=9)

    def test_integer_line_can_push(self):
        pool = self.pool([-1, -1, 0, 0, 0, 1, 1] * 20)
        result = probability_for(pool, "points", 24.0, 28.0, 24)
        self.assertGreater(result["push"], 0.0)

    def test_half_line_never_pushes(self):
        pool = self.pool([-1, 0, 1] * 40)
        result = probability_for(pool, "points", 24.0, 28.0, 24.5)
        self.assertEqual(0.0, result["push"])

    def test_thin_pool_is_unavailable_with_a_reason(self):
        pool = self.pool([0.0] * (MIN_POOL_SAMPLES - 1))
        result = probability_for(pool, "points", 20.0, 28.0, 19.5)
        self.assertEqual("unavailable", result["status"])
        self.assertIn("measured residuals", result["reason"])

    def test_combo_uses_joint_sample_not_a_product(self):
        pool = self.pool([0.0] * 100)
        single = probability_for(pool, "points", 20.0, 28.0, 19.5)
        combo = probability_for(pool, "pra", 30.0, 28.0, 29.5)
        self.assertEqual(single["samples"], combo["samples"])
        self.assertEqual("empirical residual frequency; unvalidated against market prices",
                         combo["method"])


class PriceabilityTests(unittest.TestCase):
    def test_gap_beyond_measured_error_is_withheld(self):
        gate = priceability(25.1, 31.5, 5.9)
        self.assertFalse(gate["priceable"])
        self.assertIn("beyond the measured mean absolute error", gate["reason"])

    def test_gap_inside_measured_error_is_priceable(self):
        self.assertTrue(priceability(24.0, 24.5, 5.9)["priceable"])

    def test_missing_scale_is_not_priceable(self):
        self.assertFalse(priceability(20.0, 19.5, None)["priceable"])

    def test_residual_scale_is_measured_not_assumed(self):
        pool = {"singles": {"points": {3: [1.0, -1.0, 2.0, -2.0]}},
                "combos": {"pra": {3: []}}, "band_width_minutes": 8.0}
        # Below the minimum sample, the scale is unavailable rather than invented.
        self.assertIsNone(residual_scale(pool, "points", 28.0))


class QuotaTests(unittest.TestCase):
    def test_quota_sums_actual_provider_cost(self):
        note = po.quota_note([{"credit_cost": 6, "remaining": 94},
                              {"cached": True, "credit_cost": 0, "remaining": 94}])
        self.assertEqual(6, note["credits_spent"])
        self.assertEqual(94, note["credits_remaining"])
        self.assertEqual(1, note["cache_hits"])

    def test_header_numbers_never_crash_on_garbage(self):
        self.assertIsNone(po._header_number({"x-requests-last": "n/a"}, "x-requests-last"))
        self.assertIsNone(po._header_number({}, "x-requests-last"))


if __name__ == "__main__":
    unittest.main()
