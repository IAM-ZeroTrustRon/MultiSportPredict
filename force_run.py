#!/usr/bin/env python
"""force_run.py - run any game, with props, through a points model. No guards.

For games the normal runners refuse: leagues with no store (Australian NBL,
NCAAF, anything else), teams with too few games, stale data. The store, the
data guard, the fixture guard and the minimum-games floors are all bypassed.

What is NOT bypassed: every number must be supplied. This script never fills a
missing input with a league average -- that is the bug that produced fake
edges in this project for months. A missing required input stops the run and
names the field.

Results are never written to multisport_history.db, so forced runs cannot
touch the graded record. Output goes to output/forced/.

Sports: basketball, nfl, ncaaf (any points-based league), and soccer
(Poisson goals model: 1X2, over/under, BTTS, draw no bet, double chance).
Soccer "pts_for"/"pts_against" are GOALS per game. Soccer prices are American.

Run from Git Bash:
    python force_run.py output/forced/inputs/<game>.json            # run
    python force_run.py output/forced/inputs/<game>.json --push     # run + Discord
    python force_run.py --template > output/forced/inputs/new.json  # blank input
"""
import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output" / "forced"

# Spread of real outcomes around the projection. Standard published figures;
# each is printed with the result so it is never hidden.
SPORT = {
    #              margin SD, total SD, home adv (pts), 1H share, 1Q share
    "basketball": dict(margin_sd=12.0, total_sd=17.0, hfa=2.0, h1=0.49, q1=0.25),
    "nfl":        dict(margin_sd=13.5, total_sd=13.0, hfa=1.8, h1=0.50, q1=0.24),
    "ncaaf":      dict(margin_sd=17.0, total_sd=16.0, hfa=2.5, h1=0.51, q1=0.25),
    # Soccer: expected goals = mean(own goals for, opponent goals against),
    # times a home/away multiplier. Override with "home_mult"/"away_mult".
    "soccer":     dict(home_mult=1.10, away_mult=0.90),
}
SOCCER_MARKET_KEYS = ("ml_home", "ml_draw", "ml_away", "total", "over_price",
                      "under_price", "btts_yes", "btts_no", "dnb_home",
                      "dnb_away", "dc_1x", "dc_x2", "dc_12")
PROP_SHRINK_K = 5      # games before a player's own average outweighs the line
LEAN, BET = 3.0, 6.0   # edge thresholds in percentage points

TEMPLATE = {
    "sport": "basketball",
    "league": "NBL",
    "date": "YYYY-MM-DD",
    "start_et": "5:30 AM ET",
    "venue": "",
    "home": {"name": "", "pts_for": None, "pts_against": None, "games": None,
             "source": ""},
    "away": {"name": "", "pts_for": None, "pts_against": None, "games": None,
             "source": ""},
    "league_avg_pts": None,
    "regress": 0.0,
    "adjustments": [
        {"side": "away", "points": 0.0, "reason": "e.g. travel / back-to-back"}
    ],
    "market": {"spread_home": None, "spread_home_price": None,
               "spread_away_price": None, "total": None,
               "over_price": None, "under_price": None,
               "ml_home": None, "ml_away": None,
               "h1_spread_home": None, "h1_total": None,
               "q1_spread_home": None, "q1_total": None,
               "q1_home_total": None, "q1_away_total": None},
    "props": [
        {"player": "", "team": "home", "stat": "points", "avg": None,
         "games": None, "line": None, "over": -110, "under": -110, "sd": None,
         "source": ""}
    ],
}


# ---------------------------------------------------------------- maths
def phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def implied(american):
    if american is None:
        return None
    a = float(american)
    return 100.0 / (a + 100.0) if a > 0 else -a / (-a + 100.0)


def no_vig(a, b):
    pa, pb = implied(a), implied(b)
    if pa is None or pb is None:
        return None, None
    s = pa + pb
    return pa / s, pb / s


def fair_american(p: float) -> str:
    p = min(max(p, 0.001), 0.999)
    return f"{-round(p / (1 - p) * 100)}" if p >= 0.5 else f"+{round((1 - p) / p * 100)}"


def call(edge_pct: float) -> str:
    if edge_pct >= BET:
        return "BET"
    if edge_pct >= LEAN:
        return "LEAN"
    return "PASS"


# ---------------------------------------------------------------- checks
def need(d: dict, key: str, where: str, missing: list):
    if d.get(key) is None or d.get(key) == "":
        missing.append(f"{where}.{key}")
    return d.get(key)


