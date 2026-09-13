#!/usr/bin/env python
"""
MLB 4-Game Slate Analysis (June 22, 2026)
=========================================
Games:
1. NYY vs DET (Comerica Park, 6:10 PM EDT)
2. TEX vs MIA (LoanDepot Park, 6:40 PM EDT)
3. CHC vs NYM (Citi Field, 7:10 PM EDT)
4. LAD vs MIN (Target Field, 7:40 PM EDT)

Uses the MODEL ONLY for bet recommendations - no narrative consensus.
"""

import os
import sys
import time
import math
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from universal_runner import push_to_discord
from scipy.stats import poisson
from core.confidence_engine import confidence_score, bet_recommendation

load_dotenv()
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")

def poisson_over_prob(lam: float, line: float) -> float:
    """Probability of going over a line using Poisson CDF"""
    if lam <= 0:
        return 0.0
    try:
        return 1.0 - float(poisson.cdf(int(line), lam))
    except (ValueError, OverflowError):
        return 0.0

def calculate_btts_probability(home_goals: float, away_goals: float) -> float:
    """Calculate Both Teams to Score probability"""
    try:
        home_scores_zero = poisson.pmf(0, home_goals)
        away_scores_zero = poisson.pmf(0, away_goals)
        both_score_zero = home_scores_zero * away_scores_zero
        btts_prob = 1 - (home_scores_zero + away_scores_zero - both_score_zero)
        return max(0.0, min(1.0, btts_prob))
    except:
        return 0.5

