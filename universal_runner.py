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
from team_stats_provider import get_soccer_team_stats
from extra_markets import enrich_result, print_extra_markets


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
    if sport in ("basketball", "kbl", "nznbl", "euroleague", "eurocup", "liga acb"):
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
    league: Optional[str] = None,
    prices: Optional[Dict[str, Any]] = None,
) -> bool:
    """Log a prediction to core.historical_storage. Returns whether it landed.

    prices: the real American prices on the board when the prediction was
    made -- any of home_ml, away_ml, draw_ml, over, under, spread_home_price,
    spread_away_price. They go into raw_json["market_odds"], the one place the
    grader reads, so a win settles at what was actually offered instead of a
    flat -110. Missing prices are left out, never guessed.

    This used to return None and swallow the exception, so a caller counting
    its own loop reported "3 stored" when two had failed with disk I/O errors
    printed one line above. A write that did not happen is not a write.
    """
    if prices:
        clean = {k: float(v) for k, v in prices.items()
                 if isinstance(v, (int, float)) and v != 0}
        if clean:
            raw_json = dict(raw_json)
            existing = raw_json.get("market_odds")
            raw_json["market_odds"] = {**(existing if isinstance(existing, dict) else {}),
                                       **clean}
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
            league=league,
        )
        # The success path fell off the end of the function and returned None,
        # so `if _store_prediction(...)` was False on every write that actually
        # landed -- the same swallow the docstring above says was fixed, just
        # pointing the other way.
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Failed to store prediction to historical_storage: {exc}")
        return False


def _display_full_result(result: Dict[str, Any]) -> None:
    """Display model output as compact, readable Rich tables."""
    if result.get("sport") == "tennis":
        from run_tennis import format_tennis_review

        moneyline = result.get("moneyline") or {}
        auto = result.get("auto_odds") or {}
        home_price = result.get("market_home_odds")
        away_price = result.get("market_away_odds")
        market_source = ("live" if auto.get("status") in ("live", "cached")
                         else "user" if home_price is not None and away_price is not None
                         else None)
        review = {
            "p1": result.get("home_team") or moneyline.get("home"),
            "p2": result.get("away_team") or moneyline.get("away"),
            "tournament": result.get("tournament"),
            "surface": result.get("surface"),
            "best_of_5": result.get("best_of_5"),
            "model_prob": moneyline.get("home_win_prob"),
            "market_prob": result.get("market_prob"),
            "p1_ml": home_price,
            "p2_ml": away_price,
            "market_source": market_source,
            "custom_markets": [],
            "alternative_markets": result.get("alternative_markets") or [],
        }
        print("\n".join(format_tennis_review(review)))
        return

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

    for section in ("props", "markets", "moneyline", "totals",
                     "side", "btts", "corners", "halftime", "player_props"):
        values = result.get(section)
        if isinstance(values, dict):
            if any(key in values for key in ("recommendation", "lean", "probability", "over_prob")):
                add_market(section, values)
            else:
                for market_name, market_values in values.items():
                    if isinstance(market_values, dict):
                        add_market(f"{section}.{market_name}", market_values)

    # Baseball's moneyline/run-line lives under "moneyline_and_side" (not
    # "moneyline") and only carries a real market edge when --home-ml/
    # --away-ml were actually supplied -- without that, silently say nothing
    # rather than print a probability with no recommendation attached to it.
    baseball_ml = result.get("moneyline_and_side")
    if isinstance(baseball_ml, dict) and baseball_ml.get("recommendation"):
        # "confidence" on this dict is the predictor's nested {total, side}
        # block; the table wants the flat market-edge confidence instead --
        # substitute it for display only, without touching the stored dict.
        add_market("moneyline", {**baseball_ml, "confidence": baseball_ml.get("ml_confidence")})

    if result.get("sport") == "tennis":
        from embed_builder import extract_tennis
        market_rows.clear()
        for item in extract_tennis(result)["markets"]:
            if item:
                market_rows.append((str(item.get("label", item.get("name", "Market"))),
                    str(item.get("verdict") or item.get("pick") or "MODEL ONLY"),
                    str(item.get("model") or "N/A"), str(item.get("extra") or item.get("edge") or "")))

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
        from discord_integration import push_prediction_to_all
        count = push_prediction_to_all(sport, result, dry_run=False)
        return count > 0
    except ImportError as exc:
        print(f"[WARN] Full Discord formatter unavailable: {exc}")
        return False


def _fetch_live_soccer_market(home: str, away: str, league: Optional[str]) -> Dict[str, Any]:
    """Fetch a matched live soccer market without inventing missing odds."""
    from live_odds import get_soccer_odds, resolve_soccer_league

    # Single resolver: league_keys map removed so this cannot drift from
    # SOCCER_LEAGUES again. resolve_soccer_league is the one mapping.
    _config, _canonical, _status = resolve_soccer_league(league or "Premier League")
    fetched = get_soccer_odds(league or "Premier League", home, away)
    status = fetched.get("status", "error")
    result = {"source": "odds_api", "status": status,
              "league_key": (_config or {}).get("key") if _config else None,
              "league_canonical": _canonical,
              "captured_at": fetched.get("captured_at")}
    if status in ("live", "cached"):
        result["market"] = {k: v for k, v in fetched.items()
                            if k not in ("status", "captured_at")}
    else:
        result["detail"] = fetched.get("reason", "No priced fixture available")
    return result



# ============================================================================
# SPORT RUNNERS
# ============================================================================