def validate(inp: dict) -> list:
    missing = []
    if inp.get("sport") not in SPORT:
        missing.append(f"sport (one of {', '.join(SPORT)})")
    for side in ("home", "away"):
        t = inp.get(side) or {}
        for k in ("name", "pts_for", "pts_against", "source"):
            need(t, k, side, missing)
    for i, p in enumerate(inp.get("props") or []):
        if not p.get("player"):
            continue                       # blank template row: ignored
        for k in ("team", "stat", "avg", "line", "source"):
            need(p, k, f"props[{i}]", missing)
    return missing


# ---------------------------------------------------------------- model
def _pois(lam: float, k: int) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


def run_soccer(inp: dict) -> dict:
    cfg = SPORT["soccer"]
    h, a = inp["home"], inp["away"]
    avg = inp.get("league_avg_pts")
    avg_src = "supplied"
    if avg is None:
        avg = (h["pts_for"] + h["pts_against"] + a["pts_for"] + a["pts_against"]) / 4
        avg_src = "mean of the two teams' supplied for/against"
    rg = float(inp.get("regress") or 0)
    def pull(x): return x + (avg - x) * rg
    hf, ha, af, aa = (pull(h["pts_for"]), pull(h["pts_against"]),
                      pull(a["pts_for"]), pull(a["pts_against"]))
    hm = float(inp.get("home_mult", cfg["home_mult"]))
    am = float(inp.get("away_mult", cfg["away_mult"]))
    lh, la = (hf + aa) / 2 * hm, (af + ha) / 2 * am
    notes = [f"inputs regressed {rg:.0%} toward average"] if rg else []
    for adj in inp.get("adjustments") or []:
        g = float(adj.get("points") or 0)
        if not g:
            continue
        if adj.get("side") == "home":
            lh += g
        elif adj.get("side") == "away":
            la += g
        notes.append(f"{adj.get('side')} {g:+.2f} goals: {adj.get('reason', '')}")
    lh, la = max(lh, 0.05), max(la, 0.05)

    grid = [[_pois(lh, i) * _pois(la, j) for j in range(12)] for i in range(12)]
    cells = [(i, j, grid[i][j]) for i in range(12) for j in range(12)]
    ph = sum(p for i, j, p in cells if i > j)
    pd = sum(p for i, j, p in cells if i == j)
    pa = sum(p for i, j, p in cells if i < j)
    btts = sum(p for i, j, p in cells if i > 0 and j > 0)
    m = inp.get("market") or {}
    rows = []

    def add(market, line, pick, prob, price, push=0.0):
        # Edge = win prob minus the break-even of the price actually offered.
        # With a push (draw no bet) the break-even is scaled by the no-push share.
        if price is None:
            return
        be = implied(price)
        eff = prob / (1 - push) if push < 1 else 0
        edge = (eff - be) * 100
        rows.append(dict(market=market, line=line, pick=pick, prob=eff,
                         fair=fair_american(eff), edge=edge, call=call(edge),
                         price=price))

    add("1X2", "home", f"HOME ({h['name']})", ph, m.get("ml_home"))
    add("1X2", "draw", "DRAW", pd, m.get("ml_draw"))
    add("1X2", "away", f"AWAY ({a['name']})", pa, m.get("ml_away"))
    add("Draw no bet", "home", f"HOME ({h['name']})", ph, m.get("dnb_home"), push=pd)
    add("Draw no bet", "away", f"AWAY ({a['name']})", pa, m.get("dnb_away"), push=pd)
    add("Double chance", "1X", f"{h['name']} or draw", ph + pd, m.get("dc_1x"))
    add("Double chance", "X2", f"{a['name']} or draw", pa + pd, m.get("dc_x2"))
    add("Double chance", "12", "either team wins", ph + pa, m.get("dc_12"))
    line = m.get("total")
    if line is not None:
        over = sum(p for i, j, p in cells if i + j > line)
        exact = sum(p for i, j, p in cells if i + j == line)   # whole-number lines push
        under = 1 - over - exact
        add("Total", f"{line:g}", "OVER", over, m.get("over_price") or -110, push=exact)
        add("Total", f"{line:g}", "UNDER", under, m.get("under_price") or -110, push=exact)
    add("BTTS", "yes", "YES", btts, m.get("btts_yes"))
    add("BTTS", "no", "NO", 1 - btts, m.get("btts_no"))

    top = sorted(cells, key=lambda c: -c[2])[:3]
    thin = [f"{t['name']} ({t.get('games')} games)"
            for t in (h, a) if (t.get("games") or 0) < 5]
    return dict(home=h["name"], away=a["name"], proj_home=round(lh, 2),
                proj_away=round(la, 2), margin=round(lh - la, 2),
                total=round(lh + la, 2), p_home_win=ph, p_draw=pd, p_away_win=pa,
                p_btts=btts,
                likely_scores=[f"{i}-{j} ({p:.1%})" for i, j, p in top],
                league_avg=round(avg, 2), league_avg_source=avg_src,
                hfa=f"x{hm:g} home / x{am:g} away", adjustments=notes,
                markets=rows, props=[], thin_samples=thin, settings=cfg)


