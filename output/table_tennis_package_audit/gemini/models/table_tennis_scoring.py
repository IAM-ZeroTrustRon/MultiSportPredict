"""
Table Tennis Scoring Engine - Rule-Faithful Absorbing Point-State Model
Section 4 of Czech Liga Pro Handoff Specification.

Enforces legal ITTF / Czech Liga Pro scoring:
- Games played to 11 points, win by 2.
- Immediate termination when terminal state reached.
- Deuce continuation beyond 15 with no arbitrary truncation.
- Live in-play conditioning on current points and games.
- Distinction between GAME handicap and POINT handicap.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any

@dataclass
class PointState:
    points_a: int = 0
    points_b: int = 0
    server: Optional[str] = None  # 'A', 'B', or None if unknown

    def is_terminal(self) -> bool:
        if self.points_a >= 11 and (self.points_a - self.points_b) >= 2:
            return True
        if self.points_b >= 11 and (self.points_b - self.points_a) >= 2:
            return True
        return False

    def winner(self) -> Optional[str]:
        if not self.is_terminal():
            return None
        return 'A' if self.points_a > self.points_b else 'B'

@dataclass
class MatchState:
    games_a: int = 0
    games_b: int = 0
    best_of: int = 5
    current_game: PointState = field(default_factory=PointState)
    completed_game_scores: List[Tuple[int, int]] = field(default_factory=list)

    @property
    def target_games(self) -> int:
        return (self.best_of // 2) + 1

    def is_terminal(self) -> bool:
        return self.games_a >= self.target_games or self.games_b >= self.target_games

    def winner(self) -> Optional[str]:
        if self.games_a >= self.target_games:
            return 'A'
        if self.games_b >= self.target_games:
            return 'B'
        return None

class TableTennisGameScorer:
    """
    Solves absorbing Markov chain for an 11-point table tennis game (win by 2)
    from any valid point state (points_a, points_b).
    """
    def __init__(self, p_point_a: float):
        if not (0.0 < p_point_a < 1.0):
            raise ValueError(f"Point win probability p must be in (0, 1), got {p_point_a}")
        self.p = p_point_a
        self.q = 1.0 - p_point_a

    def deuce_win_probability(self) -> float:
        """P(A wins game | score is 10-10 or k-k for k>=10)."""
        denom = (self.p ** 2) + (self.q ** 2)
        if denom == 0.0:
            return 0.5
        return (self.p ** 2) / denom

    def deuce_expected_remaining_points(self) -> float:
        """Expected remaining points from a 10-10 state."""
        denom = (self.p ** 2) + (self.q ** 2)
        if denom == 0.0:
            return 4.0
        return 2.0 / denom

    def win_probability_from_state(self, a: int, b: int) -> float:
        """Calculates exact P(A wins game | current score is a-b)."""
        state = PointState(a, b)
        if state.is_terminal():
            return 1.0 if state.winner() == 'A' else 0.0

        # If at or beyond deuce territory (a >= 10 and b >= 10)
        if a >= 10 and b >= 10:
            diff = a - b
            v0 = self.deuce_win_probability()
            if diff == 0:
                return v0
            elif diff == 1:
                return self.p + self.q * v0
            elif diff == -1:
                return self.p * v0
            elif diff >= 2:
                return 1.0
            else:
                return 0.0

        # Backward induction grid up to (10, 10)
        # dp[i][j] = P(A wins from score i - j)
        dp = [[0.0 for _ in range(11)] for _ in range(11)]
        dp[10][10] = self.deuce_win_probability()

        # Terminal boundaries backwards from 9 down to 0
        for i in range(9, -1, -1):
            dp[10][i] = self.p * 1.0 + self.q * dp[10][i + 1]
        for j in range(9, -1, -1):
            dp[j][10] = self.p * dp[j + 1][10] + self.q * 0.0

        # Backward fill
        for i in range(9, -1, -1):
            for j in range(9, -1, -1):
                dp[i][j] = self.p * dp[i + 1][j] + self.q * dp[i][j + 1]

        if a <= 10 and b <= 10:
            return dp[a][b]

        return dp[min(a, 10)][min(b, 10)]

    def terminal_score_distribution_from_0_0(self) -> Dict[Tuple[int, int], float]:
        """
        Computes the exact probability distribution over terminal game scores.
        Valid Czech Liga Pro terminal scores:
        (11, 0) .. (11, 9)
        (0, 11) .. (9, 11)
        (12, 10), (13, 11), ... and inverse for deuce
        """
        dist: Dict[Tuple[int, int], float] = {}

        # 1. Normal wins before deuce (opponent has 0..9 points)
        for k in range(10):
            ways = math.comb(10 + k - 1, k)
            prob_a = ways * (self.p ** 10) * (self.q ** k) * self.p
            prob_b = ways * (self.q ** 10) * (self.p ** k) * self.q
            dist[(11, k)] = prob_a
            dist[(k, 11)] = prob_b

        # 2. Deuce outcomes: reach 10-10 with prob_10_10
        prob_10_10 = math.comb(20, 10) * (self.p ** 10) * (self.q ** 10)
        p_tie = 2.0 * self.p * self.q
        p_win_2 = self.p ** 2
        p_loss_2 = self.q ** 2

        # Terminating at 10+2k - 10+2k-2:
        for k in range(1, 15):
            prob_cycle = prob_10_10 * (p_tie ** (k - 1))
            score_win = 10 + 2 * (k - 1) + 2
            score_loss = 10 + 2 * (k - 1)
            dist[(score_win, score_loss)] = prob_cycle * p_win_2
            dist[(score_loss, score_win)] = prob_cycle * p_loss_2

        # Normalize negligible remaining tail mass
        total_mass = sum(dist.values())
        if total_mass > 0:
            for k in dist:
                dist[k] /= total_mass

        return dist

    def expected_points_from_state(self, a: int, b: int) -> float:
        """Expected additional points to complete the game from score a-b."""
        state = PointState(a, b)
        if state.is_terminal():
            return 0.0

        if a >= 10 and b >= 10:
            diff = abs(a - b)
            if diff == 1:
                return 1.0 + (2.0 * self.p * self.q) * self.deuce_expected_remaining_points()
            else:
                return self.deuce_expected_remaining_points()

        # Expected points via backward induction from 9 down to 0
        exp_pts = [[0.0 for _ in range(11)] for _ in range(11)]
        exp_pts[10][10] = self.deuce_expected_remaining_points()

        for i in range(9, -1, -1):
            exp_pts[10][i] = 1.0 + self.q * exp_pts[10][i + 1]
        for j in range(9, -1, -1):
            exp_pts[j][10] = 1.0 + self.p * exp_pts[j + 1][10]

        for i in range(9, -1, -1):
            for j in range(9, -1, -1):
                exp_pts[i][j] = 1.0 + self.p * exp_pts[i + 1][j] + self.q * exp_pts[i][j + 1]

        return exp_pts[min(a, 10)][min(b, 10)]


class TableTennisMatchScorer:
    """
    Evaluates complete Best-of-5 Czech Liga Pro match from any pre-match or live state.
    Produces joint distributions across match winner, total games, game handicap,
    total points, and point handicap.
    """
    def __init__(self, p_point_a: float, best_of: int = 5):
        self.p_point = p_point_a
        self.game_scorer = TableTennisGameScorer(p_point_a)
        self.best_of = best_of
        self.target = (best_of // 2) + 1

    def solve_match(self, match_state: MatchState) -> Dict[str, Any]:
        """
        Solves match forward from current match_state.
        If current_game has points played, conditions on current_game state.
        """
        if match_state.is_terminal():
            winner = match_state.winner()
            return {
                "match_winner_a": 1.0 if winner == 'A' else 0.0,
                "match_winner_b": 0.0 if winner == 'A' else 1.0,
                "status": "completed",
                "final_game_score": f"{match_state.games_a}-{match_state.games_b}"
            }

        # P(A wins current game)
        curr_g = match_state.current_game
        p_curr_game_a = self.game_scorer.win_probability_from_state(curr_g.points_a, curr_g.points_b)
        
        # P(A wins future neutral game from 0-0)
        p_neutral_game_a = self.game_scorer.win_probability_from_state(0, 0)

        outcomes_prob: Dict[Tuple[int, int], float] = {}

        def search_paths(g_a: int, g_b: int, is_first: bool, path_prob: float):
            if g_a >= self.target or g_b >= self.target:
                score = (g_a, g_b)
                outcomes_prob[score] = outcomes_prob.get(score, 0.0) + path_prob
                return

            prob_a = p_curr_game_a if is_first else p_neutral_game_a
            prob_b = 1.0 - prob_a

            search_paths(g_a + 1, g_b, False, path_prob * prob_a)
            search_paths(g_a, g_b + 1, False, path_prob * prob_b)

        search_paths(match_state.games_a, match_state.games_b, True, 1.0)

        # Match Winner Probabilities
        match_win_a = sum(prob for (ga, gb), prob in outcomes_prob.items() if ga > gb)
        match_win_b = sum(prob for (ga, gb), prob in outcomes_prob.items() if gb > ga)

        # Game Scores Distribution
        score_distribution = {f"{ga}-{gb}": prob for (ga, gb), prob in outcomes_prob.items()}

        # Total Games Markets (best-of-5: 3, 4, or 5 games)
        prob_3_games = outcomes_prob.get((3, 0), 0.0) + outcomes_prob.get((0, 3), 0.0)
        prob_4_games = outcomes_prob.get((3, 1), 0.0) + outcomes_prob.get((1, 3), 0.0)
        prob_5_games = outcomes_prob.get((3, 2), 0.0) + outcomes_prob.get((2, 3), 0.0)

        over_3_5_games = prob_4_games + prob_5_games
        under_3_5_games = prob_3_games
        over_4_5_games = prob_5_games
        under_4_5_games = prob_3_games + prob_4_games
        expected_games = 3.0 * prob_3_games + 4.0 * prob_4_games + 5.0 * prob_5_games

        # GAME Handicap (-1.5 Games A / +1.5 Games B)
        # Home -1.5 Games covers on 3-0 or 3-1 wins
        game_spread_home_minus_1_5 = outcomes_prob.get((3, 0), 0.0) + outcomes_prob.get((3, 1), 0.0)
        game_spread_away_plus_1_5 = 1.0 - game_spread_home_minus_1_5

        # Expected Points calculation
        completed_pts = sum(pa + pb for pa, pb in match_state.completed_game_scores)
        curr_played_pts = curr_g.points_a + curr_g.points_b
        curr_rem_pts = self.game_scorer.expected_points_from_state(curr_g.points_a, curr_g.points_b)
        neutral_game_exp_pts = self.game_scorer.expected_points_from_state(0, 0)

        games_played_so_far = len(match_state.completed_game_scores) + (1 if curr_played_pts > 0 else 0)
        exp_future_neutral_games = max(0.0, expected_games - games_played_so_far)

        expected_total_points = completed_pts + curr_played_pts + curr_rem_pts + (exp_future_neutral_games * neutral_game_exp_pts)

        # Expected point margin (A - B):
        point_diff_per_point = 2.0 * self.p_point - 1.0
        expected_point_margin = expected_total_points * point_diff_per_point

        return {
            "p_point_a": self.p_point,
            "match_winner_a": match_win_a,
            "match_winner_b": match_win_b,
            "score_distribution": score_distribution,
            "game_handicap": {
                "unit": "GAMES",
                "home_minus_1_5": game_spread_home_minus_1_5,
                "away_plus_1_5": game_spread_away_plus_1_5
            },
            "total_games": {
                "unit": "GAMES",
                "over_3_5": over_3_5_games,
                "under_3_5": under_3_5_games,
                "over_4_5": over_4_5_games,
                "under_4_5": under_4_5_games,
                "expected": expected_games
            },
            "total_points": {
                "unit": "POINTS",
                "expected": expected_total_points,
                "expected_margin_a": expected_point_margin
            }
        }
