"""
MLB NRFI/YRFI Engine
=====================
Project No Runs First Inning (NRFI) / Yes Runs First Inning (YRFI)
probabilities for MLB games.

Model factors:
- Starting pitcher ERA, K/9, WHIP (higher quality = higher NRFI prob)
- Team scoring output (runs per game proxy for first-inning scoring)
- Park factor (pitcher parks boost NRFI)
- Weather (wind out / warm = lower NRFI via HR boost)
- Game total anchor (low totals -> higher NRFI)
- Sharp money alignment (positive = sharp on NRFI)

Uses the confidence engine (mlb_nrfi market type) for bet recommendations.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.confidence_engine import confidence_score, bet_recommendation, get_volatility


def project_nrfi(
    home_pitcher: Dict[str, Any],
    away_pitcher: Dict[str, Any],
    home_team_stats: Optional[Dict[str, Any]] = None,
    away_team_stats: Optional[Dict[str, Any]] = None,
    park_factor: float = 1.0,
    weather: Optional[Dict[str, Any]] = None,
    market_total: float = 8.5,
    sharp_alignment: float = 0.0,
) -> Dict[str, Any]:
    """
    Project NRFI/YRFI probabilities for an MLB game.

    Args:
        home_pitcher: Home pitcher stats dict with era, k9, whip
        away_pitcher: Away pitcher stats dict with era, k9, whip
        home_team_stats: Optional home team stats (rpg)
        away_team_stats: Optional away team stats (rpg)
        park_factor: Park run factor (< 1.0 = pitcher-friendly)
        weather: Weather dict with wind_speed, temperature, wind_direction_factor
        market_total: Market game total (line)
        sharp_alignment: -1 to +1 (positive = sharp money on NRFI)

    Returns:
        Dict with nrfi_probability, yrfi_probability, edge, lean, confidence,
        recommendation, and factor drivers
    """
    # --- Base NRFI rate (league average ~55%) ---
    base_nrfi = 0.55

    # --- Starting pitcher quality adjustments ---
    home_era = float(home_pitcher.get("era", 4.2))
    away_era = float(away_pitcher.get("era", 4.2))
    home_k9 = float(home_pitcher.get("k9", 8.0))
    away_k9 = float(away_pitcher.get("k9", 8.0))
    home_whip = float(home_pitcher.get("whip", 1.25))
    away_whip = float(away_pitcher.get("whip", 1.25))

    # Lower ERA = higher NRFI
    era_adj = ((5.0 - home_era) + (5.0 - away_era)) * 0.015
    # More strikeouts = higher NRFI
    k_adj = ((home_k9 - 8.0) + (away_k9 - 8.0)) * 0.012
    # Lower WHIP = higher NRFI (fewer baserunners)
    whip_adj = ((1.25 - home_whip) + (1.25 - away_whip)) * 0.10

    # --- Team scoring adjustments ---
    home_rpg = float(home_team_stats.get("rpg", 4.3)) if home_team_stats else 4.3
    away_rpg = float(away_team_stats.get("rpg", 4.3)) if away_team_stats else 4.3
    # Higher scoring = lower NRFI
    team_adj = -((home_rpg - 4.3) + (away_rpg - 4.3)) * 0.02

    # --- Park factor adjustment ---
    park_adj = 0.0
    if park_factor != 0:
        park_adj = (1.0 - park_factor) * 0.15

    # --- Weather adjustment ---
    weather_adj = 0.0
    if weather:
        wind_speed = float(weather.get("wind_speed", 0))
        wind_dir = float(weather.get("wind_direction_factor", 0))
        temp = float(weather.get("temperature", 72))
        if wind_dir > 0.5:
            weather_adj -= wind_speed * 0.004
        if temp >= 85:
            weather_adj -= 0.02
        elif temp <= 55:
            weather_adj += 0.02

    # --- Market total anchor ---
    total_adj = (8.5 - market_total) * 0.02

    # --- Sharp alignment ---
    sharp_adj = sharp_alignment * 0.03

    # --- Combine & clamp ---
    nrfi_prob = (
        base_nrfi + era_adj + k_adj + whip_adj +
        team_adj + park_adj + weather_adj + total_adj + sharp_adj
    )
    nrfi_prob = max(0.35, min(0.80, nrfi_prob))
    yrfi_prob = 1.0 - nrfi_prob

    # --- Edge vs market baseline (~52% typical NRFI price) ---
    market_nrfi = 0.52
    edge = nrfi_prob - market_nrfi

    # --- Confidence & recommendation ---
    volatility = get_volatility("mlb_nrfi")
    conf = confidence_score(edge * 100, volatility, sharp_alignment)
    rec = bet_recommendation(conf, "mlb_nrfi")

    return {
        "nrfi_probability": round(nrfi_prob, 4),
        "yrfi_probability": round(yrfi_prob, 4),
        "lean": "NRFI" if nrfi_prob > 0.54 else "YRFI",
        "edge_vs_market": round(edge, 4),
        "confidence": conf,
        "recommendation": rec,
        "market_total": market_total,
        "drivers": {
            "era_adjustment": round(era_adj, 4),
            "k9_adjustment": round(k_adj, 4),
            "whip_adjustment": round(whip_adj, 4),
            "team_scoring_adjustment": round(team_adj, 4),
            "park_adjustment": round(park_adj, 4),
            "weather_adjustment": round(weather_adj, 4),
            "total_anchor_adjustment": round(total_adj, 4),
            "sharp_alignment_adjustment": round(sharp_adj, 4),
        },
    }