def run(inp: dict) -> dict:
    if inp["sport"] == "soccer":
        return run_soccer(inp)
    cfg = SPORT[inp["sport"]]
    h, a = inp["home"], inp["away"]
    avg = inp.get("league_avg_pts")
    avg_src = "supplied"
    if avg is None:
        # Not a league default: the mean of the four numbers actually supplied.
        avg = (h["pts_for"] + h["pts_against"] + a["pts_for"] + a["pts_against"]) / 4
        avg_src = "mean of the two teams' supplied for/against"

    # Prior-season numbers overstate how different teams are once rosters
    # change. "regress" pulls each supplied figure that fraction of the way
    # back to the average (0.3 = the NFL model's prior-season setting).
    rg = float(inp.get("regress") or 0)
    def pull(x): return x + (avg - x) * rg
    hf, ha, af, aa = (pull(h["pts_for"]), pull(h["pts_against"]),
                      pull(a["pts_for"]), pull(a["pts_against"]))
    hfa = inp.get("home_adv", cfg["hfa"])
    home = avg + (hf - avg) + (aa - avg) + hfa
    away = avg + (af - avg) + (ha - avg)
    notes = [f"inputs regressed {rg:.0%} toward average"] if rg else []
    for adj in inp.get("adjustments") or []:
        pts = float(adj.get("points") or 0)
        if not pts:
            continue
        if adj.get("side") == "home":
            home += pts
        elif adj.get("side") == "away":
            away += pts
        notes.append(f"{adj.get('side')} {pts:+.1f}: {adj.get('reason', '')}")

    margin, total = home - away, home + away
    m = inp.get("market") or {}
    rows = []

    def spread_row(label, proj_margin, sd, line, home_price=None, away_price=None):
        if line is None:
            return
        p_home = phi((proj_margin + line) / sd)
        # Price both sides; the better bet is the bigger edge, which with
        # lopsided prices is not always the more likely side.
        opts = []
        for s, pr, price in (("HOME", p_home, home_price), ("AWAY", 1 - p_home, away_price)):
            be = implied(price) if price is not None else 0.5238   # -110 default
            opts.append(((pr - be) * 100, s, pr))
        edge, side, p = max(opts)
        rows.append(dict(market=f"{label} spread", line=f"home {line:+g}",
                         pick=f"{side} ({h['name'] if side == 'HOME' else a['name']})",
                         prob=p, fair=fair_american(p), edge=edge, call=call(edge)))

    def total_row(label, proj_total, sd, line, over_price=None, under_price=None):
        if line is None:
            return
        p_over = 1 - phi((line - proj_total) / sd)
        opts = []
        for s, pr, price in (("OVER", p_over, over_price), ("UNDER", 1 - p_over, under_price)):
            be = implied(price) if price is not None else 0.5238
            opts.append(((pr - be) * 100, s, pr))
        edge, pick, p = max(opts)
        rows.append(dict(market=f"{label} total", line=f"{line:g}", pick=pick,
                         prob=p, fair=fair_american(p), edge=edge, call=call(edge),
                         proj=round(proj_total, 1)))

    # full game
    spread_row("Game", margin, cfg["margin_sd"], m.get("spread_home"),
               m.get("spread_home_price"), m.get("spread_away_price"))
    total_row("Game", total, cfg["total_sd"], m.get("total"),
              m.get("over_price"), m.get("under_price"))
    p_home_win = phi(margin / cfg["margin_sd"])
    nv_h, nv_a = no_vig(m.get("ml_home"), m.get("ml_away"))
    if nv_h is not None:
        edge_h = (p_home_win - nv_h) * 100
        side = "HOME" if edge_h > 0 else "AWAY"
        edge = abs(edge_h)
        rows.append(dict(market="Game moneyline",
                         line=f"{m['ml_home']:+g}/{m['ml_away']:+g}",
                         pick=f"{side} ({h['name'] if side == 'HOME' else a['name']})",
                         prob=p_home_win if side == "HOME" else 1 - p_home_win,
                         fair=fair_american(p_home_win) + " home",
                         edge=edge, call=call(edge)))

    # segments
    for label, share, k in (("1H", cfg["h1"], "h1"), ("1Q", cfg["q1"], "q1")):
        seg_sd_m = cfg["margin_sd"] * math.sqrt(share)
        seg_sd_t = cfg["total_sd"] * math.sqrt(share)
        spread_row(label, margin * share, seg_sd_m, m.get(f"{k}_spread_home"),
                   m.get(f"{k}_spread_home_price"), m.get(f"{k}_spread_away_price"))
        total_row(label, total * share, seg_sd_t, m.get(f"{k}_total"),
                  m.get(f"{k}_over_price"), m.get(f"{k}_under_price"))
        for side_key, proj in (("home", home * share), ("away", away * share)):
            line = m.get(f"{k}_{side_key}_total")
            if line is not None:
                total_row(f"{label} {inp[side_key]['name']} team", proj,
                          seg_sd_t / math.sqrt(2), line,
                          m.get(f"{k}_{side_key}_over_price"),
                          m.get(f"{k}_{side_key}_under_price"))

    # props
    props = []
    for p in inp.get("props") or []:
        if not p.get("player"):
            continue
        g = p.get("games") or 0
        w = g / (g + PROP_SHRINK_K)
        proj = w * p["avg"] + (1 - w) * p["line"]
        sd = p.get("sd") or max(1.5, 0.35 * proj)
        p_over = 1 - phi((p["line"] - proj) / sd)
        opts = []
        for s, pr, price in (("OVER", p_over, p.get("over")), ("UNDER", 1 - p_over, p.get("under"))):
            be = implied(price) if price is not None else 0.5238
            opts.append(((pr - be) * 100, s, pr))
        edge, pick, prob = max(opts)
        props.append(dict(player=p["player"], stat=p["stat"], line=p["line"],
                          avg=p["avg"], games=g, proj=round(proj, 1),
                          sd=round(sd, 1), sd_default=p.get("sd") is None,
                          pick=pick, prob=prob, edge=edge, call=call(edge)))

    thin = [f"{t['name']} ({t.get('games')} games)"
            for t in (h, a) if (t.get("games") or 0) < 5]
    return dict(home=h["name"], away=a["name"], proj_home=round(home, 1),
                proj_away=round(away, 1), margin=round(margin, 1),
                total=round(total, 1), p_home_win=p_home_win,
                league_avg=round(avg, 1), league_avg_source=avg_src,
                hfa=hfa, adjustments=notes, markets=rows, props=props,
                thin_samples=thin, settings=cfg)


