#!/usr/bin/env python
"""
Deep Dive Analysis — MLB June 15, 2026 Doubleheader

1) Miami Marlins vs Philadelphia Phillies
2) Colorado Rockies vs Chicago Cubs
"""

import sys
import json
import math
from datetime import datetime
from pathlib import Path

from models.baseball_predictor import (
    BaseballPredictor,
    get_league_config,
)
from core.confidence_engine import confidence_score, bet_recommendation


def sigmoid(x: float) -> float:
    x = max(-500, min(500, x))
    return 1 / (1 + math.exp(-x))


def clamp(x: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, x))


def nrfi_compute(home_k_rate, away_k_rate, home_era, away_era):
    """Compute No Run First Inning probability"""
    base_nrfi = 0.53
    era_adj = ((5.0 - home_era) + (5.0 - away_era)) * 0.015
    k_adj = ((home_k_rate - 0.22) + (away_k_rate - 0.22)) * 0.5
    nrfi_prob = max(0.30, min(0.75, base_nrfi + era_adj + k_adj))
    edge = nrfi_prob - 0.50
    conf = confidence_score(edge * 100, volatility=0.60)
    lean = "NRFI" if nrfi_prob > 0.55 else "YRFI"
    rec = bet_recommendation(conf, "mlb_nrfi")
    return {"probability": round(nrfi_prob, 4), "lean": lean, "confidence": round(conf, 1), "recommendation": rec}


def analyze_marlins_phillies():
    """Miami Marlins vs Philadelphia Phillies"""
    
    print("\n" + "=" * 80)
    print("MLB: Miami Marlins vs Philadelphia Phillies")
    print("=" * 80 + "\n")

    # ========================================================
    # Miami Marlins (Home)
    # ========================================================
    # 2026: Rebuilding, young pitching, low offense
    # Park: LoanDepot Park (pitcher-friendly, suppresses HRs ~10%)
    marlins_runs_scored = 3.9
    marlins_runs_allowed = 4.4
    marlins_era = 4.10
    marlins_whip = 1.28
    marlins_obp = 0.310
    marlins_slg = 0.385
    marlins_k_rate = 0.235   # Pitching staff K%
    marlins_hr_rate = 0.028  # HR/PA allowed
    marlins_park_factor = 0.92  # Pitcher-friendly

    # ========================================================
    # Philadelphia Phillies (Away)
    # ========================================================
    # 2026: Contender, powerful lineup, solid pitching
    # Harper, Schwarber, Castellanos, Turner core
    phillies_runs_scored = 4.8
    phillies_runs_allowed = 4.0
    phillies_era = 3.70
    phillies_whip = 1.20
    phillies_obp = 0.330
    phillies_slg = 0.430
    phillies_k_rate = 0.240
    phillies_hr_rate = 0.032

    # ========================================================
    # Expected Runs
    # ========================================================
    home_runs = (marlins_runs_scored + phillies_runs_allowed) / 2
    away_runs = (phillies_runs_scored + marlins_runs_allowed) / 2
    total_runs = home_runs + away_runs
    run_diff = home_runs - away_runs

    # Park factor adjustment
    home_runs *= marlins_park_factor
    away_runs *= (2 - marlins_park_factor)  # Visiting team adjustment

    # Pitcher matchup edge
    pitcher_edge = (phillies_era - marlins_era) * 0.5
    home_runs += pitcher_edge
    away_runs -= pitcher_edge

    total_runs = home_runs + away_runs
    run_diff = home_runs - away_runs
    home_win_prob = clamp(sigmoid(run_diff / 2.5 + 0.12))

    print("1. RUN PROJECTION")
    print("-" * 40)
    print(f"   {home_runs:.2f} - {away_runs:.2f} (Total: {total_runs:.2f})")
    print(f"   Miami Win Prob: {home_win_prob:.1%}")
    print(f"   Projected Run Diff: {run_diff:+.2f}")
    print()

    # ========================================================
    # NRFI
    # ========================================================
    print("2. NRFI (NO RUN FIRST INNING) ANALYSIS")
    print("-" * 40)
    nrfi = nrfi_compute(
        marlins_k_rate, phillies_k_rate,
        marlins_era, phillies_era
    )
    print(f"   NRFI Probability: {nrfi['probability']:.1%}")
    print(f"   Lean: {nrfi['lean']} | Conf: {nrfi['confidence']:.1f}%")
    print()

    # ========================================================
    # OVER/UNDER Analysis
    # ========================================================
    print("3. OVER/UNDER ANALYSIS")
    print("-" * 40)
    market_total = 8.0
    total_edge = total_runs - market_total
    total_conf = confidence_score(total_edge * 8, volatility=0.55)
    print(f"   Market Total: O/U {market_total}")
    print(f"   Projected: {total_runs:.2f}")
    print(f"   Edge: {total_edge:+.2f}")
    print(f"   Recommendation: {'OVER' if total_edge > 0 else 'UNDER'} (Conf: {total_conf:.1f}%)")
    print()

    # ========================================================
    # PROP ANALYSIS
    # ========================================================
    print("4. PLAYER PROP ANALYSIS")
    print("-" * 40)
    
    # Phillies HR probability (vs Marlins pitching in pitcher-friendly park)
    phillies_hr_proj = phillies_hr_rate * 38 * 0.5 * marlins_park_factor
    marlins_hr_proj = marlins_hr_rate * 38 * 0.5 * (2 - marlins_park_factor)
    print(f"   Phillies Team HR Projection: {phillies_hr_proj:.1f}")
    print(f"   Marlins Team HR Projection: {marlins_hr_proj:.1f}")
    
    # Strikeouts
    phillies_k_proj = phillies_k_rate * 38 * 0.5
    marlins_k_proj = marlins_k_rate * 38 * 0.5
    print(f"   Phillies K (pitched): {away_runs * 1.5:.1f}")
    print(f"   Marlins K (pitched): {home_runs * 1.5:.1f}")
    print()

    results = {
        "match": "Miami Marlins vs Philadelphia Phillies",
        "projected_score": f"MIA {home_runs:.1f} - {away_runs:.1f} PHI",
        "projected_total": round(total_runs, 2),
        "home_win_prob": round(home_win_prob, 3),
        "nrfi_analysis": nrfi,
        "total_analysis": {
            "market": market_total,
            "projected": round(total_runs, 2),
            "edge": round(total_edge, 2),
            "confidence": round(total_conf, 1),
            "recommendation": "OVER" if total_edge > 0 else "UNDER",
        },
        "recommendations": {
            "side": "PHI ML" if home_win_prob < 0.50 else "MIA ML",
            "total": "OVER" if total_edge > 0 else "UNDER",
            "nrfi": nrfi['lean'],
        }
    }
    
    print("   === RECOMMENDATIONS ===")
    print(f"   Side: {results['recommendations']['side']}")
    print(f"   Total: {'OVER' if total_edge > 0 else 'UNDER'} {market_total} (Conf: {total_conf:.1f}%)")
    print(f"   NRFI: {nrfi['lean']} (Conf: {nrfi['confidence']:.1f}%)")
    print()

    return results


