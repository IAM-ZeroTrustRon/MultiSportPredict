#!/usr/bin/env python
"""
Live Football Match Tracker — API-Football v3
=============================================
Real-time polling of live match statistics with rolling-window delta
calculations for momentum analysis and Discord alerts.

Usage:
    # Basic usage (prompts for fixture ID):
    python run_live_football_tracker.py

    # With fixture ID and team names (for Discord alerts):
    python run_live_football_tracker.py --fixture 1036321 --home "Barcelona" --away "Valencia"

    # Custom poll interval and rolling window:
    python run_live_football_tracker.py --fixture 1036321 --poll 30 --window 10

    # One-shot mode (single poll, no loop):
    python run_live_football_tracker.py --fixture 1036321 --oneshot

    # List fixtures from command line (interactive mode):
    python run_live_football_tracker.py --interactive

Integration Example (in another script):
    from live_tracker import LiveFootballTracker

    tracker = LiveFootballTracker(
        fixture_id="1036321",
        poll_interval=60,
        rolling_window_mins=15,
    )
    tracker.start()
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load .env before any imports that read env vars
load_dotenv()

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    API_FOOTBALL_BASE_URL,
    API_FOOTBALL_DEFAULT_POLL_INTERVAL_SECS,
    API_FOOTBALL_DEFAULT_ROLLING_WINDOW_MINS,
)
from live_tracker import LiveFootballTracker

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_live_football_tracker")


# ---------------------------------------------------------------------------
# ARGUMENT PARSER
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Live football match tracker using API-Football v3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_live_football_tracker.py --fixture 1036321
  python run_live_football_tracker.py --fixture 1036321 --poll 30 --window 10 --oneshot
  python run_live_football_tracker.py --fixture 1036321 --home "FC Barcelona" --away "Valencia CF"
        """,
    )

    parser.add_argument(
        "--fixture",
        type=str,
        default=None,
        help="API-Football fixture ID to track. If omitted, you'll be prompted.",
    )
    parser.add_argument(
        "--home",
        type=str,
        default=None,
        help="Home team name (used for Discord alerts). Falls back to HOME_TEAM env var.",
    )
    parser.add_argument(
        "--away",
        type=str,
        default=None,
        help="Away team name (used for Discord alerts). Falls back to AWAY_TEAM env var.",
    )
    parser.add_argument(
        "--poll",
        type=int,
        default=API_FOOTBALL_DEFAULT_POLL_INTERVAL_SECS,
        help=f"Poll interval in seconds (default: {API_FOOTBALL_DEFAULT_POLL_INTERVAL_SECS})",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=API_FOOTBALL_DEFAULT_ROLLING_WINDOW_MINS,
        help=f"Rolling window in minutes (default: {API_FOOTBALL_DEFAULT_ROLLING_WINDOW_MINS})",
    )
    parser.add_argument(
        "--oneshot",
        action="store_true",
        help="Execute a single poll cycle and exit (no continuous loop).",
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="Disable CSV logging of data points.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive mode: prompts for fixture ID and team names.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=12.0,
        help="Dangerous attacks threshold for model alerts (default: 12).",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Override API key. Defaults to API_FOOTBALL_KEY env var.",
    )

    return parser


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    parser = build_parser()
    args = parser.parse_args()

    # ── Interactive mode ──────────────────────────────────────────────────
    if args.interactive:
        print("\n=== LIVE FOOTBALL TRACKER — Interactive Setup ===\n")
        fixture_id = input("Enter API-Football Fixture ID: ").strip()
        home_team = input("Enter Home Team Name (or leave blank): ").strip() or None
        away_team = input("Enter Away Team Name (or leave blank): ").strip() or None
        poll_secs = input(f"Poll Interval in seconds [{args.poll}]: ").strip()
        window_mins = input(f"Rolling Window in minutes [{args.window}]: ").strip()

        args.fixture = fixture_id
        args.home = home_team or args.home
        args.away = away_team or args.away
        if poll_secs:
            args.poll = int(poll_secs)
        if window_mins:
            args.window = int(window_mins)

    # ── Validate fixture ID ───────────────────────────────────────────────
    if not args.fixture:
        args.fixture = input("Enter API-Football Fixture ID: ").strip()
        if not args.fixture:
            print("❌ No fixture ID provided. Exiting.")
            sys.exit(1)

    # ── Set team names as env vars for Discord integration ────────────────
    if args.home:
        os.environ["HOME_TEAM"] = args.home
    if args.away:
        os.environ["AWAY_TEAM"] = args.away

    # Print configured team names
    home_display = os.environ.get("HOME_TEAM", "(not set)")
    away_display = os.environ.get("AWAY_TEAM", "(not set)")

    # ── Custom alert thresholds ────────────────────────────────────────────
    custom_thresholds = {
        "dangerous_attacks": (
            args.threshold,
            ">> 🔥 MODEL ALERT: {} team applying massive pressure. "
            "High probability of a corner/shot.",
        ),
    }

    # ── Build tracker ─────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  🏃 LIVE TRACKER STARTING")
    print(f"  Fixture ID     : {args.fixture}")
    print(f"  Home Team      : {home_display}")
    print(f"  Away Team      : {away_display}")
    print(f"  Poll Interval  : {args.poll}s")
    print(f"  Rolling Window : {args.window} min")
    print(f"  Alert Threshold: {args.threshold} dangerous attacks")
    print(f"  CSV Logging    : {'OFF' if args.no_csv else 'ON'}")
    print(f"{'='*60}\n")

    tracker = LiveFootballTracker(
        fixture_id=args.fixture,
        api_key=args.api_key,
        api_base=API_FOOTBALL_BASE_URL,
        poll_interval=args.poll,
        rolling_window_mins=args.window,
        alert_thresholds=custom_thresholds,
        log_csv=not args.no_csv,
    )

    # ── Oneshot vs Continuous ─────────────────────────────────────────────
    if args.oneshot:
        print("  [One-shot mode] Performing a single poll cycle...\n")
        result = tracker.force_poll()
        if result:
            home_poss = result.get("home", {}).get("possession", "?")
            away_poss = result.get("away", {}).get("possession", "?")
            home_da = result.get("home", {}).get("dangerous_attacks", "?")
            away_da = result.get("away", {}).get("dangerous_attacks", "?")
            print(f"\n  ✅ Poll complete.")
            print(f"  Possession:        {home_poss}% / {away_poss}%")
            print(f"  Dangerous Attacks: {home_da} / {away_da}")
        else:
            print("\n  ⚠️  No statistics available yet (match may not be live).")
    else:
        try:
            tracker.start()
        except KeyboardInterrupt:
            print("\n  🛑 Tracker stopped by user.")
        except Exception as exc:
            logger.error("Fatal error: %s", exc)
            print(f"\n  ❌ Fatal error: {exc}")
            sys.exit(1)

    print("\n  👋 Goodbye.\n")


if __name__ == "__main__":
    main()