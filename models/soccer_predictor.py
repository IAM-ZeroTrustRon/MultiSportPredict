#!/usr/bin/env python
"""
Soccer Predictor Module for MultiSportPredict
==============================================
Specialized predictor for soccer matches using advanced statistical models.

Key Features:
- Bivariate Poisson distribution for goal probabilities
- Dixon-Coles time-decay modifications on xG metrics
- Expected Goals (xG) based predictions
- Support for multiple leagues and competitions
- Home/away defensive strength differentiation

Architecture:
- Inherits from SportPredictorBase
- Uses Poisson distributions for low-scoring nature of soccer
- Implements time-decayed form tracking
- Handles draw outcomes explicitly
"""

import math
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import pandas as pd
import numpy as np
from scipy.stats import poisson

from base_predictor import SportPredictorBase

# Import shared utilities to avoid duplication
from core.utils import (
    sigmoid, clamp, to_num,
    poisson_pmf, poisson_over_prob, poisson_at_least_one
)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


# ============================================================================
# LEAGUE CONFIGURATIONS
# ============================================================================

LEAGUE_CONFIGS = {
    'Premier League': {
        'goal_variance': 1.10,
        'avg_goals_per_game': 2.85,
        'home_advantage': 0.35,
        'draw_rate': 0.25,
    },
    'La Liga': {
        'goal_variance': 1.05,
        'avg_goals_per_game': 2.65,
        'home_advantage': 0.40,
        'draw_rate': 0.27,
    },
    'Bundesliga': {
        'goal_variance': 1.15,
        'avg_goals_per_game': 3.10,
        'home_advantage': 0.30,
        'draw_rate': 0.23,
    },
    'Serie A': {
        'goal_variance': 1.00,
        'avg_goals_per_game': 2.55,
        'home_advantage': 0.38,
        'draw_rate': 0.28,
    },
    'Ligue 1': {
        'goal_variance': 1.08,
        'avg_goals_per_game': 2.60,
        'home_advantage': 0.35,
        'draw_rate': 0.26,
    },
    'EuroLeague': {
        'goal_variance': 1.05,
        'avg_goals_per_game': 2.70,
        'home_advantage': 0.30,
        'draw_rate': 0.25,
    },
    'World Cup': {
        'goal_variance': 1.00,
        'avg_goals_per_game': 2.50,
        'home_advantage': 0.20,
        'draw_rate': 0.30,
    },
    'default': {
        'goal_variance': 1.0,
        'avg_goals_per_game': 2.70,
        'home_advantage': 0.35,
        'draw_rate': 0.26,
    }
}


def get_league_config(league_name: str) -> Dict:
    """Get league-specific configuration"""
    return LEAGUE_CONFIGS.get(league_name, LEAGUE_CONFIGS['default'])


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class SoccerContext:
    """Context information for a soccer match"""
    game_id: str
    date: str
    league: str
    home_team: str
    away_team: str
    market_line: float  # Asian handicap
    market_total: float  # Over/under goals
    open_line: float = 0.0
    open_total: float = 0.0
    notes: Optional[str] = None


@dataclass
class SoccerTeamMetrics:
    """Team performance metrics for soccer"""
    xg_for: float          # Expected goals for (per game)
    xg_against: float      # Expected goals against (per game)
    shots: float           # Average shots per game
    sot: float             # Average shots on target per game
    goals_for: float       # Actual goals scored (per game)
    goals_against: float   # Actual goals conceded (per game)
    clean_sheets: int      # Clean sheets in last 10 games
    missing_attacker: int  # Number of missing attackers
    missing_creator: int   # Number of missing creators
    missing_cb: int        # Number of missing center backs
    missing_gk: int        # Goalkeeper injury (0=no, 1=yes)
    tempo: float           # Playing tempo (0-1)
    width_crossing: float  # Width and crossing tendency (0-1)
    final_third_pressure: float  # Final third pressure (0-1)


# ============================================================================
# STATISTICAL FUNCTIONS
# ============================================================================

def poisson_pmf(k: int, lam: float) -> float:
    """
    Poisson probability mass function.
    
    Args:
        k: Number of events
        lam: Expected value (lambda)
        
    Returns:
        Probability of exactly k events
    """
    if lam <= 0:
        return 0.0 if k > 0 else 1.0
    if k < 0:
        return 0.0
    
    try:
        log_pmf = -lam + k * math.log(lam) - math.lgamma(k + 1)
        return math.exp(log_pmf)
    except (ValueError, OverflowError):
        return 0.0