# ---------------------------------------------------------------- output
def print_result(inp: dict, r: dict) -> None:
    print("=" * 78)
    print(f"  FORCED RUN - guards off - {inp.get('league', '')} {inp.get('date', '')}")
    print(f"  {r['away']} @ {r['home']}")
    print("=" * 78)
    print(f"  Projection   {r['home']} {r['proj_home']}  -  {r['away']} {r['proj_away']}")
    print(f"  Margin {r['margin']:+.1f} home   Total {r['total']}   "
          f"Home win {r['p_home_win']:.1%}")
    if "p_draw" in r:
        print(f"  1X2  home {r['p_home_win']:.1%}  draw {r['p_draw']:.1%}  "
              f"away {r['p_away_win']:.1%}   BTTS {r['p_btts']:.1%}")
        print(f"  Likely scores  {', '.join(r['likely_scores'])}")
    print(f"  League avg {r['league_avg']} ({r['league_avg_source']})   "
          f"Home adv {r['hfa']}")
    for n in r["adjustments"]:
        print(f"  Adjustment   {n}")
    if r["thin_samples"]:
        print(f"  THIN SAMPLE  {', '.join(r['thin_samples'])} - treat as low confidence")
    print()
    print(f"  {'MARKET':<34}{'LINE':>12}  {'PICK':<26}{'PROB':>7}{'EDGE':>7}  CALL")
    for x in r["markets"]:
        print(f"  {x['market']:<34}{x['line']:>12}  {x['pick']:<26}"
              f"{x['prob']:>6.1%}{x['edge']:>+6.1f}  {x['call']}")
    if r["props"]:
        print()
        print(f"  {'PROP':<34}{'LINE':>6}{'PROJ':>7}{'SD':>6}  {'PICK':<6}{'PROB':>7}{'EDGE':>7}  CALL")
        for p in r["props"]:
            flag = "*" if p["sd_default"] else " "
            print(f"  {(p['player'] + ' ' + p['stat'])[:33]:<34}{p['line']:>6}"
                  f"{p['proj']:>7}{p['sd']:>5}{flag}  {p['pick']:<6}"
                  f"{p['prob']:>6.1%}{p['edge']:>+6.1f}  {p['call']}")
        print("  * default SD (35% of projection). Props shrink toward the line "
              f"until a player has ~{PROP_SHRINK_K} games.")
    print()
    print("  Not stored in multisport_history.db. Edges assume -110 where no price was given.")
    print("=" * 78)


