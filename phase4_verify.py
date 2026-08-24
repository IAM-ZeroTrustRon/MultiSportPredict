"""Phase 4 verification: with/without real team stats must produce different output."""
import json
import sys

from predict_match import run_soccer_game

GAMES = [
    ("Ajax", "PSV", "Eredivisie"),
    ("Feyenoord", "AZ", "Eredivisie"),
]

def pick(r):
    return json.dumps({k: r.get(k) for k in ["game", "predictions"]}, sort_keys=True)

def main():
    res_no_1 = run_soccer_game(GAMES[0][0], GAMES[0][1], GAMES[0][2])
    res_no_2 = run_soccer_game(GAMES[1][0], GAMES[1][1], GAMES[1][2])

    hs1 = {"xg_for": 2.2, "xg_against": 0.9, "shots": 16.0, "sot": 6.2,
           "goals_for": 2.4, "goals_against": 0.8, "clean_sheets": 6, "tempo": 0.5}
    as1 = {"xg_for": 1.6, "xg_against": 1.2, "shots": 12.0, "sot": 4.2,
           "goals_for": 1.7, "goals_against": 1.1, "clean_sheets": 3, "tempo": 0.3}
    res_w_1 = run_soccer_game(GAMES[0][0], GAMES[0][1], GAMES[0][2], home_stats=hs1, away_stats=as1)

    hs2 = {"xg_for": 1.5, "xg_against": 1.3, "shots": 11.0, "sot": 3.8,
           "goals_for": 1.4, "goals_against": 1.2, "clean_sheets": 2, "tempo": 0.2}
    as2 = {"xg_for": 1.9, "xg_against": 1.0, "shots": 14.0, "sot": 5.1,
           "goals_for": 2.0, "goals_against": 0.9, "clean_sheets": 5, "tempo": 0.4}
    res_w_2 = run_soccer_game(GAMES[1][0], GAMES[1][1], GAMES[1][2], home_stats=hs2, away_stats=as2)

    out = {
        "no_stats_identical": pick(res_no_1) == pick(res_no_2),
        "with_stats_identical": pick(res_w_1) == pick(res_w_2),
        "no_vs_with_differs": (pick(res_no_1) != pick(res_w_1)) and (pick(res_no_2) != pick(res_w_2)),
        "no_stats_sources": [res_no_1.get("_stats_source"), res_no_2.get("_stats_source")],
        "with_stats_sources": [res_w_1.get("_stats_source"), res_w_2.get("_stats_source")],
        "no_game1_total": res_no_1.get("game", {}).get("projected_total_goals"),
        "no_game2_total": res_no_2.get("game", {}).get("projected_total_goals"),
        "with_game1_total": res_w_1.get("game", {}).get("projected_total_goals"),
        "with_game2_total": res_w_2.get("game", {}).get("projected_total_goals"),
        "with_game1_home_xg_used": res_w_1.get("team_metrics", {}).get("home", {}).get("xg_for"),
        "with_game2_home_xg_used": res_w_2.get("team_metrics", {}).get("home", {}).get("xg_for"),
    }

    with open("phase4_test_results.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print("DONE OK")

if __name__ == "__main__":
    main()