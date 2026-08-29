#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run_soccer_batch.py - Run a slate of soccer matches, review, then push what you pick

    python run_soccer_batch.py                        run the slate, NO Discord
    python run_soccer_batch.py --slate slate_today.json
    python run_soccer_batch.py --review               reprint the last review table
    python run_soccer_batch.py --push 1 4 7           push those line numbers
    python run_soccer_batch.py --push-all
    python run_soccer_batch.py --dry-run              resolve names, predict nothing

HOW THIS IS MEANT TO BE USED
    1. Run it. Nothing goes to Discord. Every match is predicted, stored to the
       database, and printed in a comparison table.
    2. Read the table. It shows the model's probability next to the book's, with
       the vig stripped out, so the number in the EDGE column is the actual
       disagreement rather than a difference the margin explains.
    3. Push the ones you like:  --push 2 5

WHY THE MARKET COLUMN IS DE-VIGGED
    A three-way soccer price sums to more than 100% -- that surplus is the
    book's margin, not an opinion about the game. Comparing a model probability
    against the raw implied number therefore shows an edge on every single
    selection, which is worse than useless. The NO-VIG column normalises the
    three prices back to 100% so the comparison is like for like.

MATCHES ARE SKIPPED, NOT GUESSED
    A club with no stats in the store is reported and skipped. It is never run
    on league averages, because a confident-looking number built from nothing
    is the failure mode this whole pipeline exists to avoid.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import difflib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

SLATE = ROOT / "slate_today.json"
REVIEW = ROOT / "data" / "batch_review.json"


def log(message: str = "") -> None:
    print(message, flush=True)


def rule(char: str = "=", width: int = 100) -> None:
    log(char * width)


# ==========================================================================
# ODDS
# ==========================================================================

def implied(american: Optional[float]) -> Optional[float]:
    """American odds -> implied probability, vig included."""
    if american is None:
        return None
    value = float(american)
    if value < 0:
        return abs(value) / (abs(value) + 100.0)
    return 100.0 / (value + 100.0)


