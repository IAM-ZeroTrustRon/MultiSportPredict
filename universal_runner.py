#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
universal_runner.py — Universal Match Prediction Hub
======================================================
The high-level CLI hub that `run_match.py` and `auto_mlb_scraper.py` already
shell out to. Routes every sport through the canonical predictors and logs
results to `core.historical_storage` (the live SQLite store).

Usage:
    python universal_runner.py --sport soccer --home "Ajax" --away "PSV" \\
        --league Eredivisie --market-total 3.0 --store-to-db
    python universal_runner.py --sport basketball --home "Real Madrid" --away "FC Barcelona" \\
        --market-line -4.5 --store-to-db
    python universal_runner.py --sport baseball --home "NYY" --away "BOS" \\
        --markets nrfi strikeouts --market-total 8.5 \\
        --home-sp-era 3.20 --home-sp-k 8.5 --away-sp-era 4.10 --away-sp-k 7.0
    python universal_runner.py --sport tennis --home "Jannik Sinner" --away "Carlos Alcaraz" \\
        --surface hard --tournament "US Open" --round-name "Final" --best-of-5

Canonical deps (see ARCHITECTURE.md):
  - core/historical_storage.py  (store_prediction)
  - core/confidence_engine.py   (confidence_score, bet_recommendation)
  - team_stats_provider.py      (real soccer/basketball stats)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root on sys.path for bare "team_stats_provider" / core imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import requests
except ImportError:
    requests = None

from dotenv import load_dotenv

load_dotenv()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


# ============================================================================
# DISCORD COMPATIBILITY WRAPPER
# ============================================================================
# Many downstream scripts import `from universal_runner import push_to_discord`.
# That function is thin: it delegates to discord_integration.push_to_discord(),
# which is the canonical webhook helper. Keep the signature wide so callers
# can pass whatever subset they have.

def push_to_discord(
    sport: str = "",
    home: str = "",
    away: str = "",
    market_total: Optional[float] = None,
    projected_total: Optional[float] = None,
    edge: Optional[str] = "",
    recommendation: Optional[str] = "",
    confidence: Optional[float] = None,
    webhook_url: Optional[str] = None,
    extra_metrics: Optional[str] = "",
    market_line: Optional[float] = None,
    primary_recommendation: Optional[str] = None,
) -> bool:
    """Push a prediction message to Discord.

    Delegates to `discord_integration.push_to_discord` when available so all
    Discord formatting stays in one place. Returns True on success.
    """
    webhook = webhook_url or DISCORD_WEBHOOK_URL
    rec = primary_recommendation or recommendation or ""
    conf = confidence if confidence is not None else 50.0

    try:
        from discord_integration import push_to_discord as _discord_push
    except ImportError as exc:
        print(f"[push_to_discord] discord_integration unavailable: {exc}")
        return False

    additional_fields: Dict[str, str] = {}
    if projected_total is not None:
        additional_fields["Projected Total"] = f"{projected_total:.2f}"
    if extra_metrics:
        additional_fields["Additional Metrics"] = extra_metrics

    # Pass structured values to the canonical Discord helper.
    payload_sport = sport or "prediction"
    payload_home = home or "Unknown"
    payload_away = away or "Unknown"
    payload_recommendation = rec or "PASS"
    payload_edge = edge or "0.0"

    return bool(
        _discord_push(
            sport=payload_sport,
            home=payload_home,
            away=payload_away,
            recommendation=payload_recommendation,
            confidence=conf,
            edge=payload_edge,
            market_line=market_line,
            market_total=market_total,
            webhook_url=webhook,
            additional_fields=additional_fields or None,
        )
    )


# ============================================================================
# STAT SOURCE
# ============================================================================

def get_team_stats(sport: str, home: str, away: str,
                   league: Optional[str] = None) -> tuple[Optional[Dict], Optional[Dict]]:
    """Pull real team stats for soccer/basketball via team_stats_provider.py.

    Returns (home_stats, away_stats); either may be None if no data exists.
    """
    try:
        from team_stats_provider import get_soccer_team_stats, get_basketball_team_stats
    except ImportError as exc:
        print(f"[WARN] team_stats_provider not available ({exc}); using placeholder fallback.")
        return None, None

    if sport in ("soccer", "football"):
        hs = get_soccer_team_stats(home, league)
        aws = get_soccer_team_stats(away, league)
        return hs, aws
    if sport in ("basketball", "kbl", "euroleague", "eurocup", "liga acb"):
        hs = get_basketball_team_stats(home, league)
        aws = get_basketball_team_stats(away, league)
        return hs, aws
    return None, None


