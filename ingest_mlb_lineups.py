#!/usr/bin/env python
"""Fetch today's official MLB batting orders into the model's lineup store."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ingest_all_sports import ROOT, ingest_mlb_lineups

LINEUPS_FILE = ROOT / "data" / "mlb_lineups.json"


def fetch_and_save_lineups(target_date: str | None = None) -> Path:
    result = ingest_mlb_lineups(target_date=target_date)
    print(result.detail or f"Saved {result.count} team lineup(s).")
    return LINEUPS_FILE


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="Fetch lineups for an ISO date (YYYY-MM-DD).")
    args = parser.parse_args()
    try:
        fetch_and_save_lineups(args.date)
    except Exception as exc:  # noqa: BLE001
        print(f"[mlb-lineups] failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())