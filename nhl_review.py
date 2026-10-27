"""Hockey-specific review: separate regulation goals, OT winner and readiness."""
from score_review import market_rows, percent, price, recommendation


def verdict_line(result):
    """The single status/verdict for a game, shared by terminal, saved review and Discord.

    A gated game states one verdict, not one per market: the blockers are about the
    fixture, not about each price. Goalie identity is called out by name because it is
    the one blocker that leaves the priced estimate meaningful.
    """
    gate = result["readiness"]
    if gate["eligible"]:
        return gate["status"]
    reasons = gate.get("reasons") or []
    if not reasons:
        return "NO BET — insufficient verified inputs"
    goalie_only = all("goalies" in reason.lower() for reason in reasons)
    if goalie_only:
        suffix = " (model EV shown for information only)" if result.get("estimates_retained") else ""
        return "NO BET — starting goalies unconfirmed" + suffix
    head = reasons[0]
    if len(reasons) > 1:
        head += f" (+{len(reasons) - 1} more blocker(s))"
    return "NO BET — " + head


def format_review(result):
    p = result["projection"]; gate = result["readiness"]
    keep = bool(result.get("estimates_retained"))
    reasons = gate.get("reasons") or []
    lines = [f"NHL • {result['game_date']} | {result['away_team']} @ {result['home_team']}",
             f"HOME: {result['home_team']} | AWAY: {result['away_team']}",
             f"VERDICT: {verdict_line(result)}"]
    if len(reasons) > 1:
        lines.append("Blockers: " + " | ".join(reasons))
    counts = gate["season_games_played"]
    lines += ["",
              f"Projected final goals: {result['home_team']} {p['home_points']:.2f} | "
              f"{result['away_team']} {p['away_points']:.2f}"
              + ("  (OT/SO included)" if p.get("final_probability_available") else "  (regulation only)"),
              f"Regulation goals:       {result['home_team']} {p['regulation_home']:.2f} | "
              f"{result['away_team']} {p['regulation_away']:.2f}",
              f"Model: {result['model_version']}",
              f"Current-season games: Home {counts['home']} | Away {counts['away']} "
              f"| policy minimum {gate['required_games']}"]
    if result.get("goalie_context"):
        context = result["goalie_context"]
        lines.append(f"User-confirmed goalie IDs: Home {context['home']['player_id']} | "
                     f"Away {context['away']['player_id']} "
                     f"(identity only; no numeric goalie adjustment)")

    rows = [(market, row) for market in result["markets"]
            for row in market_rows(result, market, keep_estimates=keep)]
    width = max([len("Selection")] + [len(row["selection"]) for _, row in rows])
    lines += ["", "CAPTURED MARKETS / MODEL REFERENCES",
              f"{'Market':<12} {'Selection':<{width}}  {'Odds':>7}  {'Probability':>11}  "
              f"{'Model EV':>9}", "-" * (width + 50)]
    for market in result["markets"]:
        for row in market_rows(result, market, keep_estimates=keep):
            ev = percent(row["ev"], True) if row["ev"] is not None else "--"
            lines.append(f"{row['market']:<12} {row['selection']:<{width}}  "
                         f"{price(row['price']):>7}  {percent(row['probability']):>11}  {ev:>9}")
        # Only an actionable market repeats a line here; a gated game already has its
        # one verdict above, so restating it per market is noise.
        if market.get("pick"):
            lines.append("  PICK: " + recommendation(result, market))
    if keep and not gate["eligible"]:
        lines.append("* Model EV is the model probability priced at the offered odds: "
                     "a MODEL ESTIMATE, not a recommendation.")

    v = p["validation"]
    lines.append(f"\nHOLDOUT: {v['games']} games | Goal deviance {v['goal_deviance']:.3f} "
                 f"vs baseline {v['baseline_goal_deviance']:.3f}")
    lines.append("Winner Brier: " + (f"{v['winner_brier']:.3f}" if v["winner_brier"] is not None
                                    else "unavailable"))
    lines += ["\nDATA / LIMITATIONS", *("- " + str(x) for x in result["notes"])]
    lines.append("MoneyPuck.com advanced history. Model probabilities are not proven betting returns.")
    return "\n".join(lines)
