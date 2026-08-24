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
from typing import Optional

from models.soccer_league_config import (
    get_league_config,
    get_league_config_for_match,
    add_league_detection_to_df,
    DEFAULT_LEAGUE_CONFIG,
)

FEATURE_COLS = [
    "home_xg", "away_xg", "home_xga", "away_xga",
    "home_shots", "away_shots",
    "home_corners", "away_corners",
    "home_form", "away_form",
    "sharp_score", "reverse_line_movement",
    "money_ticket_gap", "public_tickets_pct", "public_money_pct"
]


class SoccerModel:
    """Soccer prediction model with league-aware tuning."""
    
    def __init__(self, league: Optional[str] = None):
        """Initialize model, optionally for a specific league."""
        self.league_config = get_league_config(league) if league else DEFAULT_LEAGUE_CONFIG
        self.league_key = league or "unknown"
        
        # Create pipeline with league-specific hyperparameters
        self.goal_pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("rf", RandomForestRegressor(
                n_estimators=self.league_config.model_n_estimators,
                max_depth=self.league_config.model_max_depth,
                min_samples_split=self.league_config.model_min_samples_split,
                random_state=self.league_config.model_random_state
            ))
        ])

    def fit(self, df: pd.DataFrame, target_col: str = "total_goals"):
        """Fit model on training data."""
        # Add league detection if not present
        if "league" not in df.columns:
            df = add_league_detection_to_df(df)
        
        X = df.reindex(columns=FEATURE_COLS).fillna(df[FEATURE_COLS].median(numeric_only=True))
        y = df[target_col].fillna(df[target_col].median())
        self.goal_pipeline.fit(X, y)

    def predict(self, row: pd.Series) -> dict:
        """Predict goals for a single match."""
        # Ensure required features are present
        X = row.reindex(FEATURE_COLS).to_frame().T.fillna(0)
        
        # Predict goals
        pred_goals = float(self.goal_pipeline.predict(X)[0])
        
        # Determine lean (Over/Under)
        goals_line = float(row.get("goals_line", self.league_config.goals_line_default))
        lean = "Over" if pred_goals > goals_line else "Under"
        
        # Determine BTTS (Both Teams To Score)
        home_xg = row.get("home_xg", 1.0)
        away_xg = row.get("away_xg", 1.0)
        btts_threshold = self.league_config.btts_xg_threshold
        btts = "Yes" if (home_xg > btts_threshold and away_xg > btts_threshold) else "No"
        
        return {
            "predicted_goals": round(pred_goals, 2),
            "lean": lean,
            "btts": btts,
            "league": self.league_key,
        }
