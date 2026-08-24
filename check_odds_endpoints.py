"""Check various ESPN odds endpoints for today's ATP Cincinnati matches."""
import json
import urllib.request

urls = [
    "https://sports.core.api.espn.com/v2/sports/tennis/leagues/atp/events/181897/competitions/181897/odds",
    "https://sports.core.api.espn.com/v2/sports/tennis/leagues/atp/events/181897/odds",
    "https://site.api.espn.com/apis/site/v2/sports/tennis/atp/scoreboard/181897",
    "https://site.api.espn.com/apis/site/v2/sports/tennis/atp/summary?event=181897",
]

output = []
for url in urls:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = json.load(urllib.request.urlopen(req, timeout=15))
        output.append(f"OK: {url}")
        output.append(f"  Keys: {list(data.keys())[:20]}")
        if isinstance(data, dict) and "items" in data:
            output.append(f"  Items: {json.dumps(data['items'][:3], indent=1, default=str)[:2000]}")
        else:
            output.append(f"  Data: {json.dumps(data, indent=1, default=str)[:1500]}")
        break
    except Exception as e:
        output.append(f"FAIL: {url} -> {e}")

with open("odds_endpoints_result.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output))
print("Written to odds_endpoints_result.txt")
