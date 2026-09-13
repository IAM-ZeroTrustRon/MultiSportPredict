#!/usr/bin/env python
"""
BATCH MLB ANALYSIS — JUNE 16, 2026 — ALL 15 GAMES
Full slate recalibrated with correct pitchers, parks, and market data
"""

import json, math
from datetime import datetime

def calc_projected_runs(home_rpg, away_rpg, home_rpg_allowed, away_rpg_allowed, home_era, away_era, 
                        park_factor, weather_adj=1.0, custom_adj_home=0.0, custom_adj_away=0.0):
    home_proj = (home_rpg + away_era) / 2
    away_proj = (away_rpg + home_era) / 2
    home_net_adj = (home_rpg - home_rpg_allowed) * 0.08
    away_net_adj = (away_rpg - away_rpg_allowed) * 0.08
    home_proj += home_net_adj + custom_adj_home
    away_proj += away_net_adj + custom_adj_away
    home_proj *= park_factor * weather_adj
    away_proj *= park_factor * weather_adj
    total = home_proj + away_proj
    return round(home_proj, 2), round(away_proj, 2), round(total, 2)

def calc_ou_confidence(edge_runs):
    base = min(abs(edge_runs) * 25, 80)
    return round(base, 1)

# All 15 games
games = [
    # 1) MIA @ PHI
    {'game': 'MIA @ PHI', 'time': '6:40 PM', 'venue': 'Citizens Bank Park',
     'away_team': 'Miami Marlins', 'home_team': 'Philadelphia Phillies',
     'away_pitcher': 'Tyler Phillips (RHP)', 'home_pitcher': 'Jesús Luzardo (LHP)',
     'away_rpg': 3.9, 'home_rpg': 4.8, 'away_rpg_allowed': 4.4, 'home_rpg_allowed': 4.0,
     'away_era': 4.10, 'home_era': 3.70, 'park_factor': 1.08, 'weather_adj': 1.01,
     'market_total': 8.5, 'custom_adj_away': 0.30, 'custom_adj_home': 0.25},
    # 2) KC @ WAS
    {'game': 'KC @ WAS', 'time': '6:45 PM', 'venue': 'Nationals Park',
     'away_team': 'Kansas City Royals', 'home_team': 'Washington Nationals',
     'away_pitcher': 'Michael Wacha (RHP)', 'home_pitcher': 'Foster Griffin (LHP)',
     'away_rpg': 4.3, 'home_rpg': 4.1, 'away_rpg_allowed': 4.0, 'home_rpg_allowed': 4.6,
     'away_era': 3.85, 'home_era': 4.30, 'park_factor': 0.98, 'weather_adj': 1.0,
     'market_total': 8.5, 'custom_adj_away': 0.0, 'custom_adj_home': 0.0},
    # 3) TOR @ BOS
    {'game': 'TOR @ BOS', 'time': '6:45 PM', 'venue': 'Fenway Park',
     'away_team': 'Toronto Blue Jays', 'home_team': 'Boston Red Sox',
     'away_pitcher': 'Dylan Cease (RHP)', 'home_pitcher': 'Payton Tolle (LHP)',
     'away_rpg': 4.5, 'home_rpg': 4.7, 'away_rpg_allowed': 4.2, 'home_rpg_allowed': 4.3,
     'away_era': 3.95, 'home_era': 4.05, 'park_factor': 1.05, 'weather_adj': 1.0,
     'market_total': 8.5, 'custom_adj_away': 0.0, 'custom_adj_home': 0.0},
    # 4) CWS @ NYY
    {'game': 'CWS @ NYY', 'time': '7:05 PM', 'venue': 'Yankee Stadium',
     'away_team': 'Chicago White Sox', 'home_team': 'New York Yankees',
     'away_pitcher': 'Davis Martin (RHP)', 'home_pitcher': 'Gerrit Cole (RHP)',
     'away_rpg': 3.8, 'home_rpg': 4.9, 'away_rpg_allowed': 4.7, 'home_rpg_allowed': 3.8,
     'away_era': 4.45, 'home_era': 3.55, 'park_factor': 1.02, 'weather_adj': 1.0,
     'market_total': 8.0, 'custom_adj_away': 0.0, 'custom_adj_home': 0.0},
    # 5) NYM @ CIN
    {'game': 'NYM @ CIN', 'time': '7:10 PM', 'venue': 'Great American Ball Park',
     'away_team': 'New York Mets', 'home_team': 'Cincinnati Reds',
     'away_pitcher': 'Kodai Senga (RHP)', 'home_pitcher': 'Brady Singer (RHP)',
     'away_rpg': 4.4, 'home_rpg': 4.5, 'away_rpg_allowed': 4.1, 'home_rpg_allowed': 4.3,
     'away_era': 3.90, 'home_era': 4.00, 'park_factor': 1.12, 'weather_adj': 1.02,
     'market_total': 9.0, 'custom_adj_away': 0.0, 'custom_adj_home': 0.0},
    # 6) SF @ ATL
    {'game': 'SF @ ATL', 'time': '7:15 PM', 'venue': 'Truist Park',
     'away_team': 'San Francisco Giants', 'home_team': 'Atlanta Braves',
     'away_pitcher': 'Adrian Houser (RHP)', 'home_pitcher': 'Grant Holmes (RHP)',
     'away_rpg': 4.45, 'home_rpg': 5.12, 'away_rpg_allowed': 4.10, 'home_rpg_allowed': 4.25,
     'away_era': 3.85, 'home_era': 3.95, 'park_factor': 1.05, 'weather_adj': 1.02,
     'market_total': 9.0, 'custom_adj_away': 0.35, 'custom_adj_home': 0.40},
    # 7) CLE @ MIL
    {'game': 'CLE @ MIL', 'time': '7:40 PM', 'venue': 'American Family Field',
     'away_team': 'Cleveland Guardians', 'home_team': 'Milwaukee Brewers',
     'away_pitcher': 'Slade Cecconi (RHP)', 'home_pitcher': 'Robert Gasser (LHP)',
     'away_rpg': 4.3, 'home_rpg': 4.5, 'away_rpg_allowed': 3.9, 'home_rpg_allowed': 4.0,
     'away_era': 3.75, 'home_era': 3.80, 'park_factor': 1.01, 'weather_adj': 1.0,
     'market_total': 8.0, 'custom_adj_away': 0.0, 'custom_adj_home': 0.0},
    # 8) SD @ STL
    {'game': 'SD @ STL', 'time': '7:45 PM', 'venue': 'Busch Stadium',
     'away_team': 'San Diego Padres', 'home_team': 'St. Louis Cardinals',
     'away_pitcher': 'Michael King (RHP)', 'home_pitcher': 'Andre Pallante (RHP)',
     'away_rpg': 4.4, 'home_rpg': 4.2, 'away_rpg_allowed': 4.0, 'home_rpg_allowed': 4.3,
     'away_era': 3.85, 'home_era': 4.05, 'park_factor': 0.96, 'weather_adj': 1.0,
     'market_total': 8.0, 'custom_adj_away': 0.0, 'custom_adj_home': 0.0},
    # 9) MIN @ TEX
    {'game': 'MIN @ TEX', 'time': '8:05 PM', 'venue': 'Globe Life Field',
     'away_team': 'Minnesota Twins', 'home_team': 'Texas Rangers',
     'away_pitcher': 'Zebby Matthews (RHP)', 'home_pitcher': 'Kumar Rocker (RHP)',
     'away_rpg': 4.5, 'home_rpg': 4.6, 'away_rpg_allowed': 4.2, 'home_rpg_allowed': 4.1,
     'away_era': 3.95, 'home_era': 3.90, 'park_factor': 0.97, 'weather_adj': 1.0,
     'market_total': 8.5, 'custom_adj_away': 0.15, 'custom_adj_home': 0.0},
    # 10) COL @ CHC
    {'game': 'COL @ CHC', 'time': '8:05 PM', 'venue': 'Wrigley Field',
     'away_team': 'Colorado Rockies', 'home_team': 'Chicago Cubs',
     'away_pitcher': 'Ryan Feltner (RHP)', 'home_pitcher': 'Edward Cabrera (RHP)',
     'away_rpg': 4.1, 'home_rpg': 4.6, 'away_rpg_allowed': 4.8, 'home_rpg_allowed': 4.1,
     'away_era': 4.65, 'home_era': 3.85, 'park_factor': 1.0, 'weather_adj': 1.0,
     'market_total': 8.5, 'custom_adj_away': 0.20, 'custom_adj_home': 0.0},
    # 11) DET @ HOU
    {'game': 'DET @ HOU', 'time': '8:10 PM', 'venue': 'Minute Maid Park',
     'away_team': 'Detroit Tigers', 'home_team': 'Houston Astros',
     'away_pitcher': 'Framber Valdez (LHP)', 'home_pitcher': 'Hunter Brown (RHP)',
     'away_rpg': 4.0, 'home_rpg': 4.8, 'away_rpg_allowed': 4.0, 'home_rpg_allowed': 4.0,
     'away_era': 3.85, 'home_era': 3.75, 'park_factor': 1.04, 'weather_adj': 1.0,
     'market_total': 8.5, 'custom_adj_away': -0.25, 'custom_adj_home': 0.0},
    # 12) BAL @ SEA
    {'game': 'BAL @ SEA', 'time': '9:40 PM', 'venue': 'T-Mobile Park',
     'away_team': 'Baltimore Orioles', 'home_team': 'Seattle Mariners',
     'away_pitcher': 'Brandon Young (RHP)', 'home_pitcher': 'Logan Gilbert (RHP)',
     'away_rpg': 4.7, 'home_rpg': 4.2, 'away_rpg_allowed': 4.1, 'home_rpg_allowed': 3.9,
     'away_era': 3.90, 'home_era': 3.65, 'park_factor': 0.92, 'weather_adj': 1.0,
     'market_total': 7.5, 'custom_adj_away': 0.0, 'custom_adj_home': -0.30},
    # 13) PIT @ OAK
    {'game': 'PIT @ OAK', 'time': '9:40 PM', 'venue': 'Oakland Coliseum',
     'away_team': 'Pittsburgh Pirates', 'home_team': 'Athletics',
     'away_pitcher': 'Mitch Keller (RHP)', 'home_pitcher': 'Jack Perkins (RHP)',
     'away_rpg': 4.2, 'home_rpg': 3.9, 'away_rpg_allowed': 4.3, 'home_rpg_allowed': 4.5,
     'away_era': 4.10, 'home_era': 4.25, 'park_factor': 0.94, 'weather_adj': 1.0,
     'market_total': 8.0, 'custom_adj_away': 0.0, 'custom_adj_home': 0.15},
    # 14) LAA @ ARI
    {'game': 'LAA @ ARI', 'time': '9:40 PM', 'venue': 'Chase Field',
     'away_team': 'Los Angeles Angels', 'home_team': 'Arizona Diamondbacks',
     'away_pitcher': 'Reid Detmers (LHP)', 'home_pitcher': 'Merrill Kelly (RHP)',
     'away_rpg': 4.1, 'home_rpg': 4.6, 'away_rpg_allowed': 4.4, 'home_rpg_allowed': 4.3,
     'away_era': 4.15, 'home_era': 4.00, 'park_factor': 1.06, 'weather_adj': 1.01,
     'market_total': 9.0, 'custom_adj_away': 0.0, 'custom_adj_home': 0.0},
    # 15) TB @ LAD
    {'game': 'TB @ LAD', 'time': '10:10 PM', 'venue': 'Dodger Stadium',
     'away_team': 'Tampa Bay Rays', 'home_team': 'Los Angeles Dodgers',
     'away_pitcher': 'Drew Rasmussen (RHP)', 'home_pitcher': 'Justin Wrobleski (LHP)',
     'away_rpg': 4.2, 'home_rpg': 5.0, 'away_rpg_allowed': 3.8, 'home_rpg_allowed': 3.9,
     'away_era': 3.60, 'home_era': 3.65, 'park_factor': 1.03, 'weather_adj': 1.0,
     'market_total': 8.5, 'custom_adj_away': -0.20, 'custom_adj_home': 0.15},
]

