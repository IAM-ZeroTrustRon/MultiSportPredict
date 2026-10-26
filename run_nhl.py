"""Verified NHL fixtures, cached team models, immutable workflow and explicit odds."""
import argparse
import datetime as dt
import json
import math
import sys
import joblib
from pathlib import Path

from sports_feed import ROOT,today,atomic_json
from nhl_sources import stamp,utcnow
from features.nhl_features import pregame_features
from models.nhl_model import market_probabilities
from models.score_ratings import price_market
from models.basketball_readiness import observation_markets


def select_games(games,day,matches=None,now=None):
    now=stamp(now or utcnow());found=[]
    for g in games:
        if (g["date"]==day and not g["completed"] and g["status"] in {"FUT","PRE"}
                and stamp(g["start_time"])>now):found.append(g)
    if matches:
        from run_ncaaf import resolve
        names=sorted({g[s+"_team"] for g in games for s in ("home","away")})
        chosen=[]
        for text in matches:
            parts=text.split(" vs ")
            if len(parts)!=2:raise ValueError('Use --match "Home Team vs Away Team"')
            pair={resolve(p,names) for p in parts}
            hits=[g for g in found if {g["home_team"],g["away_team"]}==pair]
            if len(hits)!=1:raise ValueError("No unique upcoming NHL fixture for "+text)
            chosen.append(hits[0])
        found=chosen
    if not found:raise ValueError("No verified upcoming NHL games on "+day+"; completed/started fixtures are refused")
    return found


def forecast(game,data,model,specs,now=None,goalies=None):
    now=stamp(now or utcnow())
    if game["completed"] or stamp(game["start_time"])<=now:raise ValueError("NHL game already started/completed")
    if (now-stamp(data["retrieved_utc"])).total_seconds()>86400:raise ValueError("NHL feed stale; run msp.py refresh --sport nhl")
    for observed in (data['retrieved_utc'],game['retrieved_utc']):
        age=(now-stamp(observed)).total_seconds()
        if not -5<=age<=86400:raise ValueError('NHL fixture/source timestamp stale or in the future')
    if stamp(model.trained_before)>now or stamp(model.trained_before)>=stamp(game["start_time"]):
        raise ValueError("Model trained after the requested forecast cutoff")
    if (now-stamp(model.created_utc)).total_seconds()>7*86400:raise ValueError("NHL model stale; run train_nhl.py")
    if model.data_hash!=data["data_hash"]:raise ValueError("NHL history/model versions differ; run train_nhl.py")
    earlier=[g for g in data["games"] if stamp(g["start_time"])<now]
    features,obs=pregame_features(game,earlier)
    result=model.predict(features,game["season_type"]==3)
    d=result.pop("distribution")
    counts={s:obs[s]["season_games_played"] for s in ("home","away")}
    reasons=[]
    if game.get('neutral_site'):reasons.append('Neutral-site effect is not separately validated by this team baseline')
    # Provisional operational gate, not a claim of a validated season cutoff.
    if min(counts.values())<10:reasons.append("Observation policy: fewer than 10 current-season games for a team")
    v=model.validation
    if (v["winner_brier"] is None or v["winner_brier"]>=v["baseline_winner_brier"]
            or v["goal_deviance"]>=v["baseline_goal_deviance"]):
        reasons.append("Historical benchmark did not improve both baseline winner and scoring metrics")
    if max(v["goal_dispersion"])>v.get("dispersion_limit",1.5):reasons.append("Goal dispersion exceeds the Poisson operational limit")
    if d is None:reasons.append("No validated OT/SO component for this game type; eventual-winner markets unavailable")
    goalie_context=None
    if goalies is not None:
        if not isinstance(goalies,dict):raise ValueError('Goalie context must be a JSON object')
        if str(goalies.get("game_id"))!=game["game_id"]:raise ValueError("Goalie context game ID mismatch")
        if not -5<=(now-stamp(goalies["observed_utc"])).total_seconds()<=7200:raise ValueError("Goalie context older than two hours/future")
        for s in ("home","away"):
            detail=goalies.get(s,{})
            if (not isinstance(detail,dict) or str(detail.get("team_id"))!=game[s+"_id"]
                    or not str(detail.get('player_id','')).isdigit() or int(detail.get('player_id',0))<=0
                    or detail.get("confirmed") is not True or not str(detail.get("source_url","")).startswith("https://")):
                raise ValueError("Goalie context requires confirmed numeric player/team identity and HTTPS source for each side")
        goalie_context=goalies
    if goalie_context is None:reasons.append("Starting goalies unconfirmed; no goalie-quality adjustment or betting recommendation")
    gate=dict(eligible=not reasons,season=game["season"],required_games=10,season_games_played=counts,
              status="Team baseline eligible — still uncalibrated" if not reasons else "Insufficient verified NHL inputs — Projection only",
              reasons=reasons,policy="Provisional operational policy; not an accuracy guarantee")
    markets=[]
    for spec in specs:
        if (any(spec.get(k) is not None for k in ('price_a','price_b'))
                and spec.get('scope')!='official_final_including_ot_so'):
            raise ValueError('Priced NHL market lacks verified full-game settlement scope')
        probabilities=market_probabilities(d,spec["kind"],spec["line"])
        if probabilities is None:
            item=dict(kind=spec["kind"],line=spec["line"],prob_a=None,prob_b=None,push_prob=None,
                      fair_prob_a=None,fair_prob_b=None,price_a=spec.get("price_a"),price_b=spec.get("price_b"),
                      ev_a=None,ev_b=None,pick=None,stake_size=None,
                      stake_basis="unavailable: no eventual-final distribution",
                      recommendation="INFO — No eventual-final distribution")
        else:item=price_market(spec["kind"],spec["line"],probabilities,spec.get("price_a"),spec.get("price_b"))
        item.update(quote={k:val for k,val in spec.items() if k not in {"price_a","price_b"}},scope="official_final_including_ot_so")
        if d:item["omitted_tail"]=d["omitted_tail"]
        markets.append(item)
    if reasons:
        markets=observation_markets(markets)
        for item in markets:item.update(status=gate["status"],recommendation="INFO — "+gate["status"])
    h,a=result["regulation_home"],result["regulation_away"]
    if d:
        h+=d["regulation"]["draw"]*result["ot_home_probability"]
        a+=d["regulation"]["draw"]*(1-result["ot_home_probability"])
    return dict(sport="nhl",league="NHL",home_team=game["home_team"],away_team=game["away_team"],
                game_id=game["game_id"],game_date=game["date"],fixture=game,readiness=gate,
                projection=dict(home_points=h,away_points=a,**result,final_probability_available=d is not None,validation=v),
                markets=markets,model_version=model.version,observations=obs,features=features,
                goalie_context=goalie_context,created_utc=now.isoformat(),sources=data["sources"],
                settlement=dict(scope="official_final_including_ot_so",rule="Standard full-game two-way markets; regulation three-way not supported"),
                notes=["MoneyPuck.com advanced history; team 5-on-5 benchmark plus published 5-on-4/4-on-5 special-teams rates. Individual goalie quality, injuries and betting splits are not modeled",
                       "Goalie context, if supplied, is user-verified identity only; no numeric goalie-strength effect is invented",
                       "Features use earlier completed games; prior seasons are retained as historical samples",
                       "Historical MoneyPuck model revisions are not archived live feature snapshots",
                       "OT/SO winner model is fitted on regular-season regulation ties; not reused for playoff OT",
                       "Poisson baseline does not explicitly model empty-net strategy; validation dispersion is reported"])