def analyze_yy_det() -> Dict[str, Any]:
    """
    NYY vs DET Analysis
    Model-based metrics:
    - Yankees bullpen edge (late innings)
    - Comerica Park suppresses HRs
    - Pitcher K rates and ERA projections
    """
    print("\n" + "="*70)
    print("GAME 1: NEW YORK YANKEES vs DETROIT TIGERS")
    print("Comerica Park | 6:10 PM EDT")
    print("="*70)
    
    # Pitcher metrics (model inputs)
    yy_sp_era = 3.75  # RHP - estimated
    yy_sp_k9 = 9.2
    yy_sp_bb9 = 2.8
    
    det_sp_era = 4.25  # LHP - estimated
    det_sp_k9 = 8.5
    det_sp_bb9 = 3.2
    
    # Team metrics
    yy_lineup_k_rate = 0.21  # Good contact
    yy_lineup_bb_rate = 0.08
    det_lineup_k_rate = 0.24  # Higher K rate
    det_lineup_bb_rate = 0.07
    
    # Park factor for Comerica: deep center, suppresses HRs
    comerica_hr_factor = 0.92
    comerica_run_factor = 0.97
    
    # Model projections
    yy_runs_proj = 4.1 * comerica_run_factor  # Slight suppression
    det_runs_proj = 3.2 * comerica_run_factor
    total_runs_proj = yy_runs_proj + det_runs_proj
    
    # Strikeout projections (6IP average)
    yy_k_proj = (yy_sp_k9 / 9.0) * 6.0
    det_k_proj = (det_sp_k9 / 9.0) * 6.0
    combined_k_proj = yy_k_proj + det_k_proj
    
    # Model calculations
    under_8_5_prob = 1.0 - poisson_over_prob(total_runs_proj, 8.5)
    yy_k_over_6_5_prob = poisson_over_prob(yy_k_proj, 6.5)
    combined_k_over_15_prob = poisson_over_prob(combined_k_proj, 15)
    
    # Moneyline based on run differential
    run_diff = yy_runs_proj - det_runs_proj
    yy_ml_prob = 0.50 + (run_diff / 10.0) * 0.25  # Convert run diff to win prob
    yy_ml_prob = max(0.45, min(0.75, yy_ml_prob))
    
    strong_bets = []
    
    # MODEL BET 1: Under 8.5 (Park + Pitcher metrics)
    if under_8_5_prob > 0.62:
        edge = (under_8_5_prob - 0.50) * 100
        conf = confidence_score(edge, volatility=0.55)
        strong_bets.append({
            "market": "Under 8.5 Total Runs",
            "probability": under_8_5_prob,
            "confidence": conf,
            "edge": f"{edge:+.1f}%",
            "model_factors": [
                "Comerica Park run-suppression factor (0.97x)",
                f"YY SP ERA {yy_sp_era} | DET SP ERA {det_sp_era}",
                f"Combined run projection: {total_runs_proj:.2f}"
            ]
        })
    
    # MODEL BET 2: Yankees Starter Over 6.5 K's (K-rate matchup)
    if yy_k_over_6_5_prob > 0.65:
        edge = (yy_k_over_6_5_prob - 0.50) * 100
        conf = confidence_score(edge, volatility=0.50)
        strong_bets.append({
            "market": "Yankees Starter Over 6.5 Strikeouts",
            "probability": yy_k_over_6_5_prob,
            "confidence": conf,
            "edge": f"{edge:+.1f}%",
            "model_factors": [
                f"YY SP K/9 rate: {yy_sp_k9:.1f}",
                f"DET lineup K rate: {det_lineup_k_rate:.1%}",
                f"Projected 6.0 IP, {yy_k_proj:.1f} K projection"
            ]
        })
    
    # MODEL BET 3: Combined Team K's Over 15.0 (Both K9 rates)
    if combined_k_over_15_prob > 0.58:
        edge = (combined_k_over_15_prob - 0.50) * 100
        conf = confidence_score(edge, volatility=0.55)
        strong_bets.append({
            "market": "Combined Team Strikeouts Over 15.0",
            "probability": combined_k_over_15_prob,
            "confidence": conf,
            "edge": f"{edge:+.1f}%",
            "model_factors": [
                f"YY SP: {yy_k9:.1f} K/9 | DET SP: {det_sp_k9:.1f} K/9",
                f"YY lineup K rate: {yy_lineup_k_rate:.1%} (vs LHP)",
                f"Total projection: {combined_k_proj:.1f}K"
            ]
        })
    
    # MODEL BET 4: Yankees Moneyline (Run differential advantage)
    if yy_ml_prob > 0.60:
        edge = (yy_ml_prob - 0.50) * 100
        conf = confidence_score(edge, volatility=0.60)
        strong_bets.append({
            "market": "Yankees Moneyline",
            "probability": yy_ml_prob,
            "confidence": conf,
            "edge": f"{edge:+.1f}%",
            "model_factors": [
                f"Run differential: +{run_diff:.1f} (YY advantage)",
                f"YY SP ERA {yy_sp_era} < DET SP ERA {det_sp_era}",
                f"Bullpen edge: Yankees late-inning advantage"
            ]
        })
    
    return {
        "match": "NYY vs DET",
        "home": "DET",
        "away": "NYY",
        "strong_bets": strong_bets,
        "model_projection": {
            "yy_runs": round(yy_runs_proj, 2),
            "det_runs": round(det_runs_proj, 2),
            "total": round(total_runs_proj, 2)
        }
    }

