"""Verified NBA/WNBA/NCAAB season schedules and final scores from ESPN."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from sports_feed import ROOT, fetch_json, parse_game, atomic_json, today
from models.basketball_readiness import season_count_metadata

LEAGUES = {"NBA": "nba", "WNBA": "wnba", "NCAAB": "mens-college-basketball", "NCAAW": "womens-college-basketball"}


def ingest(league, seasons, check=False):
    slug = LEAGUES[league.upper()]
    base = f"https://site.web.api.espn.com/apis/site/v2/sports/basketball/{slug}"
    payload = fetch_json(base + "/teams?limit=500")
    teams = payload["sports"][0]["leagues"][0]["teams"]
    if not teams:
        raise ValueError("No team registry; existing store retained")
    def load(task):
        team, season = task
        result = fetch_json(f"{base}/teams/{team['team']['id']}/schedule?season={season}&seasontype=2")
        output = []
        for event in result.get("events", []):
            row = parse_game(event, league.upper())
            if row and row["season"] == season:
                row["season_type"] = 2
                output.append(row)
        # Add postseason where published; regular-season emptiness is allowed
        # only for a future season, never used as a successful ratings refresh.
        post = fetch_json(f"{base}/teams/{team['team']['id']}/schedule?season={season}&seasontype=3")
        for event in post.get("events", []):
            row = parse_game(event, league.upper())
            if row and row["season"] == season:
                row["season_type"] = 3
                output.append(row)
        return output
    roster_ids = {str(t["team"]["id"]) for t in teams}
    games = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for rows in pool.map(load, [(t, s) for t in teams for s in seasons]):
            games.update({r["game_id"]: r for r in rows
                          if r["home_id"] in roster_ids and r["away_id"] in roster_ids})
    if sum(r["completed"] for r in games.values()) < 80:
        raise ValueError("Insufficient final scores; existing store retained")
    result = {"updated": today(), "league": league.upper(), "source": "ESPN team schedules",
              "seasons": seasons, "games": sorted(games.values(), key=lambda r:(r["date"],r["game_id"]))}
    result["season_games_played"] = season_count_metadata(result["games"], league.upper(), today(),
        [t["team"]["displayName"] for t in teams])
    print(f"{league}: {len(teams)} teams, {len(games)} fixtures, {sum(r['completed'] for r in games.values())} final")
    if not check:
        atomic_json(ROOT / f"data/basketball_{league.lower()}_games.json", result)
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--leagues", nargs="+", choices=LEAGUES, default=["NBA", "WNBA"])
    ap.add_argument("--seasons", nargs="+", type=int, default=[int(today()[:4]), int(today()[:4])+1])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    for league in args.leagues:
        ingest(league, args.seasons, args.check)
