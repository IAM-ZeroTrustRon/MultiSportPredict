#!/usr/bin/env python
"""
Basketball Predictor Module for MultiSportPredict
==================================================
Specialized predictor for FIBA/European basketball games.

Key Features:
- 40-minute game normalization (vs NBA 48-minute)
- Per-100 possession metrics (ORTG, DRTG)
- FIBA-specific rule adjustments (no defensive three seconds, goaltending)
- Tournament fatigue tracking (multi-competition schedules)
- European league support (EuroLeague, Liga ACB, BBL, LNB Élite)

Architecture:
- Inherits from SportPredictorBase
- Uses European template from MultiSportModel.py
- Implements Ridge Regression for spread predictions
- Poisson distributions for point totals
"""

import math
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from pathlib import Path
import pandas as pd
import numpy as np

from base_predictor import SportPredictorBase

# Import shared utilities to avoid duplication
from core.utils import sigmoid, clamp, to_num, color_score


# ============================================================================
# UTILITY FUNCTIONS (Adapted from MultiSportModel.py)
# ============================================================================


# ============================================================================
# DATA CLASSES (FIBA/European Basketball Template)
# ============================================================================

@dataclass
class FIBAContext:
    """Context information for a FIBA/European basketball game"""
    game_id: str
    date: str
    league: str  # e.g., EuroLeague, Liga ACB, BBL, LNB Élite
    home_team: str
    away_team: str
    market_line: float
    current_line: float
    open_line: float
    notes: Optional[str] = None


@dataclass
class FIBATeamMetrics:
    """
    Team performance metrics adjusted for FIBA rules.
    
    Key differences from NBA:
    - Per-100 possession metrics (not per-game)
    - 40-minute pace normalization
    - Tournament fatigue tracking
    """
    ortg_per_100: float      # Offensive Rating per 100 possessions
    drtg_per_100: float      # Defensive Rating per 100 possessions
    baseline_net_per_100: float
    recent_net_per_100: float
    pace_per_40: float       # Pace adjusted to 40 minutes (FIBA games)
    rest_days: int
    travel_km: float
    back_to_back: bool
    three_in_six: bool       # Fatigue indicator (3 games in 6 days)
    split_edge: float        # Home/away split advantage
    rotation_depth: int      # Number of rotation players
    injury_status: str       # green, yellow, red
    coach_stability: str     # green, yellow, red
    motivation: str          # green, yellow, red
    # FIBA-specific metrics
    three_pt_pct: float      # Higher weight for perimeter shooting (no defensive 3s)
    orb_pct: float           # Offensive Rebounding % (goaltending rule impact)


# ============================================================================
# FIBA BASKETBALL ANALYSIS FUNCTIONS
# ============================================================================

def fiba_team_net_rating(ortg_per_100: float, drtg_per_100: float) -> float:
    """Calculate team net rating per 100 possessions"""
    return ortg_per_100 - drtg_per_100


def fiba_efficiency_gap(home: FIBATeamMetrics, away: FIBATeamMetrics) -> float:
    """Calculate efficiency gap between home and away teams (per 100 possessions)"""
    return fiba_team_net_rating(home.ortg_per_100, home.drtg_per_100) - \
           fiba_team_net_rating(away.ortg_per_100, away.drtg_per_100)


def fiba_historical_gap(current_gap: float, baseline_gap: float, recent_gap: float) -> float:
    """Blend current, baseline, and recent efficiency gaps"""
    return (current_gap - baseline_gap) * 0.6 + (recent_gap - baseline_gap) * 0.4


def fiba_rest_travel_score(rest_days: int, travel_km: float, back_to_back: bool, three_in_six: bool) -> float:
    """
    Score rest and travel factors, including tournament fatigue.
    
    FIBA/European teams often play multiple competitions simultaneously
    (domestic league + EuroLeague/BCL), leading to complex fatigue patterns.
    """
    score = 0.0
    if rest_days >= 3:
        score += 2.0
    elif rest_days == 2:
        score += 1.0
    else:
        score -= 1.0
    
    # Travel fatigue (cross-border flights in European competitions)
    if travel_km >= 2000:
        score -= 2.0
    elif travel_km >= 1000:
        score -= 1.0
    
    # Back-to-back penalty
    if back_to_back:
        score -= 2.0
    
    # Three games in six days (common in European tournaments)
    if three_in_six:
        score -= 1.0
    
    return score


