#!/usr/bin/env python
"""EuroLeague 1Q, halftime, and full-game prediction engine."""

from __future__ import annotations

import argparse
import json
import math
import os
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
            if not math.isfinite(float(stats[key])) or float(stats[key]) <= 0:
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
            edge = differential + line if line is not None else None
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
            "notes": "40-minute model using stored/supplied ORtg/DRtg/pace and assumed segment splits.",
        }
        from models.score_ratings import market_probability, price_market
        full = segments["full_game"]
        result["markets"] = []
        line = self._market_line("full_game")
        total_line = self.market_lines.get("total")
        specs = list(self.market_lines.get("alternatives") or [])
        if line is not None:
            specs.append({"kind": "spread", "line": line,
                "price_a": self.market_lines.get("spread_home_price"), "price_b": self.market_lines.get("spread_away_price")})
        if total_line is not None:
            specs.append({"kind": "total", "line": float(total_line),
                "price_a": self.market_lines.get("over_price"), "price_b": self.market_lines.get("under_price")})
        for spec in specs:
            kind = spec["kind"]
            mean = full["projected_spread"] if kind == "spread" else full["projected_total"]
            sigma = full["sigma"] if kind == "spread" else float(self.league.get("total_sd", 16.0))
            result["markets"].append(price_market(kind, spec["line"], market_probability(mean, sigma, spec["line"], kind == "spread"), spec.get("price_a"), spec.get("price_b")))
        # Segment markets (Q1/H1): price spread + total + moneyline per segment
        # when the caller supplied auto-fetched lines. Tennis parity -- every
        # segment the feed prices gets an EV, not just the full game.
        seg_extra = self.market_lines.get("segment_markets") or {}
        for seg_name, seg_key in (("q1", "q1"), ("halftime", "h1")):
            seg = segments[seg_name]
            sline = self._market_line(seg_name)
            if sline is not None:
                seg["market_spread"] = sline
                seg["spread_edge"] = round(seg["projected_spread"] + sline, 2)
                seg["model_edge"] = seg["spread_edge"]
                result["markets"].append(price_market(
                    f"{seg_key}_spread", sline,
                    market_probability(seg["projected_spread"], seg["sigma"], sline, True),
                    seg_extra.get(f"{seg_key}_spread_home_price"),
                    seg_extra.get(f"{seg_key}_spread_away_price")))
            stotal = self.market_lines.get(f"{seg_key}_total")
            if stotal is not None:
                seg["market_total"] = float(stotal)
                seg["total_edge"] = round(seg["projected_total"] - float(stotal), 2)
                result["markets"].append(price_market(
                    f"{seg_key}_total", float(stotal),
                    market_probability(seg["projected_total"], seg["sigma"] * 1.45, float(stotal), False),
                    seg_extra.get(f"{seg_key}_over_price"),
                    seg_extra.get(f"{seg_key}_under_price")))
            hml = seg_extra.get(f"{seg_key}_home_ml")
            aml = seg_extra.get(f"{seg_key}_away_ml")
            if hml is not None or aml is not None:
                p = seg["home_moneyline_probability"]
                result["markets"].append(price_market(
                    f"{seg_key}_moneyline", 0.5, (p, 1 - p, 0), hml, aml))
        fml_h, fml_a = self.market_lines.get("home_ml"), self.market_lines.get("away_ml")
        if fml_h is not None or fml_a is not None:
            p = full["home_moneyline_probability"]
            result["markets"].append(price_market(
                "moneyline", 0.5, (p, 1 - p, 0), fml_h, fml_a))
        result["notes"] += " Spread is home-signed. Segment/total uncertainties are model assumptions unless fitted inputs are supplied; no calibrated confidence is claimed."
        result["segments"] = {"1q": segments["q1"], "ht": segments["halftime"], "fg": segments["full_game"]}
        return result


ROOT = Path(__file__).resolve().parent
EUROLEAGUE_STORE = ROOT / "data" / "euroleague_stats.json"
HOOPS_STORE = ROOT / "data" / "basketball_stats.json"
BLEAGUE_STORE = ROOT / "data" / "bleague_stats.json"

