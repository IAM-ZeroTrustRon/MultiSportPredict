"""One-command tennis research package: source history, all markets, context and saved review."""
import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path

from sports_feed import ROOT, atomic_json, today
from tennis_package_source import BASE, page, parse_history, prepare_fixture

LATEST = ROOT / "data/tennis/full_review.json"


def metric(rows, name, surface):
    own = [r for r in rows if name in (r["winner_name"], r["loser_name"]) and r["surface"] == surface]
    latest = sorted(own, key=lambda r:r["tournament_date"], reverse=True)[:10]
    wins = sum(r["winner_name"] == name for r in latest)
    return dict(surface=surface, matches=len(own), wins=sum(r["winner_name"] == name for r in own),
                recent10=f"{wins}-{len(latest)-wins}", latest=latest[0]["tournament_date"] if latest else None,
                mean_games=sum(r["games"] for r in latest)/len(latest) if latest else None)


def render(package):
    result, names = package["result"], package["names"]
    lines = [f"# {names[0]} vs {names[1]}",
             f"{package['tournament']} | {package['game_date']} | {package['surface']} | Best of 3",
             f"Captured: {package['captured_at']}", f"Source: {package['source_url']}", "",
             "EXPERIMENTAL MODEL REVIEW — estimates are uncalibrated, not verified betting recommendations.",
             "Opponent histories are incomplete for Challenger/ITF players; new opponents start at the Elo prior.",
             "", "## Model and measured results"]
    for name in names:
        m = package["metrics"][name]
        lines += [f"{name}: Elo {result['elo_ratings'][name]:.0f}; {result['match_counts'][name]} matches in run history.",
                  f"Sourced 2025–2026 {m['surface']} singles: {m['wins']}/{m['matches']} wins; latest ten {m['recent10']}; "
                  f"mean games {m['mean_games']:.1f}." if m['mean_games'] is not None else "No measured games available."]
    holds = result.get("serve_return_inputs")
    lines += [f"Serve/return inputs: {holds['source'] if holds else 'No measured player point counts; 75% hold prior.'}",
              "", "## Moneyline"]
    ml = package.get("moneyline")
    prob = result["moneyline"]["home_win_prob"]
    lines += [f"Model: {names[0]} {prob:.1%} | {names[1]} {1-prob:.1%}"]
    if ml:
        lines += [f"{ml['bookmaker']}: {names[0]} {ml['home_ml']:+g} | {names[1]} {ml['away_ml']:+g}",
                  f"Quote update: {ml['last_update']}"]
        priced = result.get("moneyline_ev") or {}
        for side, label in (("home",names[0]),("away",names[1])):
            # price_market calls sides a/b; retrieve explicitly below if present.
            value = priced.get("ev_a" if side == "home" else "ev_b")
            if value is not None:
                lines.append(f"{label} model EV: {value:.1%}")
    else:
        lines.append("MISSING: paired moneyline odds. Supply --p1-ml and --p2-ml.")
    lines += ["Model verdict: " + str(result['moneyline'].get('recommendation') or 'PASS'),
              "", "## Every available alternative market"]
    for m in result["alternative_markets"]:
        total = m["kind"].endswith("total")
        a,b = ("Over","Under") if total else tuple(names)
        lines += [f"{m['kind']} {m['line']:+g}: {a} {m['prob_a']:.1%} | {b} {m['prob_b']:.1%} | push {m['push_prob']:.1%}"]
        if m.get("price_a") is not None and m.get("price_b") is not None:
            lines += [f"  {m.get('bookmaker','Manual')}: {a} {m['price_a']:+g} (model EV {m['ev_a']:+.1%}) | "
                      f"{b} {m['price_b']:+g} (model EV {m['ev_b']:+.1%})",
                      f"  Quote update: {m.get('last_update','unknown')}. Verdict: MODEL ONLY — not calibrated."]
        else:
            lines.append("  Unpriced reference line. PASS — no bookmaker prices; model probabilities only.")
    lines += ["", "## Observations — reviewed, no invented numerical effects"]
    for name, item in package["context"]["players"].items():
        lines.append(name + ":")
        labels={"current_rank":"Ranking", "injury_status":"Current injury status", "historical_retirement_notes":"Historical retirement entries",
                "travel_status":"Travel / arrival", "venue_notes":"Venue", "recent_results_notes":"Recent form"}
        for key in labels:
            if item.get(key) is not None:
                lines.append(f"  {labels[key]}: {item[key]}")
    lines += ["", "## Missing inputs", *package["missing"], "", package["schedule_note"],
              "Sourced results and market data are refreshed automatically. Injury diagnoses and arrival times remain unknown unless sourced."]
    return "\n".join(lines) + "\n"