# ============================================================================
# STORAGE
# ============================================================================

def _store_prediction(
    sport: str,
    home: str,
    away: str,
    market_type: str,
    model_value: float,
    market_value: float,
    edge: float,
    confidence: float,
    recommendation: str,
    raw_json: Dict[str, Any],
) -> None:
    """Log a prediction to core.historical_storage (canonical store)."""
    try:
        from core.historical_storage import init_db, store_prediction

        init_db()
        store_prediction(
            sport=sport,
            home_team=home,
            away_team=away,
            market_type=market_type,
            model_value=model_value,
            market_value=market_value,
            edge=edge,
            confidence=confidence,
            recommendation=recommendation,
            raw_json=raw_json,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Failed to store prediction to historical_storage: {exc}")


def _display_full_result(result: Dict[str, Any]) -> None:
    """Display model output as compact, readable Rich tables."""
    market_rows: List[tuple[str, str, str, str]] = []
    support_rows: List[tuple[str, str]] = []
    predictions = result.get("predictions", {})

    def format_value(value: Any) -> str:
        if isinstance(value, float):
            return f"{value:.3f}"
        if isinstance(value, (dict, list)):
            return json.dumps(value, default=str, separators=(",", ":"))
        return str(value)

    def add_market(section: str, values: Dict[str, Any]) -> None:
        recommendation = values.get("recommendation", values.get("lean", "N/A"))
        probability = values.get("probability", values.get("over_prob", "N/A"))
        if isinstance(probability, (int, float)) and 0 <= probability <= 1:
            probability = f"{probability:.1%}"
        edge = values.get("edge", values.get("edge_pct", "N/A"))
        confidence = values.get("confidence", values.get("confidence_score", "N/A"))
        if isinstance(confidence, (int, float)):
            confidence = f"{confidence:.1f}%"
        market_rows.append((section, str(recommendation), str(probability), f"Edge {edge} | Conf {confidence}"))

    for section, values in predictions.items():
        if isinstance(values, dict):
            add_market(section, values)

    goals_analysis = result.get("goals_analysis")
    if isinstance(goals_analysis, dict):
        for line in ("15", "25", "35"):
            probability = goals_analysis.get(f"over_{line}_prob")
            if probability is not None:
                market_rows.append((f"Goals Over {int(line) / 10:g}", "Model probability", f"{probability:.1%}", ""))

    corners_analysis = result.get("corners_analysis")
    if isinstance(corners_analysis, dict):
        for line in ("85", "95", "105"):
            probability = corners_analysis.get(f"over_{line}_prob")
            if probability is not None:
                market_rows.append((f"Corners Over {int(line) / 10:g}", "Model probability", f"{probability:.1%}", ""))

    for section in ("props", "markets", "moneyline", "totals", "side", "btts", "corners", "halftime", "player_props"):
        values = result.get(section)
        if isinstance(values, dict):
            if any(key in values for key in ("recommendation", "lean", "probability", "over_prob")):
                add_market(section, values)
            else:
                for market_name, market_values in values.items():
                    if isinstance(market_values, dict):
                        add_market(f"{section}.{market_name}", market_values)

    game = result.get("game", result.get("game_projection", {}))
    if isinstance(game, dict):
        for key, value in game.items():
            support_rows.append((key.replace("_", " ").title(), format_value(value)))

    for section in ("goals_analysis", "corners_analysis", "team_metrics", "live_market", "weather", "umpire", "data_source"):
        values = result.get(section)
        if values is not None:
            support_rows.append((section.replace("_", " ").title(), format_value(values)))

    try:
        from rich.console import Console
        from rich.table import Table

        console = Console(width=120)
        home = result.get("home_team", result.get("home", "Home"))
        away = result.get("away_team", result.get("away", "Away"))
        league = result.get("league", "")
        console.print(f"\n[bold cyan]{result.get('sport', 'MATCH').upper()}[/bold cyan] | [bold]{home} vs {away}[/bold] {league}")

        if market_rows:
            markets_table = Table(title="Recommendations", show_lines=False, expand=True)
            markets_table.add_column("Market", style="cyan", no_wrap=True)
            markets_table.add_column("Recommendation", style="bold green")
            markets_table.add_column("Probability", justify="right")
            markets_table.add_column("Edge / Confidence", style="yellow")
            for row in market_rows:
                markets_table.add_row(*row)
            console.print(markets_table)

        if support_rows:
            support_table = Table(title="Projection & Context", show_lines=False, expand=True)
            support_table.add_column("Metric", style="cyan")
            support_table.add_column("Value", style="green")
            for row in support_rows:
                support_table.add_row(*row)
            console.print(support_table)
    except ImportError:
        print("\nRecommendations")
        for market, recommendation, probability, details in market_rows:
            print(f"  {market}: {recommendation} | {probability} | {details}")
        print("Projection & Context")
        for label, value in support_rows:
            print(f"  {label}: {value}")


def _push_full_result(sport: str, home: str, away: str, result: Dict[str, Any]) -> bool:
    """Send the complete result through the shared Discord formatter."""
    try:
        from discord_integration import push_full_prediction_to_discord
        return push_full_prediction_to_discord(
            sport=sport, home=home, away=away, prediction=result,
            webhook_url=DISCORD_WEBHOOK_URL,
        )
    except ImportError as exc:
        print(f"[WARN] Full Discord formatter unavailable: {exc}")
        return False


def _fetch_live_soccer_market(home: str, away: str, league: Optional[str]) -> Dict[str, Any]:
    """Fetch a matched live soccer market without inventing missing odds."""
    league_keys = {
        "epl": "soccer_epl",
        "premier league": "soccer_epl",
        "la liga": "soccer_spain_la_liga",
        "serie a": "soccer_italy_serie_a",
        "bundesliga": "soccer_germany_bundesliga",
        "ligue 1": "soccer_france_ligue_one",
    }
    league_key = league_keys.get((league or "epl").strip().lower(), league or "soccer_epl")
    try:
        from OddsApiIngestor import OddsApiIngestor

        ingestor = OddsApiIngestor()
        match = ingestor.fetch_specific_match(league_key, home, away)
        if not match:
            return {"source": "odds_api", "status": "event_not_found", "league_key": league_key}
        return {
            "source": "odds_api",
            "status": "live",
            "league_key": league_key,
            "market": ingestor.extract_market_lines(match),
        }
    except ValueError as exc:
        return {"source": "odds_api", "status": "not_configured", "detail": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"source": "odds_api", "status": "error", "detail": str(exc)}


# ============================================================================
# SPORT RUNNERS
# ============================================================================

def run_soccer(home: str, away: str, league: Optional[str], market_line: float,
               market_total: float, store_to_db: bool,
               push_discord: bool, live_odds: bool = False) -> Dict[str, Any]:
    from predict_match import run_soccer_game

    hs, aws = get_team_stats("soccer", home, away, league)
    result = run_soccer_game(home, away, league=league or "Premier League",
                             market_line=market_line, market_total=market_total,
                             home_stats=hs, away_stats=aws)
    if live_odds:
        result["live_market"] = _fetch_live_soccer_market(home, away, league)
        output_path = Path("output/soccer") / f"{home.replace(' ', '_')}_vs_{away.replace(' ', '_')}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    _display_full_result(result)

    game = result.get("game", {})
    total_edge = float(result.get("predictions", {}).get("total", {}).get("edge", 0.0))
    confidence = float(result.get("predictions", {}).get("total", {}).get("confidence", 50.0))
    rec = result.get("predictions", {}).get("total", {}).get("recommendation", "PASS")

    if store_to_db:
        _store_prediction(
            sport="soccer",
            home=home,
            away=away,
            market_type="total",
            model_value=float(game.get("projected_total_goals", 0.0)),
            market_value=market_total,
            edge=total_edge,
            confidence=confidence,
            recommendation=rec,
            raw_json=result,
        )
        print(f"[OK] Soccer prediction stored to multisport_history.db")

    if push_discord:
        status = _push_full_result("soccer", home, away, result)
        print(f"[{ 'OK' if status else 'FAILED' }] Full soccer result pushed to Discord")

    return result


def run_basketball(home: str, away: str, league: Optional[str], market_line: float,
                   store_to_db: bool, push_discord: bool) -> Dict[str, Any]:
    from predict_match import run_basketball_game

    hs, aws = get_team_stats("basketball", home, away, league)
    result = run_basketball_game(home, away, league=league or "EuroLeague",
                                 market_line=market_line, home_stats=hs, away_stats=aws)
    _display_full_result(result)

    full_game = result.get("full_game", {})
    model_prob = float(full_game.get("probability", 0.5))
    edge = float(full_game.get("model_edge", 0.0))
    conf = float(full_game.get("confidence", 50.0)) or 50.0
    rec = full_game.get("lean", "PASS")

    if store_to_db:
        _store_prediction(
            sport="basketball",
            home=home,
            away=away,
            market_type="spread",
            model_value=model_prob,
            market_value=market_line,
            edge=edge,
            confidence=conf,
            recommendation=rec,
            raw_json=result,
        )
        print(f"[OK] Basketball prediction stored to multisport_history.db")

    if push_discord:
        status = _push_full_result("basketball", home, away, result)
        print(f"[{ 'OK' if status else 'FAILED' }] Full basketball result pushed to Discord")

    return result


def run_baseball(home: str, away: str, league: Optional[str], markets: Optional[List[str]], market_total: float,
                 home_sp_era: Optional[float], home_sp_k: Optional[float],
                 away_sp_era: Optional[float], away_sp_k: Optional[float],
                 store_to_db: bool, push_discord: bool) -> Dict[str, Any]:
    from predict_match import run_baseball_game

    batters_faced_est = max(5.5 * 4.3, 1.0)
    home_sp_overrides = None
    if home_sp_era is not None or home_sp_k is not None:
        home_sp_overrides = {}
        if home_sp_era is not None:
            home_sp_overrides["era"] = float(home_sp_era)
        if home_sp_k is not None:
            home_sp_overrides["k_rate"] = max(
                0.0, min(0.60, float(home_sp_k) / batters_faced_est)
            )

    away_sp_overrides = None
    if away_sp_era is not None or away_sp_k is not None:
        away_sp_overrides = {}
        if away_sp_era is not None:
            away_sp_overrides["era"] = float(away_sp_era)
        if away_sp_k is not None:
            away_sp_overrides["k_rate"] = max(
                0.0, min(0.60, float(away_sp_k) / batters_faced_est)
            )

    result = run_baseball_game(
        home, away, league=league or "MLB",
        markets=markets or ["nrfi", "strikeouts", "home_runs"],
        market_total=market_total,
        home_sp_overrides=home_sp_overrides,
        away_sp_overrides=away_sp_overrides,
    )
    _display_full_result(result)

    summary = result.get("summary", {})
    conf = float(summary.get("confidence", 50.0))
    rec = summary.get("recommendation", "PASS")
    edge = summary.get("edge", "0.0")
    proj_total = float(result.get("game_projection", {}).get("total", 0.0))

    if store_to_db:
        _store_prediction(
            sport="baseball",
            home=home,
            away=away,
            market_type="total",
            model_value=proj_total,
            market_value=market_total,
            edge=float(summary.get("implied_over_prob", 0.5)) - 0.5,
            confidence=conf,
            recommendation=rec,
            raw_json=result,
        )
        print(f"[OK] Baseball prediction stored to multisport_history.db")

    if push_discord:
        game = result.get("moneyline_and_side", {})
        side_confidence = game.get("confidence", {}).get("side", {})
        props = result.get("props", {})
        nrfi = props.get("nrfi", {})
        strikeouts = props.get("strikeouts", {})
        home_runs = props.get("home_runs", {})
        full_slip_message = "\n".join([
            f"Moneyline: {home} {float(game.get('home_win_probability', 0.0)):.1%}"
            f" / {away} {float(game.get('away_win_probability', 0.0)):.1%}",
            f"Run Line: {side_confidence.get('recommendation', 'PASS')}"
            f" ({float(side_confidence.get('score', 0.0)):.1f}% confidence)",
            f"Total: {summary.get('recommendation', 'PASS')}",
            f"NRFI: {nrfi.get('lean', 'N/A')}"
            f" ({float(nrfi.get('probability', 0.0)):.1%})",
            f"K Props: {strikeouts.get('home_team_projected_ks', 0.0):.1f}"
            f" home / {strikeouts.get('away_team_projected_ks', 0.0):.1f} away",
            f"HR Props: {home_runs.get('home_team_projected_hrs', 0.0):.1f}"
            f" home / {home_runs.get('away_team_projected_hrs', 0.0):.1f} away",
        ])
        print(f"\nFull betting slip for {home} vs {away}:\n{full_slip_message}")
        status = _push_full_result("baseball", home, away, result)
        print(f"[{ 'OK' if status else 'FAILED' }] Full baseball result pushed to Discord")

    return result


def run_tennis(home: str, away: str, surface: str, tournament: Optional[str],
               round_name: Optional[str], best_of_5: bool,
               store_to_db: bool, push_discord: bool) -> Dict[str, Any]:
    """Tennis branch: call the real predictor directly (bypass predict_match.py)."""
    from models.tennis_predictor import predict_tennis_match

    result = predict_tennis_match(
        home_player=home,
        away_player=away,
        surface=surface or "grass",
        best_of_5=best_of_5,
        tournament=tournament,
        round_name=round_name,
    )
    _display_full_result(result)

    ml = result.get("moneyline", {})
    home_win_prob = float(ml.get("home_win_prob", 0.5))
    edge = float(ml.get("edge_pct", 0.0))
    conf = float(ml.get("confidence", 50.0)) or 50.0
    rec = ml.get("recommendation", "PASS")

    if store_to_db:
        _store_prediction(
            sport="tennis",
            home=home,
            away=away,
            market_type="moneyline",
            model_value=home_win_prob,
            market_value=0.5,
            edge=edge,
            confidence=conf,
            recommendation=rec,
            raw_json=result,
        )
        print(f"[OK] Tennis prediction stored to multisport_history.db")

    if push_discord:
        status = _push_full_result("tennis", home, away, result)
        print(f"[{ 'OK' if status else 'FAILED' }] Full tennis result pushed to Discord")

    return result


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Universal match prediction hub (canonical runner for all sports)."
    )
    parser.add_argument("--sport", required=True,
                        help="Sport: soccer, basketball, baseball/mlb, kbo, tennis")
    parser.add_argument("--home", required=True, help="Home team / player")
    parser.add_argument("--away", required=True, help="Away team / player")
    parser.add_argument("--league", default=None, help="League name (e.g. Eredivisie, MLB)")
    parser.add_argument("--markets", nargs="+", default=None,
                        help="Baseball prop markets (nrfi strikeouts home_runs).")
    parser.add_argument("--market-line", type=float, default=0.0,
                        help="Basketball/soccer market line (spread/handicap).")
    parser.add_argument("--market-total", type=float, default=2.5,
                        help="Market total (over/under).")
    parser.add_argument("--store-to-db", action="store_true",
                        help="Store prediction in core.historical_storage.")
    parser.add_argument("--push-discord", action="store_true",
                        help="Push result to Discord.")
    parser.add_argument("--live-odds", action="store_true",
                        help="Fetch matched live soccer odds when ODDS_API_KEY is configured.")
    # MLB SP overrides
    parser.add_argument("--home-sp-era", type=float, default=None)
    parser.add_argument("--home-sp-k", type=float, default=None)
    parser.add_argument("--away-sp-era", type=float, default=None)
    parser.add_argument("--away-sp-k", type=float, default=None)
    # Tennis
    parser.add_argument("--surface", default=None,
                        help="Tennis surface: grass, clay, hard.")
    parser.add_argument("--tournament", default=None,
                        help="Tennis tournament name.")
    parser.add_argument("--round-name", default=None,
                        help="Tennis round name.")
    parser.add_argument("--best-of-5", action="store_true",
                        help="Best-of-5 set match (default: Grand Slam auto-detect).")

    args = parser.parse_args()

    sport = args.sport.strip().lower()
    home = args.home.strip()
    away = args.away.strip()

    # Grand Slam auto-detect for best_of_5 if not explicitly set
    best_of_5 = args.best_of_5
    if not best_of_5 and args.tournament:
        gs = {"wimbledon", "french open", "roland garros", "us open",
              "australian open", "aus open"}
        best_of_5 = str(args.tournament).lower() in gs

    if sport in ("soccer", "football"):
        run_soccer(home, away, args.league, args.market_line, args.market_total,
                   args.store_to_db, args.push_discord, args.live_odds)
    elif sport in ("basketball", "kbl", "euroleague", "eurocup", "liga acb", "acb"):
        run_basketball(home, away, args.league, args.market_line,
                       args.store_to_db, args.push_discord)
    elif sport in ("baseball", "mlb", "kbo"):
        run_baseball(home, away, args.league, args.markets, args.market_total,
                     args.home_sp_era, args.home_sp_k,
                     args.away_sp_era, args.away_sp_k,
                     args.store_to_db, args.push_discord)
    elif sport == "tennis":
        run_tennis(home, away, args.surface, args.tournament, args.round_name,
                   best_of_5, args.store_to_db, args.push_discord)
    else:
        print(f"Unsupported sport: {sport}")
        sys.exit(1)


if __name__ == "__main__":
    main()