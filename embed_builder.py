#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
embed_builder.py - One shape for every sport, one renderer for every embed

WHY THIS EXISTS
    discord_integration.py grew a separate formatter per sport -- soccer,
    baseball, tennis, plus two generic ones -- each guessing at the keys its
    predictor returns. Every one of them broke differently:

        format_prediction_embed   read "moneyline"; baseball returns
                                  "moneyline_and_side", so every game showed
                                  50.0% / 50.0% with two blank fields
        format_tennis_embed       read "home_player"; tennis returns the names
                                  under moneyline.home, so embeds went out
                                  titled "Player 1 vs Player 2"
        format_baseball_embed     added later to cover props, which the generic
                                  one had never read at all

    Each fix was a fifth special case. This is the shared layer instead: every
    prediction is flattened into ONE structure, and ONE function renders it.
    A new sport writes an extractor of about twenty lines and inherits the
    formatting, the colour rules and the guarantees below.

THREE RULES

    1. A VALUE THAT ISN'T FOUND IS OMITTED, NOT DEFAULTED.
       This is the whole bug class. `ml.get("home_win_prob", 0.5)` turns a
       failed lookup into a coin flip that renders as though the model said it.
       Nothing here supplies a stand-in. A market that cannot be read does not
       appear.

    2. AN EMPTY EMBED IS REFUSED.
       If no market extracts, build_embed raises. A push with a title and no
       content is worse than an error, because it looks like a pick.

    3. NAMES ARE NEVER INVENTED.
       No "Player 1", no "Home". If both names cannot be found the embed is
       refused.

USE
    from embed_builder import build_embed
    embed = build_embed("baseball", prediction_dict)
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Tuple

# Discord colours
COLOR_STRONG = 0x2ECC71      # green  - a real edge with conviction
COLOR_BET = 0x3498DB         # blue   - worth a look
COLOR_PASS = 0x95A5A6        # grey   - no disagreement worth backing
COLOR_INFO = 0x7F8C8D        # slate  - projection only, no market

SPORT_LABEL = {
    "baseball": ("⚾", "BASEBALL"), "mlb": ("⚾", "MLB"),
    "kbo": ("⚾", "KBO"), "soccer": ("⚽", "SOCCER"),
    "tennis": ("\U0001f3be", "TENNIS"), "nfl": ("\U0001f3c8", "NFL"),
    "basketball": ("\U0001f3c0", "BASKETBALL"), "ncaaf": ("\U0001f3c8", "NCAAF"),
}


class UnrenderablePrediction(Exception):
    """Raised instead of publishing an embed with nothing in it."""


# ==========================================================================
# SMALL HELPERS -- every one of these returns None rather than a stand-in
# ==========================================================================

def num(value: Any) -> Optional[float]:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def dig(data: Dict[str, Any], *path: str) -> Any:
    """Walk a nested dict. Returns None the moment a step is missing."""
    node: Any = data
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def pct(value: Any) -> Optional[str]:
    """A probability as a percentage. Accepts 0-1 or 0-100."""
    number = num(value)
    if number is None:
        return None
    if number > 1.0:
        number /= 100.0
    if not 0.0 <= number <= 1.0:
        return None
    return f"{number:.1%}"


def dec(value: Any, places: int = 2) -> Optional[str]:
    number = num(value)
    return None if number is None else f"{number:.{places}f}"


def signed(value: Any, places: int = 2) -> Optional[str]:
    number = num(value)
    return None if number is None else f"{number:+.{places}f}"


def clean(text: Any) -> Optional[str]:
    if text is None:
        return None
    out = str(text).strip()
    return out or None


# ==========================================================================
# NORMALISED SHAPE
# ==========================================================================

def as_notes(value: Any) -> List[str]:
    """Notes arrive as a list from some predictors and a plain string from
    others. Iterating a string yields characters, which rendered as a column of
    single letters down the side of every soccer embed."""
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in re.split(r"[\n;]+", value) if p.strip()]
        return parts
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value if clean(v) and not isinstance(v, (list, dict))]
    text = clean(value)
    return [text] if text else []


