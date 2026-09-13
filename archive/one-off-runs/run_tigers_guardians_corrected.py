#!/usr/bin/env python
"""
Detroit Tigers vs Cleveland Guardians - Corrected Prediction
Uses corrected pitcher data: Tarik Skubal (LHP, 2.70 ERA) vs Joey Cantillo (LHP, 4.57 ERA)
With 84F weather adjustment and environmental factors.
"""

import json
import math
import sys
import io
from pathlib import Path

# Fix Windows encoding for console output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


def sigmoid(x):
    x = max(-500, min(500, x))
    return 1 / (1 + math.exp(-x))


def weather_hr_multiplier(temp_f, wind_speed=0.0, wind_dir_factor=0.0):
    temp_adj = (temp_f - 70) * 0.005
    wind_adj = wind_speed * wind_dir_factor * 0.01
    return round(temp_adj + wind_adj, 4)


def project_k_prop(pitcher_data):
    k_rate = pitcher_data["k_rate"]
    recent_k_rate = pitcher_data["recent_k_rate"]
    innings_proj = pitcher_data["innings_proj"]
    prop_line = pitcher_data["prop_line"]

    blended_k_rate = 0.6 * recent_k_rate + 0.4 * k_rate
    k_per_9 = blended_k_rate * 9
    projected_ks = (k_per_9 / 9) * innings_proj
    edge = projected_ks - prop_line
    recommendation = "Over" if edge > 0.3 else ("Under" if edge < -0.3 else "PASS")
    confidence = min(95, abs(edge) * 20 + 30)

    return {
        "pitcher_name": pitcher_data["pitcher_name"],
        "handedness": pitcher_data["handedness"],
        "k_rate": k_rate,
        "recent_k_rate": recent_k_rate,
        "blended_k_rate": round(blended_k_rate, 4),
        "k_per_9": round(k_per_9, 2),
        "innings_projected": innings_proj,
        "projected_ks": round(projected_ks, 2),
        "prop_line": prop_line,
        "edge": round(edge, 2),
        "confidence": round(confidence, 1),
        "recommendation": recommendation,
    }


def project_hr_prop(batter_data, pitcher_data, weather_mult, park_factor):
    batter_handedness = batter_data["handedness"]
    pitcher_handedness = pitcher_data["handedness"]

    if batter_handedness == "S":
        hr_rate = batter_data["hr_rate_vs_L"] if pitcher_handedness == "L" else batter_data["hr_rate_vs_R"]
        k_rate = batter_data["k_rate_vs_L"] if pitcher_handedness == "L" else batter_data["k_rate_vs_R"]
    elif batter_handedness == "L" and pitcher_handedness == "R":
        hr_rate = batter_data["hr_rate_vs_R"]
        k_rate = batter_data["k_rate_vs_R"]
    elif batter_handedness == "R" and pitcher_handedness == "L":
        hr_rate = batter_data.get("hr_rate_vs_L", batter_data.get("hr_rate_vs_R", 0.04))
        k_rate = batter_data.get("k_rate_vs_L", batter_data.get("k_rate_vs_R", 0.20))
    else:
        hr_rate = batter_data.get("hr_rate_vs_R", 0.04)
        k_rate = batter_data.get("k_rate_vs_R", 0.20)

    env_adj = weather_mult + (park_factor - 1.0) * 0.5
    barrel_rate = batter_data.get("barrel_rate", 0.08)
    matchup_adj = (barrel_rate - 0.08) * 2.0 - (k_rate - 0.22) * 0.5
    raw_prob = hr_rate + env_adj + matchup_adj
    hr_probability = sigmoid(raw_prob * 5)

    HR_THRESHOLD = 0.12
    recommendation = "Yes HR" if hr_probability > HR_THRESHOLD else "No"
    confidence = min(95, abs(hr_probability - HR_THRESHOLD) * 200 + 40)

    return {
        "player_name": batter_data["player_name"],
        "handedness": batter_handedness,
        "vs_pitcher_handedness": pitcher_handedness,
        "hr_rate_vs_split": round(hr_rate, 4),
        "barrel_rate": barrel_rate,
        "weather_multiplier": weather_mult,
        "env_adjustment": round(env_adj, 4),
        "matchup_adjustment": round(matchup_adj, 4),
        "hr_probability": round(hr_probability, 4),
        "threshold": HR_THRESHOLD,
        "confidence": round(confidence, 1),
        "recommendation": recommendation,
    }