def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--match",action="append");p.add_argument("--date",default=today())
    p.add_argument("--odds",action="store_true");p.add_argument("--dry-run",action="store_true")
    p.add_argument("--goalies-file",type=Path)
    p.add_argument('--observations',action='store_true',help='Read-only forward observation metrics, separate from bets')
    args=p.parse_args()
    try:
        if args.observations:
            from nhl_observations import report
            print(json.dumps(report(),indent=2,ensure_ascii=False));return
        dt.date.fromisoformat(args.date)
        data=json.loads((ROOT/"data/nhl_games.json").read_text(encoding="utf-8"))
        model=joblib.load(ROOT/"data/nhl_model.joblib")
        games=select_games(data["games"],args.date,args.match)
        events=[];note="No odds requested; references have no price/EV"
        if args.odds:
            from score_odds import fetch
            try:events=fetch("NHL");note="Fresh matching paired quotes only"
            except ValueError as exc:note=str(exc)+"; observation run without odds"
        goalie=json.loads(args.goalies_file.read_text()) if args.goalies_file else None
        rows=[]
        for game in games:
            from score_odds import for_fixture
            specs,odds_note=for_fixture(events,game) if events else ([],note)
            specs=specs or [dict(kind="moneyline",line=.5),dict(kind="spread",line=-1.5),dict(kind="total",line=6.5)]
            try:result=forecast(game,data,model,specs,goalies=goalie)
            except ValueError as exc:
                if args.match:raise
                print("SKIPPED:",game["away_team"],"@",game["home_team"],str(exc));continue
            result["notes"].append(odds_note)
            from nhl_review import format_review
            result["formatted_review"]=format_review(result);print(result["formatted_review"],flush=True)
            rows.append(result)
        if not rows:raise ValueError("No NHL fixtures passed data requirements")
        if not args.dry_run:
            from run_ncaaf import store
            from core.historical_storage import capture_prediction_odds
            for row in rows:
                store(row)
                # Immutable record of the prices this forecast was priced with.
                capture=capture_prediction_odds(row)
                if capture["refused"]:print("Odds snapshot refused:",capture["refused"])
            atomic_json(ROOT/"data/nhl_review.json",dict(generated=today(),rows=rows))
            folder=ROOT/"output/nhl";folder.mkdir(parents=True,exist_ok=True)
            for row in rows:atomic_json(folder/(row["game_id"]+".json"),row)
            print(f"Saved {len(rows)} NHL observation/forecast(s). Discord OFF.")
        return rows
    except (ValueError,OSError,KeyError) as exc:p.exit(2,"NHL run failed: "+str(exc)+"\n")


if __name__=="__main__":main()
