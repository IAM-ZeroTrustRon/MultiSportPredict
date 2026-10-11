import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
"""
Comprehensive Test Suite for Czech Liga Pro Table Tennis Engine
Adheres to Section 8 Acceptance Tests in CZECH_LIGA_PRO_GEMINI_HANDOFF.md.
"""

import unittest
import math
from datetime import datetime, timezone, timedelta

from models.table_tennis_poisson import poisson_distribution, evaluate_poisson_losing_points_diagnostic
from models.table_tennis_scoring import (
    PointState, MatchState, TableTennisGameScorer, TableTennisMatchScorer
)
from models.table_tennis_features import (
    TableTennisFeaturePipeline, HistoricalMatchRecord, PlayerSessionWorkload
)
from models.table_tennis_predictor import CzechLigaProPredictor, HybridModelWeights
from table_tennis.provider_discovery import LeagueScopeValidator
from table_tennis.alerts import TableTennisAlertManager
from ingest_table_tennis import TableTennisIngestor

class TestTableTennisScoringLegalRules(unittest.TestCase):
    """Verifies legal table tennis scoring mechanics (ITTF / Czech Liga Pro)."""

    def setUp(self):
        self.scorer = TableTennisGameScorer(p_point_a=0.55)

    def test_terminal_states_11_0_and_11_9(self):
        # 11-0 is terminal (lead >= 2 and pts >= 11)
        s_11_0 = PointState(11, 0)
        self.assertTrue(s_11_0.is_terminal())
        self.assertEqual(s_11_0.winner(), 'A')
        self.assertEqual(self.scorer.win_probability_from_state(11, 0), 1.0)

        # 11-9 is terminal
        s_11_9 = PointState(11, 9)
        self.assertTrue(s_11_9.is_terminal())
        self.assertEqual(s_11_9.winner(), 'A')
        self.assertEqual(self.scorer.win_probability_from_state(11, 9), 1.0)

        # 9-11 is terminal for B
        s_9_11 = PointState(9, 11)
        self.assertTrue(s_9_11.is_terminal())
        self.assertEqual(s_9_11.winner(), 'B')
        self.assertEqual(self.scorer.win_probability_from_state(9, 11), 0.0)

    def test_non_terminal_10_10_and_11_10(self):
        # 10-10 is deuce, non-terminal
        s_10_10 = PointState(10, 10)
        self.assertFalse(s_10_10.is_terminal())
        self.assertIsNone(s_10_10.winner())

        # 11-10 is lead of 1, non-terminal
        s_11_10 = PointState(11, 10)
        self.assertFalse(s_11_10.is_terminal())
        self.assertIsNone(s_11_10.winner())

        # Win probability from 11-10 is strictly between deuce and 1.0
        p_10_10 = self.scorer.win_probability_from_state(10, 10)
        p_11_10 = self.scorer.win_probability_from_state(11, 10)
        self.assertGreater(p_11_10, p_10_10)
        self.assertLess(p_11_10, 1.0)

    def test_terminal_12_10(self):
        # 12-10 is terminal
        s_12_10 = PointState(12, 10)
        self.assertTrue(s_12_10.is_terminal())
        self.assertEqual(s_12_10.winner(), 'A')
        self.assertEqual(self.scorer.win_probability_from_state(12, 10), 1.0)

    def test_deuce_continuation_beyond_15(self):
        # Test 16-16 deuce continuation
        s_16_16 = PointState(16, 16)
        self.assertFalse(s_16_16.is_terminal())
        p_16_16 = self.scorer.win_probability_from_state(16, 16)
        # Should match exact deuce formula p^2 / (p^2 + q^2)
        expected_deuce = (0.55 ** 2) / (0.55 ** 2 + 0.45 ** 2)
        self.assertAlmostEqual(p_16_16, expected_deuce, places=4)

        # 18-16 is terminal
        s_18_16 = PointState(18, 16)
        self.assertTrue(s_18_16.is_terminal())
        self.assertEqual(s_18_16.winner(), 'A')

    def test_symmetry_and_probability_bounds(self):
        scorer_even = TableTennisGameScorer(p_point_a=0.50)
        self.assertAlmostEqual(scorer_even.win_probability_from_state(0, 0), 0.50, places=4)

        # Player reversal symmetry
        scorer_a = TableTennisGameScorer(p_point_a=0.58)
        scorer_b = TableTennisGameScorer(p_point_a=0.42)
        self.assertAlmostEqual(scorer_a.win_probability_from_state(0, 0) + scorer_b.win_probability_from_state(0, 0), 1.0, places=4)

    def test_terminal_score_distribution_sums_to_one(self):
        dist = self.scorer.terminal_score_distribution_from_0_0()
        total_prob = sum(dist.values())
        self.assertAlmostEqual(total_prob, 1.0, places=4)
        for score, prob in dist.items():
            self.assertGreaterEqual(prob, 0.0)
            self.assertLessEqual(prob, 1.0)

    def test_live_conditioning_preserves_played_points(self):
        # If A leads 10-0, A's win probability must be much higher than from 0-0
        p_from_0_0 = self.scorer.win_probability_from_state(0, 0)
        p_from_10_0 = self.scorer.win_probability_from_state(10, 0)
        self.assertGreater(p_from_10_0, 0.99)
        self.assertGreater(p_from_10_0, p_from_0_0)


