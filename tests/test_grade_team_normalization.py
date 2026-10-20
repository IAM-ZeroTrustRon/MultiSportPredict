#!/usr/bin/env python
"""Regression tests for sport-scoped grading name normalization."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from grade_predictions import normalise_team  # noqa: E402


def test_aliases_normalize_across_requested_sports():
    cases = [
        ("Doosan", "Doosan Bears", "kbo"),
        ("BAL", "Baltimore Orioles", "mlb"),
        ("Keys M.", "Madison Keys", "tennis"),
        ("Oregon St", "Oregon State Beavers", "ncaaf"),
        ("BAL", "Baltimore Ravens", "nfl"),
        ("Busan", "Busan KCC Egis", "kbl"),
        ("Hawks", "Hawke's Bay Hawks", "NZ NBL"),
        ("Efes", "Anadolu Efes", "EuroLeague"),
        ("Man City", "Manchester City", "soccer"),
    ]
    for alias, canonical, sport in cases:
        assert normalise_team(alias, sport) == normalise_team(canonical, sport)


def test_abbreviations_are_scoped_to_the_sport():
    assert normalise_team("BAL", "mlb") != normalise_team("BAL", "nfl")
    assert normalise_team("KC", "mlb") != normalise_team("KC", "nfl")
    assert normalise_team("WAS", "baseball") != normalise_team("WAS", "nfl")


def test_nfl_season_tag_is_ignored():
    assert normalise_team("Arizona Cardinals (2026)", "nfl") == normalise_team(
        "Arizona Cardinals", "nfl")

def test_tennis_completed_winner_is_returned(monkeypatch, tmp_path):
    import json
    import grade_predictions as grading
    import run_tennis
    store = tmp_path / "players.json"
    store.write_text(json.dumps({"Alcaraz C.": {}, "Sinner J.": {}}))
    monkeypatch.setattr(run_tennis, "STORE", store)
    competition = {"status": {"type": {"completed": True}}, "competitors": [
        {"homeAway": "home", "athlete": {"fullName": "Carlos Alcaraz"}, "winner": True},
        {"homeAway": "away", "athlete": {"fullName": "Jannik Sinner"}, "winner": False},
    ]}
    def payload(comp):
        return {"events": [{"groupings": [{"grouping": {"slug": "mens-singles"}, "competitions": [comp]}]}]}
    monkeypatch.setattr(grading, "_get_json", lambda url: payload(competition))
    key = ("2026-10-10", grading.normalise_team("Alcaraz C.", "tennis"), grading.normalise_team("Sinner J.", "tennis"))
    assert grading.fetch_tennis_results("2026-10-10", "2026-10-10")[key] == (1.0, 0.0)
    competition["competitors"][0]["winner"] = False
    competition["competitors"][1]["winner"] = True
    assert grading.fetch_tennis_results("2026-10-10", "2026-10-10")[key] == (0.0, 1.0)
    competition["status"]["type"]["completed"] = False
    assert grading.fetch_tennis_results("2026-10-10", "2026-10-10") == {}
    competition["status"]["type"]["completed"] = True
    competition["competitors"][0]["athlete"]["fullName"] = "Unknown Player"
    assert grading.fetch_tennis_results("2026-10-10", "2026-10-10") == {}
