"""Build FBS-only multi-season history and verified upcoming fixtures."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
from sports_feed import fetch_json, atomic_json, parse_game, today, ROOT

BASE = "https://site.web.api.espn.com/apis/site/v2/sports/football/college-football"
PATH = ROOT / "data/ncaaf_model.json"


def registry(season):
    url = f"https://site.web.api.espn.com/apis/v2/sports/football/college-football/standings?season={season}&group=80"
    payload = fetch_json(url)
    result = {}
    def visit(node):
        for entry in node.get("standings", {}).get("entries", []):
            team = entry["team"]
            result[str(team["id"])] = {"name": team["displayName"], "conference": node.get("name")}
        for child in node.get("children", []):
            visit(child)
    visit(payload)
    if len(result) < 100:
        raise ValueError(f"Incomplete FBS registry for {season}: {len(result)} teams")
    return result


def ingest(seasons, check=False):
    games, teams, urls = {}, {}, []
    for season in seasons:
        roster = registry(season)
        teams.update(roster)
        first = fetch_json(f"{BASE}/scoreboard?dates={season}&seasontype=2&week=1&groups=80&limit=400")
        for block in first["leagues"][0]["calendar"]:
            for week in block.get("entries", []):
                urls.append((season, roster, f"{BASE}/scoreboard?dates={season}&seasontype={block['value']}&week={week['value']}&groups=80&limit=400"))
    def load(task):
        season, roster, url = task
        payload = fetch_json(url)
        if int(payload.get("season", {}).get("year", season)) != season:
            raise ValueError(f"Wrong season returned for {url}")
        rows = []
        for event in payload.get("events", []):
            row = parse_game(event, "NCAAF")
            if row and row["home_id"] in roster and row["away_id"] in roster:
                rows.append(row)
        return rows
    # Any requested week failure aborts writes; a partial season must not
    # silently replace the complete ratings history.
    with ThreadPoolExecutor(max_workers=4) as pool:
        for rows in pool.map(load, urls):
            games.update({r["game_id"]: r for r in rows})
    if not games:
        raise ValueError("No FBS-vs-FBS games; existing store is unchanged")
    result = {"updated": today(), "source": "ESPN", "seasons": seasons, "teams": teams,
              "games": sorted(games.values(), key=lambda r: (r["date"], r["game_id"]))}
    print(f"NCAAF: {len(teams)} FBS teams; {len(games)} fixtures; "
          f"{sum(r['completed'] for r in games.values())} final; FCS opponents excluded")
    if not check:
        atomic_json(PATH, result)
        old_path = ROOT / "data/ncaaf_schedule.json"
        old = json.loads(old_path.read_text(encoding="utf-8-sig")) if old_path.exists() else {}
        merged = {r["game_id"]: r for r in old.get("games", [])}
        merged.update(games)
        atomic_json(old_path, {"_generated": today(), "_source": "ESPN FBS", "games": list(merged.values())})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seasons", nargs="+", type=int, default=[int(today()[:4])-1, int(today()[:4])])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    ingest(args.seasons, args.check)