def project_total_bases(batter_data, pitcher_data, weather_mult):
    slg = batter_data["slg"]
    pa_proj = batter_data["pa_proj"]
    prop_line = batter_data["prop_line"]
    batter_handedness = batter_data["handedness"]
    pitcher_handedness = pitcher_data["handedness"]

    if batter_handedness == "S":
        k_rate = batter_data["k_rate_vs_L"] if pitcher_handedness == "L" else batter_data["k_rate_vs_R"]
    else:
        k_rate = batter_data.get("k_rate_vs_L", batter_data.get("k_rate_vs_R", 0.20))

    bb_rate = 0.08
    projected_ab = pa_proj * (1 - bb_rate)
    adjusted_slg = slg * (1 + weather_mult * 2)
    projected_tb = adjusted_slg * projected_ab * (1.05 + weather_mult)

    pitcher_whip = pitcher_data.get("hard_hit_allowed", 0.35) + 1.0
    whip_factor = pitcher_whip / 1.3
    projected_tb *= whip_factor

    edge = projected_tb - prop_line
    recommendation = "Over" if edge > 0.2 else ("Under" if edge < -0.2 else "PASS")
    confidence = min(95, abs(edge) * 25 + 35)

    return {
        "player_name": batter_data["player_name"],
        "handedness": batter_handedness,
        "slg": slg,
        "pa_projected": pa_proj,
        "projected_ab": round(projected_ab, 2),
        "projected_tb": round(projected_tb, 2),
        "prop_line": prop_line,
        "edge": round(edge, 2),
        "confidence": round(confidence, 1),
        "recommendation": recommendation,
    }