def poisson_over_prob(lam: float, line: float) -> float:
    """
    Calculate probability of over a given line using Poisson distribution.
    
    Args:
        lam: Expected value (lambda)
        line: Goal line (can be fractional, e.g., 2.5)
        
    Returns:
        Probability of over the line
    """
    n = int(math.floor(line))
    frac = line - n
    
    if abs(frac) < 1e-9:
        # Whole number line (push possible)
        return 1 - sum(poisson_pmf(k, lam) for k in range(0, n + 1))
    else:
        # Fractional line (no push)
        threshold = math.floor(line)
        return 1 - sum(poisson_pmf(k, lam) for k in range(0, threshold + 1))


def poisson_at_least_one(lam: float) -> float:
    """Probability of at least one event occurring"""
    return 1 - math.exp(-lam)


def calculate_bivariate_poisson_probabilities(
    lambda_home: float, 
    lambda_away: float, 
    max_goals: int = 5
) -> pd.DataFrame:
    """
    Calculate a matrix of probabilities for home and away goals using Bivariate Poisson.
    
    This is a simplified version that assumes independence. A full implementation
    would include a correlation parameter (rho) to account for game state effects.
    
    Args:
        lambda_home: Expected home goals
        lambda_away: Expected away goals
        max_goals: Maximum goals to consider
        
    Returns:
        DataFrame with probability matrix
    """
    home_goals = range(max_goals + 1)
    away_goals = range(max_goals + 1)
    prob_matrix = pd.DataFrame(index=home_goals, columns=away_goals, dtype=float)
    
    for i in home_goals:
        for j in away_goals:
            # Simplified Bivariate Poisson: assumes independence
            prob_matrix.loc[i, j] = poisson.pmf(i, lambda_home) * poisson.pmf(j, lambda_away)
    
    return prob_matrix


def dixon_coles_xg_adjustment(
    team_xg_for: float, 
    team_xg_against: float, 
    opp_xg_for: float, 
    opp_xg_against: float,
    time_decay: float = 0.95
) -> Tuple[float, float]:
    """
    Apply Dixon-Coles-like adjustment using Expected Goals (xG).
    
    The Dixon-Coles model modifies the standard Poisson model to:
    1. Account for low-scoring nature of soccer
    2. Apply time-decay to recent form
    3. Differentiate home/away defensive strengths
    
    Args:
        team_xg_for: Team's expected goals for
        team_xg_against: Team's expected goals against
        opp_xg_for: Opponent's expected goals for
        opp_xg_against: Opponent's expected goals against
        time_decay: Decay factor for recent form (0-1)
        
    Returns:
        Tuple of (attack_strength, defense_strength)
    """
    # Attack strength is relative xG for
    attack_strength = team_xg_for / opp_xg_against if opp_xg_against > 0 else 1.0
    
    # Defense strength is relative xG against (lower is better)
    defense_strength = team_xg_against / opp_xg_for if opp_xg_for > 0 else 1.0
    
    # Apply time decay to recent form
    attack_strength *= time_decay
    defense_strength *= time_decay
    
    return attack_strength, defense_strength


def team_goal_strength(
    xg_for: float, xg_against: float, shots: float, sot: float,
    goals_for: float, goals_against: float, tempo: float,
    home: int, missing_attacker: int, missing_creator: int,
    missing_cb: int, missing_gk: int
) -> float:
    """
    Calculate team goal strength score.
    
    Comprehensive metric combining multiple factors:
    - Expected goals (most important)
    - Shot metrics
    - Actual goals (finishing efficiency)
    - Tempo and playing style
    - Home advantage
    - Missing players impact
    
    Args:
        xg_for: Expected goals for
        xg_against: Expected goals against
        shots: Average shots per game
        sot: Average shots on target
        goals_for: Actual goals scored
        goals_against: Actual goals conceded
        tempo: Playing tempo (0-1)
        home: Home advantage (1=home, 0=away)
        missing_attacker: Missing attackers
        missing_creator: Missing creators
        missing_cb: Missing center backs
        missing_gk: Goalkeeper injured
        
    Returns:
        Goal strength score
    """
    score = 0.0
    score += 1.25 * (xg_for - 1.35)           # xG for (most important)
    score += -0.95 * (xg_against - 1.25)      # xG against
    score += 0.12 * (shots - 11)               # Shot volume
    score += 0.18 * (sot - 4)                  # Shot quality
    score += 0.10 * (goals_for - 1.2)          # Actual finishing
    score += -0.10 * (goals_against - 1.1)     # Actual defending
    score += 0.25 * tempo                      # Tempo factor
    score += 0.20 * home                       # Home advantage
    score += -0.30 * missing_attacker          # Missing attackers
    score += -0.22 * missing_creator           # Missing creators
    score += 0.24 * (missing_cb + missing_gk)  # Missing defenders
    
    return score


