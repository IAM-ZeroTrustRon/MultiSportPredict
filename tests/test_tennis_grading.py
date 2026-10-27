"""Tennis grading: uniquely verified fixtures, no swapped duplicates, market settlement.

The three rules under test are the ones that made 55% of the tennis record invisible:

* ESPN's tennis scoreboard returns the whole tournament for any ``dates`` value, so a
  fixture must be keyed on the competition's own date.
* A stored row may spell a player either as a full name or as the older store key, so
  both must reach the same uniquely verified result.
* A completed match is not necessarily a clean finish: retirement settles a
  match-winner market on the official winner, while no play at all voids every market.
"""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import grade_predictions as g
import universal_runner as ur


def competition(date, home, away, home_won, status="STATUS_FINAL", slug="men's-singles"):
    return {
        "date": date,
        "status": {"type": {"name": status, "completed": True}},
        "competitors": [
            {"homeAway": "home", "winner": home_won,
             "athlete": {"fullName": home}},
            {"homeAway": "away", "winner": not home_won,
             "athlete": {"fullName": away}},
        ],
    }


def scoreboard(*competitions):
    return {"events": [{"groupings": [{"grouping": {"slug": "men's-singles"},
                                       "competitions": list(competitions)}]}]}


class SettlementRuleTests(unittest.TestCase):
    def test_match_winner_survives_a_retirement(self):
        rule, why = g.tennis_settlement_rule("moneyline", "STATUS_RETIRED")
        self.assertEqual("settle", rule)
        self.assertIn("official winner", why)

    def test_prop_markets_cannot_settle_on_a_retirement(self):
        rule, why = g.tennis_settlement_rule("games_total", "STATUS_RETIRED")
        self.assertEqual("void", rule)
        self.assertIn("completed match", why)

    def test_walkover_voids_every_market(self):
        for market in ("moneyline", "games_total", "sets_spread"):
            rule, why = g.tennis_settlement_rule(market, "STATUS_WALKOVER")
            self.assertEqual("void", rule, market)
            self.assertIn("no play", why)

    def test_clean_finish_needs_no_note(self):
        self.assertEqual(("settle", None), g.tennis_settlement_rule("moneyline", "STATUS_FINAL"))


class ResultFetchTests(unittest.TestCase):
    def _fetch(self, payload, start, end, store):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "players.json"
            path.write_text(json.dumps(store), encoding="utf-8")
            with patch.object(g, "_get_json", return_value=payload), \
                    patch("run_tennis.STORE", path):
                return g.fetch_tennis_results(start, end)

    def test_result_is_keyed_on_the_match_date_not_the_query_date(self):
        payload = scoreboard(
            competition("2026-10-17T10:30Z", "Alice Smith", "Bob Jones", True),
            competition("2026-10-23T10:30Z", "Alice Smith", "Bob Jones", False),
        )
        results = self._fetch(payload, "2026-10-23", "2026-10-24",
                              {"Alice Smith": {}, "Bob Jones": {}})
        self.assertIn(("2026-10-23", "alicesmith", "bobjones"), results)
        self.assertNotIn(("2026-10-17", "alicesmith", "bobjones"), results)
        self.assertEqual((0.0, 1.0), results[("2026-10-23", "alicesmith", "bobjones")])

    def test_full_name_and_store_key_both_reach_the_same_result(self):
        payload = scoreboard(competition("2026-10-23T10:30Z", "Alice Smith", "Bob Jones", True))
        results = self._fetch(payload, "2026-10-23", "2026-10-23",
                              {"A. Smith": {}, "B. Jones": {}})
        self.assertIn(("2026-10-23", "alicesmith", "bobjones"), results)
        self.assertIn(("2026-10-23", "asmith", "bjones"), results)
        self.assertEqual(results[("2026-10-23", "alicesmith", "bobjones")],
                         results[("2026-10-23", "asmith", "bjones")])

    def test_conflicting_results_on_one_day_are_withdrawn(self):
        payload = scoreboard(
            competition("2026-10-23T10:30Z", "Alice Smith", "Bob Jones", True),
            competition("2026-10-23T18:30Z", "Alice Smith", "Bob Jones", False),
        )
        results = self._fetch(payload, "2026-10-23", "2026-10-23",
                              {"Alice Smith": {}, "Bob Jones": {}})
        self.assertEqual({}, results)

    def test_a_result_without_its_own_date_is_not_keyed(self):
        payload = scoreboard(competition(None, "Alice Smith", "Bob Jones", True))
        results = self._fetch(payload, "2026-10-23", "2026-10-23",
                              {"Alice Smith": {}, "Bob Jones": {}})
        self.assertEqual({}, results)

    def test_unresolvable_names_are_skipped(self):
        payload = scoreboard(competition("2026-10-23T10:30Z", "Nobody Known", "Bob Jones", True))
        results = self._fetch(payload, "2026-10-23", "2026-10-23", {"Bob Jones": {}})
        self.assertEqual({}, results)

    def test_endings_are_recorded_for_the_caller(self):
        payload = scoreboard(competition("2026-10-23T10:30Z", "Alice Smith", "Bob Jones",
                                         True, status="STATUS_RETIRED"))
        self._fetch(payload, "2026-10-23", "2026-10-23",
                    {"Alice Smith": {}, "Bob Jones": {}})
        self.assertEqual("STATUS_RETIRED",
                         g.fetch_tennis_results.settlements[("2026-10-23", "alicesmith",
                                                             "bobjones")]["status"])


