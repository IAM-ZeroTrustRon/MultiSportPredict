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


def short_name(name: Any) -> Optional[str]:
    """A team label short enough for an inline field, still unambiguous.

    Inline fields are a third of the card wide, so "Los Angeles Dodgers" wraps
    and pushes the number onto its own line. Abbreviations and short names are
    kept whole; longer ones drop to the nickname, keeping two words when the
    last is tiny so "Chicago White Sox" is "White Sox" and not "Sox".
    """
    text = clean(name)
    if text is None or len(text) <= 14:
        return text
    parts = text.split()
    if len(parts) >= 2 and len(parts[-1]) <= 4:
        return " ".join(parts[-2:])
    return parts[-1]


def pair(away_name: Any, away_value: Optional[str],
         home_name: Any, home_value: Optional[str]) -> Optional[str]:
    """Two sides, each tied to the team it belongs to, away first.

    An unlabelled "67.4% / 32.6%" is not readable: nothing on the card says
    which end is which, and the pair was home-first while the title reads
    "away at home", so the natural reading was exactly backwards. Every
    two-sided row goes through here. A side with no number is dropped rather
    than shown as a bare slash.
    """
    away, home = short_name(away_name), short_name(home_name)
    bits = []
    if away_value and away:
        bits.append(f"**{away}** {away_value}")
    if home_value and home:
        bits.append(f"**{home}** {home_value}")
    return "\n".join(bits) or None


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
           extra: Optional[str] = None, verdict: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """One row. Returns None when there is nothing real to show.

    A row needs at least a model number or a pick. A heading with an empty
    value renders as though the answer were zero, which is how "Model Edge"
    and "Confidence" once shipped as blank fields for weeks.

    verdict: one unambiguous sentence -- action (BET/LEAN/PASS), the exact
    side and market, the price it's predicated on, and the strength -- built
    by the extractor (see moneyline_verdict()) and rendered FIRST and bold,
    ahead of the supporting model/market/edge numbers. Without this, the
    reader has to derive the verdict themselves from percentages scattered
    across the field, which is how "LEAN St. Louis Cardinals ML
    (edge: -9.1%)" shipped looking like a fadeable pick instead of the
    correctly-recommended one it was. A row can carry both verdict and pick;
    when verdict is set, the renderer shows verdict first and drops pick
    from the body (verdict already says what pick would have said, plus
    the price and the side, which pick alone did not).
    """
    if model is None and pick is None and extra is None and verdict is None:
        return None
    return {"name": name, "model": model, "market": market_value,
            "edge": edge, "pick": pick, "extra": extra, "verdict": verdict}


def moneyline_verdict(action: Optional[str], side: Optional[str], strength: Optional[str],
                      market_label: str, price_text: Optional[str], has_market: bool,
                      model_side: Optional[str] = None,
                      model_prob_text: Optional[str] = None) -> Optional[str]:
    """One line: action + exact side + market + price it's predicated on + strength.

    Assembled from the predictor's own already-resolved action/side/strength
    (models/tennis_predictor.py's _recommendation(), predict_match.py's
    _moneyline_edge() -- both return these as clean fields precisely so this
    never has to re-derive or parse a sentence apart) plus the price it was
    computed against. A reader should never have to combine model%, market%,
    edge and confidence themselves to work out what the pick actually is.

    When no market odds exist, that is the verdict -- PASS, stated as a
    reason, not a bare model percentage that reads like a priced edge.
    """
    if not has_market:
        who = f" ({model_side} {model_prob_text})" if model_side and model_prob_text else ""
        return f"PASS — {market_label}: no market odds supplied{who}"

    price_clause = f" @ {price_text} market" if price_text else ""
    if action is None or action == "PASS" or side is None:
        return f"PASS — {market_label} market efficient{price_clause}"

    strength_clause = f" — {strength} edge" if strength else ""
    return f"{action} {side} {market_label}{price_clause}{strength_clause}"


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

def _nrfi_pick(pick: Optional[str]) -> str:
    """A bare "YRFI" under two percentages does not say what it is.

    The predictor's lean is one token; on the card it sits directly beneath
    the NRFI and YRFI numbers, where it reads like a third value rather than
    the side being leaned. Anything already phrased (BET/LEAN/PASS) is left
    exactly as the predictor wrote it.
    """
    if not pick:
        return "PASS — no side"
    if pick.strip().upper() in {"NRFI", "YRFI", "YES", "NO"}:
        return f"lean {pick.strip().upper()}"
    return pick


