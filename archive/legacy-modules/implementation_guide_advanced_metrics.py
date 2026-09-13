"""
Implementation Guide: Adding Advanced Metrics to Soccer Predictor
==================================================================

This module shows code examples for adding the suggested enhancements.
"""

# ============================================================================
# 1. TEAM STRENGTH INDICATORS
# ============================================================================

import requests
from typing import Dict, Any
from datetime import datetime, timedelta
import json

class TeamStrengthAnalyzer:
    """Adds FIFA/ELO ratings and recent form analysis."""
    
    def __init__(self):
        self.fifa_cache = {}
        self.form_cache = {}
    
    def get_team_elo(self, team_name: str) -> float:
        """
        Get ELO rating for team.
        
        Sources:
        - eloratings.net (official)
        - worldfootballelo.net (programmatic)
        """
        # Example using a JSON endpoint
        try:
            response = requests.get(
                f"https://api.worldfootballelo.com/teams/{team_name}",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("elo", 1500)  # Default Elo if not found
        except:
            pass
        
        # Fallback: Manual mapping
        elo_ratings = {
            "netherlands": 1759,
            "sweden": 1657,
            "argentina": 1793,
            "brazil": 1808,
        }
        return elo_ratings.get(team_name.lower(), 1500)
    
    def get_recent_form(self, team_name: str, last_n_matches: int = 5) -> Dict[str, Any]:
        """
        Get team's recent form statistics.
        
        Returns:
        - Goals scored/conceded average
        - Win rate
        - Points per game
        - Trend (improving/declining)
        """
        # In production, fetch from ESPN, Transfermarkt, or official API
        # For now, return placeholder
        
        recent_matches = [
            {"opponent": "Team A", "goals_for": 2, "goals_against": 1, "result": "W"},
            {"opponent": "Team B", "goals_for": 1, "goals_against": 1, "result": "D"},
            {"opponent": "Team C", "goals_for": 3, "goals_against": 0, "result": "W"},
            {"opponent": "Team D", "goals_for": 1, "goals_against": 2, "result": "L"},
            {"opponent": "Team E", "goals_for": 2, "goals_against": 1, "result": "W"},
        ]
        
        goals_for = sum(m["goals_for"] for m in recent_matches) / len(recent_matches)
        goals_against = sum(m["goals_against"] for m in recent_matches) / len(recent_matches)
        wins = sum(1 for m in recent_matches if m["result"] == "W")
        
        return {
            "goals_per_game": goals_for,
            "goals_conceded_per_game": goals_against,
            "win_percentage": wins / len(recent_matches),
            "trending": "up" if recent_matches[-1]["result"] in ["W", "D"] else "down",
        }
    
    def adjust_prediction(self, base_goals: float, team_strength: float) -> float:
        """Adjust goal projection based on team strength."""
        # Higher ELO = higher scoring
        elo_adjustment = (team_strength - 1500) / 1500 * 0.5
        return base_goals * (1 + elo_adjustment)


# ============================================================================
# 2. ADVANCED STATISTICAL MODELS
# ============================================================================

import numpy as np
from scipy.stats import poisson

class AdvancedGoalPredictor:
    """Generate predictions with confidence intervals."""
    
    @staticmethod
    def predict_with_intervals(
        mean_goals: float,
        confidence_level: float = 0.95
    ) -> Dict[str, Any]:
        """
        Generate goal prediction with confidence intervals using Poisson distribution.
        
        Args:
            mean_goals: Expected goals (lambda parameter)
            confidence_level: 0.90, 0.95, or 0.99
        
        Returns:
            Point estimate and confidence bands
        """
        
        # Poisson distribution parameters
        lambda_param = mean_goals
        
        # Calculate percentiles for confidence interval
        if confidence_level == 0.95:
            lower_pct, upper_pct = 2.5, 97.5
        elif confidence_level == 0.90:
            lower_pct, upper_pct = 5, 95
        else:  # 0.99
            lower_pct, upper_pct = 0.5, 99.5
        
        # Find bounds (inverse CDF)
        lower_bound = poisson.ppf(lower_pct/100, lambda_param)
        upper_bound = poisson.ppf(upper_pct/100, lambda_param)
        
        return {
            "point_estimate": mean_goals,
            f"confidence_{int(confidence_level*100)}_lower": float(lower_bound),
            f"confidence_{int(confidence_level*100)}_upper": float(upper_bound),
            "probability_over_2_5": 1 - poisson.cdf(2, lambda_param),
            "probability_over_3_5": 1 - poisson.cdf(3, lambda_param),
        }
    
    @staticmethod
    def dixon_coles_weighting(match_days_ago: int, decay_factor: float = 0.3) -> float:
        """
        Apply Dixon-Coles time decay to weight recent matches higher.
        
        Recent matches get more weight in calculation.
        decay_factor: 0.3 = moderate recency bias, 0.5 = high recency bias
        """
        return np.exp(-decay_factor * match_days_ago)


# ============================================================================
# 3. CONTEXTUAL FACTORS
# ============================================================================

from geopy.distance import geodesic
import json

class ContextualFactorAnalyzer:
    """Add weather, travel, venue, and other contextual factors."""
    
    # Stadium coordinates (example)
    STADIUMS = {
        "amsterdam": (52.3140, 4.9421),
        "stockholm": (59.2994, 18.0322),
    }
    
    def get_weather_data(self, city: str, match_date: datetime) -> Dict[str, Any]:
        """
        Fetch weather data for match location.
        
        Source: Open-Meteo API (free, no key required)
        """
        try:
            # Open-Meteo API example
            response = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": 52.3140,  # Example: Amsterdam
                    "longitude": 4.9421,
                    "daily": "temperature_2m_max,precipitation_sum,windspeed_10m_max",
                    "temperature_unit": "celsius"
                },
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "temperature": data["daily"]["temperature_2m_max"][0],
                    "precipitation": data["daily"]["precipitation_sum"][0],
                    "wind_speed": data["daily"]["windspeed_10m_max"][0],
                    "weather_impact": "moderate" if data["daily"]["precipitation_sum"][0] > 5 else "minimal"
                }
        except:
            pass
        
        return {
            "temperature": 15,
            "precipitation": 0,
            "wind_speed": 10,
            "weather_impact": "unknown"
        }
    
    def calculate_travel_fatigue(self, home_city: str, away_city: str) -> float:
        """
        Calculate fatigue from travel distance.
        
        Longer distances = more fatigue = potentially fewer goals
        """
        home_coords = self.STADIUMS.get(home_city.lower())
        away_coords = self.STADIUMS.get(away_city.lower())
        
        if not home_coords or not away_coords:
            return 0.0
        
        distance_km = geodesic(home_coords, away_coords).kilometers
        
        # Fatigue factor: -0.1 per 500km traveled
        fatigue_adjustment = -0.1 * (distance_km / 500)
        
        return max(-0.5, fatigue_adjustment)  # Cap at -0.5 goals


