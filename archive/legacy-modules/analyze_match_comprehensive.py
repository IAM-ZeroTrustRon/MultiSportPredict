#!/usr/bin/env python
"""
Comprehensive Soccer Match Analysis with Rich Table Display
============================================================

Runs a full soccer prediction with all markets and displays results in rich table format.
Also identifies additional data and metrics for improved analysis.
"""

import sys
import os
import json
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

# Set up logging
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.layout import Layout
except ImportError:
    print("Installing rich library for table formatting...")
    os.system("pip install rich -q")
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.layout import Layout

console = Console()


def calculate_btts_probability(home_goals: float, away_goals: float) -> float:
    """
    Calculate Both Teams to Score (BTTS) probability using Poisson distribution.
    
    BTTS occurs when both teams score at least 1 goal.
    Uses Poisson CDF: P(both > 0) = 1 - P(home=0) - P(away=0) + P(both=0)
    """
    try:
        from scipy.stats import poisson
        
        # Probability that team scores 0 goals
        home_scores_zero = poisson.pmf(0, home_goals)
        away_scores_zero = poisson.pmf(0, away_goals)
        both_score_zero = home_scores_zero * away_scores_zero
        
        # BTTS = 1 - (both score 0 or one scores 0)
        btts_prob = 1 - (home_scores_zero + away_scores_zero - both_score_zero)
        
        return max(0.0, min(1.0, btts_prob))  # Clamp to [0,1]
    except:
        # Fallback calculation if scipy unavailable
        # Simple approximation: if both teams average >1 goal, BTTS likely
        if home_goals > 0.8 and away_goals > 0.8:
            return 0.65
        elif home_goals > 0.5 and away_goals > 0.5:
            return 0.50
        else:
            return 0.35


def run_soccer_analysis(home: str, away: str, league: str = "World Cup") -> Dict[str, Any]:
    """Run comprehensive soccer analysis."""
    
    console.print(f"\n[bold blue]🔄 Analyzing {home} vs {away}[/bold blue] ({league})\n")
    
    # Import predictor
    try:
        from models.soccer_predictor import SoccerPredictor
    except ImportError as e:
        console.print(f"[red]Error importing SoccerPredictor: {e}[/red]")
        return {}
    
    try:
        predictor = SoccerPredictor(league=league)
        result = predictor.predict(
            features=None,
            model=None,
            home_team=home,
            away_team=away,
            market_line=0.0,
            market_total=2.5,
        )
        return result
    except Exception as e:
        console.print(f"[red]Error running prediction: {e}[/red]")
        import traceback
        traceback.print_exc()
        return {}


