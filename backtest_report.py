#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backtest_report.py — Calibration, Accuracy & ROI Report
=========================================================
Reads settled predictions from core.historical_storage (the canonical SQLite
store) and answers the questions that actually matter for a betting model:

  1. CALIBRATION: When the model says 63%, does it win ~63% of the time?
     (Brier score, log loss, reliability table by probability bucket)
  2. DISCRIMINATION: Does the model separate winners from losers at all?
     (AUC-style hit rate by confidence tier)
  3. ROI: Would following the model's recommendations have made money,
     using the actual odds taken (not just raw win %)?
  4. CLV: Did the line move in the direction the model expected between
     open and close? (A model with no real edge should be ~50/50 here
     even if its win rate looks OK over a small sample.)

DATA-SOURCE NOTE: historical_storage.py's schema is generic across market
types (a single `model_value`/`market_value` pair, not a raw 0-1 probability).
Brier score and log-loss therefore only apply cleanly to rows where
`market_type` is a moneyline-style market — i.e. `model_value` is literally
a 0-1 probability. For other market types those two numbers should be
ignored (the CLI warns when a dataset isn't probability-valued).

Usage:
    python backtest_report.py --db multisport_history.db
    python backtest_report.py --db multisport_history.db --sport soccer
    python backtest_report.py --db multisport_history.db --min-n 30
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Dict, Optional

import pandas as pd

from core.historical_storage import get_predictions


# ============================================================================
# METRICS
# ============================================================================

def _is_probability_valued(df: pd.DataFrame) -> bool:
    """True if model_value is a 0-1 probability for the rows in df.

    Brier/log-loss only make sense when model_value is literally a
    predicted probability. For spread/total rows model_value is a points
    projection (e.g. 4.76 goals) and those metrics are meaningless.
    """
    if df.empty:
        return True
    vals = df["model_value"].dropna()
    if vals.empty:
        return False
    return bool((vals.between(0.0, 1.0)).all())


def brier_score(df: pd.DataFrame) -> float:
    """Mean squared error between predicted probability and actual outcome (0/1).
    Lower is better. 0.25 is what you'd get from a constant 50% guess on a
    50/50 population — you want to beat that, not just be 'accurate-sounding'.
    """
    return float(((df["model_prob"] - df["actual"]) ** 2).mean())


def log_loss(df: pd.DataFrame, eps: float = 1e-6) -> float:
    """Lower is better. Heavily penalizes confident-and-wrong predictions,
    which raw accuracy hides."""
    p = df["model_prob"].clip(eps, 1 - eps)
    y = df["actual"]
    return float(-(y * p.apply(math.log) + (1 - y) * (1 - p).apply(math.log)).mean())


def reliability_table(df: pd.DataFrame, n_bins: int = 5) -> pd.DataFrame:
    """Buckets predictions by stated probability and compares to actual hit
    rate in that bucket. A well-calibrated model has predicted ≈ actual in
    every row. Systematic gaps here tell you exactly where the hand-tuned
    weights are over- or under-confident.
    """
    d = df.copy()
    d["bucket"] = pd.cut(d["model_prob"], bins=n_bins, include_lowest=True)
    grouped = d.groupby("bucket", observed=True).agg(
        n=("actual", "size"),
        predicted_avg=("model_prob", "mean"),
        actual_rate=("actual", "mean"),
    ).reset_index()
    grouped["gap"] = grouped["actual_rate"] - grouped["predicted_avg"]
    return grouped


def roi_report(df: pd.DataFrame, flat_stake: float = 100.0) -> pd.DataFrame:
    """Profit/loss assuming a flat stake per bet at the odds actually taken.
    Rows without raw_json odds data are excluded (can't compute payout).
    """
    # Pull odds_american out of raw_json if present (historical_storage keeps
    # the full prediction dict in raw_json, not a dedicated odds column).
    def extract_odds(row):
        raw = row.get("raw_json_parsed")
        if isinstance(raw, dict):
            ml = raw.get("moneyline") or {}
            odds = ml.get("market_home_odds") or ml.get("odds_american")
            if odds:
                try:
                    return int(str(odds).replace("+", "").replace("−", "-"))
                except ValueError:
                    return None
        return None

    d = df.copy()
    d["odds_american"] = d.apply(extract_odds, axis=1)
    d = d.dropna(subset=["odds_american"]).copy()
    if d.empty:
        return pd.DataFrame()

    def payout(row):
        odds = row["odds_american"]
        if row["actual"] == 0:
            return -flat_stake
        # American odds -> profit on a win
        if odds > 0:
            return flat_stake * (odds / 100.0)
        else:
            return flat_stake * (100.0 / abs(odds))

    d["pnl"] = d.apply(payout, axis=1)
    by_rec = d.groupby("recommendation", dropna=False).agg(
        n=("pnl", "size"),
        total_staked=("pnl", lambda s: flat_stake * len(s)),
        pnl=("pnl", "sum"),
    ).reset_index()
    by_rec["roi_pct"] = (by_rec["pnl"] / by_rec["total_staked"] * 100).round(2)
    return by_rec.sort_values("pnl", ascending=False)


def clv_report(df: pd.DataFrame) -> Optional[Dict[str, float]]:
    """
    Closing Line Value: of the predictions where we have both an opening
    and closing line, how often did the line move in the direction the
    model's edge implied? This is a sample-size-independent sanity check —
    real edge should show up here even before enough bets have settled to
    trust the win-rate number.
    """
    def extract_lines(row):
        raw = row.get("raw_json_parsed")
        if isinstance(raw, dict):
            opening = raw.get("opening_line") or raw.get("open_line")
            closing = raw.get("closing_line") or raw.get("current_line")
            if opening is not None and closing is not None:
                try:
                    return float(opening), float(closing)
                except (TypeError, ValueError):
                    return None, None
        return None, None

    d = df.copy()
    lines = d.apply(lambda r: extract_lines(r), axis=1)
    d["opening_line"] = [x[0] for x in lines]
    d["closing_line"] = [x[1] for x in lines]
    d = d.dropna(subset=["opening_line", "closing_line"]).copy()
    if d.empty:
        return None

    # model_value > 0.5 implies the model favors the side (moneyline context);
    # a line move that makes that side more attractive at close is "agreement".
    # This is intentionally simple: positive line movement in the model's
    # favored direction counts as a hit.
    d["line_move"] = d["closing_line"] - d["opening_line"]
    d["model_favored_more_negative"] = d["model_value"] > 0.5
    d["agree"] = (
        ((d["model_favored_more_negative"]) & (d["line_move"] <= 0))
        | ((~d["model_favored_more_negative"]) & (d["line_move"] >= 0))
    )
    return {
        "n": int(len(d)),
        "agreement_rate": round(float(d["agree"].mean()), 3),
    }


# ============================================================================
# REPORT ASSEMBLY
# ============================================================================

def build_report(db_path: str, sport: Optional[str], market_type: Optional[str], min_n: int) -> None:
    df = get_predictions(sport=sport, market_type=market_type, db_path=db_path)

    if df.empty:
        print("No predictions found in core.historical_storage. Nothing to report yet.")
        print("(Log predictions via universal_runner.py --store-to-db, then settle")
        print("outcomes via core.historical_storage.update_prediction_outcome().)")
        return

    # 'result_outcome' is the settled result column in historical_storage
    # ('win'/'loss'/'push'); rows with NULL are unsettled.
    settled = df["result_outcome"].notna()
    if not settled.any():
        print("No SETTLED predictions found in core.historical_storage.")
        print("(Rows exist but none have result_outcome set yet. Use")
        print("core.historical_storage.update_prediction_outcome() once results are known.)")
        return

    df = df[settled].copy()
    df = df[df["result_outcome"].isin(["win", "loss"])].copy()
    df["actual"] = (df["result_outcome"] == "win").astype(int)

    n = len(df)
    print("=" * 78)
    print("BACKTEST / CALIBRATION REPORT")
    print("=" * 78)
    print(f"Settled predictions analyzed: {n}")
    if sport:
        print(f"Sport filter: {sport}")
    if market_type:
        print(f"Market filter: {market_type}")

    if n < min_n:
        print(f"\n[WARNING] Only {n} settled predictions — below --min-n={min_n}.")
        print("Metrics below are NOT reliable at this sample size. Treat as directional")
        print("only. Brier score and log loss especially need volume to mean anything.")

    # For Brier/log-loss, only rows where model_value is a 0-1 probability
    # (moneyline-style markets) are meaningful — see module docstring.
    prob_df = df[_is_probability_valued(df)]
    if prob_df.empty:
        print("\n[NOTE] No moneyline-style rows (model_value is a 0-1 probability) found.")
        print("Brier score / log-loss are SKIPPED because historical_storage's generic")
        print("schema doesn't cleanly support them for spread/total market types.")
    else:
        if len(prob_df) < len(df):
            print(f"\n[NOTE] Brier/log-loss computed on {len(prob_df)} moneyline-style rows only")
            print("(spread/total rows are excluded — their model_value isn't a probability).")
        prob_df = prob_df.copy()
        prob_df["model_prob"] = prob_df["model_value"]
        print(f"\nBrier score : {brier_score(prob_df):.4f}  (lower is better; 0.25 = naive 50/50 baseline)")
        print(f"Log loss    : {log_loss(prob_df):.4f}  (lower is better)")
    print(f"Raw hit rate: {df['actual'].mean() * 100:.1f}%")

    # Reliability table (probability-valued rows only)
    print("\n" + "-" * 78)
    print("RELIABILITY TABLE (predicted probability vs. actual outcome rate)")
    print("-" * 78)
    if not prob_df.empty:
        n_bins = min(5, max(2, len(prob_df) // 10)) if len(prob_df) >= 20 else 2
        rel = reliability_table(prob_df, n_bins=n_bins)
        print(rel.to_string(index=False))
        print("\nRead this as: 'gap' > 0 means the model is UNDER-confident in that")
        print("bucket (wins more than it claims); 'gap' < 0 means OVER-confident.")
        print("Large systematic gaps = the sigmoid centering / weight scaling needs")
        print("refitting, not just the individual feature weights.")
    else:
        print("No probability-valued rows to bucket.")

    print("\n" + "-" * 78)
    print("HIT RATE BY RECOMMENDATION TIER")
    print("-" * 78)
    if "recommendation" in df.columns and df["recommendation"].notna().any():
        by_tier = df.groupby("recommendation").agg(
            n=("actual", "size"), hit_rate=("actual", "mean")
        ).reset_index().sort_values("hit_rate", ascending=False)
        by_tier["hit_rate"] = (by_tier["hit_rate"] * 100).round(1)
        print(by_tier.to_string(index=False))
        print("\nSTRONG BET should clearly outperform BET, which should outperform")
        print("LEAN. If tiers are flat or inverted, the confidence score isn't")
        print("actually tracking real edge.")
    else:
        print("No recommendation tier data available.")

    print("\n" + "-" * 78)
    print("ROI (flat $100 stake, using odds actually taken)")
    print("-" * 78)
    roi = roi_report(df)
    if roi.empty:
        print("No odds data in raw_json — can't compute ROI.")
    else:
        print(roi.to_string(index=False))

    print("\n" + "-" * 78)
    print("CLOSING LINE VALUE (CLV)")
    print("-" * 78)
    clv = clv_report(df)
    if clv is None:
        print("No opening_line/closing_line pairs recorded — can't compute CLV.")
        print("This is worth fixing: CLV agreement is a sample-size-independent")
        print("signal of real edge, useful even before you have enough settled")
        print("bets to trust the win-rate numbers above.")
    else:
        print(f"n = {clv['n']}, line moved in model's favor {clv['agreement_rate'] * 100:.1f}% of the time")
        print("(50% = no detectable edge vs. the market; meaningfully >50% is a good sign)")

    print("\n" + "=" * 78)


def main():
    parser = argparse.ArgumentParser(description="Backtest/calibration report for MultiSportPredict")
    parser.add_argument("--db", default="multisport_history.db",
                        help="Path to the historical_storage SQLite db")
    parser.add_argument("--sport", default=None, help="Filter to a single sport")
    parser.add_argument("--market-type", default=None, help="Filter to a single market type")
    parser.add_argument("--min-n", type=int, default=30, help="Warn if fewer settled predictions than this")
    args = parser.parse_args()

    build_report(args.db, args.sport, args.market_type, args.min_n)


if __name__ == "__main__":
    main()