"""
check_odds_coverage.py - queries The Odds API directly to find out which
of your target leagues it actually covers, instead of guessing.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("ODDS_API_KEY")

TARGET_LEAGUES = [
    "premier league", "la liga", "bundesliga", "bundesliga 2", "serie a",
    "eredivisie", "eerste divisie", "belgian pro league", "champions league",
    "efl cup", "carabao cup", "estonian", "norway", "npl", "euroleague",
    "mlb", "kbo", "nba", "wta", "atp",
]

resp = requests.get(
    "https://api.the-odds-api.com/v4/sports",
    params={"apiKey": API_KEY, "all": "true"},
    timeout=15,
)
resp.raise_for_status()
sports = resp.json()

print(f"Total sports/leagues available to your key: {len(sports)}\n")
print("=" * 70)
print("MATCHES FOUND FOR YOUR TARGET LEAGUES:")
print("=" * 70)
for target in TARGET_LEAGUES:
    matches = [s for s in sports if target in s["title"].lower() or target in s["key"].lower()]
    if matches:
        for m in matches:
            print(f"  [FOUND] '{target}' -> key='{m['key']}'  title='{m['title']}'  active={m['active']}")
    else:
        print(f"  [NOT FOUND] '{target}'")

print("\n" + "=" * 70)
print("Remaining quota check:")
print(f"  x-requests-remaining header: {resp.headers.get('x-requests-remaining')}")
print(f"  x-requests-used header: {resp.headers.get('x-requests-used')}")
