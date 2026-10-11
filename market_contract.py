"""Canonical records shared by automatic market sources, models and reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class MarketQuote:
    event_id: str
    bookmaker: str
    market_key: str
    period: str
    family: str
    selection: str
    line: Optional[float]
    american_price: Optional[float]
    updated_at: Optional[str]
    source: str
    regulation_only: bool
    participant_id: Optional[str] = None
    participant_name: Optional[str] = None
    competition: Optional[str] = None
    gender: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def market_status(status: str, reason: str, **details: Any) -> Dict[str, Any]:
    """Represent support state explicitly; absence must never resemble a pass."""
    return {"status": status, "reason": reason, **details}


def american_to_decimal(price: Optional[float]) -> Optional[float]:
    if price is None:
        return None
    value = float(price)
    if value <= -100:
        return 1.0 + 100.0 / abs(value)
    if value >= 100:
        return 1.0 + value / 100.0
    raise ValueError("American price must be <= -100 or >= +100")


def quote_from_outcome(event: Dict[str, Any], bookmaker: Dict[str, Any],
                       market: Dict[str, Any], outcome: Dict[str, Any],
                       period: str, family: str) -> MarketQuote:
    point = outcome.get("point")
    return MarketQuote(
        event_id=str(event.get("id", "")),
        bookmaker=str(bookmaker.get("key", "unknown")),
        market_key=str(market.get("key", "")),
        period=period,
        family=family,
        selection=str(outcome.get("name", "")),
        line=float(point) if point is not None else None,
        american_price=(float(outcome["price"]) if outcome.get("price") is not None else None),
        updated_at=(market.get("last_update") or bookmaker.get("last_update")),
        source="the-odds-api",
        regulation_only=period != "FG",
        participant_id=(str(outcome["id"]) if outcome.get("id") is not None else None),
        participant_name=(str(outcome.get("description") or outcome.get("name") or "")),
        competition=event.get("sport_title"),
    )
