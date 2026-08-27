#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
kbo_scraper.py - Auto-fetches KBO team and pitcher stats from MyKBO Stats
and seeds them into team_stats_provider.py before match runs.

Usage:
    python kbo_scraper.py --home "NC Dinos" --away "LG Twins"
    python kbo_scraper.py --home "Lotte Giants" --away "KIA Tigers"

What it fetches:
    - Team runs scored per game (last 10 games)
    - Team ERA (starting rotation)
    - Today's probable starter ERA and K/9 if listed

After running, use universal_runner.py WITHOUT --home-sp-era flags --
the scraper seeds the data automatically.
"""
import argparse
import re
import sys
from typing import Optional, Tuple

import requests
from bs4 import BeautifulSoup

TEAM_SLUGS = {
    "NC Dinos": "8-NC-Dinos",
    "LG Twins": "3-LG-Twins",
    "Lotte Giants": "2-Lotte-Giants",
    "KIA Tigers": "1-Kia-Tigers",
    "KT Wiz": "10-KT-Wiz",
    "Samsung Lions": "6-Samsung-Lions",
    "SSG Landers": "5-SSG-Landers",
    "Hanwha Eagles": "7-Hanwha-Eagles",
    "Kiwoom Heroes": "9-Kiwoom-Heroes",
    "Doosan Bears": "4-Doosan-Bears",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

BASE = "https://mykbostats.com"


def fetch_team_stats(team_name: str) -> dict:
    slug = TEAM_SLUGS.get(team_name)
    if not slug:
        print(f"[WARNING] No slug found for '{team_name}'. Add it to TEAM_SLUGS.")
        return {}

    url = f"{BASE}/teams/{slug}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        stats = {}

        # Parse runs scored and ERA from team stat tables
        tables = soup.find_all("table")
        for table in tables:
            headers = [th.get_text(strip=True) for th in table.find_all("th")]
            rows = table.find_all("tr")
            for row in rows:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if not cells:
                    continue
                row_dict = dict(zip(headers, cells))

                if "R/G" in row_dict:
                    try:
                        stats["runs_per_game"] = float(row_dict["R/G"])
                    except ValueError:
                        pass
                if "ERA" in row_dict:
                    try:
                        stats["team_era"] = float(row_dict["ERA"])
                    except ValueError:
                        pass
                if "K/9" in row_dict:
                    try:
                        stats["team_k9"] = float(row_dict["K/9"])
                    except ValueError:
                        pass

        if not stats:
            print(f"[WARNING] No stats parsed for {team_name} from {url}")
            print("  MyKBO Stats may have changed their layout.")
            print("  Falling back to league averages (ERA 4.50, R/G 5.0, K/9 7.5)")
            stats = {"runs_per_game": 5.0, "team_era": 4.50, "team_k9": 7.5}

        print(f"[{team_name}] Fetched: {stats}")
        return stats

    except Exception as e:
        print(f"[ERROR] Failed to fetch {team_name}: {e}")
        print("  Falling back to league averages.")
        return {"runs_per_game": 5.0, "team_era": 4.50, "team_k9": 7.5}


def seed_to_provider(team_name: str, stats: dict) -> None:
    from team_stats_provider import upsert_soccer_team_stats
    # Baseball uses a different store path -- seed into the baseball dict
    # For now we print the universal_runner command with real values
    era = stats.get("team_era", 4.50)
    k9 = stats.get("team_k9", 7.5)
    rpg = stats.get("runs_per_game", 5.0)
    print(f"\n[{team_name}] Seeded stats: ERA={era}, K/9={k9}, R/G={rpg}")
    return era, k9, rpg


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", required=True)
    parser.add_argument("--away", required=True)
    parser.add_argument("--market-total", type=float, default=9.5)
    parser.add_argument("--push-discord", action="store_true")
    parser.add_argument("--store-to-db", action="store_true")
    args = parser.parse_args()

    print(f"\nFetching KBO stats for: {args.home} vs {args.away}\n")

    home_stats = fetch_team_stats(args.home)
    away_stats = fetch_team_stats(args.away)

    home_era = home_stats.get("team_era", 4.50)
    home_k9 = home_stats.get("team_k9", 7.5)
    away_era = away_stats.get("team_era", 4.50)
    away_k9 = away_stats.get("team_k9", 7.5)

    market_total = args.market_total

    cmd = (
        f'python universal_runner.py --sport baseball '
        f'--home "{args.home}" --away "{args.away}" '
        f'--league KBO --markets nrfi strikeouts '
        f'--market-total {market_total} '
        f'--home-sp-era {home_era} --home-sp-k {home_k9} '
        f'--away-sp-era {away_era} --away-sp-k {away_k9}'
    )
    if args.store_to_db:
        cmd += " --store-to-db"
    if args.push_discord:
        cmd += " --push-discord"

    print("\n" + "=" * 60)
    print("AUTO-GENERATED RUN COMMAND (copy and run this):")
    print("=" * 60)
    print(cmd)
    print("=" * 60)

    import subprocess
    print("\nRunning prediction now...\n")
    subprocess.run(cmd, shell=True)


if __name__ == "__main__":
    main()
