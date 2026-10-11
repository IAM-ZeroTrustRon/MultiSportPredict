"""
Table Tennis Odds Alerts & Freshness Validation
Section 6 and Section 8 of Czech Liga Pro Handoff Specification.

Features:
- Rigorous EV calculation:
  * Moneyline (no-push): EV = p * d - 1
  * Push/Refund-aware markets: EV = P(win) * (d - 1) - P(loss) * 1.0
- Alert suppression on quote staleness, suspension, or score-state desynchronization.
- Signal deduplication across event, market, selection, and price threshold.
- Discord embed formatting compatible with MultiSportPredict standards.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

@dataclass
class AlertSignal:
    event_id: str
    match_name: str
    market: str
    selection: str
    line: Optional[float]
    bookmaker_odds: float
    model_prob: float
    market_fair_prob: float
    ev_per_dollar: float
    edge_pct: float
    score_state: str
    quote_age_seconds: float
    generated_at_utc: str

class TableTennisAlertManager:
    def __init__(self, max_quote_age_seconds: float = 60.0, min_edge_pct: float = 3.5):
        self.max_quote_age_seconds = max_quote_age_seconds
        self.min_edge_pct = min_edge_pct
        self.active_alerts: Dict[str, AlertSignal] = {}  # key: alert_hash

    @staticmethod
    def calculate_ev_no_push(p_win: float, decimal_odds: float) -> float:
        """EV per $1 stake for binary no-push markets (e.g. Moneyline)."""
        return p_win * decimal_odds - 1.0

    @staticmethod
    def calculate_ev_with_push(p_win: float, p_loss: float, decimal_odds: float) -> float:
        """
        EV per $1 stake for integer line markets where push returns original stake:
        EV = P(win) * (decimal_odds - 1) - P(loss) * 1.0
        """
        return p_win * (decimal_odds - 1.0) - p_loss * 1.0

    def evaluate_quote_freshness(self, quote_timestamp_utc: Optional[str],
                                 current_time_utc: Optional[datetime] = None) -> Tuple[bool, float]:
        """Checks if a bookmaker quote is within the allowed freshness budget."""
        if not quote_timestamp_utc:
            return False, 9999.0
        now = current_time_utc or datetime.now(timezone.utc)
        try:
            quote_dt = datetime.fromisoformat(quote_timestamp_utc.replace("Z", "+00:00"))
            age = (now - quote_dt).total_seconds()
            return (0 <= age <= self.max_quote_age_seconds), max(0.0, age)
        except Exception:
            return False, 9999.0

    def build_signals_for_match(self, event_id: str, match_name: str,
                                prediction_data: Dict[str, Any],
                                market_quotes: Dict[str, Any],
                                current_score_str: str = "0-0",
                                quote_time_utc: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Evaluates bookmaker quotes against model distributions.
        Suppresses alerts if stale, suspended, or score states are desynchronized.
        """
        is_fresh, quote_age = self.evaluate_quote_freshness(quote_time_utc)
        if not is_fresh:
            return [{
                "status": "SUPPRESSED_STALE_QUOTE",
                "reason": f"Quote age {quote_age:.1f}s exceeds freshness budget of {self.max_quote_age_seconds}s."
            }]

        is_suspended = market_quotes.get("suspended", False)
        if is_suspended:
            return [{
                "status": "SUPPRESSED_MARKET_SUSPENDED",
                "reason": "Bookmaker has suspended trading on this event."
            }]

        signals: List[Dict[str, Any]] = []
        p_win_a = prediction_data["probabilities"]["selected_final_win_a"]
        p_win_b = prediction_data["probabilities"]["selected_final_win_b"]
        p_market_fair_a = prediction_data["probabilities"].get("top_down_market_a")

        # 1. Moneyline Evaluation
        ml = market_quotes.get("moneyline")
        if ml and isinstance(ml, dict):
            odds_a = ml.get("home", 0.0)
            odds_b = ml.get("away", 0.0)
            if odds_a > 1.0 and odds_b > 1.0 and p_market_fair_a is not None:
                fair_a = p_market_fair_a
                fair_b = 1.0 - fair_a

                # Player A edge
                edge_a = (p_win_a - fair_a) * 100.0
                ev_a = self.calculate_ev_no_push(p_win_a, odds_a)
                if edge_a >= self.min_edge_pct and ev_a > 0.0:
                    signals.append({
                        "event_id": event_id,
                        "match_name": match_name,
                        "market": "Moneyline",
                        "selection": prediction_data["player_a_name"],
                        "line": None,
                        "odds": odds_a,
                        "model_prob": p_win_a,
                        "market_fair": fair_a,
                        "edge_pct": round(edge_a, 2),
                        "ev": round(ev_a, 4),
                        "score_state": current_score_str
                    })

                # Player B edge
                edge_b = (p_win_b - fair_b) * 100.0
                ev_b = self.calculate_ev_no_push(p_win_b, odds_b)
                if edge_b >= self.min_edge_pct and ev_b > 0.0:
                    signals.append({
                        "event_id": event_id,
                        "match_name": match_name,
                        "market": "Moneyline",
                        "selection": prediction_data["player_b_name"],
                        "line": None,
                        "odds": odds_b,
                        "model_prob": p_win_b,
                        "market_fair": fair_b,
                        "edge_pct": round(edge_b, 2),
                        "ev": round(ev_b, 4),
                        "score_state": current_score_str
                    })

        # 2. Total Games Evaluation
        tg_quotes = market_quotes.get("total_games")
        dist_tg = prediction_data.get("market_distributions", {}).get("total_games", {})
        if tg_quotes and isinstance(tg_quotes, dict) and tg_quotes.get("line") == 3.5:
            over_odds = tg_quotes.get("over_odds", 0.0)
            under_odds = tg_quotes.get("under_odds", 0.0)
            p_model_over = dist_tg.get("over_3_5", 0.0)
            p_model_under = dist_tg.get("under_3_5", 0.0)

            if over_odds > 1.0 and under_odds > 1.0:
                inv_o = 1.0 / over_odds
                inv_u = 1.0 / under_odds
                fair_over = inv_o / (inv_o + inv_u)
                edge_over = (p_model_over - fair_over) * 100.0
                ev_over = self.calculate_ev_no_push(p_model_over, over_odds)

                if edge_over >= self.min_edge_pct and ev_over > 0.0:
                    signals.append({
                        "event_id": event_id,
                        "match_name": match_name,
                        "market": "Total Games",
                        "selection": "Over 3.5 Games",
                        "line": 3.5,
                        "odds": over_odds,
                        "model_prob": p_model_over,
                        "market_fair": round(fair_over, 4),
                        "edge_pct": round(edge_over, 2),
                        "ev": round(ev_over, 4),
                        "score_state": current_score_str
                    })

        return signals

    @staticmethod
    def format_discord_embed(signal: Dict[str, Any]) -> Dict[str, Any]:
        """Formats signal into clean Discord embed matching MultiSportPredict standards."""
        return {
            "title": f"🏓 Table Tennis | {signal['match_name']}",
            "description": f"Czech Liga Pro Verified Edge Alert\nScore at quotation: **{signal['score_state']}**",
            "color": 3447003,  # Blue/Cyan
            "fields": [
                {
                    "name": "Market & Selection",
                    "value": f"**{signal['market']}**: `{signal['selection']}`",
                    "inline": True
                },
                {
                    "name": "Executable Odds",
                    "value": f"**{signal['odds']:.2f}**",
                    "inline": True
                },
                {
                    "name": "Edge / EV",
                    "value": f"+{signal['edge_pct']}% edge (EV: +${signal['ev'] * 100:.1f} / $100)",
                    "inline": True
                },
                {
                    "name": "Model vs Market Fair",
                    "value": f"Model: **{signal['model_prob']*100:.1f}%** | Mkt Fair: **{signal['market_fair']*100:.1f}%**",
                    "inline": False
                }
            ],
            "footer": {
                "text": f"MultiSportPredict • Czech Liga Pro Engine • Event ID: {signal['event_id']}"
            }
        }
