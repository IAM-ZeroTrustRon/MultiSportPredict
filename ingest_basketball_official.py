"""Public official KBL, NZ NBL and German BBL feeds; no RealGM dependency."""
import argparse
import datetime as dt
import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from sports_feed import ROOT, EASTERN, today, atomic_json

LEAGUES = {"KBL", "NZNBL", "BBL"}


def get(url, headers=None, params=None):
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0", **(headers or {})},
                            params=params, timeout=40)
    response.raise_for_status()
    return response


def html(url):
    return get(url).content.decode("utf-8")


def game_row(identifier, stamp, league, season, home, away, completed, hs, aus, source, **extra):
    return dict(game_id=str(identifier), date=stamp.astimezone(EASTERN).date().isoformat(),
                start_time=stamp.isoformat(), league=league, season=season,
                home_team=home, away_team=away, completed=completed,
                home_score=float(hs) if completed else None,
                away_score=float(aus) if completed else None,
                neutral_site=False, status="STATUS_FINAL" if completed else "STATUS_SCHEDULED",
                source=source, **extra)


def kbl():
    base = "https://api.kbl.or.kr"
    headers = {"Channel": "WEB", "TeamCode": "XX", "Referer": "https://www.kbl.or.kr/"}
    fetch = lambda path, params=None: get(base+path, headers, params).json()
    registry = fetch("/common/teamList")
    names = {str(t["teamCode"]): t["teamNameFullEn"].title() for t in registry}
    for code, name in names.items():
        for acronym in ("Db", "Sk", "Lg", "Kcc", "Kt"):
            name = re.sub(r"\b"+acronym+r"\b", acronym.upper(), name)
        names[code] = name
    seasons = [s for s in fetch("/season/list") if s["seasonCategory"] == "R" and s["seasonGrade"] == 1][:2]
    codes = {s["glkey"]: int(s["seasonName"].split("-")[-1]) for s in seasons}
    raw = fetch("/match/list", dict(fromDate=min(s["gamedateStart"] for s in seasons),
                                   toDate=max(s["gamedateEnd"] for s in seasons), tcodeList="all"))
    games, current = [], []
    for g in raw:
        if g["glkey"] not in codes or str(g["tcodeH"]) not in names or str(g["tcodeA"]) not in names:
            continue
        stamp = dt.datetime.strptime(g["gameDate"]+g["gameStart"], "%Y%m%d%H%M").replace(tzinfo=ZoneInfo("Asia/Seoul"))
        games.append(game_row(g["gmkey"], stamp, "KBL", codes[g["glkey"]],
            names[str(g["tcodeH"])], names[str(g["tcodeA"])], bool(g["isEnded"]),
            g["scoreH"], g["scoreA"], base+"/match/list",
            home_id=str(g["tcodeH"]), away_id=str(g["tcodeA"])))
        if g["glkey"] == seasons[0]["glkey"] and g["isEnded"]:
            current.append(g)
    # Public completed-game box scores supply both teams' measured rates.
    buckets = defaultdict(list)
    def load(g):
        return fetch(f"/match/{g['gmkey']}/team-record")
    with ThreadPoolExecutor(max_workers=4) as pool:
        for box in pool.map(load, current):
            for team in box:
                buckets[str(team["tcode"])].append(team["records"])
    records = {}
    for code, rows in buckets.items():
        records[names[code]] = dict(league="KBL", season=codes[seasons[0]["glkey"]], games=len(rows),
            ortg=sum(r["offrtg"] for r in rows)/len(rows), drtg=sum(r["defrtg"] for r in rows)/len(rows),
            pace=sum(r["pace"] for r in rows)/len(rows), source=base+"/match/{gmkey}/team-record",
            updated=today(), note="Mean official per-game rates; early-season sample, score runner also uses prior season")
    if len(names) != 10 or not games:
        raise ValueError("KBL returned an incomplete team registry/history")
    return records, games


def parse_nz_schedule(text, year):
    soup = BeautifulSoup(text, "html.parser")
    games = []
    for node in soup.select(".match-wrap"):
        stamp_node = node.select_one(".match-time span")
        if not stamp_node:
            continue
        stamp = dt.datetime.strptime(stamp_node.get_text(strip=True), "%d %b %Y, %I:%M %p").replace(tzinfo=ZoneInfo("Pacific/Auckland"))
        if stamp.year != year:
            raise ValueError("NZ NBL returned a different season")
        teams = [node.select_one(f".{side}-team .team-name-full") for side in ("home", "away")]
        if not all(teams):
            continue
        completed = "STATUS_COMPLETE" in node.get("class", [])
        scores = [node.select_one(f".{side}score .fake-cell") for side in ("home", "away")]
        if completed and not all(scores):
            raise ValueError("NZ NBL final score missing")
        games.append(game_row(node["id"].replace("extfix_", ""), stamp, "NZNBL", year,
            teams[0].get_text(strip=True), teams[1].get_text(strip=True), completed,
            scores[0].get_text(strip=True) if completed else None,
            scores[1].get_text(strip=True) if completed else None,
            "https://hosted.wh.geniussports.com/NZNBL/en/"))
    return games


