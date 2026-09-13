#!/usr/bin/env python3
"""
Scrape actual match results for July 2026 MultiSportPredict recommendations.
Sources: ESPN API (free, no key needed), Wikipedia (Wimbledon), RealGM (FIBA)
"""
import json
import os
import sys
from datetime import datetime

import requests

# ============================================================================
# MLB RESULTS via ESPN API
# ============================================================================

def fetch_mlb_scores(date_str: str) -> list:
    """Fetch MLB scores for a given date (YYYYMMDD format)."""
    url = f"http://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard?dates={date_str}"
    r = requests.get(url, timeout=15)
    if r.status_code != 200:
        print(f"  [X] MLB {date_str}: HTTP {r.status_code}")
        return []
    
    data = r.json()
    results = []
    for event in data.get("events", []):
        name = event.get("name", "")
        status = event.get("status", {}).get("type", {}).get("description", "")
        if status != "Final":
            continue
        
        comps = event.get("competitions", [{}])[0]
        competitors = comps.get("competitors", [])
        
        teams = {}
        for c in competitors:
            team_name = c.get("team", {}).get("displayName", "")
            score = c.get("score", "0")
            is_winner = c.get("winner", False)
            home_away = c.get("homeAway", "")
            teams[home_away] = {
                "name": team_name,
                "score": int(score) if score.isdigit() else 0,
                "winner": is_winner
            }
        
        if "home" in teams and "away" in teams:
            results.append({
                "sport": "baseball",
                "date": date_str,
                "home_team": teams["home"]["name"],
                "away_team": teams["away"]["name"],
                "home_score": teams["home"]["score"],
                "away_score": teams["away"]["score"],
                "home_winner": teams["home"]["winner"],
                "away_winner": teams["away"]["winner"],
                "total_runs": teams["home"]["score"] + teams["away"]["score"],
                "source": "ESPN"
            })
    
    return results


# ============================================================================
# TENNIS RESULTS via ESPN API
# ============================================================================

def fetch_tennis_scores(date_str: str) -> list:
    """Fetch ATP tennis scores for a given date."""
    url = f"http://site.api.espn.com/apis/site/v2/sports/tennis/atp/scoreboard?dates={date_str}"
    r = requests.get(url, timeout=15)
    if r.status_code != 200:
        print(f"  [X] Tennis {date_str}: HTTP {r.status_code}")
        return []
    
    data = r.json()
    results = []
    for event in data.get("events", []):
        name = event.get("name", "")
        status = event.get("status", {}).get("type", {}).get("description", "")
        
        comps = event.get("competitions", [{}])[0]
        competitors = comps.get("competitors", [])
        
        players = {}
        for c in competitors:
            player_name = c.get("team", {}).get("displayName", "")
            score = c.get("score", "")
            is_winner = c.get("winner", False)
            home_away = c.get("homeAway", "")
            players[home_away] = {
                "name": player_name,
                "score": score,
                "winner": is_winner
            }
        
        if "home" in players and "away" in players:
            results.append({
                "sport": "tennis",
                "date": date_str,
                "player_a": players["home"]["name"],
                "player_b": players["away"]["name"],
                "player_a_score": players["home"]["score"],
                "player_b_score": players["away"]["score"],
                "player_a_winner": players["home"]["winner"],
                "player_b_winner": players["away"]["winner"],
                "status": status,
                "source": "ESPN"
            })
    
    return results


# ============================================================================
# BASKETBALL RESULTS via ESPN API
# ============================================================================

def fetch_basketball_scores(date_str: str, league: str = "mens-college-world") -> list:
    """Fetch basketball scores. For FIBA, use mens-college-world endpoint."""
    url = f"http://site.api.espn.com/apis/site/v2/sports/basketball/{league}/scoreboard?dates={date_str}"
    r = requests.get(url, timeout=15)
    if r.status_code != 200:
        return []
    
    data = r.json()
    results = []
    for event in data.get("events", []):
        name = event.get("name", "")
        status = event.get("status", {}).get("type", {}).get("description", "")
        
        comps = event.get("competitions", [{}])[0]
        competitors = comps.get("competitors", [])
        
        teams = {}
        for c in competitors:
            team_name = c.get("team", {}).get("displayName", "")
            score = c.get("score", "0")
            is_winner = c.get("winner", False)
            home_away = c.get("homeAway", "")
            teams[home_away] = {
                "name": team_name,
                "score": int(score) if score.isdigit() else 0,
                "winner": is_winner
            }
        
        if "home" in teams and "away" in teams:
            results.append({
                "sport": "basketball",
                "date": date_str,
                "home_team": teams["home"]["name"],
                "away_team": teams["away"]["name"],
                "home_score": teams["home"]["score"],
                "away_score": teams["away"]["score"],
                "home_winner": teams["home"]["winner"],
                "away_winner": teams["away"]["winner"],
                "total_points": teams["home"]["score"] + teams["away"]["score"],
                "source": "ESPN"
            })
    
    return results