class VoidRecordingTests(unittest.TestCase):
    def test_void_is_recorded_as_a_refunded_push_with_a_reason(self):
        from core import historical_storage as store
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = Path(tmp) / "history.db"
            with patch.object(store, "DB_PATH", db):
                store.init_db(db)
                row_id = store.store_prediction(
                    sport="tennis", home_team="Alice Smith", away_team="Bob Jones",
                    market_type="moneyline", model_value=0.6, market_value=0.55,
                    edge=5.0, confidence=60.0,
                    recommendation="BET HOME ML (edge: +6.0%)", raw_json={},
                    db_path=db)
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM predictions WHERE id=?", (row_id,)).fetchone()
            outcome = g.apply_result(conn, row, 1.0, 0.0, "tennis feed",
                                     void_reason="void: no play (walkover)")
            conn.commit()
            settled = conn.execute("SELECT * FROM predictions WHERE id=?", (row_id,)).fetchone()
            conn.close()
        self.assertEqual("push", outcome)
        self.assertEqual("push", settled["result_outcome"])
        self.assertEqual(0.0, settled["profit_loss"])
        self.assertIn("void", settled["grade_note"])


class DuplicatePreventionTests(unittest.TestCase):
    def _row(self, home, away):
        from core import historical_storage as store
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = Path(tmp) / "history.db"
            with patch.object(store, "DB_PATH", db):
                store.init_db(db)
                store.store_prediction(
                    sport="tennis", home_team=home, away_team=away,
                    market_type="moneyline", model_value=0.6, market_value=0.55,
                    edge=5.0, confidence=60.0,
                    recommendation="BET HOME ML (edge: +6.0%)",
                    raw_json={"game_date": "2026-10-23"}, db_path=db)
                return ur._reversed_tennis_duplicate("Bob Jones", "Alice Smith", "2026-10-23"), \
                    ur._reversed_tennis_duplicate("Alice Smith", "Bob Jones", "2026-10-23")

    def test_reversed_orientation_is_detected(self):
        reversed_hit, same = self._row("Alice Smith", "Bob Jones")
        self.assertIsNotNone(reversed_hit)
        self.assertEqual("Alice Smith", reversed_hit["home_team"])
        # The same orientation is a legitimate re-price, not a duplicate fixture.
        self.assertIsNone(same)

    def test_other_dates_are_not_duplicates(self):
        from core import historical_storage as store
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = Path(tmp) / "history.db"
            with patch.object(store, "DB_PATH", db):
                store.init_db(db)
                store.store_prediction(
                    sport="tennis", home_team="Alice Smith", away_team="Bob Jones",
                    market_type="moneyline", model_value=0.6, market_value=0.55,
                    edge=5.0, confidence=60.0,
                    recommendation="BET HOME ML (edge: +6.0%)",
                    raw_json={"game_date": "2026-10-23"}, db_path=db)
                other_day = ur._reversed_tennis_duplicate("Bob Jones", "Alice Smith",
                                                         "2026-10-24")
        self.assertIsNone(other_day)


if __name__ == "__main__":
    unittest.main()