# Run analysis
results = []
for g in games:
    home_proj, away_proj, total_proj = calc_projected_runs(
        home_rpg=g['home_rpg'], away_rpg=g['away_rpg'],
        home_rpg_allowed=g['home_rpg_allowed'], away_rpg_allowed=g['away_rpg_allowed'],
        home_era=g['home_era'], away_era=g['away_era'],
        park_factor=g['park_factor'], weather_adj=g['weather_adj'],
        custom_adj_home=g['custom_adj_home'], custom_adj_away=g['custom_adj_away']
    )
    edge = round(total_proj - g['market_total'], 2)
    conf = calc_ou_confidence(edge)
    direction = 'OVER' if total_proj > g['market_total'] else 'UNDER'
    results.append({**g, 'home_proj': home_proj, 'away_proj': away_proj, 'total_proj': total_proj, 'edge': edge, 'confidence': conf, 'direction': direction})

results.sort(key=lambda x: x['confidence'], reverse=True)

# Save results
output = []
print('=' * 95)
print('MLB JUNE 16, 2026 — FULL 15-GAME SLATE — STRONGEST OVER/UNDER BETS')
print('=' * 95)
print(f'Generated: {datetime.now().strftime("%I:%M:%S %p ET")} — Game times Eastern')
print('=' * 95)
print()