def no_vig(home: Optional[float], draw: Optional[float],
           away: Optional[float]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Strip the book's margin by normalising the three prices back to 1.0."""
    parts = [implied(home), implied(draw), implied(away)]
    if any(p is None for p in parts):
        return (None, None, None)
    total = sum(parts)  # type: ignore[arg-type]
    if total <= 0:
        return (None, None, None)
    return tuple(round(p / total, 4) for p in parts)  # type: ignore[return-value]


def fmt_odds(value: Optional[float]) -> str:
    if value is None:
        return "  -  "
    return f"+{int(value)}" if value > 0 else str(int(value))


def fmt_pct(value: Optional[float]) -> str:
    return "  -  " if value is None else f"{value * 100:5.1f}%"


# ==========================================================================
# TEAM RESOLUTION
# ==========================================================================

def load_all_soccer_teams() -> Dict[str, Dict[str, Any]]:
    """Both stores, auto first -- same precedence get_soccer_team_stats uses."""
    teams: Dict[str, Dict[str, Any]] = {}
    for path in (ROOT / "data" / "team_stats" / "soccer_stats.json",
                 ROOT / "data" / "soccer_stats.json"):
        if not path.exists():
            continue
        try:
            store = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            continue
        for name, record in store.items():
            if not name.startswith("_") and isinstance(record, dict):
                teams[name] = record
    return teams


def squash(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


_NOISE = re.compile(r"\b(fc|sbv|afc|jk|sc|cf|ac|united|city|club)\b", re.I)


def resolve(typed: str, teams: Dict[str, Dict[str, Any]]) -> Tuple[Optional[str], str]:
    if not typed:
        return None, "empty"
    if typed in teams:
        return typed, "exact"

    squashed = {squash(name): name for name in teams}
    target = squash(typed)
    if target in squashed:
        return squashed[target], "case/punctuation"

    contains = [real for flat, real in squashed.items()
                if target and (target in flat or flat in target)]
    if len(contains) == 1:
        return contains[0], "partial"
    if len(contains) > 1:
        return None, f"ambiguous: {', '.join(sorted(contains))}"

    # Feeds drop the decorations: "FC Nomme United" is often just "Nomme",
    # "Bournemouth AFC" just "Bournemouth".
    stripped = squash(_NOISE.sub(" ", typed))
    if stripped and stripped != target:
        contains = [real for flat, real in squashed.items()
                    if stripped in flat or flat in stripped]
        if len(contains) == 1:
            return contains[0], "partial (ignoring FC/AFC/United/City)"
        if len(contains) > 1:
            return None, f"ambiguous: {', '.join(sorted(contains))}"

    close = difflib.get_close_matches(target, list(squashed), n=3, cutoff=0.78)
    if len(close) == 1:
        return squashed[close[0]], "fuzzy"
    if close:
        return None, f"ambiguous: {', '.join(squashed[c] for c in close)}"
    return None, "no match"


# ==========================================================================
# RUN
# ==========================================================================

def extract_model(result: Dict[str, Any]) -> Dict[str, Any]:
    game = result.get("game", {}) or {}
    preds = result.get("predictions", {}) or {}
    total_block = preds.get("total", {}) or {}
    side_block = preds.get("side", {}) or {}
    return {
        "home_prob": game.get("home_win_prob"),
        "draw_prob": game.get("draw_prob"),
        "away_prob": game.get("away_win_prob"),
        "proj_total": game.get("projected_total_goals"),
        "proj_home": game.get("projected_home_goals"),
        "proj_away": game.get("projected_away_goals"),
        "total_rec": total_block.get("recommendation"),
        "total_conf": total_block.get("confidence"),
        "side_rec": side_block.get("recommendation"),
        "side_conf": side_block.get("confidence"),
    }


def run_slate(matches: List[Dict[str, Any]], dry_run: bool) -> List[Dict[str, Any]]:
    teams = load_all_soccer_teams()
    if not teams:
        raise SystemExit(
            "No soccer teams in either store.\n"
            "Pull the leagues first, e.g.:\n"
            "  venv/Scripts/python.exe ingest_soccer_fd.py "
            "--countries netherlands england")

    rows: List[Dict[str, Any]] = []
    for index, match in enumerate(matches, start=1):
        typed_home, typed_away = match["home"], match["away"]
        home, how_home = resolve(typed_home, teams)
        away, how_away = resolve(typed_away, teams)

        entry: Dict[str, Any] = {
            "n": index, "league": match.get("league", ""),
            "typed_home": typed_home, "typed_away": typed_away,
            "home": home, "away": away,
            "home_ml": match.get("home_ml"), "draw_ml": match.get("draw_ml"),
            "away_ml": match.get("away_ml"),
            "total": match.get("total", 2.5),
        }
        market = no_vig(match.get("home_ml"), match.get("draw_ml"), match.get("away_ml"))
        entry["mkt_home"], entry["mkt_draw"], entry["mkt_away"] = market

        missing = [t for t, r in ((typed_home, home), (typed_away, away)) if r is None]
        if missing:
            entry["status"] = "skipped"
            entry["missing"] = missing
            entry["reason"] = f"{how_home} / {how_away}"
            rows.append(entry)
            continue

        for typed, matched, how in ((typed_home, home, how_home),
                                    (typed_away, away, how_away)):
            if how != "exact":
                log(f'[name] "{typed}" -> "{matched}"  ({how})')

        # Refuse wrong-season data. This is the check that would have caught
        # the 1999/2000 squads before they reached a slate.
        try:
            from data_guard import guard_teams
            safe, note = guard_teams(teams, "soccer", [home, away])
            if not safe:
                entry["status"] = "skipped"
                entry["missing"] = []
                entry["reason"] = "stale data"
                log(f"[STALE] {typed_home} v {typed_away}")
                for line in note.splitlines():
                    log(f"        {line}")
                rows.append(entry)
                continue
            if note != "data age OK":
                log(f"[age] {typed_home} v {typed_away}: {note.splitlines()[0]}")
        except ImportError:
            pass

        if dry_run:
            entry["status"] = "dry-run"
            rows.append(entry)
            continue

        try:
            from universal_runner import run_soccer
            result = run_soccer(home, away, league=match.get("league"),
                                market_line=0.0, market_total=entry["total"],
                                store_to_db=True, push_discord=False)
            entry["status"] = "ok"
            entry["model"] = extract_model(result)
            entry["raw"] = result
        except Exception as exc:  # noqa: BLE001
            entry["status"] = "failed"
            entry["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(entry)
    return rows


# ==========================================================================
# REVIEW TABLE
# ==========================================================================

def print_review(rows: List[Dict[str, Any]]) -> None:
    log("")
    rule()
    log("REVIEW  -  model vs market (vig removed).  Nothing has been pushed.")
    rule()
    log(f"  {'#':>2}  {'MATCH':<38}{'PICK':<7}{'MODEL':>7}{'NO-VIG':>8}"
        f"{'EDGE':>7}{'PRICE':>7}  {'TOTAL':<18}")
    log("  " + "-" * 96)

    for row in rows:
        label = f"{row['typed_home']} v {row['typed_away']}"[:36]
        if row["status"] != "ok":
            note = {"skipped": "no stats: " + ", ".join(row.get("missing", [])),
                    "failed": row.get("error", "failed"),
                    "dry-run": "dry run"}.get(row["status"], row["status"])
            log(f"  {row['n']:>2}  {label:<38}{note[:52]}")
            continue

        model = row["model"]
        options = [
            ("HOME", model.get("home_prob"), row.get("mkt_home"), row.get("home_ml")),
            ("DRAW", model.get("draw_prob"), row.get("mkt_draw"), row.get("draw_ml")),
            ("AWAY", model.get("away_prob"), row.get("mkt_away"), row.get("away_ml")),
        ]
        scored = [(name, m, k, price, (m - k))
                  for name, m, k, price in options
                  if isinstance(m, (int, float)) and isinstance(k, (int, float))]
        if scored:
            best = max(scored, key=lambda item: item[4])
            name, model_p, market_p, price, edge = best
            row["best_side"] = name
            row["best_edge"] = round(edge, 4)
            edge_text = f"{edge * 100:+5.1f}"
        else:
            name, model_p, market_p, price, edge_text = "-", None, None, None, "  -  "

        total_text = ""
        if model.get("proj_total") is not None:
            total_text = f"{model['proj_total']:.2f} vs {row['total']}"
            if model.get("total_rec"):
                total_text += f" {str(model['total_rec'])[:10]}"

        log(f"  {row['n']:>2}  {label:<38}{name:<7}{fmt_pct(model_p):>7}"
            f"{fmt_pct(market_p):>8}{edge_text:>7}{fmt_odds(price):>7}  {total_text:<18}")

    rule()
    ran = [r for r in rows if r["status"] == "ok"]
    skipped = [r for r in rows if r["status"] == "skipped"]
    if ran:
        log(f"  {len(ran)} predicted and stored. Push the ones you want:")
        log(f"      venv/Scripts/python.exe run_soccer_batch.py --push "
            f"{' '.join(str(r['n']) for r in ran[:3])}")
    if skipped:
        log(f"\n  {len(skipped)} skipped for missing stats. Pull their leagues:")
        leagues = sorted({r["league"] for r in skipped})
        log(f"      leagues affected: {', '.join(leagues)}")
        log(f"      venv/Scripts/python.exe ingest_soccer_fd.py --list")
    log("\n  EDGE is model minus no-vig market. Small edges are noise: under a")
    log("  couple of points it is model error, not disagreement worth backing.")
    rule()


# ==========================================================================
# PUSH
# ==========================================================================

def push_selected(numbers: List[int], all_of_them: bool) -> None:
    if not REVIEW.exists():
        raise SystemExit("No saved review. Run the slate first.")
    saved = json.loads(REVIEW.read_text(encoding="utf-8-sig"))
    rows = saved.get("rows", [])

    env = ROOT / ".env"
    if not os.environ.get("DISCORD_WEBHOOK_URL") and env.exists():
        for raw in env.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if raw.strip().startswith("DISCORD_WEBHOOK_URL"):
                os.environ["DISCORD_WEBHOOK_URL"] = \
                    raw.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not os.environ.get("DISCORD_WEBHOOK_URL"):
        raise SystemExit("DISCORD_WEBHOOK_URL is not set -- nothing pushed.")

    from discord_integration import push_soccer_prediction_to_discord

    chosen = [r for r in rows
              if r.get("status") == "ok" and (all_of_them or r.get("n") in numbers)]
    if not chosen:
        raise SystemExit(f"Nothing to push for: {numbers or 'all'}")

    for row in chosen:
        name = f"{row['home']} vs {row['away']}"
        ok = push_soccer_prediction_to_discord(name, row.get("raw", {}))
        log(f"  [{'OK' if ok else 'FAILED'}] {row['n']}. {name}")


# ==========================================================================
# MAIN
# ==========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--slate", type=Path, default=SLATE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--review", action="store_true",
                        help="Reprint the last review table without re-running.")
    parser.add_argument("--push", nargs="+", type=int, metavar="N",
                        help="Push these numbered matches to Discord.")
    parser.add_argument("--push-all", action="store_true")
    args = parser.parse_args()

    if args.push or args.push_all:
        push_selected(args.push or [], args.push_all)
        return

    if args.review:
        if not REVIEW.exists():
            raise SystemExit("No saved review yet.")
        print_review(json.loads(REVIEW.read_text(encoding="utf-8-sig")).get("rows", []))
        return

    if not args.slate.exists():
        raise SystemExit(f"No slate file at {args.slate}")
    slate = json.loads(args.slate.read_text(encoding="utf-8-sig"))
    matches = slate.get("matches", [])
    if not matches:
        raise SystemExit(f"{args.slate.name} has no matches.")

    rule()
    log(f"SOCCER BATCH  -  {len(matches)} match(es)  -  Discord: OFF")
    rule()

    rows = run_slate(matches, args.dry_run)
    print_review(rows)

    if not args.dry_run:
        REVIEW.parent.mkdir(parents=True, exist_ok=True)
        REVIEW.write_text(json.dumps(
            {"generated": _dt.datetime.now().isoformat(timespec="seconds"),
             "rows": rows}, indent=2, default=str) + "\n", encoding="utf-8")
        log(f"\nSaved to {REVIEW.relative_to(ROOT)} -- --push reads from there.")


if __name__ == "__main__":
    main()