# ============================================================================
# 4. PLAYER-LEVEL METRICS
# ============================================================================

class PlayerAnalyzer:
    """Track player availability, form, and xG contribution."""
    
    def __init__(self):
        self.injury_data = {}
    
    def get_player_injuries(self, team_name: str) -> Dict[str, Any]:
        """
        Fetch injury data from API.
        
        Free sources:
        - ESPN player status
        - Transfermarkt injury list
        - Team official websites
        """
        # Placeholder for injury data structure
        return {
            "out": [
                {"name": "Key Striker", "position": "ST", "impact": "high", "days_out": 7},
                {"name": "Backup RB", "position": "RB", "impact": "low", "days_out": 14},
            ],
            "doubtful": [
                {"name": "Star CB", "position": "CB", "impact": "high", "availability": 0.6},
            ]
        }
    
    def adjust_for_key_injuries(self, base_goals: float, injuries: Dict[str, Any]) -> float:
        """Adjust goal projection based on injuries."""
        
        adjustment = 0
        
        for injured_player in injuries.get("out", []):
            if injured_player["position"] in ["ST", "LW", "RW"]:  # Attack
                adjustment -= 0.3 * injured_player["impact"] / 10
            elif injured_player["position"] in ["CB", "LB", "RB"]:  # Defense
                adjustment += 0.2 * injured_player["impact"] / 10
        
        for doubtful_player in injuries.get("doubtful", []):
            availability = doubtful_player.get("availability", 0.5)
            if doubtful_player["position"] in ["ST", "LW", "RW"]:
                adjustment -= 0.3 * (1 - availability)
        
        return max(0.5, base_goals + adjustment)  # Floor at 0.5 goals


# ============================================================================
# 5. MARKET MICROSTRUCTURE
# ============================================================================

