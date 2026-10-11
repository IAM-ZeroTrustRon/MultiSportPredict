"""Official WTA season results, with explicit singles/result/surface filters."""
from concurrent.futures import ThreadPoolExecutor
from sports_feed import fetch_json, today


def atp_recent_rows(days=14):
    import datetime as dt
    # Explicit current tournament mappings; unknown surfaces are skipped.
    # China Open/Shanghai/Tokyo publish hard in their official ATP overview.
    surfaces = {"china open": ("Beijing", "hard"), "rolex shanghai masters": ("Shanghai", "hard"),
                "shanghai masters": ("Shanghai", "hard"),
                "japan open tennis championships": ("Tokyo", "hard"),
                "kinoshita group japan open tennis championships": ("Tokyo", "hard"),
                "chengdu open": ("Chengdu", "hard"), "hangzhou open": ("Hangzhou", "hard")}
    end = dt.date.fromisoformat(today())
    dates = [(end-dt.timedelta(days=i)).strftime("%Y%m%d") for i in range(days)]
    def read(date):
        return fetch_json(f"https://site.web.api.espn.com/apis/site/v2/sports/tennis/atp/scoreboard?dates={date}", 0.25)
    rows, unknown = {}, set()
    with ThreadPoolExecutor(max_workers=4) as pool:
        for payload in pool.map(read, dates):
            for event in payload.get("events", []):
                groups = [g for g in event.get("groupings", []) if g.get("grouping", {}).get("slug") == "mens-singles"]
                if not groups:
                    continue
                mapping = surfaces.get(event["name"].lower())
                if not mapping:
                    unknown.add(event["name"]); continue
                tournament, surface = mapping
                for group in groups:
                    for match in group.get("competitions", []):
                        if not match.get("status", {}).get("type", {}).get("completed"):
                            continue
                        round_name = match.get("round", {}).get("displayName", "")
                        if "qualifying" in round_name.lower():
                            continue
                        players = match.get("competitors", [])
                        winner = next((p for p in players if p.get("winner") is True), None)
                        loser = next((p for p in players if p.get("winner") is False), None)
                        if not winner or not loser or not winner.get("linescores"):
                            continue
                        stamp = str(match.get("date", ""))[:10]
                        if not stamp or stamp > today():
                            continue
                        rows[str(match["id"])] = {"Winner": winner["athlete"]["displayName"],
                            "Loser": loser["athlete"]["displayName"], "Surface": surface, "Date": stamp,
                            "Tournament": tournament, "Round": round_name, "source": "ESPN recent ATP",
                            "match_id": "espn:"+str(match["id"])}
    return list(rows.values()), unknown


def wta_season_rows(year):
    tournaments = {}
    page = 0
    while True:
        url = f"https://api.wtatennis.com/tennis/tournaments/?page={page}&pageSize=100&from={year}-01-01&to={year}-12-31&excludeLevels=ITF"
        data = fetch_json(url, 12 if year < int(today()[:4]) else 1)
        items = data.get("content", [])
        if not items:
            break
        for item in items:
            level = item.get("level") or item.get("tournamentGroup", {}).get("level")
            if level in {"WTA 250", "WTA 500", "WTA 1000", "Grand Slam", "WTA Finals", "Finals"} and item["startDate"] <= today():
                tournaments[str(item["tournamentGroup"]["id"])] = item
        page += 1
        if page*100 >= data.get("pageInfo", {}).get("numEntries", len(items)):
            break
        if page > 20:
            raise ValueError("Unexpected WTA pagination; refusing incomplete season")
    if len(tournaments) < 10:
        raise ValueError(f"Incomplete WTA calendar: {len(tournaments)} tournaments")
    def read(item):
        surface = str(item.get("surface", "")).lower()
        if surface not in {"hard", "clay", "grass", "carpet"}:
            raise ValueError(f"Unknown official surface for {item['title']}")
        identifier = item["tournamentGroup"]["id"]
        data = fetch_json(f"https://api.wtatennis.com/tennis/tournaments/{identifier}/{year}/matches",
                          24 if item["endDate"] < today() else 0.25)
        rows = []
        for match in data.get("matches", []):
            if match.get("DrawMatchType") != "S" or match.get("DrawLevelType") != "M" or match.get("MatchState") != "F":
                continue
            code = str(match.get("Winner", ""))
            # Official live-score result codes: 2/3 normal A/B winner,
            # 4/5 A/B winner by retirement. Walkovers are excluded.
            if code not in {"2", "3", "4", "5"}:
                continue
            winner = "A" if code in {"2", "4"} else "B"
            loser = "B" if winner == "A" else "A"
            name = lambda side: (str(match.get("PlayerNameFirst"+side, "")) + " " +
                                 str(match.get("PlayerNameLast"+side, ""))).strip()
            stamp = str(match.get("MatchTimeStamp") or "")[:10]
            if not stamp or stamp > today() or not name(winner) or not name(loser):
                continue
            rows.append({"Winner": name(winner), "Loser": name(loser), "Surface": surface,
                         "Date": stamp, "Tournament": item["title"], "Round": match.get("RoundID"),
                         "Comment": match.get("ResultString", ""), "source": "WTA official API",
                         "match_id": f"wta:{year}:{identifier}:{match['MatchID']}"})
        return rows
    result = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for rows in pool.map(read, tournaments.values()):
            result.extend(rows)
    if not result:
        raise ValueError("WTA returned no valid main-draw singles results")
    print(f"  WTA official {year}: {len(tournaments)} tournaments, {len(result)} completed main-draw singles")
    return result
