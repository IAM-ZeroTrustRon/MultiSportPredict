"""Hockey-specific review: separate regulation goals, OT winner and readiness."""
from score_review import market_rows, percent, price, recommendation


def format_review(result):
    p=result["projection"];gate=result["readiness"]
    lines=[f"NHL {result['game_date']} | {result['away_team']} @ {result['home_team']}",
           f"REGULATION GOAL MEANS: {result['home_team']} {p['regulation_home']:.2f} | {result['away_team']} {p['regulation_away']:.2f}",
           f"Model: {result['model_version']} | {gate['status']}"]
    if p.get("final_probability_available"):
        lines.append(f"Expected official final goals (OT/SO included): Home {p['home_points']:.2f} | Away {p['away_points']:.2f}")
    counts=gate["season_games_played"]
    lines.append(f"Current-season games: Home {counts['home']} | Away {counts['away']}; policy minimum {gate['required_games']}")
    lines+=gate["reasons"]
    if result.get('goalie_context'):
        context=result['goalie_context']
        lines.append(f"User-confirmed goalie IDs: Home {context['home']['player_id']} | Away {context['away']['player_id']} (identity only; no numeric goalie adjustment)")
    lines.append("\nCAPTURED MARKETS / MODEL REFERENCES")
    for market in result["markets"]:
        for row in market_rows(result,market):
            ev=percent(row["ev"],True) if row["ev"] is not None else "Unavailable — projection only or no paired price"
            lines.append(f"{row['selection']} | Odds {price(row['price'])} | Probability {percent(row['probability'])} | EV {ev}")
        lines.append("  "+recommendation(result,market))
    v=p["validation"]
    lines.append(f"\nHOLDOUT: {v['games']} games | Goal deviance {v['goal_deviance']:.3f} vs baseline {v['baseline_goal_deviance']:.3f}")
    lines.append("Winner Brier: "+(f"{v['winner_brier']:.3f}" if v["winner_brier"] is not None else "unavailable"))
    lines += ["\nDATA / LIMITATIONS",*("- "+str(x) for x in result["notes"])]
    lines.append("MoneyPuck.com advanced history. Model probabilities are not proven betting returns.")
    return "\n".join(lines)
