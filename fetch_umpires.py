from __future__ import annotations

from typing import Dict


def fetch_daily_umpires() -> Dict[str, str]:
    """
    Fetches daily umpire assignments.

    This repo currently doesn't include a working umpire provider integration.
    For now, returns an empty mapping so callers can gracefully fall back
    to "Unknown".

    Production approach:
      - Load from CSV/API and return mapping:
          "{away_team} @ {home_team}" -> "Home Plate Umpire Name"
    """
    return {}
