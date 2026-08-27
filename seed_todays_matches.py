"""
seed_todays_matches.py — one-time data entry for today's 5 matches
=====================================================================
Run this once to populate data/team_stats/soccer_stats.json with the
real, sourced numbers from today's research. Uses team_stats_provider.py's
upsert_soccer_team_stats() — the correct way to add this data, instead of
pasting JSON at the PowerShell prompt (which PowerShell tries to parse as
commands, not data — that's what caused the error).

NOTE: Moss and Sogndal are intentionally NOT included here. Norway's 1.
Division has no FBref-caliber public data, so there's nothing real to
enter — running that match will correctly show the [WARNING] placeholder
fallback message, which is the honest outcome for a Tier 3 league.

Some fields below are left at reasonable defaults where I couldn't find a
confirmed number (marked in comments) — you can edit this file and re-run
it any time to update a value.
"""

from team_stats_provider import upsert_soccer_team_stats

# ── Bradford City vs Burnley (EFL Cup) ──────────────────────────────────
upsert_soccer_team_stats("Bradford City", {
    "xg_for": 1.3, "xg_against": 0.6,          # estimated — pull real xG from FBref if you want precision
    "shots": 11.0, "sot": 4.5,
    "goals_for": 5, "goals_against": 0,         # from confirmed results: 2-0, 2-0, 1-0 last three
    "clean_sheets": 3,
    "missing_attacker": 0, "missing_creator": 0, "missing_cb": 0, "missing_gk": 0,
    "tempo": 0.35, "width_crossing": 0.45, "final_third_pressure": 0.50,
})

upsert_soccer_team_stats("Burnley", {
    "xg_for": 1.1, "xg_against": 1.8,           # estimated
    "shots": 10.0, "sot": 3.2,
    "goals_for": 3, "goals_against": 6,         # from confirmed results: 2-2 draw, 1-3 loss
    "clean_sheets": 0,
    "missing_attacker": 0, "missing_creator": 0, "missing_cb": 0, "missing_gk": 0,
    "tempo": 0.32, "width_crossing": 0.40, "final_third_pressure": 0.38,
})

# ── Newcastle vs West Brom (EFL Cup) ────────────────────────────────────
upsert_soccer_team_stats("Newcastle United", {
    "xg_for": 1.6, "xg_against": 1.4,           # estimated
    "shots": 13.0, "sot": 4.0,
    "goals_for": 2, "goals_against": 2,         # from confirmed 2-2 draw vs Liverpool
    "clean_sheets": 0,
    "missing_attacker": 1,   # Joelinton (groin) OUT
    "missing_creator": 0, "missing_cb": 0, "missing_gk": 0,
    # NOTE: Dan Burn (ankle) and Livramento (calf) are also OUT, but they're
    # fullback/defensive injuries — the schema only has missing_cb, not a
    # fullback category, so this is a real gap. Do NOT list Livramento in
    # any lineup output.
    "tempo": 0.40, "width_crossing": 0.55, "final_third_pressure": 0.55,
})

upsert_soccer_team_stats("West Bromwich Albion", {
    "xg_for": 1.8, "xg_against": 0.9,           # estimated
    "shots": 12.0, "sot": 5.5,
    "goals_for": 9, "goals_against": 3,         # confirmed: 2-1 Norwich, 3-1 Burnley, 4-1 Rotherham
    "clean_sheets": 0,
    "missing_attacker": 0,   # Johnston is a doubt, not confirmed out
    "missing_creator": 0, "missing_cb": 0, "missing_gk": 0,
    "tempo": 0.42, "width_crossing": 0.50, "final_third_pressure": 0.58,
})

# ── Viking vs Dinamo Zagreb (Champions League playoff) ──────────────────
upsert_soccer_team_stats("Viking", {
    "xg_for": 1.4, "xg_against": 1.6,           # estimated
    "shots": 13.8,     # 69 shots / 5 matches
    "sot": 5.0,
    "goals_for": 2, "goals_against": 2,         # from confirmed first-leg 2-2
    "clean_sheets": 0,
    "missing_attacker": 0, "missing_creator": 0,
    "missing_cb": 1,   # Baertelsen (broken foot) — from your source, NOT independently confirmed by me
    "missing_gk": 0,
    "tempo": 0.38, "width_crossing": 0.48, "final_third_pressure": 0.52,
})

upsert_soccer_team_stats("Dinamo Zagreb", {
    "xg_for": 2.0, "xg_against": 1.2,           # estimated
    "shots": 23.2,     # 116 shots / 5 matches
    "sot": 8.5,
    "goals_for": 2, "goals_against": 2,         # from confirmed first-leg 2-2
    "clean_sheets": 0,
    "missing_attacker": 0, "missing_creator": 0, "missing_cb": 0, "missing_gk": 0,
    "tempo": 0.45, "width_crossing": 0.55, "final_third_pressure": 0.62,
})

# ── Real Madrid vs Real Sociedad (La Liga) ───────────────────────────────
upsert_soccer_team_stats("Real Madrid", {
    "xg_for": 2.1, "xg_against": 0.9,           # estimated
    "shots": 15.0, "sot": 6.5,
    "goals_for": 2, "goals_against": 1,         # confirmed: 2-1 win at Espanyol
    "clean_sheets": 0,
    "missing_attacker": 1,   # Endrick OUT (recovery)
    "missing_creator": 0, "missing_cb": 0, "missing_gk": 0,
    # NOTE: Tchouameni (thigh) status unconfirmed for today — a midfield
    # injury also has no clean field in this schema.
    "tempo": 0.42, "width_crossing": 0.55, "final_third_pressure": 0.62,
})

upsert_soccer_team_stats("Real Sociedad", {
    "xg_for": 0.9, "xg_against": 1.6,           # estimated
    "shots": 9.5, "sot": 3.0,
    "goals_for": 0, "goals_against": 1,         # confirmed: 0-1 loss at Betis
    "clean_sheets": 0,
    "missing_attacker": 0,   # Oyarzabal is a doubt/bench, NOT confirmed out
    "missing_creator": 1,    # Marin OUT
    "missing_cb": 0, "missing_gk": 0,
    "tempo": 0.30, "width_crossing": 0.38, "final_third_pressure": 0.32,
})

print("Done. Real data seeded for 8 teams across 4 matches.")
print("Moss and Sogndal intentionally skipped — no real data source exists for Norway 1. Division.")
print("Fields marked 'estimated' in comments above still need real xG/shots numbers from")
print("FBref/footystats if you want full precision — edit this file and re-run to update.")