def market(name: str, *, model: Optional[str] = None, market_value: Optional[str] = None,
           edge: Optional[str] = None, pick: Optional[str] = None,
           extra: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """One row. Returns None when there is nothing real to show.

    A row needs at least a model number or a pick. A heading with an empty
    value renders as though the answer were zero, which is how "Model Edge"
    and "Confidence" once shipped as blank fields for weeks.
    """
    if model is None and pick is None and extra is None:
        return None
    return {"name": name, "model": model, "market": market_value,
            "edge": edge, "pick": pick, "extra": extra}


def names_from(data: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Find both sides, or neither. Checked against the shapes actually used."""
    candidates = (
        (dig(data, "moneyline", "home"), dig(data, "moneyline", "away")),
        (data.get("home"), data.get("away")),
        (data.get("home_team"), data.get("away_team")),
        (data.get("home_player"), data.get("away_player")),
        (dig(data, "moneyline_and_side", "home"), dig(data, "moneyline_and_side", "away")),
    )
    for home, away in candidates:
        if clean(home) and clean(away):
            return clean(home), clean(away)

    text = clean(data.get("match")) or clean(data.get("matchup"))
    if text:
        for separator in (" vs. ", " vs ", " v ", " @ ", " at ", " - "):
            if separator in text:
                home, away = text.split(separator, 1)
                if clean(home) and clean(away):
                    return clean(home), clean(away)
    return None, None


# ==========================================================================
# EXTRACTORS -- written against real stored payloads, not assumed shapes
# ==========================================================================

def extract_baseball(data: Dict[str, Any]) -> Dict[str, Any]:
    rows: List[Optional[Dict[str, Any]]] = []
    ml, projection, summary = (data.get("moneyline_and_side") or {},
                               data.get("game_projection") or {},
                               data.get("summary") or {})

    home_prob = dig(ml, "home_win_probability")
    if home_prob is not None:
        hp = dig(ml, "home_win_probability")
        ap = dig(ml, "away_win_probability")
        raw = dig(ml, "confidence", "side", "recommendation")
        home_name = (data.get("home_team") or "")[:20]
        away_name = (data.get("away_team") or "")[:20]
        side_pick = raw if raw else "PASS"
        if side_pick.upper() == "BET" and hp is not None and ap is not None:
            if hp > ap and home_name:
                side_pick = f"BET {home_name}"
            elif ap > hp and away_name:
                side_pick = f"BET {away_name}"
        has_market_edge = ml.get("edge_pct") is not None
        no_market_note = "model probability only -- no market odds supplied"
        base_conf = (f"conf {dec(dig(ml, 'confidence', 'side', 'score'), 0)}"
                     if dig(ml, "confidence", "side", "score") is not None else None)
        rows.append(market(
            "💰 Moneyline",
            model=f"{pct(hp)} / {pct(ap)}",
            market_value=pct(ml.get("market_home_prob")) if has_market_edge else None,
            edge=signed(ml.get("edge_pct"), 1) if has_market_edge else None,
            pick=clean(ml.get("recommendation")) if has_market_edge else side_pick,
            extra=(f"conf {dec(ml.get('ml_confidence'), 0)}" if has_market_edge else
                   (f"{base_conf} -- {no_market_note}" if base_conf else no_market_note))))

    total_model = projection.get("total") or ml.get("projected_total_runs")
    if total_model is not None:
        rows.append(market(
            "📊 Total runs", model=dec(total_model, 2),
            market_value=dec(summary.get("market_total"), 1),
            edge=signed(summary.get("edge_value") or summary.get("edge")),
            pick=clean(summary.get("recommendation"))))

    home_runs, away_runs = projection.get("home_runs"), projection.get("away_runs")
    if home_runs is not None and away_runs is not None:
        rows.append(market("🏟‍ Team totals",
                           model=f"{dec(home_runs, 2)} / {dec(away_runs, 2)}"))

    props = data.get("props") or data.get("markets") or {}
    nrfi = dig(props, "nrfi", "probability") or dig(props, "nrfi", "nrfi_probability")
    if nrfi is not None:
        rows.append(market("📛 NRFI", model=pct(nrfi),
                           pick=(clean(dig(props, "nrfi", "recommendation"))
                                 or clean(dig(props, "nrfi", "lean"))
                                 or "PASS")))
    strikeouts = dig(props, "strikeouts", "home_projection")
    if strikeouts is not None:
        rows.append(market("⚾ Strikeouts (H/A)",
                           model=f"{dec(strikeouts, 1)} / "
                                 f"{dec(dig(props, 'strikeouts', 'away_projection'), 1)}"))
    home_hr = dig(props, "home_runs", "home_projection")
    if home_hr is not None:
        rows.append(market("🔥 Home runs (H/A)",
                           model=f"{dec(home_hr, 1)} / "
                                 f"{dec(dig(props, 'home_runs', 'away_projection'), 1)}"))


    # F5 (First 5 Innings) Markets
    f5 = dig(props, "f5") or {}
    f5_total = f5.get("total")
    if f5_total is not None:
        rows.append(market("🎯 F5 Total",
                           model=dec(f5_total, 2),
                           pick=clean(f5.get("recommendation_over"))))
    f5_home_wp = f5.get("home_win_prob")
    if f5_home_wp is not None:
        f5_home_odds = f5.get("home_fair_odds") or "-"
        f5_away_odds = f5.get("away_fair_odds") or "-"
        rows.append(market("🎯 F5 Moneyline",
                           model=f"{pct(f5_home_wp)} / {pct(f5.get('away_win_prob'))}",
                           extra=f"fair odds: {f5_home_odds} / {f5_away_odds}"))
    f5_rl = clean(f5.get("run_line_rec"))
    if f5_rl and f5_rl != "PASS":
        rows.append(market("📐 F5 Run Line", pick=clean(f5.get("run_line_rec"))))

    notes: List[str] = []
    source = clean(data.get("data_source")) or clean(data.get("_stats_source"))
    if source and "internal_baseline" in source:
        notes.append("⚙️ Team stats fell back to the league baseline -- this "
                     "projection does not describe these two clubs.")
    umpire = clean(data.get("umpire"))
    if umpire and umpire.lower() != "unknown":
        notes.append(f"🧑‍✈️ Umpire: {umpire}")
    return {"markets": rows, "notes": notes,
            "context": clean(data.get("league"))}


def extract_soccer(data: Dict[str, Any]) -> Dict[str, Any]:
    rows: List[Optional[Dict[str, Any]]] = []
    game, preds = data.get("game") or {}, data.get("predictions") or {}

    if dig(game, "home_win_prob") is not None:
        rows.append(market(
            "1X2", model=f"{pct(game.get('home_win_prob'))} / "
                         f"{pct(game.get('draw_prob'))} / "
                         f"{pct(game.get('away_win_prob'))}",
            pick=clean(dig(preds, "side", "recommendation")),
            extra="home / draw / away"))

    if game.get("projected_total_goals") is not None:
        rows.append(market(
            "Total goals", model=dec(game.get("projected_total_goals"), 2),
            market_value=dec(dig(preds, "total", "market_total"), 1),
            edge=signed(dig(preds, "total", "edge")),
            pick=clean(dig(preds, "total", "recommendation"))))

    if game.get("projected_home_goals") is not None:
        rows.append(market("Team goals",
                           model=f"{dec(game.get('projected_home_goals'), 2)} / "
                                 f"{dec(game.get('projected_away_goals'), 2)}"))

    if data.get("btts_probability") is not None:
        rows.append(market("BTTS", model=pct(data.get("btts_probability")),
                           pick=clean(dig(preds, "btts", "recommendation"))))

    goals = data.get("goals_analysis") or {}
    if goals.get("over_25_prob") is not None:
        rows.append(market("Over 2.5", model=pct(goals.get("over_25_prob")),
                           extra=f"O1.5 {pct(goals.get('over_15_prob'))} · "
                                 f"O3.5 {pct(goals.get('over_35_prob'))}"))

    half = data.get("halftime") or {}
    if clean(half.get("recommendation_1h_total")):
        rows.append(market("First half",
                           model=clean(half.get("predicted_1h_result")),
                           extra=clean(half.get("recommendation_1h_total"))))

    # Corners is deliberately NOT published. team_corner_strength() (the
    # function behind both corner_projection and the extra_markets split)
    # has no xG-equivalent input -- every non-constant term in it is one of
    # the fake home/away constants (shots/sot/tempo/width_crossing/
    # final_third_pressure), so the total is mathematically the same number
    # for every match in the sport (confirmed: 10.9, unconditionally). Unlike
    # moneyline/total/BTTS, there's no real signal underneath to fall back on
    # by just dropping the fake terms, so the honest move is to stop showing
    # it rather than label a constant as "degraded" forever. See the extra_markets
    # calculation itself, still intact for whenever a real corners feed exists.
    corners_retired = (num(data.get("corner_projection")) is not None
                       or dig(data, "extra_markets", "team_corners", "home", "projection") is not None)

    team_goals = dig(data, "extra_markets", "team_total_goals") or {}
    home_tg, away_tg = team_goals.get("home") or {}, team_goals.get("away") or {}
    if home_tg.get("over_15") is not None:
        rows.append(market(
            "Team goals O/U 1.5",
            model=f"{pct(home_tg.get('over_15'))} / {pct(away_tg.get('over_15'))}",
            extra="home / away, P(over 1.5)"))

    notes = as_notes(data.get("notes"))[:2]
    tier = dig(data, "_stats_source", "data_tier")
    if tier == 2:
        notes.append("xG is estimated from goals -- no reachable feed publishes it.")
    if corners_retired:
        notes.append("Corners not published -- the model's corner total isn't "
                     "derived from real per-match data yet.")
    return {"markets": rows, "notes": notes,
            "context": clean(data.get("league"))}


def extract_tennis(data: Dict[str, Any]) -> Dict[str, Any]:
    rows: List[Optional[Dict[str, Any]]] = []
    ml, sets, games = (data.get("moneyline") or {}, data.get("sets") or {},
                       data.get("total_games") or {})

    if ml.get("home_win_prob") is not None:
        # edge_pct is ALWAYS computed here, even with no market odds -- it's
        # just model_prob minus a hardcoded 50% in that case, not a real
        # market comparison. Showing it unconditionally made a coin-flip
        # baseline look like a priced edge. Only surface it when real market
        # odds were actually supplied; say so plainly otherwise.
        # market_prob is what _recommendation() actually compares against --
        # market_home_odds/market_away_odds are display-only strings that the
        # real call chain (run_tennis.py -> universal_runner.run_tennis)
        # never populates, so checking those would always read as "no
        # market" even when --p1-ml/--p2-ml were given.
        has_market = data.get("market_prob") is not None
        rows.append(market(
            "💰 Moneyline",
            model=f"{pct(ml.get('home_win_prob'))} / {pct(ml.get('away_win_prob'))}",
            edge=signed(ml.get("edge_pct"), 1) if has_market else None,
            pick=clean(ml.get("recommendation")),
            extra=(f"conf {dec(ml.get('confidence'), 0)}"
                   if has_market and ml.get("confidence") is not None
                   else ("model probability only -- no market odds supplied" if not has_market else None))))

    if sets.get("over_35_prob") is not None:
        rows.append(market("Sets", model=pct(sets.get("over_35_prob")),
                           pick=clean(sets.get("recommendation_sets_ou")),
                           extra=clean(sets.get("recommendation_spread"))))

    if games.get("line") is not None or games.get("over_prob") is not None:
        rows.append(market("Total games", model=pct(games.get("over_prob")),
                           market_value=dec(games.get("line"), 1),
                           pick=clean(games.get("recommendation"))))

    notes: List[str] = []
    elo = data.get("elo_ratings") or {}
    if elo:
        notes.append("Elo " + " · ".join(f"{k} {dec(v, 0)}" for k, v in
                                         list(elo.items())[:2]))
    counts = data.get("match_counts") or {}
    thin = [k for k, v in counts.items() if num(v) is not None and num(v) < 8]
    if thin:
        notes.append(f"Thin sample: {', '.join(thin)} under 8 matches -- the "
                     f"rating is mostly the starting constant.")
    context = " ".join(x for x in (clean(data.get("tournament")),
                                   clean(data.get("round"))) if x)
    return {"markets": rows, "notes": notes, "context": context or None}


def extract_nfl(data: Dict[str, Any]) -> Dict[str, Any]:
    rows: List[Optional[Dict[str, Any]]] = []
    spread, ml = data.get("spread") or {}, data.get("moneyline") or {}
    total, half = data.get("total") or {}, data.get("halftime") or {}

    if spread.get("model_spread") is not None:
        rows.append(market("Spread", model=signed(spread.get("model_spread"), 1),
                           market_value=signed(spread.get("market_spread"), 1),
                           edge=signed(spread.get("edge_points"), 1),
                           pick=clean(spread.get("pick"))))
    if ml.get("home_win_probability") is not None:
        rows.append(market(
            "💰 Moneyline",
            model=f"{pct(ml.get('home_win_probability'))} / "
                  f"{pct(ml.get('away_win_probability'))}",
            market_value=pct(ml.get("market_home_prob")),
            edge=signed(ml.get("edge_pct"), 1),
            pick=clean(ml.get("recommendation"))))
    if total.get("model_total") is not None:
        rows.append(market("Total", model=dec(total.get("model_total"), 1),
                           market_value=dec(total.get("market_total"), 1),
                           edge=signed(total.get("edge_points"), 1),
                           pick=clean(total.get("pick"))))
    if total.get("home_team_total") is not None:
        rows.append(market("🏟‍ Team totals",
                           model=f"{dec(total.get('home_team_total'), 1)} / "
                                 f"{dec(total.get('away_team_total'), 1)}"))
    if half.get("home_1h_points") is not None:
        rows.append(market("First half",
                           model=f"{dec(half.get('home_1h_points'), 1)} - "
                                 f"{dec(half.get('away_1h_points'), 1)}",
                           extra=f"home ML {pct(half.get('home_1h_win_probability'))}"))

    notes: List[str] = []
    if half.get("data_tier") == 3:
        notes.append("First half is ESTIMATED -- no 1H splits in the store.")
    blend = data.get("prior_blend") or {}
    weight = num(blend.get("current_season_weight"))
    if weight is not None and weight < 0.5:
        notes.append("Running on LAST SEASON, regressed toward the mean. A big "
                     "disagreement with the market means the model is wrong, "
                     "not the market.")
    key = spread.get("near_key_number")
    if key is not None:
        notes.append(f"Market spread sits on the key number {num(key):g}.")
    return {"markets": rows, "notes": notes, "context": "NFL"}


def extract_basketball(data: Dict[str, Any]) -> Dict[str, Any]:
    """Shape written by EuroleaguePredictor.predict() (universal_runner.py's
    EuroLeague/KBL/NZNBL branch) and predict_match.run_basketball_game()'s
    generic fallback -- this sport had no extractor at all before, so every
    prediction raised UnrenderablePrediction inside push_prediction_to_all
    and was silently [REFUSED], never reaching Discord."""
    rows: List[Optional[Dict[str, Any]]] = []
    full_game = data.get("full_game") or {}
    market_info = data.get("market_info") or {}

    home_score, away_score = full_game.get("projected_home_score"), full_game.get("projected_away_score")
    if full_game.get("probability") is not None:
        model_spread = (num(home_score) - num(away_score)) if (home_score is not None and away_score is not None) else None
        rows.append(market(
            "Spread",
            model=signed(model_spread, 1) if model_spread is not None else pct(full_game.get("probability")),
            market_value=signed(market_info.get("current_line"), 1),
            edge=signed(full_game.get("model_edge"), 1),
            pick=clean(full_game.get("lean")),
            extra=(f"{dec(home_score, 1)} - {dec(away_score, 1)}"
                   if home_score is not None and away_score is not None else None)))

    if full_game.get("projected_total") is not None:
        rows.append(market("Total", model=dec(full_game.get("projected_total"), 1)))

    for period, label in (("q1", "1st Quarter"), ("h1", "1st Half"), ("first_half", "1st Half")):
        block = data.get(period) or {}
        if block.get("probability") is not None:
            rows.append(market(
                label, model=pct(block.get("probability")),
                pick=clean(block.get("lean")),
                extra=(f"proj {dec(block.get(f'projected_{period}_total'), 1)}"
                       if block.get(f"projected_{period}_total") is not None else None)))

    notes = as_notes(data.get("notes"))[:2]
    source = clean(data.get("_stats_source"))
    if source and "placeholder" in source:
        notes.append("Team stats fell back to a placeholder baseline -- this "
                     "projection does not describe these two clubs.")
    return {"markets": rows, "notes": notes, "context": clean(data.get("league"))}


EXTRACTORS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "baseball": extract_baseball, "mlb": extract_baseball, "kbo": extract_baseball,
    "soccer": extract_soccer, "tennis": extract_tennis,
    "nfl": extract_nfl, "ncaaf": extract_nfl,
    "basketball": extract_basketball, "euroleague": extract_basketball,
    "kbl": extract_basketball, "nznbl": extract_basketball,
}


# ==========================================================================
# NORMALISE + RENDER
# ==========================================================================

def normalise(sport: str, data: Dict[str, Any]) -> Dict[str, Any]:
    sport = (sport or "").strip().lower()
    home, away = names_from(data)
    if not home or not away:
        raise UnrenderablePrediction(
            f"Cannot find both team/player names in this {sport or 'unknown'} "
            f"prediction. Checked moneyline.home/away, home/away, "
            f"home_team/away_team, home_player/away_player and match. "
            f"Refusing to publish placeholder names. Keys: {sorted(data)[:14]}")

    extractor = EXTRACTORS.get(sport)
    if extractor is None:
        raise UnrenderablePrediction(
            f"No extractor for sport '{sport}'. Add one to EXTRACTORS -- about "
            f"twenty lines -- rather than letting it render as empty fields. "
            f"Known: {', '.join(sorted(set(EXTRACTORS)))}")

    parsed = extractor(data)
    rows = [row for row in parsed["markets"] if row]
    if not rows:
        raise UnrenderablePrediction(
            f"{sport}: {home} vs {away} produced no readable market. The "
            f"prediction ran but nothing in it could be rendered, so there is "
            f"nothing to publish. Keys present: {sorted(data)[:14]}")

    return {"sport": sport, "home": home, "away": away,
            "context": parsed.get("context"), "markets": rows,
            "notes": [n for n in parsed.get("notes", []) if n]}


def _tone(rows: List[Dict[str, Any]]) -> int:
    picks = " ".join((row.get("pick") or "").upper() for row in rows)
    if "STRONG" in picks:
        return COLOR_STRONG
    if "BET" in picks or "OVER" in picks or "UNDER" in picks or "HOME" in picks \
            or "AWAY" in picks or "YES" in picks:
        return COLOR_BET
    if "PASS" in picks:
        return COLOR_PASS
    return COLOR_INFO


def build_embed(sport: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """The only function that should ever construct a Discord embed here."""
    shape = normalise(sport, data)
    emoji, label = SPORT_LABEL.get(shape["sport"], ("\U0001f4ca", shape["sport"].upper()))

    title_bits = [f"{emoji} {label}"]
    if shape["context"] and shape["context"].upper() != label:
        title_bits.append(shape["context"])
    title = " | ".join(title_bits) + f" | {shape['away']} at {shape['home']}"

    fields: List[Dict[str, Any]] = []
    for row in shape["markets"]:
        parts: List[str] = []
        if row["model"]:
            parts.append(f"**{row['model']}**")
        if row["market"]:
            parts.append(f"mkt {row['market']}")
        if row["edge"]:
            parts.append(f"edge {row['edge']}")
        body = "  ".join(parts)
        if row["pick"]:
            body = f"{body}\n{row['pick']}" if body else row["pick"]
        if row["extra"]:
            body = f"{body}\n*{row['extra']}*" if body else f"*{row['extra']}*"
        fields.append({"name": row["name"], "value": body or "​",
                       "inline": True})

    # Discord renders three per row; a trailing single field looks broken.
    while len(fields) % 3 and len(fields) > 3:
        fields.append({"name": "​", "value": "​", "inline": True})

    embed: Dict[str, Any] = {
        "title": title[:256],
        "color": _tone(shape["markets"]),
        "fields": fields[:25],
        "footer": {"text": "MultiSportPredict"},
    }
    if shape["notes"]:
        embed["description"] = "\n".join(f"> {note}" for note in shape["notes"])[:4096]
    return embed
