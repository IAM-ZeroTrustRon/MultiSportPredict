#!/usr/bin/env python
"""Houston Astros vs Kansas City Royals - Full Game Model"""
import json, math, sys, io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

def sigmoid(x):
    x = max(-500, min(500, x))
    return 1 / (1 + math.exp(-x))

def weather_mult(t, ws=0, wdf=0):
    return round((t - 70) * 0.005 + ws * wdf * 0.01, 4)

def project_k_prop(name, hand, k9, proj_ip, line):
    k_rate = k9 / 27.0
    pk = k_rate
    bk = 0.6 * pk + 0.4 * k_rate
    bk9 = bk * 9
    pk_proj = (bk9 / 9) * proj_ip
    edge = pk_proj - line
    rec = "Over" if edge > 0.3 else ("Under" if edge < -0.3 else "PASS")
    conf = min(95, abs(edge) * 20 + 30)
    return {"name": name, "hand": hand, "bk9": round(bk9, 2), "proj_ks": round(pk_proj, 2),
            "line": line, "edge": round(edge, 2), "conf": round(conf, 1), "rec": rec}

def project_hr(name, hand, hr_rate, barrel, vs_hand, wm, pf):
    env = wm + (pf - 1.0) * 0.5
    match = (barrel - 0.08) * 2.0
    raw = hr_rate + env + match
    prob = sigmoid(raw * 5)
    rec = "Yes HR" if prob > 0.12 else "No"
    conf = min(95, abs(prob - 0.12) * 200 + 40)
    return {"name": name, "hand": hand, "vs": vs_hand, "hr_split": round(hr_rate, 4),
            "barrel": barrel, "env": round(env, 4), "match": round(match, 4),
            "prob": round(prob, 4), "conf": round(conf, 1), "rec": rec}