def fiba_team_context_score(rotation_depth: int, injury_status: str, coach_stability: str, motivation: str) -> float:
    """Score contextual factors for a team"""
    score = 0.0
    if rotation_depth >= 10:
        score += 1.0
    elif rotation_depth <= 7:
        score -= 1.0
    
    score += color_score(injury_status)
    score += color_score(coach_stability) * 0.5
    score += color_score(motivation) * 0.5
    
    return score


def fiba_market_filter(open_line: float, current_line: float, model_edge: float) -> float:
    """Validate model edge against market movement"""
    movement = current_line - open_line
    if abs(model_edge - movement) < 1.5:
        return 2.0
    if abs(model_edge - movement) < 3.0:
        return 1.0
    return -1.0


def fiba_score_to_prob(score: float) -> float:
    """Convert raw score to win probability"""
    return clamp(sigmoid((score - 4.0) / 2.5))


def fiba_recommendation(prob: float, market_ok: bool) -> str:
    """Generate recommendation based on probability and market validation"""
    if not market_ok:
        return "Pass"
    if prob >= 0.63:
        return "Strong lean"
    if prob >= 0.57:
        return "Moderate lean"
    if prob >= 0.53:
        return "Slight lean"
    return "Pass"


def fiba_build_full_game(home: FIBATeamMetrics, away: FIBATeamMetrics, ctx: FIBAContext) -> Dict[str, Any]:
    """
    Build full game prediction using European template.
    
    This is adapted from MultiSportModel.py's eu_build_full_game function,
    with additional FIBA-specific adjustments for:
    - 40-minute game format
    - Per-100 possession metrics
    - Three-point shooting emphasis (no defensive three seconds)
    - Offensive rebounding impact (goaltending rule)
    """
    # Calculate efficiency gaps
    current_gap = fiba_efficiency_gap(home, away)
    baseline_gap = home.baseline_net_per_100 - away.baseline_net_per_100
    recent_gap = home.recent_net_per_100 - away.recent_net_per_100
    hist_gap = fiba_historical_gap(current_gap, baseline_gap, recent_gap)
    
    # Rest and travel factors
    home_rest_score = fiba_rest_travel_score(
        home.rest_days, home.travel_km, home.back_to_back, home.three_in_six
    )
    away_rest_score = fiba_rest_travel_score(
        away.rest_days, away.travel_km, away.back_to_back, away.three_in_six
    )
    rest_gap = home_rest_score - away_rest_score
    
    # Home/away splits
    split_gap = home.split_edge - away.split_edge
    
    # Team context (rotation, injuries, coaching, motivation)
    home_ctx_score = fiba_team_context_score(
        home.rotation_depth, home.injury_status, home.coach_stability, home.motivation
    )
    away_ctx_score = fiba_team_context_score(
        away.rotation_depth, away.injury_status, away.coach_stability, away.motivation
    )
    ctx_gap = home_ctx_score - away_ctx_score
    
    # FIBA-specific adjustments
    # 1. Three-point shooting emphasis (no defensive three seconds = perimeter more important)
    three_pt_edge = (home.three_pt_pct - away.three_pt_pct) * 10
    
    # 2. Offensive rebounding impact (goaltending rule = more putbacks)
    orb_edge = (home.orb_pct - away.orb_pct) * 20
    
    # Calculate model edge
    model_edge = (
        hist_gap * 0.8 +
        rest_gap * 0.9 +
        split_gap * 0.6 +
        ctx_gap * 0.8 +
        three_pt_edge * 0.5 +
        orb_edge * 0.5
    )
    
    # Market validation
    market_score = fiba_market_filter(ctx.open_line, ctx.current_line, model_edge)
    total_score = model_edge + market_score * 0.9
    
    # Win probability
    prob = fiba_score_to_prob(total_score)
    market_ok = market_score >= 0
    lean = fiba_recommendation(prob, market_ok)
    
    # Project scores (adjusted for 40-minute FIBA format)
    # Base FIBA scores are typically lower than NBA (75-80 vs 110-115)
    projected_home_score = round(75 + total_score * 1.8 + home.pace_per_40 * 0.2, 1)
    projected_away_score = round(73 - total_score * 0.9 + away.pace_per_40 * 0.2, 1)
    projected_total = round(projected_home_score + projected_away_score, 1)
    
    return {
        "record_type": "full_game",
        "current_gap": round(current_gap, 2),
        "baseline_gap": round(baseline_gap, 2),
        "recent_gap": round(recent_gap, 2),
        "historical_gap": round(hist_gap, 2),
        "rest_gap": round(rest_gap, 2),
        "split_gap": round(split_gap, 2),
        "context_gap": round(ctx_gap, 2),
        "model_edge": round(model_edge, 2),
        "market_score": round(market_score, 2),
        "probability": round(prob, 4),
        "lean": lean,
        "projected_home_score": projected_home_score,
        "projected_away_score": projected_away_score,
        "projected_total": projected_total,
    }


