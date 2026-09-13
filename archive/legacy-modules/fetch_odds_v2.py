"""Try alternative odds sources for today's ATP Cincinnati matches."""
import json
import urllib.request

MATCHES = [
    {"id": "181897", "home": "Nuno Borges", "away": "Andrey Rublev"},
    {"id": "181885", "home": "Lorenzo Musetti", "away": "Michael Zheng"},
    {"id": "181913", "home": "Daniel Merida", "away": "Taylor Fritz"},
    {"id": "181900", "home": "Daniil Medvedev", "away": "Brandon Nakashima"},
    {"id": "181879", "home": "Adam Walton", "away": "Jaime Faria"},
    {"id": "181919", "home": "Felix Auger-Aliassime", "away": "Juan Manuel Cerundolo"},
]

results = {}

def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))

# 1) Fliff public API - categories
try:
    data = fetch("https://api.fliff.com/api/v1/public/categories")
    cats = data if isinstance(data, list) else data.get("categories", [])
    results["fliff_categories"] = cats[:5]
except Exception as e:
    results["fliff_categories_error"] = str(e)

# 2) Fliff public API - fixture/markets endpoint
try:
    data = fetch("https://api.fliff.com/api/v1/public/in-play")
    results["fliff_inplay"] = data if isinstance(data, list) else list(data)[:5]
except Exception as e:
    results["fliff_inplay_error"] = str(e)

# 3) ESPN scoreboard - check for betting odds in the full event data
try:
    data = fetch("https://site.api.espn.com/apis/site/v2/sports/tennis/atp/scoreboard?dates=20260818")
    event = data.get("events", [{}])[0]
    # Look for odds-related keys in competitions
    comps = []
    for g in event.get("groupings", []):
        for c in g.get("competitions", []):
            comps.append({
                "id": c.get("id"),
                "status": c.get("status", {}).get("type", {}).get("description"),
                "date": c.get("date", ""),
                "has_odds": "odds" in c or "pickcenter" in c,
                "keys": [k for k in c.keys()],
            })
    results["esn_comp_info"] = comps[:5]
except Exception as e:
    results["esn_error"] = str(e)

# 4) ESPN single event using the correct URL pattern (different sport URL structure)
try:
    data = fetch("https://site.api.espn.com/apis/site/v2/sports/tennis/atp/summary?event=181897")
    results["esn_summary"] = list(data.keys())[:20]
except Exception as e:
    results["esn_summary_error"] = str(e)

with open("cincinnati_odds_v2.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False, default=str)

print(json.dumps({k: (v[:200] if isinstance(v, list) else str(v)[:200]) for k, v in results.items()}, indent=2))