def run_soccer(home: str, away: str, league: Optional[str], market_line: float,
               market_total: float, store_to_db: bool,
               push_discord: bool, live_odds: bool = False,
               auto_odds: bool = True, market_total_given: bool = False,
               market_line_given: bool = False,
               home_ml: Optional[float] = None, draw_ml: Optional[float] = None,
               away_ml: Optional[float] = None,
               over_price: Optional[float] = None,
               under_price: Optional[float] = None,
               spread_home_price: Optional[float] = None,
               spread_away_price: Optional[float] = None,
               game_date: Optional[str] = None) -> Dict[str, Any]:
    """
    auto_odds: try live_odds.get_soccer_odds() BEFORE predicting, so the
    prediction itself (not just an attached "live_market" afterthought) is
    built against real lines when they are fetchable. This is the fix for
    "PASS, model probability only" runs that used to need a second, manual
    re-run once someone typed a price in -- see live_odds.py.

    market_total_given: True when the CALLER explicitly supplied a real
    market_total (CLI flag or slate file), not the bare 2.5 default. A real
    caller-supplied number always wins over an auto-fetch; auto-fetch only
    fills the gap when nothing was actually given. Same rule applies to
    market_line_given and the price kwargs.
    """
    from predict_match import run_soccer_game
    if game_date:
        from fixture_guard import verify_fixture
        valid, message, orientation = verify_fixture("soccer", home, away, game_date, league)
        if not valid or orientation not in {"correct", "reversed"}:
            raise ValueError(f"Soccer fixture/date/home-away verification failed: {message}")
        print(message)
        if orientation == "reversed":
            # Manual side quotes belong to the requested teams, not the input
            # labels. Reverse them with the teams before stats/automatic odds.
            home, away = away, home
            home_ml, away_ml = away_ml, home_ml
            spread_home_price, spread_away_price = spread_away_price, spread_home_price
            market_line = -market_line
            print(f"Using verified home/away: {home} vs {away}; side prices and handicap remapped")

    hs = get_soccer_team_stats(home, league)
    aws = get_soccer_team_stats(away, league)
    if hs is None or aws is None:
        raise ValueError(f"Stats missing for '{home}' or '{away}'. Seed stats in team_stats_provider.py before running.")

    fetched_market: Dict[str, Any] = {}
    result_extra: Dict[str, Any] = {}
    market_source = "user"
    market_note: Optional[str] = None
    if auto_odds and not (market_total_given and market_line_given
                          and home_ml is not None and away_ml is not None):
        from live_odds import get_soccer_odds
        fetched_market = get_soccer_odds(league or "Premier League", home, away)
        if fetched_market.get("status") in ("live", "cached"):
            if not market_total_given and fetched_market.get("total_line") is not None:
                market_total = float(fetched_market["total_line"])
            if not market_line_given and fetched_market.get("spread_line") is not None:
                market_line = float(fetched_market["spread_line"])
            if home_ml is None and fetched_market.get("home_ml") is not None:
                home_ml = fetched_market["home_ml"]
            if draw_ml is None and fetched_market.get("draw_ml") is not None:
                draw_ml = fetched_market["draw_ml"]
            if away_ml is None and fetched_market.get("away_ml") is not None:
                away_ml = fetched_market["away_ml"]
            if over_price is None and fetched_market.get("over_price") is not None:
                over_price = fetched_market["over_price"]
            if under_price is None and fetched_market.get("under_price") is not None:
                under_price = fetched_market["under_price"]
            if spread_home_price is None and fetched_market.get("spread_home_price") is not None:
                spread_home_price = fetched_market["spread_home_price"]
            if spread_away_price is None and fetched_market.get("spread_away_price") is not None:
                spread_away_price = fetched_market["spread_away_price"]
            market_source = fetched_market["status"]
            # H1 / corners / team-totals / BTTS ride along for the review
            # table + embed + clean summary; absent stays None, never guessed.
            for extra_key in (
                    "h1_home_ml", "h1_away_ml", "h1_draw_ml",
                    "h1_spread_line", "h1_spread_home_price", "h1_spread_away_price",
                    "h1_total_line", "h1_over_price", "h1_under_price",
                    "corner_total_line", "corner_over_price", "corner_under_price",
                    "corner_spread_line",
                    "team_total_home_line", "team_total_home_over_price",
                    "team_total_home_under_price", "team_total_away_line",
                    "team_total_away_over_price", "team_total_away_under_price",
                    "btts_yes_price", "btts_no_price",
                    "h1_btts_yes_price", "h1_btts_no_price"):
                if fetched_market.get(extra_key) is not None:
                    result_extra[extra_key] = fetched_market[extra_key]
        else:
            market_note = str(fetched_market.get("reason", "no market"))
            market_source = "none"
    elif market_total_given or market_line_given or home_ml is not None:
        market_source = "user"

    result = run_soccer_game(home, away, league=league or "Premier League",
                             market_line=market_line, market_total=market_total,
                             home_stats=hs, away_stats=aws)
    # Preserve the extended quotes collected before prediction on the same
    # result sent to the saved JSON, review, database and Discord formatter.
    # Missing values were excluded above; zero Asian handicaps remain valid.
    result.update(result_extra)
    if game_date:
        result["game_date"] = game_date
    # run_soccer_game() writes output/soccer/*.json itself on return, before
    # this wrapper attaches the auto-odds fields below. Merge them into the
    # same file so the stored JSON carries the three markets the model used.
    odds_status = (fetched_market or {}).get("status")
    if fetched_market:
        result["auto_odds"] = fetched_market
    if home_ml is not None or draw_ml is not None or away_ml is not None:
        result["market_moneyline"] = {"home_ml": home_ml, "draw_ml": draw_ml,
                                      "away_ml": away_ml, "source": market_source,
                                      "captured_at": (fetched_market or {}).get("captured_at")}
    if over_price is not None or under_price is not None:
        result["market_totals_prices"] = {"over_price": over_price,
                                          "under_price": under_price,
                                          "source": market_source,
                                          "captured_at": (fetched_market or {}).get("captured_at")}
    if spread_home_price is not None or spread_away_price is not None:
        result["market_spread_prices"] = {"spread_line": market_line,
                                          "spread_home_price": spread_home_price,
                                          "spread_away_price": spread_away_price,
                                          "source": market_source,
                                          "captured_at": (fetched_market or {}).get("captured_at")}
    if market_source == "none" or odds_status in ("unknown_league", "not_covered", "no_fixture"):
        result["market_status"] = "UNLISTED (Simulation Only - No EV)"
        result["market_note"] = market_note or (fetched_market or {}).get("reason", "no market")
    else:
        result["market_status"] = market_source
        if market_note:
            result["market_note"] = market_note
    try:
        out_path = Path("output") / "soccer" / f"{home.replace(' ', '_')}_vs_{away.replace(' ', '_')}.json"
        if out_path.exists():
            stored = json.loads(out_path.read_text(encoding="utf-8-sig"))
            stored.update({k: v for k, v in result.items() if k not in stored or stored[k] != v})
            out_path.write_text(json.dumps(stored, indent=2, default=str) + "\n", encoding="utf-8")
    except (OSError, ValueError):
        pass

    # Wire extra_markets — halftime, team corners, BTTS enrichment
    try:
        from extra_markets import enrich_result
        result = enrich_result(
            result,
            home_team=home,
            away_team=away,
            home_stats=hs,
            away_stats=aws,
        )
        em = result.get("extra_markets", {})
        # Halftime
        fh = em.get("first_half_goals", {})
        result["halftime"] = {
            "recommendation_1h_total": f"Over 0.5: {fh.get('over_05', 0)*100:.1f}% | Over 1.5: {fh.get('over_15', 0)*100:.1f}%",
            "predicted_1h_result": f"Proj: {fh.get('projection', 'N/A')}",
        }
        # Team corners
        tc = em.get("team_corners", {})
        if tc and "_warning" not in tc:
            result["team_corners"] = {
                "home_proj": tc.get("home", {}).get("projection", "N/A"),
                "away_proj": tc.get("away", {}).get("projection", "N/A"),
            }
    except Exception as e:
        print(f"[WARNING] extra_markets enrichment failed: {e}")

    # Wire confidence engine into result before Discord push
    try:
        from core.confidence_engine import analyze_bet, bet_recommendation, confidence_score
        game = result.get("game", {})
        proj_total = float(game.get("projected_total_goals", 0))
        if proj_total > 0:
            edge = round(proj_total - market_total, 3)
            vol = 0.55
            conf = confidence_score(edge, volatility=vol)
            rec = bet_recommendation(conf, market_type="soccer_totals")
            result["confidence_engine"] = {
                "edge": edge,
                "confidence": conf,
                "recommendation": rec,
            }
    except Exception as e:
        print(f"[WARNING] Confidence engine error: {e}")
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
            league=league,
            prices={k: (result.get("auto_odds") or {}).get(src)
                    for k, src in (("over", "over_price"), ("under", "under_price"),
                                   ("home_ml", "home_ml"), ("away_ml", "away_ml"),
                                   ("draw_ml", "draw_ml"))},
        )
        print(f"[OK] Soccer prediction stored to multisport_history.db")

    if push_discord:
        status = _push_full_result("soccer", home, away, result)
        print(f"[{ 'OK' if status else 'FAILED' }] Full soccer result pushed to Discord")

    return result


