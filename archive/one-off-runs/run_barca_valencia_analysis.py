#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Barcelona vs Valencia Basket - ACB Liga Endesa Analysis
=======================================================
Using actual 2025-2026 season team stats.
"""

import json
import math
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# 2025-2026 SEASON STATS (provided)
# ---------------------------------------------------------------------------

# Barcelona (home)
BARCA = {
    "team": "FC Barcelona",
    "gp": 41,
    "ppg": 90.71,
    "fgm": 32.95, "fga": 63.17, "fg_pct": 0.522,
    "tpm": 10.05, "tpa": 25.20, "tp_pct": 0.399,
    "ftm": 14.76, "fta": 19.63, "ft_pct": 0.752,
    "orb": 9.10,  "drb": 24.54, "trb": 33.66,
    "apg": 16.15, "spg": 7.24,  "bpg": 2.66,
    "tov": 11.66, "pf":  20.85,
}

BARCA_OPP = {
    "ppg": 82.76,
    "fgm": 29.24, "fga": 61.95, "fg_pct": 0.472,
    "tpm": 8.78,  "tpa": 25.61, "tp_pct": 0.343,
    "ftm": 15.49, "fta": 19.85, "ft_pct": 0.780,
    "orb": 8.66,  "drb": 21.56, "trb": 30.24,
    "apg": 16.05, "spg": 6.24,  "bpg": 2.34,
    "tov": 12.39,
}

# Valencia Basket (away)
VALENCIA = {
    "team": "Valencia Basket",
    "gp": 40,
    "ppg": 94.90,
    "fgm": 33.98, "fga": 71.35, "fg_pct": 0.476,
    "tpm": 11.60, "tpa": 32.65, "tp_pct": 0.355,
    "ftm": 15.35, "fta": 21.30, "ft_pct": 0.721,
    "orb": 13.97, "drb": 26.18, "trb": 40.17,
    "apg": 20.60, "spg": 8.05,  "bpg": 3.60,
    "tov": 11.93, "pf":  19.35,
}

VALENCIA_OPP = {
    "ppg": 84.03,
    "fgm": 30.10, "fga": 67.97, "fg_pct": 0.443,
    "tpm": 10.15, "tpa": 30.50, "tp_pct": 0.333,
    "ftm": 13.68, "fta": 17.93, "ft_pct": 0.763,
    "orb": 11.38, "drb": 23.57, "trb": 34.98,
    "apg": 16.60, "spg": 6.45,  "bpg": 3.00,
    "tov": 13.32,
}

# Head-to-Head (since 2000-01)
H2H_BARCA_WINS   = 27
H2H_VALENCIA_WINS = 55
H2H_TOTAL = H2H_BARCA_WINS + H2H_VALENCIA_WINS

# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def possessions(fga, orb, tov, fta):
    """Estimate team possessions per game using standard formula."""
    return fga - orb + tov + 0.44 * fta

def offensive_rating(ppg, poss):
    """Points per 100 possessions."""
    return (ppg / poss) * 100

def efg_pct(fgm, tpm, fga):
    """Effective Field Goal %."""
    return (fgm + 0.5 * tpm) / fga

def tov_rate(tov, poss):
    """Turnover rate per 100 possessions."""
    return tov / poss * 100

def ft_rate(fta, fga):
    """Free throw rate = FTA / FGA."""
    return fta / fga

def off_reb_pct(orb, opp_drb):
    """Offensive rebound %."""
    total = orb + opp_drb
    return orb / total if total > 0 else 0

def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))

def sigmoid(x):
    x = max(-500.0, min(500.0, x))
    return 1.0 / (1.0 + math.exp(-x))

# ---------------------------------------------------------------------------
# PACE & RATING CALCULATIONS
# ---------------------------------------------------------------------------

def compute_metrics(team, opp):
    poss = possessions(team["fga"], team["orb"], team["tov"], team["fta"])
    opp_poss = possessions(opp["fga"], opp["orb"], opp["tov"], opp["fta"])
    ortg = offensive_rating(team["ppg"], poss)
    drtg = offensive_rating(opp["ppg"], opp_poss)
    net  = ortg - drtg
    return {
        "poss":   round(poss, 2),
        "ortg":   round(ortg, 2),
        "drtg":   round(drtg, 2),
        "net_rtg": round(net, 2),
        "efg_off": round(efg_pct(team["fgm"], team["tpm"], team["fga"]), 4),
        "efg_def": round(efg_pct(opp["fgm"],  opp["tpm"],  opp["fga"]),  4),
        "tov_rate_off": round(tov_rate(team["tov"], poss), 2),
        "tov_rate_def": round(tov_rate(opp["tov"],  opp_poss), 2),
        "ft_rate_off":  round(ft_rate(team["fta"], team["fga"]), 4),
        "ft_rate_def":  round(ft_rate(opp["fta"],  opp["fga"]),  4),
        "orb_pct": round(off_reb_pct(team["orb"], opp["drb"]), 4),
    }

# ---------------------------------------------------------------------------
# SCORE PROJECTION
# ---------------------------------------------------------------------------

def project_score(home_metrics, away_metrics, home_team, away_team,
                  h2h_home_wins, h2h_away_wins,
                  home_court_advantage=3.5):
    """
    Project final score using Four Factors model.
    """
    # Game pace = avg of both teams
    game_pace = (home_metrics["poss"] + away_metrics["poss"]) / 2

    # Base score projection (adjusted rating / 100 * pace)
    proj_home = ((home_metrics["ortg"] + away_metrics["drtg"]) / 2) * game_pace / 100
    proj_away = ((away_metrics["ortg"] + home_metrics["drtg"]) / 2) * game_pace / 100

    # Home court advantage
    proj_home += home_court_advantage / 2
    proj_away -= home_court_advantage / 2

    # Head-to-Head adjustment (away team historical dominance)
    h2h_total = h2h_home_wins + h2h_away_wins
    h2h_away_edge_pct = (h2h_away_wins / h2h_total) - 0.50  # positive = away historically better
    h2h_adj = h2h_away_edge_pct * 4.0  # scale: 17% edge = ~0.68 pt away boost
    proj_away  += h2h_adj
    proj_home  -= h2h_adj

    spread = proj_home - proj_away
    total  = proj_home + proj_away

    return round(proj_home, 1), round(proj_away, 1), round(spread, 2), round(total, 1)

# ---------------------------------------------------------------------------
# WIN PROBABILITY
# ---------------------------------------------------------------------------

def win_probability(spread_model, spread_sigma=10.5):
    """Convert model spread to win probability using normal distribution approx."""
    z = spread_model / spread_sigma
    prob = sigmoid(z * 1.7)  # logistic approximation of normal CDF
    return round(prob, 4)

# ---------------------------------------------------------------------------
# FOUR FACTORS COMPOSITE RATING
# ---------------------------------------------------------------------------

def four_factors_edge(home_m, away_m):
    """
    Composite edge from Dean Oliver's Four Factors.
    Weights: eFG% 40%, TOV% 25%, ORB% 20%, FTR 15%
    Returns home advantage in raw points (positive = home better)
    """
    # eFG edge: home offense vs away defense
    efg_edge = (home_m["efg_off"] - away_m["efg_def"]) * 40  # scale to pts
    # TOV edge: fewer turnovers = better (lower is better, so negate)
    tov_edge = (away_m["tov_rate_off"] - home_m["tov_rate_off"]) * 0.5
    # ORB edge
    orb_edge = (home_m["orb_pct"] - away_m["orb_pct"]) * 20
    # FTR edge
    ftr_edge = (home_m["ft_rate_off"] - away_m["ft_rate_off"]) * 5
    total = efg_edge + tov_edge + orb_edge + ftr_edge
    return {
        "efg_edge": round(efg_edge, 3),
        "tov_edge": round(tov_edge, 3),
        "orb_edge": round(orb_edge, 3),
        "ftr_edge": round(ftr_edge, 3),
        "total":    round(total, 3),
    }

# ---------------------------------------------------------------------------
# Q1 / 1H / FULL GAME SPLIT PROJECTIONS
# ---------------------------------------------------------------------------

def project_splits(proj_home, proj_away, home_pace, away_pace):
    """
    Break down Full Game projection into Q1, 1H, and Full Game lines
    with spread and total recommendations.

    Methodology:
      - Q1 total  : ~24.5% of FG total (slightly front-loaded in ACB)
      - 1H total  : ~51.5% of FG total (first halves run slightly lower)
      - Q1 spread : ~45% of FG spread (tighter in early minutes)
      - 1H spread : ~52% of FG spread
    Games with high pace inflate early-quarter totals by ~0.5%.
    """
    fg_total  = proj_home + proj_away
    fg_spread = proj_home - proj_away  # positive = home favored

    # Pace factor: if average pace > 76 possessions, bump early-game totals
    avg_pace = (home_pace + away_pace) / 2
    pace_bonus = max(0.0, (avg_pace - 76.0) * 0.003)  # tiny adjustment

    # ---- Q1 ----
    q1_total_pct  = 0.245 + pace_bonus
    q1_spread_pct = 0.45
    q1_home  = round(proj_home * q1_total_pct * 2 / 2, 1)   # proportional
    q1_away  = round(proj_away * q1_total_pct * 2 / 2, 1)
    q1_total = round(fg_total * q1_total_pct, 1)
    q1_spread = round(fg_spread * q1_spread_pct, 2)

    # ---- 1H ----
    h1_total_pct  = 0.515 + pace_bonus * 2
    h1_spread_pct = 0.52
    h1_home  = round(proj_home * h1_total_pct, 1)
    h1_away  = round(proj_away * h1_total_pct, 1)
    h1_total = round(fg_total * h1_total_pct, 1)
    h1_spread = round(fg_spread * h1_spread_pct, 2)

    return {
        "q1": {
            "home": q1_home, "away": q1_away,
            "total": q1_total, "spread": q1_spread,
        },
        "h1": {
            "home": h1_home, "away": h1_away,
            "total": h1_total, "spread": h1_spread,
        },
        "fg": {
            "home": round(proj_home, 1), "away": round(proj_away, 1),
            "total": round(fg_total, 1), "spread": round(fg_spread, 2),
        },
    }


def market_rec(model_val, market_val, label="total", threshold=1.0):
    """
    Compare model value to market line and return recommendation.
    For totals: OVER/UNDER. For spreads: home/away +/-.
    """
    if market_val is None:
        return "MODEL ONLY (no market line)"
    edge = model_val - market_val
    if label == "total":
        if edge > threshold:
            return f"OVER  (model {model_val:.1f} > mkt {market_val:.1f}, edge +{edge:.1f})"
        elif edge < -threshold:
            return f"UNDER (model {model_val:.1f} < mkt {market_val:.1f}, edge {edge:.1f})"
        else:
            return f"PASS  (edge {edge:+.1f}, within {threshold:.1f} pt threshold)"
    else:
        if edge > threshold:
            return f"HOME  (model {model_val:+.2f} vs mkt {market_val:+.2f}, edge +{edge:.2f})"
        elif edge < -threshold:
            return f"AWAY  (model {model_val:+.2f} vs mkt {market_val:+.2f}, edge {edge:.2f})"
        else:
            return f"PASS  (edge {edge:+.2f}, within {threshold:.2f} pt threshold)"


def print_split_table(splits, home_name, away_name,
                      mkt_q1_total=None, mkt_h1_total=None, mkt_fg_total=None,
                      mkt_q1_spread=None, mkt_h1_spread=None, mkt_fg_spread=None):
    """Print the Q1 / 1H / FG split table with market recommendations."""
    abbr_h = home_name.split()[0]
    abbr_a = away_name.split()[0]

    print(f"\n[ Q1 / 1H / FULL GAME SPLIT PROJECTIONS ]")
    print(f"{'Period':<6} {'Proj Score':<22} {'Total':>7} {'Spread':>8}  {'Total Rec':<38} {'Spread Rec'}")
    print("-" * 110)

    periods = [
        ("Q1",  splits["q1"], mkt_q1_total, mkt_q1_spread),
        ("1H",  splits["h1"], mkt_h1_total, mkt_h1_spread),
        ("FG",  splits["fg"], mkt_fg_total, mkt_fg_spread),
    ]
    for period, s, mkt_tot, mkt_spd in periods:
        score_str = f"{abbr_h} {s['home']:.1f} - {abbr_a} {s['away']:.1f}"
        tot_rec   = market_rec(s["total"],  mkt_tot, "total",  threshold=0.8)
        spd_rec   = market_rec(s["spread"], mkt_spd, "spread", threshold=0.8)
        print(f"  {period:<4} {score_str:<22} {s['total']:>7.1f} {s['spread']:>+8.2f}  {tot_rec:<38} {spd_rec}")

    print()


# ---------------------------------------------------------------------------
# MAIN ANALYSIS
# ---------------------------------------------------------------------------

def run_analysis():
    home_name = BARCA["team"]
    away_name = VALENCIA["team"]

    print(f"\n{'='*65}")
    print(f"  BASKETBALL ANALYSIS: {home_name} vs {away_name}")
    print(f"  League: ACB Liga Endesa  |  Season: 2025-2026")
    print(f"{'='*65}\n")

    # --- Compute advanced metrics ---
    barca_m   = compute_metrics(BARCA,   BARCA_OPP)
    valencia_m = compute_metrics(VALENCIA, VALENCIA_OPP)

    print("[ ADVANCED METRICS ]")
    print(f"{'Metric':<28} {'Barcelona':>12} {'Valencia':>12}")
    print("-" * 54)
    rows = [
        ("Possessions / Game",  barca_m["poss"],         valencia_m["poss"]),
        ("Off. Rating (ORtg)",   barca_m["ortg"],         valencia_m["ortg"]),
        ("Def. Rating (DRtg)",   barca_m["drtg"],         valencia_m["drtg"]),
        ("Net Rating",           barca_m["net_rtg"],      valencia_m["net_rtg"]),
        ("eFG% Offense",         f"{barca_m['efg_off']:.1%}",   f"{valencia_m['efg_off']:.1%}"),
        ("eFG% Defense Allowed", f"{barca_m['efg_def']:.1%}",   f"{valencia_m['efg_def']:.1%}"),
        ("TOV Rate Off.",        f"{barca_m['tov_rate_off']:.1f}%", f"{valencia_m['tov_rate_off']:.1f}%"),
        ("TOV Rate Def.",        f"{barca_m['tov_rate_def']:.1f}%", f"{valencia_m['tov_rate_def']:.1f}%"),
        ("Off. Reb %",           f"{barca_m['orb_pct']:.1%}",  f"{valencia_m['orb_pct']:.1%}"),
        ("FT Rate (FTA/FGA)",    f"{barca_m['ft_rate_off']:.3f}", f"{valencia_m['ft_rate_off']:.3f}"),
        ("FT%",                  f"{BARCA['ft_pct']:.1%}",        f"{VALENCIA['ft_pct']:.1%}"),
        ("3P%",                  f"{BARCA['tp_pct']:.1%}",         f"{VALENCIA['tp_pct']:.1%}"),
        ("PPG",                  BARCA["ppg"],            VALENCIA["ppg"]),
        ("Opp PPG",              BARCA_OPP["ppg"],        VALENCIA_OPP["ppg"]),
    ]
    for label, h_val, a_val in rows:
        print(f"  {label:<26} {str(h_val):>12} {str(a_val):>12}")

    # --- Four Factors ---
    print(f"\n[ FOUR FACTORS EDGE (Home vs Away) ]")
    ff = four_factors_edge(barca_m, valencia_m)
    ff_labels = {
        "efg_edge": "eFG% Edge (40% wt)",
        "tov_edge": "TOV Rate Edge (25% wt)",
        "orb_edge": "Off. Reb Edge (20% wt)",
        "ftr_edge": "FT Rate Edge (15% wt)",
        "total":    "COMPOSITE EDGE",
    }
    for k, label in ff_labels.items():
        marker = " <<" if k == "total" else ""
        val = ff[k]
        direction = f"(Barca +{val:.2f})" if val > 0 else f"(Valencia +{abs(val):.2f})"
        print(f"  {label:<28} {val:>+8.3f}  {direction}{marker}")

    # --- Score Projection ---
    proj_home, proj_away, model_spread, model_total = project_score(
        barca_m, valencia_m,
        home_name, away_name,
        H2H_BARCA_WINS, H2H_VALENCIA_WINS,
        home_court_advantage=3.5,
    )

    win_prob_home = win_probability(model_spread)
    win_prob_away = 1.0 - win_prob_home

    print(f"\n[ SCORE PROJECTION ]")
    print(f"  {home_name:<22}   {proj_home:.1f}")
    print(f"  {away_name:<22}   {proj_away:.1f}")
    print(f"  Model Spread (Home):      {model_spread:+.2f}")
    print(f"  Model Total:              {model_total:.1f}")
    print(f"  Win Probability Barca:    {win_prob_home:.1%}")
    print(f"  Win Probability Valencia: {win_prob_away:.1%}")

    # --- Q1 / 1H / FG Splits ---
    splits = project_splits(proj_home, proj_away, barca_m["poss"], valencia_m["poss"])
    # Pass market lines here if known; None = model-only output
    print_split_table(
        splits, home_name, away_name,
        mkt_q1_total=None, mkt_h1_total=None, mkt_fg_total=None,
        mkt_q1_spread=None, mkt_h1_spread=None, mkt_fg_spread=None,
    )

    # --- Head-to-Head Context ---
    h2h_pct_valencia = H2H_VALENCIA_WINS / H2H_TOTAL
    print(f"\n[ HEAD-TO-HEAD SINCE 2000-01 ]")
    print(f"  Barcelona wins:        {H2H_BARCA_WINS:>3}  ({1-h2h_pct_valencia:.1%})")
    print(f"  Valencia Basket wins:  {H2H_VALENCIA_WINS:>3}  ({h2h_pct_valencia:.1%})")
    print(f"  H2H adjustment applied: +{(h2h_pct_valencia-0.5)*4:.2f} pts toward Valencia")

    # --- Market Guidance ---
    print(f"\n[ MODEL SUMMARY & MARKET GUIDANCE ]")

    lean = home_name if model_spread > 1.0 else away_name if model_spread < -1.0 else "EVEN (PASS)"
    spread_label = "BARCA -ML" if model_spread > 0 else "VALENCIA -ML"

    # Quarter 1 projection (25% of total with slight home variance)
    q1_proj = round(model_total * 0.255, 1)

    print(f"  Lean:               {lean}")
    print(f"  Model Spread:       {model_spread:+.2f}  (positive = Barca favored)")
    print(f"  Model Total:        {model_total:.1f}")
    print(f"  Q1 Total Proj:      {q1_proj:.1f}")
    print()

    # Market comparison (no live line provided; flag for user)
    print(f"  >> Barca ORtg ({barca_m['ortg']:.1f}) vs Valencia DRtg ({valencia_m['drtg']:.1f}) = "
          f"{barca_m['ortg'] - valencia_m['drtg']:+.1f} off edge")
    print(f"  >> Valencia ORtg ({valencia_m['ortg']:.1f}) vs Barca DRtg ({barca_m['drtg']:.1f}) = "
          f"{valencia_m['ortg'] - barca_m['drtg']:+.1f} off edge")
    print()

    # Flag key mismatches
    print("[ KEY MATCHUP FLAGS ]")
    flags = []
    if BARCA["tp_pct"] > VALENCIA["tp_pct"] + 0.03:
        flags.append(f"  [+] Barca 3P% edge: {BARCA['tp_pct']:.1%} vs {VALENCIA['tp_pct']:.1%}")
    if BARCA["fg_pct"] > VALENCIA["fg_pct"] + 0.02:
        flags.append(f"  [+] Barca FG% edge: {BARCA['fg_pct']:.1%} vs {VALENCIA['fg_pct']:.1%}")
    if VALENCIA["orb"] > BARCA["orb"] + 3:
        flags.append(f"  [!] Valencia dominates offensive glass: {VALENCIA['orb']:.1f} vs {BARCA['orb']:.1f} ORB")
    if BARCA_OPP["ppg"] < VALENCIA_OPP["ppg"] - 1:
        flags.append(f"  [+] Barca defense: allows {BARCA_OPP['ppg']:.1f} vs Valencia's {VALENCIA_OPP['ppg']:.1f}")
    if VALENCIA["ppg"] > BARCA["ppg"] + 3:
        flags.append(f"  [!] Valencia scores more: {VALENCIA['ppg']:.1f} vs {BARCA['ppg']:.1f} PPG")
    if VALENCIA["apg"] > BARCA["apg"] + 2:
        flags.append(f"  [!] Valencia ball movement advantage: {VALENCIA['apg']:.1f} vs {BARCA['apg']:.1f} APG")
    if not flags:
        flags.append("  No dominant mismatches detected — balanced matchup")
    for f in flags:
        print(f)

    print(f"\n{'='*65}\n")

    # --- Build JSON output ---
    result = {
        "sport": "basketball",
        "league": "ACB Liga Endesa",
        "season": "2025-2026",
        "home_team": home_name,
        "away_team": away_name,
        "timestamp": datetime.now().isoformat(),
        "advanced_metrics": {
            "barcelona": barca_m,
            "valencia": valencia_m,
        },
        "four_factors": ff,
        "projection": {
            "home_score": proj_home,
            "away_score": proj_away,
            "model_spread": model_spread,
            "model_total": model_total,
            "win_prob_home": win_prob_home,
            "win_prob_away": win_prob_away,
            "lean": lean,
        },
        "splits": splits,
        "h2h": {
            "barca_wins": H2H_BARCA_WINS,
            "valencia_wins": H2H_VALENCIA_WINS,
            "total_games": H2H_TOTAL,
            "valencia_win_pct": round(h2h_pct_valencia, 4),
        },
        "key_flags": flags,
    }

    out_dir = Path("output/basketball")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "barcelona_vs_valencia_basket.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"[Saved] Results written to: {out_path}")
    return result


if __name__ == "__main__":
    run_analysis()