def create_markets_table(result: Dict[str, Any]) -> Table:
    """Create rich table with all market recommendations."""
    
    table = Table(
        title="⚽ MARKET RECOMMENDATIONS",
        show_header=True,
        header_style="bold cyan",
        border_style="cyan",
        padding=(0, 1),
    )
    
    table.add_column("Market", style="bold white", width=20)
    table.add_column("Selection", style="bold yellow", width=25)
    table.add_column("Probability", style="green", width=15)
    table.add_column("Confidence", style="magenta", width=15)
    table.add_column("Recommendation", style="bold", width=15)
    
    game = result.get("game", {})
    
    # 1x2 Moneyline Markets
    home_win = game.get("home_win_prob", 0)
    draw = game.get("draw_prob", 0)
    away_win = game.get("away_win_prob", 0)
    
    home_team = game.get("home_team", "Home")
    away_team = game.get("away_team", "Away")
    
    best_1x2 = max(
        [(home_win, f"{home_team} Win"), (draw, "Draw"), (away_win, f"{away_team} Win")],
        key=lambda x: x[0]
    )
    
    table.add_row(
        "1X2 (Moneyline)",
        best_1x2[1],
        f"{best_1x2[0]:.1%}",
        f"{min(best_1x2[0] * 100, 95):.0f}%",
        "BET" if best_1x2[0] > 0.55 else "LEAN" if best_1x2[0] > 0.50 else "PASS"
    )
    
    # Over/Under Markets
    proj_home = game.get("projected_home_goals", 0)
    proj_away = game.get("projected_away_goals", 0)
    proj_total = proj_home + proj_away
    
    over_25_prob = game.get("over_25_prob", None)
    under_25_prob = game.get("under_25_prob", None)
    
    if over_25_prob is not None:
        over_under_rec = "OVER 2.5" if over_25_prob > 0.55 else "UNDER 2.5" if under_25_prob > 0.55 else "PASS"
        table.add_row(
            "Over/Under 2.5",
            f"{'Over' if over_25_prob > 0.5 else 'Under'} 2.5",
            f"{max(over_25_prob, under_25_prob):.1%}",
            f"{max(over_25_prob, under_25_prob) * 100:.0f}%",
            "BET" if max(over_25_prob, under_25_prob) > 0.60 else "LEAN" if max(over_25_prob, under_25_prob) > 0.55 else "PASS"
        )
    else:
        table.add_row(
            "Over/Under 2.5",
            f"{'Over' if proj_total > 2.5 else 'Under'} (Projected {proj_total:.1f})",
            f"{abs(proj_total - 2.5):.2f} edge",
            f"{min(abs(proj_total - 2.5) * 50, 80):.0f}%",
            "OVER" if proj_total > 2.7 else "UNDER" if proj_total < 2.3 else "PASS"
        )
    
    # Both Teams to Score (BTTS) - ALWAYS calculate
    btts_prob = game.get("btts_prob", None)
    
    # If not in model, calculate from projected goals
    if btts_prob is None:
        proj_home = game.get("projected_home_goals", 1.5)
        proj_away = game.get("projected_away_goals", 1.2)
        btts_prob = calculate_btts_probability(proj_home, proj_away)
    
    table.add_row(
        "BTTS (Both Score)",
        "Yes" if btts_prob > 0.5 else "No",
        f"{btts_prob:.1%}",
        f"{abs(btts_prob - 0.5) * 200:.0f}%",
        "BET" if btts_prob > 0.60 else "LEAN" if btts_prob > 0.55 else "PASS"
    )
    
    # Corners
    corner_proj = result.get("corner_projection")
    if corner_proj is not None:
        corners_over_85 = result.get("corners_analysis", {}).get("over_85_prob", 0)
        corners_over_95 = result.get("corners_analysis", {}).get("over_95_prob", 0)
        corners_over_105 = result.get("corners_analysis", {}).get("over_105_prob", 0)
        
        if corners_over_105 > 0:
            table.add_row(
                "Corners O/U 8.5",
                f"Over 8.5 (Proj {corner_proj:.1f})",
                f"{corners_over_85:.1%}",
                f"{corners_over_85 * 100:.0f}%",
                "OVER 8.5" if corners_over_85 > 0.60 else "PASS"
            )
            table.add_row(
                "Corners O/U 9.5",
                f"Over 9.5" if corners_over_95 > 0.5 else "Under 9.5",
                f"{corners_over_95:.1%}",
                f"{corners_over_95 * 100:.0f}%",
                "OVER 9.5" if corners_over_95 > 0.55 else "PASS"
            )
            table.add_row(
                "Corners O/U 10.5",
                f"Over 10.5" if corners_over_105 > 0.5 else "Under 10.5",
                f"{corners_over_105:.1%}",
                f"{corners_over_105 * 100:.0f}%",
                "OVER 10.5" if corners_over_105 > 0.55 else "PASS"
            )
    
    # Team Totals
    home_team_over = game.get("home_team_over_prob")
    away_team_over = game.get("away_team_over_prob")
    
    if home_team_over is not None:
        rec_home = "OVER 1.5" if home_team_over > 0.60 else "UNDER 1.5" if (1 - home_team_over) > 0.60 else "PASS"
        table.add_row(
            f"{home_team} Total O/U",
            f"{'Over' if home_team_over > 0.5 else 'Under'} 1.5",
            f"{home_team_over:.1%}",
            f"{max(home_team_over, 1-home_team_over) * 100:.0f}%",
            rec_home
        )
    
    if away_team_over is not None:
        rec_away = "OVER 1.5" if away_team_over > 0.60 else "UNDER 1.5" if (1 - away_team_over) > 0.60 else "PASS"
        table.add_row(
            f"{away_team} Total O/U",
            f"{'Over' if away_team_over > 0.5 else 'Under'} 1.5",
            f"{away_team_over:.1%}",
            f"{max(away_team_over, 1-away_team_over) * 100:.0f}%",
            rec_away
        )
    
    return table


