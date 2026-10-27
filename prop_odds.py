"""Player-prop and team-market prices from the-odds-api, with explicit caching.

The player does not assemble prices by hand and no price is invented. Every price
here carries the bookmaker that published it and the bookmaker's own update time.
When a market cannot be read the caller gets a reason, never a blank that could be
mistaken for "no edge".

Credit discipline
-----------------
* Listing events costs 0 credits.
* An event-odds request costs one credit per market per region. Markets are
  therefore requested together in one call, and results are cached on disk so a
  repeated preview does not spend again.

Nothing in this module sends a message, writes a prediction or places anything.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import unicodedata
from pathlib import Path

import requests

BASE = "https://api.the-odds-api.com/v4"
CACHE = Path(__file__).resolve().parent / "data/prop_odds"
SPORTS = {
    "NBA": "basketball_nba",
    "NBL": "basketball_nbl",
    "EUROLEAGUE": "basketball_euroleague",
    "NFL": "americanfootball_nfl",
    "NHL": "icehockey_nhl",
}
PROP_MARKETS = {
    "points": "player_points",
    "rebounds": "player_rebounds",
    "assists": "player_assists",
    "pra": "player_points_rebounds_assists",
    "pa": "player_points_assists",
    "ra": "player_rebounds_assists",
}
TEAM_MARKETS = "h2h,spreads,totals"
EVENTS_TTL_SECONDS = 600
ODDS_TTL_SECONDS = 600
REQUEST_TIMEOUT = 30
MAX_ATTEMPTS = 2


def _key():
    """Read the provider key without ever printing or returning it in output."""
    key = os.environ.get("ODDS_API_KEY", "").strip()
    if not key:
        env = Path(__file__).resolve().parent / ".env"
        try:
            for raw in env.read_text(encoding="utf-8-sig").splitlines():
                if raw.strip().startswith("ODDS_API_KEY"):
                    key = raw.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        except OSError:
            key = ""
    if not key:
        raise RuntimeError("ODDS_API_KEY is not configured; no price can be requested")
    return key


def _cache_path(name):
    CACHE.mkdir(parents=True, exist_ok=True)
    return CACHE / name


def _read_cache(path, ttl):
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    fetched = payload.get("fetched_epoch")
    if not isinstance(fetched, (int, float)) or time.time() - fetched > ttl:
        return None
    return payload


def _write_cache(path, body, headers, url):
    record = {
        "fetched_epoch": time.time(),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "url": url,
        "credit_cost": _header_number(headers, "x-requests-last"),
        "credits_remaining": _header_number(headers, "x-requests-remaining"),
        "payload": body,
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(record), encoding="utf-8")
    temporary.replace(path)
    return record


def _header_number(headers, name):
    raw = (headers or {}).get(name)
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _get(url, params, attempts=MAX_ATTEMPTS):
    """Bounded retry on transport/5xx only. A 4xx is a real answer, not a retry."""
    last = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            last = f"{type(exc).__name__}: {exc}"
            if attempt < attempts:
                time.sleep(1.0)
                continue
            raise RuntimeError(f"odds request failed after {attempts} attempts: {last}") from exc
        if response.status_code >= 500 and attempt < attempts:
            last = f"HTTP {response.status_code}"
            time.sleep(1.0)
            continue
        return response
    raise RuntimeError(f"odds request failed: {last}")


def list_events(sport_key, use_cache=True):
    """Upcoming events for a sport. This endpoint costs 0 credits."""
    key = _key()
    path = _cache_path(f"events_{sport_key}.json")
    if use_cache:
        cached = _read_cache(path, EVENTS_TTL_SECONDS)
        if cached:
            return cached["payload"], {"cached": True, "credit_cost": 0,
                                       "remaining": cached.get("credits_remaining"),
                                       "fetched_at": cached.get("fetched_at")}
    url = f"{BASE}/sports/{sport_key}/events"
    response = _get(url, {"apiKey": key, "dateFormat": "iso"})
    if response.status_code != 200:
        raise RuntimeError(f"event list refused (HTTP {response.status_code}): "
                           f"{response.text[:180]}")
    body = response.json()
    record = _write_cache(path, body, response.headers, url)
    return body, {"cached": False, "credit_cost": record["credit_cost"],
                  "remaining": record["credits_remaining"], "fetched_at": record["fetched_at"]}


# Club-type noise and known provider spellings. Applied token by token so the
# identity key stays exact: "FC Barcelona Bàsquet" and "FC Barcelona" collapse to
# the same key, while two different clubs never do.
_CLUB_NOISE = {"fc", "bc", "cb", "kk", "bk", "basquet", "basket", "basketball"}
_TOKEN_ALIASES = {"munchen": "munich", "zvezda": "crvenazvezda"}


def _fold(name):
    """Accent-, punctuation- and club-suffix-insensitive identity key."""
    text = unicodedata.normalize("NFKD", str(name or "")).casefold()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    tokens = [t for t in re.split(r"[^a-z0-9]+", text) if t]
    kept = [_TOKEN_ALIASES.get(t, t) for t in tokens if t not in _CLUB_NOISE]
    return "".join(kept)


def match_event(events, away, home):
    """Exact, case-folded match on both teams. Never fuzzy-matches a fixture."""
    wanted = {_fold(away), _fold(home)}
    hits = [e for e in events or []
            if {_fold(e.get("away_team")), _fold(e.get("home_team"))} == wanted]
    if len(hits) > 1:
        raise ValueError(f"More than one priced event matches {away} @ {home}")
    if not hits:
        return None
    event = hits[0]
    if _fold(event.get("home_team")) != _fold(home) or _fold(event.get("away_team")) != _fold(away):
        raise ValueError(f"Priced event orientation does not match {away} @ {home}")
    return event


def event_odds(sport_key, event_id, markets, regions="us", use_cache=True):
    """Event markets in one request. Returns ``(payload, meta)`` or ``(None, reason)``.

    ``meta['credit_cost']`` is the provider's own accounting for the call, so the
    spend is reported rather than estimated.
    """
    key = _key()
    market_list = [m.strip() for m in str(markets).split(",") if m.strip()]
    if not market_list:
        raise ValueError("At least one market is required")
    signature = hashlib.sha256(
        f"{sport_key}|{event_id}|{','.join(sorted(market_list))}|{regions}".encode()
    ).hexdigest()[:16]
    path = _cache_path(f"{sport_key}_{event_id}_{signature}.json")
    if use_cache:
        cached = _read_cache(path, ODDS_TTL_SECONDS)
        if cached:
            return cached["payload"], {"cached": True, "credit_cost": 0,
                                       "remaining": cached.get("credits_remaining"),
                                       "fetched_at": cached.get("fetched_at"),
                                       "markets_requested": market_list}
    url = f"{BASE}/sports/{sport_key}/events/{event_id}/odds"
    response = _get(url, {"apiKey": key, "regions": regions,
                          "markets": ",".join(market_list),
                          "oddsFormat": "american", "dateFormat": "iso"})
    if response.status_code != 200:
        return None, {"status": "refused", "reason": (
            f"market request refused (HTTP {response.status_code}): {response.text[:180]}"),
            "credit_cost": _header_number(response.headers, "x-requests-last"),
            "remaining": _header_number(response.headers, "x-requests-remaining"),
            "markets_requested": market_list}
    body = response.json()
    record = _write_cache(path, body, response.headers, url)
    meta = {"cached": False, "credit_cost": record["credit_cost"],
            "remaining": record["credits_remaining"], "fetched_at": record["fetched_at"],
            "markets_requested": market_list}
    present = {m.get("key") for b in body.get("bookmakers") or []
               for m in b.get("markets") or []}
    missing = [m for m in market_list if m not in present]
    if missing:
        meta["markets_unavailable"] = missing
    return body, meta


def player_lines(payload, player_name, market_key):
    """Every offered line for one player and market, from every book."""
    target = _fold(player_name)
    rows = []
    for book in (payload or {}).get("bookmakers") or []:
        for market in book.get("markets") or []:
            if market.get("key") != market_key:
                continue
            by_line = {}
            for outcome in market.get("outcomes") or []:
                if _fold(outcome.get("description")) != target:
                    continue
                point = outcome.get("point")
                price = outcome.get("price")
                if point is None or price is None:
                    continue
                side = str(outcome.get("name") or "").casefold()
                if side not in ("over", "under"):
                    continue
                by_line.setdefault(float(point), {})[side] = float(price)
            for line, prices in by_line.items():
                if "over" not in prices and "under" not in prices:
                    continue
                rows.append({
                    "bookmaker": book.get("key"),
                    "bookmaker_title": book.get("title"),
                    "line": line,
                    "over_price": prices.get("over"),
                    "under_price": prices.get("under"),
                    "updated_at": market.get("last_update") or book.get("last_update"),
                })
    return rows


def consensus_line(rows):
    """Modal line across books, tie-broken toward the books that price both sides.

    Books publish different lines; picking the modal line avoids quoting a price
    from one book against a line another book set.
    """
    if not rows:
        return None
    tally = {}
    for row in rows:
        weight = 1 + (1 if row.get("over_price") is not None and row.get("under_price") is not None else 0)
        tally[row["line"]] = tally.get(row["line"], 0) + weight
    return max(sorted(tally), key=lambda line: tally[line])


def best_prices(rows, line):
    """Best available price per side at exactly one line, with its book."""
    at_line = [r for r in rows if abs(r["line"] - line) < 1e-9]
    best = {}
    for side in ("over", "under"):
        priced = [r for r in at_line if r.get(f"{side}_price") is not None]
        if not priced:
            continue
        pick = max(priced, key=lambda r: r[f"{side}_price"])
        best[side] = {"price": pick[f"{side}_price"], "bookmaker": pick.get("bookmaker"),
                      "updated_at": pick.get("updated_at")}
    return best


def de_vig(over_price, under_price):
    """Two-way no-vig probability from one book, as a benchmark only.

    Returns ``(over_fair, under_fair)`` or ``None``. This is the market's own
    opinion; it is never substituted for the model probability.
    """
    def implied(price):
        price = float(price)
        if price <= -100:
            return 100.0 / (100.0 + abs(price)) if price != -100 else 0.5
        if price >= 100:
            return 100.0 / (100.0 + price)
        raise ValueError("American price must be <= -100 or >= +100")

    over, under = implied(over_price), implied(under_price)
    total = over + under
    if total <= 0:
        return None
    return over / total, under / total


def _modal(values):
    tally = {}
    for value in values:
        tally[value] = tally.get(value, 0) + 1
    return max(sorted(tally), key=lambda value: tally[value]) if tally else None


def team_price_flags(payload, away, home):
    """Translate h2h/spreads/totals into the EuroLeague engine's CLI price flags.

    Only flags that have a real price are returned; anything unread is left out so
    the engine reports it as unavailable instead of being handed a made-up zero.
    """
    flags = []
    want = {_fold(away): "away", _fold(home): "home"}
    h2h = {"home": [], "away": []}
    spread_rows = []
    total_rows = []
    for book in (payload or {}).get("bookmakers") or []:
        for market in book.get("markets") or []:
            key = market.get("key")
            outcomes = market.get("outcomes") or []
            if key == "h2h":
                for outcome in outcomes:
                    side = want.get(_fold(outcome.get("name")))
                    if side and outcome.get("price") is not None:
                        h2h[side].append(float(outcome["price"]))
            elif key == "spreads":
                by_side = {}
                for outcome in outcomes:
                    side = want.get(_fold(outcome.get("name")))
                    if side and outcome.get("point") is not None and outcome.get("price") is not None:
                        by_side[side] = (float(outcome["point"]), float(outcome["price"]))
                if set(by_side) == {"home", "away"}:
                    spread_rows.append(by_side)
            elif key == "totals":
                row = {}
                points = []
                for outcome in outcomes:
                    side = str(outcome.get("name") or "").casefold()
                    if side in ("over", "under") and outcome.get("point") is not None \
                            and outcome.get("price") is not None:
                        row[side] = float(outcome["price"])
                        points.append(float(outcome["point"]))
                if set(row) == {"over", "under"} and len(set(points)) == 1:
                    total_rows.append((points[0], row["over"], row["under"]))

    if h2h["home"] and h2h["away"]:
        flags += ["--home-ml", str(max(h2h["home"])), "--away-ml", str(max(h2h["away"]))]
    if spread_rows:
        line = _modal([row["home"][0] for row in spread_rows])
        at_line = [row for row in spread_rows if row["home"][0] == line]
        home_price = max(row["home"][1] for row in at_line)
        away_price = max(row["away"][1] for row in at_line)
        flags += ["--market-spread", str(line), "--spread-home-price", str(home_price),
                  "--spread-away-price", str(away_price)]
    if total_rows:
        line = _modal([row[0] for row in total_rows])
        at_line = [row for row in total_rows if row[0] == line]
        flags += ["--market-total", str(line),
                  "--over-price", str(max(row[1] for row in at_line)),
                  "--under-price", str(max(row[2] for row in at_line))]
    return flags


def quota_note(metas):
    """Compact, honest spend summary for saved output and the terminal."""
    spent = sum(m.get("credit_cost") or 0 for m in metas)
    remaining = next((m.get("remaining") for m in reversed(metas)
                      if m.get("remaining") is not None), None)
    cached = sum(1 for m in metas if m.get("cached"))
    return {"credits_spent": spent, "credits_remaining": remaining,
            "requests": len(metas), "cache_hits": cached}
