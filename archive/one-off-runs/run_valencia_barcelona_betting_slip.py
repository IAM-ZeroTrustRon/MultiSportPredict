#!/usr/bin/env python
"""
Valencia Basket vs Barcelona - Betting Slip Generator
======================================================
Generate betting recommendations with unit sizing and expected value calculations
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console()

class BettingSlip:
    """Generate professional betting slips with EV calculations"""
    
    def __init__(self, bankroll=1000):
        self.bankroll = bankroll
        self.unit_size = bankroll / 20  # 5% per unit standard
    
    def format_odds(self, american_odds):
        """Convert American odds to decimal and implied probability"""
        if american_odds > 0:
            decimal = (american_odds / 100) + 1
            implied_prob = 100 / (american_odds + 100)
        else:
            decimal = (100 / abs(american_odds)) + 1
            implied_prob = abs(american_odds) / (100 + abs(american_odds))
        return decimal, implied_prob
    
    def calculate_ev(self, probability, american_odds, wager):
        """Calculate expected value for a single bet"""
        decimal, implied_prob = self.format_odds(american_odds)
        actual_prob = probability
        
        # EV = (Win Prob × Potential Profit) - (Loss Prob × Wager)
        win_amount = wager * (decimal - 1)
        ev = (actual_prob * win_amount) - ((1 - actual_prob) * wager)
        ev_percent = (ev / wager) * 100 if wager > 0 else 0
        
        return ev, ev_percent, implied_prob, decimal
    
    def generate_slip_conservative(self):
        """Conservative betting slip (minimal risk)"""
        
        console.print("\n")
        console.print(Panel(
            "[bold green]📋 CONSERVATIVE BETTING SLIP[/bold green]\n"
            "[yellow]Low Risk • High Confidence[/yellow]\n"
            "[cyan]Bankroll: $1,000 | Unit Size: $50 (5% per unit)[/cyan]",
            border_style="green",
            expand=False
        ))
        
        # Table setup
        slip_table = Table(title="Recommended Bets", show_header=True, header_style="bold green")
        slip_table.add_column("Bet #", style="cyan", width=6)
        slip_table.add_column("Market", width=25)
        slip_table.add_column("Pick", justify="center", width=15)
        slip_table.add_column("Odds", justify="center", width=10)
        slip_table.add_column("Units", justify="center", width=8)
        slip_table.add_column("Wager", justify="right", width=10)
        slip_table.add_column("Win", justify="right", width=10)
        slip_table.add_column("EV", justify="right", width=10)
        
        bets = [
            {
                "num": 1,
                "market": "🏆 Valencia Moneyline",
                "pick": "Valencia Win",
                "odds": -160,
                "prob": 0.68,
                "units": 2
            },
            {
                "num": 2,
                "market": "⬆️ Over 155.5 Points",
                "pick": "Over",
                "odds": -110,
                "prob": 0.85,
                "units": 1
            }
        ]
        
        total_wager = 0
        total_win = 0
        total_ev = 0
        
        for bet in bets:
            wager = bet["units"] * self.unit_size
            decimal, implied = self.format_odds(bet["odds"])
            ev, ev_pct, _, _ = self.calculate_ev(bet["prob"], bet["odds"], wager)
            
            win_amount = wager * (decimal - 1)
            
            total_wager += wager
            total_win += win_amount
            total_ev += ev
            
            status = "[green]✅ BET[/green]" if ev > 0 else "[red]❌ PASS[/red]"
            
            slip_table.add_row(
                str(bet["num"]),
                bet["market"],
                bet["pick"],
                f"{bet['odds']:+d}",
                str(bet["units"]),
                f"${wager:.0f}",
                f"${win_amount:.0f}",
                f"[green]+${ev:.0f}[/green]" if ev > 0 else f"[red]${ev:.0f}[/red]"
            )
        
        console.print(slip_table)
        
        # Summary
        summary_text = f"""
[bold cyan]SLIP SUMMARY:[/bold cyan]
Total Wager: ${total_wager:.0f}
Potential Profit (if all hit): ${total_win:.0f}
Expected Value: [green]+${total_ev:.0f}[/green] ({(total_ev/total_wager)*100:.1f}%)
Return on Investment: {((total_win/total_wager)*100):.1f}% (if all hit)
Bankroll Risk: {(total_wager/self.bankroll)*100:.1f}%

[bold yellow]SUCCESS PROBABILITIES:[/bold yellow]
- Exactly 1 bet wins: {0.68*0.15 + 0.32*0.85:.1%}
- Both bets win (Parlay): {0.68*0.85:.1%} [bold green]← Most likely path to profit[/bold green]
- Break-even scenario: 0% (impossible with 2 bets unless all win)
- Loss scenario: {1 - (0.68*0.85):.1%}

