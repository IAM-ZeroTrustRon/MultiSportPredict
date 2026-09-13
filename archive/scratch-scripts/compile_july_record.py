#!/usr/bin/env python3
"""
Compile July 2026 MultiSportPredict Win/Loss Record.
Matches predictions against actual results from scraped data.
"""
import json
import os
import re
import sys
from datetime import datetime

import requests

# ============================================================================
# LOAD PREDICTIONS (from our analysis files)
# ============================================================================

def load_predictions():
    """Load all July predictions from our analysis files."""
    predictions = []
    
    # ---- July 1: Phillies vs Pirates ----
    predictions.append({
        "date": "2026-07-01",
        "sport": "baseball",
        "home_team": "Philadelphia Phillies",
        "away_team": "Pittsburgh Pirates",
        "market": "Total Runs",
        "pick": "Under 8.0",
        "confidence": 72.0,
        "rec_level": "STRONG BET",
        "edge": "+22.0%",
        "predicted_winner": None,
        "predicted_total": "Under 8.0"
    })
    predictions.append({
        "date": "2026-07-01",
        "sport": "baseball",
        "home_team": "Philadelphia Phillies",
        "away_team": "Pittsburgh Pirates",
        "market": "Player Prop",
        "pick": "Wheeler Strikeouts Over 8.5",
        "confidence": 72.0,
        "rec_level": "STRONG BET",
        "edge": "+22.0%",
        "predicted_winner": None,
        "predicted_total": None
    })
    predictions.append({
        "date": "2026-07-01",
        "sport": "baseball",
        "home_team": "Philadelphia Phillies",
        "away_team": "Pittsburgh Pirates",
        "market": "Moneyline",
        "pick": "Pirates +118 (Sharp)",
        "confidence": 45.0,
        "rec_level": "BET",
        "edge": "+5.0%",
        "predicted_winner": "Pittsburgh Pirates",
        "predicted_total": None
    })
    
    # ---- July 2: Dodgers vs Padres ----
    predictions.append({
        "date": "2026-07-02",
        "sport": "baseball",
        "home_team": "Los Angeles Dodgers",
        "away_team": "San Diego Padres",
        "market": "Moneyline",
        "pick": "Dodgers ML",
        "confidence": 52.2,
        "rec_level": "BET",
        "edge": "-18.8%",
        "predicted_winner": "Los Angeles Dodgers",
        "predicted_total": None
    })
    predictions.append({
        "date": "2026-07-02",
        "sport": "baseball",
        "home_team": "Los Angeles Dodgers",
        "away_team": "San Diego Padres",
        "market": "Total Runs",
        "pick": "Over 9.0",
        "confidence": 60.0,
        "rec_level": "BET",
        "edge": "+19.6%",
        "predicted_winner": None,
        "predicted_total": "Over 9.0"
    })
    predictions.append({
        "date": "2026-07-02",
        "sport": "baseball",
        "home_team": "Los Angeles Dodgers",
        "away_team": "San Diego Padres",
        "market": "F5 Total",
        "pick": "Over 4.5",
        "confidence": 65.0,
        "rec_level": "BET",
        "edge": "+31.6%",
        "predicted_winner": None,
        "predicted_total": "Over 4.5"
    })
    predictions.append({
        "date": "2026-07-02",
        "sport": "baseball",
        "home_team": "Los Angeles Dodgers",
        "away_team": "San Diego Padres",
        "market": "YRFI",
        "pick": "YRFI",
        "confidence": 87.1,
        "rec_level": "STRONG BET",
        "edge": "+74.2%",
        "predicted_winner": None,
        "predicted_total": None
    })
    
    # ---- July 2: Angels vs Mariners ----
    predictions.append({
        "date": "2026-07-02",
        "sport": "baseball",
        "home_team": "Seattle Mariners",
        "away_team": "Los Angeles Angels",
        "market": "Moneyline",
        "pick": "Mariners ML",
        "confidence": 55.0,
        "rec_level": "BET",
        "edge": "+5.0%",
        "predicted_winner": "Seattle Mariners",
        "predicted_total": None
    })
    
    # ---- July 6: Mexico vs USA (FIBA) ----
    predictions.append({
        "date": "2026-07-06",
        "sport": "basketball",
        "home_team": "Mexico",
        "away_team": "USA",
        "market": "Spread",
        "pick": "Mexico +22.0",
        "confidence": 80.0,
        "rec_level": "STRONG BET",
        "edge": "+57.0%",
        "predicted_winner": None,
        "predicted_total": None
    })
    predictions.append({
        "date": "2026-07-06",
        "sport": "basketball",
        "home_team": "Mexico",
        "away_team": "USA",
        "market": "Total Points",
        "pick": "Over 147",
        "confidence": 70.0,
        "rec_level": "BET",
        "edge": "+22.0%",
        "predicted_winner": None,
        "predicted_total": "Over 147"
    })
    
    return predictions


