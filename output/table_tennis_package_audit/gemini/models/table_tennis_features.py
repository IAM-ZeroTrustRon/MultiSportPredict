"""
Table Tennis Feature Engineering & H2H Shrinkage Pipeline
Section 3 of Czech Liga Pro Handoff Specification.

Features:
- Chronology-safe H2H metrics with date tracking & explicit sample counts.
- Empirical shrinkage toward baseline expectation: (sum(w_i * y_i) + strength * p_base) / (sum(w_i) + strength).
- Residual H2H features (actual outcomes minus expected outcome at meeting time).
- Rest & Workload metrics calculated strictly from preceding matches in the event venue timezone (Europe/Prague).
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

@dataclass
class HistoricalMatchRecord:
    event_id: str
    match_timestamp_utc: datetime
    player_a_id: str
    player_b_id: str
    a_won_match: bool
    games_a: int
    games_b: int
    total_points_a: int
    total_points_b: int
    first_game_won_a: bool
    prior_expected_prob_a: float  # Model or market expectation available prior to match

@dataclass
class PlayerSessionWorkload:
    player_id: str
    date_str: str  # YYYY-MM-DD in venue timezone (Europe/Prague)
    matches_completed: int = 0
    games_completed: int = 0
    points_completed: int = 0
    last_match_end_utc: Optional[datetime] = None

class TableTennisFeaturePipeline:
    def __init__(self, h2h_prior_strength: float = 3.0, half_life_days: float = 45.0):
        """
        h2h_prior_strength: Shrinkage parameter m in (sum(w*y) + m*p_base) / (sum(w) + m).
        half_life_days: Recency exponential decay half-life for historical meetings.
        """
        self.prior_strength = h2h_prior_strength
        self.half_life_days = half_life_days

    def calculate_recency_weight(self, match_time_utc: datetime, ref_time_utc: datetime) -> float:
        """Computes exponential decay weight based on days elapsed."""
        delta_days = max(0.0, (ref_time_utc - match_time_utc).total_seconds() / 86400.0)
        return math.exp(-math.log(2.0) * delta_days / self.half_life_days)

    def extract_h2h_features(self, history: List[HistoricalMatchRecord],
                             player_a_id: str, player_b_id: str,
                             prediction_time_utc: datetime,
                             baseline_prob_a: float) -> Dict[str, Any]:
        """
        Extracts strictly chronological H2H statistics between Player A and Player B.
        Excludes matches occurring at or after prediction_time_utc.
        """
        # Filter strictly past direct meetings
        past_meetings = [
            m for m in history
            if m.match_timestamp_utc < prediction_time_utc and
            ((m.player_a_id == player_a_id and m.player_b_id == player_b_id) or
             (m.player_a_id == player_b_id and m.player_b_id == player_a_id))
        ]
        # Sort chronologically
        past_meetings.sort(key=lambda m: m.match_timestamp_utc)

        sample_size = len(past_meetings)
        if sample_size == 0:
            return {
                "h2h_sample_size": 0,
                "h2h_weighted_sum": 0.0,
                "raw_match_win_rate_a": 0.5,
                "shrunk_match_win_prob_a": baseline_prob_a,
                "shrunk_residual_h2h": 0.0,
                "games_won_ratio_a": 0.5,
                "avg_point_margin_per_game_a": 0.0,
                "same_day_rematch_count": 0,
                "first_game_win_rate_a": 0.5
            }

        weighted_wins_a = 0.0
        sum_weights = 0.0
        raw_wins_a = 0
        total_games_a = 0
        total_games_b = 0
        total_point_diff_a = 0
        first_game_wins_a = 0
        sum_residuals_a = 0.0

        # Check same-day rematches (in UTC or venue date)
        same_day_count = 0
        pred_date = prediction_time_utc.date()

        for m in past_meetings:
            w = self.calculate_recency_weight(m.match_timestamp_utc, prediction_time_utc)
            is_a_direct = (m.player_a_id == player_a_id)

            won_match = m.a_won_match if is_a_direct else not m.a_won_match
            g_won = m.games_a if is_a_direct else m.games_b
            g_lost = m.games_b if is_a_direct else m.games_a
            pt_diff = (m.total_points_a - m.total_points_b) if is_a_direct else (m.total_points_b - m.total_points_a)
            fg_won = m.first_game_won_a if is_a_direct else not m.first_game_won_a
            prior_exp = m.prior_expected_prob_a if is_a_direct else (1.0 - m.prior_expected_prob_a)

            y = 1.0 if won_match else 0.0
            weighted_wins_a += w * y
            sum_weights += w
            if won_match:
                raw_wins_a += 1

            total_games_a += g_won
            total_games_b += g_lost
            total_point_diff_a += pt_diff
            if fg_won:
                first_game_wins_a += 1

            # Residual: actual outcome (1 or 0) minus prior expectation
            sum_residuals_a += w * (y - prior_exp)

            if m.match_timestamp_utc.date() == pred_date:
                same_day_count += 1

        # Shrinkage toward baseline
        shrunk_win_prob = (weighted_wins_a + self.prior_strength * baseline_prob_a) / (sum_weights + self.prior_strength)
        shrunk_residual = sum_residuals_a / (sum_weights + self.prior_strength)

        total_games = total_games_a + total_games_b
        avg_pt_margin_game = (total_point_diff_a / total_games) if total_games > 0 else 0.0

        return {
            "h2h_sample_size": sample_size,
            "h2h_weighted_sum": round(sum_weights, 2),
            "raw_match_win_rate_a": round(raw_wins_a / sample_size, 4),
            "shrunk_match_win_prob_a": round(shrunk_win_prob, 4),
            "shrunk_residual_h2h": round(shrunk_residual, 4),
            "games_won_ratio_a": round(total_games_a / total_games, 4) if total_games > 0 else 0.5,
            "avg_point_margin_per_game_a": round(avg_pt_margin_game, 2),
            "same_day_rematch_count": same_day_count,
            "first_game_win_rate_a": round(first_game_wins_a / sample_size, 4)
        }

    def extract_workload_and_rest(self, workload_a: PlayerSessionWorkload,
                                 workload_b: PlayerSessionWorkload,
                                 match_start_utc: datetime) -> Dict[str, Any]:
        """
        Calculates same-day workload and elapsed rest in minutes before match start.
        """
        rest_min_a = None
        if workload_a.last_match_end_utc:
            diff_a = (match_start_utc - workload_a.last_match_end_utc).total_seconds() / 60.0
            rest_min_a = max(0.0, diff_a)

        rest_min_b = None
        if workload_b.last_match_end_utc:
            diff_b = (match_start_utc - workload_b.last_match_end_utc).total_seconds() / 60.0
            rest_min_b = max(0.0, diff_b)

        return {
            "player_a_matches_today": workload_a.matches_completed,
            "player_b_matches_today": workload_b.matches_completed,
            "player_a_games_today": workload_a.games_completed,
            "player_b_games_today": workload_b.games_completed,
            "player_a_rest_minutes": round(rest_min_a, 1) if rest_min_a is not None else None,
            "player_b_rest_minutes": round(rest_min_b, 1) if rest_min_b is not None else None,
            "rest_difference_minutes": round(rest_min_a - rest_min_b, 1) if (rest_min_a is not None and rest_min_b is not None) else 0.0,
            "workload_game_difference": workload_a.games_completed - workload_b.games_completed
        }
