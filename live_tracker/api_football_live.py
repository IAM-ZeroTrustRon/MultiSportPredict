"""
API-Football v3 Live Tracker
=============================
Real-time polling of the API-Football /v3/fixtures/statistics endpoint with
rolling-window delta calculations for live-match momentum analysis.

Key Features:
    - Configurable poll interval (default 60s — respects API rate limits)
    - Rolling 15-minute window for dangerous attacks, possession, shots, etc.
    - Discord push integration when momentum thresholds are crossed
    - CSV logging of all data points for post-match analysis
    - Graceful error handling and reconnection
"""

import csv
import logging
import os
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

import requests

# Ensure project root is on sys.path for cross-module imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import PROJECT_ROOT as CFG_ROOT, OUTPUT_DIR

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TRACKER CONFIGURATION  (can be overridden via env vars)
# ---------------------------------------------------------------------------
DEFAULT_API_BASE = "https://v3.football.api-sports.io"
DEFAULT_POLL_INTERVAL_SECS = 60
DEFAULT_ROLLING_WINDOW_MINS = 15

# Fields tracked from the statistics endpoint
TRACKED_STAT_TYPES = {
    "Ball Possession": "possession",
    "Dangerous Attacks": "dangerous_attacks",
    "Total Shots": "total_shots",
    "Shots on Goal": "shots_on_goal",
    "Shots off Goal": "shots_off_goal",
    "Corner Kicks": "corners",
    "Yellow Cards": "yellow_cards",
    "Red Cards": "red_cards",
}

# ---------------------------------------------------------------------------
# ROLLING STATS WINDOW
# ---------------------------------------------------------------------------

class RollingStatsWindow:
    """
    Tracks a time-series of cumulative stats and computes deltas over a
    configurable rolling window.

    Each data point is a tuple of: (timestamp, home_total, away_total)
    """

    def __init__(self, window_minutes: int = DEFAULT_ROLLING_WINDOW_MINS):
        self.window_seconds = window_minutes * 60
        self._history: Deque[Tuple[float, float, float]] = deque()

    def add_point(self, timestamp: float, home_total: float, away_total: float) -> None:
        """Append a new cumulative data point and purge expired entries."""
        self._history.append((timestamp, home_total, away_total))
        cutoff = timestamp - self.window_seconds
        while self._history and self._history[0][0] < cutoff:
            self._history.popleft()

    @property
    def count(self) -> int:
        return len(self._history)

    @property
    def window_seconds_actual(self) -> float:
        """Return the actual time span covered by stored points (0 if empty)."""
        if self.count < 2:
            return 0.0
        return self._history[-1][0] - self._history[0][0]

    def delta(self) -> Optional[Tuple[float, float]]:
        """
        Return (home_delta, away_delta) over the rolling window.

        Returns None if fewer than 2 data points have been collected.
        """
        if self.count < 2:
            return None
        oldest = self._history[0]
        newest = self._history[-1]
        return (newest[1] - oldest[1], newest[2] - oldest[2])

    def latest_total(self) -> Optional[Tuple[float, float]]:
        """Return the most recent (home_total, away_total) or None."""
        if not self._history:
            return None
        last = self._history[-1]
        return (last[1], last[2])

    def clear(self) -> None:
        self._history.clear()


# ---------------------------------------------------------------------------
# LIVE FOOTBALL TRACKER
# ---------------------------------------------------------------------------

