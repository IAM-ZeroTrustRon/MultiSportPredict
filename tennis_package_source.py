"""Public TennisExplorer Challenger fallback; paired quotes and completed singles only."""
import datetime as dt
import hashlib
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from sports_feed import ROOT, today

BASE = "https://www.tennisexplorer.com"
PROFILES = {"Thiago Seyboth Wild": "/player/seyboth-wild/",
            "Felipe Meligeni Alves": "/player/meligeni-rodrigues-alves/"}


def page(path, refresh=False):
    url = urljoin(BASE, path)
    if not url.startswith(BASE + "/"):
        raise ValueError("Source must be TennisExplorer")
    cache = ROOT / "data/cache/tennis_full" / (hashlib.sha256(url.encode()).hexdigest() + ".html")
    if not refresh and cache.exists() and dt.datetime.now().timestamp()-cache.stat().st_mtime < 900:
        html = cache.read_text(encoding="utf-8")
    else:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        response.raise_for_status()
        html = response.text
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(html, encoding="utf-8")
    return BeautifulSoup(html, "html.parser")


def decimal_american(value):
    value = float(value)
    if not 1 < value < 1000:
        raise ValueError("Invalid decimal price")
    return round(100*(value-1) if value >= 2 else -100/(value-1), 2)


def price(cell):
    node = cell.select_one(".odds-in") if cell else None
    if node is None:
        return None
    # Nested history tables contain OLD prices; use the direct current text only.
    raw = "".join(str(x) for x in node.find_all(string=True, recursive=False)).strip()
    try:
        return decimal_american(raw)
    except (ValueError, TypeError):
        return None


def timestamp(cell):
    row = cell.select_one(".odds-change-div tr") if cell else None
    return row.get_text(" ", strip=True).split()[:2] if row else []


def parse_odds(soup, swapped=False):
    quotes, moneylines = [], []
    for menu in (1, 2, 3):
        table = soup.select_one(f"#oddsMenu-{menu}-data > table")
        if table is None:
            continue
        kind = None
        for row in table.select(":scope > tbody > tr"):
            if "odds-type" in (row.get("class") or []):
                heading = row.get_text(" ", strip=True).lower()
                units = "sets" if re.search(r"\bsets?\b", heading) else "games" if "games" in heading else None
                kind = f"{units}_{'total' if menu == 2 else 'spread'}" if units else None
                continue
            a, b = row.select_one("td.k1"), row.select_one("td.k2")
            pa, pb = price(a), price(b)
            book = row.select_one("td.first .t")
            if pa is None or pb is None or book is None:
                continue
            metadata = dict(bookmaker=book.get_text(strip=True), source=BASE,
                line_origin="live public odds comparison feed",
                last_update=" / ".join(" ".join(timestamp(c)) for c in (a,b)) + " (source display timezone unspecified)")
            if menu == 1:
                moneylines.append(dict(home_ml=pb if swapped else pa, away_ml=pa if swapped else pb, **metadata))
            elif kind:
                try:
                    line = float(row.select_one("td.value").get_text(strip=True))
                except (AttributeError, ValueError):
                    continue
                # The simulator supports whole/half lines, not Asian quarter settlement.
                if abs(line*2-round(line*2)) > 1e-8:
                    continue
                spread = kind.endswith("spread")
                quotes.append(dict(kind=kind, line=-line if swapped and spread else line,
                    price_a=pb if swapped and spread else pa, price_b=pa if swapped and spread else pb, **metadata))
    return moneylines, quotes


def parse_history(soup, year, cutoff):
    rows = []
    for table in soup.select("table.result.balance"):
        # The singles table has individual profile links and full set scores.
        tournament = None
        for row in table.select(":scope > tbody > tr"):
            if "head" in (row.get("class") or []):
                node = row.select_one("td.t-name a")
                tournament = node.get_text(" ", strip=True) if node else None
                continue
            date, names = row.select_one("td.time"), row.select_one("td.t-name")
            surface = row.select_one("td.s-color span[title]")
            if not tournament or date is None or names is None or surface is None:
                continue
            links = names.select('a[href^="/player/"]')
            result = row.select_one('a[href^="/match-detail/"]')
            if len(links) != 2 or result is None:
                continue
            try:
                stamp = dt.datetime.strptime(date.get_text(strip=True)+str(year), "%d.%m.%Y").date().isoformat()
            except ValueError:
                continue
            score = result.get_text(" ", strip=True)
            # Retirements/walkovers distort games and workload; exclude from this supplement.
            pairs = re.findall(r"(\d+)-(\d+)(?:\(\d+\))?", score)
            if stamp >= cutoff or not pairs or any(x in score.lower() for x in ("ret", "w/o", "walk", "ab")):
                continue
            wins = sum(int(a)>int(b) for a,b in pairs)
            losses = sum(int(b)>int(a) for a,b in pairs)
            if max(wins, losses) < 2 or wins == losses:
                continue
            winner = 0 if wins > losses else 1
            surface_name = surface["title"].lower()
            if surface_name not in {"clay", "hard", "grass", "carpet"}:
                continue
            rows.append(dict(winner_path=links[winner]["href"].rstrip("/")+"/",
                loser_path=links[1-winner]["href"].rstrip("/")+"/",
                winner_display=links[winner].get("title") or links[winner].get_text(strip=True),
                loser_display=links[1-winner].get("title") or links[1-winner].get_text(strip=True),
                surface=surface_name,
                tournament_date=stamp, tournament=tournament, round=row.select_one("td.round").get_text(strip=True),
                match_id=result["href"], score=score, games=sum(int(a)+int(b) for a,b in pairs)))
    return rows


