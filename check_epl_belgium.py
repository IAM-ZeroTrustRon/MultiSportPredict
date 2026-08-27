import requests, os
from dotenv import load_dotenv
load_dotenv()
r = requests.get("https://api.the-odds-api.com/v4/sports", params={"apiKey": os.getenv("ODDS_API_KEY"), "all": "true"}, timeout=15)
sports = r.json()
for s in sports:
    if "epl" in s["key"].lower() or "england" in s["key"].lower() or s["title"].lower() == "epl":
        print(f"EPL candidate: key={s['key']} title={s['title']} active={s['active']}")
    if "belgium" in s["key"].lower() or "belgian" in s["title"].lower() or "jupiler" in s["title"].lower():
        print(f"Belgium candidate: key={s['key']} title={s['title']} active={s['active']}")