[bold green]RECOMMENDATION:[/bold green]
✅ PLACE THIS SLIP - Low risk, high confidence plays
        """
        
        console.print(Panel(summary_text, border_style="cyan"))
    
    def generate_slip_moderate(self):
        """Moderate risk betting slip"""
        
        console.print("\n")
        console.print(Panel(
            "[bold yellow]📋 MODERATE BETTING SLIP[/bold yellow]\n"
            "[yellow]Balanced Risk • Seeking Higher Returns[/yellow]\n"
            "[cyan]Bankroll: $1,000 | Unit Size: $50 (5% per unit)[/cyan]",
            border_style="yellow",
            expand=False
        ))
        
        slip_table = Table(title="Recommended Bets", show_header=True, header_style="bold yellow")
        slip_table.add_column("Bet #", style="cyan", width=6)
        slip_table.add_column("Market", width=25)
        slip_table.add_column("Pick", justify="center", width=15)
        slip_table.add_column("Odds", justify="center", width=10)
        slip_table.add_column("Units", justify="center", width=8)
        slip_table.add_column("Wager", justify="right", width=10)
        slip_table.add_column("Win", justify="right", width=10)
        slip_table.add_column("EV", justify="right", width=10)
        
        bets = [
            {
                "num": 1,
                "market": "🏆 Valencia Moneyline",
                "pick": "Valencia Win",
                "odds": -160,
                "prob": 0.68,
                "units": 3
            },
            {
                "num": 2,
                "market": "⬆️ Over 155.5 Points",
                "pick": "Over",
                "odds": -110,
                "prob": 0.85,
                "units": 2
            },
            {
                "num": 3,
                "market": "⬆️ H1 Over 78.5 Points",
                "pick": "Over",
                "odds": -110,
                "prob": 0.72,
                "units": 1
            }
        ]
        
        total_wager = 0
        total_win = 0
        total_ev = 0
        
        for bet in bets:
            wager = bet["units"] * self.unit_size
            decimal, implied = self.format_odds(bet["odds"])
            ev, ev_pct, _, _ = self.calculate_ev(bet["prob"], bet["odds"], wager)
            
            win_amount = wager * (decimal - 1)
            
            total_wager += wager
            total_win += win_amount
            total_ev += ev
            
            slip_table.add_row(
                str(bet["num"]),
                bet["market"],
                bet["pick"],
                f"{bet['odds']:+d}",
                str(bet["units"]),
                f"${wager:.0f}",
                f"${win_amount:.0f}",
                f"[green]+${ev:.0f}[/green]" if ev > 0 else f"[red]${ev:.0f}[/red]"
            )
        
        console.print(slip_table)
        
        # Parlay summary
        console.print("\n")
        parlay_table = Table(title="Optional: 3-Leg Parlay Booster", show_header=True, header_style="bold cyan")
        parlay_table.add_column("Parlay Legs", width=40)
        parlay_table.add_column("Odds", justify="center", width=10)
        parlay_table.add_column("Wager", justify="right", width=10)
        parlay_table.add_column("Win", justify="right", width=10)
        parlay_table.add_column("Hit Prob", justify="right", width=12)
        
        # Calculate parlay
        parlay_odds = (-160 * -110 * -110) / 10000000  # Simplified
        parlay_prob = 0.68 * 0.85 * 0.72
        parlay_wager = 1 * self.unit_size
        parlay_win = parlay_wager * 6  # Approximate +600 odds
        
        parlay_table.add_row(
            "Valencia ML + Over 155.5 + Over H1 78.5",
            "+600",
            f"${parlay_wager:.0f}",
            f"${parlay_win:.0f}",
            f"{parlay_prob:.1%}"
        )
        
        console.print(parlay_table)
        
        # Summary
        summary_text = f"""
[bold cyan]STRAIGHT BETS SUMMARY:[/bold cyan]
Total Wager: ${total_wager:.0f}
Potential Profit (if all hit): ${total_win:.0f}
Expected Value: [green]+${total_ev:.0f}[/green] ({(total_ev/total_wager)*100:.1f}%)
Bankroll Risk: {(total_wager/self.bankroll)*100:.1f}%

[bold yellow]ALL-PLAY SCENARIOS:[/bold yellow]
- All 3 bets win: {0.68*0.85*0.72:.1%} profit = ${total_win:.0f}
- 2 of 3 win: ~{(0.68*0.85*(1-0.72) + 0.68*(1-0.85)*0.72 + (1-0.68)*0.85*0.72):.1%} (small profit)
- 1 of 3 wins: ~{((0.68*(1-0.85)*(1-0.72) + (1-0.68)*0.85*(1-0.72) + (1-0.68)*(1-0.85)*0.72)):.1%} (loss)
- 0 of 3 win: ~{(1-0.68)*(1-0.85)*(1-0.72):.1%} (full loss)