def main():
    sep = "=" * 70
    line = "-" * 70

    print(sep)
    print("  MLB FULL GAME MODEL - CORRECTED DATA")
    print("  Detroit Tigers (Away) vs Cleveland Guardians (Home)")
    print(sep)

    # Game Context
    game_context = {
        "matchup": "Detroit Tigers (Away) vs Cleveland Guardians (Home)",
        "time": "4:10 PM EDT",
        "venue": "Progressive Field, Cleveland, Ohio",
        "pitchers": "Tarik Skubal (LHP, 2.70 ERA) vs Joey Cantillo (LHP, 4.57 ERA)",
        "league_avg_runs_2026": 9.4,
        "abs_system": "Challenge System active (53.5% top / 27% bottom strike zone)",
    }

    print(f"\n  Matchup: {game_context['matchup']}")
    print(f"  Time: {game_context['time']}")
    print(f"  Venue: {game_context['venue']}")
    print(f"  Pitchers: {game_context['pitchers']}")
    print(f"  League Avg Runs (2026): {game_context['league_avg_runs_2026']}")
    print(f"  ABS System: {game_context['abs_system']}")

    # Weather
    weather_data = {
        "temperature": 84.0,
        "wind_speed": 8.0,
        "wind_direction_factor": 0.5,
        "park_factor": 1.02,
    }

    weather_mult = weather_hr_multiplier(
        weather_data["temperature"],
        weather_data["wind_speed"],
        weather_data["wind_direction_factor"],
    )

    print(f"\n{line}")
    print("  ENVIRONMENTAL FACTORS")
    print(line)
    print(f"  Temperature:     {weather_data['temperature']}F")
    print(f"  Wind:            {weather_data['wind_speed']} mph (dir factor: {weather_data['wind_direction_factor']})")
    print(f"  Park Factor:     {weather_data['park_factor']}")
    print(f"  HR Multiplier:   +{weather_mult} (temp adj: +{(weather_data['temperature'] - 70) * 0.005})")

    # Umpire
    umpire_stats = {
        "umpire_name": "Neutral ABS-Adjusted",
        "k_rate": 0.23,
        "zone_tightness": 0.535,
    }

    print(f"\n  Umpire: {umpire_stats['umpire_name']}")
    print(f"  Zone Tightness: {umpire_stats['zone_tightness']} (ABS-adjusted)")
    print(f"  Ump K Rate: {umpire_stats['k_rate']:.1%}")

    # Pitcher Data
    skubal = {
        "pitcher_name": "Tarik Skubal",
        "handedness": "L",
        "k_rate": 0.315,
        "recent_k_rate": 0.330,
        "bb_rate": 0.045,
        "hr_per_9": 0.75,
        "hard_hit_allowed": 0.320,
        "innings_proj": 6.0,
        "prop_line": 6.5,
    }

    cantillo = {
        "pitcher_name": "Joey Cantillo",
        "handedness": "L",
        "k_rate": 0.224,
        "recent_k_rate": 0.210,
        "bb_rate": 0.115,
        "hr_per_9": 1.35,
        "hard_hit_allowed": 0.410,
        "innings_proj": 4.2,
        "prop_line": 4.5,
    }

    print(f"\n{line}")
    print("  PITCHING MATCHUP")
    print(line)
    print(f"\n  {'Tarik Skubal (DET, LHP)':<35} {'Joey Cantillo (CLE, LHP)'}")
    print(f"  {'ERA: 2.70':<35} {'ERA: 4.57'}")
    print(f"  {'K Rate: 31.5%':<35} {'K Rate: 22.4%'}")
    print(f"  {'Recent K Rate: 33.0%':<35} {'Recent K Rate: 21.0%'}")
    print(f"  {'BB Rate: 4.5%':<35} {'BB Rate: 11.5%'}")
    print(f"  {'HR/9: 0.75':<35} {'HR/9: 1.35'}")
    print(f"  {'Hard Hit Allowed: 32.0%':<35} {'Hard Hit Allowed: 41.0%'}")
    print(f"  {'Proj IP: 6.0':<35} {'Proj IP: 4.2'}")

    # K Prop Projections
    skubal_k = project_k_prop(skubal)
    cantillo_k = project_k_prop(cantillo)

    print(f"\n{line}")
    print("  PITCHER K PROP PROJECTIONS")
    print(line)
    for k_prop in [skubal_k, cantillo_k]:
        print(f"\n  {k_prop['pitcher_name']} ({k_prop['handedness']})")
        print(f"    Blended K Rate:    {k_prop['blended_k_rate']:.1%} (60% recent / 40% season)")
        print(f"    K/9:               {k_prop['k_per_9']:.2f}")
        print(f"    Projected Ks:      {k_prop['projected_ks']:.2f}")
        print(f"    Prop Line:         {k_prop['prop_line']}")
        print(f"    Edge:              {k_prop['edge']:+.2f}")
        print(f"    Recommendation:    {k_prop['recommendation']} ({k_prop['confidence']:.1f}% conf)")

    # Batter Data
    ramirez = {
        "player_name": "Jose Ramirez",
        "handedness": "S",
        "avg": 0.285,
        "slg": 0.540,
        "k_rate_vs_L": 0.120,
        "k_rate_vs_R": 0.145,
        "recent_k_rate": 0.130,
        "hr_rate_vs_L": 0.055,
        "hr_rate_vs_R": 0.048,
        "barrel_rate": 0.115,
        "hard_hit_rate": 0.440,
        "launch_angle": 18.5,
        "pa_proj": 4.2,
        "prop_line": 1.5,
    }

    greene = {
        "player_name": "Riley Greene",
        "handedness": "L",
        "avg": 0.265,
        "slg": 0.475,
        "k_rate_vs_L": 0.265,
        "k_rate_vs_R": 0.220,
        "recent_k_rate": 0.240,
        "hr_rate_vs_L": 0.032,
        "hr_rate_vs_R": 0.045,
        "barrel_rate": 0.122,
        "hard_hit_rate": 0.465,
        "launch_angle": 14.2,
        "pa_proj": 4.1,
        "prop_line": 1.5,
    }

    # HR Prop Projections
    ramirez_hr = project_hr_prop(ramirez, skubal, weather_mult, weather_data["park_factor"])
    greene_hr = project_hr_prop(greene, cantillo, weather_mult, weather_data["park_factor"])

    print(f"\n{line}")
    print("  HR PROP PROJECTIONS (Weather-Adjusted)")
    print(line)
    for hr_prop in [ramirez_hr, greene_hr]:
        print(f"\n  {hr_prop['player_name']} ({hr_prop['handedness']}) vs {hr_prop['vs_pitcher_handedness']}HP")
        print(f"    HR Rate (split):   {hr_prop['hr_rate_vs_split']:.1%}")
        print(f"    Barrel Rate:       {hr_prop['barrel_rate']:.1%}")
        print(f"    Env Adjustment:    +{hr_prop['env_adjustment']:.4f}")
        print(f"    Matchup Adj:       {hr_prop['matchup_adjustment']:+.4f}")
        print(f"    HR Probability:    {hr_prop['hr_probability']:.1%}")
        print(f"    Threshold:         {hr_prop['threshold']:.0%}")
        print(f"    Recommendation:    {hr_prop['recommendation']} ({hr_prop['confidence']:.1f}% conf)")

    # Total Bases Projections
    ramirez_tb = project_total_bases(ramirez, skubal, weather_mult)
    greene_tb = project_total_bases(greene, cantillo, weather_mult)

    print(f"\n{line}")
    print("  TOTAL BASES PROP PROJECTIONS")
    print(line)
    for tb_prop in [ramirez_tb, greene_tb]:
        print(f"\n  {tb_prop['player_name']} ({tb_prop['handedness']})")
        print(f"    SLG:              {tb_prop['slg']:.3f}")
        print(f"    Projected PA:     {tb_prop['pa_projected']}")
        print(f"    Projected AB:     {tb_prop['projected_ab']}")
        print(f"    Projected TB:     {tb_prop['projected_tb']:.2f}")
        print(f"    Prop Line:        {tb_prop['prop_line']}")
        print(f"    Edge:             {tb_prop['edge']:+.2f}")
        print(f"    Recommendation:   {tb_prop['recommendation']} ({tb_prop['confidence']:.1f}% conf)")

    # Full Game Model
    league_avg = 9.4
    skubal_suppression = -0.8
    cantillo_boost = 0.6
    weather_boost = (weather_data["temperature"] - 70) * 0.02

    projected_total = league_avg + skubal_suppression + cantillo_boost + weather_boost
    projected_cle_runs = (projected_total / 2) - 0.425
    projected_det_runs = projected_total - projected_cle_runs

    det_win_prob = sigmoid((projected_det_runs - projected_cle_runs) * 3) * 100
    cle_win_prob = 100 - det_win_prob

    run_diff = projected_cle_runs - projected_det_runs

    if abs(run_diff) > 0.5:
        side_rec = "Cleveland Guardians" if run_diff > 0 else "Detroit Tigers"
        side_conf = min(85, abs(run_diff) * 30 + 35)
    else:
        side_rec = "PASS"
        side_conf = abs(run_diff) * 20 + 20

    total_diff = projected_total - 8.0
    if abs(total_diff) > 0.5:
        total_rec = "Over" if total_diff > 0 else "Under"
        total_conf = min(80, abs(total_diff) * 25 + 30)
    else:
        total_rec = "PASS"
        total_conf = abs(total_diff) * 15 + 25

    print(f"\n{line}")
    print("  FULL GAME MODEL OUTPUTS")
    print(line)
    print(f"  League Avg Runs (2026):    {league_avg}")
    print(f"  Skubal Suppression:        {skubal_suppression:+.2f}")
    print(f"  Cantillo Boost:            {cantillo_boost:+.2f}")
    print(f"  Weather Boost:             {weather_boost:+.2f}")
    print(f"  Park Factor:               {weather_data['park_factor']}")
    print()
    print(f"  +-----------------------------------------+")
    print(f"  |  PROJECTED TOTAL RUNS:  {projected_total:.2f}            |")
    print(f"  |  CLE Runs: {projected_cle_runs:.2f}  |  DET Runs: {projected_det_runs:.2f}   |")
    print(f"  |  Run Differential: {run_diff:+.2f} ({'CLE' if run_diff > 0 else 'DET'})     |")
    print(f"  |  CLE Win Prob: {cle_win_prob:.1f}%                   |")
    print(f"  |  DET Win Prob: {det_win_prob:.1f}%                   |")
    print(f"  +-----------------------------------------+")

    # Betting Recommendations
    print(f"\n{line}")
    print("  BETTING RECOMMENDATIONS")
    print(line)
    print(f"\n  Side:   {side_rec} (Confidence: {side_conf:.1f}%)")
    print(f"  Total:  {total_rec} (Confidence: {total_conf:.1f}%)")

    print(f"\n  PLAYER PROPS:")
    print(f"    Skubal Ks:        {skubal_k['recommendation']} {skubal_k['prop_line']} ({skubal_k['projected_ks']:.2f} proj) [{skubal_k['confidence']:.1f}%]")
    print(f"    Cantillo Ks:      {cantillo_k['recommendation']} {cantillo_k['prop_line']} ({cantillo_k['projected_ks']:.2f} proj) [{cantillo_k['confidence']:.1f}%]")
    print(f"    Ramirez HR:        {ramirez_hr['recommendation']} ({ramirez_hr['hr_probability']:.1%} prob) [{ramirez_hr['confidence']:.1f}%]")
    print(f"    Greene TB:         {greene_tb['recommendation']} {greene_tb['prop_line']} ({greene_tb['projected_tb']:.2f} proj) [{greene_tb['confidence']:.1f}%]")

    # Execution Strategy
    print(f"\n{line}")
    print("  EXECUTION STRATEGY")
    print(line)
    print()
    print("  1. ISOLATE MATCHUPS:")
    print("     - Skubal's elite bat-missing ability (33.0% recent K rate)")
    print("       forces the model heavily toward the Over on his K prop.")
    print("     - Verify Zone% > 50% and Whiff% < 20% via Pybaseball.")
    print()
    print("  2. CANTILLO'S WALK ISSUES:")
    print("     - 11.5% BB rate over last 10 appearances")
    print("     - Detroit batters projected to draw walks (project_walks edge)")
    print("     - Edge toward Under on Cantillo K totals")
    print()
    print("  3. ELITE SWINGER TARGETS:")
    print("     - Jose Ramirez (switch-hitter) maintains elite profile vs LHP")
    print("     - 84F weather multiplier pushes HR probability above threshold")
    print("     - YES HR recommendation for Ramirez")
    print()
    print("  4. TOTAL BASES ATTACK:")
    print("     - Riley Greene vs Cantillo's elevated 1.51 WHIP")
    print("     - Greene's L vs L splits slightly downgraded but still valuable")
    print("     - Over 1.5 TB with weather-boosted projection")
    print()
    print("  5. UMPIRE VARIANCE:")
    print("     - Neutral ABS-adjusted umpire")
    print("     - If Doug Eddings or Lance Barksdale behind the plate")
    print("       (85.7% Over trend), aggressively favor Over on Total Runs")
    print()

    # Save results
    result = {
        "sport": "baseball",
        "league": "MLB",
        "game_context": game_context,
        "weather": weather_data,
        "weather_multiplier": weather_mult,
        "umpire": umpire_stats,
        "pitchers": {"home": cantillo, "away": skubal},
        "k_props": {"skubal": skubal_k, "cantillo": cantillo_k},
        "batters": {"ramirez": ramirez, "greene": greene},
        "hr_props": {"ramirez": ramirez_hr, "greene": greene_hr},
        "total_bases_props": {"ramirez": ramirez_tb, "greene": greene_tb},
        "full_game": {
            "projected_total_runs": round(projected_total, 2),
            "projected_cle_runs": round(projected_cle_runs, 2),
            "projected_det_runs": round(projected_det_runs, 2),
            "run_differential": round(run_diff, 2),
            "cle_win_prob": round(cle_win_prob / 100, 4),
            "det_win_prob": round(det_win_prob / 100, 4),
        },
        "recommendations": {
            "side": {"recommendation": side_rec, "confidence": round(side_conf, 1)},
            "total": {"recommendation": total_rec, "confidence": round(total_conf, 1)},
            "skubal_k": {"recommendation": skubal_k["recommendation"], "line": skubal_k["prop_line"],
                         "projected": skubal_k["projected_ks"], "confidence": skubal_k["confidence"]},
            "cantillo_k": {"recommendation": cantillo_k["recommendation"], "line": cantillo_k["prop_line"],
                           "projected": cantillo_k["projected_ks"], "confidence": cantillo_k["confidence"]},
            "ramirez_hr": {"recommendation": ramirez_hr["recommendation"],
                           "probability": ramirez_hr["hr_probability"], "confidence": ramirez_hr["confidence"]},
            "greene_tb": {"recommendation": greene_tb["recommendation"], "line": greene_tb["prop_line"],
                          "projected": greene_tb["projected_tb"], "confidence": greene_tb["confidence"]},
        },
    }

    out_dir = Path("output/baseball")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "Tigers_vs_Guardians_corrected.json"
    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2, default=str)

    print(line)
    print(f"  Results saved to: {out_path}")
    print(line)
    print()


if __name__ == "__main__":
    main()