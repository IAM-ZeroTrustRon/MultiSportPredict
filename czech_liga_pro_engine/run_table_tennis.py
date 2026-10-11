"""
Czech Liga Pro Table Tennis Runner
MultiSportPredict Architecture - Sections 6, 7, 10.

Usage:
  # 1. Names-only match run (auto-resolves ratings and market quotes from local stores)
  venv/Scripts/python.exe run_table_tennis.py --match "Havrda Leos vs Kulhanek Pavel"

  # 2. Match run with explicit event ID
  venv/Scripts/python.exe run_table_tennis.py --match "Havrda Leos vs Kulhanek Pavel" --event-id "cz_tt_37257_m01"

  # 3. Match run with manual rating and odds overrides (optional fallback only)
  venv/Scripts/python.exe run_table_tennis.py --match "Havrda Leos vs Kulhanek Pavel" --event-id "cz_tt_37257_m01" --home-rating 428 --away-rating 476 --odds 2.15 1.65

  # 4. Live in-play state conditioning (Games: 1-0, Points: 8-5 in Game 2)
  venv/Scripts/python.exe run_table_tennis.py --match "Havrda Leos vs Kulhanek Pavel" --event-id "cz_tt_37257_m01" --live --live-games 1 0 --live-points 8 5

  # 5. Push saved run directly to Discord format (zero recomputation)
  venv/Scripts/python.exe run_table_tennis.py --push "cz_tt_37257_m01"
"""

import sys
import os
import json
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

from models.table_tennis_scoring import MatchState, PointState
from models.table_tennis_features import (
    TableTennisFeaturePipeline, HistoricalMatchRecord, PlayerSessionWorkload
)
from models.table_tennis_predictor import CzechLigaProPredictor
from table_tennis.alerts import TableTennisAlertManager

SAVED_RUNS_DIR = "output/saved_runs"
RATINGS_STORE_PATH = "data/czech_liga_pro_ratings.json"
ODDS_SAMPLES_PATH = "data/czech_liga_pro_samples/real_captured_odds_payloads.json"