def run_basketball(home: str, away: str, league: Optional[str], market_line: Optional[float],
                   store_to_db: bool, push_discord: bool, market_total: Optional[float] = None,
                   home_ml: Optional[float] = None, away_ml: Optional[float] = None,
                   over_price: Optional[float] = None, under_price: Optional[float] = None,
                   game_date: Optional[str] = None, auto_odds: bool = True,
                   q1_spread: Optional[float] = None, q1_total: Optional[float] = None,
                   h1_spread: Optional[float] = None, h1_total: Optional[float] = None) -> Dict[str, Any]:
    """Basketball branch. auto_odds mirrors tennis: try
    live_odds.get_basketball_odds() BEFORE predicting so a bare call prices
    FG + H1 + Q1 moneyline/spread/total from the feed. Manual CLI values
    always win; a missing segment or an unlisted league (SBL) runs as
    UNLISTED (Simulation Only - No EV) instead of demanding 8 manual flags.
    """
    fetched: Dict[str, Any] = {}
    if auto_odds and market_line is None and market_total is None \
            and home_ml is None and away_ml is None:
        from live_odds import get_basketball_odds
        fetched = get_basketball_odds(home, away, league or "EuroLeague")
        if fetched.get("status") in ("live", "cached"):
            if fetched.get("spread_line") is not None:
                market_line = float(fetched["spread_line"])
            if fetched.get("total_line") is not None:
                market_total = float(fetched["total_line"])
            if fetched.get("home_ml") is not None:
                home_ml = fetched["home_ml"]
            if fetched.get("away_ml") is not None:
                away_ml = fetched["away_ml"]
            if fetched.get("over_price") is not None:
                over_price = fetched["over_price"]
            if fetched.get("under_price") is not None:
                under_price = fetched["under_price"]
            if fetched.get("q1_spread_line") is not None:
                q1_spread = float(fetched["q1_spread_line"])
            if fetched.get("q1_total_line") is not None:
                q1_total = float(fetched["q1_total_line"])
            if fetched.get("h1_spread_line") is not None:
                h1_spread = float(fetched["h1_spread_line"])
            if fetched.get("h1_total_line") is not None:
                h1_total = float(fetched["h1_total_line"])
    from euroleague_engine import run_cli
    command = ["--home", home, "--away", away, "--league", league or "EuroLeague"]
    for flag, value in (("--market-spread", market_line), ("--market-total", market_total),
                        ("--home-ml", home_ml), ("--away-ml", away_ml),
                        ("--over-price", over_price), ("--under-price", under_price),
                        ("--q1-spread", q1_spread), ("--q1-total", q1_total),
                        ("--h1-spread", h1_spread), ("--h1-total", h1_total)):
        if value is not None:
            command.extend([flag, str(value)])
    # Pass through segment moneylines as JSON so the engine can price Q1/H1
    # ML EV without new scalar flags.
    if fetched.get("status") in ("live", "cached"):
        seg_ml = {k: fetched[k] for k in (
            "q1_home_ml", "q1_away_ml", "h1_home_ml", "h1_away_ml",
            "q1_spread_home_price", "q1_spread_away_price",
            "h1_spread_home_price", "h1_spread_away_price",
            "q1_over_price", "q1_under_price",
            "h1_over_price", "h1_under_price",
            "spread_home_price", "spread_away_price") if fetched.get(k) is not None}
        if seg_ml:
            import json as _json
            command.extend(["--segment-markets", _json.dumps(seg_ml)])
    if store_to_db:
        if not game_date:
            raise SystemExit("Basketball storage requires --game-date YYYY-MM-DD; use run_basketball.py for verified NBA/WNBA/NCAAB fixtures")
        command.extend(["--store-to-db", "--game-date", game_date])
    if push_discord:
        command.append("--push-discord")
    result = run_cli(command)
    if fetched:
        result["auto_odds"] = fetched
        status = fetched.get("status")
        if status in ("unknown_league", "not_covered", "no_fixture",
                      "no_bookmaker", "in_play", "error"):
            result["market_status"] = "UNLISTED (Simulation Only - No EV)"
            result["market_note"] = fetched.get("reason", "no market")
        else:
            result["market_status"] = status
    _display_full_result(result)
    return result