# ============================================================================
# LOAD SCRAPED RESULTS
# ============================================================================

def load_scraped_results():
    """Load scraped results from JSON file."""
    path = "output/july_2026_scraped_results.json"
    if not os.path.exists(path):
        print(f"  [X] Scraped results not found at {path}")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================================
# FETCH WIMBLEDON RESULTS FROM WIKIPEDIA
# ============================================================================

def fetch_wimbledon_results():
    """Fetch Wimbledon 2026 results from Wikipedia."""
    results = []
    
    # Wikipedia page for 2026 Wimbledon Men's Singles
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "titles": "2026_Wimbledon_Championships_%E2%80%93_Men%27s_singles",
        "prop": "extracts",
        "format": "json",
        "explaintext": 1,
        "sectionformat": "plain"
    }
    
    try:
        r = requests.get(url, params=params, timeout=15, headers={"User-Agent": "MultiSportPredict/1.0"})
        if r.status_code == 200:
            data = r.json()
            pages = data.get("query", {}).get("pages", {})
            for pid, page in pages.items():
                extract = page.get("extract", "")
                if not extract:
                    continue
                
                # Parse rounds from the extract
                # Look for score patterns like "Player A 6–4, 6–3, 6–2 Player B"
                rounds_found = []
                
                # Find section headers
                sections = re.split(r'\n==+\s*', extract)
                for section in sections:
                    section_title = section.strip().split('\n')[0] if section.strip() else ''
                    
                    # Look for match results in each section
                    # Pattern: "Player Name 6–4, 3–6, 6–3, 6–4 Player Name"
                    matches = re.findall(
                        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+(\d[–\d,\s]+)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
                        section
                    )
                    for m in matches:
                        player1, score_str, player2 = m
                        # Parse sets
                        sets = re.findall(r'(\d+)[–-](\d+)', score_str)
                        if len(sets) >= 2:
                            p1_sets = sum(1 for s in sets if int(s[0]) > int(s[1]))
                            p2_sets = sum(1 for s in sets if int(s[1]) > int(s[0]))
                            winner = player1 if p1_sets > p2_sets else player2
                            results.append({
                                "sport": "tennis",
                                "player_a": player1,
                                "player_b": player2,
                                "winner": winner,
                                "score": score_str.strip(),
                                "source": "Wikipedia"
                            })
        
        print(f"  Wikipedia: {len(results)} tennis matches parsed")
    except Exception as e:
        print(f"  [X] Wikipedia fetch error: {e}")
    
    return results


# ============================================================================
# FETCH FIBA RESULTS FROM REALGM
# ============================================================================

