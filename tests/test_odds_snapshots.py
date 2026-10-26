"""Immutable odds snapshots, pre-kickoff closing capture and CLV separation."""
import datetime as dt
import sqlite3

import pytest

from core.historical_storage import (capture_prediction_odds, get_odds_snapshots,
                                     init_db, save_odds_snapshot)
from closing_collector import collect as _collect
from clv import clv_report, compare_snapshots

UTC = dt.timezone.utc
KICKOFF = "2026-10-31T19:30:00Z"
OBSERVED = "2026-10-31T12:05:00Z"


def prediction_result(kind="spread", line=-3.5, price_a=-110, price_b=-110):
    return {
        "sport": "ncaaf", "league": "NCAAF", "game_id": "401",
        "game_date": "2026-10-31", "home_team": "Georgia Bulldogs",
        "away_team": "Florida Gators",
        "fixture": {"start_time": KICKOFF},
        "settlement": {"scope": "full_game_including_overtime"},
        "markets": [{"kind": kind, "line": line, "price_a": price_a, "price_b": price_b,
                     "pick": "HOME", "stake_size": 0.03}],
        "odds_source": {"note": "Bookmaker draftkings; event evt1", "markets": [
            {"kind": kind, "line": line, "price_a": price_a, "price_b": price_b,
             "bookmaker": "draftkings", "updated": "2026-10-31T12:00:00Z",
             "source_event_id": "evt1", "scope": "full_game_including_overtime"}]},
    }


def snapshot(kind, observed, price_a=-110, price_b=-110, market="moneyline", line=0.5,
             kickoff=KICKOFF, quote_updated=None):
    return {
        "capture_kind": kind, "sport": "nhl", "league": "NHL",
        "event_key": f"NHL:evt1:{market}:{line}", "source_event_id": "evt1",
        "game_date": "2026-10-31", "kickoff_utc": kickoff,
        "home_team": "Florida Panthers", "away_team": "Chicago Blackhawks",
        "market_type": market, "line": line, "price_a": price_a, "price_b": price_b,
        "bookmaker": "draftkings", "observed_utc": observed,
        "quote_updated_utc": quote_updated or observed,
        "scope": "official_final_including_ot_so", "payload": {"period":"full_game"},
    }


def event(commence=KICKOFF, market_update="2026-10-31T17:20:00Z"):
    market = {"key": "spreads", "last_update": market_update, "outcomes": [
        {"name": "Georgia Bulldogs", "point": -3.5, "price": -110},
        {"name": "Florida Gators", "point": 3.5, "price": -110}]}
    return {"id": "evt1", "commence_time": commence, "home_team": "Georgia Bulldogs",
            "away_team": "Florida Gators",
            "bookmakers": [{"key": "draftkings", "markets": [market]}]}


def collect(events, league, **kwargs):
    db=kwargs.get("db_path")
    capture_prediction_odds(prediction_result(),db,observed_utc=OBSERVED)
    kwargs.setdefault("window_minutes",180)
    kwargs.setdefault("min_lead_minutes",10)
    kwargs.setdefault("max_quote_age_minutes",60)
    kwargs["fixtures"]=[dict(game_id="401",home_team="Georgia Bulldogs",away_team="Florida Gators",
                              date="2026-10-31",start_time=KICKOFF,status="STATUS_SCHEDULED",completed=False)]
    return _collect(events,league,**kwargs)


def test_prediction_capture_archives_the_stored_price_pair(tmp_path):
    db = tmp_path / "history.db"
    init_db(db)
    capture = capture_prediction_odds(prediction_result(), db, observed_utc=OBSERVED)
    assert capture["refused"] == []
    assert [row["inserted"] for row in capture["saved"]] == [True]

    rows = get_odds_snapshots(db)
    assert len(rows) == 1
    row = rows[0]
    assert row["capture_kind"] == "prediction"
    assert row["event_key"] == "NCAAF:401:spread:-3.5"
    assert (row["price_a"], row["price_b"]) == (-110, -110)
    assert (row["home_team"], row["away_team"]) == ("Georgia Bulldogs", "Florida Gators")
    assert row["bookmaker"] == "draftkings"
    assert row["source_event_id"] == "evt1"
    assert row["scope"] == "full_game_including_overtime"
    assert row["kickoff_utc"] == "2026-10-31T19:30:00+00:00"
    assert row["observed_utc"] == "2026-10-31T12:05:00+00:00"


