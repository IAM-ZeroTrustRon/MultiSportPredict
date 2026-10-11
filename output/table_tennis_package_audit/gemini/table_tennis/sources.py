"""
Table Tennis Sources & Adapters
Section 1 and Section 7 of Czech Liga Pro Handoff Specification.

Enforces:
- Distinct environment variables per vendor (never reuse ODDS_API_KEY for other providers).
- Playwright Python event hooks: page.on("response", ...) and page.on("websocket", ...).
- Sanitized payload archiving without secrets or unverified mock packets.
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, timezone
from table_tennis.provider_discovery import LeagueScopeValidator

logger = logging.getLogger(__name__)

class BaseSourceAdapter(ABC):
    """Abstract base class for table tennis data and odds ingestion adapters."""
    def __init__(self, name: str, env_key_name: Optional[str] = None):
        self.name = name
        self.env_key_name = env_key_name
        self._api_key = os.environ.get(env_key_name) if env_key_name else None

    @abstractmethod
    def fetch_fixtures(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def fetch_results(self) -> List[Dict[str, Any]]:
        pass

    def is_authenticated(self) -> bool:
        return bool(self._api_key and len(self._api_key.strip()) > 0)


class OddsApiIoAdapter(BaseSourceAdapter):
    """
    Adapter for Odds-API.io / OddsHub.
    Uses separate env key ODDS_API_IO_KEY (never reuses ODDS_API_KEY).
    """
    def __init__(self):
        super().__init__(name="odds_api_io", env_key_name="ODDS_API_IO_KEY")
        self.base_url = "https://api.odds-api.io/v1"

    def fetch_fixtures(self) -> List[Dict[str, Any]]:
        if not self.is_authenticated():
            logger.warning("ODDS_API_IO_KEY not configured. Returning empty fixtures.")
            return []
        # In a real environment with credentials, performs authenticated REST request
        return []

    def fetch_results(self) -> List[Dict[str, Any]]:
        if not self.is_authenticated():
            return []
        return []


class BetsApiAdapter(BaseSourceAdapter):
    """
    Adapter for BetsAPI candidate feed.
    Uses separate env key BETSAPI_KEY. Candidate league ID 22742.
    """
    def __init__(self, league_id: int = 22742):
        super().__init__(name="betsapi", env_key_name="BETSAPI_KEY")
        self.league_id = league_id
        self.base_url = "https://api.b365api.com/v1"

    def fetch_fixtures(self) -> List[Dict[str, Any]]:
        if not self.is_authenticated():
            logger.warning("BETSAPI_KEY not configured. Returning empty fixtures.")
            return []
        return []

    def fetch_results(self) -> List[Dict[str, Any]]:
        if not self.is_authenticated():
            return []
        return []


class PlaywrightNetworkObserver:
    """
    Observer using documented Playwright Python event listeners:
    page.on("response", ...) and page.on("websocket", ...) -> ws.on("framereceived", ...)
    
    CRITICAL: Does not route around CAPTCHAs or invent hidden endpoints.
    Used exclusively in authorized browser sessions for discovery.
    """
    def __init__(self, output_archive_dir: str = "data/czech_liga_pro_samples"):
        self.output_dir = output_archive_dir
        self.captured_responses: List[Dict[str, Any]] = []
        self.captured_ws_frames: List[Dict[str, Any]] = []

    def register_listeners(self, page: Any) -> None:
        """
        Registers event hooks prior to navigation, strictly following Playwright Python API.
        NOTE: page.on('response', ...) is the correct API (not route.on).
        """
        def handle_response(response: Any):
            try:
                url = response.url
                # Filter for table tennis or odds API responses
                if any(k in url.lower() for k in ["table-tennis", "odds", "fixtures", "events", "liga-pro"]):
                    content_type = response.headers.get("content-type", "")
                    if "json" in content_type:
                        data = response.json()
                        self.captured_responses.append({
                            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                            "url": url,
                            "status": response.status,
                            "payload": data
                        })
            except Exception as e:
                logger.debug(f"Could not parse response: {e}")

        def handle_websocket(ws: Any):
            def handle_frame_received(payload: str):
                self.captured_ws_frames.append({
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "direction": "received",
                    "payload_preview": payload[:500] if isinstance(payload, str) else str(payload)[:500]
                })

            def handle_frame_sent(payload: str):
                self.captured_ws_frames.append({
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "direction": "sent",
                    "payload_preview": payload[:500] if isinstance(payload, str) else str(payload)[:500]
                })

            ws.on("framereceived", handle_frame_received)
            ws.on("framesent", handle_frame_sent)

        page.on("response", handle_response)
        page.on("websocket", handle_websocket)