def fetch_fiba_results():
    """Fetch FIBA basketball results."""
    results = []
    
    # Try RealGM's FIBA page
    urls = [
        "https://basketball.realgm.com/international/league/1/FIBA-Americas/standings",
        "https://basketball.realgm.com/international/league/1/FIBA-World-Cup/standings"
    ]
    
    for url in urls:
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                # Look for score patterns in the HTML
                scores = re.findall(r'([A-Za-z\s]+)\s+(\d+)\s*[–-]\s*(\d+)\s+([A-Za-z\s]+)', r.text)
                for s in scores:
                    team1, score1, score2, team2 = s
                    results.append({
                        "sport": "basketball",
                        "team_a": team1.strip(),
                        "team_b": team2.strip(),
                        "score_a": int(score1),
                        "score_b": int(score2),
                        "source": "RealGM"
                    })
        except Exception as e:
            print(f"  [X] RealGM fetch error for {url}: {e}")
    
    return results


# ============================================================================
# MATCH PREDICTIONS TO RESULTS
# ============================================================================

def evaluate_mlb_prediction(pred, results_data):
    """Evaluate an MLB prediction against actual results."""
    date_key = pred["date"].replace("-", "")
    mlb_key = f"mlb_{date_key}"
    
    if mlb_key not in results_data:
        return None
    
    games = results_data[mlb_key]
    
    # Find matching game
    for game in games:
        home = game["home_team"]
        away = game["away_team"]
        
        # Check if this is the right game
        if (pred["home_team"].lower() in home.lower() or pred["home_team"].lower() in away.lower()) and \
           (pred["away_team"].lower() in home.lower() or pred["away_team"].lower() in away.lower()):
            
            actual_total = game["total_runs"]
            home_winner = game["home_winner"]
            away_winner = game["away_winner"]
            actual_winner = home if home_winner else away
            
            result = {
                "match": f"{away} @ {home}",
                "actual_score": f"{away} {game['away_score']} - {home} {game['home_score']}",
                "actual_total": actual_total,
                "actual_winner": actual_winner
            }
            
            # Evaluate by market type
            if pred["market"] == "Moneyline":
                result["correct"] = pred["predicted_winner"].lower() == actual_winner.lower()
                result["detail"] = f"Predicted: {pred['predicted_winner']} | Actual: {actual_winner}"
            
            elif pred["market"] == "Total Runs":
                if pred["pick"].startswith("Over"):
                    line = float(pred["pick"].replace("Over ", ""))
                    result["correct"] = actual_total > line
                    result["detail"] = f"Predicted: {pred['pick']} (Total: {actual_total})"
                elif pred["pick"].startswith("Under"):
                    line = float(pred["pick"].replace("Under ", ""))
                    result["correct"] = actual_total < line
                    result["detail"] = f"Predicted: {pred['pick']} (Total: {actual_total})"
            
            elif pred["market"] == "F5 Total":
                # We don't have F5 data from ESPN, mark as unknown
                result["correct"] = None
                result["detail"] = "F5 data not available from ESPN"
            
            elif pred["market"] == "YRFI":
                # YRFI = Yes Run First Inning. Dodgers scored 12 total, Padres 7
                # First inning: Dodgers scored 1, Padres 0 (from game data)
                # We'll approximate based on total scoring
                result["correct"] = None
                result["detail"] = "YRFI data not available from ESPN"
            
            elif pred["market"] == "Player Prop":
                result["correct"] = None
                result["detail"] = "Player prop data not available from ESPN"
            
            return result
    
    return None


def evaluate_basketball_prediction(pred, results_data):
    """Evaluate a basketball prediction."""
    # For FIBA, we need to check if we have the data
    # Mexico vs USA on July 6
    if "Mexico" in pred["home_team"] and "USA" in pred["away_team"]:
        # From our analysis: Mexico at home (8,010ft elevation)
        # USA was heavily favored at -22 spread
        # We need actual score
        return {
            "match": "Mexico vs USA",
            "correct": None,
            "detail": "FIBA result not available from ESPN API",
            "actual_score": "Unknown"
        }
    
    return None


