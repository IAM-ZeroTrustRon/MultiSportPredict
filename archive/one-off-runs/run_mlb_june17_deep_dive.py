#!/usr/bin/env python
"""
MLB FULL SLATE DEEP DIVE ANALYSIS
June 17, 2026 — 15 Games
Format: Per-game NRFI, Props, Projections, Run-scoring, Moneyline edge
Pushed: Run in background, outputs saved to output/mlb/june17/
"""

import json, math
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path("output/mlb/june17")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def sigmoid(x): return 1 / (1 + math.exp(-x))


def clamp(x, low=0.0, high=1.0): return max(low, min(high, x))


def nrfi_compute(home_k_rate, away_k_rate, home_era, away_era, park_factor=1.0,
                 home_bullpen_era=4.00, away_bullpen_era=4.00,
                 weather_factor=0.0, first_hitter_xwoba=0.320):
    """NRFI with bullpen + weather + lineup context"""
    base_nrfi = 0.545

    starter_era_adj = ((4.50 - home_era) + (4.50 - away_era)) * 0.020
    k_adj = ((home_k_rate - 0.225) + (away_k_rate - 0.225)) * 0.60
    park_adj = (1.0 - park_factor) * 0.18
    bullpen_adj = ((4.00 - home_bullpen_era) + (4.00 - away_bullpen_era)) * 0.010

    lineup_factor = (first_hitter_xwoba - 0.320) * 0.30

    nrfi_prob = base_nrfi + starter_era_adj + k_adj + park_adj + bullpen_adj + lineup_factor + weather_factor
    nrfi_prob = max(0.30, min(0.78, nrfi_prob))

    edge = nrfi_prob - 0.50
    lean = "NRFI" if nrfi_prob > 0.57 else "YRFI" if nrfi_prob < 0.43 else "NRFI/YRFI Toss-up"
    conf = min(abs(edge) * 120, 75.0)
    tier = "STRONG BET" if abs(edge) >= 0.06 else "LEAN" if abs(edge) >= 0.03 else "PASS"

    return {
        "nrfi_probability": round(nrfi_prob, 4),
        "yrfi_probability": round(1.0 - nrfi_prob, 4),
        "edge_vs_50pct": round(edge, 4),
        "lean": lean,
        "confidence": round(conf, 1),
        "tier": tier,
    }


def project_hr_prob(hr_rate, barrel_rate, hard_hit_rate, pitcher_hr_per_9,
                    pitcher_handedness, park_factor, weather_hr_boost=0.0,
                    platoon_boost=0.0):
    base = hr_rate * park_factor
    base += (barrel_rate - 0.08) * 0.04
    base += (hard_hit_rate - 0.38) * 0.02
    base += (pitcher_hr_per_9 - 1.0) * 0.03
    base += weather_hr_boost + platoon_boost
    return clamp(base, 0.02, 0.45)


def estimate_runs_pa(team_rpg, pitcher_era, park_factor,
                     pitcher_recent_adj=0.0, bullpen_penalty=0.0):
    base = (team_rpg + pitcher_era) / 2
    base += pitcher_recent_adj + bullpen_penalty
    base *= park_factor
    return base


