"""
Table Tennis Predictor - Top-Down Market Pricing & Calibrated Hybrid Model
Section 3 of Czech Liga Pro Handoff Specification.

Features:
- Proportional margin removal for same-book price pairs.
- Calibrated hybrid regression integrating market anchor, independent rating,
  shrunk residual H2H, rest, and workload.
- Separately validated bottom-up fallback when reference odds are missing.
- Inversion to legal point-state scoring distributions.
"""

import math
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple
from models.table_tennis_scoring import TableTennisMatchScorer, MatchState, PointState

@dataclass
class HybridModelWeights:
    intercept: float = 0.0
    beta_market: float = 0.82
    beta_strength: float = 0.0018  # scaled per rating point difference
    beta_h2h: float = 0.25         # shrunk residual H2H weight
    beta_rest: float = 0.0008      # rest difference in minutes
    beta_load: float = -0.015      # games played difference

class CzechLigaProPredictor:
    def __init__(self, weights: Optional[HybridModelWeights] = None,
                 rating_scale: float = 650.0):
        self.weights = weights or HybridModelWeights()
        self.rating_scale = rating_scale

    @staticmethod
    def devig_proportional(odds_a: float, odds_b: float) -> Optional[Tuple[float, float]]:
        """
        Removes margin proportionally from a complete same-book pair.
        Never combine opposite sides from different books into a single market.
        """
        if odds_a <= 1.0 or odds_b <= 1.0:
            return None
        q_a = 1.0 / odds_a
        q_b = 1.0 / odds_b
        overround = q_a + q_b
        return (q_a / overround, q_b / overround)

    @staticmethod
    def logit(p: float, eps: float = 1e-6) -> float:
        p_clamped = max(eps, min(1.0 - eps, p))
        return math.log(p_clamped / (1.0 - p_clamped))

    @staticmethod
    def expit(x: float) -> float:
        if x >= 40.0:
            return 1.0
        if x <= -40.0:
            return 0.0
        return 1.0 / (1.0 + math.exp(-x))

    def predict_bottom_up(self, rating_a: float, rating_b: float,
                          shrunk_h2h_residual: float = 0.0,
                          rest_diff_min: float = 0.0,
                          load_diff_games: float = 0.0) -> float:
        """
        Standalone bottom-up fallback model when market reference quotes are unavailable.
        Uses pure independent strength + historical residual + workload adjustments.
        """
        rating_diff = rating_a - rating_b
        # Base logit derived from Elo rating differential
        base_logit = (rating_diff / self.rating_scale) * math.log(10.0)
        adjusted_logit = (
            base_logit +
            self.weights.beta_h2h * shrunk_h2h_residual +
            self.weights.beta_rest * rest_diff_min +
            self.weights.beta_load * load_diff_games
        )
        return self.expit(adjusted_logit)

    def predict_hybrid(self, p_reference_market: float,
                       rating_a: float, rating_b: float,
                       shrunk_h2h_residual: float = 0.0,
                       rest_diff_min: float = 0.0,
                       load_diff_games: float = 0.0) -> float:
        """
        Calibrated hybrid prediction combining market anchor with independent strength,
        residual H2H, and physical rest/workload.
        """
        market_logit = self.logit(p_reference_market)
        rating_diff = rating_a - rating_b
        
        hybrid_logit = (
            self.weights.intercept +
            self.weights.beta_market * market_logit +
            self.weights.beta_strength * rating_diff +
            self.weights.beta_h2h * shrunk_h2h_residual +
            self.weights.beta_rest * rest_diff_min +
            self.weights.beta_load * load_diff_games
        )
        return self.expit(hybrid_logit)

    def invert_match_prob_to_point_prob(self, p_match_target: float, tol: float = 1e-5) -> float:
        """
        Inverts match win probability into underlying point-win probability p_point
        under best-of-5 11-point table tennis rules using bisection.
        """
        if p_match_target <= 0.001:
            return 0.35
        if p_match_target >= 0.999:
            return 0.65

        low = 0.30
        high = 0.70
        for _ in range(30):
            mid = (low + high) / 2.0
            match_scorer = TableTennisMatchScorer(p_point_a=mid, best_of=5)
            # Evaluate match probability from neutral pre-match state
            res = match_scorer.solve_match(MatchState(best_of=5))
            p_mid = res["match_winner_a"]
            if abs(p_mid - p_match_target) < tol:
                return mid
            if p_mid < p_match_target:
                low = mid
            else:
                high = mid
        return (low + high) / 2.0

    def generate_full_prediction(self, player_a: Dict[str, Any],
                                 player_b: Dict[str, Any],
                                 reference_odds: Optional[Tuple[float, float]] = None,
                                 h2h_data: Optional[Dict[str, Any]] = None,
                                 workload_data: Optional[Dict[str, Any]] = None,
                                 live_match_state: Optional[MatchState] = None) -> Dict[str, Any]:
        """
        Generates full market report and distributions comparing top-down,
        bottom-up, and hybrid models.
        """
        rating_a = float(player_a.get("rating", 750.0))
        rating_b = float(player_b.get("rating", 750.0))

        shrunk_h2h_res = h2h_data.get("shrunk_residual_h2h", 0.0) if h2h_data else 0.0
        rest_diff = workload_data.get("rest_difference_minutes", 0.0) if workload_data else 0.0
        load_diff = workload_data.get("workload_game_difference", 0.0) if workload_data else 0.0

        p_bottom_up = self.predict_bottom_up(
            rating_a=rating_a, rating_b=rating_b,
            shrunk_h2h_residual=shrunk_h2h_res,
            rest_diff_min=rest_diff, load_diff_games=load_diff
        )

        p_market_fair_a = None
        p_hybrid = None

        if reference_odds and reference_odds[0] > 1.0 and reference_odds[1] > 1.0:
            devigged = self.devig_proportional(reference_odds[0], reference_odds[1])
            if devigged:
                p_market_fair_a = devigged[0]
                p_hybrid = self.predict_hybrid(
                    p_reference_market=p_market_fair_a,
                    rating_a=rating_a, rating_b=rating_b,
                    shrunk_h2h_residual=shrunk_h2h_res,
                    rest_diff_min=rest_diff, load_diff_games=load_diff
                )

        # Primary decision probability
        final_p_match = p_hybrid if p_hybrid is not None else p_bottom_up
        strategy_used = "HYBRID_TOP_DOWN_H2H" if p_hybrid is not None else "BOTTOM_UP_FALLBACK"

        # Invert to legal point probability and resolve full scoring distribution
        implied_p_point = self.invert_match_prob_to_point_prob(final_p_match)
        match_scorer = TableTennisMatchScorer(p_point_a=implied_p_point, best_of=5)
        
        state_to_solve = live_match_state or MatchState(best_of=5)
        distribution_results = match_scorer.solve_match(state_to_solve)

        return {
            "strategy": strategy_used,
            "player_a_name": player_a.get("name", "Player A"),
            "player_b_name": player_b.get("name", "Player B"),
            "probabilities": {
                "top_down_market_a": round(p_market_fair_a, 4) if p_market_fair_a is not None else None,
                "bottom_up_strength_a": round(p_bottom_up, 4),
                "hybrid_final_a": round(p_hybrid, 4) if p_hybrid is not None else None,
                "selected_final_win_a": round(final_p_match, 4),
                "selected_final_win_b": round(1.0 - final_p_match, 4),
                "implied_point_win_prob_a": round(implied_p_point, 4)
            },
            "h2h_metrics": h2h_data or {},
            "workload_metrics": workload_data or {},
            "market_distributions": distribution_results
        }