def test_capture_skips_markets_without_a_complete_price_pair(tmp_path):
    db = tmp_path / "history.db"
    init_db(db)
    result = prediction_result()
    result["markets"][0]["price_b"] = None
    capture = capture_prediction_odds(result, db, observed_utc=OBSERVED)
    assert capture["saved"] == []
    assert capture["skipped_without_price"] == 1
    assert get_odds_snapshots(db) == []


def test_snapshots_are_append_only(tmp_path):
    db = tmp_path / "history.db"
    init_db(db)
    first = save_odds_snapshot(snapshot("prediction", OBSERVED), db)
    again = save_odds_snapshot(snapshot("prediction", OBSERVED), db)
    later = save_odds_snapshot(snapshot("prediction", "2026-10-31T13:00:00Z"), db)

    assert first["inserted"] is True
    assert again["inserted"] is False          # identical observation is not duplicated
    assert later["inserted"] is True           # a new observation is a new row
    assert len(get_odds_snapshots(db)) == 2

    with sqlite3.connect(db) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE odds_snapshots SET price_a = 500")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM odds_snapshots")


def test_closing_capture_requires_a_verified_pre_kickoff_observation(tmp_path):
    db = tmp_path / "history.db"
    init_db(db)
    assert save_odds_snapshot(snapshot("closing", "2026-10-31T19:00:00Z"), db)["inserted"]

    with pytest.raises(ValueError, match="in-play"):
        save_odds_snapshot(snapshot("closing", "2026-10-31T19:30:00Z"), db)
    with pytest.raises(ValueError, match="in-play"):
        save_odds_snapshot(snapshot("closing", "2026-10-31T19:00:00Z",
                                    quote_updated="2026-10-31T19:31:00Z"), db)
    with pytest.raises(ValueError, match="verified kickoff"):
        save_odds_snapshot(snapshot("closing", "2026-10-31T19:00:00Z", kickoff=None), db)
    with pytest.raises(ValueError, match="timezone"):
        save_odds_snapshot(snapshot("closing", "2026-10-31T19:00:00"), db)
    assert len(get_odds_snapshots(db)) == 1


def test_prediction_capture_reports_an_in_play_quote_instead_of_storing_it(tmp_path):
    db = tmp_path / "history.db"
    init_db(db)
    capture = capture_prediction_odds(prediction_result(), db,
                                      observed_utc="2026-10-31T20:00:00Z")
    assert capture["saved"] == []
    assert "in-play" in capture["refused"][0]["reason"]
    assert get_odds_snapshots(db) == []


def test_collector_captures_only_verified_pre_kickoff_quotes(tmp_path):
    db = tmp_path / "history.db"
    init_db(db)
    report = collect([event()], "NCAAF", now=dt.datetime(2026, 10, 31, 17, 30, tzinfo=UTC),
                     db_path=db)
    assert report["refused"] == []
    assert len(report["captured"]) == 1

    rows = get_odds_snapshots(db,capture_kind="closing")
    assert len(rows) == 1
    row = rows[0]
    assert row["capture_kind"] == "closing"
    assert row["event_key"] == "NCAAF:evt1:spread:-3.5"
    assert row["kickoff_utc"] == "2026-10-31T19:30:00+00:00"
    assert row["observed_utc"] == "2026-10-31T17:30:00+00:00"
    assert row["quote_updated_utc"] == "2026-10-31T17:20:00+00:00"


def test_collector_refuses_in_play_events(tmp_path):
    db = tmp_path / "history.db"
    init_db(db)
    report = collect([event()], "NCAAF", now=dt.datetime(2026, 10, 31, 20, 0, tzinfo=UTC),
                     db_path=db)
    assert report["captured"] == []
    assert report["refused"][0]["reason"] == "in_play"
    assert get_odds_snapshots(db,capture_kind="closing") == []


def test_collector_refuses_stale_or_unverified_quotes(tmp_path):
    db = tmp_path / "history.db"
    init_db(db)
    stale = collect([event(market_update="2026-10-31T16:00:00Z")], "NCAAF",
                    now=dt.datetime(2026, 10, 31, 17, 30, tzinfo=UTC),
                    max_quote_age_minutes=30, db_path=db)
    assert stale["refused"][0]["reason"] == "stale_quote"

    unverified = event()
    unverified["bookmakers"][0]["markets"][0].pop("last_update")
    unverified["bookmakers"][0].pop("last_update", None)
    result = collect([unverified], "NCAAF", now=dt.datetime(2026, 10, 31, 17, 30, tzinfo=UTC),
                     db_path=db)
    assert result["refused"][0]["reason"] == "unverified_quote_time"
    assert get_odds_snapshots(db,capture_kind="closing") == []