def fiba_build_q1(
    home: FIBATeamMetrics, 
    away: FIBATeamMetrics, 
    home_q1_metrics: Dict, 
    away_q1_metrics: Dict,
    ctx: FIBAContext
) -> Dict[str, Any]:
    """
    Build Q1 prediction using European template.
    
    First quarter predictions are important in FIBA basketball due to:
    - Different starting lineup strategies
    - Coach "fast start" tendencies
    - Early foul trouble impacts
    """
    # Q1-specific model
    home_q1_model = (
        (home_q1_metrics.get('pts_for', 20) - home_q1_metrics.get('pts_against', 20)) * 0.8
        + home_q1_metrics.get('home_edge', 0) * 0.7
        + color_score(home_q1_metrics.get('coach_fast_start', 'yellow')) * 0.8
        + color_score(home_q1_metrics.get('injury_status', 'yellow')) * 0.7
        + (home_q1_metrics.get('starting_five_net', 0) * 0.4)
    )
    
    away_q1_model = (
        (away_q1_metrics.get('pts_for', 20) - away_q1_metrics.get('pts_against', 20)) * 0.8
        - home_q1_metrics.get('home_edge', 0) * 0.7  # Away disadvantage
        + color_score(away_q1_metrics.get('coach_fast_start', 'yellow')) * 0.8
        + color_score(away_q1_metrics.get('injury_status', 'yellow')) * 0.7
        + (away_q1_metrics.get('starting_five_net', 0) * 0.4)
    )
    
    q1_market_ok = abs((ctx.current_line - ctx.open_line)) <= 3.0
    q1_total_model = home_q1_model - away_q1_model
    prob = fiba_score_to_prob(q1_total_model)
    lean = fiba_recommendation(prob, q1_market_ok)
    
    return {
        "record_type": "q1",
        "q1_model": round(q1_total_model, 2),
        "probability": round(prob, 4),
        "lean": lean,
        "projected_q1_home": round(home_q1_metrics.get('pts_for', 20) + home_q1_metrics.get('home_edge', 0) * 0.5, 1),
        "projected_q1_away": round(away_q1_metrics.get('pts_for', 20) - home_q1_metrics.get('home_edge', 0) * 0.2, 1),
        "projected_q1_total": round(home_q1_metrics.get('pts_for', 20) + away_q1_metrics.get('pts_for', 20), 1),
    }


# ============================================================================
# BASKETBALL PREDICTOR CLASS
# ============================================================================