def create_metrics_table(result: Dict[str, Any]) -> Table:
    """Create table with key statistical metrics."""
    
    table = Table(
        title="📊 MATCH METRICS & STATISTICS",
        show_header=True,
        header_style="bold cyan",
        border_style="cyan",
        padding=(0, 1),
    )
    
    table.add_column("Metric", style="bold white", width=25)
    table.add_column("Home", style="green", width=20)
    table.add_column("Away", style="yellow", width=20)
    
    game = result.get("game", {})
    
    # Projected Goals
    table.add_row(
        "Projected Goals",
        f"{game.get('projected_home_goals', 0):.2f}",
        f"{game.get('projected_away_goals', 0):.2f}"
    )
    
    # Expected Goals
    home_xg = game.get("home_xg", None)
    away_xg = game.get("away_xg", None)
    if home_xg is not None:
        table.add_row("Expected Goals (xG)", f"{home_xg:.2f}", f"{away_xg:.2f}")
    
    # Shots & SOT
    home_shots = game.get("home_shots", None)
    away_shots = game.get("away_shots", None)
    if home_shots is not None:
        table.add_row("Shots", f"{home_shots:.1f}", f"{away_shots:.1f}")
    
    home_sot = game.get("home_sot", None)
    away_sot = game.get("away_sot", None)
    if home_sot is not None:
        table.add_row("Shots on Target", f"{home_sot:.1f}", f"{away_sot:.1f}")
    
    # Possession
    home_poss = game.get("home_possession", None)
    away_poss = game.get("away_possession", None)
    if home_poss is not None:
        table.add_row("Ball Possession", f"{home_poss:.1%}", f"{away_poss:.1%}")
    
    # Pass Accuracy
    home_pass_acc = game.get("home_pass_accuracy", None)
    away_pass_acc = game.get("away_pass_accuracy", None)
    if home_pass_acc is not None:
        table.add_row("Pass Accuracy", f"{home_pass_acc:.1%}", f"{away_pass_acc:.1%}")
    
    # Corners
    home_corners = game.get("home_corners", None)
    away_corners = game.get("away_corners", None)
    if home_corners is not None:
        table.add_row("Corners (Projected)", f"{home_corners:.1f}", f"{away_corners:.1f}")
    
    # Fouls & Yellow Cards
    home_fouls = game.get("home_fouls", None)
    away_fouls = game.get("away_fouls", None)
    if home_fouls is not None:
        table.add_row("Fouls", f"{home_fouls:.1f}", f"{away_fouls:.1f}")
    
    home_yellows = game.get("home_yellow_cards", None)
    away_yellows = game.get("away_yellow_cards", None)
    if home_yellows is not None:
        table.add_row("Yellow Cards (Proj)", f"{home_yellows:.1f}", f"{away_yellows:.1f}")
    
    # Win Probabilities
    table.add_row(
        "[bold]Match Outcome Probability[/bold]",
        "",
        ""
    )
    table.add_row(
        f"  {game.get('home_team', 'Home')} Win",
        f"{game.get('home_win_prob', 0):.1%}",
        "-"
    )
    table.add_row(
        "  Draw",
        f"{game.get('draw_prob', 0):.1%}",
        "-"
    )
    table.add_row(
        f"  {game.get('away_team', 'Away')} Win",
        "-",
        f"{game.get('away_win_prob', 0):.1%}"
    )
    
    return table