def nznbl():
    base = "https://hosted.wh.geniussports.com/NZNBL/en"
    text = html(base+"/statistics/team")
    soup = BeautifulSoup(text, "html.parser")
    choice = soup.select_one("#competitionChooser option[selected]")
    label = choice.get_text(strip=True)
    if "Rapid" in label or not re.search(r"20\d\d", label):
        raise ValueError("NZ NBL main competition/year could not be verified")
    year = int(re.search(r"20\d\d", label)[0])
    url = choice["value"].replace("https://hosted.dcd.shared.geniussports.com", "https://hosted.wh.geniussports.com")
    tables = soup.select("table")
    records = {}
    for table in tables:
        rows = table.select("tr")
        headers = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])]
        if not {"GP", "FGA", "FTA", "OFF", "TO", "Pts Agt"}.issubset(headers):
            continue
        for row in rows[1:]:
            cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
            if len(cells) != len(headers):
                raise ValueError("NZ NBL totals columns changed")
            r = dict(zip(headers, cells))
            possessions = float(r["FGA"])+.44*float(r["FTA"])-float(r["OFF"])+float(r["TO"])
            records[r["Team"]] = dict(league="NZ NBL", season=year, games=int(r["GP"]),
                ortg=100*float(r["Pts"])/possessions, drtg=100*float(r["Pts Agt"])/possessions,
                pace=possessions/int(r["GP"]), source=url, updated=today(),
                note="Box-score possession estimate; opponent points observed, shared possession denominator; OT not normalized")
    if len(records) < 10:
        raise ValueError("Incomplete NZ NBL totals table")
    games = []
    for phase in ("Regular Season", "Playoffs"):
        schedule = url.replace("/statistics/team", "/schedule")
        games.extend(parse_nz_schedule(get(schedule, params={"phaseName": phase, "poolNumber": -1}).content.decode("utf-8"), year))
    from collections import Counter
    counts = Counter(g[s+"_team"] for g in games if g["completed"] for s in ("home", "away"))
    if any(counts[n] != r["games"] for n,r in records.items()):
        raise ValueError("NZ NBL schedule does not reconcile with official team games played")
    return records, games


def bbl():
    site = "https://www.easycredit-bbl.de/statistiken/teams"
    text = html(site)
    public = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', text)[1])
    props = public["props"]["pageProps"]
    # Guest credentials issued in the public page, exactly as its JS client uses them.
    # Never log or persist the visitor token separately.
    headers = {"x-api-key": "publicWebUser", "x-api-secret": props["key"][::-1].replace(":", "-"), "Referer": site}
    base = "https://api.basketball-bundesliga.de"
    fetch = lambda path, params=None: get(base+path, headers, params).json()
    active = max(s["id"] for s in fetch("/seasons") if s["isActive"])
    stats = fetch(f"/seasons/{active}/team-statistics", {"displayType": "MAIN_ROUND"})
    names = {str(r["seasonTeam"]["teamId"]): r["seasonTeam"]["name"] for r in stats}
    records = {}
    for r in stats:
        possessions = r["fieldGoalsAttempted"]+.44*r["freeThrowsAttempted"]-r["offensiveRebounds"]+r["turnovers"]
        if not possessions or not r["gamesPlayed"]:
            continue
        # plusMinus is total points scored minus observed opponent points.
        conceded = r["points"]-r["plusMinus"]
        records[r["seasonTeam"]["name"]] = dict(league="BBL", season=active+1, games=r["gamesPlayed"],
            ortg=100*r["points"]/possessions, drtg=100*conceded/possessions,
            pace=possessions/(r["secondsPlayed"]/300/40), updated=today(), source=site,
            note="Box-score possession estimate; opponent points from points minus plusMinus; pace normalized to 40 minutes")
    games = []
    for season in (active-1, active):
        page = 1
        while True:
            result = fetch("/games", dict(seasonId=season, currentPage=page, pageSize=500,
                                         gameType="all", competition="BBL"))
            for g in result["items"]:
                if g["competition"] != "BBL" or g["seasonId"] != season or g.get("isTBD"):
                    continue
                completed = g["status"] in {"OFFICIAL", "POST"}
                stamp = dt.datetime.fromisoformat(g["scheduledTime"].replace("Z", "+00:00"))
                h, a = g["homeTeam"], g["guestTeam"]
                score = g.get("result") or {}
                games.append(game_row(g["id"], stamp, "BBL", season+1,
                    names.get(str(h["teamId"]), h["name"]), names.get(str(a["teamId"]), a["name"]),
                    completed, score.get("homeTeamFinalScore"), score.get("guestTeamFinalScore"),
                    base+"/games", home_id=str(h["teamId"]), away_id=str(a["teamId"]), stage=g["stage"]))
            if page >= result["totalPages"]:
                break
            page += 1
            if page > 10:
                raise ValueError("Unexpected BBL pagination")
    if len(records) < 16:
        raise ValueError("Incomplete BBL team statistics")
    return records, games


def ingest(league, check=False):
    league = league.upper()
    records, rows = {"KBL": kbl, "NZNBL": nznbl, "BBL": bbl}[league]()
    games = {g["game_id"]: g for g in rows}
    if sum(g["completed"] for g in games.values()) < 80:
        raise ValueError("Official history incomplete; existing files retained")
    result = dict(updated=today(), league=league, source="Public official league feeds",
                  games=sorted(games.values(), key=lambda g:(g["date"],g["game_id"])))
    if not check:
        store = ROOT/"data/basketball_stats.json"
        previous = json.loads(store.read_text(encoding="utf-8-sig")) if store.exists() else {}
        label = "NZ NBL" if league == "NZNBL" else league
        # Retain all other leagues, replace aliases of this league with canonical names.
        previous = {n:r for n,r in previous.items() if not isinstance(r,dict) or r.get("league") != label}
        atomic_json(store, {**previous, **records})
        atomic_json(ROOT/f"data/basketball_{league.lower()}_games.json", result)
    print(f"{league}: {len(records)} current team records, {len(games)} fixtures, {sum(g['completed'] for g in games.values())} final; official source")
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--leagues", nargs="+", choices=sorted(LEAGUES), default=sorted(LEAGUES))
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    for league in args.leagues:
        ingest(league, args.check)