def run_baseball(home: str, away: str, league: Optional[str], markets: Optional[List[str]], market_total: float,
                 home_sp_era: Optional[float], home_sp_k: Optional[float],
                 away_sp_era: Optional[float], away_sp_k: Optional[float],
                 store_to_db: bool, push_discord: bool,
                 home_sp_limit: Optional[float] = None,
                 away_sp_limit: Optional[float] = None,
                 home_pitcher: Optional[str] = None, away_pitcher: Optional[str] = None,
                 home_hitters: Optional[List[str]] = None, away_hitters: Optional[List[str]] = None,
                 home_ml: Optional[float] = None, away_ml: Optional[float] = None,
                 over_price: Optional[float] = None, under_price: Optional[float] = None,
                 home_sp_name: Optional[str] = None, away_sp_name: Optional[str] = None,
                 home_key_batters: Optional[List[str]] = None,
                 away_key_batters: Optional[List[str]] = None,
                 runline: Optional[float] = None,
                 runline_home_price: Optional[float] = None,
                 runline_away_price: Optional[float] = None,
                 market_total_given: bool = False,
                 auto_odds: bool = True,
                 game_date: Optional[str] = None, fixture: Optional[dict] = None) -> Dict[str, Any]:
    """Baseball branch. auto_odds mirrors the tennis default: try
    live_odds.get_mlb_odds() BEFORE predicting so a bare
    `--match "A vs B"` still prices moneyline + run line + total from the
    feed. Manual CLI values always win; a missing market falls back to the
    caller default, labelled simulation-only rather than a real price.
    """
    from predict_match import run_baseball_game

    market_source = "user" if market_total_given or home_ml is not None else "default"
    market_note: Optional[str] = None
    fetched: Dict[str, Any] = {}
    league_norm = (league or "MLB").strip().upper()
    if auto_odds and league_norm == "MLB" and not (
            market_total_given and home_ml is not None and away_ml is not None
            and over_price is not None and runline is not None):
        from live_odds import get_mlb_odds
        fetched = get_mlb_odds(home, away)
        if fetched.get("status") in ("live", "cached"):
            if not market_total_given and fetched.get("total_line") is not None:
                market_total = float(fetched["total_line"])
            if home_ml is None and fetched.get("home_ml") is not None:
                home_ml = fetched["home_ml"]
            if away_ml is None and fetched.get("away_ml") is not None:
                away_ml = fetched["away_ml"]
            if over_price is None and fetched.get("over_price") is not None:
                over_price = fetched["over_price"]
            if under_price is None and fetched.get("under_price") is not None:
                under_price = fetched["under_price"]
            if runline is None and fetched.get("runline") is not None:
                runline = float(fetched["runline"])
            if runline_home_price is None and fetched.get("runline_home_price") is not None:
                runline_home_price = fetched["runline_home_price"]
            if runline_away_price is None and fetched.get("runline_away_price") is not None:
                runline_away_price = fetched["runline_away_price"]
            market_source = fetched["status"]
        else:
            market_note = str(fetched.get("reason", "no market"))
            market_source = "none"


    advanced_args = (home_pitcher, away_pitcher, home_hitters, away_hitters)
    if any(value is not None for value in advanced_args):
        if not all(advanced_args):
            raise ValueError("Advanced MLB mode requires both pitchers and non-empty hitter lists.")
        from predict_mlb_advanced import MLBAdvancedPredictor

        seed_path = Path("data/mlb_stats.json")
        if not seed_path.exists():
            raise ValueError("Missing data/mlb_stats.json. Run ingest_mlb_props.py first.")
        result = MLBAdvancedPredictor(seed_path).predict(
            home_team=home,
            away_team=away,
            home_pitcher=home_pitcher,
            away_pitcher=away_pitcher,
            home_hitters=home_hitters,
            away_hitters=away_hitters,
            market_lines={"f5": market_total, "full_game": market_total},
        )
        _display_full_result(result)
        if push_discord:
            status = _push_full_result("baseball", home, away, result)
            print(f"[{ 'OK' if status else 'FAILED' }] Full baseball result pushed to Discord")
        return result

    # K/9 is strikeouts per NINE INNINGS, so the denominator has to be batters
    # faced per nine innings -- about 4.25 per inning, so ~38.
    #
    # This was 5.5 * 4.3 = 23.65, which is batters faced in an average START.
    # Dividing a per-nine number by a per-start number inflated every starter's
    # strikeout rate by about 60%: Sean Burke at 9.7 K/9 came out as a .41
    # strikeout rate, which no pitcher in history has posted. NRFI reads
    # k_rate directly, so every NRFI this project has produced was too high --
    # a Pirates/White Sox game priced at 72% when the league baseline is 53%.
    batters_faced_est = 9.0 * 4.25
    home_sp_overrides = None
    if home_sp_era is not None or home_sp_k is not None or home_sp_limit is not None:
        home_sp_overrides = {}
        if home_sp_era is not None:
            home_sp_overrides["era"] = float(home_sp_era)
        if home_sp_k is not None:
            home_sp_overrides["k_rate"] = max(
                0.0, min(0.60, float(home_sp_k) / batters_faced_est)
            )
            # The prop model needs the rate per nine, not per batter faced.
            # Only k_rate was passed, so the starter never reached the
            # strikeout projection at all -- it used the staff rate for all
            # nine innings no matter who was pitching.
            home_sp_overrides["k9"] = float(home_sp_k)
        if home_sp_limit is not None:
            home_sp_overrides["pitch_limit"] = float(home_sp_limit)

    away_sp_overrides = None
    if away_sp_era is not None or away_sp_k is not None or away_sp_limit is not None:
        away_sp_overrides = {}
        if away_sp_era is not None:
            away_sp_overrides["era"] = float(away_sp_era)
        if away_sp_k is not None:
            away_sp_overrides["k_rate"] = max(
                0.0, min(0.60, float(away_sp_k) / batters_faced_est)
            )
            away_sp_overrides["k9"] = float(away_sp_k)
        if away_sp_limit is not None:
            away_sp_overrides["pitch_limit"] = float(away_sp_limit)

    # Real team metrics, written daily by ingest_all_sports.py. Missing data is
    # reported rather than silently replaced with a league average.
    from team_stats_provider import get_baseball_team_stats

    team_overrides: Dict[str, float] = {}
    seeded = {}
    for side, team_name in (("home", home), ("away", away)):
        stats = get_baseball_team_stats(team_name, league)
        seeded[side] = bool(stats)
        if not stats:
            adapter = "kbo" if (league or "").strip().upper() == "KBO" else "mlb"
            print(f"[WARNING] No real team stats for '{team_name}'. This matchup will fall "
                  f"back to league averages. Fix: python ingest_all_sports.py --only {adapter}")
            continue
        for field in ("runs", "runs_allowed", "era", "whip", "obp", "slg", 
                       "k9", "avg", "ops", "bb9"):
            value = stats.get(field)
            if value is not None:
                team_overrides[f"{side}_{field}"] = float(value)
    if all(seeded.values()):
        print(f"[OK] Loaded real team metrics for {home} and {away}")

    # Starter names are display metadata: they ride to the prediction dict
    # so the card can name them. The advanced path resolves home_pitcher /
    # away_pitcher itself; here prefer the explicit sp_name (from the
    # probables feed via run_mlb.py), falling back to home_pitcher alias.
    resolved_home_sp = home_sp_name or home_pitcher
    resolved_away_sp = away_sp_name or away_pitcher
    # Key-batter lists ride along verbatim; advanced hitter lists double as
    # the lineup when no separate key-batter feed is wired.
    resolved_home_batters = home_key_batters or home_hitters
    resolved_away_batters = away_key_batters or away_hitters
    result = run_baseball_game(
        home, away, league=league or "MLB",
        markets=markets or ["nrfi", "strikeouts", "home_runs"],
        market_total=market_total,
        home_sp_overrides=home_sp_overrides,
        away_sp_overrides=away_sp_overrides,
        team_overrides=team_overrides or None,
        home_ml=home_ml, away_ml=away_ml,
        home_sp_name=resolved_home_sp, away_sp_name=resolved_away_sp,
        home_key_batters=resolved_home_batters,
        away_key_batters=resolved_away_batters,
    )
    if game_date:
        result["game_date"] = game_date
    if fixture:
        result["fixture"] = fixture
    if fetched:
        result["auto_odds"] = fetched
    result["market_status"] = ("UNLISTED (Simulation Only - No EV)"
                               if market_source == "none" else market_source)
    if market_note:
        result["market_note"] = market_note
    if runline is not None:
        result["market_runline"] = {"runline": runline,
                                    "runline_home_price": runline_home_price,
                                    "runline_away_price": runline_away_price,
                                    "source": market_source}
    if over_price is not None or under_price is not None:
        result["market_totals_prices"] = {"over_price": over_price,
                                          "under_price": under_price,
                                          "source": market_source}
    _display_full_result(result)

    summary = result.get("summary", {})
    conf = float(summary.get("confidence", 50.0))
    rec = summary.get("recommendation", "PASS")
    edge = float(summary.get("edge_value", 0.0))
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
            league=league or "MLB",
            prices={"home_ml": home_ml, "away_ml": away_ml,
                    "over": over_price, "under": under_price},
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
            f"K Props: {strikeouts.get('home_projection', 0.0):.1f}"
            f" home / {strikeouts.get('away_projection', 0.0):.1f} away",
            f"HR Props: {home_runs.get('home_projection', 0.0):.1f}"
            f" home / {home_runs.get('away_projection', 0.0):.1f} away",
        ])
        # Add F5 betting slip if available
        f5 = props.get("f5", {})
        if f5.get("total") is not None:
            f5_slip = []
            f5_slip.append(f"    F5 Total: {f5.get('total'):.2f} ({f5.get('recommendation_over', 'PASS')})")
            f5_slip.append(f"    F5 Moneyline: {home} {f5.get('home_fair_odds', '-')} / {away} {f5.get('away_fair_odds', '-')}")
            f5_rl = f5.get("run_line_rec")
            if f5_rl and f5_rl != "PASS":
                f5_slip.append(f"    F5 Run Line: {f5_rl}")
            full_slip_message += "\n" + "\n".join(f5_slip)

        print(f"\nFull betting slip for {home} vs {away}:\n{full_slip_message}")
        status = _push_full_result("baseball", home, away, result)
        print(f"[{ 'OK' if status else 'FAILED' }] Full baseball result pushed to Discord")

    return result