# CLI --league values that map onto the same underlying store slice.
# NOTE: Australian NBL ("NBL": Brisbane, Illawarra, ...) and New Zealand
# NBL ("NZ NBL": Wellington, Canterbury, ...) are DIFFERENT leagues with
# different teams. Do not merge them -- a cross-league fallback would
# dress foreign averages up as a prediction.
LEAGUE_ALIASES = {
    "euroleague": "EuroLeague",
    "euro league": "EuroLeague",
    "el": "EuroLeague",
    "kbl": "KBL",
    "bbl": "BBL",
    "bundesliga": "BBL",
    "german bbl": "BBL",
    "nbl": "NBL",
    "australian nbl": "NBL",
    "aus nbl": "NBL",
    "nbl27": "NBL",
    "nznbl": "NZ NBL",
    "nz nbl": "NZ NBL",
    "nz-nbl": "NZ NBL",
    "new zealand nbl": "NZ NBL",
    "bleague": "B League",
    "b league": "B League",
    "b.league": "B League",
    "b.premier": "B League",
    "b premier": "B League",
    "japan b league": "B League",
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
    if flat == "bleague":
        store = _load_store(BLEAGUE_STORE)
        teams = store.get("teams") if isinstance(store.get("teams"), dict) else store
        hit = _find_team(teams, team)
        if hit is None:
            whole = _load_store(HOOPS_STORE)
            hit = _find_team(_league_slice(whole, "B League"), team)
        if hit is None:
            known = sorted(n for n in teams if not n.startswith("_"))[:10]
            raise SystemExit(
                f"[STRICT-FAIL] '{team}' is not in {BLEAGUE_STORE.name} "
                f"for league '{league}'. Pass --home/away-ortg/drtg/pace "
                f"overrides or seed the store. Known: {', '.join(known)}")
        return hit
    if flat in ("kbl", "nznbl", "nbl"):
        tag = {"kbl": "KBL", "nznbl": "NZ NBL", "nbl": "NBL"}[flat]
        sliced = _league_slice(_load_store(HOOPS_STORE), tag)
        hit = _find_team(sliced, team)
        if hit is None:
            known = sorted(sliced)[:10]
            raise SystemExit(
                f"[STRICT-FAIL] '{team}' is not in {HOOPS_STORE.name} "
                f"under '{tag}'. No cross-league fallback is applied. Pass "
                f"overrides or seed the store. Known: {', '.join(known)}")
        return hit
    sliced = _league_slice(_load_store(HOOPS_STORE), canon)
    hit = _find_team(sliced, team)
    if hit is not None:
        return hit
    raise SystemExit(
        f"[STRICT-FAIL] League '{league}' has no team-metrics store. "
        f"Re-run with --home-ortg/--home-drtg/--home-pace and "
        f"--away-ortg/--away-drtg/--away-pace.")


def _league_baseline(league: str, home_stats, away_stats) -> Dict[str, Any]:
    canon = _normalise_league(league)
    flat = canon.lower().replace(".", "").replace(" ", "")
    if flat == "euroleague":
        base = _load_store(EUROLEAGUE_STORE).get("_league_baseline")
        if isinstance(base, dict):
            return dict(base)
    if flat == "bleague":
        base = _load_store(BLEAGUE_STORE).get("_league_baseline")
        if isinstance(base, dict):
            out = {"pace": 71.0, "ortg": 108.5, "drtg": 108.5,
                   "q1_ratio": 0.245, "ht_ratio": 0.495}
            out.update(base)
            return out
    if flat in ("kbl", "nznbl", "nbl"):
        tag = {"kbl": "KBL", "nznbl": "NZ NBL", "nbl": "NBL"}[flat]
        rows = _league_slice(_load_store(HOOPS_STORE), tag)
        paces = [float(r["pace"]) for r in rows.values() if r.get("pace")]
        ortgs = [float(r["ortg"]) for r in rows.values() if r.get("ortg")]
        if paces and ortgs:
            avg = round(sum(ortgs) / len(ortgs), 2)
            return {"pace": round(sum(paces) / len(paces), 2),
                    "ortg": avg, "drtg": avg,
                    "q1_ratio": 0.245, "ht_ratio": 0.495}
    pace = round((float(home_stats["pace"]) + float(away_stats["pace"])) / 2.0, 2)
    avg = sum(float(r[k]) for r in (home_stats, away_stats) for k in ("ortg", "drtg"))/4
    return {"pace": pace, "ortg": avg, "drtg": avg,
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
    p.add_argument("--game-date", default=None)
    p.add_argument("--push-discord", action="store_true")
    p.add_argument("--store-to-db", action="store_true")
    for flag in ("home-ml", "away-ml", "spread-home-price", "spread-away-price", "over-price", "under-price"):
        p.add_argument("--"+flag, type=float)
    for flag in ("q1-spread", "q1-total", "h1-spread", "h1-total"):
        p.add_argument("--"+flag, type=float, default=None,
                       help=f"Auto-fetched {flag} line (no manual entry needed).")
    p.add_argument("--segment-markets", type=str, default=None,
                   help="JSON with Q1/H1 moneyline + spread/total prices from auto-fetch.")
    p.add_argument("--alt-total", action="append", nargs=3, metavar=("LINE", "OVER_ODDS", "UNDER_ODDS"))
    p.add_argument("--alt-spread", action="append", nargs=3, metavar=("HOME_LINE", "HOME_ODDS", "AWAY_ODDS"))
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
        if not math.isfinite(v) or v <= 0:
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
    market_lines["total"] = ns.market_total
    for key in ("spread_home_price", "spread_away_price", "over_price", "under_price"):
        market_lines[key] = getattr(ns, key)
    if getattr(ns, "q1_spread", None) is not None:
        market_lines["q1"] = float(ns.q1_spread)
    if getattr(ns, "q1_total", None) is not None:
        market_lines["q1_total"] = float(ns.q1_total)
    if getattr(ns, "h1_spread", None) is not None:
        market_lines["halftime"] = float(ns.h1_spread)
    if getattr(ns, "h1_total", None) is not None:
        market_lines["h1_total"] = float(ns.h1_total)
    if getattr(ns, "segment_markets", None):
        try:
            market_lines["segment_markets"] = json.loads(ns.segment_markets)
        except (ValueError, TypeError):
            pass
    if getattr(ns, "home_ml", None) is not None:
        market_lines["home_ml"] = float(ns.home_ml)
    if getattr(ns, "away_ml", None) is not None:
        market_lines["away_ml"] = float(ns.away_ml)
    market_lines["alternatives"] = []
    for flag, kind in (("alt_total", "total"), ("alt_spread", "spread")):
        for line, a, b in getattr(ns, flag) or []:
            market_lines["alternatives"].append({"kind": kind, "line": float(line),
                "price_a": None if a.lower()=="none" else float(a), "price_b": None if b.lower()=="none" else float(b)})
    from data_guard import check_records
    for name, metrics, override in ((home_name, home_stats, home_over), (away_name, away_stats, away_over)):
        if override is None:
            issues = check_records({name: metrics}, "basketball")
            errors = [p.message for p in issues if p.severity == "error"]
            if errors:
                raise SystemExit("[STRICT-FAIL] " + "; ".join(errors))
    baseline = _league_baseline(league, home_stats, away_stats)
    predictor = EuroleaguePredictor(
        home_name, away_name, home_stats, away_stats,
        league_baseline=baseline, market_lines=market_lines)
    result = predictor.predict()
    result["league"] = league
    result["market_info"]["total"] = (float(ns.market_total)
                                      if ns.market_total is not None else None)
    result["notes"] += (
        f" {league} model using stored or supplied ORtg/DRtg/pace and assumed segment splits. "
        f"Strict-fail lookup: unlisted teams stop the run unless "
        f"--home/away-ortg/drtg/pace overrides are supplied.")

    if ns.home_ml is not None or ns.away_ml is not None:
        # Replace the engine's unpriced moneyline with the priced one so the same
        # market is never stored twice.
        result["markets"] = [m for m in result["markets"] if m.get("kind") != "moneyline"]
        from models.score_ratings import price_market
        p = result["full_game"]["home_moneyline_probability"]
        result["markets"].append(price_market("moneyline", 0.5, (p, 1-p, 0), ns.home_ml, ns.away_ml))
    for item in result["markets"]:
        print(f"{item['kind']} {item['line']}: {item['prob_a']:.1%}/{item['prob_b']:.1%}, push {item['push_prob']:.1%}; {item['recommendation']}")
    if ns.store_to_db:
        if not ns.game_date:
            raise SystemExit("--store-to-db requires --game-date YYYY-MM-DD for international basketball")
        from run_ncaaf import store
        from core.historical_storage import capture_prediction_odds
        projected = result["full_game"]
        payload = {"sport": "basketball", "league": league, "game_date": ns.game_date,
            "game_id": f"{league}:{ns.game_date}:{home_name}:{away_name}",
            "home_team": home_name, "away_team": away_name, "markets": result["markets"],
            "projection": {"home_points": projected["projected_home_points"], "away_points": projected["projected_away_points"]},
            # Tag the row with the workflow run so saved-review lookup can find it.
            "_workflow_run_id": os.environ.get("MSP_RUN_ID"),
            "model_result": result}
        store(payload)
        # The exact prices this forecast used, archived immutably for CLV.
        refused = capture_prediction_odds(payload)["refused"]
        if refused:
            print(f"[WARN] Odds snapshot refused: {refused}")
    if ns.push_discord:
        from universal_runner import _push_full_result
        if not _push_full_result("basketball", home_name, away_name, result):
            raise SystemExit("Discord push failed")
    if ns.output_json is not None:
        out = ns.output_json
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            raise SystemExit(f"[ERROR] Could not write {out}: {exc}")
        print(f"[+] Wrote prediction to {out}")
    elif ns.store_to_db:
        # A saved workflow run gets a readable card, not a raw dictionary dump.
        fg = result["full_game"]
        print("")
        print("=" * 78)
        print(f"{league.upper()}  {ns.game_date}  |  {home_name} (home) vs {away_name} (away)")
        print("=" * 78)
        print(f"Projected: {home_name} {fg['projected_home_points']:.1f} | "
              f"{away_name} {fg['projected_away_points']:.1f} "
              f"(total {fg['projected_total_points']:.1f})")
        if fg.get("market_spread") is not None:
            print(f"Market spread {fg['market_spread']:+.1f} | model edge {fg.get('spread_edge')}")
        for item in result["markets"]:
            print(f"  {item['kind']:<10} {item.get('recommendation')}")
        print("Probabilities are uncalibrated model estimates, not proven betting returns.")
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