class BettingMarketAnalyzer:
    """Detect sharp money and line movement."""
    
    def __init__(self):
        self.line_history = {}
    
    def detect_sharp_money(
        self,
        opening_odds: Dict[str, float],
        current_odds: Dict[str, float],
        volume: int
    ) -> str:
        """
        Detect if sharp money is affecting the line.
        
        Sharp money = large volume at quick movement
        """
        
        if volume > 1000:  # High volume threshold
            line_movement = current_odds.get("over", 2.5) - opening_odds.get("over", 2.5)
            
            if abs(line_movement) > 0.15:
                if line_movement < 0:
                    return "SHARP MONEY ON UNDER"
                else:
                    return "SHARP MONEY ON OVER"
        
        return "SQUARE MONEY" if volume < 500 else "MIXED BETTING"
    
    def track_line_movement(self, match_id: str, odds: Dict[str, float], timestamp: datetime):
        """Track line changes over time."""
        if match_id not in self.line_history:
            self.line_history[match_id] = []
        
        self.line_history[match_id].append({
            "timestamp": timestamp,
            "odds": odds
        })


# ============================================================================
# COMPLETE EXAMPLE: Enhanced Soccer Prediction
# ============================================================================

def predict_match_with_all_factors(
    home_team: str,
    away_team: str,
    league: str,
    match_city: str,
    match_date: datetime
) -> Dict[str, Any]:
    """
    Complete prediction incorporating all factors.
    
    Integration example:
    """
    
    # 1. Get base prediction
    from models.soccer_predictor import SoccerPredictor
    predictor = SoccerPredictor(league=league)
    base_result = predictor.predict(
        features=None,
        model=None,
        home_team=home_team,
        away_team=away_team,
    )
    
    base_home_goals = base_result["game"]["projected_home_goals"]
    base_away_goals = base_result["game"]["projected_away_goals"]
    
    # 2. Add team strength
    strength_analyzer = TeamStrengthAnalyzer()
    home_elo = strength_analyzer.get_team_elo(home_team)
    away_elo = strength_analyzer.get_team_elo(away_team)
    
    adjusted_home_goals = strength_analyzer.adjust_prediction(base_home_goals, home_elo)
    adjusted_away_goals = strength_analyzer.adjust_prediction(base_away_goals, away_elo)
    
    # 3. Add weather
    context = ContextualFactorAnalyzer()
    weather = context.get_weather_data(match_city, match_date)
    
    if weather["weather_impact"] == "moderate":
        adjusted_home_goals *= 0.92  # Rainy weather reduces scoring
        adjusted_away_goals *= 0.92
    
    # 4. Add travel fatigue
    travel_adjustment = context.calculate_travel_fatigue(
        home_team.split("_")[0],  # Extract city
        away_team.split("_")[0]
    )
    adjusted_away_goals += travel_adjustment  # Away team gets penalized
    
    # 5. Add injuries
    player_analyzer = PlayerAnalyzer()
    home_injuries = player_analyzer.get_player_injuries(home_team)
    away_injuries = player_analyzer.get_player_injuries(away_team)
    
    adjusted_home_goals = player_analyzer.adjust_for_key_injuries(
        adjusted_home_goals, home_injuries
    )
    adjusted_away_goals = player_analyzer.adjust_for_key_injuries(
        adjusted_away_goals, away_injuries
    )
    
    # 6. Generate predictions with confidence intervals
    advanced_model = AdvancedGoalPredictor()
    home_prediction = advanced_model.predict_with_intervals(adjusted_home_goals)
    away_prediction = advanced_model.predict_with_intervals(adjusted_away_goals)
    
    return {
        "base_prediction": base_result,
        "home_team": {
            "goals": home_prediction,
            "elo": home_elo,
            "injuries": home_injuries,
        },
        "away_team": {
            "goals": away_prediction,
            "elo": away_elo,
            "injuries": away_injuries,
        },
        "weather": weather,
        "total_goals": {
            "point_estimate": adjusted_home_goals + adjusted_away_goals,
            "over_2_5_prob": advanced_model.predict_with_intervals(
                adjusted_home_goals + adjusted_away_goals
            ).get("probability_over_2_5"),
        }
    }


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    # Example: Enhanced prediction for Netherlands vs Sweden
    result = predict_match_with_all_factors(
        home_team="Netherlands",
        away_team="Sweden",
        league="World Cup",
        match_city="Amsterdam",
        match_date=datetime.now() + timedelta(days=2)
    )
    
    print("Enhanced Prediction Result:")
    print(json.dumps({
        "home_goals": result["home_team"]["goals"]["point_estimate"],
        "away_goals": result["away_team"]["goals"]["point_estimate"],
        "total": result["total_goals"]["point_estimate"],
        "over_2_5_probability": result["total_goals"]["over_2_5_prob"],
        "elo_ratings": {
            "home": result["home_team"]["elo"],
            "away": result["away_team"]["elo"]
        }
    }, indent=2))
