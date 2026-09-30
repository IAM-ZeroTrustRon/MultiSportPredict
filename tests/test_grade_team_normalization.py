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