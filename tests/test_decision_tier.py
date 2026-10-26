"""Decision-tier classification: bare directional picks are real bets.

Regression for the asymmetry that silently dropped every bare HOME/AWAY
recommendation: `OVER`/`UNDER` counted as bets while `HOME`/`AWAY` fell through
to INFO, so NFL spread and moneyline picks were never graded or counted even
though the totals from the same fixture were.
"""
from grade_predictions import is_excluded_tier, tier_of


def test_bare_directional_sides_are_bets():
    for side in ("HOME", "AWAY", "OVER", "UNDER"):
        assert tier_of(side) == "BET", side
        assert not is_excluded_tier(side), side


def test_prefixed_sides_keep_their_tier():
    assert tier_of("BET AWAY") == "BET"
    assert tier_of("LEAN HOME") == "LEAN"
    assert tier_of("STRONG BET HOME") == "STRONG BET"


def test_declined_and_unnamed_rows_stay_excluded():
    for text in ("PASS", "PASS - market efficient",
                 "PASS — no priced model value",
                 "INFO — Insufficient NHL inputs",
                 "Over: 63.9% | Under: 36.1%"):
        assert is_excluded_tier(text), text


def test_void_rows_are_never_graded():
    assert tier_of("VOID") == "VOID"
    assert is_excluded_tier("VOID")
