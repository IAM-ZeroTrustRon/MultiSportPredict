import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import soccer_resolution as sr

HOME = "Alpha FC"
AWAY = "Beta FC"
STATS = {"xg_for": 1.6, "xg_against": 1.1}


class ResolutionTierTests(unittest.TestCase):
    def test_local_hit_is_tier_one_and_never_refreshes(self):
        with patch.object(sr, "_lookup", return_value=(STATS, STATS)), \
                patch.object(sr, "refresh_once") as refresh:
            home, away, tier, notes = sr.resolve_team_stats(HOME, AWAY, "Bundesliga")
        self.assertEqual(sr.TIER_LOCAL, tier)
        self.assertEqual(STATS, home)
        refresh.assert_not_called()
        self.assertTrue(any("local history" in note for note in notes))

    def test_miss_without_refresh_is_tier_three_but_keeps_the_side_that_resolved(self):
        with patch.object(sr, "_lookup", return_value=(None, STATS)), \
                patch.object(sr, "refresh_once") as refresh:
            home, away, tier, notes = sr.resolve_team_stats(HOME, AWAY, "Bundesliga",
                                                            refresh=False)
        self.assertEqual(sr.TIER_EXPLORATORY, tier)
        self.assertIsNone(home)
        # The verified side is not thrown away because its opponent is missing.
        self.assertEqual(STATS, away)
        refresh.assert_not_called()
        self.assertTrue(any("refresh disabled" in note for note in notes))

    def test_one_refresh_can_promote_to_tier_two(self):
        calls = {"n": 0}

        def lookup(*_args):
            calls["n"] += 1
            return (None, None) if calls["n"] == 1 else (STATS, STATS)

        with patch.object(sr, "_lookup", side_effect=lookup), \
                patch.object(sr, "refresh_once", return_value=(True, ["espn: ok"])) as refresh:
            home, away, tier, notes = sr.resolve_team_stats(HOME, AWAY, "Bundesliga")
        self.assertEqual(sr.TIER_REFRESHED, tier)
        self.assertEqual(STATS, away)
        refresh.assert_called_once()
        self.assertTrue(any("one supported public refresh" in note for note in notes))

    def test_failed_refresh_stays_exploratory(self):
        with patch.object(sr, "_lookup", return_value=(None, None)), \
                patch.object(sr, "refresh_once", return_value=(False, ["espn: failed"])):
            home, away, tier, notes = sr.resolve_team_stats(HOME, AWAY, "Bundesliga")
        self.assertEqual(sr.TIER_EXPLORATORY, tier)
        self.assertIsNone(home)
        self.assertTrue(any("still missing" in note for note in notes))


class ExploratoryObservationTests(unittest.TestCase):
    def test_observation_discloses_every_substitution_and_stays_out_of_the_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(sr, "ROOT", root):
                document = sr.exploratory_observation(HOME, AWAY, "Bundesliga", "2026-10-31")
            path = root / document["path"]
            self.assertTrue(path.exists())
            saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(document["exploratory"])
        self.assertEqual("EXPLORATORY", document["cohort"])
        self.assertFalse(document["value_ledger"])
        self.assertGreaterEqual(len(document["substitutions"]), 3)
        self.assertIn("EXPLORATORY SOCCER OBSERVATION", document["card"])
        self.assertNotIn("EV", saved["projection"])

    def test_every_substitution_names_its_source_and_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(sr, "ROOT", Path(tmp)):
                document = sr.exploratory_observation(HOME, AWAY, "Bundesliga", "2026-10-31")
        for item in document["substitutions"]:
            self.assertTrue(item["input"])
            self.assertTrue(item["source"])
            self.assertTrue(item["why"])
        self.assertIn("excluded from the value record", document["card"])

    def test_partial_data_keeps_the_measured_side_and_substitutes_only_the_other(self):
        strong = {"xg_for": 2.5, "goals_for": 2.5, "xg_against": 1.0, "games": 9,
                  "season": "2026", "source": "test store"}
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(sr, "ROOT", Path(tmp)):
                pure = sr.exploratory_observation(HOME, AWAY, "Bundesliga", "2026-10-31")
                partial = sr.exploratory_observation(HOME, AWAY, "Bundesliga", "2026-10-31",
                                                     home_stats=strong)
        self.assertTrue(partial["partial"])
        self.assertEqual([HOME], partial["verified_sides"])
        self.assertEqual([AWAY], partial["substituted_sides"])
        self.assertEqual("MEASURED", partial["inputs"]["home"]["status"])
        self.assertEqual("SUBSTITUTED", partial["inputs"]["away"]["status"])
        # The verified side's own scoring rate replaces its league placeholder.
        self.assertGreater(partial["projection"]["home_goals"], pure["projection"]["home_goals"])
        self.assertIn("MEASURED", partial["card"])
        self.assertIn("SUBSTITUTED", partial["card"])
        self.assertIn(HOME, partial["card"])
        self.assertFalse(pure["partial"])
        self.assertNotIn("EV", partial["projection"])

    def test_measured_side_is_named_in_the_substitution_list_as_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(sr, "ROOT", Path(tmp)):
                document = sr.exploratory_observation(HOME, AWAY, "Bundesliga", "2026-10-31",
                                                      away_stats={"goals_for": 1.9})
        measured = [item for item in document["substitutions"] if "verified" in item["value"]]
        self.assertTrue(measured)
        self.assertTrue(any(AWAY in item["input"] for item in measured))
        self.assertEqual([AWAY], document["verified_sides"])

    def test_unknown_league_uses_declared_generic_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(sr, "ROOT", Path(tmp)):
                document = sr.exploratory_observation(HOME, AWAY, "Nowhere League", "2026-10-31")
        joined = " ".join(item["why"] for item in document["substitutions"])
        self.assertIn("Nowhere League", joined)


if __name__ == "__main__":
    unittest.main()
