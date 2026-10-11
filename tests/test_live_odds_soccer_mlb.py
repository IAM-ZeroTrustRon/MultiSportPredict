"""Tests for tennis-parity live odds: soccer + MLB auto-fetch, no manual lines."""
from __future__ import annotations

import live_odds


SOCCER_EVENT = {
    "home_team": "Lens", "away_team": "Lyon",
    "bookmakers": [{"key": "b", "markets": [
        {"key": "h2h", "outcomes": [
            {"name": "Lens", "price": 150},
            {"name": "Lyon", "price": 190},
            {"name": "Draw", "price": 220}]},
        {"key": "totals", "outcomes": [
            {"name": "Over", "price": -110, "point": 2.5},
            {"name": "Under", "price": -110, "point": 2.5}]},
        {"key": "spreads", "outcomes": [
            {"name": "Lens", "price": -110, "point": -0.5},
            {"name": "Lyon", "price": -110, "point": 0.5}]}]}],
}

MLB_EVENT = {
    "home_team": "New York Yankees", "away_team": "Boston Red Sox",
    "bookmakers": [{"key": "b", "markets": [
        {"key": "h2h", "outcomes": [
            {"name": "New York Yankees", "price": -150},
            {"name": "Boston Red Sox", "price": 130}]},
        {"key": "totals", "outcomes": [
            {"name": "Over", "price": -105, "point": 8.0},
            {"name": "Under", "price": -115, "point": 8.0}]},
        {"key": "spreads", "outcomes": [
            {"name": "New York Yankees", "price": -110, "point": -1.5},
            {"name": "Boston Red Sox", "price": -110, "point": 1.5}]}]}],
}


def test_soccer_aliases_resolve_to_covered_keys():
    for label, canonical in (("French Ligue 1", "ligue 1"),
                             ("German Bundesliga", "bundesliga"),
                             ("Spanish La Liga", "la liga"),
                             ("EPL", "premier league"),
                             ("Italian Serie A", "serie a")):
        config, canon, status = live_odds.resolve_soccer_league(label)
        assert status == "ok", label
        assert canon == canonical, label
        assert config and config.get("covered")


def test_soccer_extraction_includes_spread():
    out = live_odds._extract_soccer_market(SOCCER_EVENT)
    assert out["home_ml"] == 150 and out["draw_ml"] == 220
    assert out["total_line"] == 2.5 and out["over_price"] == -110
    assert out["spread_line"] == -0.5
    assert out["spread_home_price"] == -110 and out["spread_away_price"] == -110


def test_mlb_extraction_includes_runline_and_prices():
    out = live_odds._extract_mlb_market(MLB_EVENT)
    assert out["home_ml"] == -150 and out["away_ml"] == 130
    assert out["total_line"] == 8.0 and out["under_price"] == -115
    assert out["runline"] == -1.5
    assert out["runline_home_price"] == -110 and out["runline_away_price"] == -110


def test_unknown_league_never_raises():
    config, canonical, status = live_odds.resolve_soccer_league("Swedish SBL")
    assert status == "unknown_league" and config is None
    out = live_odds.get_soccer_odds("Swedish SBL", "A", "B")
    assert out["status"] == "unknown_league" and out["captured_at"] is None