def prepare_fixture(names, source_url=None, refresh=False):
    from run_tennis import squash
    profiles = {}
    supplied = page(source_url, refresh) if source_url else None
    for name in names:
        path = PROFILES.get(name) or "/player/" + "-".join(name.lower().split()[1:]) + "/"
        if supplied:
            candidates = [a for a in supplied.select('table.gDetail a[href^="/player/"]')
                          if all(squash(word) in squash(a.get_text()) for word in name.split())]
            if len(candidates) == 1:
                path = candidates[0]["href"].rstrip("/")+"/"
        soup = page(path + "?annual=" + today()[:4], refresh)
        heading = soup.select_one("table.plDetail h3")
        if heading is None or not all(squash(word) in squash(heading.text) for word in name.split()):
            raise ValueError(f"Cannot identify profile for {name}; provide --source-url for the exact match")
        profiles[name] = (path, soup)
    ids = [{a["href"] for a in soup.select('table.gamedetail a[href^="/match-detail/"]')}
           for _, soup in profiles.values()]
    shared = ids[0] & ids[1]
    if source_url:
        if source_url.removeprefix(BASE) not in shared:
            raise ValueError("Supplied match URL is not an upcoming shared fixture on both player profiles")
    else:
        if len(shared) != 1:
            raise ValueError("No unique upcoming match for this pair. Needed: --source-url with the TennisExplorer match link")
        source_url = BASE + next(iter(shared))
    soup = supplied or page(source_url, refresh)
    links = soup.select("table.gDetail td.name a") or soup.select('table.gDetail a[href^="/player/"]')
    paths = [a["href"].rstrip("/")+"/" for a in links]
    requested = [profiles[n][0] for n in names]
    if paths not in (requested, list(reversed(requested))):
        raise ValueError("Source match names do not match requested players")
    header = soup.select_one("h1").find_next_sibling().get_text(" ", strip=True)
    surface = next((x for x in ("clay", "hard", "grass", "carpet") if re.search(r"\b"+x+r"\b", header.lower())), None)
    if not surface:
        raise ValueError("Needed: verified match surface; source has none")
    # Explicit date from current player schedule, not a guessed UTC conversion.
    schedule_link = next((a for a in profiles[names[0]][1].select('table.gamedetail a[href^="/match-detail/"]')
                          if a["href"] == source_url.removeprefix(BASE)), None)
    schedule_row = schedule_link.find_parent("tr") if schedule_link else None
    schedule = schedule_row.select_one("td.time") if schedule_row else None
    if schedule is None:
        raise ValueError("Source no longer lists an upcoming match; refusing pre-match run")
    stamp = schedule.get_text(strip=True).split()[0]
    game_date = dt.datetime.strptime(stamp + today()[:4], "%d.%m.%Y").date().isoformat()
    if game_date < today():
        raise ValueError("Source fixture is in the past")
    moneylines, quotes = parse_odds(soup, paths != requested)
    tournament_node = soup.select_one("h1").find_next_sibling().select_one('a[href*="/atp-men/"]')
    tournament = tournament_node.get_text(strip=True) if tournament_node else header
    round_node = schedule_row.select_one("td:nth-of-type(2)")
    round_name = round_node.get_text(strip=True) if round_node else "Unknown"
    return dict(source_url=source_url, profiles=profiles, soup=soup, surface=surface,
                game_date=game_date, tournament=tournament, moneylines=moneylines, markets=quotes,
                round_name=round_name,
                schedule_note="Date matched on source; exact UTC start not verified. Check book before betting.")
