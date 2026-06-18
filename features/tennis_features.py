"""
Tennis Feature Engineering Module
==================================
Advanced metrics for tennis match prediction including:
- Dominance Ratio (DR)
- Fatigue & Rustiness Deltas
- Environmental Interactions (Altitude, Court Speed, Elo)
"""

import numpy as np
import pandas as pd


def engineer_tennis_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates Dominance Ratio, Fatigue Deltas, and Rustiness.
    
    Args:
        df: DataFrame with tennis match and player statistics
        
    Returns:
        DataFrame with engineered tennis features
    """
    df = df.copy()
    
    # Core Serving & Returning Efficiency
    if "player_a_sv_pts" in df.columns and "player_b_sv_pts" in df.columns:
        df["pA_total_serve_won_pct"] = (
            df.get("player_a_1st_won", 0) + df.get("player_a_2nd_won", 0)
        ) / df["player_a_sv_pts"].replace(0, np.nan)
        
        df["pA_return_won_pct"] = df.get("player_a_ret_pts_won", 0) / df["player_b_sv_pts"].replace(0, np.nan)
    else:
        df["pA_total_serve_won_pct"] = np.nan
        df["pA_return_won_pct"] = np.nan
    
    # 1. The Dominance Ratio (DR)
    serve_denom = 1 - df["pA_total_serve_won_pct"].replace(0, np.nan)
    df["pA_dominance_ratio"] = df["pA_return_won_pct"] / serve_denom.replace(0, np.nan)
    
    # 2. Fatigue & Rustiness Deltas
    if "player_a_minutes_last_48h" in df.columns and "player_b_minutes_last_48h" in df.columns:
        df["fatigue_delta_48h"] = df["player_a_minutes_last_48h"] - df["player_b_minutes_last_48h"]
    else:
        df["fatigue_delta_48h"] = 0
    
    if "pA_days_since_last_match" in df.columns:
        df["pA_is_rusty"] = np.where(df["pA_days_since_last_match"] >= 14, 1, 0)
    else:
        df["pA_is_rusty"] = 0
    
    # 3. Environmental Interactions (Altitude x Elo x Court Speed)
    surface_speed_map = {"Clay": 0.85, "Hard_Outdoor": 1.00, "Hard_Indoor": 1.15, "Grass": 1.25}
    if "surface" in df.columns:
        df["court_speed_multiplier"] = df["surface"].map(surface_speed_map).fillna(1.0)
    else:
        df["court_speed_multiplier"] = 1.0
    
    if "player_a_current_elo" in df.columns and "player_b_current_elo" in df.columns:
        df["altitude_x_elo_diff"] = (
            df["player_a_current_elo"] - df["player_b_current_elo"]
        ) * df["court_speed_multiplier"]
    else:
        df["altitude_x_elo_diff"] = 0
    
    return df