def push(package):
    # Keep the entire market report attached: Discord's embed limits must not hide alternatives.
    import requests
    from discord_integration import _get_target_webhooks
    hooks = _get_target_webhooks()
    if not hooks:
        raise ValueError("Needed: DISCORD_WEBHOOK_URL in .env")
    text = render(package)
    payload = {"content": "Tennis full review — captured model estimates and sourced observations; all markets in attached report.",
               "embeds": [{"title": " vs ".join(package["names"]), "description":
                   f"{package['tournament']} | {package['game_date']}\nExperimental, uncalibrated. Captured {package['captured_at']}",
                   "url": package["source_url"], "color": 3066993}]}
    for hook in hooks:
        try:
            response = requests.post(hook, data={"payload_json":json.dumps(payload)},
                files={"files[0]":("tennis_full_review.md",text.encode("utf-8"),"text/markdown")},timeout=30)
        except requests.RequestException as exc:
            raise ValueError("Discord connection failed: " + type(exc).__name__) from None
        if response.status_code not in (200,204):
            raise ValueError(f"Discord HTTP {response.status_code}")
    print(f"Pushed captured full report to {len(hooks)} configured Discord destination(s).")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--match", help='"First Player vs Second Player"')
    ap.add_argument("--source-url", help="Optional exact TennisExplorer match URL if discovery is ambiguous")
    ap.add_argument("--context", type=Path, help="Optional fresh sourced observations; automatically created otherwise")
    ap.add_argument("--refresh", action="store_true", help="Bypass the 15-minute source-page cache")
    ap.add_argument("--allow-thin", action="store_true", help="Explicit experimental review if fewer than eight real matches")
    ap.add_argument("--push", action="store_true", help="Push the last captured full review; no refetch or recalculation")
    ap.add_argument("--p1-ml", type=float)
    ap.add_argument("--p2-ml", type=float)
    args = ap.parse_args(argv)
    if args.push:
        if not LATEST.exists():
            ap.error("No full review saved. Run --match first.")
        push(json.loads(LATEST.read_text(encoding="utf-8")))
        return
    if not args.match:
        ap.error("Needed: --match with both player names")
    from run_tennis import parse_match, resolve, american_to_prob, no_vig
    from models.tennis_elo import TennisElo
    typed = parse_match(args.match)
    store = json.loads((ROOT / "data/tennis/players.json").read_text(encoding="utf-8-sig"))
    names = []
    for name in typed:
        resolved, reason = resolve(name, store)
        if resolved is None:
            ap.error(f"Cannot identify {name}: {reason}")
        names.append(resolved)
    print("Fetching verified fixture, Challenger history and all market types...",flush=True)
    fixture = prepare_fixture(names, args.source_url, args.refresh)
    profiles = fixture["profiles"]
    supplemented = []
    year = int(fixture["game_date"][:4])
    for name, (path,soup) in profiles.items():
        for season in (year-1,year):
            season_soup = soup if season == year else page(path+f"?annual={season}",args.refresh)
            supplemented += parse_history(season_soup, season, fixture["game_date"])
    # Preserve known full-name identities; source headings remain identities for unknown opponents.
    aliases = {path:name for name,(path,_) in profiles.items()}
    display = {r[k+"_path"]:r[k+"_display"] for r in supplemented for k in ("winner","loser")}
    for path, abbreviated in display.items():
        if path not in aliases:
            name, _ = resolve(abbreviated, store)
            if name is None:
                heading = page(path).select_one("table.plDetail h3")
                if heading is None:
                    raise ValueError(f"Cannot identify opponent profile {path}")
                name = "TE: " + heading.get_text(strip=True)
            aliases[path] = name
    unique = {}
    for r in supplemented:
        r = dict(r, winner_name=aliases[r["winner_path"]],loser_name=aliases[r["loser_path"]],source="TennisExplorer completed singles")
        unique[r["match_id"]] = r
    supplemented = list(unique.values())
    print(f"Fetched {len(supplemented)} completed singles results (retirements excluded).",flush=True)
    with (ROOT / "data/tennis/matches.csv").open(encoding="utf-8",newline="") as f:
        base = [r for r in csv.DictReader(f) if r["tournament_date"] < fixture["game_date"]]
    # The archive sometimes dates a whole tournament on its start day. Replace overlapping pair results.
    pairs = {}
    for r in supplemented:
        pairs.setdefault((r["winner_name"],r["loser_name"],r["surface"]),[]).append(dt.date.fromisoformat(r["tournament_date"]))
    base = [r for r in base if not any(abs((dt.date.fromisoformat(r["tournament_date"])-d).days)<=7
             for d in pairs.get((r["winner_name"],r["loser_name"],r["surface"]),[]))]
    merged = sorted(base+supplemented,key=lambda r:(r["tournament_date"],r.get("match_id","")))
    slug = re.sub(r"[^a-z0-9]+","_","_vs_".join(names).lower()).strip("_")
    out = ROOT / "output/tennis";out.mkdir(parents=True,exist_ok=True)
    history_path = out / (slug+"_history.csv")
    with history_path.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=["winner_name","loser_name","surface","tournament_date"],extrasaction="ignore")
        writer.writeheader();writer.writerows(merged)
    engine=TennisElo();engine.load_match_history(str(history_path))
    missing = []
    for name in names:
        count = engine.get_match_count(name)
        if count < 8 and not args.allow_thin:
            raise ValueError(f"{name}: only {count} matches even after refresh; use --allow-thin for an experimental review")
        if count < 8:
            missing.append(f"{name}: fewer than eight real results; explicit thin-data override.")
    metrics = {n:metric(supplemented,n,fixture["surface"]) for n in names}
    context = {"players":{}}
    for name, (_,soup) in profiles.items():
        injury=soup.select_one("table.injured")
        retirement_notes = "; ".join(r.get_text(" ",strip=True) for r in injury.select("tr")[1:4]) if injury else "No historical retirement entries shown; this is not medical clearance."
        rank = next((x.get_text(strip=True) for x in soup.select("table.plDetail .date") if "rank - singles" in x.get_text()),"Unknown")
        context["players"][name] = dict(source=fixture["source_url"],as_of=today(),elo_adjustment=0,
            injury_status="unknown",current_rank=rank,historical_retirement_notes=retirement_notes,
            travel_status="Actual departure, arrival and acclimatization unknown.",
            venue_notes=f"{fixture['tournament']}, {fixture['surface']}; recent results establish participation, not arrival time.",
            recent_results_notes=f"Sourced {fixture['surface']} record: {metrics[name]['wins']}/{metrics[name]['matches']} wins; latest ten {metrics[name]['recent10']}. Last result {metrics[name]['latest']}.")
    if args.context:
        supplied=json.loads(args.context.read_text(encoding="utf-8-sig"))
        if not isinstance(supplied.get("players"),dict):
            raise ValueError("Context needs a players object")
        context["players"].update(supplied["players"])
    context_path=out/(slug+"_context.json");atomic_json(context_path,context)
    quotes={}
    for row in fixture["markets"]:
        key=(row["kind"],row["line"])
        # Select one complete book quote per line, never combine opposing prices across books.
        preferred={"Pinnacle":0,"bet365":1,"BetRivers":2,"1xBet":3}
        if key not in quotes or preferred.get(row["bookmaker"],100)<preferred.get(quotes[key]["bookmaker"],100):
            quotes[key]=row
    ml=next((r for r in fixture["moneylines"] if r["bookmaker"]=="Pinnacle"),fixture["moneylines"][0] if fixture["moneylines"] else None)
    if args.p1_ml is not None or args.p2_ml is not None:
        if args.p1_ml is None or args.p2_ml is None:
            ap.error("Both --p1-ml and --p2-ml are required together")
        ml=dict(home_ml=args.p1_ml,away_ml=args.p2_ml,bookmaker="Manual",last_update="user supplied")
    probability=no_vig(american_to_prob(ml["home_ml"]),american_to_prob(ml["away_ml"])) if ml else None
    from models.tennis_predictor import predict_tennis_match
    result=predict_tennis_match(names[0],names[1],surface=fixture["surface"],best_of_5=False,tournament=fixture["tournament"],round_name=fixture["round_name"],
        market_prob=probability,market_home_odds=str(ml["home_ml"]) if ml else None,
        market_away_odds=str(ml["away_ml"]) if ml else None,elo_engine=engine,custom_markets=list(quotes.values()),player_context=context)
    result["game_date"]=fixture["game_date"]
    for kind in ("games_total","sets_total","games_spread","sets_spread"):
        if not any(r["kind"]==kind for r in fixture["markets"]):
            missing.append(f"No source prices for {kind}; unpriced reference estimate only.")
    missing += ["Current injury diagnosis/status and verified arrival time unknown.",
                "Opponent-complete Challenger history and calibrated serve/return model unavailable."]
    package=dict(names=names,result=result,context=context,metrics=metrics,moneyline=ml,
        tournament=fixture["tournament"],game_date=fixture["game_date"],surface=fixture["surface"],
        source_url=fixture["source_url"],captured_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        missing=missing,schedule_note=fixture["schedule_note"],context_path=str(context_path),history_path=str(history_path))
    atomic_json(LATEST,package);atomic_json(out/(slug+"_review.json"),package)
    text=render(package);report=out/(slug+"_review.md");report.write_text(text,encoding="utf-8")
    print(text);print(f"Context JSON: {context_path}\nFull report: {report}")
    print("No database bets or Discord messages created. Push captured report: venv/Scripts/python.exe run_tennis_full.py --push")


if __name__ == "__main__":
    try:
        main()
    except (ValueError,OSError) as exc:
        raise SystemExit(str(exc))
