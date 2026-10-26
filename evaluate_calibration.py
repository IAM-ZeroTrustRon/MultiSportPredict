"""Chronological probability calibration report for saved predictions.

Answers one question the ledger cannot: are the model's probabilities
calibrated, and does a larger claimed edge actually predict a better result?

Everything is computed from rows already stored in multisport_history.db. No
model is refitted, no probability is rewritten, nothing is graded and no price
is fetched. Pushes are excluded from win/loss metrics and counted separately.

Alignment
---------
A row is only scored against the market entry for its OWN market AND line.
A spread row also stores a moneyline entry (and alternate totals share a kind),
so matching on kind alone prices a selection off a market it never settled on.

Chronology is enforced, never shuffled:
  * rows are ordered by (game_date, id)
  * every split is a whole-date boundary, so no fixture can sit in both the
    training and the evaluation side of a split
  * the isotonic check fits on the earliest 60% of dates and scores the newest
    40%, so the corrected probabilities it reports are genuinely out-of-sample
  * a first-half / second-half table shows whether the miscalibration is
    drifting or steady

Large model-vs-market gaps are labelled MODEL/MARKET DISCREPANCY and reported
neutrally. They are not a gate, and neither the model nor the market is
assumed correct.

Usage:
    venv/Scripts/python.exe -u evaluate_calibration.py
    venv/Scripts/python.exe -u evaluate_calibration.py --sport ncaaf
    venv/Scripts/python.exe -u evaluate_calibration.py --json
"""
import argparse
import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path

from probability_signal import (HIGH_PROBABILITY_THRESHOLD,
                               picked_side_signal)

DB = Path(__file__).resolve().parent / "multisport_history.db"
BINS = [(0.0, 0.4), (0.4, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.01)]
EV_BUCKETS = [(0.05, 0.10), (0.10, 0.20), (0.20, 0.35), (0.35, 0.60), (0.60, 99.0)]
DISCREPANCY_PERCENTILE = 0.90   # descriptive cut, computed from the data
MIN_ISOTONIC = 40               # below this, a fitted curve is noise
TRAIN_FRACTION = 0.60


def decimal(price):
    price = float(price)
    if price > 0:
        return 1.0 + price / 100.0
    if price < 0:
        return 1.0 + 100.0 / abs(price)
    raise ValueError("American odds cannot be 0")


def devig(price_a, price_b):
    """Power de-vig via the repo implementation; None when it cannot apply."""
    from core.market_handicapper import devig_power, implied_probability
    try:
        fair = devig_power([implied_probability(price_a), implied_probability(price_b)])
    except (ValueError, TypeError, ZeroDivisionError):
        return None
    if len(fair) != 2 or any(not math.isfinite(p) or not 0 < p < 1 for p in fair):
        return None
    return fair


def load_rows(db, sport=None):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    rows = list(conn.execute(
        "SELECT * FROM predictions WHERE result_outcome IN ('win','loss','push') "
        "ORDER BY game_date, id"))
    conn.close()
    if sport:
        rows = [r for r in rows if (r["sport"] or "").lower() == sport.lower()]
    return rows