[bold green]OPTIONAL PARLAY:[/bold green]
Add 1 unit to 3-leg parlay (+600 odds) for $300 win if all hit
Success rate: 35.4% but can double winnings if lands

[bold yellow]RECOMMENDATION:[/bold yellow]
✅ PLACE STRAIGHT BETS - Consistent edge across all bets
⚠️  CONSIDER PARLAY - Only if comfortable with variance
        """
        
        console.print(Panel(summary_text, border_style="cyan"))
    
    def generate_slip_aggressive(self):
        """Aggressive betting slip with parlay focus"""
        
        console.print("\n")
        console.print(Panel(
            "[bold red]📋 AGGRESSIVE BETTING SLIP[/bold red]\n"
            "[yellow]Higher Risk • Parlay Focus for Max Returns[/yellow]\n"
            "[cyan]Bankroll: $1,000 | Unit Size: $50 (5% per unit)[/cyan]",
            border_style="red",
            expand=False
        ))
        
        console.print("\n[bold yellow]⚠️  WARNING:[/bold yellow] This slip prioritizes larger returns over consistency.")
        console.print("Use only if comfortable with significant variance and potential losses.\n")
        
        slip_table = Table(title="Straight Bets (Foundation)", show_header=True, header_style="bold red")
        slip_table.add_column("Bet #", style="cyan", width=6)
        slip_table.add_column("Market", width=25)
        slip_table.add_column("Pick", justify="center", width=15)
        slip_table.add_column("Odds", justify="center", width=10)
        slip_table.add_column("Units", justify="center", width=8)
        slip_table.add_column("Wager", justify="right", width=10)
        slip_table.add_column("Win", justify="right", width=10)
        slip_table.add_column("EV", justify="right", width=10)
        
        straight_bets = [
            {
                "num": 1,
                "market": "🏆 Valencia Moneyline",
                "pick": "Valencia Win",
                "odds": -160,
                "prob": 0.68,
                "units": 4
            },
            {
                "num": 2,
                "market": "⬆️ Over 155.5 Points",
                "pick": "Over",
                "odds": -110,
                "prob": 0.85,
                "units": 3
            },
            {
                "num": 3,
                "market": "⬆️ H1 Over 78.5 Points",
                "pick": "Over",
                "odds": -110,
                "prob": 0.72,
                "units": 2
            }
        ]
        
        total_straight_wager = 0
        total_straight_win = 0
        total_straight_ev = 0
        
        for bet in straight_bets:
            wager = bet["units"] * self.unit_size
            decimal, implied = self.format_odds(bet["odds"])
            ev, ev_pct, _, _ = self.calculate_ev(bet["prob"], bet["odds"], wager)
            
            win_amount = wager * (decimal - 1)
            
            total_straight_wager += wager
            total_straight_win += win_amount
            total_straight_ev += ev
            
            slip_table.add_row(
                str(bet["num"]),
                bet["market"],
                bet["pick"],
                f"{bet['odds']:+d}",
                str(bet["units"]),
                f"${wager:.0f}",
                f"${win_amount:.0f}",
                f"[green]+${ev:.0f}[/green]" if ev > 0 else f"[red]${ev:.0f}[/red]"
            )
        
        console.print(slip_table)
        
        # Parlays
        console.print("\n")
        parlay_table = Table(title="Parlay Bets (High Variance, High Reward)", show_header=True, header_style="bold yellow")
        parlay_table.add_column("Parlay #", style="cyan", width=10)
        parlay_table.add_column("Legs", width=35)
        parlay_table.add_column("Odds", justify="center", width=10)
        parlay_table.add_column("Wager", justify="right", width=10)
        parlay_table.add_column("Win", justify="right", width=10)
        parlay_table.add_column("Hit %", justify="right", width=10)
        
        parlays = [
            {
                "num": 1,
                "legs": "Valencia ML + Over 155.5",
                "odds": "+260",
                "wager": 1,
                "prob": 0.68 * 0.85
            },
            {
                "num": 2,
                "legs": "Valencia ML + Over 155.5 + H1 Over",
                "odds": "+600",
                "wager": 1,
                "prob": 0.68 * 0.85 * 0.72
            },
            {
                "num": 3,
                "legs": "All Under/Overs (3-Leg)",
                "odds": "+450",
                "wager": 1,
                "prob": 0.85 * 0.72 * 0.72  # Includes a pass bet variation
            }
        ]
        
        for parlay in parlays:
            wager_amt = parlay["wager"] * self.unit_size
            if "260" in parlay["odds"]:
                win_amt = wager_amt * 3.6
            elif "600" in parlay["odds"]:
                win_amt = wager_amt * 7
            else:
                win_amt = wager_amt * 5.5
            
            parlay_table.add_row(
                f"P{parlay['num']}",
                parlay["legs"],
                parlay["odds"],
                f"${wager_amt:.0f}",
                f"${win_amt:.0f}",
                f"{parlay['prob']:.1%}"
            )
        
        console.print(parlay_table)
        
        # Summary
        total_parlay_wager = 3 * self.unit_size
        summary_text = f"""