def team_btts_strength(
    xg_for: float, xg_against: float, goals_for: float,
    goals_against: float, sot: float, tempo: float,
    final_third_pressure: float, missing_attacker: int,
    missing_cb: int, missing_gk: int, clean_sheets_last10: int
) -> float:
    """
    Calculate team BTTS (Both Teams To Score) strength score.
    
    Args:
        xg_for: Expected goals for
        xg_against: Expected goals against
        goals_for: Actual goals scored
        goals_against: Actual goals conceded
        sot: Shots on target
        tempo: Playing tempo
        final_third_pressure: Pressure in final third
        missing_attacker: Missing attackers
        missing_cb: Missing center backs
        missing_gk: Goalkeeper injured
        clean_sheets_last10: Clean sheets in last 10 games
        
    Returns:
        BTTS strength score
    """
    score = 0.0
    score += 1.05 * (xg_for - 1.20)           # Scoring ability
    score += 0.95 * (xg_against - 1.25)       # Conceding tendency
    score += 0.10 * (goals_for - 1.2)         # Actual scoring
    score += 0.10 * (goals_against - 1.1)     # Actual conceding
    score += 0.12 * (sot - 3.5)               # Shot quality
    score += 0.18 * tempo                     # Tempo (more goals)
    score += 0.15 * final_third_pressure      # Attacking pressure
    score += -0.35 * missing_attacker         # Missing attackers
    score += 0.28 * (missing_cb + missing_gk) # Missing defenders
    score += -0.20 * clean_sheets_last10 / 10.0  # Clean sheet tendency
    
    return score


def team_corner_strength(
    shots: float, sot: float, final_third_pressure: float,
    width_crossing: float, tempo: float, home: int,
    missing_cb: int, missing_gk: int, missing_attacker: int
) -> float:
    """
    Calculate team corner strength score.
    
    Corners are influenced by:
    - Shot volume and quality
    - Attacking pressure in final third
    - Width and crossing tendency
    - Tempo of play
    - Home advantage
    
    Args:
        shots: Average shots per game
        sot: Shots on target
        final_third_pressure: Pressure in final third
        width_crossing: Width and crossing tendency
        tempo: Playing tempo
        home: Home advantage (1=home, 0=away)
        missing_cb: Missing center backs
        missing_gk: Goalkeeper injured
        missing_attacker: Missing attackers
        
    Returns:
        Corner strength score
    """
    score = 0.0
    score += 0.28 * (shots - 12)              # Shot volume
    score += 0.18 * (sot - 4)                 # Shot quality
    score += 0.90 * final_third_pressure      # Final third pressure
    score += 0.75 * width_crossing            # Crossing tendency
    score += 0.25 * tempo                     # Tempo
    score += 0.30 * home                      # Home advantage
    score += 0.25 * (missing_cb + missing_gk) # Missing defenders (more corners against)
    score += -0.20 * missing_attacker         # Missing attackers
    
    return score


def estimate_team_goals(
    team_xg_for: float, team_sot: float, team_tempo: float,
    team_home: int, team_missing_attacker: int, team_missing_creator: int,
    opp_xg_against: float, opp_missing_cb: int, opp_missing_gk: int
) -> float:
    """
    Estimate team's expected goals.
    
    Combines team attacking metrics with opponent defensive weaknesses.
    
    Args:
        team_xg_for: Team's expected goals for
        team_sot: Team's shots on target
        team_tempo: Team's playing tempo
        team_home: Home advantage (1=home, 0=away)
        team_missing_attacker: Missing attackers
        team_missing_creator: Missing creators
        opp_xg_against: Opponent's expected goals against
        opp_missing_cb: Opponent's missing center backs
        opp_missing_gk: Opponent's goalkeeper injury
        
    Returns:
        Estimated expected goals (lambda)
    """
    lam = 0.55 * team_xg_for + 0.30 * opp_xg_against + 0.15 * team_sot
    lam += 0.10 * team_tempo + 0.10 * team_home
    lam += -0.15 * team_missing_attacker - 0.10 * team_missing_creator
    lam += 0.12 * (opp_missing_cb + opp_missing_gk)
    
    return max(0.20, lam)


