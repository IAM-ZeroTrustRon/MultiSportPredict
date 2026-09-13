"""Fetch today's ATP Cincinnati matches and try to get odds from multiple sources."""
import json
import urllib.request

# Today's scheduled ATP Cincinnati R3 matches from ESPN scoreboard
MATCHES = [
    {"id": "181897", "home": "Nuno Borges", "away": "Andrey Rublev"},
    {"id": "181885", "home": "Lorenzo Musetti", "away": "Michael Zheng"},
    {"id": "181913", "home": "Daniel Merida", "away": "Taylor Fritz"},
    {"id": "181900", "home": "Daniil Medvedev", "away": "Brandon Nakashima"},
    {"id": "181879", "home": "Adam Walton", "away": "Jaime Faria"},
    {"id": "181919", "home": "Felix Auger-Aliassime", "away": "Juan Manuel Cerundolo"},
]

results = []

for m in MATCHES:
    match_info = {"id": m["id"], "home": m["home"], "away": m["away"]}
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/tennis/atp/summary?event={m['id']}"
        data = json.load(urllib.request.urlopen(url, timeout=10))
        # Check for odds/pickcenter data
        odds = data.get("odds", [])
        pickcenter = data.get("pickcenter", {})
        match_info["odds_count"] = len(odds) if odds else 0
        if odds:
            match_info["odds_sample"] = odds[0]
        match_info["pickcenter"] = pickcenter if pickcenter else None
        # Get header/competition info
        header = data.get("header", {})
        match_info["header_status"] = header.get("competitions", [{}])[0].get("status", {}).get("type", {}).get("description", "") if header.get("competitions") else ""
        # Try betting odds
        try:
            bet_url = f"https://sports.core.api.espn.com/v2/sports/tennis/leagues/atp/events/{m['id']}/competitions/{m['id']}/odds"
            bet_data = json.load(urllib.request.urlopen(bet_url, timeout=15))
            items = bet_data.get("items", [])
            match_info["esn_bet_odds"] = items[:3] if items else []
        except Exception as e:
            match_info["esn_bet_error"] = str(e)
    except Exception as e:
        match_info["error"] = str(e)
    results.append(match_info)

with open("cincinnati_odds.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False, default=str)

for r in results:
    print(f"{r['home']} vs {r['away']}: odds_count={r.get('odds_count', 'N/A')}, pickcenter={'Y' if r.get('pickcenter') else 'N'}, esn_odds={'Y' if r.get('esn_bet_odds') else 'N'} ({r.get('esn_bet_error', 'none')})")