def extract_baseball(data: Dict[str, Any]) -> Dict[str, Any]:
    rows: List[Optional[Dict[str, Any]]] = []
    ml, projection, summary = (data.get("moneyline_and_side") or {},
                               data.get("game_projection") or {},
                               data.get("summary") or {})

    # Every two-sided row is labelled with these, so they are resolved once
    # here rather than per row (and via names_from() when the payload carries
    # the names somewhere other than home_team/away_team).
    fallback_home, fallback_away = names_from(data)
    home_name = clean(data.get("home_team")) or fallback_home
    away_name = clean(data.get("away_team")) or fallback_away

    home_prob = dig(ml, "home_win_probability")
    if home_prob is not None:
        hp = dig(ml, "home_win_probability")
        ap = dig(ml, "away_win_probability")
        has_market_edge = ml.get("edge_pct") is not None
        # action/side/strength come straight from _moneyline_edge() in
        # predict_match.py (only present when real home_ml/away_ml were
        # supplied) -- same clean-fields pattern as tennis's _recommendation(),
        # so the verdict is assembled, not parsed or re-derived.
        action, rec_side, strength = ml.get("action"), ml.get("side"), ml.get("strength")
        market_home_prob = num(ml.get("market_home_prob"))
        if has_market_edge and market_home_prob is not None:
            side_price = (market_home_prob if rec_side == home_name
                         else (1 - market_home_prob) if rec_side == away_name
                         else market_home_prob)
            price_text = pct(side_price)
        else:
            price_text = None
        fav_name = home_name if num(hp or 0) >= num(ap or 0) else away_name
        fav_prob = pct(hp if fav_name == home_name else ap)
        verdict = moneyline_verdict(action, rec_side, strength, "Moneyline",
                                    price_text, has_market_edge,
                                    model_side=short_name(fav_name),
                                    model_prob_text=fav_prob)
        rows.append(market(
            "💰 Moneyline",
            model=pair(away_name, pct(ap), home_name, pct(hp)),
            market_value=pct(ml.get("market_home_prob")) if has_market_edge else None,
            edge=signed(ml.get("edge_pct"), 1) if has_market_edge else None,
            verdict=verdict,
            extra=(f"conf {dec(ml.get('ml_confidence'), 0)}" if has_market_edge else None)))

    total_model = projection.get("total") or ml.get("projected_total_runs")
    if total_model is not None:
        total_pick = clean(summary.get("recommendation"))
        rows.append(market(
            "📊 Total runs (O/U)", model=f"proj {dec(total_model, 2)}",
            market_value=dec(summary.get("market_total"), 1),
            edge=signed(summary.get("edge_value") or summary.get("edge")),
            # "PASS" alone reads as a missing value; say what was passed on.
            pick=(total_pick if total_pick and total_pick.upper() not in ("PASS", "NO BET")
                  else ("PASS — no side on the total" if total_pick else None))))

    home_runs, away_runs = projection.get("home_runs"), projection.get("away_runs")
    if home_runs is not None and away_runs is not None:
        rows.append(market("🏟‍ Team totals (runs)",
                           model=pair(away_name, dec(away_runs, 2),
                                      home_name, dec(home_runs, 2))))

    props = data.get("props") or data.get("markets") or {}
    nrfi = dig(props, "nrfi", "probability") or dig(props, "nrfi", "nrfi_probability")
    if nrfi is not None:
        # "50.8%" beside a YRFI lean read as though YRFI were the 50.8%. Both
        # sides are now named with their own number, so the lean is checkable.
        nrfi_num = num(nrfi)
        nrfi_prob = nrfi_num / 100.0 if nrfi_num is not None and nrfi_num > 1.0 else nrfi_num
        yrfi_text = pct(1.0 - nrfi_prob) if nrfi_prob is not None else None
        rows.append(market(
            "📛 NRFI / YRFI",
            model="\n".join(bit for bit in (
                f"**NRFI** {pct(nrfi)}" if pct(nrfi) else None,
                f"**YRFI** {yrfi_text}" if yrfi_text else None) if bit) or None,
            pick=_nrfi_pick(clean(dig(props, "nrfi", "recommendation"))
                            or clean(dig(props, "nrfi", "lean")))))
    strikeouts = dig(props, "strikeouts", "home_projection")
    if strikeouts is not None:
        rows.append(market("⚾ Strikeouts (SP)",
                           model=pair(away_name,
                                      dec(dig(props, 'strikeouts', 'away_projection'), 1),
                                      home_name, dec(strikeouts, 1))))
    home_hr = dig(props, "home_runs", "home_projection")
    if home_hr is not None:
        rows.append(market("🔥 Home runs",
                           model=pair(away_name,
                                      dec(dig(props, 'home_runs', 'away_projection'), 1),
                                      home_name, dec(home_hr, 1))))


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
                           model=pair(away_name, pct(f5.get('away_win_prob')),
                                      home_name, pct(f5_home_wp)),
                           extra=f"fair odds: {short_name(away_name)} {f5_away_odds} / "
                                 f"{short_name(home_name)} {f5_home_odds}"))
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
        home_name, away_name = clean(ml.get("home")), clean(ml.get("away"))
        market_prob = num(data.get("market_prob"))
        rec_side, action, strength = ml.get("side"), ml.get("action"), ml.get("strength")
        # Price the recommended side was actually priced against -- market_prob
        # is home's devigged probability; the away side's is the complement
        # (no_vig() makes the two sum to 1 by construction).
        if market_prob is not None:
            side_price = (market_prob if rec_side == home_name
                         else (1 - market_prob) if rec_side == away_name
                         else market_prob)
            price_text = pct(side_price)
        else:
            price_text = None
        fav_name = home_name if num(ml.get("home_win_prob") or 0) >= \
                   num(ml.get("away_win_prob") or 0) else away_name
        fav_prob = pct(ml.get("home_win_prob") if fav_name == home_name
                       else ml.get("away_win_prob"))
        verdict = moneyline_verdict(action, rec_side, strength, "Moneyline",
                                    price_text, has_market,
                                    model_side=fav_name, model_prob_text=fav_prob)
        rows.append(market(
            "💰 Moneyline",
            model=f"{pct(ml.get('home_win_prob'))} / {pct(ml.get('away_win_prob'))}",
            edge=signed(ml.get("edge_pct"), 1) if has_market else None,
            verdict=verdict,
            extra=(f"conf {dec(ml.get('confidence'), 0)}" if has_market and
                   ml.get("confidence") is not None else None)))

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
    # verdict rows carry the recommendation there instead of in pick (see
    # market()''s docstring) -- both are scanned so a BET/PASS verdict still
    # colours the embed correctly.
    picks = " ".join(
        f"{row.get('pick') or ''} {row.get('verdict') or ''}".upper()
        for row in rows)
    if "STRONG" in picks:
        return COLOR_STRONG
    if "BET" in picks or "OVER" in picks or "UNDER" in picks or "HOME" in picks \
            or "AWAY" in picks or "YES" in picks:
        return COLOR_BET
    if "PASS" in picks:
        return COLOR_PASS
    return COLOR_INFO


