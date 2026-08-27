#!/usr/bin/env python
"""EuroLeague 1Q, halftime, and full-game prediction engine."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional


class EuroleaguePredictor:
    """Project EuroLeague segments from seeded per-100 and per-40 metrics."""

    DEFAULT_LEAGUE_BASELINE = {
        "pace": 72.0,
        "ortg": 112.0,
        "drtg": 112.0,
        "q1_ratio": 0.245,
        "ht_ratio": 0.495,
    }
    SEGMENTS = {
        "q1": {"ratio": 0.245, "sigma": 5.5, "hca": 0.9},
        "halftime": {"ratio": 0.495, "sigma": 7.8, "hca": 1.8},
        "full_game": {"ratio": 1.0, "sigma": 11.0, "hca": 3.5},
    }

    def __init__(
        self,
        home_team: str,
        away_team: str,
        home_stats: Mapping[str, Any],
        away_stats: Mapping[str, Any],
        league_baseline: Optional[Mapping[str, Any]] = None,
        market_lines: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self.home_team = home_team
        self.away_team = away_team
        self.home_stats = dict(home_stats)
        self.away_stats = dict(away_stats)
        self.league = {**self.DEFAULT_LEAGUE_BASELINE, **(league_baseline or {})}
        self.market_lines = dict(market_lines or {})
        self._validate_stats(self.home_stats, home_team)
        self._validate_stats(self.away_stats, away_team)

    @staticmethod
    def _validate_stats(stats: Mapping[str, Any], team: str) -> None:
        missing = [key for key in ("ortg", "drtg", "pace") if key not in stats]
        if missing:
            raise ValueError(f"Missing EuroLeague metrics for '{team}': {', '.join(missing)}")
        for key in ("ortg", "drtg", "pace"):
            if float(stats[key]) <= 0:
                raise ValueError(f"EuroLeague metric '{key}' for '{team}' must be positive")

    @staticmethod
    def _number(stats: Mapping[str, Any], *keys: str, default: float) -> float:
        for key in keys:
            if stats.get(key) is not None:
                return float(stats[key])
        return default

    def _segment_ratio(self, segment: str) -> float:
        default = float(self.league.get("q1_ratio" if segment == "q1" else "ht_ratio", self.SEGMENTS[segment]["ratio"]))
        if segment == "full_game":
            return 1.0
        ratios = []
        for stats in (self.home_stats, self.away_stats):
            direct = self._number(stats, f"{segment}_ratio", default=0.0)
            if direct > 0:
                ratios.append(direct)
                continue
            split_for = self._number(stats, f"{segment}_points_for", f"{segment}_for", default=0.0)
            full_for = self._number(stats, "points_for", "full_game_points_for", default=0.0)
            if split_for > 0 and full_for > 0:
                ratios.append(split_for / full_for)
        return sum(ratios) / len(ratios) if ratios else default

    def _market_line(self, segment: str) -> Optional[float]:
        aliases = {
            "q1": ("q1", "1q", "q1_spread"),
            "halftime": ("halftime", "ht", "ht_spread"),
            "full_game": ("full_game", "fg", "spread", "full_game_spread"),
        }
        value = next((self.market_lines[key] for key in aliases[segment] if key in self.market_lines), None)
        return float(value) if value is not None else None

    @staticmethod
    def _normal_cdf(value: float, sigma: float) -> float:
        return 0.5 * (1.0 + math.erf(value / (sigma * math.sqrt(2.0))))

    def predict(self) -> Dict[str, Any]:
        league_pace = float(self.league["pace"])
        expected_pace = (float(self.home_stats["pace"]) * float(self.away_stats["pace"])) / league_pace
        home_eff = (float(self.home_stats["ortg"]) + float(self.away_stats["drtg"])) / 2.0
        away_eff = (float(self.away_stats["ortg"]) + float(self.home_stats["drtg"])) / 2.0
        base_home = expected_pace * home_eff / 100.0
        base_away = expected_pace * away_eff / 100.0

        segments: Dict[str, Any] = {}
        for name, config in self.SEGMENTS.items():
            ratio = self._segment_ratio(name)
            home_points = base_home * ratio + config["hca"]
            away_points = base_away * ratio
            differential = home_points - away_points
            model_probability = self._normal_cdf(differential, config["sigma"])
            line = self._market_line(name)
            edge = differential - line if line is not None else None
            segment_result = {
                "projected_home_points": round(home_points, 2),
                "projected_away_points": round(away_points, 2),
                "projected_total_points": round(home_points + away_points, 2),
                "projected_spread": round(differential, 2),
                "home_moneyline_probability": round(model_probability, 4),
                "away_moneyline_probability": round(1.0 - model_probability, 4),
                "market_spread": line,
                "spread_edge": round(edge, 2) if edge is not None else None,
                "sigma": config["sigma"],
            }
            segment_result.update({
                "projected_home_score": segment_result["projected_home_points"],
                "projected_away_score": segment_result["projected_away_points"],
                "projected_total": segment_result["projected_total_points"],
                "probability": segment_result["home_moneyline_probability"],
                "away_probability": segment_result["away_moneyline_probability"],
                "model_edge": segment_result["spread_edge"],
                "lean": self.home_team if model_probability >= 0.5 else self.away_team,
            })
            segments[name] = segment_result

        result = {
            "sport": "basketball",
            "league": "EuroLeague",
            "home_team": self.home_team,
            "away_team": self.away_team,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "expected_pace": round(expected_pace, 2),
            "team_metrics": {"home": self.home_stats, "away": self.away_stats},
            "q1": segments["q1"],
            "halftime": segments["halftime"],
            "full_game": segments["full_game"],
            "market_info": {"lines": self.market_lines},
            "notes": "EuroLeague 40-minute model using seeded ORtg/DRtg/pace and historical segment splits.",
        }
        result["segments"] = {"1q": segments["q1"], "ht": segments["halftime"], "fg": segments["full_game"]}
        return result


if __name__ == "__main__":
    demo = EuroleaguePredictor(
        "Home", "Away",
        {"ortg": 115, "drtg": 108, "pace": 72},
        {"ortg": 111, "drtg": 113, "pace": 70},
    )
    print(demo.predict())
