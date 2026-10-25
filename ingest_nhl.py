"""Refresh public NHL history and MoneyPuck; preserve the last good store on failure."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import hashlib
import json

from nhl_sources import MP, TEAM_COLUMNS, schedule, team_history, download_csv, money_team_rows, attach_advanced, utcnow
from sports_feed import ROOT, today, atomic_json


def ingest(seasons=None):
    year = int(today()[:4]); start = year if int(today()[5:7]) >= 7 else year-1
    seasons = seasons or [start-2, start-1, start]
    current = schedule(today())
    clubs = {g[s+"_abbrev"] for g in current for s in ("home", "away")}
    if len(clubs) < 30:
        raise ValueError("NHL schedule week does not expose a complete active club registry")
    print(f"NHL: fetching {len(clubs)} club schedules across {len(seasons)} seasons", flush=True)
    def load(task):
        return team_history(*task)
    combined = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        for rows in pool.map(load, [(club, season) for club in sorted(clubs) for season in seasons]):
            for g in rows:
                old = combined.get(g["game_id"])
                if old and any(old[k] != g[k] for k in ["home_id", "away_id", "start_time"]):
                    raise ValueError("Conflicting official fixture identities")
                combined[g["game_id"]] = g
    combined.update({g["game_id"]: g for g in current})
    path = ROOT/"data/nhl_games.json"
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        combined = {**{g["game_id"]: g for g in previous["games"]}, **combined}
    games = sorted(combined.values(), key=lambda g:(g["start_time"],g["game_id"]))
    if sum(g["completed"] for g in games) < 500:
        raise ValueError("Insufficient official completed history; previous store retained")
    print("NHL: downloading/validating published MoneyPuck 5-on-5 game history", flush=True)
    csv_path, meta = download_csv(f"{MP}/careers/gameByGame/all_teams.csv", "all_teams.csv", TEAM_COLUMNS)
    team_rows = money_team_rows(csv_path, min(seasons))
    matched = attach_advanced(games, team_rows)
    if matched < 500:
        raise ValueError("Too few verified advanced-stat joins; previous NHL store retained")
    from ingest.nhl_api_fetcher import NHLAPIFetcher
    warnings = []
    try:
        summary = NHLAPIFetcher().fetch_advanced_metrics(start)
        summary_meta = summary.attrs["source"]
        atomic_json(ROOT/"data/nhl_current_team_metrics.json", {
            "source": summary_meta, "rows": json.loads(summary.to_json(orient="records"))})
    except Exception as exc:
        summary_meta = None; warnings.append("Current team summary unavailable: "+type(exc).__name__)
    try:
        goalie_path, goalie_meta = download_csv(f"{MP}/seasonSummary/{start}/regular/goalies.csv",
                                               f"goalies_{start}.csv", ["playerId", "name", "situation"])
    except Exception as exc:
        goalie_meta = None; warnings.append("Published goalie snapshot unavailable: "+type(exc).__name__)
    # Volatile retrieval timestamps must not force needless retraining.
    identity = [{k:v for k,v in g.items() if k not in {"retrieved_utc", "source"}} for g in games if g["completed"]]
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    payload = dict(updated=today(), retrieved_utc=utcnow(), league="NHL", games=games,
                   official_clubs=sorted(clubs), advanced_matched_games=matched, data_hash=digest,
                   sources={"advanced_history":meta,"team_summary":summary_meta,"goalie_summary":goalie_meta},
                   limitations=["Starting goalies are not confirmed by historical goalie statistics",
                                "MoneyPuck historical xG reflects the downloaded model revision; not archived live feature snapshots",
                                "High-danger shot share is not high-danger save percentage"], warnings=warnings)
    atomic_json(path,payload)
    print(f"NHL: {len(games)} fixtures; {sum(g['completed'] for g in games)} finals; {matched} verified advanced joins",flush=True)
    for warning in warnings: print("NOTE:",warning,flush=True)
    return payload


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seasons",nargs="+",type=int)
    p.add_argument("--no-train",action="store_true")
    args=p.parse_args()
    try:
        ingest(args.seasons)
        if not args.no_train:
            from train_nhl import train
            train()
    except Exception as exc:
        p.exit(1,"NHL refresh failed; previous good data/model retained: "+type(exc).__name__+": "+str(exc)+"\n")