def run_nfl(home: str, away: str, *,
            market_spread: Optional[float] = None,
            market_total: Optional[float] = None,
            market_home_ml: Optional[float] = None,
            market_away_ml: Optional[float] = None,
            spread_home_price: Optional[float] = None,
            spread_away_price: Optional[float] = None,
            over_price: Optional[float] = None,
            under_price: Optional[float] = None,
            neutral_site: bool = False,
            store_to_db: bool = True,
            push_discord: bool = False,
            game_date: Optional[str] = None) -> Dict[str, Any]:
    """NFL branch: points model -> spread, moneyline, total, halftime.

    Each market is stored as its own row, because they settle separately and a
    single row cannot record that the spread lost while the total won.

    THE SPREAD PICK IS WRITTEN DOWN. Soccer and basketball spreads in this
    database are permanently ungradable: model_value holds a number but nothing
    records which side it belongs to, so the grader cannot tell a cover from a
    push. That is not repeated here -- the side goes into `pick` at prediction
    time, when it is still known.
    """
    from models.nfl_predictor import predict_nfl_game, describe, clean_team
    from ingest_nfl_schedule import resolve_fixture
    fixture = resolve_fixture(home, away, date=game_date)
    if clean_team(home) != fixture["home_team"] or clean_team(away) != fixture["away_team"]:
        raise ValueError("NFL home/away order must match the verified fixture")

    result = predict_nfl_game(
        home, away,
        market_spread=market_spread, market_total=market_total,
        market_home_ml=market_home_ml, market_away_ml=market_away_ml,
        neutral_site=neutral_site,
    )
    # Belt-and-braces: the predictor already returns clean names, but any
    # caller passing a year-tagged string must never let "(YYYY)" reach the
    # DB, Discord, or the grader -- ESPN feeds carry no such suffix.
    result["home"] = clean_team(result.get("home", home))
    result["away"] = clean_team(result.get("away", away))
    moneyline = result.get("moneyline") or {}
    moneyline["home"] = result["home"]
    moneyline["away"] = result["away"]
    result["match"] = f"{result['home']} vs {result['away']}"
    result["fixture"] = fixture
    result["game_date"] = fixture["date"]

    print()
    print(describe(result))
    print()

    if store_to_db:
        spread, total, moneyline = (result["spread"], result["total"],
                                    result["moneyline"])
        blend = result["prior_blend"]
        # Confidence is capped while the model is running on a prior season. A
        # number derived entirely from last year should not present itself with
        # the same conviction as one built on games that have been played.
        cap = 60.0 if blend["current_season_weight"] < 0.5 else 100.0

        rows = []
        if spread.get("market_spread") is not None:
            cover = float(spread.get("cover_prob", 0.5))
            rows.append(("spread", cover, 0.5,
                         float(spread.get("edge_points", 0.0)),
                         min(abs(cover - 0.5) * 200.0, cap),
                         spread.get("pick", "PASS")))
        if total.get("market_total") is not None:
            rows.append(("total", float(total["model_total"]),
                         float(total["market_total"]),
                         float(total.get("edge_points", 0.0)),
                         min(abs(float(total.get("edge_points", 0.0))) * 12.0, cap),
                         total.get("pick", "PASS")))
        if moneyline.get("market_home_prob") is not None:
            rows.append(("moneyline", float(moneyline["home_win_probability"]),
                         float(moneyline["market_home_prob"]),
                         float(moneyline.get("edge_pct", 0.0)),
                         min(abs(float(moneyline.get("edge_pct", 0.0))) * 4.0, cap),
                         moneyline.get("recommendation", "PASS")))

        stored = 0
        for market_type, model_value, market_value, edge, confidence, pick in rows:
            stored += bool(_store_prediction(
                sport="nfl", home=result["home"], away=result["away"],
                market_type=market_type, model_value=model_value,
                market_value=market_value, edge=edge, confidence=confidence,
                recommendation=pick,
                raw_json={**result, "_pick": pick, "_market": market_type,
                          "event_key": f"nfl:{fixture['game_id']}:{market_type}"},
                league="NFL",
                prices={"home_ml": market_home_ml, "away_ml": market_away_ml,
                        "spread_home_price": spread_home_price,
                        "spread_away_price": spread_away_price,
                        "over": over_price, "under": under_price},
            ))
        if stored == len(rows) and rows:
            print(f"[OK] {stored} NFL market(s) stored to multisport_history.db")
        elif rows:
            print(f"[WARN] only {stored} of {len(rows)} NFL market(s) stored -- "
                  f"the rest are NOT in the database")
        else:
            print("[skip] No market lines supplied, so nothing was stored -- a "
                  "projection with no price is not a bet.")

    if push_discord:
        status = _push_full_result("nfl", result["home"], result["away"], result)
        print(f"[{'OK' if status else 'FAILED'}] NFL result pushed to Discord")

    return result


