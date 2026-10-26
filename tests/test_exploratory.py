"""Exploratory forecasts: every substituted input disclosed, never a value claim."""
import sqlite3

import pytest

from exploratory import (EXPLORATORY_LABEL, build, format_report, store)


def test_every_substituted_input_is_listed():
    result = build("basketball", "NBA", "Team A", "Team B", "2026-10-26")
    inputs = [item["input"] for item in result["substitutions"]]
    for expected in ("league scoring baseline", "team offensive/defensive ratings",
                     "home-court advantage", "margin volatility",
                     "injuries, lineups, rest, travel"):
        assert expected in inputs, expected
    for item in result["substitutions"]:
        assert item["source"] and item["why"]


def test_unknown_league_discloses_the_generic_fallback():
    result = build("soccer", "Unconfigured Cup", "A", "B", "2026-10-26")
    first = result["substitutions"][0]
    assert "generic fallback" in first["source"]
    assert "no configured baseline" in first["why"]


def test_probabilities_are_valid_and_no_value_is_claimed():
    for sport, league in (("basketball", "NBA"), ("soccer", "Serie A")):
        result = build(sport, league, "A", "B", "2026-10-26")
        probabilities = result["probabilities"]
        total = probabilities["home_win"] + probabilities["away_win"] + (probabilities["draw"] or 0.0)
        assert total == pytest.approx(1.0, abs=1e-6)
        assert result["recommendation"] == EXPLORATORY_LABEL
        assert "no EV" in result["note"] or "No price" in result["note"]
        assert "EV" not in result["projection"]


def test_report_states_the_limits():
    text = format_report(build("soccer", "Serie A", "Torino", "Monza", "2026-10-26"))
    assert "EXPLORATORY FORECAST" in text
    assert "SUBSTITUTED INPUTS" in text
    assert "Value: unavailable" in text
    assert "cannot make an unsupported fixture reliably predictable" in text


def test_stored_rows_land_in_their_own_cohort(tmp_path):
    db = tmp_path / "history.db"
    result = build("basketball", "NBA", "Team A", "Team B", "2026-10-26")
    store(result, db_path=db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT cohort, recommendation FROM predictions").fetchone()
    assert row["cohort"] == "EXPLORATORY"
    assert row["recommendation"] == EXPLORATORY_LABEL
    conn.close()
