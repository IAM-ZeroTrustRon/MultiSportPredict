#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Barcelona vs Valencia (ACB) — 2026-06-24 analysis runner.

Generates a model projection using the repo's existing analysis engine
(run_barca_valencia_analysis.py) and writes a JSON summary to output/basketball.

This script is intentionally lightweight so Discord pushers can reuse
its output.
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

import run_barca_valencia_analysis as analysis


def main() -> dict:
    result = analysis.run_analysis()

    # Patch metadata to match the requested matchup/date/location
    result["game_context"] = {
        "date_local": "2026-06-24 14:00 ET",
        "league": "Spanish ACB",
        "venue": "Palau Blaugrana",
        "location": "Barcelona, Spain",
    }

    # Ensure deterministic output naming for the Discord pusher
    out_dir = Path("output/basketball")
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / "barcelona_vs_valencia_2026_06_24.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[Saved] {out_path}")
    return result


if __name__ == "__main__":
    main()