def load_player_rating_store() -> Dict[str, Any]:
    if os.path.exists(RATINGS_STORE_PATH):
        try:
            with open(RATINGS_STORE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def load_odds_store() -> list:
    if os.path.exists(ODDS_SAMPLES_PATH):
        try:
            with open(ODDS_SAMPLES_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("odds_records", [])
        except Exception:
            return []
    return []



def resolve_player_rating(player_name: str, store: Dict[str, Any], default_rating: float = 750.0) -> Tuple[float, str]:
    slug = player_name.strip().lower().replace(" ", "_")
    if slug in store:
        entry = store[slug]
        return float(entry.get("rating", default_rating)), f"Auto-resolved from store ({entry.get('tier', 'Unknown Tier')})"
    # Partial match
    for k, v in store.items():
        if k in slug or slug in k:
            return float(v.get("rating", default_rating)), f"Auto-resolved (partial match: {v.get('name')})"
    return default_rating, "Default baseline rating (750)"

def resolve_market_odds(home_name: str, away_name: str, event_id: str,
                        odds_records: list) -> Optional[Tuple[float, float, str, Dict[str, Any]]]:
    # Match by event_id or player names
    h_slug = home_name.lower().replace(" ", "_")
    a_slug = away_name.lower().replace(" ", "_")

    for rec in odds_records:
        rec_event = rec.get("event_id", "")
        rec_match = rec.get("match", "").lower().replace(" ", "_")
        if (event_id and event_id == rec_event) or (h_slug in rec_match and a_slug in rec_match):
            markets = rec.get("markets", {})
            ml = markets.get("moneyline", {})
            h_odds = ml.get("home_odds", 0.0)
            a_odds = ml.get("away_odds", 0.0)
            book = rec.get("bookmaker", "Aggregated Feed")
            if h_odds > 1.0 and a_odds > 1.0:
                return (h_odds, a_odds, f"Auto-resolved from {book}", markets)
    return None

def format_terminal_report(pred: Dict[str, Any], match_name: str, event_id: str,
                           rating_notes: Tuple[str, str], odds_note: str) -> str:
    probs = pred["probabilities"]
    dist = pred["market_distributions"]
    h2h = pred.get("h2h_metrics", {})
    workload = pred.get("workload_metrics", {})

    lines = [
        "=" * 74,
        f"  CZECH LIGA PRO PREDICTION REPORT | {match_name}",
        f"  Event ID: {event_id} | Strategy: {pred['strategy']}",
        "=" * 74,
        "",
        "1. INPUT RESOLUTION & PROVENANCE",
        f"  - Home Player: {pred['player_a_name']} -> {rating_notes[0]}",
        f"  - Away Player: {pred['player_b_name']} -> {rating_notes[1]}",
        f"  - Market Quotes: {odds_note}",
        "",
        "2. MODEL PROBABILITIES & PROBABILITY TREE",
        f"  - Top-Down Market Fair A:  {probs.get('top_down_market_a', 'N/A')}",
        f"  - Bottom-Up Strength A:    {probs.get('bottom_up_strength_a', 'N/A')}",
        f"  - Hybrid Final Win Prob:   {pred['player_a_name']}: {probs['selected_final_win_a']*100:.1f}% | {pred['player_b_name']}: {probs['selected_final_win_b']*100:.1f}%",
        f"  - Implied Point Win Prob:  {probs['implied_point_win_prob_a']:.4f}",
        "",
        "3. SET & GAME DISTRIBUTIONS (Best-of-5 Games)",
        f"  - Exact Score Probs:       {dist.get('score_distribution', {})}",
        f"  - Game Handicap (-1.5 G):  Home -1.5 Games: {dist['game_handicap']['home_minus_1_5']*100:.1f}% | Away +1.5 Games: {dist['game_handicap']['away_plus_1_5']*100:.1f}%",
        f"  - Total Games (O/U 3.5):   Over 3.5: {dist['total_games']['over_3_5']*100:.1f}% | Under 3.5: {dist['total_games']['under_3_5']*100:.1f}% (Exp: {dist['total_games']['expected']} games)",
        f"  - Total Games (O/U 4.5):   Over 4.5: {dist['total_games']['over_4_5']*100:.1f}% | Under 4.5: {dist['total_games']['under_4_5']*100:.1f}%",
        "",
        "4. POINT-LEVEL METRICS & HANDICAPS",
        f"  - Expected Total Points:   {dist['total_points']['expected']} pts",
        f"  - Expected Point Margin:   {dist['total_points']['expected_margin_a']} pts",
        "",
        "5. HISTORICAL H2H & WORKLOAD OBSERVATIONS",
        f"  - H2H Meetings Sample:     {h2h.get('h2h_sample_size', 0)} past matches (Weight sum: {h2h.get('h2h_weighted_sum', 0.0)})",
        f"  - Shrunk H2H Win Rate A:   {h2h.get('shrunk_match_win_prob_a', 0.5)*100:.1f}% (Residual: {h2h.get('shrunk_residual_h2h', 0.0)})",
        f"  - Same-Day Rematch Count:  {h2h.get('same_day_rematch_count', 0)}",
        f"  - Matches Completed Today: A: {workload.get('player_a_matches_today', 0)} | B: {workload.get('player_b_matches_today', 0)}",
        f"  - Rest Difference:         {workload.get('rest_difference_minutes', 0.0)} mins",
        "",
        "6. THE CASE AGAINST THE RECOMMENDATION (Risk Factors)",
        "  - High intra-session volatility in Czech Liga Pro round-robin formats.",
        "  - Same-day rematch adjustments can carry non-linear tilt and fatigue effects.",
        "  - Stale quote risk: Always check quote timestamp before execution.",
        "=" * 74
    ]
    return "\n".join(lines)

def run_prediction(home_name: str, away_name: str,
                   event_id: str,
                   home_rating: Optional[float] = None,
                   away_rating: Optional[float] = None,
                   reference_odds: Optional[Tuple[float, float]] = None,
                   market_all_quotes: Optional[Dict[str, Any]] = None,
                   live_games: Tuple[int, int] = (0, 0),
                   live_points: Tuple[int, int] = (0, 0)) -> Dict[str, Any]:

    predictor = CzechLigaProPredictor()
    feature_pipeline = TableTennisFeaturePipeline()

    now_utc = datetime.now(timezone.utc)

    # Build H2H and workload context
    h2h_metrics = feature_pipeline.extract_h2h_features(
        history=[],
        player_a_id=home_name.lower().replace(" ", "_"),
        player_b_id=away_name.lower().replace(" ", "_"),
        prediction_time_utc=now_utc,
        baseline_prob_a=0.5
    )

    workload_metrics = feature_pipeline.extract_workload_and_rest(
        workload_a=PlayerSessionWorkload(player_id=home_name, date_str=now_utc.strftime("%Y-%m-%d")),
        workload_b=PlayerSessionWorkload(player_id=away_name, date_str=now_utc.strftime("%Y-%m-%d")),
        match_start_utc=now_utc
    )

    match_state = MatchState(
        games_a=live_games[0],
        games_b=live_games[1],
        best_of=5,
        current_game=PointState(points_a=live_points[0], points_b=live_points[1])
    )

    pred = predictor.generate_full_prediction(
        player_a={"name": home_name, "rating": home_rating},
        player_b={"name": away_name, "rating": away_rating},
        reference_odds=reference_odds,
        h2h_data=h2h_metrics,
        workload_data=workload_metrics,
        live_match_state=match_state
    )

    # Save run to output
    os.makedirs(SAVED_RUNS_DIR, exist_ok=True)
    run_record = {
        "saved_run_id": event_id,
        "timestamp_utc": now_utc.isoformat(),
        "match_name": f"{home_name} vs {away_name}",
        "event_id": event_id,
        "ratings": {"home": home_rating, "away": away_rating},
        "odds": {"home": reference_odds[0] if reference_odds else None, "away": reference_odds[1] if reference_odds else None},
        "all_market_quotes": market_all_quotes or {},
        "prediction": pred,
        "live_state": {
            "games": f"{live_games[0]}-{live_games[1]}",
            "points": f"{live_points[0]}-{live_points[1]}"
        }
    }
    save_path = os.path.join(SAVED_RUNS_DIR, f"{event_id}.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(run_record, f, indent=2)

    return run_record

def main():
    parser = argparse.ArgumentParser(description="Czech Liga Pro Table Tennis Prediction Runner")
    parser.add_argument("--match", type=str, help="Match string: 'Player A vs Player B'")
    parser.add_argument("--event-id", type=str, help="Exact event ID (e.g. cz_tt_37257_m01)")
    parser.add_argument("--home-rating", type=float, help="Optional manual override for home rating")
    parser.add_argument("--away-rating", type=float, help="Optional manual override for away rating")
    parser.add_argument("--odds", nargs=2, type=float, help="Optional manual override: decimal odds HOME AWAY")
    parser.add_argument("--live", action="store_true", help="Live in-play evaluation mode")
    parser.add_argument("--live-games", nargs=2, type=int, default=[0, 0], help="Current games score: GA GB")
    parser.add_argument("--live-points", nargs=2, type=int, default=[0, 0], help="Current game points: PA PB")
    parser.add_argument("--push", type=str, help="Push saved run to Discord format (takes saved_run_id)")

    args = parser.parse_args()

    if args.push:
        saved_file = os.path.join(SAVED_RUNS_DIR, f"{args.push}.json")
        if not os.path.exists(saved_file):
            print(f"Error: Saved run '{args.push}' not found at {saved_file}")
            sys.exit(1)
        with open(saved_file, "r", encoding="utf-8") as f:
            run_data = json.load(f)
        pred = run_data["prediction"]
        stored_odds = run_data.get("odds", {})
        h_odds = stored_odds.get("home") or 1.85
        a_odds = stored_odds.get("away") or 1.85
        p_win_a = pred["probabilities"]["selected_final_win_a"]
        p_win_b = pred["probabilities"]["selected_final_win_b"]
        fair_a = pred["probabilities"].get("top_down_market_a") or 0.50

        selection = pred["player_a_name"] if p_win_a >= 0.5 else pred["player_b_name"]
        selected_odds = h_odds if p_win_a >= 0.5 else a_odds
        selected_prob = p_win_a if p_win_a >= 0.5 else p_win_b
        selected_fair = fair_a if p_win_a >= 0.5 else (1.0 - fair_a)

        edge_pct = (selected_prob - selected_fair) * 100.0
        ev = selected_prob * selected_odds - 1.0

        signal_data = {
            "event_id": run_data["event_id"],
            "match_name": run_data["match_name"],
            "market": "Moneyline",
            "selection": selection,
            "odds": selected_odds,
            "model_prob": selected_prob,
            "market_fair": selected_fair,
            "edge_pct": round(edge_pct, 2),
            "ev": round(ev, 4),
            "score_state": run_data["live_state"]["games"]
        }
        embed = TableTennisAlertManager.format_discord_embed(signal_data)
        print("DISCORD EMBED GENERATED (PUSH READY):")
        print(json.dumps(embed, indent=2))
        return

    home, away = "Player A", "Player B"
    if args.match:
        parts = args.match.split(" vs ")
        if len(parts) == 2:
            home, away = parts[0].strip(), parts[1].strip()

    # Auto-resolve ratings from store if not manually overridden
    ratings_store = load_player_rating_store()
    if args.home_rating is not None:
        r_home, note_home = args.home_rating, f"Manual CLI override: {args.home_rating}"
    else:
        r_home, note_home = resolve_player_rating(home, ratings_store)

    if args.away_rating is not None:
        r_away, note_away = args.away_rating, f"Manual CLI override: {args.away_rating}"
    else:
        r_away, note_away = resolve_player_rating(away, ratings_store)

    # Canonical event ID
    event_id = args.event_id or f"cz_tt_{home.lower()[:3]}_{away.lower()[:3]}_m01"

    # Auto-resolve odds from store if not manually overridden
    odds_store = load_odds_store()
    market_quotes_dict = None
    if args.odds is not None:
        ref_odds = (args.odds[0], args.odds[1])
        odds_note = f"Manual CLI override: {ref_odds[0]} vs {ref_odds[1]}"
    else:
        resolved_odds = resolve_market_odds(home, away, event_id, odds_store)
        if resolved_odds:
            ref_odds = (resolved_odds[0], resolved_odds[1])
            odds_note = f"{resolved_odds[2]} ({ref_odds[0]} vs {ref_odds[1]})"
            market_quotes_dict = resolved_odds[3]
        else:
            ref_odds = None
            odds_note = "No market odds available (using Bottom-Up Strength fallback)"

    run_record = run_prediction(
        home_name=home,
        away_name=away,
        event_id=event_id,
        home_rating=r_home,
        away_rating=r_away,
        reference_odds=ref_odds,
        market_all_quotes=market_quotes_dict,
        live_games=(args.live_games[0], args.live_games[1]),
        live_points=(args.live_points[0], args.live_points[1])
    )

    report_text = format_terminal_report(
        run_record["prediction"], run_record["match_name"], event_id,
        (note_home, note_away), odds_note
    )
    print(report_text)

if __name__ == "__main__":
    main()
