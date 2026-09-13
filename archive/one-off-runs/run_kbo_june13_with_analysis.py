#!/usr/bin/env python
"""
Comprehensive KBO Analysis - June 13, 2026 (Series Finale)
===========================================================
Matchup 1: Hanwha Eagles vs Kiwoom Heroes (Gocheok Sky Dome)
Matchup 2: Doosan Bears vs KIA Tigers (KIA Champions Field)

Running through MultiSportPredict pipeline with added sabermetric data,
sharp consensus, and park factor adjustments.
"""

import sys
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Import core confidence engine
from core.confidence_engine import confidence_score, bet_recommendation

from core import init_db
init_db()


def sigmoid(x: float) -> float:
    x = max(-500, min(500, x))
    return 1 / (1 + math.exp(-x))


def clamp(x: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, x))


def poisson_over_prob(lam: float, line: float) -> float:
    n = int(math.floor(line))
    return 1 - sum(math.exp(-lam) * lam**k / math.factorial(k) for k in range(0, n + 1))


# ============================================================================
# KBO TEAM STATS (Updated with analysis data)
# ============================================================================

KBO_TEAM_PROFILES = {
    "Hanwha Eagles": {
        "abbreviation": "HAN",
        "runs_per_game": 4.2,
        "runs_allowed_per_game": 5.0,
        "batting_avg": 0.248,
        "on_base_pct": 0.310,
        "slugging_pct": 0.365,
        "ops": 0.675,
        "iso": 0.118,
        "home_runs_per_game": 0.6,
        "strikeouts_per_game": 8.8,
        "walks_per_game": 3.2,
        "hits_per_game": 8.5,
        "era": 4.50,
        "whip": 1.40,
        "k_per_9": 7.5,
        "bb_per_9": 3.0,
        "fip": 4.20,
        "bullpen_fip": 4.10,
        "oswing_pct": 0.34,
        "quality_start_pct": 0.36,
        "recent_form": 0.38,
        "home_record": 0.50,
        "away_record": 0.48,
        "vs_opponent_record": 0.40,
        "woba": 0.300,
        "wrc_plus": 78,
        "swstr_pct": 0.11,
        "notes": "Severe offensive slump. ISO <.120, O-Swing% spiked. Chasing bad pitches. Severe power outage."
    },
    "Kiwoom Heroes": {
        "abbreviation": "KWO",
        "runs_per_game": 5.2,
        "runs_allowed_per_game": 4.2,
        "batting_avg": 0.272,
        "on_base_pct": 0.345,
        "slugging_pct": 0.430,
        "ops": 0.775,
        "iso": 0.158,
        "home_runs_per_game": 1.0,
        "strikeouts_per_game": 7.8,
        "walks_per_game": 3.6,
        "hits_per_game": 9.8,
        "era": 3.65,
        "whip": 1.25,
        "k_per_9": 8.5,
        "bb_per_9": 2.2,
        "fip": 3.70,
        "bullpen_fip": 3.50,
        "oswing_pct": 0.28,
        "quality_start_pct": 0.48,
        "recent_form": 0.62,
        "home_record": 0.65,
        "away_record": 0.52,
        "vs_opponent_record": 0.60,
        "woba": 0.338,
        "wrc_plus": 108,
        "swstr_pct": 0.09,
        "notes": "Excellent execution at home. High first-pitch strikes, forcing negative counts. Weak ground balls from opponent."
    },
    "Doosan Bears": {
        "abbreviation": "DOO",
        "runs_per_game": 5.2,
        "runs_allowed_per_game": 4.8,
        "batting_avg": 0.265,
        "on_base_pct": 0.348,
        "slugging_pct": 0.440,
        "ops": 0.788,
        "iso": 0.175,
        "home_runs_per_game": 1.2,
        "strikeouts_per_game": 8.2,
        "walks_per_game": 3.8,
        "hits_per_game": 9.2,
        "era": 4.10,
        "whip": 1.32,
        "k_per_9": 8.8,
        "bb_per_9": 3.2,
        "fip": 3.85,
        "bullpen_fip": 3.80,
        "oswing_pct": 0.30,
        "quality_start_pct": 0.42,
        "recent_form": 0.55,
        "home_record": 0.60,
        "away_record": 0.50,
        "vs_opponent_record": 0.52,
        "woba": 0.325,
        "wrc_plus": 100,
        "swstr_pct": 0.10,
        "notes": "Three-true-outcomes team. Pitchers hunt Ks, batters look for HR/BB. Recent 1st-inning BB% spike."
    },
    "KIA Tigers": {
        "abbreviation": "KIA",
        "runs_per_game": 5.0,
        "runs_allowed_per_game": 4.5,
        "batting_avg": 0.275,
        "on_base_pct": 0.342,
        "slugging_pct": 0.415,
        "ops": 0.757,
        "iso": 0.140,
        "home_runs_per_game": 0.9,
        "strikeouts_per_game": 7.0,
        "walks_per_game": 3.4,
        "hits_per_game": 9.8,
        "era": 3.90,
        "whip": 1.30,
        "k_per_9": 7.2,
        "bb_per_9": 2.4,
        "fip": 3.80,
        "bullpen_fip": 3.55,
        "oswing_pct": 0.27,
        "quality_start_pct": 0.43,
        "recent_form": 0.58,
        "home_record": 0.62,
        "away_record": 0.48,
        "vs_opponent_record": 0.55,
        "woba": 0.328,
        "wrc_plus": 98,
        "swstr_pct": 0.072,
        "notes": "Classic contact baseball. Lowest team SwStr% in KBO. Neutralizes Doosan's power pitchers by forcing defense to make plays."
    },
}