def _signal_badge(pick: Optional[str]) -> Optional[str]:
    """Bold emoji badge for one market row.

    Goes far beyond the single `pick` string: subscribers asked for a clearly
    scannable table where a STRONG/BET/PASS signal is visible at a glance
    instead of buried in a line of model percentages. `pick` and `verdict`
    already carry the canonical uppercase tokens the tone logic scans; this
    renders the SAME tokens with a colour-consistent emoji so the card reads
    like a table row heading rather than a footnote.

    Returns None when there is no actionable token (projection-only rows like
    "Team goals" keep their bare numbers -- no badge is a statement that the
    row is informational, not a recommendation).
    """
    text = " ".join(str(pick or "").split()).upper()
    if "STRONG" in text:
        return "🟢 **STRONG**"
    # PASS is tested before YES/NO, and YES/NO match whole words only: the
    # verdict "PASS — Moneyline: no market odds supplied" contains "NO" inside
    # "no market", which badged a declined market as a blue YES/NO call.
    if "PASS" in text or "NO BET" in text:
        return "⚪ **PASS**"
    if "BET" in text or "OVER" in text or "UNDER" in text:
        return "🔵 **BET**"
    if re.search(r"\b(YES|NO|YRFI|NRFI)\b", text):
        return "🔵 **YES/NO**"
    return None


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
        if row.get("verdict"):
            # Verdict-first rendering: the one unambiguous line goes first
            # and bold, ahead of the supporting model/market/edge numbers --
            # see market()'s docstring for why. `pick` is intentionally not
            # rendered here: verdict already carries what pick would have
            # (the recommendation), plus the side and the price, which pick
            # alone did not. The signal badge (🟢 STRONG / 🔵 BET / ⚪ PASS)
            # sits on the field NAME so it stays on the left edge of the
            # three-across grid where the eye lands first.
            signal = _signal_badge(row.get("verdict") or row.get("pick"))
            body = f"**{row['verdict']}**"
            numbers: List[str] = []
            if row["market"]:
                numbers.append(f"mkt {row['market']}")
            if row["edge"]:
                numbers.append(f"edge {row['edge']}")
            if row["model"]:
                body += "\n" + row["model"]
            if numbers:
                body += "\n" + "  ".join(numbers)
            if row["extra"]:
                body += f"\n*{row['extra']}*"
            fields.append({"name": f"{signal + ' ' if signal else ''}{row['name']}",
                           "value": body or "​", "inline": True})
            continue

        # A model value that already carries its own markup (the per-team
        # labels from pair(), one side per line) is not re-bolded: wrapping a
        # multi-line, already-bold block in another ** pair renders the
        # asterisks literally. Its support numbers go on their own line.
        support: List[str] = []
        if row["market"]:
            support.append(f"mkt {row['market']}")
        if row["edge"]:
            support.append(f"edge {row['edge']}")
        if row["model"] and "**" in row["model"]:
            body = row["model"] + ("\n" + "  ".join(support) if support else "")
        else:
            parts = ([f"**{row['model']}**"] if row["model"] else []) + support
            body = "  ".join(parts)
        if row["pick"]:
            body = f"{body}\n{row['pick']}" if body else row["pick"]
        if row["extra"]:
            body = f"{body}\n*{row['extra']}*" if body else f"*{row['extra']}*"
        signal = _signal_badge(row.get("pick"))
        fields.append({"name": f"{signal + ' ' if signal else ''}{row['name']}",
                       "value": body or "​", "inline": True})

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
