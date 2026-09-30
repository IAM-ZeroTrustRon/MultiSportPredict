#!/usr/bin/env python
"""EuroLeague 1Q, halftime, and full-game prediction engine."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple


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


ROOT = Path(__file__).resolve().parent
EUROLEAGUE_STORE = ROOT / "data" / "euroleague_stats.json"
HOOPS_STORE = ROOT / "data" / "basketball_stats.json"

# CLI --league values that map onto the same underlying store slice.
LEAGUE_ALIASES = {
    "euroleague": "EuroLeague",
    "euro league": "EuroLeague",
    "el": "EuroLeague",
    "kbl": "KBL",
    "nbl": "NZ NBL",
    "nbl27": "NZ NBL",
    "nznbl": "NZ NBL",
    "nz nbl": "NZ NBL",
    "nz-nbl": "NZ NBL",
    "new zealand nbl": "NZ NBL",
    "australian nbl": "NZ NBL",
    "bleague": "B.LEAGUE",
    "b league": "B.LEAGUE",
    "b.premier": "B.LEAGUE",
    "b premier": "B.LEAGUE",
    "japan b league": "B.LEAGUE",
}


def _squash(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _load_store(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _normalise_league(raw: str) -> str:
    key = (raw or "").strip().lower()
    return LEAGUE_ALIASES.get(key, (raw or "").strip() or "EuroLeague")


def _find_team(store: Dict[str, Any], typed: str):
    """Exact then squash-insensitive match. Never guesses across leagues."""
    if not typed:
        return None
    if typed in store and isinstance(store[typed], dict):
        return typed, dict(store[typed])
    want = _squash(typed)
    for name, record in store.items():
        if name.startswith("_") or not isinstance(record, dict):
            continue
        if _squash(name) == want:
            return name, dict(record)
    hits = [n for n in store
            if not n.startswith("_") and isinstance(store[n], dict)
            and want and want in _squash(n)]
    if len(hits) == 1:
        return hits[0], dict(store[hits[0]])
    return None


def _league_slice(store: Dict[str, Any], league: str) -> Dict[str, Any]:
    want = league.strip().lower()
    return {n: r for n, r in store.items()
            if not n.startswith("_") and isinstance(r, dict)
            and str(r.get("league", "")).strip().lower() == want}


def lookup_team_stats(team: str, league: str):
    """Resolve one team to (canonical_name, metrics). Strict-fail on miss."""
    canon = _normalise_league(league)
    flat = canon.lower().replace(".", "").replace(" ", "")
    if flat == "euroleague":
        store = _load_store(EUROLEAGUE_STORE)
        hit = _find_team(store, team)
        if hit is None:
            known = sorted(n for n in store if not n.startswith("_"))[:10]
            raise SystemExit(
                f"[STRICT-FAIL] '{team}' is not in {EUROLEAGUE_STORE.name} "
                f"for league '{league}'. Pass --home/away-ortg/drtg/pace "
                f"overrides or seed the store. "
                f"Known: {', '.join(known)}")
        return hit
    if flat in ("kbl", "nznbl"):
        tag = "KBL" if flat == "kbl" else "NZ NBL"
        sliced = _league_slice(_load_store(HOOPS_STORE), tag)
        hit = _find_team(sliced, team)
        if hit is None:
            known = sorted(sliced)[:10]
            raise SystemExit(
                f"[STRICT-FAIL] '{team}' is not in {HOOPS_STORE.name} "
                f"under '{tag}'. No EuroLeague fallback is applied. Pass "
                f"overrides or seed the store. Known: {', '.join(known)}")
        return hit
    raise SystemExit(
        f"[STRICT-FAIL] League '{league}' has no team-metrics store "
        f"(EuroLeague + KBL/NZ NBL only; no B-League data yet). Re-run "
        f"with --home-ortg/--home-drtg/--home-pace and "
        f"--away-ortg/--away-drtg/--away-pace.")


def _league_baseline(league: str, home_stats, away_stats) -> Dict[str, Any]:
    canon = _normalise_league(league)
    flat = canon.lower().replace(".", "").replace(" ", "")
    if flat == "euroleague":
        base = _load_store(EUROLEAGUE_STORE).get("_league_baseline")
        if isinstance(base, dict):
            return dict(base)
    if flat in ("kbl", "nznbl"):
        tag = "KBL" if flat == "kbl" else "NZ NBL"
        rows = _league_slice(_load_store(HOOPS_STORE), tag)
        paces = [float(r["pace"]) for r in rows.values() if r.get("pace")]
        ortgs = [float(r["ortg"]) for r in rows.values() if r.get("ortg")]
        if paces and ortgs:
            avg = round(sum(ortgs) / len(ortgs), 2)
            return {"pace": round(sum(paces) / len(paces), 2),
                    "ortg": avg, "drtg": avg,
                    "q1_ratio": 0.245, "ht_ratio": 0.495}
    pace = round((float(home_stats["pace"]) + float(away_stats["pace"])) / 2.0, 2)
    return {"pace": pace, "ortg": 112.0, "drtg": 112.0,
            "q1_ratio": 0.245, "ht_ratio": 0.495}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--home", required=True, help="Home team name")
    p.add_argument("--away", required=True, help="Away team name")
    p.add_argument("--league", default="EuroLeague")
    p.add_argument("--market-total", type=float, default=None)
    p.add_argument("--market-spread", type=float, default=None)
    p.add_argument("--home-ortg", type=float, default=None)
    p.add_argument("--home-drtg", type=float, default=None)
    p.add_argument("--home-pace", type=float, default=None)
    p.add_argument("--away-ortg", type=float, default=None)
    p.add_argument("--away-drtg", type=float, default=None)
    p.add_argument("--away-pace", type=float, default=None)
    p.add_argument("--output-json", type=Path, default=None)
    return p


def _override_stats(prefix: str, args) -> Optional[Dict[str, float]]:
    vals = {k: getattr(args, f"{prefix}_{k}") for k in ("ortg", "drtg", "pace")}
    if all(v is None for v in vals.values()):
        return None
    missing = [k for k, v in vals.items() if v is None]
    if missing:
        raise SystemExit(
            f"[STRICT-FAIL] Partial {prefix} override: missing "
            f"{', '.join(f'--{prefix}-{m}' for m in missing)}. "
            f"Supply all three of --{prefix}-ortg/drtg/pace or none.")
    for k, v in vals.items():
        if v <= 0:
            raise SystemExit(f"[STRICT-FAIL] --{prefix}-{k} must be positive.")
    return {"ortg": float(vals["ortg"]), "drtg": float(vals["drtg"]),
            "pace": float(vals["pace"])}


def run_cli(args=None) -> Dict[str, Any]:
    ns = build_parser().parse_args(args)
    league = _normalise_league(ns.league)
    home_over = _override_stats("home", ns)
    away_over = _override_stats("away", ns)

    if home_over is not None:
        home_name, home_stats = ns.home, dict(home_over)
    else:
        home_name, home_stats = lookup_team_stats(ns.home, league)
    if away_over is not None:
        away_name, away_stats = ns.away, dict(away_over)
    else:
        away_name, away_stats = lookup_team_stats(ns.away, league)

    market_lines: Dict[str, float] = {}
    if ns.market_spread is not None:
        market_lines["spread"] = float(ns.market_spread)
    baseline = _league_baseline(league, home_stats, away_stats)
    predictor = EuroleaguePredictor(
        home_name, away_name, home_stats, away_stats,
        league_baseline=baseline, market_lines=market_lines)
    result = predictor.predict()
    result["league"] = league
    result["market_info"]["total"] = (float(ns.market_total)
                                      if ns.market_total is not None else None)
    result["notes"] = (
        f"{league} model using seeded ORtg/DRtg/pace and segment splits. "
        f"Strict-fail lookup: unlisted teams stop the run unless "
        f"--home/away-ortg/drtg/pace overrides are supplied.")

    if ns.output_json is not None:
        out = ns.output_json
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            raise SystemExit(f"[ERROR] Could not write {out}: {exc}")
        print(f"[+] Wrote prediction to {out}")
    else:
        print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_cli()
    else:
        demo = EuroleaguePredictor(
            "Home", "Away",
            {"ortg": 115, "drtg": 108, "pace": 72},
            {"ortg": 111, "drtg": 113, "pace": 70},
        )
        print(demo.predict())
