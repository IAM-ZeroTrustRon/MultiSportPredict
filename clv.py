"""Closing line value from archived odds snapshots.

Two facts are kept apart on purpose:

  * exact-line CLV -- the same market and the same line, priced before kickoff.
    Positive means the archived prediction price was better than the close.
  * line movement -- the line itself changed. A price delta across different
    lines is not closing line value, so no CLV number is reported for it.

A closing capture observed at or after kickoff is refused, not reported: an
in-play price is not a closing line.

USAGE
    python clv.py
    python clv.py --sport nhl --json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math

from core.historical_storage import DB_PATH, get_odds_snapshots
from core.market_handicapper import american_to_decimal, devig_market

LINE_TOLERANCE = 1e-9
DEVIG_METHOD = "power"
INTEGER_LINE_MARKETS = {"spread", "total"}


def _stamp(value, field="timestamp"):
    if value is None:
        return None
    try:
        stamp = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{field} is not an ISO-8601 timestamp")
    if stamp.tzinfo is None:
        raise ValueError(f"{field} has no timezone")
    return stamp.astimezone(dt.timezone.utc)


def _decimal(price, label):
    if price is None or isinstance(price, bool):
        raise ValueError(f"{label} price is missing")
    value = float(price)
    if not math.isfinite(value) or abs(value) < 100:
        raise ValueError(f"{label} must be American odds of at least 100 in magnitude")
    return american_to_decimal(value)


def _same_line(left, right):
    if left is None or right is None:
        return left is None and right is None
    return abs(float(left) - float(right)) <= LINE_TOLERANCE


def _mean(values):
    return sum(values) / len(values) if values else None


def fair_probabilities(snapshot):
    """Vig-free probabilities for this pair, or (None, None) where it is not binary.

    An integer spread/total line carries push mass, so its two prices are not a
    two-outcome market and are not de-vigged into one.
    """
    if snapshot.get("market_type") in INTEGER_LINE_MARKETS:
        line = snapshot.get("line")
        if line is not None and float(line).is_integer():
            return None, None
    try:
        fair = devig_market([float(snapshot["price_a"]), float(snapshot["price_b"])],
                            method=DEVIG_METHOD)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None, None
    if len(fair) != 2 or any(not math.isfinite(p) or not 0 < p < 1 for p in fair):
        return None, None
    return fair[0], fair[1]


def _contract(snapshot):
    """Only the same event, orientation, bookmaker, scope and period may pair."""
    from core.historical_storage import odds_fixture_key
    required = ("sport", "league", "source_event_id", "bookmaker", "scope", "home_team", "away_team")
    if any(not str(snapshot.get(k) or "").strip() for k in required):
        raise ValueError("Snapshot lacks verified event/bookmaker/settlement identity")
    payload = snapshot.get("payload") if isinstance(snapshot.get("payload"), dict) else {}
    return (str(snapshot["sport"]).lower(), str(snapshot["league"]).upper(),
            str(snapshot["source_event_id"]), snapshot["market_type"],
            odds_fixture_key(snapshot["league"], None, snapshot["home_team"], snapshot["away_team"]),
            snapshot["bookmaker"], snapshot["scope"], payload.get("period") or "full_game")


def compare_snapshots(prediction, closing):
    """Compare one prediction capture with one closing capture.

    Returns {"comparison": "exact_line" | "line_moved" | "refused_in_play"}.
    """
    if prediction.get("capture_kind") != "prediction" or closing.get("capture_kind") != "closing":
        raise ValueError("CLV compares a prediction capture with a closing capture")
    if _contract(prediction) != _contract(closing):
        raise ValueError("Snapshots must match event, teams, bookmaker, market, period and settlement scope")
    if not prediction.get("kickoff_utc") or not closing.get("kickoff_utc"):
        raise ValueError("Both snapshots require verified kickoff timestamps")
    if _stamp(prediction["kickoff_utc"]) != _stamp(closing["kickoff_utc"]):
        raise ValueError("Kickoff changed; explicit verified reschedule linkage required")
    for snapshot in (prediction, closing):
        updated = _stamp(snapshot.get("quote_updated_utc"))
        observed = _stamp(snapshot.get("observed_utc"))
        if updated is None or observed is None:
            raise ValueError("Both captures require provider update and observation timestamps")
        if updated >= _stamp(snapshot["kickoff_utc"]):
            return {"comparison":"refused_in_play","event_key":snapshot.get("event_key"),
                    "market_type":snapshot.get("market_type"),"reason":"bookmaker quote published at or after kickoff"}
        if (updated-observed).total_seconds() > 5:
            raise ValueError("Invalid future bookmaker publication time")
    if _stamp(closing.get("observed_utc")) <= _stamp(prediction.get("observed_utc")):
        raise ValueError("Closing capture must be observed after the prediction capture")

    kickoff = closing.get("kickoff_utc")
    if kickoff is not None:
        kickoff_stamp = _stamp(kickoff, "kickoff_utc")
        if _stamp(closing.get("observed_utc")) >= kickoff_stamp:
            return {"comparison": "refused_in_play", "event_key": closing.get("event_key"),
                    "market_type": closing.get("market_type"),
                    "reason": "closing capture observed at or after kickoff"}
        if _stamp(prediction.get("observed_utc")) >= kickoff_stamp:
            return {"comparison": "refused_in_play", "event_key": prediction.get("event_key"),
                    "market_type": prediction.get("market_type"),
                    "reason": "prediction capture observed at or after kickoff"}

    base = {"event_key": closing.get("event_key"), "market_type": closing.get("market_type"),
            "line": prediction.get("line"),
            "prediction_observed_utc": prediction.get("observed_utc"),
            "closing_observed_utc": closing.get("observed_utc"),
            "bookmaker": closing.get("bookmaker"),
            "closing_reference": "Last observed eligible prematch quote from the same bookmaker; not guaranteed market close",
            "closing_lead_minutes": (_stamp(closing["kickoff_utc"])-_stamp(closing["observed_utc"])).total_seconds()/60,
            "run_id": (prediction.get("payload") or {}).get("run_id")}

    if not _same_line(prediction.get("line"), closing.get("line")):
        return {**base, "comparison": "line_moved",
                "prediction_line": prediction.get("line"), "closing_line": closing.get("line"),
                "delta": float(closing.get("line")) - float(prediction.get("line")),
                "note": ("The line changed, so the price change is not CLV and is not "
                         "reported as a number. Move the forecast to the closing line to "
                         "compare like with like.")}

    fair_open = fair_probabilities(prediction)
    fair_close = fair_probabilities(closing)
    sides = {}
    for index, side in enumerate(("a", "b")):
        open_decimal = _decimal(prediction.get("price_" + side), "prediction")
        close_decimal = _decimal(closing.get("price_" + side), "closing")
        record = {"side": side, "prediction_price": prediction.get("price_" + side),
                  "closing_price": closing.get("price_" + side),
                  "prediction_decimal": open_decimal, "closing_decimal": close_decimal,
                  # Positive when the archived prediction price beat the close.
                  "price_clv": open_decimal / close_decimal - 1.0,
                  "fair_prob_clv_pp": None, "fair_price_clv": None}
        if fair_open[0] is not None and fair_close[0] is not None:
            record["fair_prob_clv_pp"] = (fair_close[index] - fair_open[index]) * 100.0
            record["fair_price_clv"] = open_decimal * fair_close[index] - 1.0
        sides[side] = record
    return {**base, "comparison": "exact_line", "sides": sides}


def clv_report(db_path=None, sport=None):
    """Aggregate exact-line CLV and line movement from the snapshot archive."""
    snapshots = get_odds_snapshots(db_path, sport=sport)
    groups = {}; unverified = 0
    for snapshot in snapshots:
        try:
            contract = _contract(snapshot)
        except ValueError:
            unverified += 1
            continue
        groups.setdefault(contract, []).append(snapshot)
    comparisons = []
    exact = {"n": 0, "price_clv": {"a": [], "b": []},
             "fair_pp": {"a": [], "b": []}, "positive": {"a": 0, "b": 0},
             "priced": {"a": 0, "b": 0}}
    movement = {"n": 0, "delta": [], "by_market": {}}
    unmatched = {"no_prediction_snapshot": 0, "no_closing_snapshot": 0,
                 "unverified_identity": unverified, "invalid_comparison": 0}
    refused_in_play = 0
    for contract, rows in sorted(groups.items(), key=lambda item: str(item[0])):
        openings = [r for r in rows if r["capture_kind"] == "prediction"]
        if not openings:
            unmatched["no_prediction_snapshot"] += 1
            continue
        # Each immutable run/line is an observation. Do not discard alternatives
        # or silently substitute an older run's prices for the requested run.
        for opening in openings:
            eligible = []
            for candidate in (r for r in rows if r["capture_kind"] == "closing"):
                if _stamp(candidate["observed_utc"]) <= _stamp(opening["observed_utc"]):
                    continue
                if not candidate.get("kickoff_utc") or _stamp(candidate["observed_utc"]) >= _stamp(candidate["kickoff_utc"]):
                    refused_in_play += 1
                    continue
                eligible.append(candidate)
            if not eligible:
                unmatched["no_closing_snapshot"] += 1
                continue
            # The latest observation defines the reference. Choosing an older
            # same-line quote hides subsequent line movement and biases CLV.
            closing = max(eligible, key=lambda r: (_stamp(r["observed_utc"]), _stamp(r["created_utc"])))
            try:
                result = compare_snapshots(opening, closing)
            except (ValueError, TypeError):
                unmatched["invalid_comparison"] += 1
                continue
            comparisons.append(result)
            if result["comparison"] == "exact_line":
                exact["n"] += 1
                for side in ("a", "b"):
                    record = result["sides"][side]
                    exact["priced"][side] += 1
                    exact["price_clv"][side].append(record["price_clv"])
                    if record["price_clv"] > 0: exact["positive"][side] += 1
                    if record["fair_prob_clv_pp"] is not None:
                        exact["fair_pp"][side].append(record["fair_prob_clv_pp"])
            elif result["comparison"] == "line_moved":
                movement["n"] += 1
                movement["delta"].append(result["delta"])
                movement["by_market"][result["market_type"]] = movement["by_market"].get(result["market_type"], 0) + 1
            else:
                refused_in_play += 1

    exact_summary = {
        "n": exact["n"],
        "mean_price_clv_a": _mean(exact["price_clv"]["a"]),
        "mean_price_clv_b": _mean(exact["price_clv"]["b"]),
        "share_positive_a": (exact["positive"]["a"] / exact["priced"]["a"]
                             if exact["priced"]["a"] else None),
        "share_positive_b": (exact["positive"]["b"] / exact["priced"]["b"]
                             if exact["priced"]["b"] else None),
        "mean_fair_prob_clv_pp_a": _mean(exact["fair_pp"]["a"]),
        "mean_fair_prob_clv_pp_b": _mean(exact["fair_pp"]["b"]),
        "fair_prob_sides": {"a": len(exact["fair_pp"]["a"]), "b": len(exact["fair_pp"]["b"])},
        "basis": ("Same market, same line, both quotes archived strictly before kickoff. "
                  "Positive means the captured price beat the last observed same-bookmaker prematch reference; not guaranteed close."),
    }
    movement_summary = {
        "n": movement["n"],
        "mean_delta": _mean(movement["delta"]),
        "mean_abs_delta": _mean([abs(d) for d in movement["delta"]]),
        "by_market": movement["by_market"],
        "basis": ("The line changed between capture and close. No CLV number is computed "
                  "across different lines; these are reported as movement only."),
    }
    return {
        "snapshots": len(snapshots),
        "groups": len(groups),
        "exact_line": exact_summary,
        "line_movement": movement_summary,
        "refused_in_play": refused_in_play,
        "unmatched": unmatched,
        "comparisons": comparisons,
        "note": ("Descriptive quote observations, not independent bets or results/ROI evidence. "
                 "Empty results mean no compatible last-observed prematch reference is available, not zero CLV. "
                 "The collector is not scheduled; see docs/ODDS_CLV_SCHEDULER_PROPOSAL.md."),
    }


def _format(report):
    lines = [f"Snapshots: {report['snapshots']}  groups: {report['groups']}"]
    exact = report["exact_line"]
    lines.append(f"Exact-line comparisons: {exact['n']}")
    for side in ("a", "b"):
        mean = exact[f"mean_price_clv_{side}"]
        share = exact[f"share_positive_{side}"]
        lines.append(f"  side {side}: mean price CLV "
                     f"{'n/a' if mean is None else f'{mean:+.2%}'}, "
                     f"beat close {'n/a' if share is None else f'{share:.0%}'}")
    movement = report["line_movement"]
    lines.append(f"Line-movement comparisons: {movement['n']}"
                 + ("" if movement["mean_delta"] is None
                    else f"  mean delta {movement['mean_delta']:+.2f}"))
    lines.append(f"Refused in-play closes: {report['refused_in_play']}")
    lines.append(f"Unmatched: {report['unmatched']}")
    return "\n".join(lines)


def main(argv=None):
    import sys
    if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sport", help="Limit to one sport, for example nhl")
    parser.add_argument("--json", action="store_true", help="Print the full report as JSON")
    parser.add_argument("--db", help="Database path (defaults to the canonical database)")
    args = parser.parse_args(argv)
    report = clv_report(args.db or DB_PATH, sport=args.sport)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(_format(report))
    return report


if __name__ == "__main__":
    main()
