#!/usr/bin/env python
"""
MLB Analysis: July 2, 2026
===========================
Game 1: LA Dodgers vs San Diego Padres (Dodger Stadium)
Game 2: LA Angels vs Seattle Mariners (T-Mobile Park)

Markets: ML, F5 ML, Totals, F5 Totals, NRFI/YRFI, Player Props, Pitcher Props
"""

import sys, json, os, math
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from scipy.stats import poisson
from dotenv import load_dotenv
load_dotenv()

# ============================================================================
# MLB GAME ANALYZER
# ============================================================================

class MLBGameAnalyzer:
    """Comprehensive MLB game analysis engine."""
    
    def __init__(self, game_data: Dict):
        self.g = game_data  # Game data dict
        self.results = {}
    
    # ---- UTILITY ----
    def _poisson_prob(self, mean: float, target: int) -> float:
        """P(X >= target) using Poisson distribution."""
        return 1 - poisson.cdf(target - 1, mean)
    
    def _poisson_exact(self, mean: float, k: int) -> float:
        """P(X = k) using Poisson PMF."""
        return poisson.pmf(k, mean)
    
    def _win_prob_from_run_diff(self, run_diff: float) -> float:
        """Convert projected run differential to win probability."""
        return 1.0 / (1.0 + math.exp(-run_diff / 1.8))
    
    def _adj_rpg(self, team_rpg: float, opp_era: float, league_era: float = 4.32) -> float:
        """Adjust team RPG based on opponent pitcher quality.
        When opp_era < league_era (good pitcher), runs decrease.
        When opp_era > league_era (bad pitcher), runs increase.
        """
        return team_rpg * (opp_era / league_era)
    
    def _edge(self, proj: float, market: float) -> float:
        """Calculate edge percentage."""
        return round((proj / market - 1) * 100, 1)
    
    def _decision(self, edge_pct: float, threshold_bet: float = 4.0, threshold_lean: float = 2.0) -> str:
        """Make bet decision based on edge percentage."""
        if edge_pct >= threshold_bet:
            return "BET"
        elif edge_pct >= threshold_lean:
            return "LEAN"
        return "PASS"
    
    # ---- PITCHER ANALYSIS ----
    def analyze_pitchers(self):
        """Analyze starting pitcher matchup."""
        home_p = self.g['home_pitcher']
        away_p = self.g['away_pitcher']
        
        # Calculate pitcher quality score
        def pitcher_score(p):
            era_adj = max(0, 5.0 - float(p['era'])) * 10
            k9_adj = float(p['k9']) * 2
            whip_adj = max(0, 1.5 - float(p['whip'])) * 20
            return era_adj + k9_adj + whip_adj
        
        home_score = pitcher_score(home_p)
        away_score = pitcher_score(away_p)
        
        return {
            'home_pitcher': {
                'name': home_p['name'],
                'era': home_p['era'], 'xfip': home_p.get('xfip', home_p['era']),
                'k9': home_p['k9'], 'bb9': home_p.get('bb9', 3.0),
                'whip': home_p['whip'], 'hr9': home_p.get('hr9', 1.0),
                'quality_score': round(home_score, 1),
            },
            'away_pitcher': {
                'name': away_p['name'],
                'era': away_p['era'], 'xfip': away_p.get('xfip', away_p['era']),
                'k9': away_p['k9'], 'bb9': away_p.get('bb9', 3.0),
                'whip': away_p['whip'], 'hr9': away_p.get('hr9', 1.0),
                'quality_score': round(away_score, 1),
            },
            'edge': round(home_score - away_score, 1),
            'winner': home_p['name'] if home_score > away_score else away_p['name'],
        }
    
    # ---- TEAM ANALYSIS ----
    def analyze_teams(self):
        """Analyze team offensive/defensive efficiency."""
        home = self.g['home_team']
        away = self.g['away_team']
        
        home_net = home['rpg'] - home['era']
        away_net = away['rpg'] - away['era']
        
        return {
            'home': {
                'rpg': home['rpg'], 'ops': home['ops'],
                'era': home['era'], 'whip': home['whip'],
                'net_rating': round(home_net, 2),
                'k_rate': home.get('k_rate', 0.22),
            },
            'away': {
                'rpg': away['rpg'], 'ops': away['ops'],
                'era': away['era'], 'whip': away['whip'],
                'net_rating': round(away_net, 2),
                'k_rate': away.get('k_rate', 0.22),
            },
        }
    
    # ---- RUN PROJECTIONS ----
    def project_runs(self):
        """Project runs for full game and F5."""
        hp = self.g['home_pitcher']
        ap = self.g['away_pitcher']
        ht = self.g['home_team']
        at = self.g['away_team']
        
        # Full game projections
        home_rpg_adj = self._adj_rpg(ht['rpg'], ap['era'])
        away_rpg_adj = self._adj_rpg(at['rpg'], hp['era'])
        
        # Park factor adjustment
        pf = self.g.get('park_factor', 1.0)
        home_rpg_adj *= pf
        away_rpg_adj *= pf
        
        # F5 projections (starters dominate F5, ~60% of runs)
        f5_home = home_rpg_adj * 0.55
        f5_away = away_rpg_adj * 0.55
        
        # Full game totals
        fg_total = home_rpg_adj + away_rpg_adj
        f5_total = f5_home + f5_away
        
        return {
            'full_game': {
                'home_runs': round(home_rpg_adj, 2),
                'away_runs': round(away_rpg_adj, 2),
                'total': round(fg_total, 2),
                'run_diff': round(home_rpg_adj - away_rpg_adj, 2),
            },
            'f5': {
                'home_runs': round(f5_home, 2),
                'away_runs': round(f5_away, 2),
                'total': round(f5_total, 2),
                'run_diff': round(f5_home - f5_away, 2),
            },
        }
    
    # ---- NRFI/YRFI ----
    def project_first_inning(self):
        """Project first inning scoring (NRFI/YRFI)."""
        hp = self.g['home_pitcher']
        ap = self.g['away_pitcher']
        ht = self.g['home_team']
        at = self.g['away_team']
        
        # First inning scoring rates
        home_1st_rate = ht.get('first_inning_rpg', ht['rpg'] * 0.12)
        away_1st_rate = at.get('first_inning_rpg', at['rpg'] * 0.12)
        
        # Pitcher first inning adjustments
        hp_1st_adj = 1.0 + (float(hp.get('first_inning_era', float(hp['era']) * 1.1)) / 5.0 - 0.2)
        ap_1st_adj = 1.0 + (float(ap.get('first_inning_era', float(ap['era']) * 1.1)) / 5.0 - 0.2)
        
        home_1st = away_1st_rate * hp_1st_adj
        away_1st = home_1st_rate * ap_1st_adj
        
        total_1st = home_1st + away_1st
        
        # Probability of at least 1 run in first inning
        prob_yrfi = 1 - (math.exp(-home_1st) * math.exp(-away_1st))
        prob_nrfi = 1 - prob_yrfi
        
        return {
            'home_1st_runs': round(home_1st, 3),
            'away_1st_runs': round(away_1st, 3),
            'total_1st': round(total_1st, 3),
            'prob_yrfi': round(prob_yrfi, 3),
            'prob_nrfi': round(prob_nrfi, 3),
            'lean': 'YRFI' if prob_yrfi > 0.48 else 'NRFI',
        }
    
    # ---- PLAYER PROPS ----
    def project_player_props(self):
        """Project player prop bets."""
        props = []
        for prop in self.g.get('player_props', []):
            proj = float(prop['projection'])
            line = float(prop['line'])
            edge_pct = self._edge(proj, line) if line > 0 else 0
            
            props.append({
                'player': prop['player'],
                'team': prop['team'],
                'stat': prop['stat'],
                'line': line,
                'projection': round(proj, 2),
                'edge_pct': edge_pct,
                'lean': 'Over' if proj > line else 'Under',
                'decision': self._decision(abs(edge_pct), 5.0, 2.5),
            })
        return props
    
    # ---- PITCHER PROPS ----
    def project_pitcher_props(self):
        """Project pitcher prop bets."""
        props = []
        for prop in self.g.get('pitcher_props', []):
            proj = float(prop['projection'])
            line = float(prop['line'])
            edge_pct = self._edge(proj, line) if line > 0 else 0
            
            props.append({
                'pitcher': prop['pitcher'],
                'stat': prop['stat'],
                'line': line,
                'projection': round(proj, 2),
                'edge_pct': edge_pct,
                'lean': 'Over' if proj > line else 'Under',
                'decision': self._decision(abs(edge_pct), 5.0, 2.5),
            })
        return props
    
    # ---- MARKET ANALYSIS ----
    def analyze_markets(self, runs_proj: Dict, pitcher_analysis: Dict):
        """Analyze all betting markets."""
        fg = runs_proj['full_game']
        f5 = runs_proj['f5']
        fg_total = fg['total']
        f5_total_val = f5['total']
        fg_run_diff = fg['run_diff']
        f5_run_diff = f5['run_diff']
        
        ml = self.g['market_lines']
        
        markets = {}
        
        # Moneyline
        home_win_prob = self._win_prob_from_run_diff(fg_run_diff)
        ml_edge_pct = self._edge(home_win_prob * 100, ml.get('home_ml_implied', 50))
        markets['moneyline'] = {
            'home_team': self.g['home_team']['name'],
            'away_team': self.g['away_team']['name'],
            'home_win_prob': round(home_win_prob, 3),
            'away_win_prob': round(1 - home_win_prob, 3),
            'home_ml': ml['home_ml'],
            'away_ml': ml['away_ml'],
            'edge_pct': round(ml_edge_pct, 1),
            'decision': self._decision(abs(ml_edge_pct), 5.0, 2.5),
            'lean': self.g['home_team']['name'] if home_win_prob > 0.5 else self.g['away_team']['name'],
        }
        
        # Run Line
        rl_edge = abs(fg_run_diff) - abs(ml.get('run_line', 1.5))
        markets['run_line'] = {
            'line': ml['run_line'],
            'model_run_diff': round(fg_run_diff, 2),
            'edge': round(rl_edge, 2),
            'decision': self._decision(abs(rl_edge) * 5, 5.0, 2.5),
        }
        
        # Total
        total_edge_pct = self._edge(fg_total, ml['total'])
        markets['total'] = {
            'line': ml['total'],
            'model_total': round(fg_total, 2),
            'edge_pct': total_edge_pct,
            'decision': self._decision(abs(total_edge_pct), 4.0, 2.0),
            'lean': 'Over' if fg_total > ml['total'] else 'Under',
        }
        
        # F5 Moneyline
        f5_home_win = self._win_prob_from_run_diff(f5_run_diff)
        markets['f5_ml'] = {
            'home_win_prob': round(f5_home_win, 3),
            'away_win_prob': round(1 - f5_home_win, 3),
            'home_f5_ml': ml.get('home_f5_ml', 'N/A'),
            'away_f5_ml': ml.get('away_f5_ml', 'N/A'),
            'lean': self.g['home_team']['name'] if f5_home_win > 0.5 else self.g['away_team']['name'],
        }
        
        # F5 Total
        f5_total_edge = self._edge(f5_total_val, ml.get('f5_total', 4.5))
        markets['f5_total'] = {
            'line': ml.get('f5_total', 4.5),
            'model_total': round(f5_total_val, 2),
            'edge_pct': f5_total_edge,
            'decision': self._decision(abs(f5_total_edge), 5.0, 2.5),
            'lean': 'Over' if f5_total_val > ml.get('f5_total', 4.5) else 'Under',
        }
        
        return markets
    
    # ---- RUN FULL ANALYSIS ----
    def run(self) -> Dict:
        """Run complete game analysis."""
        g = self.g
        print(f"\nAnalyzing: {g['home_team']['name']} vs {g['away_team']['name']}")
        print(f"  Venue: {g['venue']} | Pitchers: {g['home_pitcher']['name']} vs {g['away_pitcher']['name']}")
        
        results = {}
        
        # 1. Pitcher Analysis
        results['pitchers'] = self.analyze_pitchers()
        
        # 2. Team Analysis
        results['teams'] = self.analyze_teams()
        
        # 3. Run Projections
        runs = self.project_runs()
        results['run_projections'] = runs
        
        # 4. First Inning
        results['first_inning'] = self.project_first_inning()
        
        # 5. Markets
        results['markets'] = self.analyze_markets(runs, results['pitchers'])
        
        # 6. Player Props
        results['player_props'] = self.project_player_props()
        
        # 7. Pitcher Props
        results['pitcher_props'] = self.project_pitcher_props()
        
        # Metadata
        results['meta'] = {
            'date': g['date'],
            'venue': g['venue'],
            'weather': g.get('weather', 'N/A'),
        }
        
        return results