def card(inp: dict, r: dict) -> dict:
    plays = [x for x in r["markets"] if x["call"] != "PASS"]
    plays += [dict(market=f"{p['player']} {p['stat']}", line=str(p["line"]),
                   pick=p["pick"], edge=p["edge"], call=p["call"])
              for p in r["props"] if p["call"] != "PASS"]
    plays.sort(key=lambda x: -x["edge"])
    play_txt = "\n".join(f"**{x['call']}** {x['market']} {x['line']} -> {x['pick']} "
                         f"({x['edge']:+.1f})" for x in plays[:8]) or "No edges - PASS"
    fields = [
        {"name": "Projection", "inline": False, "value":
            f"{r['home']} {r['proj_home']} - {r['away']} {r['proj_away']}\n"
            f"Total {r['total']} | Home win {r['p_home_win']:.1%}"
            + (f" | Draw {r['p_draw']:.1%} | Away {r['p_away_win']:.1%}\n"
               f"Likely: {', '.join(r['likely_scores'])}" if "p_draw" in r else "")},
        {"name": "Plays (edge, pct pts)", "inline": False, "value": play_txt[:1020]},
    ]
    if r["adjustments"]:
        fields.append({"name": "Adjustments", "inline": False,
                       "value": "\n".join(r["adjustments"])[:1020]})
    if r["thin_samples"]:
        fields.append({"name": "Thin sample", "inline": False,
                       "value": ", ".join(r["thin_samples"])[:1020]})
    return {
        "title": f"{inp.get('league', '')} | {r['away']} @ {r['home']}"[:256],
        "description": ("**FORCED RUN - model math on web-sourced inputs, guards off.**\n"
                        f"{inp.get('date', '')} {inp.get('start_et', '')} {inp.get('venue', '')}")[:4000],
        "color": 0xDD6B20,
        "fields": fields,
        "footer": {"text": "MultiSportPredict - FORCED RUN, not stored, not graded"},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="?", type=Path)
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--template", action="store_true")
    args = ap.parse_args()

    if args.template:
        print(json.dumps(TEMPLATE, indent=2))
        return
    if not args.inputs or not args.inputs.exists():
        sys.exit("Give an inputs file. Blank one: python force_run.py --template")

    inp = json.loads(args.inputs.read_text(encoding="utf-8-sig"))
    missing = validate(inp)
    if missing:
        print("[STOPPED] These inputs are required and were not supplied:")
        for m in missing:
            print(f"  - {m}")
        print("Nothing is ever filled with a league average. Add them and re-run.")
        sys.exit(1)

    r = run(inp)
    print_result(inp, r)

    OUT.mkdir(parents=True, exist_ok=True)
    stem = args.inputs.stem
    (OUT / f"{stem}.result.json").write_text(json.dumps(r, indent=2, default=str))
    c = card(inp, r)
    (OUT / f"{stem}.card.json").write_text(json.dumps(c, indent=2))
    print(f"Saved output/forced/{stem}.result.json and .card.json")

    if args.push:
        from discord_integration import _broadcast_embed   # only needed to send
        sent = _broadcast_embed(c, label=f"forced {stem}")
        print(f"Sent to {sent} destination(s)." if sent else
              "Nothing sent - check DISCORD_WEBHOOK_URL / bot settings in .env.")


if __name__ == "__main__":
    main()
