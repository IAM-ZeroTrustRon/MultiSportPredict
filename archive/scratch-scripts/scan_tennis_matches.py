#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tennis Match Scanner
====================
Scans all active ATP & WTA tournaments via The Odds API and runs the
Dominance Ratio model on each upcoming match.

Usage:
    python scan_tennis_matches.py
    python scan_tennis_matches.py --tours atp          # ATP only
    python scan_tennis_matches.py --tours wta          # WTA only
    python scan_tennis_matches.py --tours atp wta      # Both (default)
    python scan_tennis_matches.py --save               # Save results to JSON
    python scan_tennis_matches.py --min-conf 65        # Filter by confidence

Requires:
    ODDS_API_KEY env var (from https://the-odds-api.com)

Output:
    Rich dashboard table + optional JSON to output/tennis/scan_<date>.json
"""

from __future__ import annotations

import json
import logging
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rich (optional)
# ---------------------------------------------------------------------------
try:
    import io
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    _RICH = True
    # Force UTF-8 output on Windows to avoid CP1252 encoding issues
    _utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    console = Console(file=_utf8_stdout, highlight=False)
except (ImportError, AttributeError):
    _RICH = False
    console = None  # type: ignore

# ---------------------------------------------------------------------------
# Tennis Tournament Keys (The Odds API)
# ---------------------------------------------------------------------------
ATP_KEYS: List[str] = [
    "tennis_atp_wimbledon",
    "tennis_atp_queens_club_champ",
    "tennis_atp_halle_open",
    "tennis_atp_french_open",
    "tennis_atp_italian_open",
    "tennis_atp_madrid_open",
    "tennis_atp_us_open",
    "tennis_atp_aus_open_singles",
    "tennis_atp_canadian_open",
    "tennis_atp_cincinnati_open",
    "tennis_atp_china_open",
    "tennis_atp_shanghai_masters",
    "tennis_atp_paris_masters",
    "tennis_atp_indian_wells",
    "tennis_atp_miami_open",
    "tennis_atp_monte_carlo_masters",
    "tennis_atp_barcelona_open",
    "tennis_atp_munich",
    "tennis_atp_hamburg_open",
    "tennis_atp_dubai",
    "tennis_atp_qatar_open",
]

WTA_KEYS: List[str] = [
    "tennis_wta_wimbledon",
    "tennis_wta_queens_club_champ",
    "tennis_wta_german_open",
    "tennis_wta_strasbourg",
    "tennis_wta_french_open",
    "tennis_wta_italian_open",
    "tennis_wta_madrid_open",
    "tennis_wta_us_open",
    "tennis_wta_aus_open_singles",
    "tennis_wta_canadian_open",
    "tennis_wta_cincinnati_open",
    "tennis_wta_china_open",
    "tennis_wta_indian_wells",
    "tennis_wta_miami_open",
    "tennis_wta_dubai",
    "tennis_wta_qatar_open",
    "tennis_wta_charleston_open",
    "tennis_wta_stuttgart_open",
    "tennis_wta_wuhan_open",
]

# Human-readable tournament labels
TOURNAMENT_LABELS: Dict[str, str] = {
    "tennis_atp_wimbledon":         "ATP Wimbledon",
    "tennis_atp_queens_club_champ": "ATP Queen's Club",
    "tennis_atp_halle_open":        "ATP Halle Open",
    "tennis_atp_french_open":       "ATP French Open",
    "tennis_atp_italian_open":      "ATP Italian Open",
    "tennis_atp_madrid_open":       "ATP Madrid Open",
    "tennis_atp_us_open":           "ATP US Open",
    "tennis_atp_aus_open_singles":  "ATP Australian Open",
    "tennis_atp_canadian_open":     "ATP Canadian Open",
    "tennis_atp_cincinnati_open":   "ATP Cincinnati Open",
    "tennis_atp_china_open":        "ATP China Open",
    "tennis_atp_shanghai_masters":  "ATP Shanghai Masters",
    "tennis_atp_paris_masters":     "ATP Paris Masters",
    "tennis_atp_indian_wells":      "ATP Indian Wells",
    "tennis_atp_miami_open":        "ATP Miami Open",
    "tennis_atp_monte_carlo_masters": "ATP Monte Carlo",
    "tennis_atp_barcelona_open":    "ATP Barcelona Open",
    "tennis_atp_munich":            "ATP Munich Open",
    "tennis_atp_hamburg_open":      "ATP Hamburg Open",
    "tennis_atp_dubai":             "ATP Dubai Open",
    "tennis_atp_qatar_open":        "ATP Qatar Open",
    "tennis_wta_wimbledon":         "WTA Wimbledon",
    "tennis_wta_queens_club_champ": "WTA Queen's Club",
    "tennis_wta_german_open":       "WTA German Open",
    "tennis_wta_strasbourg":        "WTA Strasbourg",
    "tennis_wta_french_open":       "WTA French Open",
    "tennis_wta_italian_open":      "WTA Italian Open",
    "tennis_wta_madrid_open":       "WTA Madrid Open",
    "tennis_wta_us_open":           "WTA US Open",
    "tennis_wta_aus_open_singles":  "WTA Australian Open",
    "tennis_wta_canadian_open":     "WTA Canadian Open",
    "tennis_wta_cincinnati_open":   "WTA Cincinnati Open",
    "tennis_wta_china_open":        "WTA China Open",
    "tennis_wta_indian_wells":      "WTA Indian Wells",
    "tennis_wta_miami_open":        "WTA Miami Open",
    "tennis_wta_dubai":             "WTA Dubai",
    "tennis_wta_qatar_open":        "WTA Qatar Open",
    "tennis_wta_charleston_open":   "WTA Charleston Open",
    "tennis_wta_stuttgart_open":    "WTA Stuttgart Open",
    "tennis_wta_wuhan_open":        "WTA Wuhan Open",
}

# Court surface mapping (used for environmental multiplier in features)
SURFACE_MAP: Dict[str, str] = {
    "tennis_atp_wimbledon":         "Grass",
    "tennis_atp_queens_club_champ": "Grass",
    "tennis_atp_halle_open":        "Grass",
    "tennis_atp_french_open":       "Clay",
    "tennis_atp_italian_open":      "Clay",
    "tennis_atp_madrid_open":       "Clay",
    "tennis_atp_monte_carlo_masters": "Clay",
    "tennis_atp_barcelona_open":    "Clay",
    "tennis_atp_hamburg_open":      "Clay",
    "tennis_atp_munich":            "Clay",
    "tennis_wta_wimbledon":         "Grass",
    "tennis_wta_queens_club_champ": "Grass",
    "tennis_wta_german_open":       "Clay",
    "tennis_wta_strasbourg":        "Clay",
    "tennis_wta_french_open":       "Clay",
    "tennis_wta_italian_open":      "Clay",
    "tennis_wta_madrid_open":       "Clay",
    "tennis_wta_charleston_open":   "Clay",
    "tennis_wta_stuttgart_open":    "Clay",
}

SURFACE_SPEED_MAP = {
    "Clay":         0.85,
    "Hard_Outdoor": 1.00,
    "Hard_Indoor":  1.15,
    "Grass":        1.25,
}


# ---------------------------------------------------------------------------
# Odds API Client
# ---------------------------------------------------------------------------
class TennisOddsClient:
    """Lightweight wrapper for The Odds API tennis endpoints."""

    BASE_URL = "https://api.the-odds-api.com/v4"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.getenv("ODDS_API_KEY", "")
        self.available = bool(self.api_key)
        self._remaining_requests: Optional[int] = None
        self._remaining_quota: Optional[int] = None

    def fetch_events(self, sport_key: str) -> List[Dict]:
        """Fetch upcoming events for a tournament key."""
        if not self.available:
            return []
        try:
            import requests
            url = f"{self.BASE_URL}/sports/{sport_key}/events"
            params = {"apiKey": self.api_key, "dateFormat": "iso"}
            r = requests.get(url, params=params, timeout=(8, 20))
            # Track quota headers
            self._remaining_requests = r.headers.get("x-requests-remaining")
            self._remaining_quota = r.headers.get("x-requests-used")
            if r.status_code == 404:
                return []   # tournament not currently active
            r.raise_for_status()
            return r.json() if isinstance(r.json(), list) else []
        except Exception as e:
            logger.debug("Error fetching events for %s: %s", sport_key, e)
            return []

    def fetch_odds(self, sport_key: str) -> List[Dict]:
        """Fetch h2h odds for all matches in a tournament."""
        if not self.available:
            return []
        try:
            import requests
            url = f"{self.BASE_URL}/sports/{sport_key}/odds"
            params = {
                "apiKey": self.api_key,
                "regions": "us",
                "markets": "h2h",
                "oddsFormat": "decimal",
                "dateFormat": "iso",
            }
            r = requests.get(url, params=params, timeout=(8, 25))
            self._remaining_requests = r.headers.get("x-requests-remaining")
            if r.status_code == 404:
                return []
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.debug("Error fetching odds for %s: %s", sport_key, e)
            return []


# ---------------------------------------------------------------------------
# Tennis Model
# ---------------------------------------------------------------------------

def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def decimal_to_prob(odds: float) -> float:
    """Convert decimal odds to raw implied probability."""
    if odds and odds > 1.0:
        return 1.0 / odds
    return 0.0


def normalize_probs(p1: float, p2: float) -> Tuple[float, float]:
    """Remove bookmaker vig (normalize to sum = 1.0)."""
    total = p1 + p2
    if total <= 0:
        return 0.5, 0.5
    return p1 / total, p2 / total


def extract_moneyline(match_data: Dict) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract median h2h moneyline odds (player_a, player_b) from bookmakers.
    Returns (None, None) if no odds found.
    """
    home = match_data.get("home_team", "")
    away = match_data.get("away_team", "")
    home_odds_list: List[float] = []
    away_odds_list: List[float] = []

    for bk in match_data.get("bookmakers", []):
        for market in bk.get("markets", []):
            if market.get("key") != "h2h":
                continue
            for outcome in market.get("outcomes", []):
                name = outcome.get("name", "")
                price = outcome.get("price")
                if price is None:
                    continue
                if name.lower() == home.lower():
                    home_odds_list.append(float(price))
                elif name.lower() == away.lower():
                    away_odds_list.append(float(price))

    def median(lst: List[float]) -> Optional[float]:
        if not lst:
            return None
        s = sorted(lst)
        return s[len(s) // 2]

    return median(home_odds_list), median(away_odds_list)


def compute_dr_from_odds(prob_a: float, surface_key: str) -> Tuple[float, float]:
    """
    Estimate Dominance Ratio (DR) from win probabilities.

    DR = return_win% / (1 - serve_win%)
    Since we only have moneyline, we approximate:
      - serve_win% ≈ 0.60 + 0.20*(prob - 0.5)   (stronger player wins more serves)
      - return_win% = prob_a - 0.40 * serve_win% (rough balance)
    Then apply court speed multiplier.
    """
    surface = SURFACE_MAP.get(surface_key, "Hard_Outdoor")
    speed = SURFACE_SPEED_MAP.get(surface, 1.0)

    prob_b = 1.0 - prob_a

    # Approximate serve efficiency from win probability
    serve_a = clamp(0.60 + 0.22 * (prob_a - 0.5), 0.50, 0.80)
    serve_b = clamp(0.60 + 0.22 * (prob_b - 0.5), 0.50, 0.80)

    # Return win% ≈ (1 - opponent serve win%)
    ret_a = 1.0 - serve_b
    ret_b = 1.0 - serve_a

    # DR = return% / (1 - serve%)
    denom_a = 1.0 - serve_a
    denom_b = 1.0 - serve_b

    dr_a = (ret_a / denom_a) * speed if denom_a > 0 else 1.0
    dr_b = (ret_b / denom_b) * speed if denom_b > 0 else 1.0

    return round(dr_a, 4), round(dr_b, 4)


def model_tennis_match(
    player_a: str,
    player_b: str,
    odds_a: Optional[float],
    odds_b: Optional[float],
    surface_key: str,
) -> Dict[str, Any]:
    """
    Run the tennis Dominance Ratio model for a single match.

    Returns a result dict with recommendation, confidence, and edge.
    """
    # --- Derive win probabilities ---
    if odds_a is not None and odds_b is not None:
        raw_prob_a = decimal_to_prob(odds_a)
        raw_prob_b = decimal_to_prob(odds_b)
        prob_a, prob_b = normalize_probs(raw_prob_a, raw_prob_b)
        odds_source = "live"
    else:
        # No odds available — use even probabilities
        prob_a, prob_b = 0.5, 0.5
        odds_source = "baseline"

    # --- Dominance Ratio ---
    dr_a, dr_b = compute_dr_from_odds(prob_a, surface_key)
    dr_diff = dr_a - dr_b

    # --- Confidence Engine ---
    # Scale: DR diff of 0.20 → ~80% confidence; 0.10 → ~65%
    conf = clamp(50.0 + abs(dr_diff) * 150.0, 50.0, 98.0)

    # --- Recommendation ---
    if dr_diff > 0.10:
        rec = f"PLAY {player_a}"
        lean_player = player_a
    elif dr_diff < -0.10:
        rec = f"PLAY {player_b}"
        lean_player = player_b
    else:
        rec = "PASS (too close)"
        lean_player = "PASS"

    surface = SURFACE_MAP.get(surface_key, "Hard_Outdoor")

    return {
        "player_a": player_a,
        "player_b": player_b,
        "odds_a": odds_a,
        "odds_b": odds_b,
        "prob_a": round(prob_a, 4),
        "prob_b": round(prob_b, 4),
        "dr_a": dr_a,
        "dr_b": dr_b,
        "dr_diff": round(dr_diff, 4),
        "surface": surface,
        "recommendation": rec,
        "lean_player": lean_player,
        "confidence": round(conf, 1),
        "edge": f"{dr_diff:+.3f} DR",
        "odds_source": odds_source,
    }


def format_commence(iso_str: str) -> str:
    """Format ISO datetime to a readable string in local-ish display."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d %H:%M UTC")
    except Exception:
        return iso_str[:16] if iso_str else "TBD"


# ---------------------------------------------------------------------------
# Scanner Core
# ---------------------------------------------------------------------------

def scan_tournaments(
    tours: List[str],
    client: TennisOddsClient,
    min_conf: float = 0.0,
) -> List[Dict[str, Any]]:
    """
    Iterate through tournament keys, fetch events + odds, and run the model.

    Returns list of result dicts, one per match.
    """
    all_results: List[Dict[str, Any]] = []
    active_tournaments: int = 0

    for sport_key in tours:
        label = TOURNAMENT_LABELS.get(sport_key, sport_key)

        if client.available:
            # Use the odds endpoint (includes event + odds in one call)
            raw_matches = client.fetch_odds(sport_key)
            if not raw_matches:
                # Fall back to events only (no odds)
                raw_events = client.fetch_events(sport_key)
                raw_matches = raw_events  # odds will be empty
        else:
            raw_matches = []

        if not raw_matches:
            continue  # tournament not active / no data

        active_tournaments += 1

        for match in raw_matches:
            player_a = match.get("home_team", "Player A")
            player_b = match.get("away_team", "Player B")
            commence = match.get("commence_time", "")
            match_id = match.get("id", "")

            odds_a, odds_b = extract_moneyline(match)

            result = model_tennis_match(
                player_a=player_a,
                player_b=player_b,
                odds_a=odds_a,
                odds_b=odds_b,
                surface_key=sport_key,
            )

            result.update({
                "tournament": label,
                "sport_key": sport_key,
                "match_id": match_id,
                "commence_time": commence,
                "commence_display": format_commence(commence),
            })

            if result["confidence"] >= min_conf:
                all_results.append(result)

    if client.available and not all_results and active_tournaments == 0:
        print("\n[INFO] No active tennis tournaments found at this time.")
        print("       This is normal between tournament dates.")

    return all_results


def _demo_results() -> List[Dict[str, Any]]:
    """Return demo data when no API key is set."""
    demo_matches = [
        ("Carlos Alcaraz",   "Holger Rune",    1.40, 3.10, "tennis_atp_queens_club_champ"),
        ("Jannik Sinner",    "Alex de Minaur", 1.55, 2.55, "tennis_atp_queens_club_champ"),
        ("Novak Djokovic",   "Taylor Fritz",   1.65, 2.30, "tennis_atp_halle_open"),
        ("Alexander Zverev", "Ben Shelton",    1.80, 2.10, "tennis_atp_halle_open"),
        ("Iga Swiatek",      "Aryna Sabalenka",1.62, 2.40, "tennis_wta_german_open"),
        ("Coco Gauff",       "Elena Rybakina", 1.85, 2.05, "tennis_wta_queens_club_champ"),
    ]

    results = []
    for player_a, player_b, odds_a, odds_b, sport_key in demo_matches:
        result = model_tennis_match(player_a, player_b, odds_a, odds_b, sport_key)
        result.update({
            "tournament": TOURNAMENT_LABELS.get(sport_key, sport_key),
            "sport_key": sport_key,
            "match_id": "demo",
            "commence_time": "2026-06-20T11:00:00Z",
            "commence_display": "Jun 20 11:00 UTC",
        })
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def _conf_style(conf: float) -> str:
    """Return a rich style string based on confidence level."""
    if conf >= 75:
        return "bold green"
    if conf >= 62:
        return "yellow"
    return "dim"


def _rec_style(rec: str) -> str:
    if "PASS" in rec:
        return "dim"
    return "bold cyan"


def display_results_rich(results: List[Dict[str, Any]], demo: bool = False) -> None:
    """Render results as a rich table."""
    title_suffix = " [DEMO MODE - set ODDS_API_KEY for live data]" if demo else ""
    title = f"Tennis Match Scanner{title_suffix}"
    
    table = Table(
        title=title,
        show_header=True,
        header_style="bold white on dark_blue",
        border_style="blue",
        row_styles=["", "dim"],
    )

    table.add_column("Tournament",    style="cyan",      no_wrap=True, min_width=20)
    table.add_column("Match",         style="white",     no_wrap=False, min_width=28)
    table.add_column("Time (UTC)",    style="white",     no_wrap=True,  min_width=14)
    table.add_column("Odds A / B",    style="white",     no_wrap=True,  min_width=12)
    table.add_column("Surface",       style="magenta",   no_wrap=True,  min_width=10)
    table.add_column("DR A / B",      style="white",     no_wrap=True,  min_width=12)
    table.add_column("Model Lean",    no_wrap=True,      min_width=22)
    table.add_column("Conf %",        no_wrap=True,      min_width=8)

    for r in results:
        odds_str = (
            f"{r['odds_a']:.2f} / {r['odds_b']:.2f}"
            if r["odds_a"] is not None else "N/A"
        )
        dr_str = f"{r['dr_a']:.3f} / {r['dr_b']:.3f}"
        conf_str = f"{r['confidence']:.1f}%"
        match_str = f"{r['player_a']} vs {r['player_b']}"

        table.add_row(
            r["tournament"],
            match_str,
            r["commence_display"],
            odds_str,
            r["surface"],
            dr_str,
            Text(r["recommendation"], style=_rec_style(r["recommendation"])),
            Text(conf_str, style=_conf_style(r["confidence"])),
        )

    console.print("\n")
    console.print(table)

    # Summary stats
    bets = [r for r in results if "PASS" not in r["recommendation"]]
    strong = [r for r in bets if r["confidence"] >= 75]

    console.print(
        f"\n[bold]Summary:[/bold] {len(results)} match(es) scanned | "
        f"[cyan]{len(bets)} model lean(s)[/cyan] | "
        f"[bold green]{len(strong)} strong bet(s) (>=75% conf)[/bold green]"
    )

    if demo:
        console.print(
            "\n[yellow]!! DEMO MODE:[/yellow] No ODDS_API_KEY found. "
            "Showing example matches with synthetic odds.\n"
            "  >> Get your free key at https://the-odds-api.com\n"
            "  >> Set it: [bold]set ODDS_API_KEY=your_key_here[/bold] (Windows) or "
            "[bold]export ODDS_API_KEY=your_key_here[/bold] (Mac/Linux)"
        )


def display_results_plain(results: List[Dict[str, Any]], demo: bool = False) -> None:
    """Plain-text fallback display."""
    sep = "=" * 90
    if demo:
        print(f"\n{'='*90}")
        print("  TENNIS MATCH SCANNER  [DEMO MODE — set ODDS_API_KEY for live data]")
        print(sep)
    else:
        print(f"\n{'='*90}")
        print("  TENNIS MATCH SCANNER")
        print(sep)

    header = f"{'Tournament':<22} {'Match':<30} {'Time':<16} {'Odds A/B':<12} {'DR A/B':<13} {'Lean':<22} {'Conf':>6}"
    print(header)
    print("-" * 90)

    for r in results:
        odds_str = (
            f"{r['odds_a']:.2f}/{r['odds_b']:.2f}"
            if r["odds_a"] is not None else "N/A   "
        )
        match_str = f"{r['player_a']} vs {r['player_b']}"[:30]
        dr_str = f"{r['dr_a']:.3f}/{r['dr_b']:.3f}"
        print(
            f"{r['tournament']:<22} {match_str:<30} {r['commence_display']:<16} "
            f"{odds_str:<12} {dr_str:<13} {r['recommendation']:<22} {r['confidence']:>5.1f}%"
        )

    bets = [r for r in results if "PASS" not in r["recommendation"]]
    strong = [r for r in bets if r["confidence"] >= 75]
    print(sep)
    print(f"Total: {len(results)} match(es) | {len(bets)} lean(s) | {len(strong)} strong bet(s) >=75% conf")


# ---------------------------------------------------------------------------
# Save to JSON
# ---------------------------------------------------------------------------

def save_results(results: List[Dict[str, Any]]) -> Path:
    out_dir = Path("output/tennis")
    out_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"scan_{date_str}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    return out_path


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Scan upcoming tennis matches and run the Dominance Ratio model."
    )
    parser.add_argument(
        "--tours", nargs="+", choices=["atp", "wta"], default=["atp", "wta"],
        help="Which tours to scan (default: both ATP and WTA)"
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Save scan results to output/tennis/scan_<timestamp>.json"
    )
    parser.add_argument(
        "--min-conf", type=float, default=0.0,
        help="Only show matches with model confidence >= this value (e.g. 65)"
    )
    parser.add_argument(
        "--api-key", type=str, default="",
        help="The Odds API key (overrides ODDS_API_KEY env var)"
    )
    args = parser.parse_args()

    # Build tournament list
    keys_to_scan: List[str] = []
    if "atp" in args.tours:
        keys_to_scan.extend(ATP_KEYS)
    if "wta" in args.tours:
        keys_to_scan.extend(WTA_KEYS)

    # Initialize client
    api_key = args.api_key or os.getenv("ODDS_API_KEY", "")
    client = TennisOddsClient(api_key=api_key)

    demo_mode = not client.available

    if demo_mode:
        results = _demo_results()
    else:
        print(f"[INFO] Scanning {len(keys_to_scan)} tournament keys for upcoming matches...")
        results = scan_tournaments(keys_to_scan, client, min_conf=args.min_conf)

        if not results:
            print("[INFO] No upcoming matches found. Try again closer to tournament dates.")
            print(f"[INFO] Scanned: {', '.join(keys_to_scan[:5])}{'...' if len(keys_to_scan) > 5 else ''}")
            sys.exit(0)

    # Apply min-conf filter even in demo mode
    if args.min_conf > 0:
        results = [r for r in results if r["confidence"] >= args.min_conf]

    # Display
    if _RICH:
        display_results_rich(results, demo=demo_mode)
    else:
        display_results_plain(results, demo=demo_mode)

    # Save
    if args.save:
        out_path = save_results(results)
        msg = f"\n[Saved] Results written to: {out_path}"
        if _RICH:
            console.print(f"[bold green]{msg}[/bold green]")
        else:
            print(msg)

    # Quota info
    if client.available and client._remaining_requests:
        msg = f"[Odds API] Requests remaining: {client._remaining_requests}"
        if _RICH:
            console.print(f"[dim]{msg}[/dim]")
        else:
            print(msg)


if __name__ == "__main__":
    main()
