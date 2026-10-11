import unittest
from models.tennis_markets import evaluate_markets, score_distribution


class TennisMarketsTests(unittest.TestCase):
    def test_distribution_matches_elo_and_legal_format(self):
        for bo5 in (False, True):
            distribution = score_distribution(0.7, bo5)
            self.assertAlmostEqual(sum(distribution.values()), 1, places=8)
            self.assertAlmostEqual(sum(p for (a, b, _, _), p in distribution.items() if a > b), 0.7, places=7)
            needed = 3 if bo5 else 2
            self.assertTrue(all(max(a, b) == needed for a, b, _, _ in distribution))

    def test_push_and_price_ev(self):
        row = evaluate_markets(0.5, False, [dict(kind="sets_total", line=2, price_a=100, price_b=-100)])[0]
        self.assertAlmostEqual(row["push_prob"], 0.5)
        self.assertAlmostEqual(row["prob_a"], 0.5)
        self.assertEqual(row["prob_b"], 0)
        self.assertAlmostEqual(row["ev_a"], 0.5)
        self.assertIsNone(row["confidence"])

    def test_symmetry_and_monotonicity(self):
        specs = [dict(kind="games_spread", line=0),
                 dict(kind="games_total", line=20.5),
                 dict(kind="games_total", line=25.5)]
        spread, low, high = evaluate_markets(0.5, False, specs)
        self.assertAlmostEqual(spread["prob_a"], spread["prob_b"])
        self.assertGreater(low["prob_a"], high["prob_a"])
        for row in (spread, low, high):
            self.assertAlmostEqual(row["prob_a"] + row["prob_b"] + row["push_prob"], 1, places=5)
            self.assertIsNone(row["ev_a"])

    def test_invalid_inputs(self):
        for spec in [dict(kind="sets_total", line=-1), dict(kind="games_total", line=22.3),
                     dict(kind="games_spread", line=float("nan")),
                     dict(kind="sets_spread", line=-1.5, price_a=0)]:
            with self.assertRaises(ValueError):
                evaluate_markets(0.6, False, [spec])


if __name__ == "__main__":
    unittest.main()
