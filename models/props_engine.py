#!/usr/bin/env python
"""
Unified Props Engine for MultiSportPredict
===========================================
Generates player prop recommendations for all sports.

Features:
- Automatic prop generation for any game
- Integration with roster database
- Park/venue factor adjustments
- Weather adjustments (outdoor sports)
- Confidence scoring for each prop

Supported Prop Types:
- MLB: Ks, HRs, Hits, RBIs, Total Bases, Walks
- KBO: Same as MLB
- Basketball: Points, Rebounds, Assists, Threes
- Soccer: Shots, Goals, Assists, Cards
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import math

# Import roster system
try:
    from data.rosters import get_roster, get_starting_pitchers, Player
    ROSTER_AVAILABLE = True
except ImportError:
    ROSTER_AVAILABLE = False
    Player = None

# Import baseball predictor for prop methods
try:
    from models.baseball_predictor import BaseballPredictor
    BASEBALL_AVAILABLE = True
except ImportError:
    BASEBALL_AVAILABLE = False


@dataclass
class PropRecommendation:
    """Individual prop recommendation"""
    player_name: str
    team: str
    prop_type: str  # K, HR, Hits, Points, etc.
    line: float
    projection: float
    edge: float
    confidence: float  # 0-100
    recommendation: str  # Over, Under, Pass
    lean: str  # Over, Under, No Lean
    factors: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.factors is None:
            self.factors = {}


class PropsEngine:
    """
    Centralized props generation engine for all sports.
    
    Usage:
        engine = PropsEngine()
        props = engine.generate_props("baseball", "Giants", "Cubs")
    """
    
    def __init__(self):
        self.baseball_predictor = BaseballPredictor() if BASEBALL_AVAILABLE else None
        
        # Park factors (would be loaded from database)
        self.park_factors = {
            "SF": {"hr": 0.92, "runs": 0.95, "k": 1.02},  # Oracle Park
            "CHC": {"hr": 1.05, "runs": 1.02, "k": 0.98},  # Wrigley Field
            "LAD": {"hr": 0.98, "runs": 1.00, "k": 1.00},  # Dodger Stadium
            "NYY": {"hr": 1.10, "runs": 1.05, "k": 0.95},  # Yankee Stadium
            "BOS": {"hr": 1.08, "runs": 1.06, "k": 0.97},  # Fenway Park
        }
        
        # Weather factors (for outdoor sports)
        self.weather_adjustments = {
            "temp_factor": 0.005,  # Per degree above/below 70
            "wind_factor": 0.03,   # Per mph of wind
        }
    
    def generate_props(self, sport: str, home_team: str, away_team: str, 
                       league: str = None, **kwargs) -> Dict[str, Any]:
        """
        Generate all player props for a game.
        
        Args:
            sport: Sport type (baseball, basketball, soccer)
            home_team: Home team name
            away_team: Away team name
            league: League type (MLB, KBO, etc.)
            **kwargs: Additional parameters (weather, park factors, etc.)
            
        Returns:
            Dictionary with all prop recommendations
        """
        sport = sport.lower()
        
        if sport in ['baseball', 'mlb', 'kbo']:
            return self._generate_baseball_props(home_team, away_team, league or 'MLB', **kwargs)
        elif sport == 'basketball':
            return self._generate_basketball_props(home_team, away_team, **kwargs)
        elif sport == 'soccer':
            return self._generate_soccer_props(home_team, away_team, **kwargs)
        else:
            return {"error": f"Unsupported sport: {sport}"}
    
    def _generate_baseball_props(self, home_team: str, away_team: str, 
                                  league: str, **kwargs) -> Dict[str, Any]:
        """Generate baseball player props"""
        
        if not BASEBALL_AVAILABLE:
            return {"error": "Baseball predictor not available"}
        
        # Get rosters
        home_roster = []
        away_roster = []
        if ROSTER_AVAILABLE:
            home_roster = get_roster('mlb' if league == 'MLB' else 'kbo', home_team)
            away_roster = get_roster('mlb' if league == 'MLB' else 'kbo', away_team)
        
        # Get starting pitchers
        home_pitcher = None
        away_pitcher = None
        if ROSTER_AVAILABLE:
            pitchers = get_starting_pitchers('mlb' if league == 'MLB' else 'kbo', home_team, away_team)
            home_pitcher = pitchers.get('home')
            away_pitcher = pitchers.get('away')
        
        # Get park factor
        park_factor = self._get_park_factor(home_team, league)
        
        # Get weather (if outdoor)
        weather = kwargs.get('weather', {"temp": 72, "wind_speed": 5, "wind_direction": 0})
        
        props = {
            "sport": "baseball",
            "league": league,
            "matchup": f"{home_team} vs {away_team}",
            "park_factor": park_factor,
            "pitcher_props": [],
            "hitter_props": [],
            "top_recommendations": []
        }
        
        # Generate pitcher props
        if home_pitcher:
            k_prop = self._project_pitcher_ks(home_pitcher, away_roster, park_factor, weather)
            props["pitcher_props"].append(k_prop)
        
        if away_pitcher:
            k_prop = self._project_pitcher_ks(away_pitcher, home_roster, park_factor, weather)
            props["pitcher_props"].append(k_prop)
        
        # Generate hitter props for key players
        for player in home_roster + away_roster:
            if player.position != 'P':  # Skip pitchers as hitters (unless DH league)
                hr_prop = self._project_hitter_hr(player, away_pitcher if player.team == home_team else home_pitcher, 
                                                   park_factor, weather)
                if hr_prop:
                    props["hitter_props"].append(hr_prop)
        
        # Find top recommendations
        all_props = props["pitcher_props"] + props["hitter_props"]
        top_props = sorted(all_props, key=lambda x: abs(x.get('edge', 0)), reverse=True)
        props["top_recommendations"] = [asdict(p) if hasattr(p, '__dataclass_fields__') else p 
                                        for p in top_props[:5]]
        
        return props
    
    def _project_pitcher_ks(self, pitcher: Player, opponent_roster: List[Player],
                            park_factor: Dict, weather: Dict) -> Dict:
        """Project pitcher strikeout props"""
        
        if not pitcher or pitcher.position != 'P':
            return None
        
        # Get opponent strikeout rate
        opp_k_rate = 0.22  # League average
        if opponent_roster:
            opp_k_rate = sum(p.stats.get('k_rate', 0.22) for p in opponent_roster) / len(opponent_roster)
        
        # Get pitcher stats
        pitcher_k_rate = pitcher.stats.get('k_rate', 0.22)
        pitcher_k_per_9 = pitcher.stats.get('k_per_9', 7.0)
        innings_proj = 5.5  # Average start
        
        # Calculate projection
        ump_factor = 1.0  # Neutral umpire
        temp_factor = 1 + (weather.get('temp', 72) - 70) * 0.005
        proj_ks = pitcher_k_rate * opp_k_rate * ump_factor * park_factor.get('k', 1.0) * temp_factor * innings_proj * 3.0
        
        # Set line (would come from sportsbook)
        line = round(proj_ks + 0.5)  # Round to nearest half
        
        # Calculate edge and recommendation
        edge = proj_ks - line
        confidence = min(100, max(0, 50 + edge * 15))
        recommendation = "Over" if edge > 0.5 else "Under" if edge < -0.5 else "Pass"
        
        return {
            "player_name": pitcher.name,
            "team": pitcher.team,
            "prop_type": "Strikeouts",
            "line": line,
            "projection": round(proj_ks, 2),
            "edge": round(edge, 2),
            "confidence": round(confidence, 1),
            "recommendation": recommendation,
            "lean": recommendation if recommendation != "Pass" else "No Lean",
            "factors": {
                "pitcher_k_rate": pitcher_k_rate,
                "opp_k_rate": round(opp_k_rate, 3),
                "innings_proj": innings_proj,
                "park_k_factor": park_factor.get('k', 1.0),
            }
        }
    
    def _project_hitter_hr(self, hitter: Player, opposing_pitcher: Player,
                           park_factor: Dict, weather: Dict) -> Optional[Dict]:
        """Project hitter home run props"""
        
        if not hitter or not opposing_pitcher:
            return None
        
        # Get hitter stats
        hr_rate = hitter.stats.get('hr_rate', 0.03)
        barrel_rate = hitter.stats.get('barrel_rate', 0.05)
        hard_hit = hitter.stats.get('hard_hit_rate', 0.35)
        
        # Get pitcher HR allowed
        pitcher_hr9 = opposing_pitcher.stats.get('hr_per_9', 1.0)
        
        # Calculate base probability
        base = hr_rate * 0.6 + barrel_rate * 0.25 + hard_hit * 0.15
        base *= (1 + (pitcher_hr9 - 1.0) * 0.25)
        base *= park_factor.get('hr', 1.0)
        
        # Weather adjustments
        temp_adj = 1 + (weather.get('temp', 72) - 70) * 0.005
        wind_adj = 1 + weather.get('wind_speed', 0) * weather.get('wind_direction_factor', 0) * 0.03
        base *= temp_adj * wind_adj
        
        # Clamp probability
        hr_prob = max(0.01, min(base, 0.50))
        
        # HR Yes/No prop
        line = 0.5
        edge = hr_prob - 0.12  # Break-even around 12%
        confidence = min(100, max(0, 50 + edge * 200))
        recommendation = "Yes HR" if hr_prob > 0.15 else "No HR" if hr_prob < 0.08 else "Pass"
        
        return {
            "player_name": hitter.name,
            "team": hitter.team,
            "prop_type": "Home Run",
            "line": line,
            "projection": round(hr_prob, 3),
            "edge": round(edge, 3),
            "confidence": round(confidence, 1),
            "recommendation": recommendation,
            "lean": recommendation if recommendation != "Pass" else "No Lean",
            "factors": {
                "hr_rate": hr_rate,
                "barrel_rate": barrel_rate,
                "hard_hit_rate": hard_hit,
                "pitcher_hr9": pitcher_hr9,
                "park_hr_factor": park_factor.get('hr', 1.0),
            }
        }
    
    def _generate_basketball_props(self, home_team: str, away_team: str, **kwargs) -> Dict:
        """Generate basketball player props"""
        
        # Get rosters (would need basketball roster data source)
        home_roster = self._get_basketball_roster(home_team)
        away_roster = self._get_basketball_roster(away_team)
        
        # Venue factor (home court advantage)
        venue_factor = kwargs.get('venue_factor', 1.02)  # Slight home boost
        
        props = {
            "sport": "basketball",
            "matchup": f"{home_team} vs {away_team}",
            "venue_factor": venue_factor,
            "player_props": [],
            "top_recommendations": []
        }
        
        # Generate props for key players
        for player in home_roster + away_roster:
            # Points prop
            points_prop = self._project_basketball_points(player, venue_factor)
            if points_prop:
                props["player_props"].append(points_prop)
            
            # Rebounds prop (for bigs)
            if player.position in ['C', 'PF', 'SF']:
                reb_prop = self._project_basketball_rebounds(player, venue_factor)
                if reb_prop:
                    props["player_props"].append(reb_prop)
            
            # Assists prop (for guards)
            if player.position in ['PG', 'SG']:
                ast_prop = self._project_basketball_assists(player, venue_factor)
                if ast_prop:
                    props["player_props"].append(ast_prop)
        
        # Find top recommendations
        top_props = sorted(props["player_props"], key=lambda x: abs(x.get('edge', 0)), reverse=True)
        props["top_recommendations"] = top_props[:5]
        
        return props
    
    def _generate_soccer_props(self, home_team: str, away_team: str, **kwargs) -> Dict:
        """Generate soccer player props"""
        
        # Get rosters (would need soccer roster data source)
        home_roster = self._get_soccer_roster(home_team)
        away_roster = self._get_soccer_roster(away_team)
        
        # Pitch/venue factor
        pitch_factor = kwargs.get('pitch_factor', 1.0)
        
        # Check if ML model is available for enhanced predictions
        use_ml_model = kwargs.get('use_ml_model', True)
        ml_model = None
        if use_ml_model:
            try:
                from models.soccer_shots_prop_model import SoccerShotsPropModel
                ml_model = SoccerShotsPropModel()
                if ml_model.model is None:
                    ml_model = None
            except ImportError:
                ml_model = None
        
        # Tactical context for ML features
        home_tactics = kwargs.get('home_tactics', {})
        away_tactics = kwargs.get('away_tactics', {})
        is_low_block = away_tactics.get('is_low_block', 0)
        
        props = {
            "sport": "soccer",
            "matchup": f"{home_team} vs {away_team}",
            "pitch_factor": pitch_factor,
            "player_props": [],
            "top_recommendations": [],
            "ml_model_used": ml_model is not None,
        }
        
        # Generate props for key players
        for player in home_roster + away_roster:
            # Determine if player faces low block
            player_is_low_block = is_low_block if player.team == home_team else 0
            is_home = 1 if player.team == home_team else 0
            
            # Shots on Target prop - use ML model if available
            if ml_model and player.stats:
                sot_prop = self._project_soccer_shots_on_target_ml(
                    player, pitch_factor, ml_model, 
                    is_low_block=player_is_low_block,
                    is_home_game=is_home
                )
            else:
                sot_prop = self._project_soccer_shots_on_target(player, pitch_factor)
            
            if sot_prop:
                props["player_props"].append(sot_prop)
            
            # Goals prop (for forwards)
            if player.position in ['ST', 'CF', 'LW', 'RW', 'CAM']:
                goals_prop = self._project_soccer_goals(player, pitch_factor)
                if goals_prop:
                    props["player_props"].append(goals_prop)
            
            # Assists prop (for midfielders)
            if player.position in ['CM', 'CAM', 'CDM', 'LW', 'RW']:
                assists_prop = self._project_soccer_assists(player, pitch_factor)
                if assists_prop:
                    props["player_props"].append(assists_prop)
        
        # Find top recommendations
        top_props = sorted(props["player_props"], key=lambda x: abs(x.get('edge_rating', x.get('edge', 0))), reverse=True)
        props["top_recommendations"] = top_props[:5]
        
        return props
    
    def _get_basketball_roster(self, team: str) -> List:
        """Get basketball roster (sample data for demonstration)"""
        if not ROSTER_AVAILABLE:
            return []
        
        # Sample basketball rosters
        sample_rosters = {
            "Real Madrid": [
                Player("rm_001", "Facundo Campazzo", "Real Madrid", "PG", "basketball", {
                    "ppg": 12.5, "rpg": 2.8, "apg": 7.2, "topg": 2.5,
                    "pts_line": 12.5, "reb_line": 2.5, "ast_line": 6.5
                }),
                Player("rm_002", "Walter Tavares", "Real Madrid", "C", "basketball", {
                    "ppg": 10.2, "rpg": 7.5, "apg": 1.2, "bpg": 1.8,
                    "pts_line": 10.5, "reb_line": 7.5, "ast_line": 1.5
                }),
                Player("rm_003", "Dzanan Musa", "Real Madrid", "SF", "basketball", {
                    "ppg": 14.8, "rpg": 3.2, "apg": 2.5, "topg": 1.8,
                    "pts_line": 14.5, "reb_line": 3.5, "ast_line": 2.5
                }),
            ],
            "FC Barcelona": [
                Player("fcb_001", "Nicolas Laprovittola", "FC Barcelona", "PG", "basketball", {
                    "ppg": 11.2, "rpg": 2.5, "apg": 6.8, "topg": 2.2,
                    "pts_line": 11.5, "reb_line": 2.5, "ast_line": 6.5
                }),
                Player("fcb_002", "Jan Vesely", "FC Barcelona", "PF", "basketball", {
                    "ppg": 12.5, "rpg": 5.8, "apg": 2.2, "bpg": 0.8,
                    "pts_line": 12.5, "reb_line": 5.5, "ast_line": 2.5
                }),
                Player("fcb_003", "Jabari Parker", "FC Barcelona", "SF", "basketball", {
                    "ppg": 13.5, "rpg": 4.2, "apg": 1.8, "topg": 1.5,
                    "pts_line": 13.5, "reb_line": 4.5, "ast_line": 1.5
                }),
            ],
        }
        
        return sample_rosters.get(team, [])
    
    def _get_soccer_roster(self, team: str) -> List:
        """Get soccer roster (sample data for demonstration)"""
        if not ROSTER_AVAILABLE:
            return []
        
        # Sample soccer rosters
        sample_rosters = {
            "Liverpool": [
                Player("liv_001", "Mohamed Salah", "Liverpool", "RW", "soccer", {
                    "goals_per_90": 0.75, "assists_per_90": 0.35,
                    "shots_per_90": 3.8, "sot_per_90": 1.8,
                    "goal_line": 0.5, "sot_line": 1.5
                }),
                Player("liv_002", "Darwin Nunez", "Liverpool", "ST", "soccer", {
                    "goals_per_90": 0.55, "assists_per_90": 0.20,
                    "shots_per_90": 3.2, "sot_per_90": 1.5,
                    "goal_line": 0.5, "sot_line": 1.5
                }),
                Player("liv_003", "Trent Alexander-Arnold", "Liverpool", "RB", "soccer", {
                    "goals_per_90": 0.08, "assists_per_90": 0.45,
                    "shots_per_90": 1.2, "sot_per_90": 0.5,
                    "goal_line": 0.5, "sot_line": 0.5
                }),
            ],
            "Aston Villa": [
                Player("av_001", "Ollie Watkins", "Aston Villa", "ST", "soccer", {
                    "goals_per_90": 0.60, "assists_per_90": 0.25,
                    "shots_per_90": 3.0, "sot_per_90": 1.4,
                    "goal_line": 0.5, "sot_line": 1.5
                }),
                Player("av_002", "John McGinn", "Aston Villa", "CM", "soccer", {
                    "goals_per_90": 0.15, "assists_per_90": 0.30,
                    "shots_per_90": 1.8, "sot_per_90": 0.7,
                    "goal_line": 0.5, "sot_line": 0.5
                }),
                Player("av_003", "Moussa Diaby", "Aston Villa", "LW", "soccer", {
                    "goals_per_90": 0.35, "assists_per_90": 0.40,
                    "shots_per_90": 2.5, "sot_per_90": 1.2,
                    "goal_line": 0.5, "sot_line": 1.5
                }),
            ],
        }
        
        return sample_rosters.get(team, [])
    
    def _project_basketball_points(self, player: Player, venue_factor: float) -> Optional[Dict]:
        """Project basketball points prop"""
        if not player:
            return None
        
        ppg = player.stats.get('ppg', 10.0)
        line = player.stats.get('pts_line', ppg)
        
        # Adjust for venue (home court advantage)
        is_home = player.team == player.team  # Would need matchup info
        adj_ppg = ppg * (venue_factor if is_home else 0.98)
        
        # Calculate projection with some variance
        projection = adj_ppg * 1.0  # Could factor in opponent defense
        
        edge = projection - line
        confidence = min(100, max(0, 50 + edge * 12))
        recommendation = "Over" if edge > 1.0 else "Under" if edge < -1.0 else "Pass"
        
        return {
            "player_name": player.name,
            "team": player.team,
            "prop_type": "Points",
            "line": line,
            "projection": round(projection, 1),
            "edge": round(edge, 2),
            "confidence": round(confidence, 1),
            "recommendation": recommendation,
            "lean": recommendation if recommendation != "Pass" else "No Lean",
        }
    
    def _project_basketball_rebounds(self, player: Player, venue_factor: float) -> Optional[Dict]:
        """Project basketball rebounds prop"""
        if not player:
            return None
        
        rpg = player.stats.get('rpg', 5.0)
        line = player.stats.get('reb_line', rpg)
        
        projection = rpg * venue_factor
        edge = projection - line
        confidence = min(100, max(0, 50 + edge * 15))
        recommendation = "Over" if edge > 0.5 else "Under" if edge < -0.5 else "Pass"
        
        return {
            "player_name": player.name,
            "team": player.team,
            "prop_type": "Rebounds",
            "line": line,
            "projection": round(projection, 1),
            "edge": round(edge, 2),
            "confidence": round(confidence, 1),
            "recommendation": recommendation,
            "lean": recommendation if recommendation != "Pass" else "No Lean",
        }
    
    def _project_basketball_assists(self, player: Player, venue_factor: float) -> Optional[Dict]:
        """Project basketball assists prop"""
        if not player:
            return None
        
        apg = player.stats.get('apg', 4.0)
        line = player.stats.get('ast_line', apg)
        
        projection = apg * venue_factor
        edge = projection - line
        confidence = min(100, max(0, 50 + edge * 15))
        recommendation = "Over" if edge > 0.5 else "Under" if edge < -0.5 else "Pass"
        
        return {
            "player_name": player.name,
            "team": player.team,
            "prop_type": "Assists",
            "line": line,
            "projection": round(projection, 1),
            "edge": round(edge, 2),
            "confidence": round(confidence, 1),
            "recommendation": recommendation,
            "lean": recommendation if recommendation != "Pass" else "No Lean",
        }
    
    def _project_soccer_shots_on_target(self, player: Player, pitch_factor: float) -> Optional[Dict]:
        """Project soccer shots on target prop (baseline heuristic)"""
        if not player:
            return None
        
        sot_per_90 = player.stats.get('sot_per_90', 1.0)
        line = player.stats.get('sot_line', sot_per_90)
        
        # Adjust for pitch factor (some pitches favor more shots)
        projection = sot_per_90 * pitch_factor
        
        edge = projection - line
        confidence = min(100, max(0, 50 + edge * 30))
        recommendation = "Over" if edge > 0.3 else "Under" if edge < -0.3 else "Pass"
        edge_rating = min(10, max(0, 5 + edge * 3))
        
        return {
            "player_name": player.name,
            "team": player.team,
            "prop_type": "Shots on Target",
            "line": line,
            "projection": round(projection, 2),
            "edge": round(edge, 2),
            "edge_rating": round(edge_rating, 1),
            "confidence": round(confidence, 1),
            "recommendation": recommendation,
            "lean": recommendation if recommendation != "Pass" else "No Lean",
            "method": "heuristic",
        }
    
    def _project_soccer_shots_on_target_ml(self, player: Player, pitch_factor: float, 
                                           ml_model, is_low_block: int = 0, 
                                           is_home_game: int = 0) -> Optional[Dict]:
        """Project soccer shots on target prop using ML model"""
        if not player or not player.stats:
            return None
        
        # Build feature vector for ML model
        features = {
            'player_sot_per_90': player.stats.get('sot_per_90', 1.0),
            'shot_accuracy_pct': player.stats.get('shot_accuracy', 0.35),
            'opp_sot_allowed': 4.5,  # Would need opponent data in production
            'touches_in_box': player.stats.get('touches_in_box', 3.0),
            'is_low_block': is_low_block,
            'is_home_game': is_home_game,
            'possession_against': 0.50,  # Would need opponent possession data
            'defensive_width': 0.55,  # Would need opponent tactical data
            'xg_for': player.stats.get('xg_per_90', 0.3),
            'recent_form': 0.50,  # Would need recent match data
        }
        
        # Run ML prediction
        import pandas as pd
        df = pd.DataFrame([features])
        result = ml_model.predict(df)
        
        if result.empty:
            return None
        
        row = result.iloc[0]
        over_prob = row['over_probability']
        line = player.stats.get('sot_line', 1.5)
        
        # Edge is probability vs break-even
        edge = over_prob - 0.50
        edge_rating = row['edge_rating']
        classification = row['classification']
        
        # Confidence from edge rating
        confidence = min(95, max(35, 50 + edge_rating * 5))
        
        # Recommendation
        if classification == 'Elite':
            recommendation = f"OVER 1.5 SoT"
        elif classification == 'Strong':
            recommendation = f"Consider OVER 1.5 SoT"
        elif classification == 'Moderate':
            recommendation = "Fade"
        else:
            recommendation = "Avoid"
        
        return {
            "player_name": player.name,
            "team": player.team,
            "prop_type": "Shots on Target (ML)",
            "line": line,
            "projection": round(over_prob * 2.5, 2),  # Scale to expected SoT
            "over_probability": round(over_prob, 3),
            "true_odds": round(row.get('true_odds', 0), 0),
            "edge": round(edge, 3),
            "edge_rating": edge_rating,
            "classification": classification,
            "confidence": round(confidence, 1),
            "recommendation": recommendation,
            "lean": recommendation if recommendation not in ["Pass", "Fade", "Avoid"] else "No Lean",
            "method": "xgboost_ml",
            "features_used": features,
        }
    
    def _project_soccer_goals(self, player: Player, pitch_factor: float) -> Optional[Dict]:
        """Project soccer anytime goalscorer prop"""
        if not player:
            return None
        
        goals_per_90 = player.stats.get('goals_per_90', 0.3)
        
        # Convert to probability (anytime goal = at least 1 goal)
        # Using Poisson: P(at least 1) = 1 - P(0) = 1 - e^(-lambda)
        lambda_goals = goals_per_90 * pitch_factor
        goal_prob = 1 - math.exp(-lambda_goals)
        
        # Break-even probability for +150 odds (typical forward line)
        edge = goal_prob - 0.25  # ~25% break-even
        confidence = min(100, max(0, 50 + edge * 150))
        recommendation = "Yes Goal" if goal_prob > 0.35 else "No Goal" if goal_prob < 0.15 else "Pass"
        
        return {
            "player_name": player.name,
            "team": player.team,
            "prop_type": "Anytime Goalscorer",
            "line": 0.5,
            "projection": round(goal_prob, 3),
            "edge": round(edge, 3),
            "confidence": round(confidence, 1),
            "recommendation": recommendation,
            "lean": recommendation if recommendation != "Pass" else "No Lean",
        }
    
    def _project_soccer_assists(self, player: Player, pitch_factor: float) -> Optional[Dict]:
        """Project soccer assists prop"""
        if not player:
            return None
        
        assists_per_90 = player.stats.get('assists_per_90', 0.2)
        
        # Convert to probability
        lambda_assists = assists_per_90 * pitch_factor
        assist_prob = 1 - math.exp(-lambda_assists)
        
        edge = assist_prob - 0.20  # ~20% break-even
        confidence = min(100, max(0, 50 + edge * 150))
        recommendation = "Yes Assist" if assist_prob > 0.30 else "No Assist" if assist_prob < 0.12 else "Pass"
        
        return {
            "player_name": player.name,
            "team": player.team,
            "prop_type": "Assists",
            "line": 0.5,
            "projection": round(assist_prob, 3),
            "edge": round(edge, 3),
            "confidence": round(confidence, 1),
            "recommendation": recommendation,
            "lean": recommendation if recommendation != "Pass" else "No Lean",
        }
    
    def _get_park_factor(self, team: str, league: str) -> Dict:
        """Get park factors for a team"""
        # Map team names to abbreviations
        team_map = {
            "San Francisco Giants": "SF", "Giants": "SF",
            "Chicago Cubs": "CHC", "Cubs": "CHC",
            "Los Angeles Dodgers": "LAD", "Dodgers": "LAD",
            "New York Yankees": "NYY", "Yankees": "NYY",
            "Boston Red Sox": "BOS", "Red Sox": "BOS",
        }
        
        abbr = team_map.get(team, team[:2].upper())
        return self.park_factors.get(abbr, {"hr": 1.0, "runs": 1.0, "k": 1.0})


# Global props engine instance
props_engine = PropsEngine()


def generate_player_props(sport: str, home_team: str, away_team: str, 
                          league: str = None, **kwargs) -> Dict[str, Any]:
    """
    Convenience function to generate player props.
    
    Args:
        sport: Sport type
        home_team: Home team name
        away_team: Away team name
        league: League type
        **kwargs: Additional parameters
        
    Returns:
        Dictionary with all prop recommendations
    """
    return props_engine.generate_props(sport, home_team, away_team, league, **kwargs)