# ============================================================================
# DISCORD PUSH
# ============================================================================

def push_mlb_to_discord(game_title: str, results: Dict, webhook_url: str = None) -> bool:
    """Push MLB analysis to Discord with rich embed."""
    try:
        import requests
    except ImportError:
        print("  [X] requests not installed")
        return False
    
    if not webhook_url:
        webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url or webhook_url == "None":
        print("  [X] DISCORD_WEBHOOK_URL not set")
        return False
    
    m = results['markets']
    fi = results['first_inning']
    rp = results['run_projections']
    pp = results['player_props']
    pk = results['pitcher_props']
    
    # Determine color
    has_bet = any(d.get('decision') == 'BET' for d in [m['moneyline'], m['total'], m['f5_total']] if isinstance(d, dict))
    color = 3066993 if has_bet else 16776960
    
    fields = []
    
    # Game Info
    fields.append({
        "name": "GAME INFO",
        "value": (
            f"**{results['meta']['venue']}**\n"
            f"**Pitchers:** {results['pitchers']['home_pitcher']['name']} vs {results['pitchers']['away_pitcher']['name']}\n"
            f"Weather: {results['meta']['weather']}"
        ),
        "inline": False
    })
    
    # Score Projection
    fg = rp['full_game']
    f5 = rp['f5']
    fields.append({
        "name": "SCORE PROJECTION",
        "value": (
            f"**Full Game:** {m['moneyline']['home_team']} {fg['home_runs']:.1f} - {m['moneyline']['away_team']} {fg['away_runs']:.1f}\n"
            f"**Total:** {fg['total']:.1f} | **Run Diff:** {fg['run_diff']:+.1f}\n"
            f"**F5 Total:** {f5['total']:.1f}"
        ),
        "inline": False
    })
    
    # Moneyline + Run Line
    ml = m['moneyline']
    rl = m['run_line']
    fields.append({
        "name": "MONEYLINE & RUN LINE",
        "value": (
            f"**ML:** {ml['home_team']} {ml['home_win_prob']:.1%} | {ml['away_team']} {ml['away_win_prob']:.1%}\n"
            f"**ML Edge:** {ml['edge_pct']:+.1f}% | **Decision:** {ml['decision']}\n"
            f"**Run Line:** Model {rl['model_run_diff']:+.1f} vs Line {rl['line']} | **{rl['decision']}**"
        ),
        "inline": False
    })
    
    # Totals
    t = m['total']
    ft = m['f5_total']
    fields.append({
        "name": "TOTALS (FG & F5)",
        "value": (
            f"**FG Total:** Model {t['model_total']:.1f} vs {t['line']} | Edge: {t['edge_pct']:+.1f}%\n"
            f"**Decision:** {t['decision']} **{t['lean']}**\n"
            f"**F5 Total:** Model {ft['model_total']:.1f} vs {ft['line']} | Edge: {ft['edge_pct']:+.1f}%\n"
            f"**Decision:** {ft['decision']} **{ft['lean']}**"
        ),
        "inline": False
    })
    
    # NRFI/YRFI
    fields.append({
        "name": "FIRST INNING",
        "value": (
            f"**YRFI:** {fi['prob_yrfi']:.1%} | **NRFI:** {fi['prob_nrfi']:.1%}\n"
            f"**Lean:** {fi['lean']} ({fi['total_1st']:.2f} projected runs)"
        ),
        "inline": False
    })
    
    # Player Props
    if pp:
        pp_lines = []
        for p in pp:
            sym = "+" if p['decision'] == 'BET' else ("~" if p['decision'] == 'LEAN' else "-")
            pp_lines.append(f"{sym} {p['player']} {p['stat']}: {p['decision']} {p['lean']} {p['line']} (Proj: {p['projection']}, Edge: {p['edge_pct']:+.1f}%)")
        fields.append({
            "name": "PLAYER PROPS",
            "value": "\n".join(pp_lines[:8]),
            "inline": False
        })
    
    # Pitcher Props
    if pk:
        pk_lines = []
        for p in pk:
            sym = "+" if p['decision'] == 'BET' else ("~" if p['decision'] == 'LEAN' else "-")
            pk_lines.append(f"{sym} {p['pitcher']} {p['stat']}: {p['decision']} {p['lean']} {p['line']} (Proj: {p['projection']}, Edge: {p['edge_pct']:+.1f}%)")
        fields.append({
            "name": "PITCHER PROPS",
            "value": "\n".join(pk_lines[:6]),
            "inline": False
        })
    
    embed = {
        "title": f":baseball: {game_title}",
        "description": f"**MLB — {results['meta']['date']}**",
        "color": color,
        "fields": fields,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "footer": {"text": "MultiSportPredict • MLB • ML • F5 • Props"}
    }
    
    try:
        resp = requests.post(webhook_url, json={"embeds": [embed]},
                             headers={"Content-Type": "application/json"}, timeout=15)
        if resp.status_code in (200, 204):
            print(f"  [OK] Pushed to Discord")
            return True
        print(f"  [X] Discord error: HTTP {resp.status_code}")
        return False
    except Exception as e:
        print(f"  [X] Discord error: {e}")
        return False


