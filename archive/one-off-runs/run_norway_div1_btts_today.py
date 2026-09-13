#!/usr/bin/env python
"""
Norway Division 1 (Today) - Best BTTS Recommendations

This repo does not include an automatic fixture fetcher for Norway Division 1.
So this scanner is fixture-driven: you provide a fixtures file for "today".

Fixtures input (CSV or JSON) must include at minimum:
  - home_team
  - away_team

Optional columns:
  - league (defaults to soccer_norway_div1)
  - date (string echoed to output)
  - market_total (defaults to 2.5; passed to SoccerPredictor for edge context)
  - market_line (defaults to 0.0; passed to SoccerPredictor for side context)

Output:
  - Prints top picks ranked by projected BTTS probability.
  - Saves full ranked results to output/norway_div1_btts_today_<timestamp>.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from models.soccer_predictor import SoccerPredictor


def _read_fixtures(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Fixtures file not found: {path}")

    if p.suffix.lower() == ".csv":
        return pd.read_csv(p)

    if p.suffix.lower() == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return pd.DataFrame(data)
        if isinstance(data, dict) and "matches" in data:
            return pd.DataFrame(data["matches"])
        raise ValueError("Unsupported JSON fixtures format. Expected list or {matches:[...]}")

    raise ValueError("Unsupported fixtures file type. Use .csv or .json")


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize common column aliases to the internal names:
      home_team, away_team, league, date, market_total, market_line
    """
    col_map: Dict[str, str] = {}
    for c in df.columns:
        lc = str(c).strip().lower()
        if lc in {"home", "home_team", "home team"}:
            col_map[c] = "home_team"
        elif lc in {"away", "away_team", "away team"}:
            col_map[c] = "away_team"
        elif lc in {"league", "competition"}:
            col_map[c] = "league"
        elif lc in {"date", "match_date"}:
            col_map[c] = "date"
        elif lc in {"market_total", "market total", "btts_market_total", "total_line"}:
            col_map[c] = "market_total"
        elif lc in {"market_line", "handicap_line", "asian_handicap"}:
            col_map[c] = "market_line"

    return df.rename(columns=col_map)


def scan_best_btts(
    fixtures_path: str,
    *,
    top_n: int = 5,
    default_league: str = "soccer_norway_div1",
) -> List[Dict[str, Any]]:
    df = _read_fixtures(fixtures_path)
    df = _normalize_columns(df)

    required = {"home_team", "away_team"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Fixtures missing required columns: {sorted(missing)}")

    if "league" not in df.columns:
        df["league"] = default_league
    else:
        df["league"] = df["league"].fillna(default_league)

    if "market_total" not in df.columns:
        df["market_total"] = 2.5
    if "market_line" not in df.columns:
        df["market_line"] = 0.0

    results: List[Dict[str, Any]] = []

    predictors: Dict[str, SoccerPredictor] = {}
    for _, row in df.iterrows():
        home = str(row["home_team"])
        away = str(row["away_team"])
        league = str(row.get("league", default_league))
        market_total = float(row.get("market_total", 2.5))
        market_line = float(row.get("market_line", 0.0))
        match_date = row.get("date", None)
        match_date_str = str(match_date) if match_date is not None and str(match_date) != "nan" else None

        if league not in predictors:
            predictors[league] = SoccerPredictor(league=league)
        predictor = predictors[league]

        # If your fixtures file contains enriched xG/shot metrics columns, this script will
        # forward them; otherwise SoccerPredictor will use internal defaults.
        enriched_keys = [
            "home_xg_for", "home_xg_against", "home_shots", "home_sot",
            "home_goals_for", "home_goals_against", "home_clean_sheets",
            "home_missing_attacker", "home_missing_creator", "home_missing_cb", "home_missing_gk",
            "home_tempo", "home_width_crossing", "home_final_third_pressure",
            "away_xg_for", "away_xg_against", "away_shots", "away_sot",
            "away_goals_for", "away_goals_against", "away_clean_sheets",
            "away_missing_attacker", "away_missing_creator", "away_missing_cb", "away_missing_gk",
            "away_tempo", "away_width_crossing", "away_final_third_pressure",
        ]

        kwargs: Dict[str, Any] = dict(
            features=pd.DataFrame(),
            model=None,
            home_team=home,
            away_team=away,
            market_line=market_line,
            market_total=market_total,
            league=league,
        )

        for k in enriched_keys:
            if k in df.columns:
                v = row.get(k, None)
                if v is not None and str(v) != "nan":
                    kwargs[k] = v

        soccer_result = predictor.predict(**kwargs)

        btts_prob = float(soccer_result.get("btts_probability", 0.0))
        btts_rec = soccer_result.get("predictions", {}).get("btts", {}).get("recommendation", "PASS")
        btts_conf = soccer_result.get("predictions", {}).get("btts", {}).get("confidence", None)

        results.append(
            {
                "home_team": home,
                "away_team": away,
                "league": league,
                "date": match_date_str,
                "market_total": market_total,
                "market_line": market_line,
                "projected_btts_probability": round(btts_prob, 3),
                "btts_recommendation": btts_rec,
                "btts_confidence": btts_conf,
                "projected_total_goals": soccer_result.get("game", {}).get("projected_total_goals", None),
                "home_win_prob": soccer_result.get("game", {}).get("home_win_prob", None),
                "draw_prob": soccer_result.get("game", {}).get("draw_prob", None),
                "away_win_prob": soccer_result.get("game", {}).get("away_win_prob", None),
            }
        )

    results.sort(key=lambda x: x["projected_btts_probability"], reverse=True)
    return results[:top_n]


def main() -> None:
    parser = argparse.ArgumentParser(description="Norway Division 1 (Today) BTTS Scanner")
    parser.add_argument("--fixtures", required=True, help="Fixtures CSV/JSON path")
    parser.add_argument("--top", type=int, default=5, help="Top N picks to print/save")
    parser.add_argument("--default-league", default="soccer_norway_div1", help="League key used for predictions")
    args = parser.parse_args()

    top_results = scan_best_btts(
        args.fixtures,
        top_n=args.top,
        default_league=args.default_league,
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("output")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"norway_div1_btts_today_{ts}.json"
    out_path.write_text(json.dumps({"generated_at": ts, "top_results": top_results}, indent=2), encoding="utf-8")

    print("\n=== TOP BTTS RECOMMENDATIONS (Norway Division 1) ===")
    for i, r in enumerate(top_results, start=1):
        prob_pct = float(r["projected_btts_probability"]) * 100.0
        print(f"{i}. {r['home_team']} vs {r['away_team']} | BTTS {prob_pct:.1f}% | {r['btts_recommendation']}")

    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