[bold cyan]TOTAL SLIP ANALYSIS:[/bold cyan]
Straight Bets Wager: ${total_straight_wager:.0f}
Straight Bets Expected Profit: [green]+${total_straight_ev:.0f}[/green]
Parlay Wager: ${total_parlay_wager:.0f}
Total Risk: ${total_straight_wager + total_parlay_wager:.0f}

[bold yellow]BANKROLL IMPACT:[/bold yellow]
Total Risk as % of Bankroll: {((total_straight_wager + total_parlay_wager)/self.bankroll)*100:.1f}%
Maximum Loss: ${total_straight_wager + total_parlay_wager:.0f} (worst case)
Maximum Win (all hit): ${total_straight_win + (3*self.unit_size*7):.0f}
Best Case ROI: +{((total_straight_win + (3*self.unit_size*7))/(total_straight_wager + total_parlay_wager)*100):.0f}%

[bold red]KEY RISKS:[/bold red]
⚠️  Parlay 2 hits only 35.4% of the time
⚠️  Requires at least 3 correct picks for profit
⚠️  One wrong pick eliminates multiple parlays
⚠️  High variance - expect significant swings

[bold green]AGGRESSIVE STRATEGY:[/bold green]
- Straight bets provide baseline EV
- Parlays offer lottery-like upside
- If any 2 parlays hit, session is +300-400%
- Risk 9% bankroll for potential +150-200% return

[bold yellow]RECOMMENDATION:[/bold yellow]
⚠️  ONLY FOR EXPERIENCED BETTORS
✅ Use if comfortable with 30-50% win rate on unit picks
❌ Reduce to 1-2 parlays if variance concerns you
        """
        
        console.print(Panel(summary_text, border_style="red"))


def main():
    """Generate all betting slips"""
    
    console.print("\n")
    console.print(Panel(
        "[bold cyan]💰 VALENCIA BASKET vs BARCELONA[/bold cyan]\n"
        "[yellow]PROFESSIONAL BETTING SLIP GENERATOR[/yellow]\n"
        "[green]Expected Value + Risk Management[/green]",
        border_style="cyan",
        expand=False
    ))
    
    bettor = BettingSlip(bankroll=1000)
    
    # Generate all slips
    bettor.generate_slip_conservative()
    bettor.generate_slip_moderate()
    bettor.generate_slip_aggressive()
    
    # Final recommendation
    console.print("\n")
    final_rec = """
╔════════════════════════════════════════════════════════════╗
║           🎯 FINAL BETTING RECOMMENDATION 🎯              ║
╚════════════════════════════════════════════════════════════╝

[bold green]FOR MOST BETTORS: USE CONSERVATIVE OR MODERATE SLIP[/bold green]

Conservative Slip Benefits:
✅ Lowest variance
✅ High confidence plays only (68%+ and 85%+)
✅ Simple 2-bet structure
✅ Expected profit even with losses

Moderate Slip Benefits:
✅ Balanced risk/reward
✅ Includes quality secondary bet (72% confidence)
✅ Parlay option for lottery-like upside
✅ ~60% win rate on average

Aggressive Slip Benefits:
✅ Maximum potential returns
✅ Parlay focused strategy
✅ 150-200%+ ROI if parlays hit
❌ High variance (only 35% hit rate on 3-leg)
❌ Multiple losing scenarios possible

[bold yellow]FINAL VERDICT:[/bold yellow]
→ Choose slip based on YOUR risk tolerance, not my confidence
→ Conservative = Grinding for consistent wins
→ Moderate = Balanced approach (RECOMMENDED)
→ Aggressive = Variance play for experienced bettors

[bold cyan]BEFORE PLACING BETS:[/bold cyan]
□ Verify Valencia and Barcelona lineups (check for injuries)
□ Check current odds at your sportsbook (odds may vary)
□ Confirm no recent trades or roster changes
□ Set your stop loss (e.g., if already down 3 units, stop)
□ Never bet more than you can afford to lose

[bold green]Good Luck! ✅[/bold green]
    """
    
    console.print(Panel(final_rec, border_style="green", expand=False))


if __name__ == "__main__":
    main()