def analyze_rockies_cubs():
    """Colorado Rockies vs Chicago Cubs"""
    
    print("\n" + "=" * 80)
    print("MLB: Colorado Rockies vs Chicago Cubs")
    print("=" * 80 + "\n")

    # ========================================================
    # Colorado Rockies (Home)
    # ========================================================
    # Coors Field = extreme hitter's park (highest altitude)
    # Poor pitching, but offense boosted by park
    rockies_runs_scored = 4.4
    rockies_runs_allowed = 5.2
    rockies_era = 5.10
    rockies_whip = 1.45
    rockies_obp = 0.325
    rockies_slg = 0.420
    rockies_k_rate = 0.200
    rockies_hr_rate = 0.035
    rockies_park_factor = 1.28  # Coors Field extreme hitter park

    # ========================================================
    # Chicago Cubs (Away)
    # ========================================================
    # Competitive team, balanced roster
    # Travel to altitude = thin air adjustment
    cubs_runs_scored = 4.5
    cubs_runs_allowed = 4.2
    cubs_era = 3.90
    cubs_whip = 1.25
    cubs_obp = 0.325
    cubs_slg = 0.415
    cubs_k_rate = 0.230
    cubs_hr_rate = 0.030

    # ========================================================
    # Expected Runs (with Coors Field adjustment)
    # ========================================================
    home_runs = (rockies_runs_scored + cubs_runs_allowed) / 2
    away_runs = (cubs_runs_scored + rockies_runs_allowed) / 2
    
    # Coors Field: ~28% boost to scoring
    home_runs *= rockies_park_factor
    away_runs *= rockies_park_factor  # Visitors also benefit from thin air

    # Pitcher matchup edge
    pitcher_edge = (cubs_era - rockies_era) * 0.5
    home_runs += pitcher_edge
    away_runs -= pitcher_edge

    total_runs = home_runs + away_runs
    run_diff = home_runs - away_runs
    home_win_prob = clamp(sigmoid(run_diff / 2.5 + 0.12))

    print("1. RUN PROJECTION")
    print("-" * 40)
    print(f"   {home_runs:.2f} - {away_runs:.2f} (Total: {total_runs:.2f})")
    print(f"   Colorado Win Prob: {home_win_prob:.1%}")
    print(f"   Projected Run Diff: {run_diff:+.2f}")
    print()

    # ========================================================
    # NRFI
    # ========================================================
    print("2. NRFI (NO RUN FIRST INNING) ANALYSIS")
    print("-" * 40)
    nrfi = nrfi_compute(
        rockies_k_rate, cubs_k_rate,
        rockies_era, cubs_era
    )
    print(f"   NRFI Probability: {nrfi['probability']:.1%}")
    print(f"   Lean: {nrfi['lean']} | Conf: {nrfi['confidence']:.1f}%")
    print()

    # ========================================================
    # OVER/UNDER Analysis
    # ========================================================
    print("3. OVER/UNDER ANALYSIS")
    print("-" * 40)
    market_total = 9.5  # Coors Field games have higher totals
    total_edge = total_runs - market_total
    total_conf = confidence_score(total_edge * 8, volatility=0.55)
    print(f"   Market Total: O/U {market_total}")
    print(f"   Projected: {total_runs:.2f}")
    print(f"   Edge: {total_edge:+.2f}")
    print(f"   Recommendation: {'OVER' if total_edge > 0 else 'UNDER'} (Conf: {total_conf:.1f}%)")
    print()

    # ========================================================
    # PROP ANALYSIS
    # ========================================================
    print("4. PLAYER PROP ANALYSIS")
    print("-" * 40)
    
    cubs_hr_proj = cubs_hr_rate * 38 * 0.5 * rockies_park_factor
    rockies_hr_proj = rockies_hr_rate * 38 * 0.5 * rockies_park_factor
    print(f"   Cubs Team HR Projection (at Coors): {cubs_hr_proj:.1f}")
    print(f"   Rockies Team HR Projection: {rockies_hr_proj:.1f}")
    
    # K projections (lower at Coors due to thin air)
    cubs_k_proj = cubs_k_rate * 38 * 0.5 * 0.9  # 10% reduction at altitude
    rockies_k_proj = rockies_k_rate * 38 * 0.5 * 0.9
    print(f"   Cubs K (pitched, Coors adj): {cubs_k_proj:.1f}")
    print(f"   Rockies K (pitched, Coors adj): {rockies_k_proj:.1f}")
    print()

    results = {
        "match": "Colorado Rockies vs Chicago Cubs",
        "projected_score": f"COL {home_runs:.1f} - {away_runs:.1f} CHC",
        "projected_total": round(total_runs, 2),
        "home_win_prob": round(home_win_prob, 3),
        "nrfi_analysis": nrfi,
        "total_analysis": {
            "market": market_total,
            "projected": round(total_runs, 2),
            "edge": round(total_edge, 2),
            "confidence": round(total_conf, 1),
            "recommendation": "OVER" if total_edge > 0 else "UNDER",
        },
        "recommendations": {
            "side": "CHC ML" if home_win_prob < 0.50 else "COL ML",
            "total": "OVER" if total_edge > 0 else "UNDER",
            "nrfi": nrfi['lean'],
        }
    }
    
    print("   === RECOMMENDATIONS ===")
    print(f"   Side: {results['recommendations']['side']}")
    print(f"   Total: {'OVER' if total_edge > 0 else 'UNDER'} {market_total} (Conf: {total_conf:.1f}%)")
    print(f"   NRFI: {nrfi['lean']} (Conf: {nrfi['confidence']:.1f}%)")
    print()

    return results