def build(db, sport=None):
    rows = load_rows(db, sport)
    bets, skipped, pushes = [], defaultdict(int), 0
    for row in rows:
        recommendation = (row["recommendation"] or "").upper()
        if recommendation.startswith(("PASS", "INFO", "VOID")):
            skipped["not a selection"] += 1
            continue
        try:
            raw = json.loads(row["raw_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            skipped["unreadable raw_json"] += 1
            continue
        if not isinstance(raw, dict):
            skipped["unreadable raw_json"] += 1
            continue
        market_type = (row["market_type"] or "").strip().lower()
        # market_value holds the line for spread/total and 0.5 for moneyline.
        line = row["market_value"] if market_type in ("spread", "total") else None
        signal = picked_side_signal(market_type, raw, line=line,
                                    recommendation=row["recommendation"])
        if signal is None:
            skipped["no recoverable side+probability"] += 1
            continue
        if row["result_outcome"] == "push":
            pushes += 1
            continue
        odds = raw.get("market_odds") or {}
        price_pair = (signal.get("price"), signal.get("price_other"))
        fair = devig(*price_pair) if all(p is not None for p in price_pair) else None
        if fair is not None:
            # fair[0] belongs to price_a; the picked side may be either one.
            picked_first = str(signal.get("pick")) in ("HOME", "OVER")
            market_p = fair[0] if picked_first else fair[1]
        elif signal.get("price") is not None:
            market_p = 1.0 / decimal(signal["price"])
        else:
            market_p = None
        if market_p is None:
            skipped["no recoverable price for the picked side"] += 1
            continue
        bets.append(dict(
            sport=(row["sport"] or "?").lower(), market=market_type or "?",
            game_date=row["game_date"], won=1 if row["result_outcome"] == "win" else 0,
            probability=float(signal["probability"]), price=signal.get("price"),
            price_pair=price_pair, market_p=market_p, source=signal.get("source"),
            claimed_ev=signal.get("ev") if signal.get("ev") is not None
            else _claimed_ev(signal["probability"], signal.get("price")),
            profit_loss=row["profit_loss"], id=row["id"],
            pick=signal.get("pick")))
    return bets, dict(skipped), pushes


def _claimed_ev(probability, price):
    if price is None or probability is None:
        return None
    try:
        return probability * (decimal(price) - 1.0) - (1.0 - probability)
    except (TypeError, ValueError):
        return None


def brier(pairs):
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs) if pairs else None


def ece(pairs, bins=BINS):
    total = len(pairs)
    if not total:
        return None
    acc = 0.0
    for low, high in bins:
        bucket = [(p, y) for p, y in pairs if low <= p < high]
        if not bucket:
            continue
        mean_p = sum(p for p, _ in bucket) / len(bucket)
        mean_y = sum(y for _, y in bucket) / len(bucket)
        acc += len(bucket) / total * abs(mean_p - mean_y)
    return acc


def roi(bets):
    """Mean units per selection, preferring the grader's own settlement."""
    if not bets:
        return None
    settled = [b["profit_loss"] for b in bets if b.get("profit_loss") is not None]
    if len(settled) == len(bets):
        return sum(settled) / len(settled)
    return sum((decimal(b["price"]) - 1.0) if b["won"] else -1.0 for b in bets) / len(bets)


def date_boundary(bets, fraction):
    """First date index whose cumulative share reaches `fraction`.

    Splitting on a date rather than a row means no fixture (and no same-day
    slate) can appear on both sides of the split.
    """
    dates = sorted({b["game_date"] for b in bets if b["game_date"]})
    if len(dates) < 2:
        return None
    counts = defaultdict(int)
    for b in bets:
        counts[b["game_date"]] += 1
    target, running = fraction * len(bets), 0
    for date in dates:
        running += counts[date]
        if running >= target:
            return date
    return dates[-1]


def split_by_date(bets, boundary):
    train = [b for b in bets if b["game_date"] < boundary]
    test = [b for b in bets if b["game_date"] >= boundary]
    return train, test


def group_metrics(bets, key):
    groups = defaultdict(list)
    for bet in bets:
        groups[bet[key]].append(bet)
    out = []
    for name in sorted(groups):
        part = groups[name]
        pairs = [(b["probability"], b["won"]) for b in part]
        market_pairs = [(b["market_p"], b["won"]) for b in part]
        out.append(dict(
            name=name, n=len(part),
            mean_predicted=sum(p for p, _ in pairs) / len(pairs),
            realised=sum(y for _, y in pairs) / len(pairs),
            brier=brier(pairs), market_brier=brier(market_pairs),
            ece=ece(pairs), market_ece=ece(market_pairs), flat_roi=roi(part)))
    return out


def isotonic_holdout(bets):
    """Fit on the earliest dates, score the latest: no lookahead."""
    if len(bets) < MIN_ISOTONIC:
        return None
    boundary = date_boundary(bets, TRAIN_FRACTION)
    if boundary is None:
        return None
    train, test = split_by_date(bets, boundary)
    if len(train) < MIN_ISOTONIC // 2 or not test or len({b["won"] for b in train}) < 2:
        return None
    from sklearn.isotonic import IsotonicRegression
    model = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    model.fit([b["probability"] for b in train], [b["won"] for b in train])
    raw_pairs = [(b["probability"], b["won"]) for b in test]
    fitted_pairs = [(float(model.predict([b["probability"]])[0]), b["won"]) for b in test]
    return dict(boundary=boundary, train=len(train), test=len(test),
                brier_before=brier(raw_pairs), brier_after=brier(fitted_pairs),
                ece_before=ece(raw_pairs), ece_after=ece(fitted_pairs),
                market_brier=brier([(b["market_p"], b["won"]) for b in test]))


def _quantile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(fraction * (len(ordered) - 1)))))
    return ordered[index]