for i, g in enumerate(results, 1):
    if g['confidence'] >= 70:
        tier = '★★★★★ BEST BET'
    elif g['confidence'] >= 55:
        tier = '★★★★ STRONG'
    elif g['confidence'] >= 40:
        tier = '★★★ LEAN'
    elif g['confidence'] >= 25:
        tier = '★★ WEAK'
    else:
        tier = '★ PASS'
    
    line = f'{g["game"]:>12s} | '
    line += f'{g["time"]:>8s} | '
    line += f'{g["direction"]:5s} {g["market_total"]:<4} | '
    line += f'Proj:{g["total_proj"]:5.2f} | '
    line += f'Edge:{g["edge"]:+.2f}r | '
    line += f'Conf:{g["confidence"]:5.1f}% | '
    line += f'{tier}'
    
    print(line)
    print(f'    " {g["venue"]:30s} | {g["home_pitcher"]:>28s} vs {g["away_pitcher"]:<28s}')
    print(f'    Score: {g["away_team"]:22s} {g["away_proj"]:5.2f} - {g["home_team"]:25s} {g["home_proj"]:5.2f}')

print()
print('=' * 95)
print('TOP 5 STRONGEST O/U BETS')
print('=' * 95)
print()

top5 = results[:5]
for i, g in enumerate(top5, 1):
    print(f'  #{i}: {g["game"]} ({g["time"]})')
    print(f'       {g["direction"]} {g["market_total"]} (Proj: {g["total_proj"]}, Edge: {g["edge"]:+.2f}r, Conf: {g["confidence"]:.0f}%)')
    print(f'       {g["away_pitcher"]} @ {g["home_pitcher"]} @ {g["venue"]}')
    print(f'       Score: {g["away_team"]} {g["away_proj"]} - {g["home_team"]} {g["home_proj"]}')
    print()

print('=' * 95)
print('BOTTOM 5 (WEAKEST O/U — PASS)')
print('=' * 95)
print()
bottom5 = results[-5:]
for i, g in enumerate(bottom5, 1):
    print(f'  #{len(results)-5+i}: {g["game"]} ({g["time"]}) — {g["direction"]} {g["market_total"]} (Conf: {g["confidence"]:.0f}%) — PASS')

print()
print('=' * 95)
print('NOTES')
print('=' * 95)
print('- Confidence based on edge magnitude (|edge| * 25, capped at 80%)')
print('- Custom adjustments applied for pitcher-specific factors:')
print('  · SF@ATL: Houser contact (+0.35r) + Giants BP/injury (+0.40r) = +0.75r to total')
print('  · MIA@PHI: Luzardo LHB vulnerability (+0.30r) + Phillips walks (+0.25r) = +0.55r to total')
print('  · DET@HOU: Valdez groundball suppression (-0.25r from total)')
print('  · BAL@SEA: Gilbert elite (-0.30r) + T-Mobile Park (0.92) = strong Under lean')
print('- All data as of 5:36 PM ET, no games started yet')