# ============================================================================
# CONSOLE OUTPUT
# ============================================================================

def print_results(game_label: str, results: Dict):
    """Print formatted results."""
    sep = "=" * 72
    print(f"\n{sep}")
    print(f"  {game_label}")
    print(f"  {results['meta']['venue']} | {results['meta']['date']}")
    print(f"{sep}")
    
    # Pitchers
    p = results['pitchers']
    print(f"\n--- PITCHERS ---")
    print(f"  Home: {p['home_pitcher']['name']} (ERA: {p['home_pitcher']['era']}, K/9: {p['home_pitcher']['k9']})")
    print(f"  Away: {p['away_pitcher']['name']} (ERA: {p['away_pitcher']['era']}, K/9: {p['away_pitcher']['k9']})")
    print(f"  Edge: {p['winner']}")
    
    # Score
    fg = results['run_projections']['full_game']
    f5 = results['run_projections']['f5']
    ml = results['markets']['moneyline']
    print(f"\n--- PROJECTED SCORE ---")
    print(f"  FG: {ml['home_team']} {fg['home_runs']:.1f} - {ml['away_team']} {fg['away_runs']:.1f} (Total: {fg['total']:.1f})")
    print(f"  F5: {ml['home_team']} {f5['home_runs']:.1f} - {ml['away_team']} {f5['away_runs']:.1f} (Total: {f5['total']:.1f})")
    
    # Markets
    print(f"\n--- MARKETS ---")
    print(f"  ML: {ml['home_team']} {ml['home_win_prob']:.1%} | {ml['decision']:4s} | Edge: {ml['edge_pct']:+.1f}%")
    t = results['markets']['total']
    print(f"  Total: {t['model_total']:.1f} vs {t['line']} | {t['decision']:4s} {t['lean']:5s} | Edge: {t['edge_pct']:+.1f}%")
    ft = results['markets']['f5_total']
    print(f"  F5 Total: {ft['model_total']:.1f} vs {ft['line']} | {ft['decision']:4s} {ft['lean']:5s} | Edge: {ft['edge_pct']:+.1f}%")
    
    # First Inning
    fi = results['first_inning']
    print(f"\n--- FIRST INNING ---")
    print(f"  YRFI: {fi['prob_yrfi']:.1%} | NRFI: {fi['prob_nrfi']:.1%} | Lean: {fi['lean']}")
    
    # Props
    print(f"\n--- PLAYER PROPS ---")
    for p in results.get('player_props', []):
        print(f"  [{p['decision']:4s}] {p['player']} {p['stat']}: {p['lean']} {p['line']} (Proj: {p['projection']})")
    
    print(f"\n--- PITCHER PROPS ---")
    for p in results.get('pitcher_props', []):
        print(f"  [{p['decision']:4s}] {p['pitcher']} {p['stat']}: {p['lean']} {p['line']} (Proj: {p['projection']})")
    
    print(f"\n{sep}\n")