def run_full_game_analysis(game):
    g = game
    pf = g.get("park_factor", 1.0)

    # Base projections
    home_runs = estimate_runs_pa(
        g["home_rpg"], g["away_era"], pf,
        g.get("home_pitcher_recent_adj", 0.0),
        g.get("home_bullpen_penalty", 0.0)
    )
    away_runs = estimate_runs_pa(
        g["away_rpg"], g["home_era"], pf,
        g.get("away_pitcher_recent_adj", 0.0),
        g.get("away_bullpen_penalty", 0.0)
    )
    total_runs = home_runs + away_runs
    edge_runs = total_runs - g["market_total"]
    direction = "OVER" if edge_runs > 0 else "UNDER"
    conf_runs = min(abs(edge_runs) * 28, 75.0)

    # NRFI
    nrfi = nrfi_compute(
        home_k_rate=g.get("home_k_rate", 0.23),
        away_k_rate=g.get("away_k_rate", 0.23),
        home_era=g["home_era"],
        away_era=g["away_era"],
        park_factor=pf,
        home_bullpen_era=g.get("home_bullpen_era", 4.0),
        away_bullpen_era=g.get("away_bullpen_era", 4.0),
        weather_factor=g.get("weather_adj", 0.0),
        first_hitter_xwoba=g.get("first_hitter_xwoba", 0.320)
    )

    # Props
    props = []
    for p in g.get("player_props", []):
        hr_prob = project_hr_prob(
            hr_rate=p.get("hr_rate", 0.04),
            barrel_rate=p.get("barrel_rate", 0.09),
            hard_hit_rate=p.get("hard_hit_rate", 0.40),
            pitcher_hr_per_9=g.get("pitcher_hr_per_9",
                                   g["away_era"] if p["team"] == "home" else g["home_era"]),
            pitcher_handedness=g.get("home_pitcher_hand", "R") if p["team"] == "away" else g.get("away_pitcher_hand", "R"),
            park_factor=pf,
            weather_hr_boost=g.get("weather_adj", 0.0),
            platoon_boost=p.get("platoon_boost", 0.0)
        )
        lean = "Over" if hr_prob > 0.12 else "Under"
        props.append({
            "player": p["name"],
            "team": p["team"],
            "prop_type": p["prop"],
            "projected_probability": round(hr_prob, 4),
            "lean": lean,
            "line": p.get("line", "TBD"),
            "key_driver": p.get("driver", "")
        })

    # Moneyline implied vs model
    home_implied = 100 / (abs(g.get("ml_home", -110)) + 100) if g.get("ml_home", 0) < 0 else g.get("ml_home", 100) / (g.get("ml_home", 100) + 100)
    away_implied = 100 / (abs(g.get("ml_away", -110)) + 100) if g.get("ml_away", 0) < 0 else g.get("ml_away", 100) / (g.get("ml_away", 100) + 100)
    model_home_prob = clamp(sigmoid((home_runs - away_runs) / 2.2 + g.get("home_field_adv", 0.10)))

    result = {
        "game_info": {
            "matchup": g["matchup"],
            "home_team": g["home_team"],
            "away_team": g["away_team"],
            "venue": g["venue"],
            "date": "2026-06-17",
            "game_time": g["time"],
        },
        "pitching": {
            "home": {"name": g["home_pitcher"], "era": g["home_era"], "k_rate": g.get("home_k_rate", 0.23)},
            "away": {"name": g["away_pitcher"], "era": g["away_era"], "k_rate": g.get("away_k_rate", 0.23)}
        },
        "market_data": {
            "moneyline_home": g.get("ml_home"),
            "moneyline_away": g.get("ml_away"),
            "total": g["market_total"],
            "over_odds": g.get("over_odds", -110),
            "under_odds": g.get("under_odds", -110),
        },
        "projections": {
            "home_runs": round(home_runs, 2),
            "away_runs": round(away_runs, 2),
            "total_runs": round(total_runs, 2),
            "run_edge": round(edge_runs, 2),
            "run_direction": direction,
            "run_confidence": round(conf_runs, 1),
            "home_win_probability": round(model_home_prob, 3),
            "away_win_probability": round(1 - model_home_prob, 3),
        },
        "nrfi_analysis": nrfi,
        "player_props": props,
        "sharp_notes": g.get("sharp_notes", []),
    }
    return result


