"""Two separate signals, and cohort tagging derived from them."""
import pytest

from probability_signal import (HIGH_COHORT, EXPLORATORY_COHORT,
                                cohort_for, dual_signal, format_price,
                                high_probability_lines, picked_side_signal,
                                probability_flag, value_verdict)


def test_flag_uses_the_model_probability_not_confidence():
    assert probability_flag(0.782) == "HIGH"
    assert probability_flag(0.75) == "HIGH"
    assert probability_flag(0.749) == "NORMAL"
    assert probability_flag(None) == "UNAVAILABLE"
    assert probability_flag(float("nan")) == "UNAVAILABLE"


def test_value_verdict_is_independent_of_probability():
    # The user's illustration: 78.2% to win, -450, EV -4.4% -> likely winner, no value.
    signal = dual_signal("Philadelphia moneyline", 0.782, -450, -0.044)
    assert signal["flag"] == "HIGH"
    assert signal["value_verdict"] == "PASS"
    assert signal["probability_display"] == "78.2%"
    assert signal["price_display"] == "-450"
    assert signal["ev_display"] == "-4.4%"


def test_high_block_matches_the_agreed_shape():
    lines = high_probability_lines("Philadelphia moneyline", 0.782, -450, -0.044)
    assert lines[0] == "HIGH MODEL PROBABILITY - OVER 75%"
    assert "Selection: Philadelphia moneyline" in lines
    assert "Model probability: 78.2%" in lines
    assert "Odds: -450" in lines
    assert "Estimated EV: -4.4%" in lines
    assert "Value verdict: PASS" in lines
    assert "Probability flag: HIGH" in lines


def test_block_is_silent_below_the_threshold():
    assert high_probability_lines("x", 0.60, -110, 0.02) == []


def test_block_still_renders_without_a_price():
    lines = high_probability_lines("Home: Team A", 0.81, None, None)
    assert "Odds: unavailable" in lines
    assert "Estimated EV: unavailable" in lines
    assert "Value verdict: PASS" in lines


def test_large_gap_is_labelled_neutrally_not_gated():
    lines = high_probability_lines("Home: Team A", 0.82, -300, -0.01,
                                   market_probability=0.55)
    assert any(line.startswith("MODEL/MARKET DISCREPANCY") for line in lines)
    assert not any("suppress" in line.lower() or "refuse" in line.lower() for line in lines)


def test_decimal_prices_are_not_printed_beside_american_as_if_equal():
    assert format_price(1.20) == "-500"
    assert format_price(2.50) == "+150"
    assert format_price(-110) == "-110"
    assert format_price(130) == "+130"


def test_picked_side_probability_matches_kind_and_line():
    raw = {"markets": [
        {"kind": "moneyline", "line": 0.5, "pick": "HOME", "prob_a": 0.4636,
         "prob_b": 0.5364, "price_a": 420, "price_b": -580, "ev_a": 0.10, "ev_b": -0.10},
        {"kind": "spread", "line": 13.5, "pick": "HOME", "prob_a": 0.7382,
         "prob_b": 0.2618, "price_a": -110, "price_b": -110, "ev_a": 0.05, "ev_b": -0.05},
        {"kind": "spread", "line": 10.5, "pick": "HOME", "prob_a": 0.60,
         "prob_b": 0.40, "price_a": -105, "price_b": -115, "ev_a": 0.01, "ev_b": -0.01},
    ]}
    signal = picked_side_signal("spread", raw, line=13.5)
    # Regression: a spread selection must never be priced off the moneyline
    # entry (which would make a -110 spread look like a +420 bet).
    assert signal["price"] == -110
    assert signal["probability"] == pytest.approx(0.7382)
    assert signal["price_other"] == -110


def test_alternate_lines_are_not_confused():
    raw = {"markets": [
        {"kind": "total", "line": 51.5, "pick": "UNDER", "prob_a": 0.55,
         "prob_b": 0.45, "price_a": -105, "price_b": -115, "ev_a": 0.01, "ev_b": -0.01},
    ]}
    signal = picked_side_signal("total", raw, line=51.5)
    assert signal["pick"] == "UNDER"
    assert signal["probability"] == pytest.approx(0.45)
    assert signal["price"] == -115
    assert picked_side_signal("total", raw, line=48.5) is None


def test_cohort_tags_and_exploratory_precedence():
    assert cohort_for(0.80) == HIGH_COHORT
    assert cohort_for(0.70) is None
    assert cohort_for(0.80, exploratory=True) == EXPLORATORY_COHORT
    assert cohort_for(None) is None
