#!/usr/bin/env python
"""MLB advanced prop and F5/full-game prediction engine."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


class MLBAdvancedPredictor:
    """Predict MLB props and segment markets from validated seeded metrics."""

    def __init__(self, data: Mapping[str, Any] | str | Path) -> None:
        if isinstance(data, (str, Path)):
            data = json.loads(Path(data).read_text(encoding="utf-8-sig"))
        self.data = dict(data)
        self.pitchers = {str(item["name"]): dict(item) for item in self.data.get("pitchers", [])}
        self.hitters = {str(item["name"]): dict(item) for item in self.data.get("hitters", [])}
        if not self.pitchers or not self.hitters:
            raise ValueError("MLB seed data must contain pitchers and hitters")

    @staticmethod
    def _normal_cdf(value: float, sigma: float) -> float:
        return 0.5 * (1.0 + math.erf(value / (sigma * math.sqrt(2.0))))

    def _pitcher(self, name: str) -> Dict[str, Any]:
        if name not in self.pitchers:
            raise ValueError(f"Pitcher '{name}' is not present in MLB seed data")
        return self.pitchers[name]

    def _hitter(self, name: str) -> Dict[str, Any]:
        if name not in self.hitters:
            raise ValueError(f"Hitter '{name}' is not present in MLB seed data")
        return self.hitters[name]

    def predict(
        self,
        home_team: str,
        away_team: str,
        home_pitcher: str,
        away_pitcher: str,
        home_hitters: list[str],
        away_hitters: list[str],
        market_lines: Optional[Mapping[str, Any]] = None,
        bullpen_era: Optional[Mapping[str, float]] = None,
    ) -> Dict[str, Any]:
        home_sp = self._pitcher(home_pitcher)
        away_sp = self._pitcher(away_pitcher)
        home_batters = [self._hitter(name) for name in home_hitters]
        away_batters = [self._hitter(name) for name in away_hitters]
        lines = dict(market_lines or {})
        home_k = float(home_sp.get("k_per_9", 0.0)) * 5.0 / 9.0
        away_k = float(away_sp.get("k_per_9", 0.0)) * 5.0 / 9.0
        home_tb = sum(float(h["tb_per_pa"]) for h in home_batters) * 4.2
        away_tb = sum(float(h["tb_per_pa"]) for h in away_batters) * 4.2
        home_runs_f5 = max(0.0, 2.35 - float(away_sp.get("era", 4.5)) * 0.12 + home_tb * 0.08)
        away_runs_f5 = max(0.0, 2.10 - float(home_sp.get("era", 4.5)) * 0.12 + away_tb * 0.08)
        home_bullpen = float((bullpen_era or {}).get(f"{home_team}_bullpen_era", 4.2))
        away_bullpen = float((bullpen_era or {}).get(f"{away_team}_bullpen_era", 4.2))
        home_runs_fg = home_runs_f5 + max(0.0, away_bullpen - 4.0) * 0.25
        away_runs_fg = away_runs_f5 + max(0.0, home_bullpen - 4.0) * 0.25

        def segment(name: str, home_runs: float, away_runs: float, sigma: float) -> Dict[str, Any]:
            spread = home_runs - away_runs
            probability = self._normal_cdf(spread, sigma)
            line = lines.get(name)
            return {
                "projected_home_runs": round(home_runs, 2),
                "projected_away_runs": round(away_runs, 2),
                "projected_total_runs": round(home_runs + away_runs, 2),
                "projected_spread": round(spread, 2),
                "home_moneyline_probability": round(probability, 4),
                "away_moneyline_probability": round(1.0 - probability, 4),
                "market_spread": float(line) if line is not None else None,
                "spread_edge": round(spread - float(line), 2) if line is not None else None,
            }

        return {
            "sport": "baseball",
            "league": "MLB",
            "home_team": home_team,
            "away_team": away_team,
            "pitchers": {"home": home_sp, "away": away_sp},
            "pitcher_strikeouts": {"home": round(home_k, 2), "away": round(away_k, 2)},
            "hitter_total_bases": {
                "home": {h["name"]: round(float(h["tb_per_pa"]) * 4.2, 2) for h in home_batters},
                "away": {h["name"]: round(float(h["tb_per_pa"]) * 4.2, 2) for h in away_batters},
            },
            "f5": segment("f5", home_runs_f5, away_runs_f5, 1.8),
            "full_game": segment("full_game", home_runs_fg, away_runs_fg, 2.8),
            "market_info": {"lines": lines},
            "data_source": self.data.get("source", "seeded_mlb_data"),
        }
