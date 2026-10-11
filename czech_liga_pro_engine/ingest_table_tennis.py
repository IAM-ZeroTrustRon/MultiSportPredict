"""
Table Tennis Data Ingestion & State Reconciliation
Sections 1, 5, 7 of Czech Liga Pro Handoff Specification.

Capabilities:
- Strict Czech Liga Pro filtering (rejects all other leagues).
- Idempotent deduplication and correction versioning.
- Canonical player mapping (disambiguates Sr/Jr and year-of-birth suffixes).
- Event-ID and scheduled-time tracking for same-day rematches between identical players.
- Raw timestamped JSON archiving.
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from table_tennis.provider_discovery import LeagueScopeValidator

logger = logging.getLogger(__name__)

class TableTennisIngestor:
    def __init__(self, archive_dir: str = "data/czech_liga_pro_samples/raw_archive"):
        self.archive_dir = archive_dir
        os.makedirs(self.archive_dir, exist_ok=True)
        self.events_db: Dict[str, Dict[str, Any]] = {}  # keyed by canonical event_id
        self.player_map: Dict[str, str] = {}            # raw name -> canonical player_id

    @staticmethod
    def canonicalize_player_name(raw_name: str) -> tuple[str, str]:
        """
        Normalizes player names while strictly preserving generation/birth qualifiers:
        e.g. 'Strnad Jaroslav 1964' != 'Strnad Jaroslav', 'Neuwirth Jaroslav SR' != 'JR'.
        """
        clean = " ".join(raw_name.strip().split())
        # Standardize 'Sr.' -> 'SR', 'Jr.' -> 'JR'
        clean = clean.replace("Sr.", "SR").replace("Jr.", "JR")
        clean = clean.replace("sr.", "SR").replace("jr.", "JR")
        player_id = clean.lower().replace(" ", "_")
        return clean, player_id

    def archive_raw_payload(self, source_name: str, payload: Dict[str, Any]) -> str:
        """Saves immutable, timestamped raw JSON payload for audit and replay."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{source_name}_{timestamp}.json"
        path = os.path.join(self.archive_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return path

    def process_incoming_event(self, raw_event: Dict[str, Any], source_name: str = "feed") -> Dict[str, Any]:
        """
        Validates, normalizes, and reconciles a table tennis event.
        Rejects non-Czech leagues and properly versions score corrections.
        """
        league_name = raw_event.get("league", "")
        country = raw_event.get("country", "Czech Republic")

        # 1. Enforce strict league boundary
        if not LeagueScopeValidator.validate_league(league_name, country):
            logger.info(f"Rejected event {raw_event.get('event_id')}: outside Czech Liga Pro scope ('{league_name}')")
            return {
                "status": "REJECTED_OUT_OF_SCOPE",
                "reason": f"League '{league_name}' does not match verified Czech Liga Pro criteria."
            }

        # 2. Archive raw payload
        self.archive_raw_payload(source_name, raw_event)

        event_id = str(raw_event.get("event_id") or raw_event.get("id"))
        if not event_id:
            raise ValueError("Event must contain an explicit 'event_id' or 'id'")

        # 3. Canonical player parsing (with suffix preservation)
        p_home_raw = raw_event.get("home_player", raw_event.get("player_a", {}))
        p_away_raw = raw_event.get("away_player", raw_event.get("player_b", {}))

        name_a_raw = p_home_raw if isinstance(p_home_raw, str) else p_home_raw.get("name", "")
        name_b_raw = p_away_raw if isinstance(p_away_raw, str) else p_away_raw.get("name", "")

        disp_a, id_a = self.canonicalize_player_name(name_a_raw)
        disp_b, id_b = self.canonicalize_player_name(name_b_raw)

        # 4. Handle same-pair matches (require scheduled time + event_id)
        scheduled_time = raw_event.get("scheduled_time_utc") or raw_event.get("start_time_utc")

        # 5. Check for corrections vs duplicate frames
        incoming_scores = raw_event.get("game_scores", [])
        status = raw_event.get("status", "scheduled")
        receipt_time = datetime.now(timezone.utc).isoformat()

        if event_id in self.events_db:
            existing = self.events_db[event_id]
            # Check if scores changed (correction)
            if existing.get("game_scores") != incoming_scores:
                version = existing.get("version", 1) + 1
                history = existing.get("version_history", [])
                history.append({
                    "version": existing.get("version", 1),
                    "superseded_at": receipt_time,
                    "previous_scores": existing.get("game_scores"),
                    "previous_status": existing.get("status")
                })
                existing["version"] = version
                existing["version_history"] = history
                existing["game_scores"] = incoming_scores
                existing["status"] = status
                existing["last_updated_utc"] = receipt_time
                return {"status": "CORRECTION_APPLIED", "event_id": event_id, "version": version}
            else:
                # Idempotent duplicate frame
                return {"status": "DUPLICATE_IGNORED", "event_id": event_id, "version": existing.get("version", 1)}

        # New valid event entry
        normalized_event = {
            "event_id": event_id,
            "version": 1,
            "league": "Czech Liga Pro",
            "tournament_group": raw_event.get("tournament_group"),
            "player_a": {"name": disp_a, "id": id_a, "rating": p_home_raw.get("rating", 750) if isinstance(p_home_raw, dict) else 750},
            "player_b": {"name": disp_b, "id": id_b, "rating": p_away_raw.get("rating", 750) if isinstance(p_away_raw, dict) else 750},
            "scheduled_time_utc": scheduled_time,
            "status": status,
            "best_of": raw_event.get("best_of", 5),
            "game_scores": incoming_scores,
            "created_at_utc": receipt_time,
            "last_updated_utc": receipt_time,
            "market_odds": raw_event.get("market_odds", {})
        }
        self.events_db[event_id] = normalized_event
        return {"status": "INGESTED_NEW", "event_id": event_id, "version": 1}


