#!/usr/bin/env python
"""
Regression tests for tennis best-of-3 vs best-of-5 set formatting.

Covers the bug where a WTA (best-of-3) match could show best-of-5 set
metrics: predict_tennis_match() correctly branched the underlying set
probability by best_of_5, but the human-readable label built on top of it
(_set_rec(), models/tennis_predictor.py) hardcoded "3.5 Sets" wording
regardless of format -- so a real WTA match came back with
"LEAN OVER 3.5 Sets", a result that cannot happen in a best-of-3 match.

Run directly: venv/Scripts/python.exe tests/test_tennis_set_format.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.tennis_predictor import predict_tennis_match  # noqa: E402

# Real, well-established players already in data/tennis/players.json, so
# these calls exercise the real Elo engine rather than a mock -- only the
# format-derived structure/text is asserted on, not the specific numbers.
WTA_MATCH = dict(home_player="Sabalenka A.", away_player="Swiatek I.",
                  surface="hard", best_of_5=False, market_prob=0.58)
ATP_MATCH = dict(home_player="Alcaraz C.", away_player="Sinner J.",
                  surface="hard", best_of_5=True, market_prob=0.55)

# The only set scores a best-of-3 match can ever produce.
BO3_SCORES = {"2-0", "0-2", "2-1", "1-2"}
# Scores that require a 4th or 5th set -- impossible in best-of-3.
BO5_ONLY_SCORES = {"3-0", "0-3", "3-1", "1-3", "3-2", "2-3"}


def test_wta_set_distribution_has_no_fourth_or_fifth_set():
    result = predict_tennis_match(**WTA_MATCH)
    keys = set(result["set_distribution"].keys())
    bad = keys & BO5_ONLY_SCORES
    ok = not bad and keys <= BO3_SCORES
    print(f"[{'PASS' if ok else 'FAIL'}] WTA set_distribution keys {sorted(keys)} "
          f"(best-of-5-only scores present: {sorted(bad) or 'none'})")
    return ok


def test_wta_total_games_line_is_best_of_3():
    result = predict_tennis_match(**WTA_MATCH)
    line = result["total_games"]["line"]
    ok = line == 22.5
    print(f"[{'PASS' if ok else 'FAIL'}] WTA total_games line = {line} (expected 22.5)")
    return ok


def test_wta_sets_recommendation_does_not_say_35():
    result = predict_tennis_match(**WTA_MATCH)
    text = result["sets"]["recommendation_sets_ou"]
    ok = "2.5 Sets" in text and "3.5" not in text
    print(f"[{'PASS' if ok else 'FAIL'}] WTA recommendation_sets_ou = {text!r}")
    return ok


def test_atp_set_distribution_can_reach_a_fifth_set():
    """Sanity check the other direction -- a real best-of-5 match must
    still be ABLE to show a 3-2/2-3 score, so the fix didn't just delete
    the format distinction rather than parameterize it."""
    result = predict_tennis_match(**ATP_MATCH)
    keys = set(result["set_distribution"].keys())
    ok = bool(keys & BO5_ONLY_SCORES)
    print(f"[{'PASS' if ok else 'FAIL'}] ATP set_distribution keys {sorted(keys)} "
          f"(best-of-5 scores present: {ok})")
    return ok


def test_atp_total_games_line_is_best_of_5():
    result = predict_tennis_match(**ATP_MATCH)
    line = result["total_games"]["line"]
    ok = line == 40.5
    print(f"[{'PASS' if ok else 'FAIL'}] ATP total_games line = {line} (expected 40.5)")
    return ok


def test_atp_sets_recommendation_says_35():
    result = predict_tennis_match(**ATP_MATCH)
    text = result["sets"]["recommendation_sets_ou"]
    ok = "3.5 Sets" in text
    print(f"[{'PASS' if ok else 'FAIL'}] ATP recommendation_sets_ou = {text!r}")
    return ok


def main() -> int:
    tests = [
        test_wta_set_distribution_has_no_fourth_or_fifth_set,
        test_wta_total_games_line_is_best_of_3,
        test_wta_sets_recommendation_does_not_say_35,
        test_atp_set_distribution_can_reach_a_fifth_set,
        test_atp_total_games_line_is_best_of_5,
        test_atp_sets_recommendation_says_35,
    ]
    results = []
    for test in tests:
        try:
            results.append(bool(test()))
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] {test.__name__} crashed: {exc}")
            results.append(False)

    passed = sum(results)
    total = len(results)
    print(f"\nPassed: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