# ============================================================================
# SOCCER RESULTS via ESPN API
# ============================================================================

def fetch_soccer_scores(date_str: str) -> list:
    """Fetch soccer scores from ESPN."""
    # Try multiple soccer leagues
    leagues = [
        "soccer.uefa.champions",  # UEFA competitions
        "soccer.uefa.euro",       # Euro competitions
    ]
    results = []
    for league in leagues:
        url = f"http://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={date_str}"
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            continue
        
        data = r.json()
        for event in data.get("events", []):
            name = event.get("name", "")
            status = event.get("status", {}).get("type", {}).get("description", "")
            
            comps = event.get("competitions", [{}])[0]
            competitors = comps.get("competitors", [])
            
            teams = {}
            for c in competitors:
                team_name = c.get("team", {}).get("displayName", "")
                score = c.get("score", "0")
                is_winner = c.get("winner", False)
                home_away = c.get("homeAway", "")
                teams[home_away] = {
                    "name": team_name,
                    "score": int(score) if score.isdigit() else 0,
                    "winner": is_winner
                }
            
            if "home" in teams and "away" in teams:
                results.append({
                    "sport": "soccer",
                    "date": date_str,
                    "home_team": teams["home"]["name"],
                    "away_team": teams["away"]["name"],
                    "home_score": teams["home"]["score"],
                    "away_score": teams["away"]["score"],
                    "home_winner": teams["home"]["winner"],
                    "away_winner": teams["away"]["winner"],
                    "total_goals": teams["home"]["score"] + teams["away"]["score"],
                    "source": "ESPN"
                })
    
    return results


# ============================================================================
# MAIN SCRAPER
# ============================================================================

def main():
    print("=" * 60)
    print("  MultiSportPredict — July 2026 Results Scraper")
    print("=" * 60)
    
    all_results = {}
    
    # Dates to scrape
    dates = ["20260701", "20260702", "20260704", "20260706"]
    
    for date in dates:
        print(f"\n--- {date} ---")
        
        # MLB
        mlb = fetch_mlb_scores(date)
        if mlb:
            print(f"  MLB: {len(mlb)} games")
            for g in mlb:
                winner = g["home_team"] if g["home_winner"] else g["away_team"]
                print(f"    {g['away_team']} ({g['away_score']}) @ {g['home_team']} ({g['home_score']}) — Winner: {winner}")
            all_results[f"mlb_{date}"] = mlb
        
        # Tennis
        tennis = fetch_tennis_scores(date)
        if tennis:
            print(f"  Tennis: {len(tennis)} matches")
            for m in tennis:
                winner = m["player_a"] if m["player_a_winner"] else m["player_b"]
                print(f"    {m['player_a']} vs {m['player_b']} — Winner: {winner} ({m['status']})")
            all_results[f"tennis_{date}"] = tennis
        
        # Basketball
        bball = fetch_basketball_scores(date)
        if bball:
            print(f"  Basketball: {len(bball)} games")
            for g in bball:
                winner = g["home_team"] if g["home_winner"] else g["away_team"]
                print(f"    {g['away_team']} ({g['away_score']}) @ {g['home_team']} ({g['home_score']}) — Winner: {winner}")
            all_results[f"basketball_{date}"] = bball
        
        # Soccer
        soccer = fetch_soccer_scores(date)
        if soccer:
            print(f"  Soccer: {len(soccer)} matches")
            for g in soccer:
                winner = g["home_team"] if g["home_winner"] else g["away_team"]
                print(f"    {g['away_team']} ({g['away_score']}) @ {g['home_team']} ({g['home_score']}) — Winner: {winner}")
            all_results[f"soccer_{date}"] = soccer
    
    # Save all results
    out_path = "output/july_2026_scraped_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n  [OK] Results saved to: {out_path}")
    
    # Summary
    total = sum(len(v) for v in all_results.values())
    print(f"  Total matches found: {total}")
    print("=" * 60)


if __name__ == "__main__":
    main()