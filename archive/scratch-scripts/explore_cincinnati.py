"""Temporary script to explore ATP Cincinnati match data from ESPN."""
import json
import urllib.request
from collections import Counter

data = json.load(urllib.request.urlopen(
    "https://site.api.espn.com/apis/site/v2/sports/tennis/atp/scoreboard"
))
event = data.get("events", [])[0]
matches = []
for g in event.get("groupings", []):
    for c in g.get("competitions", []):
        comps = c.get("competitors", [])
        names = [comp.get("athlete", {}).get("displayName", "?") for comp in comps]
        matches.append({
            "date": c.get("date", "")[:10],
            "status": c.get("status", {}).get("type", {}).get("description", ""),
            "round": c.get("round", {}).get("displayName", ""),
            "match": " vs ".join(names),
            "id": c.get("id", ""),
        })

result = {
    "total_matches": len(matches),
    "by_date": dict(Counter(m["date"] for m in matches)),
    "matches_not_final": [m for m in matches if m["status"] != "Final"],
    "matches_today": [m for m in matches if m["date"] == "2026-08-18"],
}
with open("cincinnati_explore.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
print("Done - wrote cincinnati_explore.json")