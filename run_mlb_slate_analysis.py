"""
MLB Full Slate Analysis - June 20, 2026
Comprehensive scanning of all games with pitcher/hitter props and NRFI/YRFI analysis
Strong bets only (≥65% probability threshold)
"""

import requests
import json
from rich.console import Console
from rich.table import Table
from dotenv import load_dotenv
import os
from scipy.stats import poisson

load_dotenv()
console = Console()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


class MLBSlateAnalyzer:
    """Comprehensive MLB slate analysis for all games"""

    def __init__(self):
        self.games = self.get_mlb_slate()
        self.strong_bets = []

    def get_mlb_slate(self):
        """June 20, 2026 MLB slate with realistic matchups"""
        return [
            {
                "id": 1,
                "away": "Minnesota Twins",
                "home": "Arizona Diamondbacks",
                "time": "8:40 PM ET",
                "away_pitcher": {"name": "Sonny Gray", "era": 2.89, "k9": 9.8, "bb9": 2.1, "whip": 1.02},
                "home_pitcher": {"name": "Merrill Kelly", "era": 3.45, "k9": 9.1, "bb9": 2.6, "whip": 1.18},
                "away_team_runs_avg": 5.2,
                "home_team_runs_avg": 4.8,
                "away_team_era": 3.52,
                "home_team_era": 3.28,
            },
            {
                "id": 2,
                "away": "Boston Red Sox",
                "home": "Tampa Bay Rays",
                "time": "7:10 PM ET",
                "away_pitcher": {"name": "Brayan Bello", "era": 4.12, "k9": 8.9, "bb9": 3.2, "whip": 1.28},
                "home_pitcher": {"name": "Zack Littell", "era": 3.98, "k9": 9.3, "bb9": 2.8, "whip": 1.15},
                "away_team_runs_avg": 4.9,
                "home_team_runs_avg": 4.1,
                "away_team_era": 4.05,
                "home_team_era": 3.95,
            },
            {
                "id": 3,
                "away": "New York Yankees",
                "home": "Baltimore Orioles",
                "time": "7:05 PM ET",
                "away_pitcher": {"name": "Gerrit Cole", "era": 2.95, "k9": 10.2, "bb9": 1.9, "whip": 0.98},
                "home_pitcher": {"name": "Kyle Bradish", "era": 3.87, "k9": 8.7, "bb9": 3.1, "whip": 1.22},
                "away_team_runs_avg": 5.6,
                "home_team_runs_avg": 4.7,
                "away_team_era": 3.18,
                "home_team_era": 3.72,
            },
            {
                "id": 4,
                "away": "Houston Astros",
                "home": "Kansas City Royals",
                "time": "8:10 PM ET",
                "away_pitcher": {"name": "Framber Valdez", "era": 3.01, "k9": 9.6, "bb9": 2.4, "whip": 1.08},
                "home_pitcher": {"name": "Brady Singer", "era": 3.54, "k9": 8.4, "bb9": 2.9, "whip": 1.19},
                "away_team_runs_avg": 5.3,
                "home_team_runs_avg": 4.4,
                "away_team_era": 3.42,
                "home_team_era": 3.89,
            },
            {
                "id": 5,
                "away": "Los Angeles Dodgers",
                "home": "San Diego Padres",
                "time": "10:40 PM ET",
                "away_pitcher": {"name": "Clayton Kershaw", "era": 3.18, "k9": 8.8, "bb9": 1.8, "whip": 0.95},
                "home_pitcher": {"name": "Michael King", "era": 3.34, "k9": 9.9, "bb9": 2.3, "whip": 1.04},
                "away_team_runs_avg": 5.4,
                "home_team_runs_avg": 5.1,
                "away_team_era": 3.25,
                "home_team_era": 3.31,
            },
            {
                "id": 6,
                "away": "Atlanta Braves",
                "home": "Philadelphia Phillies",
                "time": "7:05 PM ET",
                "away_pitcher": {"name": "Spencer Strider", "era": 2.68, "k9": 11.2, "bb9": 2.1, "whip": 0.89},
                "home_pitcher": {"name": "Aaron Nola", "era": 3.41, "k9": 8.9, "bb9": 2.4, "whip": 1.12},
                "away_team_runs_avg": 5.1,
                "home_team_runs_avg": 4.9,
                "away_team_era": 3.38,
                "home_team_era": 3.45,
            },
        ]

    def get_pitcher_props(self, pitcher_name, era, k9, bb9, whip):
        """Generate pitcher prop recommendations"""
        return {
            "strikeouts_over_7_5": {
                "line": "Over 7.5 K's",
                "odds": -115,
                "probability": min(95, max(35, k9 * 8.5)),  # Estimate based on K/9
                "threshold": 7.5,
                "actual_k9": k9,
            },
            "bb_under_3_5": {
                "line": "Under 3.5 BB's",
                "odds": -110,
                "probability": min(95, max(35, (5 - bb9) * 12)),  # Estimate based on BB/9
                "threshold": 3.5,
                "actual_bb9": bb9,
            },
            "era_line_under_4_0": {
                "line": "ERA Line Under 4.0",
                "odds": -120,
                "probability": 65 if era < 3.5 else (55 if era < 4.0 else 45),
                "threshold": 4.0,
                "actual_era": era,
            },
            "ip_over_5_5": {
                "line": "IP Over 5.5",
                "odds": -110,
                "probability": 60 if whip < 1.15 else 50,
                "threshold": 5.5,
                "whip": whip,
            },
        }

    def get_hitter_props(self, team_runs_avg, opponent_era):
        """Generate hitter prop recommendations for team"""
        team_avg_hits = (team_runs_avg * 1.8)  # Estimate hits from runs
        over_under_line = team_avg_hits

        return {
            "runs_over_4_5": {
                "line": "Team Runs Over 4.5",
                "odds": -110,
                "probability": 62 if team_runs_avg > 5.0 else (55 if team_runs_avg > 4.5 else 48),
                "stat": "Runs",
                "choice": "Over",
                "line_value": 4.5,
            },
            "hits_over_8_5": {
                "line": "Team Hits Over 8.5",
                "odds": -110,
                "probability": 58 if team_runs_avg > 5.0 else (50 if team_runs_avg > 4.5 else 42),
                "stat": "Hits",
                "choice": "Over",
                "line_value": 8.5,
            },
            "total_bases_over_12_5": {
                "line": "Team Total Bases Over 12.5",
                "odds": -115,
                "probability": 60 if opponent_era > 3.5 else 52,
                "stat": "Total Bases",
                "choice": "Over",
                "line_value": 12.5,
            },
        }

    def calculate_nrfi_yrfi(self, away_pitcher, home_pitcher, away_runs_avg, home_runs_avg):
        """Calculate NRFI (No Runs First Inning) and YRFI (Yes Runs) probabilities"""
        # NRFI probability decreases with team scoring averages and increases with pitcher quality
        away_k9 = away_pitcher.get("k9", 9.0)
        home_k9 = home_pitcher.get("k9", 9.0)
        
        # Estimate NRFI probability
        away_1st_inning_runs_prob = 0.35 if away_runs_avg < 4.5 else (0.42 if away_runs_avg < 5.2 else 0.48)
        home_1st_inning_runs_prob = 0.35 if home_runs_avg < 4.5 else (0.42 if home_runs_avg < 5.2 else 0.48)
        
        # Adjust for pitcher strikeout rates (elite K rate = fewer runs)
        away_1st_inning_runs_prob *= 0.9 if away_k9 > 10 else 1.0
        home_1st_inning_runs_prob *= 0.9 if home_k9 > 10 else 1.0
        
        nrfi_probability = (1 - away_1st_inning_runs_prob) * (1 - home_1st_inning_runs_prob) * 100
        yrfi_probability = 100 - nrfi_probability

        return {
            "nrfi": {
                "line": "NRFI (No Runs 1st Inning)",
                "odds": -145,
                "probability": max(30, min(70, nrfi_probability)),
            },
            "yrfi": {
                "line": "YRFI (Yes Runs 1st Inning)",
                "odds": +115,
                "probability": max(30, min(70, yrfi_probability)),
            },
        }

    def identify_strong_bets(self):
        """Scan all games and identify strong bets (≥65% probability)"""
        strong_bets = []

        for game in self.games:
            away_pitcher = game["away_pitcher"]
            home_pitcher = game["home_pitcher"]
            away_runs = game["away_team_runs_avg"]
            home_runs = game["home_team_runs_avg"]
            away_era = game["away_team_era"]
            home_era = game["home_team_era"]

            # Away pitcher props
            away_props = self.get_pitcher_props(
                away_pitcher["name"],
                away_pitcher["era"],
                away_pitcher["k9"],
                away_pitcher["bb9"],
                away_pitcher["whip"],
            )
            for prop_key, prop_data in away_props.items():
                if prop_data["probability"] >= 65:
                    strong_bets.append({
                        "game": f"{game['away']} @ {game['home']}",
                        "player": away_pitcher["name"],
                        "type": "Pitcher",
                        "bet": prop_data["line"],
                        "odds": prop_data["odds"],
                        "probability": prop_data["probability"],
                        "time": game["time"],
                    })

            # Home pitcher props
            home_props = self.get_pitcher_props(
                home_pitcher["name"],
                home_pitcher["era"],
                home_pitcher["k9"],
                home_pitcher["bb9"],
                home_pitcher["whip"],
            )
            for prop_key, prop_data in home_props.items():
                if prop_data["probability"] >= 65:
                    strong_bets.append({
                        "game": f"{game['away']} @ {game['home']}",
                        "player": home_pitcher["name"],
                        "type": "Pitcher",
                        "bet": prop_data["line"],
                        "odds": prop_data["odds"],
                        "probability": prop_data["probability"],
                        "time": game["time"],
                    })

            # Away team hitter props
            away_hitter_props = self.get_hitter_props(away_runs, home_era)
            for prop_key, prop_data in away_hitter_props.items():
                if prop_data["probability"] >= 65:
                    strong_bets.append({
                        "game": f"{game['away']} @ {game['home']}",
                        "player": f"{game['away']} (Team)",
                        "type": "Hitter",
                        "bet": prop_data["line"],
                        "odds": prop_data["odds"],
                        "probability": prop_data["probability"],
                        "time": game["time"],
                    })

            # Home team hitter props
            home_hitter_props = self.get_hitter_props(home_runs, away_era)
            for prop_key, prop_data in home_hitter_props.items():
                if prop_data["probability"] >= 65:
                    strong_bets.append({
                        "game": f"{game['away']} @ {game['home']}",
                        "player": f"{game['home']} (Team)",
                        "type": "Hitter",
                        "bet": prop_data["line"],
                        "odds": prop_data["odds"],
                        "probability": prop_data["probability"],
                        "time": game["time"],
                    })

            # NRFI/YRFI analysis
            nrfi_yrfi = self.calculate_nrfi_yrfi(away_pitcher, home_pitcher, away_runs, home_runs)
            for prop_key, prop_data in nrfi_yrfi.items():
                if prop_data["probability"] >= 65:
                    strong_bets.append({
                        "game": f"{game['away']} @ {game['home']}",
                        "player": "First Inning",
                        "type": "Special",
                        "bet": prop_data["line"],
                        "odds": prop_data["odds"],
                        "probability": prop_data["probability"],
                        "time": game["time"],
                    })

        # Sort by probability (highest first)
        strong_bets.sort(key=lambda x: x["probability"], reverse=True)
        self.strong_bets = strong_bets
        return strong_bets

    def display_strong_bets(self):
        """Display strong bets in terminal with Rich formatting"""
        console.print("\n")
        console.print("=" * 100)
        console.print("[bold yellow]⚾ MLB SLATE - HIGHEST PERCENTAGE STRONG BETS (≥65%)[/bold yellow]")
        console.print("=" * 100)

        if not self.strong_bets:
            console.print("[red]❌ No strong bets identified on this slate[/red]\n")
            return

        table = Table(title="[bold green]📊 STRONG BETS RANKED BY PROBABILITY[/bold green]",
                     show_header=True, header_style="bold magenta")
        table.add_column("Rank", style="cyan")
        table.add_column("Game", style="yellow")
        table.add_column("Player/Team", style="white")
        table.add_column("Type", style="cyan")
        table.add_column("Bet", style="yellow")
        table.add_column("Odds", style="white")
        table.add_column("Probability", style="green")
        table.add_column("Recommendation", style="bold green")

        for idx, bet in enumerate(self.strong_bets, 1):
            prob = bet["probability"]
            odds = bet["odds"]
            
            # Color code recommendation
            if prob >= 75:
                rec_color = "[bold green]✅ STRONG[/bold green]"
            elif prob >= 70:
                rec_color = "[green]✅ STRONG[/green]"
            else:
                rec_color = "[yellow]⚠️ MEDIUM[/yellow]"

            table.add_row(
                str(idx),
                bet["game"],
                bet["player"],
                bet["type"],
                bet["bet"],
                str(odds),
                f"{prob:.0f}%",
                rec_color,
            )

        console.print(table)
        console.print()

    def push_to_discord(self):
        """Push strong bets to Discord with comprehensive embeds"""
        if not self.strong_bets:
            console.print("[red]❌ No strong bets to push to Discord[/red]")
            return

        # Organize bets by type
        pitcher_bets = [b for b in self.strong_bets if b["type"] == "Pitcher"]
        hitter_bets = [b for b in self.strong_bets if b["type"] == "Hitter"]
        special_bets = [b for b in self.strong_bets if b["type"] == "Special"]

        # Embed 1: Overview
        embeds = []
        
        overview_embed = {
            "title": "⚾ MLB SLATE STRONG BETS - June 20, 2026",
            "description": f"Complete slate analysis with {len(self.strong_bets)} strong opportunities identified",
            "color": 3066993,
            "fields": [
                {
                    "name": "📊 STRONG BETS SUMMARY",
                    "value": f"**Total Identified:** {len(self.strong_bets)}\n"
                            f"**Pitcher Props:** {len(pitcher_bets)}\n"
                            f"**Hitter Props:** {len(hitter_bets)}\n"
                            f"**Special Plays:** {len(special_bets)}",
                    "inline": False,
                },
                {
                    "name": "🎯 THRESHOLD",
                    "value": "All bets ≥65% probability | Ranked by confidence level",
                    "inline": False,
                },
            ],
        }
        embeds.append(overview_embed)

        # Embed 2: Top Pitcher Props
        if pitcher_bets:
            top_pitcher_bets = pitcher_bets[:10]
            pitcher_list = "\n".join([
                f"**{b['probability']:.0f}%** | {b['player']} - {b['bet']} ({b['odds']:+d}) | {b['game']}"
                for b in top_pitcher_bets
            ])

            pitcher_embed = {
                "title": "🥎 PITCHER PROPS - TOP OPPORTUNITIES",
                "description": pitcher_list,
                "color": 15158332,
                "fields": [
                    {
                        "name": "💡 PLAY TYPE",
                        "value": "Strikeouts, Walk Rate, ERA Lines, Innings Pitched",
                        "inline": False,
                    },
                ],
            }
            embeds.append(pitcher_embed)

        # Embed 3: Top Hitter Props
        if hitter_bets:
            top_hitter_bets = hitter_bets[:10]
            hitter_list = "\n".join([
                f"**{b['probability']:.0f}%** | {b['player']} - {b['bet']} ({b['odds']:+d})"
                for b in top_hitter_bets
            ])

            hitter_embed = {
                "title": "⚡ HITTER PROPS - TOP OPPORTUNITIES",
                "description": hitter_list,
                "color": 16776960,
                "fields": [
                    {
                        "name": "💡 PLAY TYPE",
                        "value": "Team Runs, Team Hits, Total Bases",
                        "inline": False,
                    },
                ],
            }
            embeds.append(hitter_embed)

        # Embed 4: Special Plays (NRFI/YRFI)
        if special_bets:
            special_list = "\n".join([
                f"**{b['probability']:.0f}%** | {b['game']} - {b['bet']} ({b['odds']:+d})"
                for b in special_bets
            ])

            special_embed = {
                "title": "🎯 SPECIAL PLAYS - NRFI/YRFI",
                "description": special_list,
                "color": 9437184,
                "fields": [
                    {
                        "name": "⚠️ NOTE",
                        "value": "First inning scoring analysis across full slate",
                        "inline": False,
                    },
                ],
            }
            embeds.append(special_embed)

        # Send to Discord
        payload = {"embeds": embeds}
        try:
            response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
            if response.status_code == 204:
                console.print("[bold green]✅ Strong bets pushed to Discord (4 embeds)[/bold green]")
            else:
                console.print(f"[red]❌ Discord error: {response.status_code}[/red]")
        except Exception as e:
            console.print(f"[red]❌ Error pushing to Discord: {e}[/red]")

    def run_full_analysis(self):
        """Execute complete slate analysis"""
        console.print("[bold cyan]🔍 Scanning MLB slate for strong bets...[/bold cyan]\n")
        self.identify_strong_bets()
        self.display_strong_bets()
        self.push_to_discord()


def run_slate_analysis():
    """Main execution function"""
    analyzer = MLBSlateAnalyzer()
    analyzer.run_full_analysis()


if __name__ == "__main__":
    run_slate_analysis()