class TestTableTennisMatchScorer(unittest.TestCase):
    """Verifies best-of-5 match resolution and market distributions."""

    def setUp(self):
        self.match_scorer = TableTennisMatchScorer(p_point_a=0.54, best_of=5)

    def test_best_of_5_pre_match_distribution(self):
        res = self.match_scorer.solve_match(MatchState(best_of=5))
        self.assertAlmostEqual(res["match_winner_a"] + res["match_winner_b"], 1.0, places=4)
        
        # Verify score distribution sums to 1.0
        scores_sum = sum(res["score_distribution"].values())
        self.assertAlmostEqual(scores_sum, 1.0, places=4)

        # Verify game handicap: Home -1.5 Games + Away +1.5 Games == 1.0
        gh = res["game_handicap"]
        self.assertEqual(gh["unit"], "GAMES")
        self.assertAlmostEqual(gh["home_minus_1_5"] + gh["away_plus_1_5"], 1.0, places=4)

        # Verify total games: Over 3.5 + Under 3.5 == 1.0
        tg = res["total_games"]
        self.assertEqual(tg["unit"], "GAMES")
        self.assertAlmostEqual(tg["over_3_5"] + tg["under_3_5"], 1.0, places=4)

        # Points metrics have unit POINTS
        tp = res["total_points"]
        self.assertEqual(tp["unit"], "POINTS")
        self.assertGreater(tp["expected"], 50.0)

    def test_live_match_state_in_play(self):
        # A leads 2-0 in games and 10-5 in game 3
        live_state = MatchState(
            games_a=2,
            games_b=0,
            best_of=5,
            current_game=PointState(points_a=10, points_b=5),
            completed_game_scores=[(11, 8), (11, 7)]
        )
        res = self.match_scorer.solve_match(live_state)
        self.assertGreater(res["match_winner_a"], 0.98)
        self.assertLess(res["total_games"]["expected"], 3.1)


class TestPoissonUtilitySection4(unittest.TestCase):
    """Tests the exact numerical count-distribution utility from Section 4."""

    def test_valid_poisson_calculation(self):
        res = poisson_distribution(rate=5.0, tolerance=1e-8, max_count=100)
        self.assertIn("probabilities", res)
        self.assertIn("tail_mass", res)
        total = sum(res["probabilities"]) + res["tail_mass"]
        self.assertAlmostEqual(total, 1.0, places=6)

    def test_zero_rate_input(self):
        res = poisson_distribution(rate=0.0)
        self.assertEqual(res["probabilities"][0], 1.0)
        self.assertEqual(res["tail_mass"], 0.0)

    def test_invalid_poisson_inputs(self):
        with self.assertRaises(ValueError):
            poisson_distribution(rate=-1.0)
        with self.assertRaises(ValueError):
            poisson_distribution(rate=5.0, tolerance=1.5)
        with self.assertRaises(ValueError):
            poisson_distribution(rate=5.0, max_count=-5)

    def test_diagnostic_overdispersion(self):
        losing_pts = [9, 8, 9, 7, 6, 8, 9, 7, 5, 8]
        diag = evaluate_poisson_losing_points_diagnostic(losing_pts, candidate_rate=7.5)
        self.assertEqual(diag["sample_size"], 10)
        self.assertIn("dispersion_ratio", diag)


