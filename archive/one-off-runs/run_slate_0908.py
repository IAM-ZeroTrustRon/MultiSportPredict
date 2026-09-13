#!/usr/bin/env python3
"""Run the Sept 8 three-game slate through the model.

Runs on the Linux VM, so it deliberately does NOT touch multisport_history.db
(sqlite writes over the mount commit-fail and leave a hot journal) and does not
push to Discord (no network here). Ron re-runs it on Windows to store and push.

Starter numbers come from data/mlb_probables.json where the Sept 7 pull already
had them, and from SLATE below where it did not.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from predict_match import run_baseball_game
from team_stats_provider import get_baseball_team_stats

PROBABLES = json.loads((ROOT / "data" / "mlb_probables.json").read_text())

# away, home, market total, home ML, away ML, away pitch cap, home pitch cap
SLATE = [
    {
        "away": "Tampa Bay Rays", "home": "Atlanta Braves",
        "total": None, "home_ml": None, "away_ml": None,
        "away_cap": None, "home_cap": None,
        # AJ Smith-Shawver was not in the Sept 7 probables pull.
        "fill": {"home": {"name": "AJ Smith-Shawver", "era": None, "k9": None}},
    },
    {
        "away": "Pittsburgh Pirates", "home": "Chicago White Sox",
        "total": None, "home_ml": None, "away_ml": None,
        "away_cap": None, "home_cap": None,
        "fill": {},
    },
    {
        "away": "Arizona Diamondbacks", "home": "Kansas City Royals",
        "total": None, "home_ml": None, "away_ml": None,
        "away_cap": 60, "home_cap": None,
        # Burnes has no meaningful 2026 line -- first start since TJ surgery.
        "fill": {"away": {"name": "Corbin Burnes", "era": None, "k9": None}},
    },
]

# Filled in from the live lookup before this runs.
OVERRIDES = json.loads(Path(sys.argv[1]).read_text()) if len(sys.argv) > 1 else {}


def probable(away, home):
    for g in PROBABLES["games"]:
        if g["game_date"] == "2026-09-08" and g["away_team"] == away and g["home_team"] == home:
            return g
    return {}


def sp(side, game_row, fill, key):
    """ERA / K9 for one starter: probables file first, then the manual fill."""
    src = probable(game_row["away"], game_row["home"])
    era = src.get(f"{side}_pitcher_era")
    k9 = src.get(f"{side}_pitcher_k9")
    name = src.get(f"{side}_pitcher")
    manual = OVERRIDES.get(key, {}).get(side) or fill.get(side) or {}
    if manual.get("era") is not None:
        era, name = manual["era"], manual.get("name", name)
    if manual.get("k9") is not None:
        k9 = manual["k9"]
    if manual.get("name") and not name:
        name = manual["name"]
    return name, era, k9


BATTERS_FACED = 9.0 * 4.25   # batters faced per nine innings

results = []
for row in SLATE:
    key = f"{row['away']}@{row['home']}"
    live = OVERRIDES.get(key, {})
    total = live.get("total", row["total"])
    home_ml = live.get("home_ml", row["home_ml"])
    away_ml = live.get("away_ml", row["away_ml"])
    away_cap = live.get("away_cap", row["away_cap"])
    home_cap = live.get("home_cap", row["home_cap"])

    h_name, h_era, h_k9 = sp("home", row, row["fill"], key)
    a_name, a_era, a_k9 = sp("away", row, row["fill"], key)

    print("\n" + "=" * 78)
    print(f"  {row['away']}  @  {row['home']}")
    print("=" * 78)
    print(f"  Away SP : {a_name or 'UNKNOWN'}  ERA {a_era}  K/9 {a_k9}"
          + (f"   [PITCH CAP {away_cap}]" if away_cap else ""))
    print(f"  Home SP : {h_name or 'UNKNOWN'}  ERA {h_era}  K/9 {h_k9}"
          + (f"   [PITCH CAP {home_cap}]" if home_cap else ""))
    print(f"  Market  : total {total}  |  ML {row['away']} {away_ml} / {row['home']} {home_ml}")

    def overrides(era, k9, cap):
        if era is None and k9 is None and cap is None:
            return None
        out = {}
        if era is not None:
            out["era"] = float(era)
        if k9 is not None:
            out["k_rate"] = max(0.0, min(0.60, float(k9) / BATTERS_FACED))
            out["k9"] = float(k9)
        if cap is not None:
            out["pitch_limit"] = float(cap)
        return out

    team_overrides = {}
    for side, team in (("home", row["home"]), ("away", row["away"])):
        stats = get_baseball_team_stats(team, "MLB")
        if not stats:
            print(f"  [ERROR] no team stats for {team}")
            continue
        for field in ("runs", "runs_allowed", "era", "whip", "obp", "slg",
                      "k9", "avg", "ops", "bb9"):
            if stats.get(field) is not None:
                team_overrides[f"{side}_{field}"] = float(stats[field])

    res = run_baseball_game(
        row["home"], row["away"], league="MLB",
        markets=["nrfi", "strikeouts", "home_runs", "f5"],
        market_total=float(total) if total is not None else 8.5,
        home_sp_overrides=overrides(h_era, h_k9, home_cap),
        away_sp_overrides=overrides(a_era, a_k9, away_cap),
        team_overrides=team_overrides or None,
        home_ml=home_ml, away_ml=away_ml,
    )
    res["_meta"] = {"away_sp": a_name, "home_sp": h_name, "market_total": total,
                    "home_ml": home_ml, "away_ml": away_ml}
    results.append((key, res))

print("\n\n" + "#" * 78)
print("#  SLATE SUMMARY")
print("#" * 78)
for key, r in results:
    gp = r["game_projection"]
    ml = r.get("moneyline_and_side", {})
    s = r.get("summary", {})
    p = r.get("props", {})
    w = r.get("starter_workload", {})
    print(f"\n{key}")
    print(f"   proj total {gp['total']}   (home {gp['home_runs']} / away {gp['away_runs']})"
          f"   market {r['_meta']['market_total']}")
    print(f"   total rec  {s.get('recommendation')}  conf {s.get('confidence')}"
          f"  edge {s.get('edge_value')}")
    print(f"   ML         home {ml.get('home_win_probability')} / away {ml.get('away_win_probability')}"
          f"   rec {ml.get('recommendation')}")
    print(f"   NRFI       {p.get('nrfi', {}).get('probability')} ({p.get('nrfi', {}).get('lean')})")
    print(f"   F5 total   {p.get('f5', {}).get('total')}  ({p.get('f5', {}).get('recommendation_over')})"
          f"   F5 ML home {p.get('f5', {}).get('home_fair_odds')}")
    print(f"   K proj     home {p.get('strikeouts', {}).get('home_projection')}"
          f" / away {p.get('strikeouts', {}).get('away_projection')}"
          f"  tier {p.get('strikeouts', {}).get('data_tier')}")
    print(f"   SP innings home {w.get('home_starter_innings')} / away {w.get('away_starter_innings')}"
          f"   caps h={w.get('home_pitch_limit')} a={w.get('away_pitch_limit')}")

Path(sys.argv[2] if len(sys.argv) > 2 else "slate_out.json").write_text(
    json.dumps({k: v for k, v in results}, indent=1, default=str))
print("\n[written] slate_out.json")