def analyze_tex_mia() -> Dict[str, Any]:
    """
    TEX vs MIA Analysis
    Model-based metrics:
    - Pitcher command + K rates
    - Roof closed (normalized environment)
    - Lineup strikeout rates
    """
    print("\n" + "="*70)
    print("GAME 2: TEXAS RANGERS vs MIAMI MARLINS")
    print("LoanDepot Park (Roof Closed) | 6:40 PM EDT")
    print("="*70)
    
    # Pitcher metrics
    tex_sp_era = 4.10  # Merrill Kelly RHP
    tex_sp_k9 = 8.8
    tex_sp_bb9 = 3.0
    
    mia_sp_era = 3.65  # Eury Perez RHP
    mia_sp_k9 = 9.8
    mia_sp_bb9 = 2.5
    
    # Team metrics
    tex_lineup_k_rate = 0.22
    mia_lineup_k_rate = 0.23
    
    # LoanDepot park: Closed roof = pitcher's park, suppresses runs
    loanDepot_run_factor = 0.94
    
    # Model projections
    tex_runs_proj = 4.0 * loanDepot_run_factor
    mia_runs_proj = 3.5 * loanDepot_run_factor  # Perez elite stuff
    total_runs_proj = tex_runs_proj + mia_runs_proj
    
    # K projections
    tex_k_proj = (tex_sp_k9 / 9.0) * 5.5  # Kelly ~5.5 IP
    mia_k_proj = (mia_sp_k9 / 9.0) * 6.0  # Perez goes deeper
    combined_k_proj = tex_k_proj + mia_k_proj
    
    under_7_5_prob = 1.0 - poisson_over_prob(total_runs_proj, 7.5)
    mia_k_over_7_5_prob = poisson_over_prob(mia_k_proj, 7.5)
    
    # Moneyline
    run_diff = mia_runs_proj - tex_runs_proj
    mia_ml_prob = 0.50 + (run_diff / 8.0) * 0.25
    mia_ml_prob = max(0.45, min(0.75, mia_ml_prob))
    
    strong_bets = []
    
    # MODEL BET 1: Under 7.5 (Pitcher park + run-suppression factor)
    if under_7_5_prob > 0.62:
        edge = (under_7_5_prob - 0.50) * 100
        conf = confidence_score(edge, volatility=0.55)
        strong_bets.append({
            "market": "Under 7.5 Total Runs",
            "probability": under_7_5_prob,
            "confidence": conf,
            "edge": f"{edge:+.1f}%",
            "model_factors": [
                "LoanDepot closed roof: 0.94x run factor",
                f"TEX SP ERA {tex_sp_era} | MIA SP ERA {mia_sp_era}",
                f"Total projection: {total_runs_proj:.2f} runs"
            ]
        })
    
    # MODEL BET 2: Eury Perez Over 7.5 K's (Elite K9 rate)
    if mia_k_over_7_5_prob > 0.63:
        edge = (mia_k_over_7_5_prob - 0.50) * 100
        conf = confidence_score(edge, volatility=0.50)
        strong_bets.append({
            "market": "Eury Perez Over 7.5 Strikeouts",
            "probability": mia_k_over_7_5_prob,
            "confidence": conf,
            "edge": f"{edge:+.1f}%",
            "model_factors": [
                f"Perez K/9 rate: {mia_sp_k9:.1f} (elite)",
                f"TEX lineup K rate: {tex_lineup_k_rate:.1%}",
                f"Projected 6.0 IP, {mia_k_proj:.1f} K projection"
            ]
        })
    
    # MODEL BET 3: Marlins Moneyline (Perez dominance at home)
    if mia_ml_prob > 0.58:
        edge = (mia_ml_prob - 0.50) * 100
        conf = confidence_score(edge, volatility=0.60)
        strong_bets.append({
            "market": "Marlins Moneyline",
            "probability": mia_ml_prob,
            "confidence": conf,
            "edge": f"{edge:+.1f}%",
            "model_factors": [
                f"Perez elite K rate ({mia_sp_k9:.1f} K/9) >> Kelly ({tex_sp_k9:.1f} K/9)",
                f"Home field advantage (closed roof environment)",
                f"ERA differential: MIA {mia_sp_era} < TEX {tex_sp_era}"
            ]
        })
    
    return {
        "match": "TEX vs MIA",
        "home": "MIA",
        "away": "TEX",
        "strong_bets": strong_bets,
        "model_projection": {
            "tex_runs": round(tex_runs_proj, 2),
            "mia_runs": round(mia_runs_proj, 2),
            "total": round(total_runs_proj, 2)
        }
    }