# ============================================================================
# GAME DATA
# ============================================================================

def get_game1_data() -> Dict:
    """Game 1: LA Dodgers vs San Diego Padres"""
    return {
        'date': 'July 2, 2026',
        'venue': 'Dodger Stadium, Los Angeles, CA',
        'weather': '72F, Sunny, Wind 8mph W',
        'park_factor': 1.02,  # Dodger Stadium slight hitter-friendly
        'home_team': {
            'name': 'LA Dodgers',
            'short': 'LAD',
            'rpg': 5.2,       # Elite offense
            'ops': 0.782,
            'era': 3.85,
            'whip': 1.22,
            'k_rate': 0.23,
            'first_inning_rpg': 0.62,
        },
        'away_team': {
            'name': 'San Diego Padres',
            'short': 'SD',
            'rpg': 4.6,
            'ops': 0.748,
            'era': 3.95,
            'whip': 1.25,
            'k_rate': 0.22,
            'first_inning_rpg': 0.52,
        },
        'home_pitcher': {
            'name': 'Roki Sasaki (RHP)',
            'era': 4.88,
            'xfip': 4.35,
            'k9': 9.0,
            'bb9': 3.8,
            'whip': 1.35,
            'hr9': 1.1,
            'first_inning_era': 5.20,
        },
        'away_pitcher': {
            'name': 'Randy Vasquez (RHP)',
            'era': 4.45,
            'xfip': 4.60,
            'k9': 7.2,
            'bb9': 3.2,
            'whip': 1.32,
            'hr9': 1.3,
            'first_inning_era': 4.80,
        },
        'market_lines': {
            'home_ml': -180,
            'away_ml': +155,
            'home_ml_implied': 64.3,
            'run_line': 1.5,
            'total': 9.0,
            'home_f5_ml': -190,
            'away_f5_ml': +160,
            'f5_total': 4.5,
        },
        'player_props': [
            {'player': 'Shohei Ohtani', 'team': 'LAD', 'stat': 'Total Bases', 'line': 1.5, 'projection': 2.1},
            {'player': 'Freddie Freeman', 'team': 'LAD', 'stat': 'RBIs', 'line': 0.5, 'projection': 0.7},
            {'player': 'Mookie Betts', 'team': 'LAD', 'stat': 'Total Bases', 'line': 1.5, 'projection': 1.8},
            {'player': 'Will Smith', 'team': 'LAD', 'stat': 'Total Bases', 'line': 0.5, 'projection': 1.0},
            {'player': 'Fernando Tatis Jr.', 'team': 'SD', 'stat': 'Total Bases', 'line': 1.5, 'projection': 1.6},
            {'player': 'Manny Machado', 'team': 'SD', 'stat': 'Total Bases', 'line': 1.5, 'projection': 1.4},
            {'player': 'Xander Bogaerts', 'team': 'SD', 'stat': 'Hits', 'line': 0.5, 'projection': 0.9},
        ],
        'pitcher_props': [
            {'pitcher': 'Roki Sasaki', 'stat': 'Strikeouts', 'line': 6.5, 'projection': 7.8},
            {'pitcher': 'Randy Vasquez', 'stat': 'Strikeouts', 'line': 4.5, 'projection': 3.8},
            {'pitcher': 'Roki Sasaki', 'stat': 'Walks', 'line': 2.5, 'projection': 2.8},
            {'pitcher': 'Randy Vasquez', 'stat': 'Hits Allowed', 'line': 5.5, 'projection': 6.2},
        ],
    }


