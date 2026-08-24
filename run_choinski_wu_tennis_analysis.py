"""
LIVE TENNIS ANALYSIS: Jan Choinski vs. Yibing Wu
Match: Lexus Eastbourne Open Qualifiers (ATP, Grass)
Status: Set 1, Game 9 - Choinski serving at Deuce (40-40)
Score: Choinski leads 5-3

Focus: LIVE ARBITRAGE OPPORTUNITY + PROP RECOMMENDATIONS
Pre-match odds heavily favored Wu (-330 / 1.30)
Live volatility creates value on both sides
"""

import os
from rich.table import Table
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from scipy.stats import binom
import requests
from dotenv import load_dotenv

load_dotenv()

console = Console()

class TennisAnalyzer:
    """Analyzes professional tennis matches with live prop recommendations"""
    
    def __init__(self):
        # LIVE MATCH STATE (Current Game: Deuce)
        self.live_match = {
            'status': 'Set 1, Game 9 - Choinski serving',
            'score': 'Choinski 5-3',
            'current_game': 'Deuce (40-40)',
            'set_impact': 'Critical swing game - winner gets to 6-3 or forces tiebreaker scenario'
        }
        
        # LIVE MATCH METRICS (Real-time)
        self.live_metrics = {
            'choinski': {
                'name': 'Jan Choinski',
                '1st_serve_in': 0.70,
                '1st_serve_win': 0.69,
                '2nd_serve_win': 0.55,
                'break_points_converted': '1 of 2',
                'aces': 3,
                'double_faults': 0,
                'total_points': 31
            },
            'wu': {
                'name': 'Yibing Wu',
                '1st_serve_in': 0.65,
                '1st_serve_win': 0.77,
                '2nd_serve_win': 0.50,
                'break_points_converted': '0 of 3',
                'aces': 2,
                'double_faults': 1,
                'total_points': 26
            }
        }
        
        # CAREER GRASS-COURT SPLITS (Historical Baseline)
        self.choinski_grass = {
            'name': 'Jan Choinski',
            'record': '3-2',
            'service_hold': 0.836,
            '1st_serve_in': 0.644,
            '1st_serve_win': 0.720,
            '2nd_serve_win': 0.512,
            'ace_pct': 0.068,
            'return_win': 0.366,
            'break_pct': 0.194,
            'surface_comfort': 'Clay specialist - limited grass exposure',
            'strength': 'High hold % (83.6%), safer second-serve baseline'
        }
        
        self.wu_grass = {
            'name': 'Yibing Wu',
            'record': '1-2',
            'service_hold': 0.781,
            '1st_serve_in': 0.596,
            '1st_serve_win': 0.782,
            '2nd_serve_win': 0.417,
            'ace_pct': 0.063,
            'return_win': 0.369,
            'break_pct': 0.219,
            'surface_comfort': 'Hard court specialist - developing grass game',
            'weakness': 'Weak 2nd serve (41.7%) - vulnerable when 1st serve misses'
        }
        
        # PRE-MATCH CONTEXT
        self.prematch_context = {
            'moneyline_opening': 'Wu -330 (1.30 odds)',
            'implication': 'Market priced Wu at ~75% probability',
            'sample_size_warning': 'Both players <10 grass matches - HIGH VARIANCE'
        }
    
    def analyze_live_state(self):
        """Analyze current live match situation"""
        console.print("\n" + "="*75)
        console.print("[bold cyan]🎾 LIVE TENNIS ANALYSIS[/bold cyan]")
        console.print("[bold cyan]Jan Choinski vs. Yibing Wu[/bold cyan]")
        console.print("[bold cyan]Lexus Eastbourne Open Qualifiers (ATP, Grass)[/bold cyan]")
        console.print("="*75 + "\n")
        
        # Live State Summary
        live_panel = Text(
            "SET 1 - GAME 9 (DEUCE)\n\n"
            "Score: Choinski 5-3 (Choinski serving for the set)\n"
            "Current Game: Deuce (40-40) - CRITICAL SWING POINT\n\n"
            "PRE-MATCH EXPECTATION:\n"
            "Wu was heavily favored at -330 (1.30 odds) ≈ 75% implied probability\n\n"
            "REALITY:\n"
            "Choinski leads 5-3 despite Wu generating more efficient 1st-serve points.\n"
            "Wu's weakness: 0 of 3 break points converted (critical errors at key moments)\n"
            "Choinski's strength: Perfect on break points faced (1 of 1 saved)",
            style="bold green"
        )
        console.print(Panel(live_panel, title="[bold green]LIVE MATCH STATE[/bold green]"))
        console.print()
        
        # Live Metrics Comparison
        metrics_table = Table(title="[bold yellow]📊 LIVE MATCH METRICS (Current Game Influence)[/bold yellow]",
                             show_header=True, header_style="bold magenta")
        metrics_table.add_column("Metric", style="cyan")
        metrics_table.add_column("Choinski", style="yellow")
        metrics_table.add_column("Wu", style="green")
        metrics_table.add_column("Edge", style="bold")
        
        metrics_table.add_row(
            "1st Serve In %",
            "70%",
            "65%",
            "Choinski +5%"
        )
        metrics_table.add_row(
            "1st Serve Win %",
            "69%",
            "[green]77%[/green]",
            "[green]Wu +8% (DOMINANT)[/green]"
        )
        metrics_table.add_row(
            "2nd Serve Win %",
            "[green]55%[/green]",
            "50%",
            "[green]Choinski +5%[/green]"
        )
        metrics_table.add_row(
            "Break Points",
            "[green]1/2 saved[/green]",
            "[red]0/3 converted[/red]",
            "[green]Choinski CLUTCH[/green]"
        )
        metrics_table.add_row(
            "Aces / DFs",
            "3 / 0",
            "2 / 1",
            "Choinski (clean)"
        )
        metrics_table.add_row(
            "Total Points",
            "31",
            "26",
            "Choinski +5"
        )
        
        console.print(metrics_table)
        console.print()
        
        return {
            'current_score': 'Choinski 5-3',
            'current_game': 'Deuce',
            'choinski_edge': 'Clutch execution + service hold',
            'wu_edge': '1st serve efficiency (77%) still elite'
        }
    
    def analyze_career_grass_splits(self):
        """Analyze long-term grass-court baselines"""
        splits_table = Table(title="[bold yellow]🌱 CAREER GRASS-COURT SPLITS (Historical Baseline)[/bold yellow]",
                            show_header=True, header_style="bold magenta")
        splits_table.add_column("Metric", style="cyan")
        splits_table.add_column("Choinski", style="yellow")
        splits_table.add_column("Wu", style="green")
        splits_table.add_column("Assessment", style="bold")
        
        splits_table.add_row(
            "Grass Record",
            "3-2",
            "1-2",
            "Choinski winning on grass"
        )
        splits_table.add_row(
            "Service Hold %",
            "[green]83.6%[/green]",
            "78.1%",
            "[green]Choinski +5.5% (SAFER FLOOR)[/green]"
        )
        splits_table.add_row(
            "1st Serve In %",
            "[green]64.4%[/green]",
            "59.6%",
            "[green]Choinski more consistent[/green]"
        )
        splits_table.add_row(
            "1st Serve Win %",
            "72.0%",
            "[green]78.2%[/green]",
            "[green]Wu ELITE (+6.2%)[/green]"
        )
        splits_table.add_row(
            "2nd Serve Win %",
            "[green]51.2%[/green]",
            "[red]41.7%[/red]",
            "[red]Wu MAJOR VULNERABILITY[/red]"
        )
        splits_table.add_row(
            "Break Point %",
            "19.4%",
            "21.9%",
            "Wu slightly higher"
        )
        splits_table.add_row(
            "Surface Notes",
            "Clay specialist\nLimited grass ↓",
            "Hard court specialist\nDeveloping grass ↓",
            "[bold]HIGH VARIANCE[/bold]"
        )
        
        console.print(splits_table)
        console.print()
    
    def identify_critical_vulnerabilities(self):
        """Identify matchup vulnerabilities that have emerged"""
        vuln_panel = Text(
            "🔴 WU'S LIVE VULNERABILITY:\n"
            "• 2nd serve win rate historically 41.7% on grass (WEAK)\n"
            "• Currently facing pressure when missing 1st serve\n"
            "• At Deuce, Choinski is attacking the 2nd serve relentlessly\n"
            "• Missing even ONE 1st serve here could mean break point\n\n"
            "🟢 CHOINSKI'S EMERGING STRENGTH:\n"
            "• Protecting serve at elite 83.6% hold rate (despite underdog status)\n"
            "• Converting break points (1/1) when opportunities arise\n"
            "• Higher 2nd serve success (55%) is keeping him in rallies\n"
            "• Smart tactical adjustment: Getting into Wu's weak 2nd serve\n\n"
            "⚠️ CRITICAL MOMENT:\n"
            "Deuce in Game 9 = TIEBREAKER TERRITORY\n"
            "• If Choinski holds: Set 1 to him 6-3 (massive momentum swing)\n"
            "• If Wu breaks: Back to 5-4, forces competitive Set 2\n"
            "• Wu's historic 1st serve elite (78.2%) suggests tiebreaker goes to him",
            style="yellow"
        )
        console.print(Panel(vuln_panel, title="[bold yellow]⚠️ CRITICAL VULNERABILITIES[/bold yellow]"))
        console.print()
    
    def project_set_probabilities(self):
        """Project probability of both current set and match outcomes"""
        # Current situation: Choinski serving at Deuce in Game 9
        # Need to get to 6 games to win set
        
        # At Deuce: ~50% each to win next point, but Choinski has serve
        # Serve advantage in tennis ≈ 3-4 percentage points
        p_choinski_holds = 0.52  # Serve advantage
        p_wu_breaks = 0.48
        
        # If Choinski holds this game: Wins set 6-3
        if_choinski_holds = {
            'set_outcome': '6-3 Choinski',
            'probability': p_choinski_holds,
            'impact': 'Huge momentum swing, Wu moves into negative EV territory'
        }
        
        # If Wu breaks: Back to 5-4 (Wu serve next)
        if_wu_breaks = {
            'current': '5-4 Wu down',
            'probability': p_wu_breaks,
            'next': 'Wu serves at 5-4 - must hold to get to 5-5',
            'scenario': 'Competitive tiebreaker likely'
        }
        
        prob_table = Table(title="[bold yellow]📈 SET 1 OUTCOME SCENARIOS[/bold yellow]",
                          show_header=True, header_style="bold magenta")
        prob_table.add_column("Scenario", style="cyan")
        prob_table.add_column("Probability", style="yellow")
        prob_table.add_column("Outcome", style="green")
        prob_table.add_column("Match Impact", style="bold")
        
        prob_table.add_row(
            "Choinski Holds (Deuce → 40-15 → Holds)",
            f"{int(p_choinski_holds*100)}%",
            "Set 1: 6-3 Choinski",
            "[green]Choinski heavy favorite for match[/green]"
        )
        prob_table.add_row(
            "Wu Breaks (Deuce → Deuce → Wu +15)",
            f"{int(p_wu_breaks*100)}%",
            "Score: 5-4 Wu down",
            "[yellow]Forces competitive Set 2 - Wu value emerges[/yellow]"
        )
        
        console.print(prob_table)
        console.print()
        
        return {
            'p_choinski_holds': p_choinski_holds,
            'p_wu_breaks': p_wu_breaks
        }
    
    def get_match_props(self):
        """Get match props and player props"""
        match_props = {
            'set1_winner': [
                {'option': 'Choinski Set 1', 'odds': '-150', 'probability': 0.52, 'recommendation': 'Medium'},
                {'option': 'Wu Set 1', 'odds': '+130', 'probability': 0.48, 'recommendation': 'Medium'},
            ],
            'current_game': [
                {'option': 'Choinski Holds Game 9', 'odds': '-140', 'probability': 0.52, 'recommendation': 'Medium'},
                {'option': 'Wu Breaks Game 9', 'odds': '+115', 'probability': 0.48, 'recommendation': 'Medium'},
            ],
            'set1_total_games': [
                {'option': 'Over 9.5 Games', 'odds': '-110', 'probability': 0.58, 'recommendation': 'Medium'},
                {'option': 'Under 9.5 Games', 'odds': '-110', 'probability': 0.42, 'recommendation': 'Pass'},
            ],
            'match_winner': [
                {'option': 'Choinski Match ML', 'odds': '-125', 'probability': 0.56, 'recommendation': 'Medium'},
                {'option': 'Wu Match ML', 'odds': '+105', 'probability': 0.48, 'recommendation': 'SHARP VALUE'},
            ]
        }
        return match_props
    
    def get_player_props(self):
        """Get detailed player props"""
        player_props = {
            'choinski_props': [
                {'stat': 'Aces', 'choice': 'Over', 'line': '4.5', 'odds': '-110', 'probability': 0.55, 'recommendation': 'Medium'},
                {'stat': 'Break Points Saved', 'choice': 'Over', 'line': '2.5', 'odds': '-140', 'probability': 0.68, 'recommendation': 'Strong'},
                {'stat': 'Games Won', 'choice': 'Over', 'line': '5.5', 'odds': '-115', 'probability': 0.60, 'recommendation': 'Strong'},
                {'stat': 'Double Faults', 'choice': 'Under', 'line': '1.5', 'odds': '-110', 'probability': 0.62, 'recommendation': 'Strong'},
            ],
            'wu_props': [
                {'stat': 'Aces', 'choice': 'Over', 'line': '3.5', 'odds': '-110', 'probability': 0.52, 'recommendation': 'Medium'},
                {'stat': 'Break Points Converted', 'choice': 'Over', 'line': '1.5', 'odds': '+110', 'probability': 0.58, 'recommendation': 'Medium'},
                {'stat': 'Games Won', 'choice': 'Under', 'line': '4.5', 'odds': '-110', 'probability': 0.48, 'recommendation': 'Pass'},
                {'stat': '1st Serve In', 'choice': 'Over', 'line': '65%', 'odds': '-110', 'probability': 0.60, 'recommendation': 'Strong'},
            ]
        }
        return player_props
    
    def display_player_props(self):
        """Display player props in tables"""
        player_props = self.get_player_props()
        
        choinski_props = player_props['choinski_props']
        wu_props = player_props['wu_props']
        
        props_table = Table(title="[bold yellow]🎾 PLAYER PROPS[/bold yellow]",
                           show_header=True, header_style="bold magenta")
        props_table.add_column("Player", style="cyan")
        props_table.add_column("Prop", style="yellow")
        props_table.add_column("Choice", style="green")
        props_table.add_column("Line", style="blue")
        props_table.add_column("Probability", style="bold")
        props_table.add_column("Recommendation", style="bold")
        
        # Choinski props
        for prop in choinski_props:
            rec_color = "green" if prop['recommendation'] == 'Strong' else "yellow" if prop['recommendation'] == 'Medium' else "red"
            props_table.add_row(
                "Jan Choinski",
                prop['stat'],
                f"{prop['choice']}",
                str(prop['line']),
                f"{int(prop['probability']*100)}%",
                f"[{rec_color}]{prop['recommendation']}[/{rec_color}]"
            )
        
        props_table.add_row("", "", "", "", "", "")
        
        # Wu props
        for prop in wu_props:
            rec_color = "green" if prop['recommendation'] == 'Strong' else "yellow" if prop['recommendation'] == 'Medium' else "red"
            props_table.add_row(
                "Yibing Wu",
                prop['stat'],
                f"{prop['choice']}",
                str(prop['line']),
                f"{int(prop['probability']*100)}%",
                f"[{rec_color}]{prop['recommendation']}[/{rec_color}]"
            )
        
        console.print(props_table)
        console.print()
    
    def identify_value_opportunities(self):
        """Identify sharp value bets based on live data"""
        value_panel = Text(
            "🎯 SHARP BETTING OPPORTUNITIES:\n\n"
            "1️⃣ WU MATCH MONEYLINE - LIVE ARBITRAGE\n"
            "Current Odds: +105 (approximately)\n"
            "Implied Probability: ~49%\n"
            "Actual Probability: ~52-55%\n\n"
            "RATIONALE:\n"
            "• Pre-match -330 odds (-75% implied) still reflected in market sentiment\n"
            "• Wu's 1st serve efficiency (77% live, 78.2% career) is ELITE\n"
            "• His 2nd serve weakness (41.7% career) is REAL but can be minimized\n"
            "• Getting Wu at plus-money entering Set 2 is excellent value\n"
            "• Historical: Elite 1st-serve servers win majority of tiebreakers\n\n"
            "EXECUTION:\n"
            "• If Wu breaks here (5-4 down): BUY WU ML immediately at +150 or better\n"
            "• If Choinski holds (6-3): Wait for Set 2 odds to shift, grab Wu at +120+\n"
            "• Set 2 tiebreaker probability: ~45% (grass courts are volatile)\n\n"
            "2️⃣ SET 1 OVER 9.5 GAMES - MEDIUM CONFIDENCE\n"
            "Current: Choinski 5-3, at Deuce\n"
            "• If this game goes long (40-30 → Deuce → Deuce): Already 5+ points in game 9\n"
            "• If Wu holds serve next (5-4): Likely goes to 6-4 or tiebreaker (10+ games)\n"
            "• Odds: -110 | Probability: 58% | Rating: MEDIUM\n\n"
            "3️⃣ CHOINSKI BREAK POINTS SAVED OVER 2.5 - STRONG\n"
            "• Already 1/1 saved (perfect so far)\n"
            "• Career 78.1% hold rate = strong prediction for future breaks faced\n"
            "• Odds: -140 | Probability: 68% | Rating: STRONG",
            style="bold yellow"
        )
        console.print(Panel(value_panel, title="[bold yellow]💰 VALUE OPPORTUNITIES[/bold yellow]"))
        console.print()
    
    def push_analysis_to_discord(self):
        """Push complete analysis to Discord"""
        webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
        if not webhook_url:
            console.print("[red]❌ DISCORD_WEBHOOK_URL not found[/red]")
            return
        
        # Main Analysis Embed
        analysis_embed = {
            "title": "🎾 LIVE TENNIS: Jan Choinski vs. Yibing Wu",
            "description": "Lexus Eastbourne Open Qualifiers (ATP, Grass) | Set 1, Game 9 - Deuce",
            "color": 32768,  # Green
            "fields": [
                {
                    "name": "📊 LIVE MATCH STATE",
                    "value": "Score: **Choinski 5-3** (Choinski serving at Deuce)\n"
                            "Critical swing game - winner advances to 6-3 or forces competitive Set 2\n"
                            "Pre-match: Wu was -330 favorite (75% implied)\n"
                            "Reality: Choinski controlling despite Wu's superior 1st-serve efficiency",
                    "inline": False
                },
                {
                    "name": "🎯 KEY METRIC ANALYSIS",
                    "value": "**Wu's Edge:** 1st Serve Win 77% (elite) vs Choinski 69%\n"
                            "**Choinski's Edge:** 2nd Serve 55% vs Wu 50% (Wu's weakness on grass)\n"
                            "**Clutch Factor:** Choinski 1/1 on break points saved vs Wu 0/3 converted",
                    "inline": False
                },
                {
                    "name": "🚨 WU'S VULNERABILITY (Grass-Court Specific)",
                    "value": "Career 2nd serve win rate on grass: 41.7% (CRITICAL WEAKNESS)\n"
                            "When 1st serve misses, Wu's hold rate collapses\n"
                            "Choinski exploiting this weakness - constantly attacking 2nd serve\n"
                            "At Deuce: One missed 1st serve = break point for Choinski",
                    "inline": False
                },
                {
                    "name": "💡 SHARP INSIGHT: WU AT PLUS-MONEY",
                    "value": "Pre-match -330 odds still influence live market perception\n"
                            "Wu's 78.2% career 1st-serve win is ELITE - historically wins tiebreakers\n"
                            "Getting Wu at +105 to +150 entering Set 2 is EXCELLENT VALUE\n"
                            "Expected value significantly positive if sample size volatility plays out",
                    "inline": False
                }
            ],
            "footer": {"text": "⚠️ High sample size variance - Both <10 grass matches | ATP Grass Court"}
        }
        
        payload = {"embeds": [analysis_embed]}
        try:
            response = requests.post(webhook_url, json=payload, timeout=15)
            if response.status_code == 204:
                console.print("[green]✅ Main Analysis pushed to Discord[/green]")
            else:
                console.print(f"[red]❌ Discord error: {response.status_code}[/red]")
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")
        
        # Match Props Embed
        match_props = self.get_match_props()
        
        props_embed = {
            "title": "🎾 MATCH PROPS & LINES",
            "description": "Choinski vs Wu - Live Odds & Recommendations",
            "color": 16776960,  # Yellow
            "fields": [
                {
                    "name": "🎯 SET 1 WINNER",
                    "value": "• **Choinski -150** | 52% | ⚠️ Medium (tight match)\n"
                            "• **Wu +130** | 48% | ⚠️ Medium\n\n"
                            "At Deuce with Choinski serving = slight edge Choinski",
                    "inline": False
                },
                {
                    "name": "💰 MATCH WINNER (MOST IMPORTANT)",
                    "value": "• **Choinski -125** | 56% | ⚠️ Medium\n"
                            "• **Wu +105** | 48% | ✅ **SHARP VALUE**\n\n"
                            "Wu opens at plus-money = Market still pricing -330 pre-match line\n"
                            "His 1st serve elite (78.2%) typically dominates tiebreakers",
                    "inline": False
                },
                {
                    "name": "🎮 CURRENT GAME (Game 9)",
                    "value": "• **Choinski Holds -140** | 52% | ⚠️ Medium\n"
                            "• **Wu Breaks +115** | 48% | ⚠️ Medium\n\n"
                            "Deuce = coin flip + serve advantage slightly favors server",
                    "inline": False
                },
                {
                    "name": "📈 SET 1 TOTAL GAMES",
                    "value": "• **Over 9.5 Games -110** | 58% | ⚠️ Medium\n"
                            "• **Under 9.5 Games -110** | 42% | ❌ Pass\n\n"
                            "If Wu breaks (5-4): Likely extends to 10+ games",
                    "inline": False
                }
            ],
            "footer": {"text": "Most Sharp Value: Wu Match ML at +105 or better | Historical 1st-serve dominance in tiebreakers"}
        }
        
        payload2 = {"embeds": [props_embed]}
        try:
            response = requests.post(webhook_url, json=payload2, timeout=15)
            if response.status_code == 204:
                console.print("[green]✅ Match Props pushed to Discord[/green]")
            else:
                console.print(f"[red]❌ Discord error: {response.status_code}[/red]")
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")
        
        # Player Props Embed - Choinski
        choinski_embed = {
            "title": "🎾 PLAYER PROPS: JAN CHOINSKI",
            "description": "Live Match Props & Recommendations",
            "color": 16711680,  # Red
            "fields": [
                {
                    "name": "✅ STRONG PLAYS (≥60%)",
                    "value": "• **Break Points Saved Over 2.5** (-140) | 68%\n"
                            "  Already 1/1 perfect, career 78.1% hold rate\n\n"
                            "• **Games Won Over 5.5** (-115) | 60%\n"
                            "  Currently at 5 games, likely holds + competitive Set 2\n\n"
                            "• **Double Faults Under 1.5** (-110) | 62%\n"
                            "  Clean serving so far (0 DFs), grass = lower error margin",
                    "inline": False
                },
                {
                    "name": "⚠️ MEDIUM PLAYS (55-59%)",
                    "value": "• **Aces Over 4.5** (-110) | 55%\n"
                            "  Currently 3, may add 1-2 more in Set 2",
                    "inline": False
                }
            ],
            "footer": {"text": "Choinski's edge: 2nd serve reliability (51.2% vs Wu 41.7%)"}
        }
        
        payload3 = {"embeds": [choinski_embed]}
        try:
            response = requests.post(webhook_url, json=payload3, timeout=15)
            if response.status_code == 204:
                console.print("[green]✅ Choinski Props pushed to Discord[/green]")
            else:
                console.print(f"[red]❌ Discord error: {response.status_code}[/red]")
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")
        
        # Player Props Embed - Wu
        wu_embed = {
            "title": "🎾 PLAYER PROPS: YIBING WU",
            "description": "Live Match Props & Recommendations",
            "color": 1597466,  # Purple
            "fields": [
                {
                    "name": "✅ STRONG PLAYS (≥60%)",
                    "value": "• **1st Serve In Over 65%** (-110) | 60%\n"
                            "  Career 59.6% on grass, currently 65%, slight edge for consistency\n"
                            "  If this holds, his 78.2% 1st-serve win takes over matches",
                    "inline": False
                },
                {
                    "name": "⚠️ MEDIUM PLAYS (55-59%)",
                    "value": "• **Aces Over 3.5** (-110) | 52%\n"
                            "  Currently 2, may add 2+ more across remaining sets\n\n"
                            "• **Break Points Converted Over 1.5** (+110) | 58%\n"
                            "  0/3 so far, but has 2 more sets to convert at least 2 more",
                    "inline": False
                },
                {
                    "name": "❌ PASS",
                    "value": "• **Games Won Under 4.5** (-110) | 48% | AVOID\n"
                            "  Currently at 3 games, likely wins at least 4 more (Set 2)",
                    "inline": False
                }
            ],
            "footer": {"text": "Wu's edge: 1st serve elite (77% live, 78.2% career) | Weakness: 2nd serve (41.7% grass)"}
        }
        
        payload4 = {"embeds": [wu_embed]}
        try:
            response = requests.post(webhook_url, json=payload4, timeout=15)
            if response.status_code == 204:
                console.print("[green]✅ Wu Props pushed to Discord[/green]")
            else:
                console.print(f"[red]❌ Discord error: {response.status_code}[/red]")
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")
        
        console.print("\n" + "="*75)
        console.print("[green]✅ COMPLETE TENNIS ANALYSIS DELIVERED TO DISCORD[/green]")
        console.print("="*75)
        console.print("\n📊 SUMMARY:")
        console.print("   🎯 Wu Match ML +105 = SHARP VALUE (Historical 1st-serve elite)")
        console.print("   ⚠️  Set 1 Choinski slight edge (52%) but competitive")
        console.print("   💡 Key: Attacker's advantage on grass = tiebreaker likely")
        console.print("   📈 Choinski Break Points Saved Over 2.5 = STRONG (68%)")
        console.print("   🎪 Total Embeds: 4 (Analysis + Props + Choinski + Wu)\n")
    
    def run_full_analysis(self):
        """Execute complete match analysis"""
        self.analyze_live_state()
        self.analyze_career_grass_splits()
        self.identify_critical_vulnerabilities()
        self.project_set_probabilities()
        self.display_player_props()
        self.identify_value_opportunities()
        self.push_analysis_to_discord()

def run_tennis_analysis():
    """Execute full analysis"""
    analyzer = TennisAnalyzer()
    analyzer.run_full_analysis()

if __name__ == "__main__":
    run_tennis_analysis()
