#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
diagnose_sources.py - Find out WHY data sources are failing.

Several sites are refusing this machine (RealGM 403, FanGraphs 403, GitHub 404
from four different hosts) while the MLB API works fine. That pattern usually
means something is intercepting Python's traffic rather than five sites all
being down. This script tests each source several different ways and prints a
grid so the cause is obvious.

Run it:      python diagnose_sources.py
Then paste the whole output back.

It only makes GET requests and writes nothing.
"""

from __future__ import annotations

import os
import socket
import ssl
import sys
import urllib.request

TIMEOUT = 15

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

BROWSER_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

TARGETS = [
    ("CONTROL  mlb api",     "https://statsapi.mlb.com/api/v1/teams?sportId=1"),
    ("CONTROL  example.com", "https://example.com"),
    ("tennis   raw.github",  "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2025.csv"),
    ("tennis   jsdelivr",    "https://cdn.jsdelivr.net/gh/JeffSackmann/tennis_atp@master/atp_matches_2025.csv"),
    ("tennis   statically",  "https://cdn.statically.io/gh/JeffSackmann/tennis_atp/master/atp_matches_2025.csv"),
    ("tennis   github.com",  "https://github.com/JeffSackmann/tennis_atp/raw/master/atp_matches_2025.csv"),
    ("github   api",         "https://api.github.com/repos/JeffSackmann/tennis_atp"),
    ("realgm   homepage",    "https://basketball.realgm.com/"),
    ("realgm   kbl stats",   "https://basketball.realgm.com/international/league/63/south-korean-kbl/team-stats/2026/Averages/Team_Totals"),
    ("fangraphs leaders",    "https://www.fangraphs.com/leaders-legacy.aspx"),
    ("fbref    comps",       "https://fbref.com/en/comps/"),
    ("kbl-alt  asia-basket", "https://basketball.asia-basket.com/South-Korea/basketball-League-KBL.aspx"),
    ("nz-alt   nznbl site",  "https://nznbl.basketball/"),
    ("nz-alt   fibalivestats", "https://fibalivestats.dcd.shared.geniussports.com/"),
]


def line(label: str, status: str, note: str = "") -> None:
    print(f"  {label:<26} {status:<14} {note}", flush=True)


# ----------------------------------------------------------------- environment
print("=" * 78)
print("ENVIRONMENT")
print("=" * 78)
print(f"  python           {sys.version.split()[0]}  ({sys.executable})")

try:
    import requests
    print(f"  requests         {requests.__version__}")
except ImportError:
    requests = None                                     # type: ignore
    print("  requests         NOT INSTALLED")

try:
    import certifi
    print(f"  certifi          {certifi.__version__}")
except Exception:
    print("  certifi          not available")

print("\n  Proxy environment variables (a value here is a very strong clue):")
found_proxy = False
for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
             "http_proxy", "https_proxy", "all_proxy", "no_proxy",
             "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE", "CURL_CA_BUNDLE"):
    value = os.environ.get(name)
    if value:
        found_proxy = True
        print(f"    {name} = {value}")
if not found_proxy:
    print("    (none set)")

if requests is not None:
    detected = requests.utils.getproxies()
    print(f"\n  Proxies auto-detected by requests (includes Windows system settings):")
    print(f"    {detected if detected else '(none)'}")

# ------------------------------------------------------------------ DNS check
print("\n" + "=" * 78)
print("DNS RESOLUTION  (an odd IP here means DNS is being redirected)")
print("=" * 78)
for host in ("statsapi.mlb.com", "raw.githubusercontent.com", "cdn.jsdelivr.net",
             "basketball.realgm.com", "www.fangraphs.com", "fbref.com"):
    try:
        addresses = sorted({info[4][0] for info in socket.getaddrinfo(host, 443, socket.AF_INET)})
        line(host, "OK", ", ".join(addresses[:3]))
    except Exception as exc:
        line(host, "FAIL", f"{type(exc).__name__}: {exc}")

# --------------------------------------------------------------- TLS identity
print("\n" + "=" * 78)
print("TLS CERTIFICATE ISSUER  (if this is not a public CA, traffic is being")
print("inspected by security software -- that is almost certainly the cause)")
print("=" * 78)
for host in ("raw.githubusercontent.com", "basketball.realgm.com", "statsapi.mlb.com"):
    try:
        context = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=TIMEOUT) as raw_sock:
            with context.wrap_socket(raw_sock, server_hostname=host) as tls:
                cert = tls.getpeercert()
        issuer = dict(x[0] for x in cert.get("issuer", ()))
        line(host, "OK", f"issuer={issuer.get('organizationName', '?')}")
    except Exception as exc:
        line(host, "FAIL", f"{type(exc).__name__}: {str(exc)[:60]}")

# ------------------------------------------------------------------- fetching
def try_requests(url: str, *, headers, bypass_proxy: bool) -> str:
    if requests is None:
        return "no requests"
    try:
        session = requests.Session()
        if bypass_proxy:
            session.trust_env = False
            session.proxies = {}
        response = session.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
        return f"{response.status_code} ({len(response.content)}b)"
    except Exception as exc:
        return f"{type(exc).__name__}"


def try_urllib(url: str) -> str:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return f"{response.status} ({len(response.read())}b)"
    except urllib.error.HTTPError as exc:
        return f"{exc.code}"
    except Exception as exc:
        return f"{type(exc).__name__}"


print("\n" + "=" * 78)
print("FETCH TEST")
print("  A = requests, browser headers, system proxy honoured")
print("  B = requests, browser headers, proxy BYPASSED (trust_env=False)")
print("  C = requests, User-Agent only")
print("  D = urllib")
print("=" * 78)
print(f"  {'SOURCE':<26} {'A':<16} {'B':<16} {'C':<16} {'D'}")
print("  " + "-" * 74)

for label, url in TARGETS:
    a = try_requests(url, headers=BROWSER_HEADERS, bypass_proxy=False)
    b = try_requests(url, headers=BROWSER_HEADERS, bypass_proxy=True)
    c = try_requests(url, headers={"User-Agent": UA}, bypass_proxy=True)
    d = try_urllib(url)
    print(f"  {label:<26} {a:<16} {b:<16} {c:<16} {d}")

print("\n" + "=" * 78)
print("HOW TO READ THIS")
print("=" * 78)
print("""  * Column B works but A fails  -> a proxy is set; the script must bypass it.
  * All columns fail the same way, but the URL loads in your browser
                                -> security software is filtering Python only.
  * TLS issuer is not a public CA (DigiCert, Let's Encrypt, Sectigo...)
                                -> TLS inspection is rewriting the connection.
  * DNS returns 127.0.0.1 or a private 10./192.168. address for a public site
                                -> DNS is being redirected locally.
  * Everything fails including the CONTROL rows -> plain connectivity problem.

  Also worth doing: open this in your browser and say whether it downloads:
  https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2025.csv
""")
