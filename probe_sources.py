#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
probe_sources.py - Download candidate data sources so they can be inspected.

Your machine can reach sites that this session cannot, and guessing at page
structure from the outside has already produced two wrong parsers. So instead:
this fetches a list of candidate pages, saves each one to data/cache/probe/,
and follows any promising links it finds on them. Nothing is parsed here and
no model data is touched -- it only downloads and reports.

    python probe_sources.py

Then say it has run. The saved HTML gets read directly and the parsers get
built against the real markup instead of an assumption.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "cache" / "probe"
TIMEOUT = 25

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

try:
    import requests
except ImportError:
    sys.exit("requests is required: pip install requests")

# Seed pages. Each entry is (label, url, keywords-to-follow).
# A keyword list means: after saving the page, find links whose text or href
# contains one of these words and fetch those too (bounded, see MAX_FOLLOW).
SEEDS: List[Tuple[str, str, List[str]]] = [
    # --- KBL: RealGM is Cloudflare-blocked, asia-basket answered 200 ---
    ("kbl_landing", "https://basketball.asia-basket.com/South-Korea/basketball-League-KBL.aspx",
     ["team", "stat", "standing"]),

    # --- NZ NBL: nznbl.basketball answered 200 ---
    ("nznbl_landing", "https://nznbl.basketball/", ["stat", "standing", "team"]),

    # --- Tennis: settle what actually exists ---
    ("gh_repo_root", "https://github.com/JeffSackmann/tennis_atp", []),
    ("gh_user_repos", "https://api.github.com/users/JeffSackmann/repos?per_page=100&sort=updated", []),
    ("gh_api_repo", "https://api.github.com/repos/JeffSackmann/tennis_atp", []),
    ("tennisabstract", "https://www.tennisabstract.com/", []),

    # --- Soccer: FBref is Cloudflare-blocked; is a different source reachable? ---
    ("football_data_uk", "https://www.football-data.co.uk/data.php", []),
    ("openfootball", "https://api.github.com/repos/openfootball/football.json", []),

    # --- NFL ---------------------------------------------------------------
    # Pro-Football-Reference is Sports Reference, the same stack as FBref,
    # which already 403s here. Probed to confirm rather than assume.
    ("nfl_pfr", "https://www.pro-football-reference.com/years/2025/", []),

    # ESPN's public JSON APIs need no key and are the most likely to work.
    ("nfl_espn_teams",
     "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams", []),
    ("nfl_espn_scoreboard",
     "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard", []),
    ("nfl_espn_standings",
     "https://site.web.api.espn.com/apis/v2/sports/football/nfl/standings?season=2025", []),
    ("nfl_espn_team_stats",
     "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2025/"
     "types/2/teams/1/statistics", []),
    ("nfl_espn_athletes",
     "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2025/athletes"
     "?limit=5", []),

    # nflverse is the best free play-by-play source, but it ships via GitHub
    # releases -- which is exactly what is 404ing on this machine.
    ("nfl_nflverse_api",
     "https://api.github.com/repos/nflverse/nflverse-data/releases/latest", []),
]

MAX_FOLLOW = 6          # per seed
MAX_TOTAL = 40


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", text)[:80]


def fetch(label: str, url: str) -> Tuple[str, int, str]:
    """Returns (status_text, size, body). Never raises."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
    except Exception as exc:  # noqa: BLE001
        return f"ERR {type(exc).__name__}", 0, ""
    body = response.text
    if response.status_code == 200 and body:
        path = OUT / f"{slug(label)}.html"
        path.write_text(body, encoding="utf-8", errors="replace")
    return str(response.status_code), len(response.content), body


LINK_RE = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                     re.IGNORECASE | re.DOTALL)


def find_links(html: str, base: str, keywords: List[str]) -> List[Tuple[str, str]]:
    seen: Dict[str, str] = {}
    for href, text in LINK_RE.findall(html):
        label = re.sub(r"<[^>]+>", " ", text)
        label = re.sub(r"\s+", " ", label).strip()
        haystack = f"{href} {label}".lower()
        if not any(word in haystack for word in keywords):
            continue
        if href.startswith(("#", "javascript:", "mailto:")):
            continue
        absolute = urljoin(base, href)
        if absolute not in seen:
            seen[absolute] = label or "(no text)"
    return list(seen.items())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("=" * 78)
    print("SOURCE PROBE -- downloading candidate pages")
    print(f"Saving to: {OUT}")
    print("=" * 78)

    fetched = 0
    for label, url, keywords in SEEDS:
        status, size, body = fetch(label, url)
        print(f"\n[{status:>6}] {size:>9,}b  {label}")
        print(f"          {url}")
        fetched += 1

        if status != "200" or not keywords or not body:
            continue

        links = find_links(body, url, keywords)
        if not links:
            print("          (no matching links found on this page)")
            continue

        print(f"          following up to {MAX_FOLLOW} of {len(links)} candidate link(s):")
        for index, (link_url, link_text) in enumerate(links[:MAX_FOLLOW]):
            if fetched >= MAX_TOTAL:
                break
            sub_label = f"{label}__{index}_{slug(link_text)[:40]}"
            sub_status, sub_size, _ = fetch(sub_label, link_url)
            fetched += 1
            print(f"            [{sub_status:>6}] {sub_size:>9,}b  {link_text[:44]}")
            print(f"                     {link_url[:100]}")

    saved = sorted(OUT.glob("*.html"))
    print("\n" + "=" * 78)
    print(f"Saved {len(saved)} page(s) to data/cache/probe/")
    for path in saved:
        print(f"  {path.stat().st_size:>9,}b  {path.name}")
    print("=" * 78)
    print("\nDone. Nothing was parsed and no model data was touched.")


if __name__ == "__main__":
    main()