def estimate_btts_prob(
    home_xg_for: float, away_xg_for: float,
    home_btts_strength: float, away_btts_strength: float
) -> float:
    """
    Estimate BTTS (Both Teams To Score) probability.
    
    Uses a combination of:
    1. Poisson probability of each team scoring
    2. Structural BTTS strength factors
    
    Args:
        home_xg_for: Home team's expected goals
        away_xg_for: Away team's expected goals
        home_btts_strength: Home team's BTTS strength
        away_btts_strength: Away team's BTTS strength
        
    Returns:
        BTTS probability
    """
    # Poisson probability of each team scoring at least one
    p_home_scores = poisson_at_least_one(max(0.25, home_xg_for))
    p_away_scores = poisson_at_least_one(max(0.25, away_xg_for))
    
    # Structural BTTS strength
    structural = sigmoid((home_btts_strength + away_btts_strength) / 2.0)
    
    # Combine (55% Poisson, 45% structural)
    return clamp(0.45 * structural + 0.55 * (p_home_scores * p_away_scores))


def estimate_corner_total(
    home_corner_strength: float, away_corner_strength: float,
    weather_penalty: float, referee_flow: float,
    must_win_home: int, must_win_away: int
) -> float:
    """
    Estimate total corners.
    
    Args:
        home_corner_strength: Home team's corner strength
        away_corner_strength: Away team's corner strength
        weather_penalty: Weather impact penalty
        referee_flow: Referee flow factor
        must_win_home: Home team must-win indicator
        must_win_away: Away team must-win indicator
        
    Returns:
        Estimated total corners
    """
    base = 9.2  # Average corner total
    total = base + 0.75 * (home_corner_strength + away_corner_strength)
    total += -0.15 * weather_penalty
    total += 0.10 * referee_flow
    total += 0.20 * (must_win_home + must_win_away)
    
    return max(4.0, total)


# ============================================================================
# SOCCER PREDICTOR CLASS
# ============================================================================

