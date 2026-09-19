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
) -> bool:
    """Log a prediction to core.historical_storage. Returns whether it landed.

    This used to return None and swallow the exception, so a caller counting
    its own loop reported "3 stored" when two had failed with disk I/O errors
    printed one line above. A write that did not happen is not a write.
    """
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
               push_discord: bool, live_odds: bool = False,
               auto_odds: bool = True, market_total_given: bool = False) -> Dict[str, Any]:
    """
    auto_odds: try live_odds.get_soccer_odds() BEFORE predicting, so the
    prediction itself (not just an attached "live_market" afterthought) is
    built against a real total when one is fetchable. This is the fix for
    "PASS, model probability only" runs that used to need a second, manual
    re-run once someone typed a price in -- see live_odds.py.

    market_total_given: True when the CALLER explicitly supplied a real
    market_total (CLI flag or slate file), not the bare 2.5 default. A real
    caller-supplied number always wins over an auto-fetch; auto-fetch only
    fills the gap when nothing was actually given.
    """
    from predict_match import run_soccer_game

    hs = get_soccer_team_stats(home, league)
    aws = get_soccer_team_stats(away, league)
    if hs is None or aws is None:
        raise ValueError(f"Stats missing for '{home}' or '{away}'. Seed stats in team_stats_provider.py before running.")

    fetched_market: Dict[str, Any] = {}
    if auto_odds and not market_total_given:
        from live_odds import get_soccer_odds
        fetched_market = get_soccer_odds(league, home, away)
        if fetched_market.get("status") in ("live", "cached") and fetched_market.get("total_line") is not None:
            market_total = float(fetched_market["total_line"])

    result = run_soccer_game(home, away, league=league or "Premier League",
                             market_line=market_line, market_total=market_total,
                             home_stats=hs, away_stats=aws)
    if fetched_market:
        result["auto_odds"] = fetched_market

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
        )
        print(f"[OK] Soccer prediction stored to multisport_history.db")

    if push_discord:
        status = _push_full_result("soccer", home, away, result)
        print(f"[{ 'OK' if status else 'FAILED' }] Full soccer result pushed to Discord")

    return result