def get_game2_data() -> Dict:
    """Game 2: LA Angels vs Seattle Mariners"""
    return {
        'date': 'July 2, 2026',
        'venue': 'T-Mobile Park, Seattle, WA',
        'weather': 'Indoor (Retractable Roof)',
        'park_factor': 0.93,  # T-Mobile pitcher-friendly
        'home_team': {
            'name': 'Seattle Mariners',
            'short': 'SEA',
            'rpg': 4.1,
            'ops': 0.712,
            'era': 3.65,
            'whip': 1.18,
            'k_rate': 0.25,
            'first_inning_rpg': 0.44,
        },
        'away_team': {
            'name': 'LA Angels',
            'short': 'LAA',
            'rpg': 4.0,
            'ops': 0.705,
            'era': 4.15,
            'whip': 1.28,
            'k_rate': 0.26,   # High K rate - good for Miller
            'first_inning_rpg': 0.42,
        },
        'home_pitcher': {
            'name': 'Bryce Miller (RHP)',
            'era': 1.97,
            'xfip': 2.45,
            'k9': 9.8,
            'bb9': 2.1,
            'whip': 0.98,
            'hr9': 0.6,
            'first_inning_era': 1.85,
        },
        'away_pitcher': {
            'name': 'Walbert Urena (RHP)',
            'era': 3.98,
            'xfip': 4.10,
            'k9': 7.5,
            'bb9': 3.2,
            'whip': 1.28,
            'hr9': 0.9,
            'first_inning_era': 3.80,
        },
        'market_lines': {
            'home_ml': -160,
            'away_ml': +135,
            'home_ml_implied': 61.5,
            'run_line': 1.5,
            'total': 7.5,
            'home_f5_ml': -165,
            'away_f5_ml': +140,
            'f5_total': 4.0,
        },
        'player_props': [
            {'player': 'Julio Rodriguez', 'team': 'SEA', 'stat': 'Total Bases', 'line': 1.5, 'projection': 1.7},
            {'player': 'Jorge Soler', 'team': 'LAA', 'stat': 'Home Runs', 'line': 0.5, 'projection': 0.18},
            {'player': 'Cal Raleigh', 'team': 'SEA', 'stat': 'Total Bases', 'line': 0.5, 'projection': 0.9},
            {'player': 'Randy Arozarena', 'team': 'SEA', 'stat': 'Total Bases', 'line': 0.5, 'projection': 0.8},
        ],
        'pitcher_props': [
            {'pitcher': 'Bryce Miller', 'stat': 'Strikeouts', 'line': 6.5, 'projection': 8.2},
            {'pitcher': 'Walbert Urena', 'stat': 'Walks', 'line': 2.5, 'projection': 3.1},
            {'pitcher': 'Bryce Miller', 'stat': 'Hits Allowed', 'line': 4.5, 'projection': 3.8},
            {'pitcher': 'Walbert Urena', 'stat': 'Strikeouts', 'line': 4.5, 'projection': 4.2},
        ],
    }


# ============================================================================
# MAIN
# ============================================================================

def main():
    sep = "=" * 72
    print(f"\n{sep}")
    print("  MLB ANALYSIS — July 2, 2026")
    print("  LA Dodgers vs San Diego Padres")
    print("  LA Angels vs Seattle Mariners")
    print(f"{sep}\n")
    
    games = [
        ("LAD vs SD", get_game1_data()),
        ("SEA vs LAA", get_game2_data()),
    ]
    
    all_results = {}
    
    for label, data in games:
        analyzer = MLBGameAnalyzer(data)
        results = analyzer.run()
        all_results[label] = results
        print_results(label, results)
    
    # Save to file
    out_dir = Path("output/mlb")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "mlb_july2_2026.json"
    with open(out_path, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  [i] Results saved to: {out_path}")
    
    # Discord push
    print(f"\n--- DISCORD PUSH ---")
    for label, data in games:
        results = all_results[label]
        game_title = f"{data['home_team']['name']} vs {data['away_team']['name']}"
        push_mlb_to_discord(game_title, results)
    
    print(f"\n{sep}")
    print("  Analysis Complete! Discord pushed.")
    print(f"{sep}\n")


if __name__ == "__main__":
    main()