def create_additional_metrics_panel() -> Panel:
    """Create panel with additional metrics to collect."""
    
    content = """[bold cyan]ADDITIONAL DATA & METRICS FOR ENHANCED ANALYSIS[/bold cyan]

[bold]1. TEAM STRENGTH INDICATORS[/bold]
   • FIFA/ELO Ratings (real-time team strength)
   • Head-to-Head Historical Records
   • Recent Form (Last 5-10 matches)
   • Home/Away Records
   • Injuries & Suspensions (Player Availability)
   • Manager Experience & Tactical Data

[bold]2. ADVANCED STATISTICAL MODELS[/bold]
   • Dixon-Coles Adjustment (time-decay for recent form)
   • Poisson Distribution Parameters (lambda values)
   • Confidence Intervals (instead of point estimates)
   • Betting Odds Implied Probabilities (Market Efficiency)
   • Sharp Money Detection (sharps vs squares)

[bold]3. CONTEXTUAL FACTORS[/bold]
   • Travel Distance & Fatigue
   • Weather Conditions (Wind, Rain, Temperature)
   • Altitude Effects (if applicable)
   • Grass Type & Pitch Condition
   • Crowd Size & Home Advantage Adjustment
   • Time of Match (Circadian Rhythms)
   • Fixture Congestion (Days since last match)

[bold]4. PLAYER-LEVEL METRICS[/bold]
   • Key Player Availability Status
   • Player xG Contribution (Top Scorers)
   • Player Form (Recent Goals/Assists)
   • Substitution Patterns & Bench Strength
   • Yellow Card Accumulation (Suspension Risk)
   • Minutes Played (Fitness Levels)

[bold]5. MARKET MICROSTRUCTURE[/bold]
   • Line Movement (Opening → Live)
   • Betting Volume & Liquidity
   • Hedging Behavior (Tells you what sharps think)
   • Live Odds Updates (During Match)
   • Asian Handicap Lines
   • Closing Line Value (CLV) Analysis

[bold]6. SITUATIONAL INSIGHTS[/bold]
   • Motivation Levels (Cup vs League Matches)
   • Revenge Factor (After Recent Loss)
   • Derby/Rivalry Effects
   • Tournament Stage Importance
   • Season Progression (Early/Mid/Late Season)
   • Rest Differential Between Teams

[bold]7. PROPRIETARY MODELS[/bold]
   • Machine Learning Ensemble (Multiple models)
   • Sentiment Analysis (Social Media/News)
   • Bookmaker Margin Analysis
   • Kelly Criterion for Bet Sizing
   • Variance Analysis (Match Quality Prediction)
"""
    
    return Panel(content, border_style="magenta", padding=(1, 2))


def main():
    """Main analysis function."""
    
    # Run prediction
    result = run_soccer_analysis("Netherlands", "Sweden", "World Cup")
    
    if not result:
        console.print("[red]Failed to generate predictions[/red]")
        return
    
    # Display markets table
    console.print("\n")
    markets_table = create_markets_table(result)
    console.print(markets_table)
    
    # Display metrics table
    console.print("\n")
    metrics_table = create_metrics_table(result)
    console.print(metrics_table)
    
    # Display additional metrics suggestion
    console.print("\n")
    console.print(create_additional_metrics_panel())
    
    # Print raw result for debugging
    console.print("\n[dim][bold]Raw Prediction Data (for reference):[/bold]")
    game = result.get("game", {})
    for key, value in sorted(game.items()):
        if not isinstance(value, dict):
            console.print(f"  {key}: {value}")
    
    console.print("\n[bold green]✅ Analysis Complete![/bold green]\n")
    
    # Summary recommendation
    console.print(Panel(
        "[bold cyan]SUMMARY[/bold cyan]\n"
        f"Match: Netherlands vs Sweden (World Cup)\n"
        f"Projected Score: {game.get('projected_home_goals', 0):.1f} - {game.get('projected_away_goals', 0):.1f}\n"
        f"Best Opportunity: {'Over 2.5 Goals' if game.get('projected_home_goals', 0) + game.get('projected_away_goals', 0) > 2.7 else 'Under 2.5 Goals' if game.get('projected_home_goals', 0) + game.get('projected_away_goals', 0) < 2.3 else 'Monitor Markets'}\n"
        f"Confidence: High",
        border_style="green",
        padding=(1, 2)
    ))


if __name__ == "__main__":
    main()