class TestLeagueScopeValidator(unittest.TestCase):
    """Verifies strict Czech Liga Pro boundaries and rejection of other leagues."""

    def test_accepts_verified_czech_liga_pro(self):
        self.assertTrue(LeagueScopeValidator.validate_league("Czech Liga Pro", "Czech Republic"))
        self.assertTrue(LeagueScopeValidator.validate_league("Liga Pro (CZ)", "Czechia"))
        self.assertTrue(LeagueScopeValidator.validate_league("Czech Republic - Czech Liga Pro", "Czech Republic"))

    def test_rejects_russian_and_setka_and_tt_cup(self):
        self.assertFalse(LeagueScopeValidator.validate_league("Russian Liga Pro", "Russia"))
        self.assertFalse(LeagueScopeValidator.validate_league("Liga Pro (RU)", "Russia"))
        self.assertFalse(LeagueScopeValidator.validate_league("Setka Cup", "Ukraine"))
        self.assertFalse(LeagueScopeValidator.validate_league("Czech TT Cup", "Czech Republic"))
        self.assertFalse(LeagueScopeValidator.validate_league("TT Cup", "Czech Republic"))
        self.assertFalse(LeagueScopeValidator.validate_league("TT Elite", "Poland"))
        self.assertFalse(LeagueScopeValidator.validate_league("WTT Champions", "China"))


class TestFeaturePipelineAndShrinkage(unittest.TestCase):
    """Verifies H2H shrinkage, residuals, and workload extraction."""

    def setUp(self):
        self.pipeline = TableTennisFeaturePipeline(h2h_prior_strength=2.0)
        self.ref_time = datetime(2026, 10, 9, 18, 0, tzinfo=timezone.utc)

    def test_h2h_shrinkage_toward_baseline(self):
        # 1 past meeting where A won
        history = [
            HistoricalMatchRecord(
                event_id="m1",
                match_timestamp_utc=self.ref_time - timedelta(days=5),
                player_a_id="player_a",
                player_b_id="player_b",
                a_won_match=True,
                games_a=3,
                games_b=1,
                total_points_a=42,
                total_points_b=34,
                first_game_won_a=True,
                prior_expected_prob_a=0.55
            )
        ]
        feats = self.pipeline.extract_h2h_features(
            history, "player_a", "player_b", self.ref_time, baseline_prob_a=0.50
        )
        self.assertEqual(feats["h2h_sample_size"], 1)
        self.assertEqual(feats["raw_match_win_rate_a"], 1.0)
        # Shrunk probability should be between baseline (0.50) and 1.0
        self.assertLess(feats["shrunk_match_win_prob_a"], 1.0)
        self.assertGreater(feats["shrunk_match_win_prob_a"], 0.50)

    def test_workload_and_rest_calculation(self):
        last_end = self.ref_time - timedelta(minutes=45)
        wl_a = PlayerSessionWorkload(player_id="player_a", date_str="2026-10-09",
                                     matches_completed=2, games_completed=8, last_match_end_utc=last_end)
        wl_b = PlayerSessionWorkload(player_id="player_b", date_str="2026-10-09",
                                     matches_completed=1, games_completed=4, last_match_end_utc=None)
        metrics = self.pipeline.extract_workload_and_rest(wl_a, wl_b, self.ref_time)
        self.assertEqual(metrics["player_a_matches_today"], 2)
        self.assertEqual(metrics["player_b_matches_today"], 1)
        self.assertAlmostEqual(metrics["player_a_rest_minutes"], 45.0, places=1)
        self.assertIsNone(metrics["player_b_rest_minutes"])


