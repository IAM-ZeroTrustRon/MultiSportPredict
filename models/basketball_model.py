# ═══════════════════════════════════════════════════════════════════════════
# DEPRECATED / ORPHANED — DO NOT EXTEND OR RELY ON THIS FILE
# ───────────────────────────────────────────────────────────────────────────
# Confirmed via repo-wide import grep (see ARCHITECTURE.md §2/§3): this file
# is NOT reachable from predict_match.py (the live entry point). It has zero
# effect on real predictions. Keep it only as reference until it is deleted.
# ═══════════════════════════════════════════════════════════════════════════

"""
Basketball Model
================
Uses RandomForest on per-100-possession metrics + consensus signals.
Feature column list is imported from config.py to stay DRY.
"""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from config import (
    BASKETBALL_FEATURE_COLS,
    BASKETBALL_TARGET_COL,
    RF_N_ESTIMATORS,
    RF_MAX_DEPTH,
    RF_RANDOM_STATE,
)


class BasketballModel:
    """Random Forest regressor for basketball total points."""

    FEATURE_COLS = BASKETBALL_FEATURE_COLS

    def __init__(self):
        self.total_pipeline = Pipeline([
            ("scaler", StandardScaler()),
            (
                "rf",
                RandomForestRegressor(
                    n_estimators=RF_N_ESTIMATORS,
                    max_depth=RF_MAX_DEPTH,
                    random_state=RF_RANDOM_STATE,
                ),
            ),
        ])

    def fit(self, df: pd.DataFrame, target_col: str = BASKETBALL_TARGET_COL):
        """Fit on full feature set, filling NaN with median."""
        X = df.reindex(columns=self.FEATURE_COLS).fillna(
            df[self.FEATURE_COLS].median(numeric_only=True)
        )
        y = df[target_col].fillna(df[target_col].median())
        self.total_pipeline.fit(X, y)

    def predict(self, row: pd.Series) -> dict:
        """Predict total for a single game row."""
        X = row.reindex(self.FEATURE_COLS).to_frame().T.fillna(0)
        pred_total = float(self.total_pipeline.predict(X)[0])
        game_line = float(row.get("game_total_line", pred_total))
        lean = "Over" if pred_total > game_line else "Under"
        return {"predicted_total": round(pred_total, 2), "lean": lean}