def report(bets, skipped, pushes, sport=None):
    pairs = [(b["probability"], b["won"]) for b in bets]
    market_pairs = [(b["market_p"], b["won"]) for b in bets]
    discrepancies = [abs(b["probability"] - b["market_p"]) for b in bets]
    cut = _quantile(discrepancies, DISCREPANCY_PERCENTILE)
    flagged = [b for b in bets if abs(b["probability"] - b["market_p"]) >= cut] if cut else []
    out = {
        "sport": sport or "all",
        "settled_selections": len(bets),
        "pushes_excluded": pushes,
        "excluded": skipped,
        "sources": dict(sorted(_count_by(bets, "source").items())),
        "markets": dict(sorted(_count_by(bets, "market").items())),
        "date_range": [bets[0]["game_date"], bets[-1]["game_date"]] if bets else [None, None],
        "model_brier": brier(pairs),
        "market_brier": brier(market_pairs),
        "model_ece": ece(pairs),
        "market_ece": ece(market_pairs),
        "mean_model_p": sum(p for p, _ in pairs) / len(pairs) if pairs else None,
        "realised_win_rate": sum(y for _, y in pairs) / len(pairs) if pairs else None,
        "flat_roi": roi(bets),
        "high_probability": {
            "threshold": HIGH_PROBABILITY_THRESHOLD,
            "n": sum(1 for b in bets if b["probability"] >= HIGH_PROBABILITY_THRESHOLD),
            "realised": (sum(b["won"] for b in bets
                             if b["probability"] >= HIGH_PROBABILITY_THRESHOLD)
                         / max(1, sum(1 for b in bets
                                      if b["probability"] >= HIGH_PROBABILITY_THRESHOLD))),
        },
        "buckets": [],
        "by_sport": group_metrics(bets, "sport"),
        "by_market": group_metrics(bets, "market"),
        "edge_buckets": [],
        "halves": [],
        "discrepancy": {
            "cut": cut,
            "flagged": len(flagged),
            "label": "MODEL/MARKET DISCREPANCY",
            "note": ("largest observed model-vs-market gaps; descriptive only, "
                     "neither score is treated as correct"),
        },
        "isotonic": isotonic_holdout(bets),
    }
    for low, high in BINS:
        bucket = [b for b in bets if low <= b["probability"] < high]
        if not bucket:
            continue
        out["buckets"].append(dict(
            range=f"{low:.2f}-{min(high, 1.0):.2f}", n=len(bucket),
            mean_predicted=sum(b["probability"] for b in bucket) / len(bucket),
            realised=sum(b["won"] for b in bucket) / len(bucket),
            gap=(sum(b["won"] for b in bucket) - sum(b["probability"] for b in bucket)) / len(bucket)))
    for low, high in EV_BUCKETS:
        bucket = [b for b in bets if b["claimed_ev"] is not None and low <= b["claimed_ev"] < high]
        if not bucket:
            continue
        out["edge_buckets"].append(dict(
            range=f"{low:.0%}-{high if high < 90 else 99:.0%}", n=len(bucket),
            mean_claimed_ev=sum(b["claimed_ev"] for b in bucket) / len(bucket),
            realised_win_rate=sum(b["won"] for b in bucket) / len(bucket),
            mean_implied=sum(b["market_p"] for b in bucket) / len(bucket),
            flat_roi=roi(bucket)))
    if len(bets) >= 2 * MIN_ISOTONIC:
        boundary = date_boundary(bets, 0.5)
        if boundary:
            for label, part in (("earlier half", [b for b in bets if b["game_date"] < boundary]),
                                ("later half", [b for b in bets if b["game_date"] >= boundary])):
                if not part:
                    continue
                half_pairs = [(b["probability"], b["won"]) for b in part]
                out["halves"].append(dict(
                    half=label, n=len(part),
                    dates=f"{part[0]['game_date']}..{part[-1]['game_date']}",
                    mean_predicted=sum(p for p, _ in half_pairs) / len(half_pairs),
                    realised=sum(y for _, y in half_pairs) / len(half_pairs),
                    brier=brier(half_pairs),
                    market_brier=brier([(b["market_p"], b["won"]) for b in part])))
    return out


def _count_by(bets, key):
    counts = defaultdict(int)
    for b in bets:
        counts[b[key]] += 1
    return counts


def _metric_row(label, n, predicted, realised, brier_score, market_brier, ece_score, flat_roi):
    roi_text = f"{flat_roi:>+9.1%}" if flat_roi is not None else f"{'--':>9}"
    return (f"{label:16s}{n:>5d}{predicted:>10.3f}{realised:>10.3f}"
            f"{brier_score:>9.4f}{market_brier:>9.4f}{ece_score:>9.4f}{roi_text}")


