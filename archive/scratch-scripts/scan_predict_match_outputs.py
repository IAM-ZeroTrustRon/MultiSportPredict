#!/usr/bin/env python
"""
Scan predict_match.py output files for STRONG BET recommendations
========================================================
Scans output/soccer/ and output/basketball/ for all JSON files
produced by predict_match.py and counts recommendations.
"""

import json
import glob
import sys
from pathlib import Path


def scan_predict_match_outputs():
    """
    Scan all JSON output files from predict_match.py.
    Counts matches, recommendations, and STRONG BET occurrences.
    """
    # Force UTF-8 output
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    soccer_files = sorted(glob.glob('output/soccer/*.json'))
    basketball_files = sorted(glob.glob('output/basketball/*.json'))
    all_files = soccer_files + basketball_files

    print("=" * 80)
    print("  PREDICT_MATCH.PY — OUTPUT SCAN REPORT")
    print("=" * 80)
    print()

    print(f"  Soccer files:     {len(soccer_files)}")
    print(f"  Basketball files: {len(basketball_files)}")
    print(f"  Total files:      {len(all_files)}")
    print()

    strong_bet_count = 0
    bet_count = 0
    pass_count = 0
    total_recs = 0
    files_with_data = 0
    files_with_strong = 0
    sport_counts = {"soccer": 0, "basketball": 0}
    sport_strong = {"soccer": 0, "basketball": 0}

    strong_details = []

    for f in all_files:
        try:
            with open(f, encoding='utf-8') as fh:
                data = json.load(fh)
        except:
            continue

        home = data.get('home_team') or data.get('game', {}).get('home_team', '?')
        away = data.get('away_team') or data.get('game', {}).get('away_team', '?')
        
        # Determine sport
        sp = data.get('sport', '')
        if 'soccer' in f or sp == 'soccer':
            sport = 'soccer'
        else:
            sport = 'basketball'
        
        has_any_rec = False
        match_strong = []
        match_bets = []

        # Check predictions dict
        preds = data.get('predictions', {})
        for market, p in preds.items():
            if isinstance(p, dict):
                rec = str(p.get('recommendation', ''))
                if rec and rec != '':
                    has_any_rec = True
                    total_recs += 1
                    sport_counts[sport] = sport_counts.get(sport, 0) + 1
                    
                    if 'STRONG' in rec.upper():
                        strong_bet_count += 1
                        sport_strong[sport] = sport_strong.get(sport, 0) + 1
                        match_strong.append(f"{market}: {rec}")
                    elif 'BET' in rec.upper() and 'STRONG' not in rec.upper():
                        bet_count += 1
                        match_bets.append(f"{market}: {rec}")
                    elif 'PASS' in rec.upper():
                        pass_count += 1

        # Check corners_analysis
        corners = data.get('corners_analysis', {})
        if isinstance(corners, dict):
            rec = str(corners.get('recommendation', ''))
            if rec and rec != '':
                has_any_rec = True
                total_recs += 1
                sport_counts[sport] = sport_counts.get(sport, 0) + 1
                if 'STRONG' in rec.upper():
                    strong_bet_count += 1
                    sport_strong[sport] = sport_strong.get(sport, 0) + 1
                    match_strong.append(f"corners: {rec}")
                elif 'BET' in rec.upper() and 'STRONG' not in rec.upper():
                    bet_count += 1
                    match_bets.append(f"corners: {rec}")
                elif 'PASS' in rec.upper():
                    pass_count += 1

        # Check double_chance
        dc = preds.get('double_chance', {})
        if isinstance(dc, dict):
            recs = dc.get('recommendation', {})
            if isinstance(recs, dict):
                for k, v in recs.items():
                    v = str(v)
                    if v and v != '':
                        has_any_rec = True
                        total_recs += 1
                        sport_counts[sport] = sport_counts.get(sport, 0) + 1
                        if 'STRONG' in v.upper():
                            strong_bet_count += 1
                            sport_strong[sport] = sport_strong.get(sport, 0) + 1
                            match_strong.append(f"DC_{k}: {v}")
                        elif 'BET' in v.upper() and 'STRONG' not in v.upper():
                            bet_count += 1
                            match_bets.append(f"DC_{k}: {v}")
                        elif 'PASS' in v.upper():
                            pass_count += 1

        if has_any_rec:
            files_with_data += 1
            if match_strong:
                files_with_strong += 1
                strong_details.append({
                    'match': f"{home} vs {away}",
                    'sport': sport,
                    'strong': match_strong,
                })

    # Print summary
    print("  SCAN RESULTS")
    print("-" * 50)
    print(f"  Files with recommendations: {files_with_data}")
    print(f"  Files with STRONG BETs:     {files_with_strong}")
    print(f"  Total recommendations:      {total_recs}")
    print()
    print(f"  STRONG BETs:  {strong_bet_count}")
    print(f"  BETs:         {bet_count}")
    print(f"  PASSes:       {pass_count}")
    print()
    print(f"  Soccer STRONG BETs:  {sport_strong.get('soccer', 0)}")
    print(f"  Basketball STRONG BETs: {sport_strong.get('basketball', 0)}")
    print()

    # Print detailed breakdown
    print("  STRONG BET DETAILS")
    print("-" * 50)
    for d in strong_details:
        print(f"  [{d['sport'].upper()}] {d['match']}")
        for sb in d['strong']:
            print(f"     -> {sb}")
        print()

    # Calculate metrics
    strong_pct = (strong_bet_count / total_recs * 100) if total_recs > 0 else 0
    print("  METRICS")
    print("-" * 50)
    print(f"  STRONG BET rate: {strong_pct:.1f}% of all recommendations")
    print(f"  Avg STRONG BETs per file with data: {strong_bet_count/files_with_data:.1f}" if files_with_data > 0 else "  N/A")
    print()

    return {
        'total_files': len(all_files),
        'files_with_data': files_with_data,
        'files_with_strong': files_with_strong,
        'total_recs': total_recs,
        'strong_bets': strong_bet_count,
        'bets': bet_count,
        'passes': pass_count,
        'soccer_strong': sport_strong.get('soccer', 0),
        'basketball_strong': sport_strong.get('basketball', 0),
        'details': strong_details,
    }


if __name__ == '__main__':
    scan_predict_match_outputs()