def run_tennis(home: str, away: str, surface: str, tournament: Optional[str],
               round_name: Optional[str], best_of_5: bool,
               store_to_db: bool, push_discord: bool,
               market_prob: Optional[float] = None,
               tour: Optional[str] = None, auto_odds: bool = True,
               home_ml: Optional[float] = None, away_ml: Optional[float] = None,
               custom_markets: Optional[List[Dict[str, Any]]] = None,
               player_context: Optional[Dict[str, Any]] = None,
               game_date: Optional[str] = None) -> Dict[str, Any]:
    """Tennis branch: call the real predictor directly (bypass predict_match.py).

    market_prob is the de-vigged probability the book gives `home`. Without it
    the predictor measures its number against 0.5, so "edge" means distance
    from a coin flip rather than disagreement with a price -- a number that
    looks like an edge and is not one. Passing it makes the edge real; leaving
    it None is honest about there being no market to compare against.

    When market_prob isn't given (no --p1-ml/--p2-ml typed), auto_odds tries
    live_odds.get_tennis_odds() before falling back to "no market" -- this is
    the fix for a run producing "PASS, model probability only" not because
    there's no edge, but because nobody typed a price in, which is why the
    same match used to get run twice. tour ("atp"/"wta") is required for the
    auto-fetch since The Odds API keys tennis per tour+tournament, not
    generally; the caller already knows it (it's what picks best_of_5).
    """
    from models.tennis_predictor import predict_tennis_match

    auto_odds_result: Dict[str, Any] = {}
    if auto_odds and tour:
        from live_odds import get_tennis_odds
        auto_odds_result = get_tennis_odds(tour, home, away)
        if auto_odds_result.get("status") in ("live", "cached"):
            if home_ml is None and away_ml is None:
                home_ml = auto_odds_result.get("home_ml")
                away_ml = auto_odds_result.get("away_ml")
            if market_prob is None and home_ml is not None and away_ml is not None:
                home_p = (-home_ml) / ((-home_ml) + 100.0) if home_ml < 0 else 100.0 / (home_ml + 100.0)
                away_p = (-away_ml) / ((-away_ml) + 100.0) if away_ml < 0 else 100.0 / (away_ml + 100.0)
                total = home_p + away_p
                if total > 0:
                    market_prob = home_p / total

    manual_markets = list(custom_markets or [])
    overridden_kinds = {m["kind"] for m in manual_markets if not m.get("line_origin", "").startswith("live")}
    automatic_markets = [m for m in auto_odds_result.get("custom_markets", [])
                         if m["kind"] not in overridden_kinds]
    custom_markets = manual_markets + automatic_markets
    if auto_odds_result.get("status") in ("live", "cached"):
        covered = {m["kind"] for m in custom_markets}
        missing = sorted({"games_total", "games_spread", "sets_total", "sets_spread"} - covered)
        if missing:
            print("No priced tennis lines for: " + ", ".join(missing) + ". Supply manual flags if available at your book.")
    if auto_odds_result.get("additional_markets_error"):
        print(f"Additional tennis lines unavailable: {auto_odds_result['additional_markets_error']}; main lines retained.")
    result = predict_tennis_match(
        home_player=home,
        away_player=away,
        surface=surface or "grass",
        best_of_5=best_of_5,
        tournament=tournament,
        round_name=round_name,
        market_prob=market_prob,
        market_home_odds=str(home_ml) if home_ml is not None else None,
        market_away_odds=str(away_ml) if away_ml is not None else None,
        custom_markets=custom_markets, player_context=player_context,
    )
    result["surface"] = surface
    result["best_of_5"] = best_of_5
    result["custom_markets"] = custom_markets
    if auto_odds_result:
        result["auto_odds"] = auto_odds_result
    from sports_feed import EASTERN
    import datetime as fixture_dt
    commence = auto_odds_result.get("commence_time")
    verified_date = None
    if commence:
        verified_date = fixture_dt.datetime.fromisoformat(commence.replace("Z", "+00:00")).astimezone(EASTERN).date().isoformat()
    if game_date:
        fixture_dt.date.fromisoformat(game_date)
        if verified_date and game_date != verified_date:
            raise ValueError(f"Supplied date {game_date} disagrees with odds fixture {verified_date}")
    result["game_date"] = game_date or verified_date
    result["fixture_status"] = "matched odds event" if verified_date else "unverified player pairing"
    if result["game_date"]:
        result["event_key"] = f"tennis:{result['game_date']}:{home}:{away}:moneyline"
    if result["game_date"]:
        print(f"Fixture date: {result['game_date']} ({result['fixture_status']})")
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
            market_value=market_prob if market_prob is not None else 0.5,
            edge=edge,
            confidence=conf,
            recommendation=rec,
            raw_json=result,
            prices={"home_ml": home_ml, "away_ml": away_ml},
        )
        print(f"[OK] Tennis prediction stored to multisport_history.db")

    if push_discord:
        status = _push_full_result("tennis", home, away, result)
        print(f"[{ 'OK' if status else 'FAILED' }] Full tennis result pushed to Discord")

    return result


