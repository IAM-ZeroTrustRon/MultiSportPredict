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

# Windows consoles/code pages default to cp1252, which cannot encode the
# emoji used throughout the review table. Without this a run that already
# finished (or already refused a match on the data guard) dies at the print
# stage with UnicodeEncodeError, showing the user a traceback instead of the
# refusal they were about to read. Force UTF-8 so the outcome is what prints.
for stream in (sys.stdout, sys.stderr):
    if stream is not None and hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

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


def _norm_league(value: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def resolve(typed: str, teams: Dict[str, Dict[str, Any]],
            league: Optional[str] = None) -> Tuple[Optional[str], str]:
    """Resolve a typed team name to a stored key, refusing rather than guessing.

    When `league` is given, matching is scoped to teams stored under that
    league ONLY -- every team record already carries a `league` field. This
    is not an optimisation, it is what stops "FC Utrecht Youth" (Eerste
    Divisie) from silently resolving to senior "Utrecht" (Eredivisie), or
    "FC Eindhoven" (Eerste Divisie) to "PSV Eindhoven" (Eredivisie): both
    pairs are real, separate clubs/rosters that happen to share a city name
    and would otherwise collide under the old substring/fuzzy matching,
    which had no concept of tier or division. A same-name hit in the wrong
    league must come back unresolved, never a fuzzy guess.
    """
    if not typed:
        return None, "empty"

    pool = teams
    if league:
        wanted = _norm_league(league)
        scoped = {name: rec for name, rec in teams.items()
                  if _norm_league(rec.get("league")) == wanted}
        if not scoped:
            known = sorted({rec.get("league") for rec in teams.values() if rec.get("league")})
            return None, (f"no teams stored for league '{league}' "
                           f"(store has: {', '.join(known)})")
        pool = scoped

    if typed in pool:
        return typed, "exact"

    squashed = {squash(name): name for name in pool}
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

    if league:
        # Nothing matched inside the requested league. Check whether the
        # typed name exists under a DIFFERENT league so the failure message
        # explains why, instead of just "no match" -- this is the case that
        # used to silently succeed.
        stripped_target = squash(_NOISE.sub(" ", typed)) or target
        cross = sorted({
            name for name in teams
            if target and (target in squash(name) or squash(name) in target
                            or stripped_target in squash(name) or squash(name) in stripped_target)
        })
        if cross:
            cross_leagues = sorted({teams[c].get("league") or "?" for c in cross})
            return None, (f"unresolved -- '{typed}' matches {', '.join(cross)} "
                           f"but under {', '.join(cross_leagues)}, not '{league}' -- "
                           f"refusing to guess across leagues/tiers")
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
        match_league = match.get("league")
        home, how_home = resolve(typed_home, teams, match_league)
        away, how_away = resolve(typed_away, teams, match_league)

        odds_given = any(match.get(k) is not None for k in ("home_ml", "draw_ml", "away_ml"))
        total_given = match.get("total") is not None
        entry: Dict[str, Any] = {
            "n": index, "league": match.get("league", ""),
            "typed_home": typed_home, "typed_away": typed_away,
            "home": home, "away": away,
            "home_ml": match.get("home_ml"), "draw_ml": match.get("draw_ml"),
            "away_ml": match.get("away_ml"),
            "total": match.get("total", 2.5),
            "total_given": total_given,
        }

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

        # Auto-fetch odds when the slate didn't supply them, so a run never
        # settles for "no market, model probability only" when a real price
        # was fetchable. A slate-supplied price always wins -- this only
        # fills the gap, matching universal_runner.run_soccer()'s own rule.
        if not dry_run and not odds_given:
            from live_odds import get_soccer_odds
            fetched = get_soccer_odds(match.get("league"), home, away)
            if fetched.get("status") in ("live", "cached"):
                if fetched.get("home_ml") is not None:
                    entry["home_ml"] = fetched.get("home_ml")
                    entry["draw_ml"] = fetched.get("draw_ml")
                    entry["away_ml"] = fetched.get("away_ml")
                    entry["odds_captured_at"] = fetched.get("captured_at")
                if not total_given and fetched.get("total_line") is not None:
                    entry["total"] = fetched["total_line"]
                    total_given = True
            else:
                entry["odds_unavailable_reason"] = fetched.get("reason")

        market = no_vig(entry.get("home_ml"), entry.get("draw_ml"), entry.get("away_ml"))
        entry["mkt_home"], entry["mkt_draw"], entry["mkt_away"] = market

        if dry_run:
            entry["status"] = "dry-run"
            rows.append(entry)
            continue

        try:
            from universal_runner import run_soccer
            result = run_soccer(home, away, league=match.get("league"),
                                market_line=0.0, market_total=entry["total"],
                                store_to_db=True, push_discord=False,
                                market_total_given=total_given)
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
    rule("=", 112)
    log("📋  REVIEW  —  model vs market (vig removed).  Nothing has been pushed.")
    rule("=", 112)
    header = (
        f"  {'#':>2}  {'⚽ MATCH':<36}{'🏆 LEAGUE':<18}{'PICK':<7}"
        f"{'🤖 MODEL':>7}{'📊 NO-VIG':>8}{'⚡ EDGE':>7}{'💵 PRICE':>7}  {'📈 TOTAL':<22}"
    )
    log(header)
    log("  " + "-" * 112)

    for row in rows:
        label = f"{row['typed_home']} vs {row['typed_away']}"[:34]
        league_label = row.get("league", "")[:16] or "-"
        if row["status"] != "ok":
            icon = {"skipped": "⏭️", "failed": "❌", "dry-run": "🔍"}.get(row["status"], "❓")
            if row.get("reason") == "stale data":
                # Guard refusal: teams ARE in the store (Brest and PSG have
                # recorded stats) but sit below the minimum-game floor, so
                # their numbers mean nothing yet. "no stats" would send you
                # re-ingesting a league you already have.
                note = "stale data (below min games)"
            else:
                note = {"skipped": "no stats: " + ", ".join(row.get("missing", [])),
                        "failed": row.get("error", "failed"),
                        "dry-run": "dry run"}.get(row["status"], row["status"])
            log(f"  {row['n']:>2}  {icon} {label:<34}{league_label:<18}{note[:40]}")
            continue

        model = row["model"]
        options = [
            ("🏠 HOME", model.get("home_prob"), row.get("mkt_home"), row.get("home_ml")),
            ("🤝 DRAW", model.get("draw_prob"), row.get("mkt_draw"), row.get("draw_ml")),
            ("✈️ AWAY", model.get("away_prob"), row.get("mkt_away"), row.get("away_ml")),
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
                total_text += f" {str(model['total_rec'])[:12]}"

        log(f"  {row['n']:>2}  {label:<34}{league_label:<18}{name:<7}"
            f"{fmt_pct(model_p):>7}{fmt_pct(market_p):>8}{edge_text:>7}"
            f"{fmt_odds(price):>7}  {total_text:<22}")

        # Never let a fetched or missing price look identical to one the
        # slate actually supplied -- a captured_at timestamp on a cached
        # price is the whole point of live_odds.py's caching, and an
        # unavailable reason must be visible, not just a blank "-" that
        # reads the same as "nothing to fetch, league not in play."
        if row.get("odds_captured_at"):
            log(f"        odds auto-fetched, captured {row['odds_captured_at']}")
        elif row.get("odds_unavailable_reason"):
            log(f"        no auto-fetched odds: {row['odds_unavailable_reason']}")

    rule("-", 112)
    ran = [r for r in rows if r["status"] == "ok"]
    skipped = [r for r in rows if r["status"] == "skipped"]
    if ran:
        log(f"  ✅  {len(ran)} predicted and stored. Push the ones you want:")
        log(f"      venv/Scripts/python.exe run_soccer_batch.py --push "
            f"{' '.join(str(r['n']) for r in ran[:3])}")
    if skipped:
        guarded = [r for r in skipped if r.get("reason") == "stale data"]
        no_stats = [r for r in skipped if r.get("reason") != "stale data"]
        if no_stats:
            log(f"\n  ⏭️  {len(no_stats)} skipped for missing stats. Pull their leagues:")
            leagues = sorted({r["league"] for r in no_stats})
            log(f"      leagues affected: {', '.join(leagues)}")
            log(f"      venv/Scripts/python.exe ingest_soccer_fd.py --list")
        if guarded:
            log(f"\n  🛡️  {len(guarded)} guarded out: teams are in the store but below the")
            log(f"      minimum-game floor, so their numbers mean nothing yet.")
            log(f"      Re-ingest these leagues later and re-run the slate:")
            leagues = sorted({r["league"] for r in guarded})
            log(f"      leagues affected: {', '.join(leagues)}")
            log(f"      venv/Scripts/python.exe ingest_soccer_espn.py --leagues ligue_1")
    log("  ⚠️   EDGE is model minus no-vig market. Small edges are noise: under a")
    log("      couple of points it is model error, not disagreement worth backing.")
    rule("=", 112)

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

    # push_soccer_prediction_to_discord was a separate, hand-written soccer
    # embed that had drifted from every other sport's formatting (different
    # fields, no honest "not priced by model" vs "odds not supplied"
    # distinction). push_prediction_to_all is the one path run_tennis.py and
    # run_mlb.py already push through -- routing soccer through it too means
    # every push you actually make looks the same.
    from discord_integration import push_prediction_to_all

    chosen = [r for r in rows
              if r.get("status") == "ok" and (all_of_them or r.get("n") in numbers)]
    if not chosen:
        raise SystemExit(f"Nothing to push for: {numbers or 'all'}")

    for row in chosen:
        name = f"{row['home']} vs {row['away']}"
        count = push_prediction_to_all("soccer", row.get("raw", {}))
        log(f"  [{'OK' if count > 0 else 'FAILED'}] {row['n']}. {name}")


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