# ============================================================
# ALL 15 GAMES — JUNE 17, 2026
# ============================================================
games = [
    # 1) NYM @ CIN
    {
        "matchup": "NYM @ CIN", "time": "7:10 PM",
        "home_team": "Cincinnati Reds", "away_team": "New York Mets",
        "venue": "Great American Ball Park",
        "home_pitcher": "Brady Singer (RHP)", "away_pitcher": "Kodai Senga (RHP)",
        "home_era": 4.00, "away_era": 3.90,
        "home_rpg": 4.85, "away_rpg": 4.40,
        "home_k_rate": 0.21, "away_k_rate": 0.25,
        "home_bullpen_era": 4.30, "away_bullpen_era": 4.10,
        "park_factor": 1.12,
        "market_total": 9.0,
        "ml_home": -108, "ml_away": -112,
        "pitcher_hr_per_9": 1.1,
        "player_props": [],
        "sharp_notes": ["GABP hitter-friendly (1.12) — Over lean"],
        "home_pitcher_recent_adj": 0.10,
        "away_pitcher_recent_adj": 0.05,
        "weather_adj": 0.02,
    },
    # 2) KC @ WAS
    {
        "matchup": "KC @ WAS", "time": "6:45 PM",
        "home_team": "Washington Nationals", "away_team": "Kansas City Royals",
        "venue": "Nationals Park",
        "home_pitcher": "Foster Griffin (LHP)", "away_pitcher": "Michael Wacha (RHP)",
        "home_era": 4.35, "away_era": 3.85,
        "home_rpg": 4.10, "away_rpg": 4.30,
        "home_k_rate": 0.20, "away_k_rate": 0.24,
        "home_bullpen_era": 4.20, "away_bullpen_era": 3.95,
        "park_factor": 0.98,
        "market_total": 8.5,
        "ml_home": 105, "ml_away": -125,
        "pitcher_hr_per_9": 1.0,
        "player_props": [],
        "sharp_notes": ["Wacha veteran presence, Nats young pitchers"],
        "home_pitcher_recent_adj": -0.05,
        "away_pitcher_recent_adj": 0.0,
        "weather_adj": 0.0,
    },
    # 3) MIA @ PHI
    {
        "matchup": "MIA @ PHI", "time": "6:40 PM",
        "home_team": "Philadelphia Phillies", "away_team": "Miami Marlins",
        "venue": "Citizens Bank Park",
        "home_pitcher": "Jesus Luzardo (LHP)", "away_pitcher": "Tyler Phillips (RHP)",
        "home_era": 3.70, "away_era": 4.10,
        "home_rpg": 4.80, "away_rpg": 3.90,
        "home_k_rate": 0.26, "away_k_rate": 0.20,
        "home_bullpen_era": 3.90, "away_bullpen_era": 4.50,
        "park_factor": 1.08,
        "market_total": 8.5,
        "ml_home": -195, "ml_away": 165,
        "pitcher_hr_per_9": 0.9,
        "player_props": [],
        "sharp_notes": ["Luzardo LHB vulnerability (.281) — Lopez, Chisholm",
                         "Phillips walks (24 BB/48.1 IP)"],
        "home_pitcher_recent_adj": 0.0,
        "away_pitcher_recent_adj": -0.10,
        "weather_adj": 0.01,
    },
    # 4) SF @ ATL
    {
        "matchup": "SF @ ATL", "time": "7:15 PM",
        "home_team": "Atlanta Braves", "away_team": "San Francisco Giants",
        "venue": "Truist Park",
        "home_pitcher": "Grant Holmes (RHP)", "away_pitcher": "Adrian Houser (RHP)",
        "home_era": 3.95, "away_era": 3.85,
        "home_rpg": 5.12, "away_rpg": 4.45,
        "home_k_rate": 0.23, "away_k_rate": 0.20,
        "home_bullpen_era": 4.25, "away_bullpen_era": 6.20,
        "park_factor": 1.05,
        "market_total": 9.0,
        "ml_home": -155, "ml_away": 135,
        "pitcher_hr_per_9": 1.2,
        "player_props": [],
        "sharp_notes": ["Houser contact pitcher (.289 BAA, 6.4 K/9)",
                        "Giants BP 6.26 ERA/14d — fatigue",
                        "Bader CF OUT — defense weakened"],
        "home_pitcher_recent_adj": 0.30,
        "away_pitcher_recent_adj": 0.35,
        "weather_adj": 0.02,
        "home_bullpen_penalty": 0.15,
        "away_bullpen_penalty": 0.25,
        "first_hitter_xwoba": 0.335,
    },
    # 5) DET @ HOU
    {
        "matchup": "DET @ HOU", "time": "8:10 PM",
        "home_team": "Houston Astros", "away_team": "Detroit Tigers",
        "venue": "Minute Maid Park",
        "home_pitcher": "Hunter Brown (RHP)", "away_pitcher": "Framber Valdez (LHP)",
        "home_era": 3.75, "away_era": 3.85,
        "home_rpg": 4.80, "away_rpg": 4.00,
        "home_k_rate": 0.24, "away_k_rate": 0.22,
        "home_bullpen_era": 3.90, "away_bullpen_era": 4.00,
        "park_factor": 1.04,
        "market_total": 8.5,
        "ml_home": -145, "ml_away": 125,
        "pitcher_hr_per_9": 1.0,
        "player_props": [],
        "sharp_notes": ["Valdez elite groundballer — suppresses run scoring",
                        "HOU offense boosted by Minute Maid"],
        "home_pitcher_recent_adj": 0.0,
        "away_pitcher_recent_adj": -0.20,
        "weather_adj": 0.0,
    },
    # 6) SD @ STL
    {
        "matchup": "SD @ STL", "time": "7:45 PM",
        "home_team": "St. Louis Cardinals", "away_team": "San Diego Padres",
        "venue": "Busch Stadium",
        "home_pitcher": "Andre Pallante (RHP)", "away_pitcher": "Michael King (RHP)",
        "home_era": 4.05, "away_era": 3.85,
        "home_rpg": 4.20, "away_rpg": 4.40,
        "home_k_rate": 0.20, "away_k_rate": 0.24,
        "home_bullpen_era": 4.10, "away_bullpen_era": 3.85,
        "park_factor": 0.96,
        "market_total": 8.0,
        "ml_home": 115, "ml_away": -135,
        "pitcher_hr_per_9": 1.0,
        "player_props": [],
        "sharp_notes": ["Busch Stadium pitcher-friendly (0.96)"],
        "home_pitcher_recent_adj": 0.0,
        "away_pitcher_recent_adj": 0.0,
        "weather_adj": 0.0,
    },
    # 7) MIN @ TEX
    {
        "matchup": "MIN @ TEX", "time": "8:05 PM",
        "home_team": "Texas Rangers", "away_team": "Minnesota Twins",
        "venue": "Globe Life Field",
        "home_pitcher": "Kumar Rocker (RHP)", "away_pitcher": "Zebby Matthews (RHP)",
        "home_era": 3.90, "away_era": 3.95,
        "home_rpg": 4.60, "away_rpg": 4.50,
        "home_k_rate": 0.24, "away_k_rate": 0.22,
        "home_bullpen_era": 4.00, "away_bullpen_era": 4.10,
        "park_factor": 0.97,
        "market_total": 8.5,
        "ml_home": -120, "ml_away": 100,
        "pitcher_hr_per_9": 1.1,
        "player_props": [],
        "sharp_notes": ["Rocker still building up — limited workload"],
        "home_pitcher_recent_adj": 0.10,
        "away_pitcher_recent_adj": 0.0,
        "weather_adj": 0.0,
    },
    # 8) COL @ CHC
    {
        "matchup": "COL @ CHC", "time": "8:05 PM",
        "home_team": "Chicago Cubs", "away_team": "Colorado Rockies",
        "venue": "Wrigley Field",
        "home_pitcher": "Edward Cabrera (RHP)", "away_pitcher": "Ryan Feltner (RHP)",
        "home_era": 3.85, "away_era": 4.65,
        "home_rpg": 4.60, "away_rpg": 4.10,
        "home_k_rate": 0.25, "away_k_rate": 0.20,
        "home_bullpen_era": 3.95, "away_bullpen_era": 4.80,
        "park_factor": 1.00,
        "market_total": 8.5,
        "ml_home": -165, "ml_away": 145,
        "pitcher_hr_per_9": 1.0,
        "player_props": [],
        "sharp_notes": ["Feltner struggles, Rox pen weak"],
        "home_pitcher_recent_adj": 0.0,
        "away_pitcher_recent_adj": 0.15,
        "weather_adj": 0.0,
    },
    # 9) CLE @ MIL
    {
        "matchup": "CLE @ MIL", "time": "7:40 PM",
        "home_team": "Milwaukee Brewers", "away_team": "Cleveland Guardians",
        "venue": "American Family Field",
        "home_pitcher": "Robert Gasser (LHP)", "away_pitcher": "Slade Cecconi (RHP)",
        "home_era": 3.80, "away_era": 3.75,
        "home_rpg": 4.50, "away_rpg": 4.30,
        "home_k_rate": 0.25, "away_k_rate": 0.23,
        "home_bullpen_era": 3.90, "away_bullpen_era": 3.85,
        "park_factor": 1.01,
        "market_total": 8.0,
        "ml_home": -130, "ml_away": 110,
        "pitcher_hr_per_9": 0.95,
        "player_props": [],
        "sharp_notes": ["Gasser effective LHP, Cecconi solid"],
        "home_pitcher_recent_adj": 0.0,
        "away_pitcher_recent_adj": 0.0,
        "weather_adj": 0.0,
    },
    # 10) BAL @ SEA
    {
        "matchup": "BAL @ SEA", "time": "9:40 PM",
        "home_team": "Seattle Mariners", "away_team": "Baltimore Orioles",
        "venue": "T-Mobile Park",
        "home_pitcher": "George Kirby (RHP)", "away_pitcher": "Kyle Bradish (RHP)",
        "home_era": 3.60, "away_era": 3.85,
        "home_rpg": 4.10, "away_rpg": 4.60,
        "home_k_rate": 0.24, "away_k_rate": 0.25,
        "home_bullpen_era": 3.70, "away_bullpen_era": 3.90,
        "park_factor": 0.92,
        "market_total": 7.5,
        "ml_home": -138, "ml_away": 118,
        "pitcher_hr_per_9": 1.2,
        "player_props": [
            {"name": "Pete Alonso", "team": "away", "prop": "Total Bases", "line": 1.5,
             "hr_rate": 0.06, "barrel_rate": 0.14, "hard_hit_rate": 0.48,
             "driver": "1.914 career OPS vs Kirby — massive matchup edge"},
            {"name": "Pete Alonso", "team": "away", "prop": "HR", "line": "TBD",
             "hr_rate": 0.06, "barrel_rate": 0.14, "hard_hit_rate": 0.48,
             "driver": "4 HR allowed by Kirby in last 5 starts"},
            {"name": "Adley Rutschman", "team": "away", "prop": "Walks", "line": 0.5,
             "hr_rate": 0.04, "barrel_rate": 0.10, "hard_hit_rate": 0.38,
             "driver": "12/20 games Over walks (55% ROI), .375 OBP"},
            {"name": "Gunnar Henderson", "team": "away", "prop": "RBIs", "line": 0.5,
             "hr_rate": 0.05, "barrel_rate": 0.12, "hard_hit_rate": 0.42,
             "driver": "17/20 road games Under RBIs — strong fade"},
            {"name": "Colton Cowser", "team": "away", "prop": "HR", "line": "TBD",
             "hr_rate": 0.04, "barrel_rate": 0.10, "hard_hit_rate": 0.40,
             "driver": "3/6 road games with HR recently"},
        ],
        "sharp_notes": ["NRFI is sharp play — T-Mobile (0.92) suppresses 1st inn runs",
                        "Bradish shaky last start (5 ER in 4 IP)",
                        "Kirby allowed 4 HR in last 5 starts"],
        "home_pitcher_recent_adj": -0.10,
        "away_pitcher_recent_adj": 0.15,
        "weather_adj": 0.0,
        "home_bullpen_penalty": 0.0,
        "away_bullpen_penalty": 0.0,
        "first_hitter_xwoba": 0.328,
    },
    # 11) PIT @ OAK
    {
        "matchup": "PIT @ OAK", "time": "9:40 PM",
        "home_team": "Athletics", "away_team": "Pittsburgh Pirates",
        "venue": "Oakland Coliseum",
        "home_pitcher": "Jack Perkins (RHP)", "away_pitcher": "Mitch Keller (RHP)",
        "home_era": 4.25, "away_era": 4.10,
        "home_rpg": 3.90, "away_rpg": 4.20,
        "home_k_rate": 0.21, "away_k_rate": 0.23,
        "home_bullpen_era": 4.40, "away_bullpen_era": 4.10,
        "park_factor": 0.94,
        "market_total": 8.0,
        "ml_home": 110, "ml_away": -130,
        "pitcher_hr_per_9": 1.1,
        "player_props": [],
        "sharp_notes": ["Perkins unproven — Keller more reliable"],
        "home_pitcher_recent_adj": 0.10,
        "away_pitcher_recent_adj": 0.0,
        "weather_adj": 0.0,
    },
    # 12) LAA @ ARI
    {
        "matchup": "LAA @ ARI", "time": "9:40 PM",
        "home_team": "Arizona Diamondbacks", "away_team": "Los Angeles Angels",
        "venue": "Chase Field",
        "home_pitcher": "Merrill Kelly (RHP)", "away_pitcher": "Reid Detmers (LHP)",
        "home_era": 4.00, "away_era": 4.15,
        "home_rpg": 4.60, "away_rpg": 4.10,
        "home_k_rate": 0.22, "away_k_rate": 0.23,
        "home_bullpen_era": 4.05, "away_bullpen_era": 4.20,
        "park_factor": 1.06,
        "market_total": 9.0,
        "ml_home": -125, "ml_away": 105,
        "pitcher_hr_per_9": 1.05,
        "player_props": [],
        "sharp_notes": ["Chase Field hitter-friendly (1.06)"],
        "home_pitcher_recent_adj": 0.05,
        "away_pitcher_recent_adj": 0.05,
        "weather_adj": 0.02,
    },
    # 13) TOR @ BOS
    {
        "matchup": "TOR @ BOS", "time": "6:45 PM",
        "home_team": "Boston Red Sox", "away_team": "Toronto Blue Jays",
        "venue": "Fenway Park",
        "home_pitcher": "Payton Tolle (LHP)", "away_pitcher": "Dylan Cease (RHP)",
        "home_era": 4.05, "away_era": 3.95,
        "home_rpg": 4.70, "away_rpg": 4.50,
        "home_k_rate": 0.22, "away_k_rate": 0.27,
        "home_bullpen_era": 4.10, "away_bullpen_era": 3.90,
        "park_factor": 1.05,
        "market_total": 8.5,
        "ml_home": 100, "ml_away": -120,
        "pitcher_hr_per_9": 1.0,
        "player_props": [],
        "sharp_notes": ["Cease elite K-rate (0.27) vs Red Sox"],
        "home_pitcher_recent_adj": 0.0,
        "away_pitcher_recent_adj": 0.10,
        "weather_adj": 0.01,
    },
    # 14) CWS @ NYY
    {
        "matchup": "CWS @ NYY", "time": "7:05 PM",
        "home_team": "New York Yankees", "away_team": "Chicago White Sox",
        "venue": "Yankee Stadium",
        "home_pitcher": "Gerrit Cole (RHP)", "away_pitcher": "Davis Martin (RHP)",
        "home_era": 3.55, "away_era": 4.45,
        "home_rpg": 4.90, "away_rpg": 3.80,
        "home_k_rate": 0.28, "away_k_rate": 0.20,
        "home_bullpen_era": 3.80, "away_bullpen_era": 4.70,
        "park_factor": 1.02,
        "market_total": 8.0,
        "ml_home": -225, "ml_away": 185,
        "pitcher_hr_per_9": 0.8,
        "player_props": [],
        "sharp_notes": ["Cole ace, but White Sox poor offense",
                        "Yankees heavy favorite — run line value on CWS +1.5?"],
        "home_pitcher_recent_adj": 0.0,
        "away_pitcher_recent_adj": -0.10,
        "weather_adj": 0.0,
    },
    # 15) TB @ LAD
    {
        "matchup": "TB @ LAD", "time": "10:10 PM",
        "home_team": "Los Angeles Dodgers", "away_team": "Tampa Bay Rays",
        "venue": "Dodger Stadium",
        "home_pitcher": "Justin Wrobleski (LHP)", "away_pitcher": "Drew Rasmussen (RHP)",
        "home_era": 3.65, "away_era": 3.60,
        "home_rpg": 5.00, "away_rpg": 4.20,
        "home_k_rate": 0.23, "away_k_rate": 0.26,
        "home_bullpen_era": 3.75, "away_bullpen_era": 3.65,
        "park_factor": 1.03,
        "market_total": 8.5,
        "ml_home": -155, "ml_away": 135,
        "pitcher_hr_per_9": 0.9,
        "player_props": [],
        "sharp_notes": ["Rasmussen elite but TOR runs deep lineup",
                        "Wrobleski LHP — Dodgers defer to pen early"],
        "home_pitcher_recent_adj": 0.10,
        "away_pitcher_recent_adj": -0.05,
        "weather_adj": 0.0,
    },
]