class LiveFootballTracker:
    """
    Polls API-Football v3/fixtures/statistics in a loop, maintains rolling
    windows for multiple stat types, and triggers Discord alerts when
    momentum thresholds are exceeded.
    """

    def __init__(
        self,
        fixture_id: str,
        api_key: Optional[str] = None,
        api_base: str = DEFAULT_API_BASE,
        poll_interval: int = DEFAULT_POLL_INTERVAL_SECS,
        rolling_window_mins: int = DEFAULT_ROLLING_WINDOW_MINS,
        alert_thresholds: Optional[Dict[str, Tuple[float, str]]] = None,
        log_csv: bool = True,
    ):
        """
        Args:
            fixture_id: The API-Football fixture ID to track.
            api_key: API-Football key. Falls back to API_FOOTBALL_KEY env var.
            api_base: Base URL for the API (default: v3).
            poll_interval: Seconds between API calls.
            rolling_window_mins: Rolling window length in minutes.
            alert_thresholds: Dict mapping stat name -> (threshold, message).
                              Defaults to dangerous_attacks > 12 = pressure alert.
            log_csv: If True, write all data points to a CSV in output/.
        """
        self.fixture_id = fixture_id
        self.api_key = api_key or os.getenv("API_FOOTBALL_KEY", "")
        if not self.api_key:
            raise ValueError(
                "API-Football key is required. Set API_FOOTBALL_KEY in .env "
                "or pass api_key to the constructor."
            )

        self.api_base = api_base.rstrip("/")
        self.poll_interval = poll_interval
        self.rolling_window_mins = rolling_window_mins
        self.log_csv = log_csv

        # Default threshold for dangerous attacks
        self.alert_thresholds = alert_thresholds or {
            "dangerous_attacks": (12, ">> 🔥 MODEL ALERT: {} team applying massive pressure. High probability of a corner/shot."),
        }

        # Rolling windows keyed by stat name (e.g. "dangerous_attacks")
        self.windows: Dict[str, RollingStatsWindow] = {}

        # Most recently parsed stats (for reference)
        self.current_stats: Dict[str, Dict[str, Any]] = {}

        # CSV writer handle
        self._csv_file: Optional[Path] = None
        self._csv_writer: Optional[csv.DictWriter] = None

        # Request session (reused for connection pooling)
        self._session = requests.Session()
        self._session.headers.update({
            "x-apisports-key": self.api_key,
            "Accept": "application/json",
        })

        # Runtime state
        self._running = False

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Begin the polling loop. Runs indefinitely until interrupted
        (KeyboardInterrupt) or self.stop() is called from another thread.
        """
        self._running = True
        fixture_label = self.fixture_id
        logger.info(
            "[%s] Starting live tracker for fixture %s (poll=%ss, window=%dm)",
            datetime.now().strftime("%H:%M:%S"),
            fixture_label,
            self.poll_interval,
            self.rolling_window_mins,
        )
        print(f"\n{'='*60}")
        print(f"  LIVE TRACKER — Fixture {fixture_label}")
        print(f"  Poll Interval : {self.poll_interval}s")
        print(f"  Rolling Window: {self.rolling_window_mins} min")
        print(f"{'='*60}\n")

        try:
            while self._running:
                self._poll()
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            logger.info("Live tracker stopped by user.")
            print("\n🛑 Tracker stopped by user.")
        finally:
            self._cleanup()

    def stop(self) -> None:
        """Signal the polling loop to exit gracefully."""
        self._running = False

    def force_poll(self) -> Dict[str, Any]:
        """
        Perform a single poll cycle (non-blocking). Useful for testing
        or one-shot analysis.
        """
        return self._poll()

    # ------------------------------------------------------------------
    # INTERNAL
    # ------------------------------------------------------------------

    def _poll(self) -> Dict[str, Any]:
        """Execute one API poll cycle. Returns the parsed stats dict."""
        url = f"{self.api_base}/fixtures/statistics?fixture={self.fixture_id}"
        try:
            resp = self._session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as exc:
            logger.error("API request failed: %s", exc)
            print(f"  ⚠ API error: {exc}")
            return {}

        parsed = self._parse_response(data)
        if not parsed:
            print(f"  [{datetime.now().strftime('%H:%M:%S')}] Waiting for match statistics...")
            return {}

        self.current_stats = parsed
        self._update_windows(parsed)
        self._log_to_csv(parsed)
        self._print_report(parsed)
        self._check_alerts(parsed)

        return parsed

    def _parse_response(self, api_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract tracked stats from the API-Football v3/fixtures/statistics
        response format.

        Returns a dict like:
            {
                "home": {"possession": 55, "dangerous_attacks": 42, ...},
                "away": {"possession": 45, "dangerous_attacks": 38, ...},
            }
        """
        teams = api_response.get("response", [])
        if not teams or len(teams) < 2:
            return {}

        result: Dict[str, Dict[str, Any]] = {"home": {}, "away": {}}

        for idx, team_data in enumerate(teams):
            side = "home" if idx == 0 else "away"
            for stat_entry in team_data.get("statistics", []):
                stat_type = stat_entry.get("type", "")
                mapped = TRACKED_STAT_TYPES.get(stat_type)
                if mapped is None:
                    continue

                raw_val = stat_entry.get("value")
                if mapped == "possession" and raw_val is not None:
                    # "55%" -> int(55)
                    parsed_val = int(str(raw_val).strip("%"))
                else:
                    try:
                        parsed_val = int(raw_val) if raw_val is not None else 0
                    except (ValueError, TypeError):
                        parsed_val = 0

                result[side][mapped] = parsed_val

        return result

    def _update_windows(self, stats: Dict[str, Dict[str, Any]]) -> None:
        """Update every rolling window with the latest cumulative values."""
        now = time.time()
        for stat_name in TRACKED_STAT_TYPES.values():
            home_val = stats.get("home", {}).get(stat_name, 0)
            away_val = stats.get("away", {}).get(stat_name, 0)

            if stat_name not in self.windows:
                self.windows[stat_name] = RollingStatsWindow(self.rolling_window_mins)

            self.windows[stat_name].add_point(now, float(home_val), float(away_val))

    def _print_report(self, stats: Dict[str, Dict[str, Any]]) -> None:
        """Print a formatted console report of current stats and deltas."""
        ts = datetime.now().strftime("%H:%M:%S")
        home_poss = stats.get("home", {}).get("possession", "?")
        away_poss = stats.get("away", {}).get("possession", "?")
        print(f"\n--- Live Match Feed ({ts}) ---")
        print(f"  Possession: Home {home_poss}% | Away {away_poss}%")

        for stat_name in ["dangerous_attacks", "total_shots", "shots_on_goal", "corners"]:
            h_now = stats.get("home", {}).get(stat_name, 0)
            a_now = stats.get("away", {}).get(stat_name, 0)

            win = self.windows.get(stat_name)
            delta_str = ""
            if win and win.count >= 2:
                d = win.delta()
                if d:
                    delta_str = f" (last {self.rolling_window_mins}m: +{d[0]:.0f} / +{d[1]:.0f})"

            label = stat_name.replace("_", " ").title()
            print(f"  {label}: Home {h_now} | Away {a_now}{delta_str}")

    def _check_alerts(self, stats: Dict[str, Dict[str, Any]]) -> None:
        """Evaluate alert thresholds and push to Discord if triggered."""
        for stat_name, (threshold, message_template) in self.alert_thresholds.items():
            win = self.windows.get(stat_name)
            if not win or win.count < 2:
                continue
            delta = win.delta()
            if not delta:
                continue

            home_delta, away_delta = delta
            triggered = []

            if home_delta >= threshold:
                triggered.append(("Home", home_delta))
            if away_delta >= threshold:
                triggered.append(("Away", away_delta))

            for side, value in triggered:
                alert_msg = message_template.format(side)
                print(f"  >> {alert_msg} ({value:.0f} in {self.rolling_window_mins}m)")

                # Push to Discord via universal_runner
                home_name = os.getenv("HOME_TEAM", f"Fixture {self.fixture_id}")
                away_name = os.getenv("AWAY_TEAM", "Opponent")

                try:
                    from universal_runner import push_to_discord
                    push_to_discord(
                        sport="soccer",
                        home=home_name,
                        away=away_name,
                        recommendation="STRONG BET",
                        confidence=min(85.0, 65.0 + value * 1.5),
                        edge=f"+{value:.0f} {stat_name.replace('_', ' ')} in {self.rolling_window_mins}m",
                        extra_metrics=f"{side} {stat_name.replace('_', ' ').title()}: {value:.0f} (rolling {self.rolling_window_mins}m)",
                    )
                except ImportError:
                    logger.debug("universal_runner not available; alert printed to console only.")

    def _log_to_csv(self, stats: Dict[str, Dict[str, Any]]) -> None:
        """Append the current data point to a CSV log file."""
        if not self.log_csv:
            return

        if self._csv_writer is None:
            log_dir = OUTPUT_DIR / "live_tracker"
            log_dir.mkdir(parents=True, exist_ok=True)
            self._csv_file = log_dir / f"fixture_{self.fixture_id}.csv"
            fieldnames = [
                "timestamp",
                "fixture_id",
                "home_possession",
                "away_possession",
                "home_dangerous_attacks",
                "away_dangerous_attacks",
                "home_total_shots",
                "away_total_shots",
                "home_shots_on_goal",
                "away_shots_on_goal",
                "home_corners",
                "away_corners",
                "home_yellow_cards",
                "away_yellow_cards",
                "home_red_cards",
                "away_red_cards",
            ]
            file_exists = self._csv_file.exists()
            self._csv_file_handle = open(self._csv_file, "a", newline="")
            self._csv_writer = csv.DictWriter(self._csv_file_handle, fieldnames=fieldnames)
            if not file_exists:
                self._csv_writer.writeheader()

        row = {
            "timestamp": datetime.utcnow().isoformat(),
            "fixture_id": self.fixture_id,
        }
        for side in ("home", "away"):
            for stat_name in TRACKED_STAT_TYPES.values():
                val = stats.get(side, {}).get(stat_name, "")
                row[f"{side}_{stat_name}"] = val

        self._csv_writer.writerow(row)
        self._csv_file_handle.flush()

    def _cleanup(self) -> None:
        """Close file handles and sessions."""
        if hasattr(self, "_csv_file_handle"):
            self._csv_file_handle.close()
        self._session.close()
        logger.info("Live tracker cleaned up.")