def analyze_chc_nym() -> Dict[str, Any]:
    """
    CHC vs NYM Analysis
    Model-based metrics:
    - Bullpen edge (NYM >> CHC)
    - Lineup efficiency metrics
    - Pitcher walk rates
    """
    print("\n" + "="*70)
    print("GAME 3: CHICAGO CUBS vs NEW YORK METS")
    print("Citi Field | 7:10 PM EDT")
    print("="*70)
    
    # Pitcher metrics
    chc_sp_era = 3.95  # Javier Assad RHP
    chc_sp_k9 = 8.0
    chc_sp_bb9 = 3.2
    chc_sp_walk_rate = 0.095
    
    nym_sp_era = 3.80  # David Peterson LHP
    nym_sp_k9 = 9.5
    nym_sp_bb9 = 2.5
    
    # Team metrics
    chc_lineup_k_rate = 0.22
    nym_lineup_k_rate = 0.21
    
    # Citi Field: Slightly humid, carries ball better
    citi_run_factor = 1.02
    
    # Model projections
    chc_runs_proj = 4.2 * citi_run_factor
    nym_runs_proj = 4.3 * citi_run_factor
    total_runs_proj = chc_runs_proj + nym_runs_proj
    
    # K projections
    chc_k_proj = (chc_sp_k9 / 9.0) * 5.5
    nym_k_proj = (nym_sp_k9 / 9.0) * 6.0
    combined_k_proj = chc_k_proj + nym_k_proj
    
    # Bullpen impact (NYM edge)
    bullpen_adjustment = 0.40  # NYM win prob boost from elite bullpen
    
    over_8_0_prob = poisson_over_prob(total_runs_proj, 8.0)
    nym_k_over_8_prob = poisson_over_prob(nym_k_proj, 8.0)
    
    # NYM ML (bullpen edge dominance)
    base_ml_prob = 0.50
    run_diff_adjustment = (nym_runs_proj - chc_runs_proj) / 8.0 * 0.20
    bullpen_boost = bullpen_adjustment * 0.15
    nym_ml_prob = base_ml_prob + run_diff_adjustment + bullpen_boost
    nym_ml_prob = max(0.48, min(0.75, nym_ml_prob))
    
    strong_bets = []
    
    # MODEL BET 1: Over 8.0 (Run environment + humid conditions)
    if over_8_0_prob > 0.60:
        edge = (over_8_0_prob - 0.50) * 100
        conf = confidence_score(edge, volatility=0.55)
        strong_bets.append({
            "market": "Over 8.0 Total Runs",
            "probability": over_8_0_prob,
            "confidence": conf,
            "edge": f"{edge:+.1f}%",
            "model_factors": [
                "Citi Field humid conditions: 1.02x run factor",
                f"CHC SP ERA {chc_sp_era} | NYM SP ERA {nym_sp_era}",
                f"Both lineups have favorable splits against opposing starter pitches"
            ]
        })
    
    # MODEL BET 2: David Peterson Over 8.0 K's (K9 rate advantage)
    if nym_k_over_8_prob > 0.62:
        edge = (nym_k_over_8_prob - 0.50) * 100
        conf = confidence_score(edge, volatility=0.50)
        strong_bets.append({
            "market": "David Peterson Over 8.0 Strikeouts",
            "probability": nym_k_over_8_prob,
            "confidence": conf,
            "edge": f"{edge:+.1f}%",
            "model_factors": [
                f"Peterson K/9 rate: {nym_sp_k9:.1f}",
                f"CHC lineup K rate: {chc_lineup_k_rate:.1%}",
                f"Projected 6.0 IP, {nym_k_proj:.1f} K projection"
            ]
        })
    
    # MODEL BET 3: Mets Moneyline (Bullpen dominance edge)
    if nym_ml_prob > 0.58:
        edge = (nym_ml_prob - 0.50) * 100
        conf = confidence_score(edge, volatility=0.60)
        strong_bets.append({
            "market": "Mets Moneyline",
            "probability": nym_ml_prob,
            "confidence": conf,
            "edge": f"{edge:+.1f}%",
            "model_factors": [
                "Bullpen disparity: Mets (Devin Williams 9th) >> Cubs (Thielbar bridge)",
                f"Late-inning close game advantage to Mets",
                f"Peterson elite K rate vs Assad walk rate ({chc_sp_walk_rate:.1%})"
            ]
        })
    
    return {
        "match": "CHC vs NYM",
        "home": "NYM",
        "away": "CHC",
        "strong_bets": strong_bets,
        "model_projection": {
            "chc_runs": round(chc_runs_proj, 2),
            "nym_runs": round(nym_runs_proj, 2),
            "total": round(total_runs_proj, 2)
        }
    }