# Run all analyses
all_results = []
for g in games:
    result = run_full_game_analysis(g)
    all_results.append(result)

    # Save per-game JSON
    fname = g["matchup"].replace(" ", "_").replace("@", "at") + ".json"
    out_path = OUTPUT_DIR / fname
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

# Master summary
all_results.sort(key=lambda x: abs(x["projections"]["run_edge"]), reverse=True)

print("=" * 100)
print(f"MLB JUNE 17, 2026 — ALL 15 GAMES DEEP DIVE")
print(f"Generated: {datetime.now().strftime('%I:%M:%S %p ET')}")
print("=" * 100)
print()

for i, r in enumerate(all_results, 1):
    p = r["projections"]
    nrfi = r["nrfi_analysis"]
    nrf_tier = "[NRFI]" if nrfi["tier"] != "PASS" else "[PASS]"

    line = f"#{i:2d}  {r['game_info']['matchup']:>12s}"
    line += f"  Time: {r['game_info']['game_time']:>7s}"
    line += f"  Total: {p['total_runs']:5.2f}"
    line += f"  Mkt: {r['market_data']['total']:4.1f}"
    line += f"  Edge: {p['run_edge']:+.2f}r"
    line += f"  {p['run_direction']:5s} {r['market_data']['total']}"
    line += f"  Conf: {p['run_confidence']:4.1f}%"
    print(line)

    line2 = f"      NRFI: {nrfi['nrfi_probability']:4.1%} ({nrfi['lean']}) Conf: {nrfi['confidence']:5.1f}% {nrf_tier}"
    print(line2)

    if r["player_props"]:
        print(f"      PROPS:")
        for prop in r["player_props"][:3]:
            print(f"        - {prop['player']} {prop['prop_type']} {prop['lean']} (Line: {prop['line']}): {prop['key_driver']}")

    if r["sharp_notes"]:
        print(f"      NOTES: {'; '.join(r['sharp_notes'][:2])}")
    print()