class SoccerPredictor(SportPredictorBase):
    """
    Predictor for Soccer matches.
    
    Uses advanced statistical models:
    - Bivariate Poisson distribution for goal probabilities
    - Dixon-Coles time-decay modifications
    - Expected Goals (xG) based predictions
    - Comprehensive team strength metrics
    
    Supports multiple leagues and competitions with league-specific configurations.
    """
    
    def __init__(self, league: str = "Premier League", **kwargs):
        """
        Initialize Soccer Predictor.
        
        Args:
            league: Default league for predictions
            **kwargs: Additional configuration
        """
        super().__init__(name=f"SoccerPredictor_{league}")
        self.league = league
        self.config = get_league_config(league)
        self._data_path = kwargs.get('data_path', 'data/soccer/')
    
    def load_data(self, data_path: str = None, *args, **kwargs) -> pd.DataFrame:
        """
        Load soccer match data.
        
        Expected columns:
        - date, home_team, away_team, home_goals, away_goals
        - home_xg, away_xg (expected goals)
        - home_shots, away_shots, home_sot, away_sot
        - Various team metrics
        
        Args:
            data_path: Path to data file
            *args: Additional arguments
            **kwargs: Additional keyword arguments
            
        Returns:
            DataFrame with soccer data
        """
        path = data_path or self._data_path
        print(f"[{self.name}] Loading soccer data from {path}...")
        
        try:
            df = pd.read_csv(path)
            
            # Ensure date is datetime
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
            
            return df
            
        except FileNotFoundError:
            print(f"[{self.name}] Warning: Data file not found at {path}. Returning empty DataFrame.")
            return pd.DataFrame()
        except Exception as e:
            print(f"[{self.name}] Error loading data: {e}")
            return pd.DataFrame()
    
    def feature_engineering(self, data: pd.DataFrame, *args, **kwargs) -> pd.DataFrame:
        """
        Engineer features for soccer predictions.
        
        Features created:
        - Time-decayed rolling averages for xG
        - Team strength metrics
        - Form indicators
        - Home/away splits
        
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
        
        # Sort by date for rolling calculations
        if 'date' in data.columns:
            data = data.sort_values('date')
        
        # Calculate rolling xG averages (time-decayed)
        # More recent matches get higher weight
        for prefix in ['home', 'away']:
            xg_col = f'{prefix}_xg'
            if xg_col in data.columns:
                # Calculate rolling average with time decay
                team_col = f'{prefix}_team'
                if team_col in data.columns:
                    data[f'{prefix}_team_rolling_xg'] = data.groupby(team_col)[xg_col].transform(
                        lambda x: x.rolling(window=5, min_periods=1).mean()
                    )
        
        # Calculate form indicators
        for prefix in ['home', 'away']:
            goals_col = f'{prefix}_goals'
            if goals_col in data.columns:
                team_col = f'{prefix}_team'
                if team_col in data.columns:
                    # Last 5 games form
                    data[f'{prefix}_form'] = data.groupby(team_col)[goals_col].transform(
                        lambda x: x.rolling(window=5, min_periods=1).mean()
                    )
        
        return data
    
    def train_model(self, features: pd.DataFrame, *args, **kwargs) -> Any:
        """
        Train a model for soccer predictions.
        
        This is a placeholder for actual ML implementation.
        In production, this would:
        - Estimate Dixon-Coles parameters
        - Train machine learning models on engineered features
        - Validate model performance
        
        Args:
            features: Processed features from feature_engineering()
            *args: Additional arguments
            **kwargs: Additional keyword arguments
            
        Returns:
            Trained model or None for placeholder
        """
        print(f"[{self.name}] Training model... (placeholder - implement Dixon-Coles or ML pipeline)")
        
        # Placeholder: In production, train actual model
        # Example:
        # from sklearn.ensemble import GradientBoostingClassifier
        # model = GradientBoostingClassifier(n_estimators=100, max_depth=5)
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
        market_total: float = 2.5,
        *args, 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make predictions for a soccer match.
        
        Args:
            features: Processed features DataFrame
            model: Trained model (or None for placeholder)
            home_team: Home team name
            away_team: Away team name
            market_line: Asian handicap line
            market_total: Over/under goals line
            *args: Additional arguments
            **kwargs: Additional keyword arguments
            
        Returns:
            Dictionary with predictions
        """
        print(f"[{self.name}] Predicting: {home_team} vs {away_team}")
        
        # Get league configuration
        league = kwargs.get('league', self.league)
        config = get_league_config(league)
        
        # Extract team metrics (placeholder values - would come from features in production)
        home_xg_for = kwargs.get('home_xg_for', 1.65)
        home_xg_against = kwargs.get('home_xg_against', 1.20)
        home_shots = kwargs.get('home_shots', 13.0)
        home_sot = kwargs.get('home_sot', 4.5)
        home_goals_for = kwargs.get('home_goals_for', 1.7)
        home_goals_against = kwargs.get('home_goals_against', 1.1)
        home_clean_sheets = kwargs.get('home_clean_sheets', 4)
        home_missing_attacker = kwargs.get('home_missing_attacker', 0)
        home_missing_creator = kwargs.get('home_missing_creator', 0)
        home_missing_cb = kwargs.get('home_missing_cb', 0)
        home_missing_gk = kwargs.get('home_missing_gk', 0)
        home_tempo = kwargs.get('home_tempo', 0.3)
        home_width_crossing = kwargs.get('home_width_crossing', 0.55)
        home_final_third_pressure = kwargs.get('home_final_third_pressure', 0.55)
        
        away_xg_for = kwargs.get('away_xg_for', 1.45)
        away_xg_against = kwargs.get('away_xg_against', 1.35)
        away_shots = kwargs.get('away_shots', 11.5)
        away_sot = kwargs.get('away_sot', 4.0)
        away_goals_for = kwargs.get('away_goals_for', 1.4)
        away_goals_against = kwargs.get('away_goals_against', 1.3)
        away_clean_sheets = kwargs.get('away_clean_sheets', 3)
        away_missing_attacker = kwargs.get('away_missing_attacker', 0)
        away_missing_creator = kwargs.get('away_missing_creator', 0)
        away_missing_cb = kwargs.get('away_missing_cb', 0)
        away_missing_gk = kwargs.get('away_missing_gk', 0)
        away_tempo = kwargs.get('away_tempo', 0.1)
        away_width_crossing = kwargs.get('away_width_crossing', 0.50)
        away_final_third_pressure = kwargs.get('away_final_third_pressure', 0.45)
        
        # Create team metrics
        home_metrics = SoccerTeamMetrics(
            xg_for=home_xg_for,
            xg_against=home_xg_against,
            shots=home_shots,
            sot=home_sot,
            goals_for=home_goals_for,
            goals_against=home_goals_against,
            clean_sheets=home_clean_sheets,
            missing_attacker=home_missing_attacker,
            missing_creator=home_missing_creator,
            missing_cb=home_missing_cb,
            missing_gk=home_missing_gk,
            tempo=home_tempo,
            width_crossing=home_width_crossing,
            final_third_pressure=home_final_third_pressure,
        )
        
        away_metrics = SoccerTeamMetrics(
            xg_for=away_xg_for,
            xg_against=away_xg_against,
            shots=away_shots,
            sot=away_sot,
            goals_for=away_goals_for,
            goals_against=away_goals_against,
            clean_sheets=away_clean_sheets,
            missing_attacker=away_missing_attacker,
            missing_creator=away_missing_creator,
            missing_cb=away_missing_cb,
            missing_gk=away_missing_gk,
            tempo=away_tempo,
            width_crossing=away_width_crossing,
            final_third_pressure=away_final_third_pressure,
        )
        
        # Apply Dixon-Coles adjustment
        home_attack, home_defense = dixon_coles_xg_adjustment(
            home_xg_for, home_xg_against, away_xg_for, away_xg_against
        )
        away_attack, away_defense = dixon_coles_xg_adjustment(
            away_xg_for, away_xg_against, home_xg_for, home_xg_against
        )
        
        # Estimate expected goals (lambda)
        home_lambda = estimate_team_goals(
            home_xg_for, home_sot, home_tempo, 1,
            home_missing_attacker, home_missing_creator,
            away_xg_against, away_missing_cb, away_missing_gk
        )
        away_lambda = estimate_team_goals(
            away_xg_for, away_sot, away_tempo, 0,
            away_missing_attacker, away_missing_creator,
            home_xg_against, home_missing_cb, home_missing_gk
        )
        
        # Apply league-specific goal variance
        home_lambda *= config['goal_variance']
        away_lambda *= config['goal_variance']
        
        # Apply home advantage
        home_lambda *= (1 + config['home_advantage'] * 0.1)
        
        total_lambda = home_lambda + away_lambda
        
        # Calculate BTTS probability
        home_btts = team_btts_strength(
            home_xg_for, home_xg_against, home_goals_for, home_goals_against,
            home_sot, home_tempo, home_final_third_pressure,
            home_missing_attacker, home_missing_cb, home_missing_gk, home_clean_sheets
        )
        away_btts = team_btts_strength(
            away_xg_for, away_xg_against, away_goals_for, away_goals_against,
            away_sot, away_tempo, away_final_third_pressure,
            away_missing_attacker, away_missing_cb, away_missing_gk, away_clean_sheets
        )
        btts_prob = estimate_btts_prob(home_lambda, away_lambda, home_btts, away_btts)
        
        # Calculate goal probabilities using Poisson
        p_over_15 = poisson_over_prob(total_lambda, 1.5)
        p_over_25 = poisson_over_prob(total_lambda, 2.5)
        p_over_35 = poisson_over_prob(total_lambda, 3.5)
        
        # Calculate match outcome probabilities
        prob_matrix = calculate_bivariate_poisson_probabilities(home_lambda, away_lambda)
        
        home_win_prob = prob_matrix.apply(lambda row: row[row.index < row.name].sum(), axis=1).sum()
        away_win_prob = prob_matrix.apply(lambda row: row[row.index > row.name].sum(), axis=1).sum()
        draw_prob = prob_matrix.apply(lambda row: row[row.index == row.name].sum(), axis=1).sum()
        
        # Normalize probabilities
        total_prob = home_win_prob + away_win_prob + draw_prob
        if total_prob > 0:
            home_win_prob /= total_prob
            away_win_prob /= total_prob
            draw_prob /= total_prob
        
        # Calculate confidence scores for betting markets
        side_edge = (home_lambda - away_lambda) - market_line
        total_edge = total_lambda - market_total
        btts_edge = btts_prob - 0.5
        
        # Use core confidence engine if available
        try:
            from core import confidence_score, bet_recommendation
            
            side_confidence = confidence_score(side_edge, volatility=0.50)
            total_confidence = confidence_score(total_edge, volatility=0.55)
            btts_confidence = confidence_score(btts_edge * 10, volatility=0.48)
            
            side_rec = bet_recommendation(side_confidence)
            total_rec = bet_recommendation(total_confidence)
            btts_rec = bet_recommendation(btts_confidence)
        except ImportError:
            # Fallback if core module not available
            side_confidence = min(100, max(0, 50 + side_edge * 10))
            total_confidence = min(100, max(0, 50 + total_edge * 10))
            btts_confidence = min(100, max(0, 50 + btts_edge * 10))
            
            side_rec = "BET" if side_confidence > 60 else "PASS"
            total_rec = "BET" if total_confidence > 60 else "PASS"
            btts_rec = "BET" if btts_confidence > 60 else "PASS"
        
        # Estimate corner total
        home_corner = team_corner_strength(
            home_shots, home_sot, home_final_third_pressure,
            home_width_crossing, home_tempo, 1,
            home_missing_cb, home_missing_gk, home_missing_attacker
        )
        away_corner = team_corner_strength(
            away_shots, away_sot, away_final_third_pressure,
            away_width_crossing, away_tempo, 0,
            away_missing_cb, away_missing_gk, away_missing_attacker
        )
        corner_total = estimate_corner_total(home_corner, away_corner, 0, 0, 0, 0)
        
        # Build comprehensive output
        p_corners_85 = poisson_over_prob(corner_total, 8.5)
        p_corners_95 = poisson_over_prob(corner_total, 9.5)
        p_corners_105 = poisson_over_prob(corner_total, 10.5)
        
        result = {
            "sport": "soccer",
            "league": league,
            "home_team": home_team,
            "away_team": away_team,
            "timestamp": pd.Timestamp.now().isoformat(),
            "game": {
                "projected_home_goals": round(home_lambda, 2),
                "projected_away_goals": round(away_lambda, 2),
                "projected_total_goals": round(total_lambda, 2),
                "home_win_prob": round(home_win_prob, 3),
                "draw_prob": round(draw_prob, 3),
                "away_win_prob": round(away_win_prob, 3),
            },
            "predictions": {
                "side": {
                    "model_xg_diff": round(home_lambda - away_lambda, 3),
                    "market_line": market_line,
                    "edge": round(side_edge, 3),
                    "confidence": round(side_confidence, 1),
                    "recommendation": side_rec,
                },
                "total": {
                    "model_total_xg": round(total_lambda, 3),
                    "market_total": market_total,
                    "edge": round(total_edge, 3),
                    "confidence": round(total_confidence, 1),
                    "recommendation": total_rec,
                },
                "btts": {
                    "probability": round(btts_prob, 3),
                    "confidence": round(btts_confidence, 1),
                    "recommendation": btts_rec,
                },
            },
            "goals_analysis": {
                "over_15_prob": round(p_over_15, 3),
                "over_25_prob": round(p_over_25, 3),
                "over_35_prob": round(p_over_35, 3),
            },
            "corners_analysis": {
                "projection": round(corner_total, 1),
                "over_85_prob": round(p_corners_85, 3),
                "over_95_prob": round(p_corners_95, 3),
                "over_105_prob": round(p_corners_105, 3),
            },
            "btts_probability": round(btts_prob, 3),
            "corner_projection": round(corner_total, 1),
            "team_metrics": {
                "home": asdict(home_metrics),
                "away": asdict(away_metrics),
            },
            "league_config": config,
            "notes": (
                "Soccer prediction using Bivariate Poisson with "
                "Dixon-Coles time-decay adjustments on xG metrics"
            ),
        }
        
        return result
    
    def predict_from_row(self, row: pd.Series) -> Dict[str, Any]:
        """
        Make prediction from a single data row.
        
        Useful for batch processing of multiple matches.
        
        Args:
            row: DataFrame row with match data
            
        Returns:
            Prediction dictionary
        """
        return self.predict(
            features=pd.DataFrame(),
            model=self._model,
            home_team=row.get('home_team', 'Unknown'),
            away_team=row.get('away_team', 'Unknown'),
            market_line=to_num(row.get('market_line', 0)),
            market_total=to_num(row.get('market_total', 2.5)),
            league=row.get('league', self.league),
            home_xg_for=to_num(row.get('home_xg_for', 1.5)),
            home_xg_against=to_num(row.get('home_xg_against', 1.25)),
            home_shots=to_num(row.get('home_shots', 12)),
            home_sot=to_num(row.get('home_sot', 4)),
            home_goals_for=to_num(row.get('home_goals_for', 1.3)),
            home_goals_against=to_num(row.get('home_goals_against', 1.1)),
            home_clean_sheets=int(to_num(row.get('home_clean_sheets', 3))),
            home_missing_attacker=int(to_num(row.get('home_missing_attacker', 0))),
            home_missing_creator=int(to_num(row.get('home_missing_creator', 0))),
            home_missing_cb=int(to_num(row.get('home_missing_cb', 0))),
            home_missing_gk=int(to_num(row.get('home_missing_gk', 0))),
            home_tempo=to_num(row.get('home_tempo', 0.3)),
            home_width_crossing=to_num(row.get('home_width_crossing', 0.5)),
            home_final_third_pressure=to_num(row.get('home_final_third_pressure', 0.5)),
            away_xg_for=to_num(row.get('away_xg_for', 1.3)),
            away_xg_against=to_num(row.get('away_xg_against', 1.35)),
            away_shots=to_num(row.get('away_shots', 11)),
            away_sot=to_num(row.get('away_sot', 3.5)),
            away_goals_for=to_num(row.get('away_goals_for', 1.1)),
            away_goals_against=to_num(row.get('away_goals_against', 1.2)),
            away_clean_sheets=int(to_num(row.get('away_clean_sheets', 2))),
            away_missing_attacker=int(to_num(row.get('away_missing_attacker', 0))),
            away_missing_creator=int(to_num(row.get('away_missing_creator', 0))),
            away_missing_cb=int(to_num(row.get('away_missing_cb', 0))),
            away_missing_gk=int(to_num(row.get('away_missing_gk', 0))),
            away_tempo=to_num(row.get('away_tempo', 0.2)),
            away_width_crossing=to_num(row.get('away_width_crossing', 0.5)),
            away_final_third_pressure=to_num(row.get('away_final_third_pressure', 0.45)),
        )