def main():
    print("=" * 80)
    print("MLB DOUBLEHEADER ANALYSIS — JUNE 15, 2026")
    print("=" * 80)
    
    miami = analyze_marlins_phillies()
    colorado = analyze_rockies_cubs()
    
    # Save combined results
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    combined = {
        "timestamp": datetime.now().isoformat(),
        "miami_vs_philadelphia": miami,
        "colorado_vs_chicago": colorado,
    }
    
    output_path = output_dir / "mlb_june15_analysis.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 80)
    print("MASTER RECOMMENDATIONS SUMMARY")
    print("=" * 80)
    
    print("\n--- MIA vs PHI ---")
    print(f"  Projected: {miami['projected_score']}")
    print(f"  Total: {miami['total_analysis']['recommendation']} {miami['total_analysis']['market']} (Conf: {miami['total_analysis']['confidence']:.1f}%)")
    print(f"  NRFI: {miami['nrfi_analysis']['lean']} (Conf: {miami['nrfi_analysis']['confidence']:.1f}%)")
    
    print("\n--- COL vs CHC ---")
    print(f"  Projected: {colorado['projected_score']}")
    print(f"  Total: {colorado['total_analysis']['recommendation']} {colorado['total_analysis']['market']} (Conf: {colorado['total_analysis']['confidence']:.1f}%)")
    print(f"  NRFI: {colorado['nrfi_analysis']['lean']} (Conf: {colorado['nrfi_analysis']['confidence']:.1f}%)")
    
    print(f"\nResults saved to: {output_path}")
    print()


if __name__ == "__main__":
    main()