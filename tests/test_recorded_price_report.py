"""Recorded-price model returns exclude assumed prices and duplicate reruns."""
import json
import sqlite3
from unittest.mock import Mock

import pytest

import grade_predictions as g
import msp_workflow as workflow


def row(ident, outcome="win", profit=1.5, sport="tennis", raw=None, **updates):
    result = dict(id=ident, sport=sport, league=None, home_team=f"Home {ident}",
                  away_team=f"Away {ident}", game_date="2026-10-20", market_type="moneyline",
                  recommendation="BET HOME", result_outcome=outcome, profit_loss=profit,
                  raw_json=json.dumps(raw if raw is not None else {
                      "_settled_at_recorded_price": True, "_settled_odds": 150}))
    result.update(updates)
    return result


def test_pushes_are_in_risk_but_not_win_percentage():
    result = g.recorded_price_breakdown([
        row(1), row(2, "loss", -1), row(3, "push", 0, sport="basketball")])
    assert result["overall"]["n"] == 3
    assert result["overall"]["win_pct"] == 50
    assert result["overall"]["units"] == .5
    assert result["overall"]["roi"] == pytest.approx(100 / 6)
    assert result["by_sport"]["basketball"]["win_pct"] is None
    assert result["by_sport"]["tennis"]["roi"] == 25


def test_stored_quarter_kelly_stakes_weight_turnover_and_units():
    result = g.stake_weighted_breakdown([
        row(1, stake_size=.05), row(2, "loss", -1, stake_size=.02),
        row(3, "push", 0, stake_size=.01)])
    assert result["n"] == 3
    assert result["staked"] == pytest.approx(.08)
    assert result["units"] == pytest.approx(.05*1.5 - .02)
    assert result["roi"] == pytest.approx((.05*1.5 - .02)/.08*100)
    assert result["excluded_without_stake"] == 0
    assert result["win_pct"] == 50


def test_rows_without_a_valid_stake_are_excluded_not_defaulted():
    result = g.stake_weighted_breakdown([
        row(1, stake_size=.05), row(2), row(3, stake_size=.5),
        row(4, stake_size="0.02"), row(5, stake_size=True)])
    assert result["n"] == 1
    assert result["staked"] == pytest.approx(.05)
    assert result["excluded_without_stake"] == 4
    assert result["roi"] == pytest.approx(150)


@pytest.mark.parametrize("raw,profit", [
    ({"_settled_at_recorded_price": False, "_settled_odds": -110}, 1),
    ({"_settled_at_recorded_price": True}, 1),
    ({"_settled_at_recorded_price": "true", "_settled_odds": 150}, 1),
    ({"_settled_at_recorded_price": True, "_settled_odds": 0}, 1),
    ({"_settled_at_recorded_price": True, "_settled_odds": "NaN"}, 1),
    ({"_settled_at_recorded_price": True, "_settled_odds": True}, 1),
    ([], 1),
    ({"_settled_at_recorded_price": True, "_settled_odds": 150}, None),
    ({"_settled_at_recorded_price": True, "_settled_odds": 150}, float("inf")),
    ({"_settled_at_recorded_price": True, "_settled_odds": 150}, True),
])
def test_invalid_or_assumed_price_settlements_are_excluded(raw, profit):
    result = g.recorded_price_breakdown([row(1, raw=raw, profit=profit)])
    assert result["overall"]["n"] == 0
    assert result["overall"]["roi"] is None
    assert result["excluded"] == 1


def test_dedup_happens_before_price_filter_and_reversed_sides_collapse():
    old = row(1)
    newer = row(2, home_team=old["away_team"], away_team=old["home_team"], raw={})
    result = g.recorded_price_breakdown([old, newer])
    assert result["overall"]["n"] == 0
    assert result["excluded"] == 1


def test_negative_american_price_and_numeric_saved_profit_are_supported():
    original = row(1, profit="0.5", raw={"_settled_at_recorded_price": True, "_settled_odds": -200})
    result = g.recorded_price_breakdown([original])
    assert result["overall"]["units"] == .5
    assert result["overall"]["roi"] == 50
    assert original["profit_loss"] == "0.5"


def test_malformed_json_excluded_and_pass_info_void_unsettled_not_counted():
    rows = [row(1, raw_json="bad JSON"), row(2, recommendation="PASS"),
            row(3, recommendation="INFO"), row(4, recommendation="VOID"),
            row(5, outcome=None)]
    result = g.recorded_price_breakdown(rows)
    assert result["overall"]["n"] == 0
    assert result["excluded"] == 1
    assert result["by_sport"] == {}


def test_terminal_table_is_explicit_about_units_and_basis(capsys):
    g.print_recorded_price_table(g.recorded_price_breakdown([row(1)]))
    output = capsys.readouterr().out
    assert "RECORDED PRICES ONLY" in output
    assert "1-0-0" in output and "+150.00%" in output
    assert "not confirmed wagers" in output


def test_discord_record_includes_separate_price_table_without_real_send(monkeypatch):
    monkeypatch.setenv("DISCORD_RESULTS_WEBHOOK_URL", "https://example.invalid/test")
    monkeypatch.setattr(g, "_HAS_REQUESTS", True)
    send = Mock(return_value=Mock(status_code=204))
    monkeypatch.setattr(g.requests, "post", send)
    rows = [row(1), row(2, "push", 0)]
    g._push_record_to_discord(rows, rows, None)
    embeds = send.call_args.kwargs["json"]["embeds"]
    assert len(embeds) == 2
    assert "ROI +75.00%" in embeds[1]["description"]
    assert "assumed odds" in embeds[0]["description"]


def test_workflow_and_detailed_report_share_the_same_calculation(monkeypatch, tmp_path, capsys):
    path = tmp_path / "history.db"
    rows = [row(1), row(2, "loss", -1), row(3, "push", 0, sport="basketball"), row(4, raw={})]
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE predictions (id INTEGER, sport TEXT, league TEXT, home_team TEXT, away_team TEXT, game_date TEXT, market_type TEXT, recommendation TEXT, result_outcome TEXT, profit_loss REAL, raw_json TEXT, confidence REAL)")
        for r in rows:
            conn.execute("INSERT INTO predictions VALUES (?,?,?,?,?,?,?,?,?,?,?,NULL)", tuple(r[k] for k in ["id", "sport", "league", "home_team", "away_team", "game_date", "market_type", "recommendation", "result_outcome", "profit_loss", "raw_json"]))
    original_read = workflow.read_db
    monkeypatch.setattr(workflow, "read_db", lambda: original_read(path))
    summary = workflow.record(True)
    assert summary["recorded_price_model_decisions"]["n"] == 3
    assert summary["recorded_price_model_decisions"]["units"] == .5
    assert summary["settlement_prices"] == {"recorded": 3, "default_or_unknown": 1}
    assert summary["recorded_price_model_decisions_by_sport"]["tennis"]["roi"] == 25
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        g.cmd_report(conn, None, None, False)
    assert "RECORDED PRICES ONLY" in capsys.readouterr().out