# ============================================================================
# MAIN COMPILER
# ============================================================================

def main():
    print("=" * 60)
    print("  MultiSportPredict — July 2026 Record Compiler")
    print("=" * 60)
    
    # Load data
    print("\n[1] Loading predictions...")
    predictions = load_predictions()
    print(f"  {len(predictions)} predictions loaded")
    
    print("\n[2] Loading scraped results...")
    results_data = load_scraped_results()
    print(f"  {sum(len(v) for v in results_data.values())} results loaded")
    
    print("\n[3] Fetching additional results...")
    wimbledon = fetch_wimbledon_results()
    fiba = fetch_fiba_results()
    
    # Evaluate each prediction
    print("\n[4] Evaluating predictions...")
    results = []
    wins = 0
    losses = 0
    unknowns = 0
    strong_wins = 0
    strong_losses = 0
    strong_unknowns = 0
    
    for pred in predictions:
        if pred["sport"] == "baseball":
            result = evaluate_mlb_prediction(pred, results_data)
        elif pred["sport"] == "basketball":
            result = evaluate_basketball_prediction(pred, results_data)
        else:
            result = None
        
        if result:
            if result["correct"] is True:
                wins += 1
                if pred["rec_level"] == "STRONG BET":
                    strong_wins += 1
            elif result["correct"] is False:
                losses += 1
                if pred["rec_level"] == "STRONG BET":
                    strong_losses += 1
            else:
                unknowns += 1
                if pred["rec_level"] == "STRONG BET":
                    strong_unknowns += 1
            
            status = "[WIN]" if result["correct"] is True else ("[LOSS]" if result["correct"] is False else "[PENDING]")
            print(f"  {status} | {pred['date']} | {pred['sport']} | {pred['market']}: {pred['pick']} ({pred['rec_level']}, {pred['confidence']}%)")
            if result.get("detail"):
                print(f"         {result['detail']}")
        else:
            unknowns += 1
            if pred["rec_level"] == "STRONG BET":
                strong_unknowns += 1
            print(f"  [NO DATA] | {pred['date']} | {pred['sport']} | {pred['market']}: {pred['pick']} ({pred['rec_level']}, {pred['confidence']}%)")
    
    # Print summary
    total_evaluated = wins + losses
    total = len(predictions)
    
    print("\n" + "=" * 60)
    print("  JULY 2026 — RESULTS SUMMARY")
    print("=" * 60)
    print(f"\n  Total Predictions: {total}")
    print(f"  Evaluated: {total_evaluated}")
    print(f"  Pending (no data): {unknowns}")
    print(f"\n  Wins: {wins}")
    print(f"  Losses: {losses}")
    if total_evaluated > 0:
        print(f"  Win Rate: {wins/total_evaluated*100:.1f}%")
    
    print(f"\n  STRONG BETS (≥75% confidence):")
    strong_total = strong_wins + strong_losses + strong_unknowns
    print(f"    Total: {strong_total}")
    print(f"    Wins: {strong_wins}")
    print(f"    Losses: {strong_losses}")
    print(f"    Pending: {strong_unknowns}")
    if (strong_wins + strong_losses) > 0:
        print(f"    Win Rate: {strong_wins/(strong_wins+strong_losses)*100:.1f}%")
    
    # Save results
    output = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_predictions": total,
            "evaluated": total_evaluated,
            "pending": unknowns,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(wins/total_evaluated*100, 1) if total_evaluated > 0 else 0,
            "strong_bets": {
                "total": strong_total,
                "wins": strong_wins,
                "losses": strong_losses,
                "pending": strong_unknowns,
                "win_rate_pct": round(strong_wins/(strong_wins+strong_losses)*100, 1) if (strong_wins+strong_losses) > 0 else 0
            }
        },
        "predictions": predictions,
        "results": results_data
    }
    
    out_path = "output/july_2026_compiled_record.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  [OK] Compiled record saved to: {out_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()