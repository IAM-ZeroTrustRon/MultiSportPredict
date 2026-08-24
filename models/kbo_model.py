# ═══════════════════════════════════════════════════════════════════════════
# DEPRECATED / ORPHANED — DO NOT EXTEND OR RELY ON THIS FILE
# ───────────────────────────────────────────────────────────────────────────
# Confirmed via repo-wide import grep (see ARCHITECTURE.md §2/§3): this file
# is NOT reachable from predict_match.py (the live entry point). It has zero
# effect on real predictions. Keep it only as reference until it is deleted.
# ═══════════════════════════════════════════════════════════════════════════

from __future__ import annotations
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURE_COLS = [
    "home_woba", "away_woba",
    "home_wrc_plus", "away_wrc_plus",
    "home_fip", "away_fip",
    "home_whip", "away_whip",
    "home_bullpen_fip", "away_bullpen_fip",
    "sharp_score", "reverse_line_movement",
    "money_ticket_gap", "public_tickets_pct", "public_money_pct"
]

class KBOModel:
    def __init__(self):
        self.total_pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("rf", RandomForestRegressor(n_estimators=300, max_depth=10, random_state=42))
        ])

    def fit(self, df: pd.DataFrame, target_col: str = "total_runs"):
        X = df.reindex(columns=FEATURE_COLS).fillna(df[FEATURE_COLS].median(numeric_only=True))
        y = df[target_col].fillna(df[target_col].median())
        self.total_pipeline.fit(X, y)

    def predict(self, row: pd.Series) -> dict:
        X = row.reindex(FEATURE_COLS).to_frame().T.fillna(0)
        pred_runs = float(self.total_pipeline.predict(X)[0])
        lean = "Over" if pred_runs > float(row.get("runs_line", pred_runs)) else "Under"
        return {"predicted_runs": round(pred_runs, 2), "lean": lean}
