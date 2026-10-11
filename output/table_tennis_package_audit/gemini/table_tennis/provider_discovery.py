"""
Czech Liga Pro Provider Discovery & Scope Enforcement
Section 1 and Section 7 of Czech Liga Pro Handoff Specification.

STRICT BOUNDARIES:
- Implement Czech Liga Pro ONLY.
- Strictly REJECT Russian Liga Pro, Setka Cup, Czech TT Cup, TT Elite, WTT, and any deceptive aliases.
- Track candidate status and unverified fields across providers.
"""

import re
from typing import Dict, Any, List, Optional

# Strictly prohibited leagues and aliases
PROHIBITED_LEAGUES = [
    "russian liga pro",
    "russia liga pro",
    "liga pro (ru)",
    "setka cup",
    "setka",
    "czech tt cup",
    "tt cup",
    "tt elite",
    "wtt",
    "world table tennis",
    "challenger series"
]

# Verified Czech Liga Pro naming patterns
CZECH_LIGA_PRO_PATTERNS = [
    r"^czech\s*liga\s*pro$",
    r"^liga\s*pro\s*\(cz\)$",
    r"^czech\s*republic\s*[-–]\s*czech\s*liga\s*pro$",
    r"^table\s*tennis\s*[-–]\s*czech\s*liga\s*pro$",
    r"^czechia\s*[-–]\s*liga\s*pro$"
]

CANDIDATE_PROVIDERS = {
    "odds_api_io": {
        "name": "Odds-API.io / OddsHub",
        "role": "First odds-stream trial candidate; compare books and archive quotes.",
        "transport": "REST snapshots + WebSocket",
        "verified": True,
        "unverified": "Account-level Czech coverage today, live markets, update delay, point scores/server, historical depth."
    },
    "betsapi": {
        "name": "BetsAPI",
        "candidate_league_id": 22742,
        "role": "Trial for fixtures, completed game scores, and H2H history.",
        "transport": "Authenticated REST",
        "verified": False,
        "unverified": "League ID 22742 requires account-level validation; point-by-point fields, books, historical depth."
    },
    "stake": {
        "name": "Stake Czech Liga Pro",
        "role": "Named-site comparison/discovery candidate for market semantics.",
        "transport": "Playwright response/WebSocket observation",
        "verified": False,
        "unverified": "Live synchronization, score-to-quote alignment, automation terms."
    },
    "parlay_api": {
        "name": "ParlayAPI",
        "role": "Secondary odds candidate to trial.",
        "transport": "REST odds endpoint",
        "verified": False,
        "unverified": "Current event coverage, score granularity, latency, bookmaker independence."
    },
    "tabletennis_api_com": {
        "name": "tabletennis-api.com",
        "role": "REJECTED - Do NOT use as an implementation-ready adapter.",
        "transport": "Placeholder drafts",
        "verified": False,
        "unverified": "All coverage, authentication, and endpoint protocols remain placeholders."
    }
}

class LeagueScopeValidator:
    @staticmethod
    def validate_league(league_name: str, country_name: Optional[str] = None) -> bool:
        """
        Validates that an incoming feed or match strictly belongs to Czech Liga Pro.
        Rejects all non-Czech leagues, TT Cup, Setka Cup, and deceptive aliases.
        """
        if not league_name or not isinstance(league_name, str):
            return False

        clean_name = league_name.strip().lower()

        # Reject explicitly prohibited leagues
        for prohibited in PROHIBITED_LEAGUES:
            if prohibited in clean_name:
                return False

        # Reject Russian country/federation references
        if country_name:
            clean_country = country_name.strip().lower()
            if "russia" in clean_country or "ukraine" in clean_country:
                return False

        # Verify positive match for Czech Liga Pro
        for pattern in CZECH_LIGA_PRO_PATTERNS:
            if re.search(pattern, clean_name):
                return True

        # Secondary check for compound tokens
        if "liga pro" in clean_name and ("czech" in clean_name or "cz" in clean_name):
            return True

        return False

    @staticmethod
    def get_provider_manifest() -> Dict[str, Any]:
        """Returns the audited candidate provider manifest and verification status."""
        return CANDIDATE_PROVIDERS