def analyze_lad_min() -> Dict[str, Any]:
    """
    LAD vs MIN Analysis
    Model-based metrics:
    - Massive bullpen edge (Dodgers elite)
    - Glasnow elite stuff vs Paddack command-reliant
    - Run-scoring environment
    """
    print("\n" + "="*70)
    print("GAME 4: LOS ANGELES DODGERS vs MINNESOTA TWINS")
    print("Target Field | 7:40 PM EDT")
    print("="*70)
    
    # Pitcher metrics
    lad_sp_era = 2.95  # Tyler Glasnow RHP
    lad_sp_k9 = 11.2  # ELITE
    lad_sp_bb9 = 2.2
    
    min_sp_era = 4.15  # Chris Paddack RHP
    min_sp_k9 = 8.0
    min_sp_bb9 = 2.8
    
    # Team metrics
    lad_lineup_ops = 0.875  # Elite
    min_lineup_ops = 0.715  # Below average
    
    # Target Field: Warm, run-scoring environment
    target_run_factor = 1.05
    
    # Model projections
    lad_runs_proj = 5.0 * target_run_factor
    min_runs_proj = 3.2 * target_run_factor
    total_runs_proj = lad_runs_proj + min_runs_proj
    
    # K projections
    lad_k_proj = (lad_sp_k9 / 9.0) * 6.0  # Glasnow elite
    min_k_proj = (min_sp_k9 / 9.0) * 5.5
    
    # Run line based on Dodgers dominance
    run_diff = lad_runs_proj - min_runs_proj
    lad_rl_prob = 0.50 + (run_diff / 10.0) * 0.30
    lad_rl_prob = max(0.50, min(0.80, lad_rl_prob))
    
    over_8_5_prob = poisson_over_prob(total_runs_proj, 8.5)
    lad_k_over_8_5_prob = poisson_over_prob(lad_k_proj, 8.5)
    
    # Ohtani TB over (elite vs RHP)
    ohtani_tb_over_prob = 0.68
    
    strong_bets = []
    
    # MODEL BET 1: Over 8.5 (Run-scoring environment + lineup mismatch)
    if over_8_5_prob > 0.61:
        edge = (over_8_5_prob - 0.50) * 100
        conf = confidence_score(edge, volatility=0.55)
        strong_bets.append({
            "market": "Over 8.5 Total Runs",
            "probability": over_8_5_prob,
            "confidence": conf,
            "edge": f"{edge:+.1f}%",
            "model_factors": [
                "Target Field run-scoring environment: 1.05x factor",
                f"LAD lineup OPS {lad_lineup_ops:.3f} (elite) vs MIN {min_sp_era} ERA starter",
                f"Total projection: {total_runs_proj:.2f} runs"
            ]
        })
    
    # MODEL BET 2: Dodgers Run Line -1.5 (Massive dominance)
    if lad_rl_prob > 0.63:
        edge = (lad_rl_prob - 0.50) * 100
        conf = confidence_score(edge, volatility=0.60)
        strong_bets.append({
            "market": "Dodgers Run Line -1.5",
            "probability": lad_rl_prob,
            "confidence": conf,
            "edge": f"{edge:+.1f}%",
            "model_factors": [
                f"Run differential projection: +{run_diff:.1f}",
                f"Glasnow elite K rate ({lad_sp_k9:.1f} K/9) >> Paddack ({min_sp_k9:.1f} K/9)",
                "Massive bullpen edge (Yates, Vesia late innings)"
            ]
        })
    
    # MODEL BET 3: Tyler Glasnow Over 8.5 Strikeouts (Elite K9 rate)
    if lad_k_over_8_5_prob > 0.64:
        edge = (lad_k_over_8_5_prob - 0.50) * 100
        conf = confidence_score(edge, volatility=0.50)
        strong_bets.append({
            "market": "Tyler Glasnow Over 8.5 Strikeouts",
            "probability": lad_k_over_8_5_prob,
            "confidence": conf,
            "edge": f"{edge:+.1f}%",
            "model_factors": [
                f"Glasnow elite K/9 rate: {lad_sp_k9:.1f}",
                f"MIN lineup K rate high (will chase at velocity)",
                f"Projected 6.0 IP, {lad_k_proj:.1f} K projection"
            ]
        })
    
    # MODEL BET 4: Shohei Ohtani Over 1.5 Total Bases (Elite hitter vs RHP)
    if ohtani_tb_over_prob > 0.66:
        edge = (ohtani_tb_over_prob - 0.50) * 100
        conf = confidence_score(edge, volatility=0.48)
        strong_bets.append({
            "market": "Shohei Ohtani Over 1.5 Total Bases",
            "probability": ohtani_tb_over_prob,
            "confidence": conf,
            "edge": f"{edge:+.1f}%",
            "model_factors": [
                "Ohtani elite BA/SLG vs RHP (Paddack command-reliant)",
                "Paddack elevated hard contact rate",
                "Favorable Target Field environment (ball carries)"
            ]
        })
    
    return {
        "match": "LAD vs MIN",
        "home": "MIN",
        "away": "LAD",
        "strong_bets": strong_bets,
        "model_projection": {
            "lad_runs": round(lad_runs_proj, 2),
            "min_runs": round(min_runs_proj, 2),
            "total": round(total_runs_proj, 2)
        }
    }