def test_collector_skips_events_outside_the_window(tmp_path):
    db = tmp_path / "history.db"
    init_db(db)
    report = collect([event()], "NCAAF", now=dt.datetime(2026, 10, 31, 9, 0, tzinfo=UTC),
                     window_minutes=180, db_path=db)
    assert report["captured"] == [] and report["refused"] == []
    assert report["outside_window"][0]["minutes_to_kickoff"] == 630.0


def test_identical_line_clv_is_measured_on_the_same_line(tmp_path):
    db = tmp_path / "history.db"
    init_db(db)
    save_odds_snapshot(snapshot("prediction", OBSERVED, price_a=120, price_b=-140), db)
    save_odds_snapshot(snapshot("closing", "2026-10-31T19:00:00Z",
                                price_a=100, price_b=-120), db)

    report = clv_report(db)
    assert report["exact_line"]["n"] == 1
    assert report["line_movement"]["n"] == 0
    comparison = report["comparisons"][0]
    assert comparison["comparison"] == "exact_line"
    # +120 (2.20) taken before it closed at +100 (2.00) is a 10% beat.
    assert comparison["sides"]["a"]["price_clv"] == pytest.approx(0.10)
    assert report["exact_line"]["mean_price_clv_a"] == pytest.approx(0.10)
    assert report["exact_line"]["share_positive_a"] == 1.0
    assert report["exact_line"]["mean_fair_prob_clv_pp_a"] is not None


def test_line_movement_is_reported_separately_from_clv(tmp_path):
    db = tmp_path / "history.db"
    init_db(db)
    save_odds_snapshot(snapshot("prediction", OBSERVED, market="spread", line=-3.5), db)
    save_odds_snapshot(snapshot("closing", "2026-10-31T19:00:00Z", market="spread", line=-4.5), db)

    report = clv_report(db)
    assert report["exact_line"]["n"] == 0
    assert report["exact_line"]["mean_price_clv_a"] is None
    assert report["line_movement"]["n"] == 1
    assert report["line_movement"]["mean_delta"] == pytest.approx(-1.0)
    assert report["line_movement"]["by_market"] == {"spread": 1}

    comparison = report["comparisons"][0]
    assert comparison["comparison"] == "line_moved"
    assert (comparison["prediction_line"], comparison["closing_line"]) == (-3.5, -4.5)
    assert "price_clv" not in comparison
    assert "sides" not in comparison


def test_latest_reference_reports_line_movement_instead_of_cherry_picking_old_line(tmp_path):
    db = tmp_path / "history.db"
    init_db(db)
    save_odds_snapshot(snapshot("prediction", OBSERVED, market="spread", line=-3.5), db)
    save_odds_snapshot(snapshot("closing", "2026-10-31T19:00:00Z", market="spread", line=-3.5,
                                price_a=100, price_b=-120), db)
    save_odds_snapshot(snapshot("closing", "2026-10-31T19:05:00Z", market="spread", line=-4.5), db)

    report = clv_report(db)
    assert report["line_movement"]["n"] == 1
    assert report["exact_line"]["n"] == 0


def test_compare_refuses_a_closing_capture_observed_after_kickoff():
    prediction = snapshot("prediction", OBSERVED)
    closing = snapshot("closing", "2026-10-31T19:45:00Z")
    result = compare_snapshots(prediction, closing)
    assert result["comparison"] == "refused_in_play"
    assert "at or after kickoff" in result["reason"]


def test_integer_lines_keep_price_clv_without_a_de_vigged_probability(tmp_path):
    db = tmp_path / "history.db"
    init_db(db)
    save_odds_snapshot(snapshot("prediction", OBSERVED, market="total", line=6.0), db)
    save_odds_snapshot(snapshot("closing", "2026-10-31T19:00:00Z", market="total", line=6.0,
                                price_a=100, price_b=-120), db)
    comparison = clv_report(db)["comparisons"][0]
    assert comparison["comparison"] == "exact_line"
    assert comparison["sides"]["a"]["price_clv"] == pytest.approx(1.909090909 / 2.0 - 1)
    assert comparison["sides"]["a"]["fair_prob_clv_pp"] is None


def test_report_counts_a_group_without_a_closing_capture_as_unmatched(tmp_path):
    db = tmp_path / "history.db"
    init_db(db)
    save_odds_snapshot(snapshot("prediction", OBSERVED), db)
    report = clv_report(db)
    assert report["exact_line"]["n"] == 0
    assert report["unmatched"]["no_closing_snapshot"] == 1
    assert report["snapshots"] == 1
