"""Source-backed player observations and explicitly chosen Elo scenarios."""
import datetime as dt
import json
import math
from pathlib import Path
from sports_feed import today


def apply_context(home, away, probability, context=None):
    result = {"baseline_probability": probability, "observations": {}, "scenario": False}
    if context is not None and (not isinstance(context, dict) or not isinstance(context.get("players", {}), dict)):
        raise ValueError("Context must be a JSON object containing a players object")
    if not 0 < probability < 1:
        raise ValueError("Baseline probability must be between zero and one")
    adjustments = {}
    for name in (home, away):
        item = (context or {}).get("players", {}).get(name)
        if item is None:
            continue
        if not isinstance(item, dict) or not str(item.get("source", "")).startswith(("https://", "http://")):
            raise ValueError(f"{name}: context needs a source URL")
        stamp = dt.date.fromisoformat(str(item.get("as_of", ""))[:10])
        age = (dt.date.fromisoformat(today())-stamp).days
        if age < 0 or age > 2:
            raise ValueError(f"{name}: context must be sourced within the last two days")
        status = str(item.get("injury_status", "unknown")).lower()
        if status in {"out", "withdrawn"}:
            raise ValueError(f"{name} is reported {status}; refusing a scheduled-match prediction")
        value = item.get("elo_adjustment", 0)
        value = float(value)
        if not math.isfinite(value) or abs(value) > 150:
            raise ValueError("Scenario Elo adjustment must be finite and within +/-150")
        if value and not item.get("adjustment_reason"):
            raise ValueError(f"{name}: a numeric scenario needs an adjustment_reason")
        adjustments[name] = value
        result["observations"][name] = item
    delta = adjustments.get(home, 0)-adjustments.get(away, 0)
    result["scenario"] = any(adjustments.values())
    if delta:
        log_odds = math.log10(probability/(1-probability)) + delta/400
        probability = 1/(1+10**(-log_odds))
        result["scenario"] = True
    result["adjusted_probability"] = probability
    result["elo_delta"] = delta
    result["note"] = "Observations do not imply measured effects. Numeric Elo changes are user scenarios, not trained injury/travel coefficients."
    return probability, result


def serve_profiles(matches):
    cutoff = dt.date.fromisoformat(today())-dt.timedelta(days=365)
    output = {}
    for m in matches:
        if dt.date.fromisoformat(m.date) < cutoff:
            continue
        for name, svpt, svwon, opponent_pt, opponent_won in (
            (m.winner, m.w_svpt, m.w_svwon, m.l_svpt, m.l_svwon),
            (m.loser, m.l_svpt, m.l_svwon, m.w_svpt, m.w_svwon)):
            if any(x is None for x in (svpt, svwon, opponent_pt, opponent_won)):
                continue
            if not (0 <= svwon <= svpt and 0 <= opponent_won <= opponent_pt):
                continue
            slot = output.setdefault(name, {}).setdefault(m.surface, dict(serve_points=0, serve_won=0, return_points=0, return_won=0, matches=0))
            slot["serve_points"] += svpt
            slot["serve_won"] += svwon
            slot["return_points"] += opponent_pt
            slot["return_won"] += opponent_pt-opponent_won
            slot["matches"] += 1
    return {"updated": today(), "source": "TennisMyLife per-match point counts", "window_days": 365, "players": output}


def hold_probability(p):
    q = 1-p
    return p**4*(1+4*q+10*q*q)+20*p**3*q**3*p*p/(p*p+q*q)


def matchup_holds(home, away, surface):
    path = Path(__file__).resolve().parent / "data/tennis/serve_return.json"
    if not path.exists():
        return None
    stored = json.loads(path.read_text(encoding="utf-8"))
    age = (dt.date.fromisoformat(today())-dt.date.fromisoformat(stored["updated"])).days
    if age < 0 or age > 14:
        return None
    profiles = stored["players"]
    a, b = profiles.get(home, {}).get(surface), profiles.get(away, {}).get(surface)
    if not a or not b or min(a["serve_points"], b["serve_points"], a["return_points"], b["return_points"]) < 200:
        return None
    pa = (a["serve_won"]/a["serve_points"] + 1-b["return_won"]/b["return_points"])/2
    pb = (b["serve_won"]/b["serve_points"] + 1-a["return_won"]/a["return_points"])/2
    return {"home_hold": hold_probability(pa), "away_hold": hold_probability(pb),
            "home_serve_point_probability": pa, "away_serve_point_probability": pb,
            "source": "Measured 365-day surface serve/return point rates; unadjusted for opponent strength",
            "home_matches": a["matches"], "away_matches": b["matches"]}


def workload_observations(home, away):
    """Observed recent play; arrival, injuries and stadium effects stay unknown."""
    import csv
    path = Path(__file__).resolve().parent / "data/tennis/matches.csv"
    now = dt.date.fromisoformat(today())
    rows = {home: [], away: []}
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            date = dt.date.fromisoformat(row["tournament_date"])
            if date >= now:
                continue
            for name in rows:
                if name in (row["winner_name"], row["loser_name"]):
                    rows[name].append((date, row.get("tournament", "")))
    output = {}
    for name, history in rows.items():
        if not history:
            continue
        history.sort()
        latest, venue = history[-1]
        output[name] = {"last_recorded_match": latest.isoformat(),
            "days_since_recorded_match": (now-latest).days,
            "matches_last_7_days": sum(0 < (now-d).days <= 7 for d, _ in history),
            "matches_last_14_days": sum(0 < (now-d).days <= 14 for d, _ in history),
            "last_recorded_tournament": venue,
            "source": "Local sourced results; archive dates can be tournament starts",
            "note": "Observed workload only; travel/arrival and causal fatigue effect are unknown"}
    return output
