"""Current-season counters must not turn early-season observations into bets."""
import copy
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from models.basketball_readiness import PROJECTION_ONLY, readiness, season_game_counts, season_count_metadata
from run_ncaaf import predict_fixture, store
from score_review import format_review, card_shape
from grade_predictions import is_excluded_tier


def fixture(league="NBA"):
    return dict(league=league, season=2027, game_id="upcoming", date="2026-11-20", home_team="A", away_team="B")


def history(n=10, league="NBA", season=2027):
    return [dict(league=league, season=season, game_id=str(i), date=f"2026-11-{i+1:02d}",
                 completed=True, season_type=2, status="STATUS_FINAL", home_team="A", away_team="B",
                 home_score=110+i, away_score=100+i) for i in range(n)]


def model(rows):
    return SimpleNamespace(games=rows, cutoff="2026-11-20", predict=lambda *args: dict(
        home_points=120, away_points=100, margin_sd=10, total_sd=20, note="Test model"))


def prediction(rows, league="NBA"):
    return predict_fixture(fixture(league), model(rows), [dict(kind="moneyline", line=.5, price_a=100, price_b=-110)], "basketball")


@pytest.mark.parametrize("league,threshold", [("NBA", 10), ("NCAAB", 8)])
def test_exact_threshold_and_one_team_short(league, threshold):
    rows = history(threshold, league)
    assert readiness(fixture(league), rows, "2026-11-20")["eligible"]
    rows[-1]["away_team"] = "C"
    gate = readiness(fixture(league), rows, "2026-11-20")
    assert not gate["eligible"]
    assert gate["season_games_played"] == {"home": threshold, "away": threshold-1}


def test_previous_season_and_future_same_day_preseason_nonfinal_do_not_count():
    rows = history(2)
    extras = [dict(rows[0], game_id="old", season=2026),
              dict(rows[0], game_id="future", date="2026-12-01"),
              dict(rows[0], game_id="same-day", date="2026-11-20"),
              dict(rows[0], game_id="preseason", season_type=1),
              dict(rows[0], game_id="scheduled", completed=False),
              dict(rows[0], game_id="canceled", status="STATUS_CANCELED"),
              dict(rows[0], game_id="no-score", home_score=None),
              dict(rows[0], game_id="bad-score", home_score=float("nan")),
              dict(rows[0], game_id="other-league", league="NCAAB")]
    counts = season_game_counts(rows+rows+extras, "NBA", 2027, "2026-11-20", ["A", "B", "C"])
    assert counts == {"A": 2, "B": 2, "C": 0}


def test_fixture_season_not_calendar_year_selects_counts():
    rows = history(10)+history(12, season=2026)
    gate = readiness(fixture(), rows, "2026-11-20")
    assert gate["season_games_played"] == {"home": 10, "away": 10}
    assert gate["season"] == 2027


def test_unknown_season_never_guesses_current_year():
    game = fixture(); game.pop("season")
    gate = readiness(game, history(), "2026-11-20")
    assert gate["season"] is None and not gate["eligible"]
    assert gate["season_games_played"] == {"home": None, "away": None}


def test_metadata_has_every_team_and_season_and_explicit_cutoff():
    result = season_count_metadata(history(2)+history(3, season=2026), "NBA", "2026-11-20", ["A", "B", "New Team"])
    assert result["by_season"]["2027"]["New Team"] == 0
    assert result["by_season"]["2026"]["A"] == 3
    assert result["counted_before"] == "2026-11-20"


def test_low_readiness_preserves_projection_and_odds_but_nulls_ev_and_pick():
    r = prediction(history(2))
    assert r["projection"]["home_points"] == 120
    assert r["projection"]["season_games_played"] == {"home": 2, "away": 2}
    market = r["markets"][0]
    assert market["price_a"] == 100 and market["prob_a"] > .9
    assert market["ev_a"] is None and market["ev_b"] is None and market["pick"] is None
    assert is_excluded_tier(market["recommendation"])
    assert market["status"] == PROJECTION_ONLY
    json.dumps(r, allow_nan=False)


def test_formatter_and_discord_defensively_hide_even_stale_ev_and_lean():
    r = prediction(history(2))
    r["markets"][0].update(ev_a=.9, ev_b=-.9, pick="HOME", recommendation="LEAN HOME")
    original = copy.deepcopy(r)
    text = format_review(r)
    assert PROJECTION_ONLY in text and "Home 2 | Away 2 | Required each: 10" in text
    assert "+90.00%" not in text and "LEAN" not in text
    card = json.dumps(card_shape(r), ensure_ascii=False)
    assert PROJECTION_ONLY in card and "LEAN" not in card and "+90.00%" not in card
    assert r == original


def test_ready_model_reenables_usual_market_calculation_and_ncaab_has_no_q1():
    r = prediction(history(10))
    assert r["readiness"]["eligible"]
    assert r["markets"][0]["ev_a"] > .5
    assert r["markets"][0]["pick"] == "HOME"
    college = prediction(history(8, "NCAAB"), "NCAAB")
    assert college["readiness"]["eligible"]
    assert "q1_projection" not in college and "1ST QUARTER" not in format_review(college)


def test_store_keeps_info_observation_excluded_from_betting_record():
    r = prediction(history(2))
    r["markets"][0].update(ev_a=.9, pick="HOME", recommendation="LEAN HOME")
    with patch("core.historical_storage.init_db"), patch("core.historical_storage.store_prediction") as save:
        store(r)
    args = save.call_args.args
    assert args[6] is None
    assert is_excluded_tier(args[8])
    assert args[9]["_pick"] is None
    assert args[9]["markets"][0]["ev_a"] is None


def test_other_leagues_and_football_are_unchanged():
    r = prediction(history(1, "KBL"), "KBL")
    assert "readiness" not in r and r["markets"][0]["ev_a"] > .5
    g = fixture("NCAAF")
    r = predict_fixture(g, model([]), [dict(kind="moneyline", line=.5, price_a=100, price_b=-110)], "ncaaf")
    assert "readiness" not in r and r["markets"][0]["pick"] == "HOME"


def test_ingest_attaches_counts_for_registry_teams_without_network(monkeypatch):
    import ingest_basketball_espn as ingest
    monkeypatch.setattr(ingest, "today", lambda: "2026-11-20")
    teams = [{"team": {"id": str(i), "displayName": name}} for i, name in enumerate(["A", "B", "New Team"])]
    games = [dict(x, home_id="0", away_id="1", game_id=str(i), date="2026-11-01")
             for i, x in enumerate(history(10)*8)]
    monkeypatch.setattr(ingest, "parse_game", lambda event, league: dict(event))
    monkeypatch.setattr(ingest, "fetch_json", lambda url: {"sports": [{"leagues": [{"teams": teams}]}]} if "/teams?" in url else {"events": [] if "seasontype=3" in url else games})
    result = ingest.ingest("NBA", [2027], check=True)
    assert result["season_games_played"]["by_season"]["2027"] == {"A": 80, "B": 80, "New Team": 0}