def print_group(title, groups):
    print(f"\n{title}")
    print(f"{'':16s}{'n':>5s}{'predicted':>10s}{'realised':>10s}"
          f"{'brier':>9s}{'mkt':>9s}{'ece':>9s}{'ROI':>9s}")
    for g in groups:
        print(_metric_row(g["name"], g["n"], g["mean_predicted"], g["realised"],
                          g["brier"], g["market_brier"], g["ece"], g["flat_roi"]))


def print_report(result):
    print(f"\nCalibration report - {result['sport']}  "
          f"({result['date_range'][0]} .. {result['date_range'][1]})")
    print(f"settled selections: {result['settled_selections']}  "
          f"pushes excluded: {result['pushes_excluded']}  "
          f"sources: {result['sources']}")
    if not result["settled_selections"]:
        print("No usable selections with a recoverable probability and price.")
        return
    print(f"\n{'':26s}{'model':>10s}{'market':>10s}")
    print(f"{'Brier (lower better)':26s}{result['model_brier']:>10.4f}{result['market_brier']:>10.4f}")
    print(f"{'ECE (lower better)':26s}{result['model_ece']:>10.4f}{result['market_ece']:>10.4f}")
    print(f"{'mean probability':26s}{result['mean_model_p']:>10.3f}{'':>10s}")
    print(f"{'realised win rate':26s}{result['realised_win_rate']:>10.3f}{'':>10s}")
    print(f"{'flat 1u ROI':26s}{result['flat_roi']:>10.2%}{'':>10s}")
    hp = result["high_probability"]
    print(f"{'>=' + format(hp['threshold'], '.0%') + ' selections':26s}{hp['n']:>10d}"
          f"{'realised ' + format(hp['realised'], '.1%'):>21s}")

    print_group("by sport", result["by_sport"])
    print_group("by market", result["by_market"])

    print(f"\nreliability by predicted probability")
    print(f"{'bucket':12s}{'n':>5s}{'predicted':>11s}{'realised':>10s}{'gap':>8s}")
    for b in result["buckets"]:
        print(f"{b['range']:12s}{b['n']:>5d}{b['mean_predicted']:>11.3f}"
              f"{b['realised']:>10.3f}{b['gap']:>+8.3f}")

    print(f"\ndoes a bigger claimed edge help? (claimed EV quintiles)")
    print(f"{'claimed EV':12s}{'n':>5s}{'mean claim':>12s}{'market implied':>15s}{'realised':>10s}{'ROI':>9s}")
    for b in result["edge_buckets"]:
        print(f"{b['range']:12s}{b['n']:>5d}{b['mean_claimed_ev']:>12.1%}"
              f"{b['mean_implied']:>15.3f}{b['realised_win_rate']:>10.3f}{b['flat_roi']:>+9.1%}")

    if result["halves"]:
        print(f"\nstability (whole-date halves, never shuffled)")
        print(f"{'half':14s}{'n':>5s}{'dates':>24s}{'predicted':>11s}{'realised':>10s}{'brier':>8s}{'mkt':>8s}")
        for h in result["halves"]:
            print(f"{h['half']:14s}{h['n']:>5d}{h['dates']:>24s}{h['mean_predicted']:>11.3f}"
                  f"{h['realised']:>10.3f}{h['brier']:>8.4f}{h['market_brier']:>8.4f}")

    discrepancy = result["discrepancy"]
    if discrepancy["cut"] is not None:
        print(f"\n{discrepancy['label']}")
        print(f"  {discrepancy['flagged']} of {result['settled_selections']} selections sit at or above "
              f"the {DISCREPANCY_PERCENTILE:.0%} observed gap ({discrepancy['cut']:.1%})")
        print(f"  {discrepancy['note']}")

    iso = result["isotonic"]
    if iso:
        print(f"\nout-of-sample isotonic check (fit dates before {iso['boundary']}, "
              f"whole-date boundary)")
        print(f"  train {iso['train']} / test {iso['test']}")
        print(f"  Brier   raw {iso['brier_before']:.4f} -> fitted {iso['brier_after']:.4f}"
              f"   (market {iso['market_brier']:.4f})")
        print(f"  ECE     raw {iso['ece_before']:.4f} -> fitted {iso['ece_after']:.4f}")
    else:
        print(f"\nout-of-sample isotonic check: skipped (needs >= {MIN_ISOTONIC} selections)")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sport", default=None, help="limit to one sport")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--db", default=str(DB), help="database path")
    args = parser.parse_args()
    bets, skipped, pushes = build(args.db, args.sport)
    result = report(bets, skipped, pushes, args.sport)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print_report(result)


if __name__ == "__main__":
    main()