def main():
    S = "=" * 70
    L = "-" * 70
    print(S)
    print("  MLB FULL GAME MODEL - HOUSTON ASTROS vs KANSAS CITY ROYALS")
    print(S)
    print("\n  Matchup: Houston Astros (Away) vs Kansas City Royals (Home)")
    print("  Time: 7:10 PM EDT | Venue: Kauffman Stadium, Kansas City, MO")
    print("  Records: Astros 32-39, Royals 28-42 (3-game losing streak)")

    print(f"\n{L}\n  TEAM METRICS\n{L}")
    print("  ASTROS: 4.5 R/G | .243 BA | .726 OPS | 80 HR | 4.98 ERA | 1.44 WHIP")
    print("  ROYALS: 4.0 R/G | .240 BA | .686 OPS | 56 HR | 4.47 ERA | 1.38 WHIP")

    wm = weather_mult(82.0, 10.0, 0.4)
    print(f"\n{L}\n  ENVIRONMENTAL FACTORS\n{L}")
    print(f"  Temp: 82F | Wind: 10 mph | Park Factor: 1.0 | HR Mult: +{wm}")

    print(f"\n{L}\n  PITCHING MATCHUP\n{L}")
    print("  Mike Burrows (HOU, RHP)          Noah Cameron (KC, LHP)")
    print("  Record: 3-8                       Record: 3-4")
    print("  ERA: 5.77  WHIP: 1.57             ERA: 3.84  WHIP: 1.19")
    print("  K/9: 7.4  (60K / 73.1 IP)         K/9: 8.6  (63K / 65.2 IP)")
    print("  Hard Hit Allowed: 42.0%            Hard Hit Allowed: 35.0%")

    # K Props
    bk = project_k_prop("Mike Burrows", "R", 7.4, 5.5, 5.5)
    ck = project_k_prop("Noah Cameron", "L", 8.6, 5.8, 5.5)
    print(f"\n{L}\n  PITCHER K PROP PROJECTIONS\n{L}")
    for p in [bk, ck]:
        print(f"\n  {p['name']} ({p['hand']})")
        print(f"    Blended K/9: {p['bk9']:.2f} | Proj Ks: {p['proj_ks']:.2f} | Line: {p['line']}")
        print(f"    Edge: {p['edge']:+.2f} | Recommendation: {p['rec']} ({p['conf']:.1f}%)")

    # HR Props
    wk = project_hr("Christian Walker", "R", 0.052, 0.130, "L", wm, 1.0)
    bw = project_hr("Bobby Witt Jr.", "R", 0.048, 0.105, "R", wm, 1.0)
    sp = project_hr("Salvador Perez", "R", 0.045, 0.110, "R", wm, 1.0)
    print(f"\n{L}\n  HR PROP TARGETS\n{L}")
    for h in [wk, bw, sp]:
        print(f"\n  {h['name']} ({h['hand']}) vs {h['vs']}HP")
        print(f"    HR Split: {h['hr_split']:.1%} | Barrel: {h['barrel']:.1%}")
        print(f"    Env: +{h['env']:.4f} | Matchup: {h['match']:+.4f}")
        print(f"    HR Probability: {h['prob']:.1%} | Recommendation: {h['rec']} ({h['conf']:.1f}%)")

    # Full Game Model
    burrows_era_impact = (5.77 - 4.5) * 0.3  # +0.38
    cameron_era_impact = (4.5 - 3.84) * 0.2   # -0.13
    wx = (82 - 70) * 0.015                     # +0.18
    lhp_boost = 0.2

    hou_r = 4.0 + cameron_era_impact + wx + lhp_boost
    kc_r = 4.0 + burrows_era_impact + wx
    total = hou_r + kc_r
    diff = hou_r - kc_r
    hou_wp = sigmoid(diff * 3) * 100
    kc_wp = 100 - hou_wp

    side_rec = "Houston Astros" if diff > 0.5 else ("Kansas City Royals" if diff < -0.5 else "PASS")
    side_conf = min(85, abs(diff) * 30 + 35) if abs(diff) > 0.5 else 20
    tot_diff = total - 9.5
    tot_rec = "Over" if tot_diff > 0.5 else ("Under" if tot_diff < -0.5 else "PASS")
    tot_conf = min(80, abs(tot_diff) * 25 + 30) if abs(tot_diff) > 0.5 else 25

    print(f"\n{L}\n  FULL GAME MODEL OUTPUTS\n{L}")
    print(f"  Burrows ERA Impact:  +{burrows_era_impact:.2f}")
    print(f"  Cameron Impact:      {cameron_era_impact:+.2f}")
    print(f"  Weather Boost:       +{wx:.2f}")
    print(f"  Astros LHP Boost:    +{lhp_boost:.2f}")
    print(f"\n  +--------------------------------------------+")
    print(f"  |  PROJECTED TOTAL RUNS:  {total:.2f}              |")
    print(f"  |  HOU Runs: {hou_r:.2f}  |  KC Runs: {kc_r:.2f}         |")
    print(f"  |  Run Diff: {diff:+.2f} ({'HOU' if diff > 0 else 'KC'})                    |")
    print(f"  |  HOU Win Prob: {hou_wp:.1f}%                   |")
    print(f"  |  KC Win Prob:  {kc_wp:.1f}%                   |")
    print(f"  +--------------------------------------------+")

    print(f"\n{L}\n  MARKET CONTEXT\n{L}")
    print("  ML: Royals -125 | Astros +105")
    print("  RL: Astros +1.5 (-190) | Royals -1.5 (+155)")
    print("  O/U: 9.5 | Astros RL Record: 33-38")

    print(f"\n{L}\n  BETTING RECOMMENDATIONS\n{L}")
    print(f"  Side:   {side_rec} ({side_conf:.1f}%)")
    print(f"  Total:  {tot_rec} ({tot_conf:.1f}%)")
    print(f"\n  PLAYER PROPS:")
    print(f"    Burrows Ks: {bk['rec']} {bk['line']} ({bk['proj_ks']:.2f}) [{bk['conf']:.1f}%]")
    print(f"    Cameron Ks: {ck['rec']} {ck['line']} ({ck['proj_ks']:.2f}) [{ck['conf']:.1f}%]")
    print(f"    Walker HR:  {wk['rec']} ({wk['prob']:.1%}) [{wk['conf']:.1f}%]")
    print(f"    Witt HR:    {bw['rec']} ({bw['prob']:.1%}) [{bw['conf']:.1f}%]")
    print(f"    Perez HR:   {sp['rec']} ({sp['prob']:.1%}) [{sp['conf']:.1f}%]")

    print(f"\n{L}\n  EXECUTION STRATEGY\n{L}")
    print("  1. Burrows (5.77 ERA, 1.57 WHIP) is hittable. Attack with")
    print("     KC power hitters Witt Jr and Perez for HR props.")
    print("  2. Cameron (3.84 ERA, 1.19 WHIP) is solid but Astros hit")
    print("     LHP well. Walker is top HR target at +350.")
    print("  3. Both pitchers have moderate K rates. Under on K props")
    print("     for Burrows; Cameron closer to push at 5.5 line.")
    print("  4. Total at 9.5 with two shaky starters -> lean Over.")
    print("  5. Check umpire for Over/Under variance.\n")

    # Save
    result = {
        "sport": "baseball", "league": "MLB",
        "game": {"away": "Houston Astros", "home": "Kansas City Royals", "time": "7:10 PM EDT",
                 "venue": "Kauffman Stadium", "records": "HOU 32-39, KC 28-42"},
        "weather": {"temp": 82, "wind": 10, "mult": wm},
        "pitchers": {"hou": {"name": "Mike Burrows", "era": 5.77, "whip": 1.57, "k9": 7.4},
                     "kc": {"name": "Noah Cameron", "era": 3.84, "whip": 1.19, "k9": 8.6}},
        "k_props": {"burrows": bk, "cameron": ck},
        "hr_props": {"walker": wk, "witt": bw, "perez": sp},
        "model": {"total_runs": round(total, 2), "hou_runs": round(hou_r, 2), "kc_runs": round(kc_r, 2),
                  "diff": round(diff, 2), "hou_win": round(hou_wp/100, 4), "kc_win": round(kc_wp/100, 4)},
        "recommendations": {"side": side_rec, "total": tot_rec},
    }
    out = Path("output/baseball")
    out.mkdir(parents=True, exist_ok=True)
    fp = out / "Astros_vs_Royals.json"
    with open(fp, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"  Results saved to: {fp}\n")

if __name__ == "__main__":
    main()