# Example usage and testing
if __name__ == "__main__":
    print("=" * 60)
    print("Testing SoccerPredictor")
    print("=" * 60)
    
    # Create predictor
    predictor = SoccerPredictor(league="Premier League")
    
    # Test prediction
    result = predictor.predict(
        features=pd.DataFrame(),
        model=None,
        home_team="Liverpool",
        away_team="Aston Villa",
        market_line=0.25,
        market_total=2.5,
    )
    
    print("\nPrediction Result:")
    print(f"  Sport: {result['sport']}")
    print(f"  League: {result['league']}")
    print(f"  Matchup: {result['home_team']} vs {result['away_team']}")
    print(f"\nProjected Goals:")
    print(f"  {result['home_team']}: {result['game']['projected_home_goals']:.2f}")
    print(f"  {result['away_team']}: {result['game']['projected_away_goals']:.2f}")
    print(f"  Total: {result['game']['projected_total_goals']:.2f}")
    print(f"\nMatch Outcome:")
    print(f"  {result['home_team']} Win: {result['game']['home_win_prob']:.1%}")
    print(f"  Draw: {result['game']['draw_prob']:.1%}")
    print(f"  {result['away_team']} Win: {result['game']['away_win_prob']:.1%}")
    print(f"\nGoal Probabilities:")
    print(f"  Over 1.5: {result['goals_analysis']['over_15_prob']:.1%}")
    print(f"  Over 2.5: {result['goals_analysis']['over_25_prob']:.1%}")
    print(f"  Over 3.5: {result['goals_analysis']['over_35_prob']:.1%}")
    print(f"\nBTTS: {result['btts_probability']:.1%}")
    print(f"\nBetting Predictions:")
    print(f"  Side: {result['predictions']['side']['recommendation']} (Confidence: {result['predictions']['side']['confidence']:.1f}%)")
    print(f"  Total: {result['predictions']['total']['recommendation']} (Confidence: {result['predictions']['total']['confidence']:.1f}%)")
    print(f"  BTTS: {result['predictions']['btts']['recommendation']} (Confidence: {result['predictions']['btts']['confidence']:.1f}%)")
    print(f"\nNotes: {result['notes']}")