def run_basketball(home: str, away: str, league: Optional[str], market_line: float,
                   store_to_db: bool, push_discord: bool) -> Dict[str, Any]:
    normalized_league = (league or "EuroLeague").strip().lower()
    if normalized_league in {"euroleague", "kbl", "nznbl"}:
        from euroleague_engine import EuroleaguePredictor
        from team_stats_provider import get_basketball_team_stats, get_euroleague_league_baseline, get_euroleague_team_stats

        if normalized_league == "euroleague":
            hs = get_euroleague_team_stats(home)
            aws = get_euroleague_team_stats(away)
            baseline = get_euroleague_league_baseline()
        else:
            hs = get_basketball_team_stats(home, normalized_league)
            aws = get_basketball_team_stats(away, normalized_league)
            baseline = {"pace": 72.0, "ortg": 112.0, "drtg": 112.0}
        if hs is None or aws is None:
            raise ValueError(f"Missing seeded stats for '{home}' or '{away}'. Please seed data.")
        result = EuroleaguePredictor(
            home_team=home,
            away_team=away,
            home_stats=hs,
            away_stats=aws,
            league_baseline=baseline,
            market_lines={"full_game": market_line},
        ).predict()
        _display_full_result(result)
        full_game = result["full_game"]
        if store_to_db:
            _store_prediction(
                sport="basketball",
                home=home,
                away=away,
                market_type="spread",
                model_value=float(full_game["probability"]),
                market_value=market_line,
                edge=float(full_game["model_edge"] or 0.0),
                confidence=float(full_game["probability"]) * 100.0,
                recommendation=str(full_game["lean"]),
                raw_json=result,
            )
            print("[OK] EuroLeague prediction stored to multisport_history.db")
        if push_discord:
            status = _push_full_result("basketball", home, away, result)
            print(f"[{ 'OK' if status else 'FAILED' }] Full basketball result pushed to Discord")
        return result

    from predict_match import run_basketball_game
    from team_stats_provider import get_basketball_team_stats

    hs = get_basketball_team_stats(home, league)
    aws = get_basketball_team_stats(away, league)
    if hs is None or aws is None:
        raise ValueError(f"Missing seeded stats for '{home}' or '{away}'. Please seed data.")
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
                 store_to_db: bool, push_discord: bool,
                 home_sp_limit: Optional[float] = None,
                 away_sp_limit: Optional[float] = None,
                 home_pitcher: Optional[str] = None, away_pitcher: Optional[str] = None,
                 home_hitters: Optional[List[str]] = None, away_hitters: Optional[List[str]] = None,
                 home_ml: Optional[float] = None, away_ml: Optional[float] = None) -> Dict[str, Any]:
    from predict_match import run_baseball_game

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

    result = run_baseball_game(
        home, away, league=league or "MLB",
        markets=markets or ["nrfi", "strikeouts", "home_runs"],
        market_total=market_total,
        home_sp_overrides=home_sp_overrides,
        away_sp_overrides=away_sp_overrides,
        team_overrides=team_overrides or None,
        home_ml=home_ml, away_ml=away_ml,
    )
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
            neutral_site: bool = False,
            store_to_db: bool = True,
            push_discord: bool = False) -> Dict[str, Any]:
    """NFL branch: points model -> spread, moneyline, total, halftime.

    Each market is stored as its own row, because they settle separately and a
    single row cannot record that the spread lost while the total won.

    THE SPREAD PICK IS WRITTEN DOWN. Soccer and basketball spreads in this
    database are permanently ungradable: model_value holds a number but nothing
    records which side it belongs to, so the grader cannot tell a cover from a
    push. That is not repeated here -- the side goes into `pick` at prediction
    time, when it is still known.
    """
    from models.nfl_predictor import predict_nfl_game, describe

    result = predict_nfl_game(
        home, away,
        market_spread=market_spread, market_total=market_total,
        market_home_ml=market_home_ml, market_away_ml=market_away_ml,
        neutral_site=neutral_site,
    )

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
                raw_json={**result, "_pick": pick, "_market": market_type},
                league="NFL",
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
               tour: Optional[str] = None, auto_odds: bool = True) -> Dict[str, Any]:
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
    if market_prob is None and auto_odds and tour:
        from live_odds import get_tennis_odds
        auto_odds_result = get_tennis_odds(tour, home, away)
        if auto_odds_result.get("status") in ("live", "cached"):
            home_ml, away_ml = auto_odds_result.get("home_ml"), auto_odds_result.get("away_ml")
            if home_ml is not None and away_ml is not None:
                home_p = (-home_ml) / ((-home_ml) + 100.0) if home_ml < 0 else 100.0 / (home_ml + 100.0)
                away_p = (-away_ml) / ((-away_ml) + 100.0) if away_ml < 0 else 100.0 / (away_ml + 100.0)
                total = home_p + away_p
                if total > 0:
                    market_prob = home_p / total

    result = predict_tennis_match(
        home_player=home,
        away_player=away,
        surface=surface or "grass",
        best_of_5=best_of_5,
        tournament=tournament,
        round_name=round_name,
        market_prob=market_prob,
    )
    if auto_odds_result:
        result["auto_odds"] = auto_odds_result
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

    if sport in ("soccer", "football"):
        run_soccer(home, away, args.league, args.market_line, args.market_total,
                   args.store_to_db, args.push_discord, args.live_odds)
    elif sport in ("basketball", "kbl", "nznbl", "euroleague", "eurocup", "liga acb", "acb"):
        run_basketball(home, away, args.league, args.market_line,
                       args.store_to_db, args.push_discord)
    elif sport in ("baseball", "mlb", "kbo"):
        run_baseball(home, away, args.league, args.markets, args.market_total,
                     args.home_sp_era, args.home_sp_k,
                     args.away_sp_era, args.away_sp_k,
                     args.store_to_db, args.push_discord,
                     args.home_pitcher, args.away_pitcher,
                     args.home_hitters, args.away_hitters)
    elif sport == "tennis":
        run_tennis(home, away, args.surface, args.tournament, args.round_name,
                   best_of_5, args.store_to_db, args.push_discord)
    else:
        print(f"Unsupported sport: {sport}")
        sys.exit(1)


if __name__ == "__main__":
    main()
