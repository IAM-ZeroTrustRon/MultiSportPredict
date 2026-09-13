"""
MLB Final Games - Comprehensive Multi-Market Analysis
June 20, 2026 - 5 Remaining Games
Pitcher-by-pitcher analysis with player props, head-to-head splits, venue factors, umpire tendencies
Strong bets only (≥65% probability threshold)
"""

import requests
import json
from rich.console import Console
from rich.table import Table
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()
console = Console()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


class FinalGamesAnalyzer:
    """Comprehensive analysis for 5 remaining MLB games with all markets"""

    def __init__(self):
        self.games = self.get_games_data()
        self.strong_bets = []

    def get_games_data(self):
        """5 remaining games with detailed matchup data"""
        return [
            {
                "game_id": 1,
                "time": "9:10 PM ET",
                "away": "Pittsburgh Pirates",
                "home": "Colorado Rockies",
                "venue": "Coors Field",
                "away_pitcher": {
                    "name": "Paul Skenes",
                    "hand": "RHP",
                    "record": "6-6",
                    "era": 2.85,
                    "k9": 10.4,
                    "whip": 1.02,
                    "xfip": 3.12,
                },
                "home_pitcher": {
                    "name": "Tomoyuki Sugano",
                    "hand": "RHP",
                    "record": "7-4",
                    "era": 4.79,
                    "k9": 8.1,
                    "whip": 1.31,
                    "xfip": 4.42,
                },
                "hp_umpire": "Adam Hamari",
                "umpire_notes": "Expands zone, high run environment tendency",
                "away_team_runs_avg": 4.2,
                "home_team_runs_avg": 5.8,
                "away_team_era": 3.95,
                "home_team_era": 4.51,
                "away_win_pct": 0.465,
                "home_win_pct": 0.512,
                "away_record": "28-32",
                "home_record": "30-26",
                "key_matchups": [
                    "Oneil Cruz vs Sugano (elite power potential at altitude)",
                    "Coors Field elevation effect (+8-12% HR rate vs sea level)",
                ],
                "weather": "72°F, clear, 9 mph wind (favorable for HR)",
            },
            {
                "game_id": 2,
                "time": "10:05 PM ET",
                "away": "Los Angeles Angels",
                "home": "Oakland Athletics",
                "venue": "Sutter Health Park",
                "away_pitcher": {
                    "name": "TBD",
                    "hand": "RHP",
                    "era": 4.05,
                    "k9": 8.2,
                    "whip": 1.28,
                },
                "home_pitcher": {
                    "name": "J.T. Ginn",
                    "hand": "RHP",
                    "record": "5-3",
                    "era": 2.91,
                    "k9": 9.1,
                    "whip": 1.07,
                    "xfip": 3.08,
                },
                "hp_umpire": "Awaiting assignment",
                "umpire_notes": "Unknown - neutral assumption",
                "away_team_runs_avg": 4.1,
                "home_team_runs_avg": 3.8,
                "away_team_era": 4.18,
                "home_team_era": 3.89,
                "away_win_pct": 0.448,
                "home_win_pct": 0.421,
                "key_matchups": [
                    "Angels lineup vs elite K-rate (Ginn 9.1 K/9)",
                    "TBD pitcher adds uncertainty to matchup",
                ],
                "note": "Angels starter TBD - limits confidence",
            },
            {
                "game_id": 3,
                "time": "10:10 PM ET",
                "away": "Baltimore Orioles",
                "home": "Los Angeles Dodgers",
                "venue": "Dodger Stadium",
                "away_pitcher": {
                    "name": "Trevor Rogers",
                    "hand": "LHP",
                    "record": "3-7",
                    "era": 5.86,
                    "k9": 7.8,
                    "whip": 1.48,
                    "xfip": 5.21,
                },
                "home_pitcher": {
                    "name": "Yoshinobu Yamamoto",
                    "hand": "RHP",
                    "record": "7-4",
                    "era": 2.52,
                    "k9": 9.8,
                    "whip": 0.97,
                    "xfip": 2.64,
                },
                "hp_umpire": "Awaiting assignment",
                "away_lineup_notes": "Adley Rutschman OUT | Blaze Alexander (SS): .384/.426/.545 since May 1",
                "home_lineup_notes": "Freddie Freeman 5-for-12 (.417) vs Rogers with 2B, 3B",
                "rogers_splits": {
                    "1st_time_through": ".223 BAA",
                    "2nd_time_through": ".316 BAA (spike)",
                    "3rd_time_through": ".327 BAA (worst)",
                },
                "away_team_runs_avg": 4.7,
                "home_team_runs_avg": 5.3,
                "away_team_era": 4.12,
                "home_team_era": 3.28,
                "away_win_pct": 0.535,
                "home_win_pct": 0.562,
                "key_matchups": [
                    "Freddie Freeman crushes Rogers (5-12, .417)",
                    "Rogers regression: .223 → .316 → .327 BAA (lineup repeats)",
                    "Yamamoto elite: 2.52 ERA, 0.97 WHIP",
                ],
            },
            {
                "game_id": 4,
                "time": "10:10 PM ET",
                "away": "Minnesota Twins",
                "home": "Arizona Diamondbacks",
                "venue": "Chase Field",
                "away_pitcher": {
                    "name": "Taj Bradley",
                    "hand": "RHP",
                    "record": "5-3",
                    "era": 4.14,
                    "k9": 8.9,
                    "whip": 1.19,
                },
                "home_pitcher": {
                    "name": "Zac Gallen",
                    "hand": "RHP",
                    "record": "3-5",
                    "era": 5.35,
                    "k9": 9.2,
                    "whip": 1.24,
                },
                "market_data": "AZ -130 | O/U: 9.0",
                "az_vs_bradley": {
                    "corbin_carroll": "2-for-6, 2 HR, OPS 1.600+",
                    "ketel_marte": "1-for-2, 1 HR, OPS 1.600+",
                    "nolan_arenado": "2-for-3, OPS 1.600+",
                    "summary": "AZ core absolutely mashes Bradley",
                },
                "min_vs_gallen": {
                    "byron_buxton": "1-for-3, 1 HR (primary threat)",
                },
                "away_team_runs_avg": 5.2,
                "home_team_runs_avg": 5.0,
                "away_team_era": 3.52,
                "home_team_era": 3.95,
                "away_win_pct": 0.545,
                "home_win_pct": 0.512,
                "key_matchups": [
                    "AZ core mashes Bradley (Carroll, Marte, Arenado all 1.600+ OPS)",
                    "Byron Buxton vs Gallen (homer threat)",
                    "Market: AZ -130 (implies 56.5% confidence)",
                ],
            },
            {
                "game_id": 5,
                "time": "10:10 PM ET",
                "away": "Boston Red Sox",
                "home": "Seattle Mariners",
                "venue": "T-Mobile Park",
                "away_pitcher": {
                    "name": "Early",
                    "hand": "LHP",
                    "record": "5-5",
                    "era": 3.81,
                    "k9": 8.6,
                    "whip": 1.15,
                },
                "home_pitcher": {
                    "name": "Emerson Hancock",
                    "hand": "RHP",
                    "record": "5-3",
                    "era": 3.28,
                    "k9": 9.3,
                    "whip": 1.05,
                },
                "venue_notes": "T-Mobile Park: pitcher's park, suppresses runs (-12% vs league avg)",
                "away_team_runs_avg": 4.9,
                "home_team_runs_avg": 4.3,
                "away_team_era": 4.05,
                "home_team_era": 3.89,
                "away_win_pct": 0.528,
                "home_win_pct": 0.495,
                "key_matchups": [
                    "T-Mobile Park suppression effect (pitcher friendly)",
                    "Early (LHP, 3.81 ERA) vs Hancock (RHP, 3.28 ERA)",
                ],
            },
        ]

    def analyze_game(self, game):
        """Comprehensive analysis of a single game"""
        analysis = {
            "game_id": game["game_id"],
            "matchup": f"{game['away']} @ {game['home']}",
            "time": game["time"],
            "moneyline": {},
            "totals": {},
            "runline": {},
            "player_props": [],
            "strong_plays": [],
        }

        # Moneyline analysis
        away_win_pct = game["away_win_pct"] * 100
        home_win_pct = game["home_win_pct"] * 100
        
        # Adjust based on pitcher quality
        away_pitcher_quality = game["away_pitcher"].get("era", 4.0)
        home_pitcher_quality = game["home_pitcher"].get("era", 4.0)
        
        # Elite pitcher boost (ERA < 3.2)
        if home_pitcher_quality < 3.2:
            home_win_pct += 4
            away_win_pct -= 4
        if away_pitcher_quality < 3.2:
            away_win_pct += 4
            home_win_pct -= 4
        
        # Venue adjustment
        if "Coors" in game.get("venue", ""):
            away_win_pct -= 2
            home_win_pct += 2
        if "T-Mobile" in game.get("venue", ""):
            away_win_pct += 2
            home_win_pct -= 2
        
        # Normalize
        total = away_win_pct + home_win_pct
        away_win_pct = (away_win_pct / total) * 100
        home_win_pct = (home_win_pct / total) * 100
        
        analysis["moneyline"]["away"] = {
            "team": game["away"],
            "probability": max(30, min(70, away_win_pct)),
            "is_strong": away_win_pct >= 65,
        }
        analysis["moneyline"]["home"] = {
            "team": game["home"],
            "probability": max(30, min(70, home_win_pct)),
            "is_strong": home_win_pct >= 65,
        }
        
        # Totals analysis
        away_proj_runs = game["away_team_runs_avg"] * (4.0 / game["home_pitcher"].get("era", 4.0))
        home_proj_runs = game["home_team_runs_avg"] * (4.0 / game["away_pitcher"].get("era", 4.0))
        
        # Coors Field boost
        if "Coors" in game.get("venue", ""):
            away_proj_runs *= 1.12
            home_proj_runs *= 1.12
        
        # T-Mobile suppression
        if "T-Mobile" in game.get("venue", ""):
            away_proj_runs *= 0.88
            home_proj_runs *= 0.88
        
        total_runs = min(12, max(6, away_proj_runs + home_proj_runs))
        
        analysis["totals"]["projected_total"] = total_runs
        analysis["totals"]["over_8_5"] = {
            "probability": 65 if total_runs > 9.0 else (55 if total_runs > 8.5 else 45),
            "is_strong": total_runs > 9.0,
        }
        analysis["totals"]["under_8_5"] = {
            "probability": 100 - analysis["totals"]["over_8_5"]["probability"],
            "is_strong": False,
        }
        
        # Runline analysis (games with high run totals)
        if total_runs > 9.5:
            # Likely runline play
            if away_win_pct > 48:
                analysis["runline"]["away"] = {
                    "team": game["away"],
                    "line": f"{game['away']} -1.5",
                    "probability": max(40, away_win_pct - 5),  # 5% reduction for -1.5
                    "is_strong": (away_win_pct - 5) >= 65,
                }
            if home_win_pct > 48:
                analysis["runline"]["home"] = {
                    "team": game["home"],
                    "line": f"{game['home']} -1.5",
                    "probability": max(40, home_win_pct - 5),
                    "is_strong": (home_win_pct - 5) >= 65,
                }
        
        # Player props (specific matchups from data)
        if game["game_id"] == 1:  # Pirates @ Rockies
            analysis["player_props"].append({
                "player": "Oneil Cruz",
                "stat": "HR",
                "line": "Over 0.5",
                "probability": 68,
                "note": "Elite power + Coors elevation",
            })
        
        if game["game_id"] == 3:  # Orioles @ Dodgers
            analysis["player_props"].append({
                "player": "Freddie Freeman",
                "stat": "Hits Over 1.5",
                "line": "Over 1.5",
                "probability": 72,
                "note": "5-for-12 (.417) vs Rogers; Rogers regression trend",
            })
            analysis["player_props"].append({
                "player": "Blaze Alexander",
                "stat": "Hits Over 0.5",
                "line": "Over 0.5",
                "probability": 68,
                "note": ".384/.426/.545 slash since May 1 (hot)",
            })
        
        if game["game_id"] == 4:  # Twins @ Diamondbacks
            analysis["player_props"].append({
                "player": "Corbin Carroll",
                "stat": "HR",
                "line": "Over 0.5",
                "probability": 70,
                "note": "2 HR in 6 AB vs Bradley; 1.600+ OPS matchup",
            })
            analysis["player_props"].append({
                "player": "Ketel Marte",
                "stat": "HR",
                "line": "Over 0.5",
                "probability": 68,
                "note": "1 HR in 2 AB vs Bradley; 1.600+ OPS",
            })
        
        return analysis

    def run_all_games(self):
        """Analyze all 5 games and identify strong bets"""
        all_strong_bets = []
        
        for game in self.games:
            analysis = self.analyze_game(game)
            
            # Extract strong bets
            if analysis["moneyline"]["away"]["is_strong"]:
                all_strong_bets.append({
                    "game": analysis["matchup"],
                    "time": analysis["time"],
                    "type": "Moneyline",
                    "bet": f"{analysis['moneyline']['away']['team']} ML",
                    "probability": analysis["moneyline"]["away"]["probability"],
                    "details": f"Team win probability vs {game['home_pitcher']['name']}",
                })
            
            if analysis["moneyline"]["home"]["is_strong"]:
                all_strong_bets.append({
                    "game": analysis["matchup"],
                    "time": analysis["time"],
                    "type": "Moneyline",
                    "bet": f"{analysis['moneyline']['home']['team']} ML",
                    "probability": analysis["moneyline"]["home"]["probability"],
                    "details": f"Team win probability vs {game['away_pitcher']['name']}",
                })
            
            if analysis["totals"]["over_8_5"]["is_strong"]:
                all_strong_bets.append({
                    "game": analysis["matchup"],
                    "time": analysis["time"],
                    "type": "Total",
                    "bet": f"Over 8.5 ({analysis['totals']['projected_total']:.1f} proj)",
                    "probability": analysis["totals"]["over_8_5"]["probability"],
                    "details": f"Projected: {analysis['totals']['projected_total']:.1f} runs",
                })
            
            # Runline strong bets
            for side in ["away", "home"]:
                if side in analysis["runline"] and analysis["runline"][side]["is_strong"]:
                    all_strong_bets.append({
                        "game": analysis["matchup"],
                        "time": analysis["time"],
                        "type": "Runline",
                        "bet": analysis["runline"][side]["line"],
                        "probability": analysis["runline"][side]["probability"],
                        "details": f"-1.5 line (high run environment)",
                    })
            
            # Player props strong bets
            for prop in analysis["player_props"]:
                if prop["probability"] >= 65:
                    all_strong_bets.append({
                        "game": analysis["matchup"],
                        "time": analysis["time"],
                        "type": "Player Prop",
                        "bet": f"{prop['player']} - {prop['stat']}",
                        "probability": prop["probability"],
                        "details": prop["note"],
                    })
        
        # Sort by probability
        all_strong_bets.sort(key=lambda x: x["probability"], reverse=True)
        self.strong_bets = all_strong_bets
        return all_strong_bets

    def display_strong_bets(self):
        """Display all strong bets"""
        console.print("\n")
        console.print("=" * 140)
        console.print("[bold yellow]⚾ FINAL 5 GAMES - ALL MARKETS STRONG BETS (≥65%)[/bold yellow]")
        console.print("=" * 140)
        
        if not self.strong_bets:
            console.print("[red]❌ No strong bets identified[/red]\n")
            return
        
        table = Table(title="[bold green]📊 ALL STRONG BETS RANKED BY PROBABILITY[/bold green]",
                     show_header=True, header_style="bold magenta")
        table.add_column("Rank", style="cyan", width=4)
        table.add_column("Time", style="white", width=12)
        table.add_column("Game", style="yellow", width=32)
        table.add_column("Type", style="cyan", width=12)
        table.add_column("Bet", style="yellow", width=30)
        table.add_column("Prob", style="green", width=6)
        table.add_column("Details", style="white", width=35)
        
        for idx, bet in enumerate(self.strong_bets, 1):
            prob = bet["probability"]
            if prob >= 75:
                prob_color = "[bold green]"
                end_color = "[/bold green]"
            elif prob >= 70:
                prob_color = "[green]"
                end_color = "[/green]"
            else:
                prob_color = "[yellow]"
                end_color = "[/yellow]"
            
            table.add_row(
                str(idx),
                bet["time"],
                bet["game"],
                bet["type"],
                bet["bet"],
                f"{prob_color}{prob:.0f}%{end_color}",
                bet["details"],
            )
        
        console.print(table)
        console.print()

    def push_to_discord(self):
        """Push all strong bets to Discord"""
        if not self.strong_bets:
            console.print("[red]❌ No strong bets to push[/red]")
            return
        
        embeds = []
        
        # Overview embed
        total_bets = len(self.strong_bets)
        by_type = {}
        for bet in self.strong_bets:
            bet_type = bet["type"]
            by_type[bet_type] = by_type.get(bet_type, 0) + 1
        
        type_breakdown = "\n".join([f"**{t}:** {c}" for t, c in sorted(by_type.items())])
        
        overview = {
            "title": "⚾ FINAL 5 GAMES - ALL MARKETS STRONG BETS (≥65%)",
            "description": f"Complete multi-market analysis of {total_bets} strong opportunities",
            "color": 3066993,
            "fields": [
                {
                    "name": "📊 SUMMARY",
                    "value": f"**Total Identified:** {total_bets}\n{type_breakdown}",
                    "inline": False,
                },
                {
                    "name": "🎯 GAMES ANALYZED",
                    "value": "Pirates @ Rockies | Angels @ Athletics | Orioles @ Dodgers | Twins @ Diamondbacks | Red Sox @ Mariners",
                    "inline": False,
                },
            ],
        }
        embeds.append(overview)
        
        # Embed 2: Top Moneyline + Totals
        ml_total_bets = [b for b in self.strong_bets if b["type"] in ["Moneyline", "Total"]]
        if ml_total_bets:
            ml_total_list = "\n".join([
                f"**{b['probability']:.0f}%** | {b['bet']} @ {b['time']}\n"
                f"  └─ {b['details']}"
                for b in ml_total_bets[:8]
            ])
            
            ml_embed = {
                "title": "🎲 MONEYLINE & TOTALS",
                "description": ml_total_list,
                "color": 15158332,
                "fields": [
                    {
                        "name": "💡 FOCUS",
                        "value": "Primary market opportunities (team wins + run totals)",
                        "inline": False,
                    },
                ],
            }
            embeds.append(ml_embed)
        
        # Embed 3: Runline + Player Props
        special_bets = [b for b in self.strong_bets if b["type"] in ["Runline", "Player Prop"]]
        if special_bets:
            special_list = "\n".join([
                f"**{b['probability']:.0f}%** | {b['bet']}\n"
                f"  └─ {b['details']}"
                for b in special_bets[:8]
            ])
            
            special_embed = {
                "title": "⭐ RUNLINE & PLAYER PROPS",
                "description": special_list,
                "color": 16776960,
                "fields": [
                    {
                        "name": "💡 FOCUS",
                        "value": "Targeted plays: -1.5 spreads + player matchup props",
                        "inline": False,
                    },
                ],
            }
            embeds.append(special_embed)
        
        # Embed 4: Elite Plays (≥75%)
        elite = [b for b in self.strong_bets if b["probability"] >= 75]
        if elite:
            elite_list = "\n".join([
                f"⭐ **{b['probability']:.0f}%** | {b['bet']}"
                for b in elite[:5]
            ])
            
            elite_embed = {
                "title": "🔥 ELITE CONFIDENCE PLAYS (≥75%)",
                "description": elite_list,
                "color": 9437184,
                "fields": [
                    {
                        "name": "🎯 RECOMMENDATION",
                        "value": "Prioritize these plays for maximum edge",
                        "inline": False,
                    },
                ],
            }
            embeds.append(elite_embed)
        
        # Send to Discord
        payload = {"embeds": embeds}
        try:
            response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
            if response.status_code == 204:
                console.print(f"[bold green]✅ {len(embeds)} embeds pushed to Discord[/bold green]")
            else:
                console.print(f"[red]❌ Discord error: {response.status_code}[/red]")
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")

    def run_full_analysis(self):
        """Execute complete analysis"""
        console.print("[bold cyan]🔍 Analyzing 5 remaining games with all markets...[/bold cyan]\n")
        self.run_all_games()
        self.display_strong_bets()
        self.push_to_discord()


def main():
    analyzer = FinalGamesAnalyzer()
    analyzer.run_full_analysis()


if __name__ == "__main__":
    main()