class TestPredictorAndDevigging(unittest.TestCase):
    """Verifies top-down proportional de-vigging and hybrid calibration."""

    def setUp(self):
        self.predictor = CzechLigaProPredictor()

    def test_proportional_devigging(self):
        # 1.80 vs 2.10
        fair_a, fair_b = self.predictor.devig_proportional(1.80, 2.10)
        self.assertAlmostEqual(fair_a + fair_b, 1.0, places=4)
        self.assertGreater(fair_a, fair_b)

    def test_invalid_odds_devigging(self):
        self.assertIsNone(self.predictor.devig_proportional(0.95, 2.0))

    def test_hybrid_and_bottom_up_predictions(self):
        player_a = {"name": "Havrda Leos", "rating": 550}
        player_b = {"name": "Kulhanek Pavel", "rating": 450}
        
        # Bottom-up when no odds
        pred_no_odds = self.predictor.generate_full_prediction(player_a, player_b, reference_odds=None)
        self.assertEqual(pred_no_odds["strategy"], "BOTTOM_UP_FALLBACK")
        self.assertGreater(pred_no_odds["probabilities"]["selected_final_win_a"], 0.50)

        # Hybrid when odds provided
        pred_with_odds = self.predictor.generate_full_prediction(player_a, player_b, reference_odds=(1.60, 2.40))
        self.assertEqual(pred_with_odds["strategy"], "HYBRID_TOP_DOWN_H2H")
        self.assertIsNotNone(pred_with_odds["probabilities"]["top_down_market_a"])


class TestAlertsAndEV(unittest.TestCase):
    """Verifies EV arithmetic, freshness budgets, and alert suppression."""

    def setUp(self):
        self.alert_mgr = TableTennisAlertManager(max_quote_age_seconds=60.0, min_edge_pct=3.0)

    def test_ev_calculations(self):
        # p=0.60, odds=2.00 -> EV = 0.60 * 2.00 - 1 = +0.20
        ev_ml = self.alert_mgr.calculate_ev_no_push(p_win=0.60, decimal_odds=2.00)
        self.assertAlmostEqual(ev_ml, 0.20, places=4)

        # Push-aware: p_win=0.45, p_loss=0.45, push=0.10, odds=2.00
        # EV = 0.45*(2.00-1) - 0.45*1.0 = 0.00
        ev_push = self.alert_mgr.calculate_ev_with_push(p_win=0.45, p_loss=0.45, decimal_odds=2.00)
        self.assertAlmostEqual(ev_push, 0.0, places=4)

    def test_stale_quote_suppresses_alert(self):
        now = datetime.now(timezone.utc)
        stale_time = (now - timedelta(seconds=120)).isoformat()
        is_fresh, age = self.alert_mgr.evaluate_quote_freshness(stale_time, now)
        self.assertFalse(is_fresh)
        self.assertGreater(age, 60.0)


class TestIngestorCorrectionsAndDedup(unittest.TestCase):
    """Verifies idempotent deduplication and correction versioning."""

    def setUp(self):
        self.ingestor = TableTennisIngestor(archive_dir="data/czech_liga_pro_samples/test_archive")

    def test_dedup_and_correction_flow(self):
        raw_event = {
            "event_id": "cz_match_101",
            "league": "Czech Liga Pro",
            "home_player": {"name": "Novak Ondrej", "rating": 1006},
            "away_player": {"name": "Zajicek Jan", "rating": 981},
            "scheduled_time_utc": "2026-10-09T18:00:00Z",
            "game_scores": [(11, 8), (11, 9)]
        }
        # Ingest new
        res1 = self.ingestor.process_incoming_event(raw_event)
        self.assertEqual(res1["status"], "INGESTED_NEW")

        # Ingest identical duplicate frame
        res2 = self.ingestor.process_incoming_event(raw_event)
        self.assertEqual(res2["status"], "DUPLICATE_IGNORED")

        # Ingest corrected score
        raw_event_corr = dict(raw_event)
        raw_event_corr["game_scores"] = [(11, 8), (9, 11)]  # score correction
        res3 = self.ingestor.process_incoming_event(raw_event_corr)
        self.assertEqual(res3["status"], "CORRECTION_APPLIED")
        self.assertEqual(res3["version"], 2)

    def test_canonical_player_sr_jr_distinction(self):
        name1, id1 = self.ingestor.canonicalize_player_name("Neuwirth Jaroslav SR")
        name2, id2 = self.ingestor.canonicalize_player_name("Neuwirth Jaroslav JR")
        self.assertNotEqual(id1, id2)
        self.assertIn("sr", id1)
        self.assertIn("jr", id2)

if __name__ == '__main__':
    unittest.main()
