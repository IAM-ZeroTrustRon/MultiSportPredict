import tempfile
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import ingest_tennis as ingest
from models.tennis_elo import TennisElo


class TennisIngestTests(unittest.TestCase):
    def test_partial_failure_preserves_wta(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            original = {"Old WTA": dict(tour="wta", last_rank=7)}
            (out / "players.json").write_text(json.dumps(original))
            (out / "matches.csv").write_text("winner_name,loser_name,surface,tournament_date\nOld WTA,Other WTA,hard,2026-08-24\n")
            blob = b"winner_name,loser_name,surface,tourney_date,score\nCarlos Alcaraz,Jannik Sinner,Hard,20260929,6-4 6-4\n"
            def download(url):
                if "tennismylife" in url:
                    return blob
                raise OSError("unavailable")
            with patch.object(ingest, "OUT_DIR", out), patch.object(ingest, "fetch", download), patch("sys.argv", ["ingest", "--years", "2026"]), patch.object(ingest, "log"), patch("tennis_sources.wta_season_rows", side_effect=OSError("offline")), patch("tennis_sources.atp_recent_rows", return_value=([], set())):
                with self.assertRaises(SystemExit) as error:
                    ingest.main()
            self.assertEqual(error.exception.code, 1)
            store = json.loads((out / "players.json").read_text())
            self.assertEqual(store["Old WTA"], original["Old WTA"])
            self.assertIn("Carlos Alcaraz", store)
            before = {p.name: p.read_bytes() for p in out.iterdir()}
            with patch.object(ingest, "OUT_DIR", out), patch.object(ingest, "fetch", side_effect=OSError("offline")), patch("sys.argv", ["ingest", "--years", "2026"]), patch.object(ingest, "log"), patch("tennis_sources.wta_season_rows", side_effect=OSError("offline")), patch("tennis_sources.atp_recent_rows", return_value=([], set())):
                with self.assertRaises(SystemExit):
                    ingest.main()
            self.assertEqual(before, {p.name: p.read_bytes() for p in out.iterdir()})

    def test_csv_mapping_and_walkover(self):
        row = dict(winner_name="Carlos Alcaraz", loser_name="Jannik Sinner",
                   surface="Hard", tourney_date="20260929", winner_rank="1",
                   loser_rank="2", score="6-4 6-4")
        matches, _ = ingest.parse_rows([row, dict(row, score="W/O")], "atp")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].date, "2026-09-29")
        self.assertEqual(matches[0].wrank, 1)
        self.assertIsNone(ingest.as_date("20261399"))
        unknown, dropped = ingest.parse_rows([dict(row, surface="Unknown")], "atp")
        self.assertEqual(unknown, [])
        self.assertTrue(dropped)

    def test_source_urls(self):
        urls = ingest.archive_urls("atp", 2026)
        self.assertEqual(len(urls), len(set(urls)))
        self.assertEqual(urls[0], "https://stats.tennismylife.org/data/2026.csv")
        self.assertIn("/2026w/2026.xlsx", ingest.archive_urls("wta", 2026)[0])

    def test_real_history_excludes_seeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "matches.csv"
            path.write_text("winner_name,loser_name,surface,tournament_date\nA,B,hard,2026-09-29\n")
            engine = TennisElo()
            self.assertEqual(engine.load_match_history(str(path)), 1)
            self.assertEqual(set(engine.ratings), {"A", "B"})
            with self.assertRaises(FileNotFoundError):
                TennisElo().load_match_history(str(path) + "missing")


if __name__ == "__main__":
    unittest.main()