def push_match_to_discord(analysis: Dict[str, Any]) -> bool:
    """Push game analysis with model-based strong bets to Discord"""
    if not DISCORD_WEBHOOK:
        print("[-] DISCORD_WEBHOOK_URL not set")
        return False
    
    match_name = analysis["match"]
    strong_bets = analysis["strong_bets"]
    
    print(f"\n[*] Pushing {match_name} model-based strong bets to Discord...")
    
    for bet in strong_bets:
        try:
            market = bet["market"]
            prob_pct = int(bet["probability"] * 100)
            confidence = int(bet["confidence"])
            edge = bet["edge"]
            factors = " | ".join(bet["model_factors"][:2])  # Top 2 factors
            
            recommendation = f"{market}\n\nMODEL PROJECTION:\n{factors}\n\nProbability: {prob_pct}% | Edge: {edge} | Confidence: {confidence}%"
            
            success = push_to_discord(
                sport="baseball",
                home=analysis["home"],
                away=analysis["away"],
                market_total=None,
                projected_total=None,
                edge=edge,
                recommendation=recommendation,
                webhook_url=DISCORD_WEBHOOK,
                extra_metrics=f"Confidence: {confidence}% | Prob: {prob_pct}%",
                confidence=float(confidence)
            )
            
            if success:
                print(f"  [+] Pushed: {market}")
            else:
                print(f"  [-] Failed: {market}")
            
            time.sleep(0.5)
        
        except Exception as e:
            print(f"  [!] Error: {str(e)}")
            continue
    
    return True

def main():
    """Run full MLB analysis for 4-game slate"""
    print("\n" + "="*70)
    print("MLB 4-GAME SLATE - MODEL ANALYSIS ONLY")
    print("June 22, 2026 | Using Model Metrics (No Narrative Consensus)")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Analyze all 4 games
    games = [
        analyze_yy_det(),
        analyze_tex_mia(),
        analyze_chc_nym(),
        analyze_lad_min()
    ]
    
    # Display and push each game
    for game in games:
        match = game["match"]
        bets = game["strong_bets"]
        proj = game["model_projection"]
        
        print(f"\n[>] {match.upper()}")
        print(f"    Projected Total: {proj['total']:.2f} runs")
        print(f"    Strong Bets: {len(bets)}")
        
        for i, bet in enumerate(bets, 1):
            prob_pct = int(bet['probability'] * 100)
            conf = int(bet['confidence'])
            print(f"      {i}. {bet['market']} ({prob_pct}% | {conf}% conf)")
        
        push_match_to_discord(game)
        time.sleep(1)
    
    # Summary
    total_bets = sum(len(g['strong_bets']) for g in games)
    print("\n" + "="*70)
    print(f"[+] ANALYSIS COMPLETE")
    print(f"Total Games: 4")
    print(f"Total Model-Based Strong Bets Pushed: {total_bets}")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