print()
print("=" * 100)
print("TOP 5 STRONGEST BETS ACROSS ALL GAMES")
print("=" * 100)
print()

top5 = all_results[:5]
for i, r in enumerate(top5, 1):
    p = r["projections"]
    nrfi = r["nrfi_analysis"]
    print(f"  #{i}: {r['game_info']['matchup']} ({r['game_info']['game_time']})")
    print(f"       Runs: {p['run_direction']} {r['market_data']['total']} (Edge: {p['run_edge']:+.2f}r, Conf: {p['run_confidence']:.0f}%)")
    if nrfi["tier"] != "PASS":
        print(f"       NRFI: {nrfi['lean']} (Conf: {nrfi['confidence']:.0f}%, Edge: {nrfi['edge_vs_50pct']:+.2f})")
    if r["player_props"]:
        best_prop = max(r["player_props"], key=lambda x: x.get("projected_probability", 0))
        print(f"       Top Prop: {best_prop['player']} {best_prop['prop_type']} {best_prop['lean']}")
    print()

# Save master file
master_path = OUTPUT_DIR / "all_15_games_summary.json"
with open(master_path, "w") as f:
    json.dump({"date": "2026-06-17", "games": all_results}, f, indent=2)

print(f"All per-game JSONs saved to: {OUTPUT_DIR}")
print(f"Master summary: {master_path}")
print()
print("=" * 100)