# ============================================================================
# MAIN
# ============================================================================

def _lookup_mlb_odds(home: str, away: str, fallback_total: float):
    """This game's live moneyline and total, or what was passed in.

    run_mlb.fetch_live_odds() already does the API call, the team-name
    matching and the quota logging, so it is reused rather than re-written.
    Failure returns the fallback: a missing price must not become a made-up
    one (the card then says plainly that no market was supplied).
    """
    try:
        from run_mlb import fetch_live_odds, _odds_key   # type: ignore
    except Exception:                                     # noqa: BLE001
        from run_mlb import fetch_live_odds              # type: ignore
        _odds_key = None                                  # type: ignore
    try:
        totals, mls = fetch_live_odds()
    except Exception as exc:                              # noqa: BLE001
        print(f"[odds] lookup failed ({type(exc).__name__}) -- no market prices.")
        return None, None, fallback_total

    def norm(name: str) -> str:
        return "".join(ch for ch in str(name).lower() if ch.isalnum())

    for key, (h_ml, a_ml) in mls.items():
        parts = key.split("|")
        if len(parts) != 2:
            continue
        k_home, k_away = norm(parts[0]), norm(parts[1])
        n_home, n_away = norm(home), norm(away)
        hit = ((n_home in k_home or k_home in n_home) and
               (n_away in k_away or k_away in n_away))
        if hit:
            total = totals.get(key, fallback_total)
            print(f"[odds] {away} {a_ml:+.0f} @ {home} {h_ml:+.0f}, total {total}")
            return h_ml, a_ml, total
    print(f"[odds] no live market found for {away} @ {home} -- "
          f"card will say no market odds were supplied.")
    return None, None, fallback_total


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Universal match prediction hub (canonical runner for all sports)."
    )
    parser.add_argument("--sport", required=True,
                        help="Sport: soccer, basketball, baseball/mlb, kbo, tennis")
    parser.add_argument("--home", required=True, help="Home team / player")
    parser.add_argument("--away", required=True, help="Away team / player")
    parser.add_argument("--game-date", default=None, help="Actual fixture date YYYY-MM-DD")
    parser.add_argument("--league", default=None, help="League name (e.g. Eredivisie, MLB)")
    parser.add_argument("--markets", nargs="+", default=None,
                        help="Baseball prop markets (nrfi strikeouts home_runs).")
    parser.add_argument("--market-line", type=float, default=None,
                        help="Basketball/soccer market line (spread/handicap).")
    parser.add_argument("--market-total", type=float, default=None,
                        help="Market total (over/under).")
    parser.add_argument("--store-to-db", action="store_true",
                        help="Store prediction in core.historical_storage.")
    parser.add_argument("--push-discord", action="store_true",
                        help="Push result to Discord.")
    parser.add_argument("--live-odds", action="store_true",
                        help="Fetch matched live soccer odds when ODDS_API_KEY is configured (default: auto-fetch on).")
    parser.add_argument("--no-odds", action="store_true",
                        help="Soccer/baseball: skip the Odds API auto-fetch (projection only, labelled UNLISTED).")
    # MLB market prices. run_baseball() has always accepted these, but main()
    # had no flags for them, so every CLI run (auto_mlb_scraper included) went
    # in with no moneyline and every card read "no market odds supplied".
    parser.add_argument("--home-ml", type=float, default=None,
                        help="Home moneyline, American odds (e.g. -125).")
    parser.add_argument("--away-ml", type=float, default=None,
                        help="Away moneyline, American odds (e.g. +105).")
    parser.add_argument("--draw-ml", type=float, default=None,
                        help="Soccer draw moneyline, American odds (e.g. +220).")
    parser.add_argument("--spread-home-price", type=float, default=None,
                        help="Price on the home side of the spread/handicap.")
    parser.add_argument("--spread-away-price", type=float, default=None,
                        help="Price on the away side of the spread/handicap.")
    parser.add_argument("--runline", type=float, default=None,
                        help="Baseball run line (usually +/-1.5).")
    parser.add_argument("--runline-home-price", type=float, default=None)
    parser.add_argument("--runline-away-price", type=float, default=None)
    parser.add_argument("--over-price", type=float, default=None)
    parser.add_argument("--under-price", type=float, default=None)
    parser.add_argument("--auto-odds", action="store_true",
                        help="MLB: look up this game's live moneyline/total "
                             "(needs ODDS_API_KEY) when prices are not passed.")
    # MLB SP overrides
    parser.add_argument("--home-sp-era", type=float, default=None)
    parser.add_argument("--home-sp-k", type=float, default=None)
    parser.add_argument("--away-sp-era", type=float, default=None)
    parser.add_argument("--away-sp-k", type=float, default=None)
    parser.add_argument("--home-pitcher", default=None)
    parser.add_argument("--away-pitcher", default=None)
    parser.add_argument("--home-hitters", nargs="+", default=None)
    parser.add_argument("--away-hitters", nargs="+", default=None)
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

    if sport == "ncaaf" or (sport in ("basketball", "nba", "wnba", "ncaab", "ncaaw") and
                             str(args.league or sport).upper() in {"NBA", "WNBA", "NCAAB", "NCAAW"}):
        from run_ncaaf import main as run_score, push as push_score
        score_sport = "ncaaf" if sport == "ncaaf" else "basketball"
        score_args = ["--league", "NCAAF" if sport == "ncaaf" else str(args.league or sport).upper(),
                      "--match", f"{home} vs {away}"]
        if args.game_date:
            score_args += ["--date", args.game_date]
        if args.live_odds:
            score_args.append("--odds")
        else:
            if args.home_ml is not None or args.away_ml is not None:
                score_args += ["--moneyline", str(args.home_ml) if args.home_ml is not None else "none",
                               str(args.away_ml) if args.away_ml is not None else "none"]
            if args.market_line is not None:
                score_args += ["--spread", str(args.market_line), "none", "none"]
            if args.market_total is not None:
                score_args += ["--total", str(args.market_total),
                               str(args.over_price) if args.over_price is not None else "none",
                               str(args.under_price) if args.under_price is not None else "none"]
        if not args.store_to_db:
            score_args.append("--dry-run")
        results = run_score(score_sport, score_args)
        if args.push_discord:
            for result in results:
                if not push_score(result):
                    raise SystemExit("Discord push failed")
    elif sport in ("soccer", "football"):
        run_soccer(home, away, args.league, args.market_line if args.market_line is not None else 0.0, args.market_total if args.market_total is not None else 2.5,
                   args.store_to_db, args.push_discord, args.live_odds,
                   auto_odds=not args.no_odds,
                   market_total_given=args.market_total is not None,
                   market_line_given=args.market_line is not None,
                   home_ml=args.home_ml, draw_ml=args.draw_ml,
                   away_ml=args.away_ml, over_price=args.over_price,
                   under_price=args.under_price,
                   spread_home_price=args.spread_home_price,
                   spread_away_price=args.spread_away_price, game_date=args.game_date)
    elif sport in ("basketball", "kbl", "nznbl", "euroleague", "eurocup", "liga acb", "acb"):
        run_basketball(home, away, args.league, args.market_line,
                       args.store_to_db, args.push_discord, args.market_total,
                       args.home_ml, args.away_ml, args.over_price, args.under_price, args.game_date)
    elif sport in ("baseball", "mlb", "kbo"):
        home_ml, away_ml = args.home_ml, args.away_ml
        market_total = args.market_total if args.market_total is not None else 8.5
        # auto_odds is the default (tennis parity): only --no-odds disables.
        # The legacy --auto-odds flag is kept for compat but no longer gates.
        run_baseball(home, away, args.league, args.markets, market_total,
                     args.home_sp_era, args.home_sp_k,
                     args.away_sp_era, args.away_sp_k,
                     args.store_to_db, args.push_discord,
                     home_pitcher=args.home_pitcher, away_pitcher=args.away_pitcher,
                     home_hitters=args.home_hitters, away_hitters=args.away_hitters,
                     home_ml=home_ml, away_ml=away_ml,
                     over_price=args.over_price, under_price=args.under_price,
                     runline=args.runline,
                     runline_home_price=args.runline_home_price,
                     runline_away_price=args.runline_away_price,
                     market_total_given=args.market_total is not None,
                     auto_odds=not args.no_odds)
    elif sport == "tennis":
        run_tennis(home, away, args.surface, args.tournament, args.round_name,
                   best_of_5, args.store_to_db, args.push_discord)
    else:
        print(f"Unsupported sport: {sport}")
        sys.exit(1)


if __name__ == "__main__":
    main()