# Park factors
PARK_FACTORS = {
    "Gocheok Sky Dome": {
        "hr_factor": 0.85,
        "runs_factor": 0.92,
        "hits_factor": 0.94,
        "k_factor": 1.05,
        "description": "Indoor, pitcher-friendly dome. Suppressed home runs and extra-base hits."
    },
    "KIA Champions Field": {
        "hr_factor": 1.05,
        "runs_factor": 1.02,
        "hits_factor": 1.01,
        "k_factor": 0.97,
        "description": "Moderate offensive park."
    }
}


def analyze_matchup(
    home_team: str,
    away_team: str,
    venue: str,
    date: str = "2026-06-13",
    series_score: str = "",
    analysis_data: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Comprehensive analysis for a KBO match using edge analysis and model.
    """
    home_stats = KBO_TEAM_PROFILES[home_team]
    away_stats = KBO_TEAM_PROFILES[away_team]
    park = PARK_FACTORS[venue]

    generation_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    print("=" * 80)
    print(f"KBO MATCH ANALYSIS: {away_team} @ {home_team}")
    print(f"Korean Baseball Organization - {date}")
    print(f"Venue: {venue} | {park['description']}")
    print(f"Series: {series_score}")
    print("Generated by MultiSportPredict Engine")
    print(f"Timestamp: {generation_time}")
    print("=" * 80)
    print()

    # ── 1. TEAM STATISTICS ──
    print("1. TEAM STATISTICS (Updated with Sabermetric Data)")
    print("-" * 50)
    for label, stats in [(f"  {home_team} (Home):", home_stats), (f"  {away_team} (Away):", away_stats)]:
        print(label)
        print(f"    Runs/Game: {stats['runs_per_game']:.1f} | Runs Allowed: {stats['runs_allowed_per_game']:.1f}")
        print(f"    Batting Avg: {stats['batting_avg']:.3f} | ISO: {stats['iso']:.3f} | OPS: {stats['ops']:.3f}")
        print(f"    wOBA: {stats['woba']:.3f} | wRC+: {stats['wrc_plus']:.0f}")
        print(f"    ERA: {stats['era']:.2f} | WHIP: {stats['whip']:.2f} | FIP: {stats['fip']:.2f}")
        print(f"    K/9: {stats['k_per_9']:.1f} | BB/9: {stats['bb_per_9']:.1f}")
        print(f"    O-Swing%: {stats['oswing_pct']:.1%} | SwStr%: {stats['swstr_pct']:.1%}")
        print(f"    Recent Form: {stats['recent_form']:.0%} | Home/Away: {stats.get('home_record', 0.5):.0%}/{stats.get('away_record', 0.45):.0%}")
        print(f"    Notes: {stats['notes']}")
        print()

    # ── 2. PARK FACTOR ADJUSTMENTS ──
    print("2. PARK FACTOR ADJUSTMENTS")
    print("-" * 50)
    print(f"    Venue: {venue}")
    print(f"    HR Factor: {park['hr_factor']:.2f} | Runs Factor: {park['runs_factor']:.2f}")
    print(f"    Hits Factor: {park['hits_factor']:.2f} | K Factor: {park['k_factor']:.2f}")
    print()

    # ── 3. RUN PROJECTIONS ──
    print("3. RUN PROJECTIONS (Model-Based)")
    print("-" * 50)

    # Base run projections adjusted for opponent ERA and park
    home_runs_base = (home_stats['runs_per_game'] / 9.8 * 5.0 + (away_stats['era'] / 4.5) * 2.5) / 2
    away_runs_base = (away_stats['runs_per_game'] / 9.8 * 5.0 + (home_stats['era'] / 4.5) * 2.5) / 2

    # Park adjustments
    home_runs_proj = home_runs_base * park['runs_factor'] * park['hr_factor']
    away_runs_proj = away_runs_base * park['runs_factor'] * park['hr_factor']

    # Home advantage
    home_runs_proj += 0.3
    away_runs_proj *= 0.92

    # Apply series/form adjustments
    home_runs_proj *= (0.85 + home_stats['recent_form'] * 0.30)
    away_runs_proj *= (0.85 + away_stats['recent_form'] * 0.30)

    total_proj = home_runs_proj + away_runs_proj

    print(f"    {home_team} Expected Runs: {home_runs_proj:.2f}")
    print(f"    {away_team} Expected Runs: {away_runs_proj:.2f}")
    print(f"    Total Projected: {total_proj:.2f}")
    print()

    # ── 4. TOTALS ANALYSIS (Poisson) ──
    print("4. TOTALS ANALYSIS (Poisson Model)")
    print("-" * 50)
    p_over_65 = poisson_over_prob(total_proj, 6.5)
    p_over_75 = poisson_over_prob(total_proj, 7.5)
    p_over_85 = poisson_over_prob(total_proj, 8.5)
    p_over_95 = poisson_over_prob(total_proj, 9.5)
    p_over_105 = poisson_over_prob(total_proj, 10.5)

    print(f"    Over 6.5: {p_over_65:.1%}")
    print(f"    Over 7.5: {p_over_75:.1%}")
    print(f"    Over 8.5: {p_over_85:.1%}")
    print(f"    Over 9.5: {p_over_95:.1%}")
    print(f"    Over 10.5: {p_over_105:.1%}")

    total_conf = confidence_score(total_proj - 8.5, volatility=0.65)
    total_rec = bet_recommendation(total_conf, "mlb_totals")
    total_lean = "Under" if total_proj < 8.5 else "Over"
    print(f"    Model Total Lean: {total_lean} (Conf: {total_conf:.1f}%)")
    print(f"    Recommendation: {total_rec}")
    print()

    # ── 5. WIN PROBABILITY ──
    print("5. WIN PROBABILITY")
    print("-" * 50)
    home_win_raw = home_runs_proj / (home_runs_proj + away_runs_proj)
    home_win_prob = clamp(home_win_raw * 0.85 + 0.12)
    away_win_prob = clamp(1 - home_win_prob)

    print(f"    {home_team} Win Probability: {home_win_prob:.1%}")
    print(f"    {away_team} Win Probability: {away_win_prob:.1%}")

    side_edge = abs(home_win_prob - 0.5) * 100
    side_conf = confidence_score(abs(home_runs_proj - away_runs_proj) * 100, volatility=0.55)
    side_rec = bet_recommendation(side_conf, "mlb_sides")
    print(f"    Side Edge: {side_edge:.1f} | Confidence: {side_conf:.1f}%")
    print(f"    Recommendation: {side_rec}")
    print()

    # ── 6. SHARP CONSENSUS & MARKET LEAN ──
    print("6. SHARP CONSENSUS & MARKET LEAN")
    print("-" * 50)
    if analysis_data:
        for key, value in analysis_data.items():
            if key == "sharp_lean":
                print(f"    MARKET LEAN: {value}")
            elif key == "notes":
                print(f"    ANALYSIS NOTES: {value}")
            elif key == "prop_angle":
                print(f"    PROP ANGLE: {value}")
            else:
                print(f"    {key.upper()}: {value}")
    print()

    # ── 7. PLAYER PROPS ──
    print("7. PLAYER PROPS PROJECTIONS")
    print("-" * 50)

    # Pitcher K props
    home_k9 = home_stats['k_per_9']
    away_k9 = away_stats['k_per_9']
    park_k_factor = park['k_factor']

    # Strikeout projections (approx. PAs per game)
    home_k_proj = home_k9 * park_k_factor * 5.5 / 9.0 * 2
    away_k_proj = away_k9 * park_k_factor * 5.5 / 9.0 * 2

    # Away pitcher K prop (primary angle for matchup 1)
    away_sp_k_proj = away_k9 * park_k_factor * 5.5 / 9.0 * 2.5

    print(f"    {home_team} SP Ks: {home_k_proj:.1f} (vs avg ~{away_k9:.1f}K/9)")
    print(f"    {away_team} SP Ks: {away_k_proj:.1f} (vs avg ~{home_k9:.1f}K/9)")
    if analysis_data and "prop_angle" in analysis_data:
        print(f"    KEY PROP: {analysis_data['prop_angle']}")
    print()

    # ── 8. RECOMMENDATIONS ──
    print("8. FINAL RECOMMENDATIONS")
    print("-" * 50)
    print(f"    TOTAL: {total_lean} {total_proj:.2f} (Conf: {total_conf:.1f}%)")
    print(f"    SIDE: {'Home' if home_win_prob > 0.5 else 'Away'} ({home_team if home_win_prob > 0.5 else away_team}) "
          f"({home_win_prob:.1%}/{away_win_prob:.1%}) | Conf: {side_conf:.1f}%")
    print(f"    RUN LINE: Home -1.5: {home_runs_proj:.2f} Projected")
    if analysis_data and "sharp_lean" in analysis_data:
        print(f"    SHARP LEAN: {analysis_data['sharp_lean']}")
    print()
    print("=" * 80)

    # Build result dict
    result = {
        "sport": "baseball",
        "league": "KBO",
        "matchup": f"{away_team} @ {home_team}",
        "venue": venue,
        "date": date,
        "series_context": series_score,
        "generated_at": generation_time,
        "park_factor": park,
        "home_team": {
            "name": home_team,
            "abbreviation": home_stats["abbreviation"],
            "stats": home_stats,
        },
        "away_team": {
            "name": away_team,
            "abbreviation": away_stats["abbreviation"],
            "stats": away_stats,
        },
        "projections": {
            "home_runs": round(home_runs_proj, 2),
            "away_runs": round(away_runs_proj, 2),
            "total_runs": round(total_proj, 2),
            "run_differential": round(home_runs_proj - away_runs_proj, 2),
        },
        "win_probability": {
            "home_prob": round(home_win_prob, 4),
            "away_prob": round(away_win_prob, 4),
        },
        "totals": {
            "over_under_75": round(p_over_75, 4),
            "over_under_85": round(p_over_85, 4),
            "over_under_95": round(p_over_95, 4),
            "model_total_lean": total_lean,
            "total_confidence": round(total_conf, 1),
            "total_recommendation": total_rec,
        },
        "side_analysis": {
            "edge": round(side_edge, 1),
            "confidence": round(side_conf, 1),
            "recommendation": side_rec,
            "lean": "Home" if home_win_prob > 0.5 else "Away",
        },
        "sharp_consensus": analysis_data or {},
        "player_props": {
            "home_sp_k_projected": round(home_k_proj, 1),
            "away_sp_k_projected": round(away_k_proj, 1),
        },
    }

    return result


def main():
    output_dir = Path("output/kbo")
    output_dir.mkdir(parents=True, exist_ok=True)

    # ──────────────────────────────────────────────────────────────────────
    # MATCHUP 1: Hanwha Eagles (Away) @ Kiwoom Heroes (Home)
    # Venue: Gocheok Sky Dome (Seoul)
    # Series: Kiwoom leads 2-0 (W 4-3 Fri, W 3-1 Sat)
    # ──────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 100)
    print("MATCHUP 1/2: Hanwha Eagles @ Kiwoom Heroes")
    print("=" * 100)

    match1_analysis = {
        "sharp_lean": "Under (Total Runs)",
        "prop_angle": "Kiwoom Starting Pitcher - Over Strikeouts (Hanwha chasing pitches, elevated SwStr%)",
        "park": "Gocheok Sky Dome - Indoors, pitcher-friendly, suppressed HR/XBH",
        "series_context": "Kiwoom has completely stifled Hanwha in first two games (4-3, 3-1)",
        "hittersEdge": "Hanwha ISO <.120, O-Swing% spiked, chasing bad pitches, severe power outage",
        "pitchingEdge": "Kiwoom staff executing perfectly: high first-pitch strikes, forcing negative counts, weak ground balls",
        "sharpReasoning": "Syndicates heavily fading Hanwha offense. Classic Under recipe: dead Eagles bat + pitcher-friendly dome.",
    }

    match1_result = analyze_matchup(
        home_team="Kiwoom Heroes",
        away_team="Hanwha Eagles",
        venue="Gocheok Sky Dome",
        date="2026-06-13",
        series_score="Kiwoom leads 2-0 (4-3, 3-1)",
        analysis_data=match1_analysis,
    )

    # Save to file
    out_path = output_dir / "hanwha_eagles_vs_kiwoom_heroes_june13_analysis.json"
    with open(out_path, 'w') as f:
        json.dump(match1_result, f, indent=2, default=str)
    print(f"\nResults saved to: {out_path}")

    # ──────────────────────────────────────────────────────────────────────
    # MATCHUP 2: Doosan Bears (Away) @ KIA Tigers (Home)
    # Venue: KIA Champions Field (Gwangju)
    # Series: Tied 1-1 (DOO 4-2 Fri, KIA 2-1 Sat)
    # ──────────────────────────────────────────────────────────────────────
    print("\n\n" + "=" * 100)
    print("MATCHUP 2/2: Doosan Bears @ KIA Tigers")
    print("=" * 100)

    match2_analysis = {
        "sharp_lean": "KIA Tigers ML (Moneyline) or F5 (First 5 Innings)",
        "prop_angle": "YRFI (Yes Run First Inning) - Doosan's recent 1st-inning BB% spike + KIA's aggressive top-of-order wRC+",
        "park": "KIA Champions Field - Moderate offensive park",
        "series_context": "Tied 1-1 (Doosan 4-2 Fri, KIA 2-1 Sat). Rubber match decides series.",
        "clashOfStyles": "Doosan = three-true-outcomes (K/BB/HR). KIA = classic contact baseball. KIA neutralizes Doosan's power pitchers.",
        "kiaContactFee": "KIA has one of the lowest SwStr% in KBO. This mathematically neutralizes Doosan's power pitchers by forcing defense to make plays.",
        "doosanWeakness": "Doosan's starting rotation has shown spike in 1st-inning BB%. Giving up free passes early is lethal against contact-heavy KIA.",
        "sharpReasoning": "Sharp money sides with home team in rubber match. KIA holds structural advantage - ability to put ball in play vs Doosan's struggling command gives highest mathematical win probability.",
    }

    match2_result = analyze_matchup(
        home_team="KIA Tigers",
        away_team="Doosan Bears",
        venue="KIA Champions Field",
        date="2026-06-13",
        series_score="Series tied 1-1 (Doosan 4-2, KIA 2-1). Rubber match.",
        analysis_data=match2_analysis,
    )

    # Save to file
    out_path = output_dir / "doosan_bears_vs_kia_tigers_june13_analysis.json"
    with open(out_path, 'w') as f:
        json.dump(match2_result, f, indent=2, default=str)
    print(f"\nResults saved to: {out_path}")

    # ──────────────────────────────────────────────────────────────────────
    # SUMMARY
    # ──────────────────────────────────────────────────────────────────────
    print("\n\n" + "=" * 100)
    print("KBO JUNE 13, 2026 - MULTI-SPORT PREDICT ANALYSIS SUMMARY")
    print("=" * 100)
    print()
    m1 = match1_result
    m2 = match2_result
    print(f"MATCH 1: {m1['home_team']['name']} vs {m1['away_team']['name']}")
    print(f"    Projected: {m1['projections']['away_runs']:.2f} @ {m1['projections']['home_runs']:.2f} (Total: {m1['projections']['total_runs']:.2f})")
    print(f"    Win Prob: {m1['away_team']['name']} {m1['win_probability']['away_prob']:.1%} | {m1['home_team']['name']} {m1['win_probability']['home_prob']:.1%}")
    print(f"    TOTAL: {m1['totals']['model_total_lean']} {m1['totals']['total_recommendation']} ({m1['totals']['total_confidence']:.1f}%)")
    print(f"    SHARP: {m1['sharp_consensus']['sharp_lean']}")
    print()
    print(f"MATCH 2: {m2['away_team']['name']} @ {m2['home_team']['name']}")
    print(f"    Projected: {m2['projections']['away_runs']:.2f} @ {m2['projections']['home_runs']:.2f} (Total: {m2['projections']['total_runs']:.2f})")
    print(f"    Win Prob: {m2['home_team']['name']} {m2['win_probability']['home_prob']:.1%} | {m2['away_team']['name']} {m2['win_probability']['away_prob']:.1%}")
    print(f"    TOTAL: {m2['totals']['model_total_lean']} {m2['totals']['total_recommendation']} ({m2['totals']['total_confidence']:.1f}%)")
    print(f"    SHARP: {m2['sharp_consensus']['sharp_lean']}")
    print()
    print("=" * 100)


if __name__ == "__main__":
    main()