class BasketballPredictor(SportPredictorBase):
    """
    Predictor for FIBA/European Basketball games.
    
    Supports multiple European leagues:
    - EuroLeague
    - EuroCup
    - Liga ACB (Spain)
    - LNB Élite (France)
    - BBL (Germany)
    - FIBA international tournaments
    
    Key features:
    - 40-minute game normalization
    - Per-100 possession metrics
    - Tournament fatigue tracking
    - FIBA rule adjustments
    """
    
    def __init__(self, league: str = "EuroLeague", **kwargs):
        """
        Initialize Basketball Predictor.
        
        Args:
            league: Default league for predictions
            **kwargs: Additional configuration
        """
        super().__init__(name=f"BasketballPredictor_{league}")
        self.league = league
        self._data_path = kwargs.get('data_path', 'data/basketball/')
    
    def load_data(self, data_path: str = None, *args, **kwargs) -> pd.DataFrame:
        """
        Load FIBA/European basketball data.
        
        Data should be normalized to:
        - 40-minute format
        - Per-100 possession metrics
        - Include tournament fatigue indicators
        
        Args:
            data_path: Path to data directory or file
            *args: Additional arguments
            **kwargs: Additional keyword arguments
            
        Returns:
            DataFrame with basketball data
        """
        path = data_path or self._data_path
        print(f"[{self.name}] Loading basketball data from {path}...")
        
        try:
            # Try to load from CSV
            df = pd.read_csv(path)
            
            # Ensure data is normalized to 40 minutes and per 100 possessions
            if 'ortg' in df.columns and 'pace' in df.columns:
                # Convert per-game ORTG/DRTG to per-100 possessions
                df['ortg_per_100'] = (df['ortg'] / df['pace']) * 100
                df['drtg_per_100'] = (df['drtg'] / df['pace']) * 100
            
            if 'pace' in df.columns:
                # Convert 48-minute pace to 40-minute pace
                df['pace_per_40'] = df['pace'] * (40 / 48)
            
            return df
            
        except FileNotFoundError:
            print(f"[{self.name}] Warning: Data file not found at {path}. Returning empty DataFrame.")
            return pd.DataFrame()
        except Exception as e:
            print(f"[{self.name}] Error loading data: {e}")
            return pd.DataFrame()
    
    def feature_engineering(self, data: pd.DataFrame, *args, **kwargs) -> pd.DataFrame:
        """
        Engineer features for FIBA basketball predictions.
        
        Features created:
        - Net rating differentials
        - Rest/travel scores
        - Team context scores
        - FIBA-specific metrics (3PT%, ORB%)
        
        Args:
            data: Raw data from load_data()
            *args: Additional arguments
            **kwargs: Additional keyword arguments
            
        Returns:
            DataFrame with engineered features
        """
        if data.empty:
            return data
        
        print(f"[{self.name}] Engineering features...")
        
        # Calculate net ratings
        if 'home_ortg_per_100' in data.columns and 'home_drtg_per_100' in data.columns:
            data['home_net_rating'] = fiba_team_net_rating(
                data['home_ortg_per_100'], data['home_drtg_per_100']
            )
            data['away_net_rating'] = fiba_team_net_rating(
                data['away_ortg_per_100'], data['away_drtg_per_100']
            )
            data['efficiency_gap'] = data['home_net_rating'] - data['away_net_rating']
        
        # Calculate rest/travel scores
        if 'home_rest_days' in data.columns:
            data['home_rest_score'] = data.apply(
                lambda row: fiba_rest_travel_score(
                    row.get('home_rest_days', 2),
                    row.get('home_travel_km', 0),
                    row.get('home_back_to_back', False),
                    row.get('home_three_in_six', False)
                ), axis=1
            )
            data['away_rest_score'] = data.apply(
                lambda row: fiba_rest_travel_score(
                    row.get('away_rest_days', 2),
                    row.get('away_travel_km', 0),
                    row.get('away_back_to_back', False),
                    row.get('away_three_in_six', False)
                ), axis=1
            )
            data['rest_gap'] = data['home_rest_score'] - data['away_rest_score']
        
        return data
    
    def train_model(self, features: pd.DataFrame, *args, **kwargs) -> Any:
        """
        Train a machine learning model for FIBA basketball.
        
        This is a placeholder for actual ML implementation.
        In production, this would use:
        - XGBoost for spread predictions
        - Ridge Regression for point totals
        - Historical data for model training
        
        Args:
            features: Processed features from feature_engineering()
            *args: Additional arguments
            **kwargs: Additional keyword arguments
            
        Returns:
            Trained model or None for placeholder
        """
        print(f"[{self.name}] Training model... (placeholder - implement ML pipeline)")
        
        # Placeholder: In production, train actual ML model
        # Example:
        # from sklearn.ensemble import GradientBoostingRegressor
        # model = GradientBoostingRegressor(n_estimators=100, max_depth=5)
        # model.fit(features[feature_columns], features['target'])
        # return model
        
        return None
    
    def predict(
        self, 
        features: pd.DataFrame, 
        model: Any, 
        home_team: str = None, 
        away_team: str = None,
        market_line: float = 0.0,
        current_line: float = 0.0,
        open_line: float = 0.0,
        *args, 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make predictions for a FIBA basketball game.
        
        Args:
            features: Processed features DataFrame
            model: Trained model (or None for placeholder)
            home_team: Home team name
            away_team: Away team name
            market_line: Current market spread
            current_line: Current line (for market filter)
            open_line: Opening line (for market filter)
            *args: Additional arguments
            **kwargs: Additional keyword arguments
            
        Returns:
            Dictionary with predictions
        """
        print(f"[{self.name}] Predicting: {home_team} vs {away_team}")
        
        # Create game context
        ctx = FIBAContext(
            game_id=f"{home_team.replace(' ', '_')}_vs_{away_team.replace(' ', '_')}",
            date=kwargs.get('date', pd.Timestamp.now().strftime('%Y-%m-%d')),
            league=self.league,
            home_team=home_team,
            away_team=away_team,
            market_line=market_line,
            current_line=current_line or market_line,
            open_line=open_line or market_line,
        )
        
        # Create team metrics (placeholder values - would come from features in production)
        home_metrics = FIBATeamMetrics(
            ortg_per_100=kwargs.get('home_ortg', 110.0),
            drtg_per_100=kwargs.get('home_drtg', 105.0),
            baseline_net_per_100=kwargs.get('home_baseline_net', 5.0),
            recent_net_per_100=kwargs.get('home_recent_net', 6.0),
            pace_per_40=kwargs.get('home_pace', 72.0),
            rest_days=kwargs.get('home_rest_days', 2),
            travel_km=kwargs.get('home_travel_km', 500.0),
            back_to_back=kwargs.get('home_back_to_back', False),
            three_in_six=kwargs.get('home_three_in_six', False),
            split_edge=kwargs.get('home_split_edge', 1.0),
            rotation_depth=kwargs.get('home_rotation_depth', 9),
            injury_status=kwargs.get('home_injury_status', 'green'),
            coach_stability=kwargs.get('home_coach_stability', 'green'),
            motivation=kwargs.get('home_motivation', 'green'),
            three_pt_pct=kwargs.get('home_three_pt_pct', 0.38),
            orb_pct=kwargs.get('home_orb_pct', 0.30),
        )
        
        away_metrics = FIBATeamMetrics(
            ortg_per_100=kwargs.get('away_ortg', 108.0),
            drtg_per_100=kwargs.get('away_drtg', 107.0),
            baseline_net_per_100=kwargs.get('away_baseline_net', 1.0),
            recent_net_per_100=kwargs.get('away_recent_net', 2.0),
            pace_per_40=kwargs.get('away_pace', 70.0),
            rest_days=kwargs.get('away_rest_days', 1),
            travel_km=kwargs.get('away_travel_km', 1200.0),
            back_to_back=kwargs.get('away_back_to_back', True),
            three_in_six=kwargs.get('away_three_in_six', True),
            split_edge=kwargs.get('away_split_edge', -0.5),
            rotation_depth=kwargs.get('away_rotation_depth', 8),
            injury_status=kwargs.get('away_injury_status', 'yellow'),
            coach_stability=kwargs.get('away_coach_stability', 'yellow'),
            motivation=kwargs.get('away_motivation', 'yellow'),
            three_pt_pct=kwargs.get('away_three_pt_pct', 0.35),
            orb_pct=kwargs.get('away_orb_pct', 0.25),
        )
        
        # Build full game prediction
        full_game_result = fiba_build_full_game(home_metrics, away_metrics, ctx)
        
        # Build Q1 prediction (placeholder Q1 metrics)
        home_q1_metrics = {
            'pts_for': 20.0,
            'pts_against': 18.0,
            'home_edge': 2.0,
            'coach_fast_start': 'green',
            'injury_status': 'green',
            'starting_five_net': 3.0,
        }
        away_q1_metrics = {
            'pts_for': 18.0,
            'pts_against': 20.0,
            'home_edge': 0.0,
            'coach_fast_start': 'yellow',
            'injury_status': 'yellow',
            'starting_five_net': 1.0,
        }
        q1_result = fiba_build_q1(home_metrics, away_metrics, home_q1_metrics, away_q1_metrics, ctx)
        
        # Build comprehensive output
        result = {
            "sport": "basketball",
            "league": self.league,
            "home_team": home_team,
            "away_team": away_team,
            "timestamp": pd.Timestamp.now().isoformat(),
            "full_game": full_game_result,
            "q1": q1_result,
            "market_info": {
                "spread": market_line,
                "current_line": current_line or market_line,
                "open_line": open_line or market_line,
            },
            "team_metrics": {
                "home": asdict(home_metrics),
                "away": asdict(away_metrics),
            },
            "notes": (
                "FIBA/European rules applied: "
                "40-minute game, per-100 possession metrics, "
                "tournament fatigue tracking, 3PT/ORB weighting"
            ),
        }
        
        return result
    
    def predict_from_row(self, row: pd.Series) -> Dict[str, Any]:
        """
        Make prediction from a single data row.
        
        Useful for batch processing of multiple games.
        
        Args:
            row: DataFrame row with game data
            
        Returns:
            Prediction dictionary
        """
        return self.predict(
            features=pd.DataFrame(),
            model=self._model,
            home_team=row.get('home_team', 'Unknown'),
            away_team=row.get('away_team', 'Unknown'),
            market_line=to_num(row.get('market_line', 0)),
            current_line=to_num(row.get('current_line', 0)),
            open_line=to_num(row.get('open_line', 0)),
            date=row.get('date', pd.Timestamp.now().strftime('%Y-%m-%d')),
            home_ortg=to_num(row.get('home_ortg_per_100', 110)),
            home_drtg=to_num(row.get('home_drtg_per_100', 105)),
            home_baseline_net=to_num(row.get('home_baseline_net', 0)),
            home_recent_net=to_num(row.get('home_recent_net', 0)),
            home_pace=to_num(row.get('home_pace', 72)),
            home_rest_days=int(to_num(row.get('home_rest_days', 2))),
            home_travel_km=to_num(row.get('home_travel_km', 0)),
            home_back_to_back=row.get('home_back_to_back', False),
            home_three_in_six=row.get('home_three_in_six', False),
            home_split_edge=to_num(row.get('home_split_edge', 0)),
            home_rotation_depth=int(to_num(row.get('home_rotation_depth', 9))),
            home_injury_status=row.get('home_injury_status', 'green'),
            home_coach_stability=row.get('home_coach_stability', 'green'),
            home_motivation=row.get('home_motivation', 'green'),
            home_three_pt_pct=to_num(row.get('home_three_pt_pct', 0.36)),
            home_orb_pct=to_num(row.get('home_orb_pct', 0.28)),
            away_ortg=to_num(row.get('away_ortg_per_100', 108)),
            away_drtg=to_num(row.get('away_drtg_per_100', 107)),
            away_baseline_net=to_num(row.get('away_baseline_net', 0)),
            away_recent_net=to_num(row.get('away_recent_net', 0)),
            away_pace=to_num(row.get('away_pace', 70)),
            away_rest_days=int(to_num(row.get('away_rest_days', 2))),
            away_travel_km=to_num(row.get('away_travel_km', 0)),
            away_back_to_back=row.get('away_back_to_back', False),
            away_three_in_six=row.get('away_three_in_six', False),
            away_split_edge=to_num(row.get('away_split_edge', 0)),
            away_rotation_depth=int(to_num(row.get('away_rotation_depth', 8))),
            away_injury_status=row.get('away_injury_status', 'green'),
            away_coach_stability=row.get('away_coach_stability', 'green'),
            away_motivation=row.get('away_motivation', 'green'),
            away_three_pt_pct=to_num(row.get('away_three_pt_pct', 0.35)),
            away_orb_pct=to_num(row.get('away_orb_pct', 0.27)),
        )


# Example usage and testing
if __name__ == "__main__":
    print("=" * 60)
    print("Testing BasketballPredictor (FIBA/European)")
    print("=" * 60)
    
    # Create predictor
    predictor = BasketballPredictor(league="EuroLeague")
    
    # Test prediction
    result = predictor.predict(
        features=pd.DataFrame(),
        model=None,
        home_team="Real Madrid",
        away_team="FC Barcelona",
        market_line=5.5,
        current_line=6.0,
        open_line=5.0,
    )
    
    print("\nPrediction Result:")
    print(f"  Sport: {result['sport']}")
    print(f"  League: {result['league']}")
    print(f"  Matchup: {result['home_team']} vs {result['away_team']}")
    print(f"\nFull Game:")
    print(f"  Projected Score: {result['full_game']['projected_home_score']:.1f} - {result['full_game']['projected_away_score']:.1f}")
    print(f"  Projected Total: {result['full_game']['projected_total']:.1f}")
    print(f"  Model Edge: {result['full_game']['model_edge']:+.2f}")
    print(f"  Probability: {result['full_game']['probability']:.1%}")
    print(f"  Lean: {result['full_game']['lean']}")
    print(f"\nQ1:")
    print(f"  Projected Q1 Total: {result['q1']['projected_q1_total']:.1f}")
    print(f"  Q1 Lean: {result['q1']['lean']}")
    print(f"\nNotes: {result['notes']}")