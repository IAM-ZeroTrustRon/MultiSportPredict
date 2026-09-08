#!/usr/bin/env python
"""
Regression tests for run_soccer_batch.resolve().

Covers the cross-league/cross-tier name collision that let "FC Utrecht
Youth" silently resolve to senior "Utrecht" and "FC Eindhoven" to
"PSV Eindhoven" -- two real, separate clubs each, wrongly matched because
the resolver ignored the `league` field every stored team already carries.
Run directly: venv/Scripts/python.exe tests/test_soccer_resolver.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from run_soccer_batch import resolve  # noqa: E402

# A synthetic store, not the live data file, so this test can't be broken by
# a future re-ingest changing what's actually on disk.
STORE = {
    "Utrecht":          {"league": "Eredivisie"},
    "Jong AZ Alkmaar":  {"league": "Eerste Divisie"},
    "AZ Alkmaar":       {"league": "Eredivisie"},
    "PSV Eindhoven":    {"league": "Eredivisie"},
    "Bournemouth":      {"league": "Premier League"},
}


def test_utrecht_youth_does_not_resolve_to_senior_utrecht():
    """Same base name, different division -- must refuse, not fuzzy-match."""
    name, how = resolve("FC Utrecht Youth", STORE, "Eerste Divisie")
    print(f"[{'PASS' if name is None else 'FAIL'}] 'FC Utrecht Youth' -> {name!r} ({how})")
    return name is None


def test_eindhoven_does_not_resolve_to_psv():
    """Different clubs, same city, different tier -- must refuse."""
    name, how = resolve("FC Eindhoven", STORE, "Eerste Divisie")
    print(f"[{'PASS' if name is None else 'FAIL'}] 'FC Eindhoven' -> {name!r} ({how})")
    return name is None


def test_league_not_in_store_refuses_cleanly():
    """A league the store has zero teams for must refuse immediately, not
    fall through to a global fuzzy search."""
    name, how = resolve("Al Khaleej", STORE, "Saudi Pro League")
    print(f"[{'PASS' if name is None else 'FAIL'}] 'Al Khaleej' (Saudi Pro League) -> {name!r} ({how})")
    return name is None


def test_legitimate_same_league_partial_still_works():
    """The fix must not break ordinary partial-name typing within the
    correct league -- only cross-league/cross-tier collisions."""
    name, how = resolve("Utrecht", STORE, "Eredivisie")
    ok = name == "Utrecht"
    print(f"[{'PASS' if ok else 'FAIL'}] 'Utrecht' (Eredivisie) -> {name!r} ({how})")
    return ok


def test_reserve_team_resolves_within_its_own_league():
    name, how = resolve("Jong AZ Alkmaar", STORE, "Eerste Divisie")
    ok = name == "Jong AZ Alkmaar"
    print(f"[{'PASS' if ok else 'FAIL'}] 'Jong AZ Alkmaar' (Eerste Divisie) -> {name!r} ({how})")
    return ok


def test_noise_stripped_partial_still_works_within_league():
    name, how = resolve("Bournemouth AFC", STORE, "Premier League")
    ok = name == "Bournemouth"
    print(f"[{'PASS' if ok else 'FAIL'}] 'Bournemouth AFC' (Premier League) -> {name!r} ({how})")
    return ok


def test_no_league_given_falls_back_to_old_global_behaviour():
    """When the caller doesn't supply a league at all (e.g. an older slate
    file), resolution should still work rather than hard-fail -- this is a
    deliberate compatibility fallback, not the safe path."""
    name, how = resolve("PSV Eindhoven", STORE, None)
    ok = name == "PSV Eindhoven"
    print(f"[{'PASS' if ok else 'FAIL'}] 'PSV Eindhoven' (no league given) -> {name!r} ({how})")
    return ok


def main() -> int:
    tests = [
        test_utrecht_youth_does_not_resolve_to_senior_utrecht,
        test_eindhoven_does_not_resolve_to_psv,
        test_league_not_in_store_refuses_cleanly,
        test_legitimate_same_league_partial_still_works,
        test_reserve_team_resolves_within_its_own_league,
        test_noise_stripped_partial_still_works_within_league,
        test_no_league_given_falls_back_to_old_global_behaviour,
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
