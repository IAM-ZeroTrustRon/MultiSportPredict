"""
Discord Integration Module for MultiSportPredict
=================================================

Provides rich embed messages, error handling, and flexible Discord webhook integration.

Features:
- Rich embed formatting with colors and fields
- Confidence-based color coding
- Error handling and logging
- Support for various sports and markets
- **Deduplication** — prevents sending duplicate content within 6 hours
- **Rich table formatting** — renders predictions in organized table layout
"""

import hashlib
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    requests = None

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Color codes for Discord embeds
COLORS = {
    "strong_bet": 3066993,      # Green
    "bet": 10181046,            # Light blue
    "lean": 16776960,           # Yellow
    "pass": 15158332,           # Red
    "neutral": 9807270,         # Gray
}

SPORT_EMOJIS = {
    "soccer": "⚽",
    "football": "🏈",
    "basketball": "🏀",
    "baseball": "⚾",
    "mlb": "⚾",
    "kbo": "⚾",
    "tennis": "🎾",
    "hockey": "🏒",
}

# ---------------------------------------------------------------------------
# DEDUPLICATION CACHE
# ---------------------------------------------------------------------------
# Prevents sending the same Discord content more than once within the window.
# Keys are SHA-256 content hashes; values are Unix timestamps of last send.
_dedup_cache: Dict[str, float] = {}
DEDUP_WINDOW_SECONDS = 6 * 3600  # 6 hours default


def _content_hash(payload: Dict[str, Any]) -> str:
    """Compute a stable hash of the Discord payload for dedup comparison."""
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _is_duplicate(content_hash: str) -> bool:
    """Check if a content hash was sent within the dedup window."""
    now = time.time()
    last_send = _dedup_cache.get(content_hash)
    if last_send is not None and (now - last_send) < DEDUP_WINDOW_SECONDS:
        return True
    _dedup_cache[content_hash] = now
    return False


def clear_dedup_cache() -> None:
    """Clear the deduplication cache (useful for testing)."""
    _dedup_cache.clear()


# ---------------------------------------------------------------------------
# RICH TABLE FORMATTING FOR CONSOLE OUTPUT
# ---------------------------------------------------------------------------

def render_prediction_table(
    title: str,
    rows: List[Tuple[str, str]],
    *,
    columns: Optional[List[str]] = None,
) -> str:
    """
    Render a rich table using the `rich` library with a graceful fallback
    to plain-text formatting if `rich` is not installed.

    Args:
        title: Table title
        rows: List of (label, value) pairs
        columns: Optional custom column headers (defaults to ["Metric", "Value"])

    Returns:
        Formatted table string suitable for console output
    """
    if columns is None:
        columns = ["Metric", "Value"]

    try:
        from rich.console import Console
        from rich.table import Table

        console = Console(force_terminal=False, width=100)
        table = Table(title=title, style="cyan", title_style="bold cyan")
        for col in columns:
            table.add_column(col, style="magenta" if col == columns[0] else "green",
                             no_wrap=False, justify="left" if col == columns[0] else "right")

        for label, value in rows:
            table.add_row(label, str(value))

        with console.capture() as capture:
            console.print(table)
        return capture.get()
    except ImportError:
        # Fallback: plain text block
        sep = "-" * 60
        lines = [sep, f"  {title}", sep]
        for label, value in rows:
            lines.append(f"  {label:<30} {value}")
        lines.append(sep)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# COLOR HELPERS
# ---------------------------------------------------------------------------

def get_color_for_recommendation(recommendation: str) -> int:
    """Get Discord embed color based on recommendation."""
    rec_lower = recommendation.lower()

    if "strong" in rec_lower:
        return COLORS["strong_bet"]
    elif "bet" in rec_lower:
        return COLORS["bet"]
    elif "lean" in rec_lower:
        return COLORS["lean"]
    elif "pass" in rec_lower:
        return COLORS["pass"]
    else:
        return COLORS["neutral"]


# ---------------------------------------------------------------------------
# EMBED BUILDERS
# ---------------------------------------------------------------------------

def create_prediction_embed(
    sport: str,
    home: str,
    away: str,
    recommendation: str,
    confidence: float,
    edge: str,
    market_line: Optional[float] = None,
    market_total: Optional[float] = None,
    additional_fields: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Create a rich Discord embed for a prediction (legacy format).

    Args:
        sport: Sport name (soccer, basketball, etc.)
        home: Home team/player name
        away: Away team/player name
        recommendation: Bet recommendation (BET, PASS, LEAN, STRONG BET)
        confidence: Confidence score (0-100)
        edge: Edge percentage as string (e.g., "+2.3%")
        market_line: Optional market line
        market_total: Optional market total
        additional_fields: Optional dict of additional fields to add

    Returns:
        Dictionary formatted as Discord embed
    """

    emoji = SPORT_EMOJIS.get(sport.lower(), "🎲")
    color = get_color_for_recommendation(recommendation)

    # Build fields list
    fields = [
        {
            "name": "📊 Market Probabilities",
            "value": f"**{recommendation}**",
            "inline": True
        },
        {
            "name": "📈 Confidence",
            "value": f"{confidence:.1f}%",
            "inline": True
        },
        {
            "name": "💰 Edge",
            "value": edge,
            "inline": True
        },
    ]

    # Add market information if provided
    if market_line is not None:
        fields.append({
            "name": "📍 Market Line",
            "value": str(market_line),
            "inline": True
        })

    if market_total is not None:
        fields.append({
            "name": "📊 Market Total",
            "value": str(market_total),
            "inline": True
        })

    # Add any additional fields
    if additional_fields:
        for field_name, field_value in additional_fields.items():
            fields.append({
                "name": field_name,
                "value": str(field_value),
                "inline": True
            })

    # Create embed
    embed = {
        "title": f"{emoji} {home.upper()} vs {away.upper()}",
        "description": f"**{sport.title()}** Prediction",
        "color": color,
        "fields": fields,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "footer": {
            "text": "MultiSportPredict"
        }
    }

    return embed


def create_organized_prediction_embed(
    sport: str,
    home: str,
    away: str,
    strong_bets: List[Dict[str, Any]],
    medium_bets: List[Dict[str, Any]],
    pass_bets: List[Dict[str, Any]],
    projected_stats: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create an organized Discord embed highlighting bets by strength.

    Perfect for soccer with clear bet categories.

    Args:
        sport: Sport name
        home: Home team name
        away: Away team name
        strong_bets: List of strong bets [{"name": "Over 2.5", "prob": 72, "edge": "+1.4"}]
        medium_bets: List of medium confidence bets
        pass_bets: List of pass recommendations
        projected_stats: Optional dict with additional stats

    Returns:
        Formatted Discord embed dict
    """

    emoji = SPORT_EMOJIS.get(sport.lower(), "🎲")

    # Determine overall color based on strongest bet
    if strong_bets and strong_bets[0].get("prob", 0) >= 75:
        color = COLORS["strong_bet"]
    elif strong_bets and strong_bets[0].get("prob", 0) >= 65:
        color = COLORS["bet"]
    else:
        color = COLORS["neutral"]

    fields = []

    # STRONG BETS section
    if strong_bets:
        strong_section = "🔥 **STRONG BETS** 🔥\n"
        for bet in strong_bets:
            strong_section += f"• {bet['name']}: {bet['prob']:.0f}% ({bet.get('edge', 'N/A')})\n"

        fields.append({
            "name": "💪 STRONG BET (≥65% Confidence)",
            "value": strong_section.strip(),
            "inline": False
        })

    # MEDIUM BETS section
    if medium_bets:
        medium_section = ""
        for bet in medium_bets:
            medium_section += f"• {bet['name']}: {bet['prob']:.0f}% ({bet.get('edge', 'N/A')})\n"

        fields.append({
            "name": "⚠️  MEDIUM BET (55-65% Confidence)",
            "value": medium_section.strip(),
            "inline": False
        })

    # PASS section
    if pass_bets:
        pass_section = ""
        for bet in pass_bets:
            pass_section += f"• {bet['name']}: {bet['prob']:.0f}% (Skip)\n"

        fields.append({
            "name": "❌ PASS (<55% Confidence)",
            "value": pass_section.strip(),
            "inline": False
        })

    # PROJECTED STATS section
    if projected_stats:
        stats_section = ""
        for stat_name, stat_value in projected_stats.items():
            stats_section += f"• {stat_name}: {stat_value}\n"

        fields.append({
            "name": "📊 Match Stats",
            "value": stats_section.strip(),
            "inline": False
        })

    # Create embed
    embed = {
        "title": f"{emoji} {home.upper()} vs {away.upper()}",
        "description": f"**{sport.title()}** - Prediction Report",
        "color": color,
        "fields": fields,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "footer": {
            "text": "MultiSportPredict • Organized Betting Guide"
        }
    }

    return embed


# ---------------------------------------------------------------------------
# CORE PUSH FUNCTIONS (with dedup)
# ---------------------------------------------------------------------------

def push_to_discord(
    *,
    sport: str,
    home: str,
    away: str,
    recommendation: str,
    confidence: float,
    edge: str,
    market_line: Optional[float] = None,
    market_total: Optional[float] = None,
    use_embed: bool = True,
    webhook_url: Optional[str] = None,
    additional_fields: Optional[Dict[str, str]] = None,
) -> bool:
    """
    Push a prediction to Discord via webhook.

    Features built-in deduplication: identical content will only be sent
    once every 6 hours to prevent spam/looping.

    Args:
        sport: Sport name
        home: Home team/player
        away: Away team/player
        recommendation: Bet recommendation
        confidence: Confidence score (0-100)
        edge: Edge percentage
        market_line: Optional market line
        market_total: Optional market total
        use_embed: Use rich embed format (True) or plain text (False)
        webhook_url: Override default webhook URL
        additional_fields: Additional custom fields for embed

    Returns:
        True if successful, False otherwise
    """

    if requests is None:
        logger.error("requests library not installed. Cannot push to Discord.")
        return False

    target_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")

    if not target_url or target_url == "None":
        logger.error("Discord push aborted: DISCORD_WEBHOOK_URL not set in environment.")
        return False

    try:
        if use_embed:
            # Rich embed format
            embed = create_prediction_embed(
                sport=sport,
                home=home,
                away=away,
                recommendation=recommendation,
                confidence=confidence,
                edge=edge,
                market_line=market_line,
                market_total=market_total,
                additional_fields=additional_fields,
            )
            payload = {"embeds": [embed]}
        else:
            # Plain text format
            emoji = SPORT_EMOJIS.get(sport.lower(), "🎲")
            message = (
                f"{emoji} **{sport.upper()}** Prediction\n"
                f"**{home}** vs **{away}**\n"
                f"├─ Recommendation: {recommendation}\n"
                f"├─ Confidence: {confidence:.1f}%\n"
                f"├─ Edge: {edge}\n"
            )

            if market_line is not None:
                message += f"├─ Market Line: {market_line}\n"
            if market_total is not None:
                message += f"├─ Market Total: {market_total}\n"
            if additional_fields:
                for field_name, field_value in additional_fields.items():
                    message += f"├─ {field_name}: {field_value}\n"

            message += "└─ MultiSportPredict"
            payload = {"content": message}

        # ---- DEDUPLICATION: skip if this exact payload was sent recently ----
        content_id = _content_hash(payload)
        if _is_duplicate(content_id):
            logger.info(
                "Discord push skipped (duplicate content within %ds window): %s vs %s [%s]",
                DEDUP_WINDOW_SECONDS, home, away, sport
            )
            return True  # Pretend success — we don't want to spam
        # --------------------------------------------------------------------

        response = requests.post(
            target_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )

        if response.status_code in (200, 204):
            logger.info("✓ Discord prediction pushed successfully: %s vs %s [%s]", home, away, sport)
            return True
        else:
            logger.error(
                "Discord push failed: status=%s body=%s",
                response.status_code,
                response.text,
            )
            return False

    except requests.exceptions.RequestException as e:
        logger.error(f"Discord webhook request failed: {e}")
        return False


def push_full_prediction_to_discord(
    *,
    sport: str,
    home: str,
    away: str,
    prediction: Dict[str, Any],
    webhook_url: Optional[str] = None,
) -> bool:
    """Push every section of a model result as bounded Discord embeds.

    Discord limits embed fields and field values. Flattening each top-level
    result section and splitting it into multiple embeds preserves all model
    markets without silently dropping nested props or probabilities.
    """
    if requests is None:
        logger.error("requests library not installed. Cannot push to Discord.")
        return False

    target_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
    if not target_url or target_url == "None":
        logger.error("Discord push aborted: DISCORD_WEBHOOK_URL not set in environment.")
        return False

    def format_value(value: Any, prefix: str = "") -> List[str]:
        if isinstance(value, dict):
            lines: List[str] = []
            for key, nested in value.items():
                label = f"{prefix}.{key}" if prefix else str(key)
                lines.extend(format_value(nested, label))
            return lines
        if isinstance(value, list):
            return [f"{prefix}: {json.dumps(value, default=str)}"]
        if isinstance(value, float):
            return [f"{prefix}: {value:.4f}"]
        return [f"{prefix}: {value}"]

    fields: List[Dict[str, Any]] = []
    for section, value in prediction.items():
        if section in {"sport", "home_team", "away_team", "timestamp"}:
            continue
        lines = format_value(value, str(section)) or [f"{section}: N/A"]
        chunks = [lines[i:i + 18] for i in range(0, len(lines), 18)]
        for chunk_index, chunk in enumerate(chunks, start=1):
            field_name = str(section) if chunk_index == 1 else f"{section} ({chunk_index})"
            fields.append({
                "name": field_name[:256],
                "value": "\n".join(chunk)[:1024],
                "inline": False,
            })

    embeds: List[Dict[str, Any]] = []
    for embed_index in range(0, len(fields), 8):
        embed_fields = fields[embed_index:embed_index + 8]
        embeds.append({
            "title": f"{SPORT_EMOJIS.get(sport.lower(), '🎲')} {home} vs {away}",
            "description": f"{sport.title()} full model results",
            "color": COLORS["neutral"],
            "fields": embed_fields,
            "footer": {"text": "MultiSportPredict | Full result"},
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    if not embeds:
        embeds = [{
            "title": f"{SPORT_EMOJIS.get(sport.lower(), '🎲')} {home} vs {away}",
            "description": "No model result sections were returned.",
            "color": COLORS["pass"],
        }]

    try:
        for batch_start in range(0, len(embeds), 10):
            payload = {"embeds": embeds[batch_start:batch_start + 10]}
            content_id = _content_hash(payload)
            if _is_duplicate(content_id):
                continue
            response = requests.post(
                target_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            if response.status_code not in (200, 204):
                logger.error("Full Discord push failed: status=%s body=%s", response.status_code, response.text)
                return False
        logger.info("Full Discord prediction pushed successfully: %s vs %s [%s]", home, away, sport)
        return True
    except requests.exceptions.RequestException as exc:
        logger.error("Full Discord webhook request failed: %s", exc)
        return False
    except Exception as e:
        logger.error(f"Unexpected error pushing to Discord: {e}")
        return False


def push_batch_to_discord(
    predictions: List[Dict[str, Any]],
    webhook_url: Optional[str] = None,
) -> int:
    """
    Push multiple predictions to Discord (dedup applies per prediction).

    Args:
        predictions: List of prediction dicts (each must have sport, home, away,
                    recommendation, confidence, edge)
        webhook_url: Override default webhook URL

    Returns:
        Number of successfully pushed predictions (not counting duplicates)
    """

    success_count = 0

    for pred in predictions:
        result = push_to_discord(
            sport=pred["sport"],
            home=pred["home"],
            away=pred["away"],
            recommendation=pred["recommendation"],
            confidence=pred["confidence"],
            edge=pred["edge"],
            market_line=pred.get("market_line"),
            market_total=pred.get("market_total"),
            webhook_url=webhook_url,
            additional_fields=pred.get("additional_fields"),
        )
        if result:
            success_count += 1

    logger.info(f"Pushed {success_count}/{len(predictions)} predictions to Discord.")
    return success_count


# ---------------------------------------------------------------------------
# SLATE PUSH WITH CONSOLIDATED FORMATTING
# ---------------------------------------------------------------------------

def push_slate_to_discord(
    slate: List[Dict[str, Any]],
    sport: str = "soccer",
    webhook_url: Optional[str] = None,
) -> int:
    """
    Push a consolidated slate of predictions to Discord as a single rich embed
    with organized table formatting.

    This is the SINGLE canonical entry point for slate pushes — prevents
    duplicate slate messages from multiple scripts.

    Args:
        slate: List of prediction dicts with keys:
               home, away, market, projected, edge, rec
        sport: Sport name (default: "soccer")
        webhook_url: Override default webhook URL

    Returns:
        1 if successful, 0 if failed
    """
    from universal_runner import push_to_discord as _universal_push

    target_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
    if not target_url or target_url == "None":
        logger.error("Slate push aborted: DISCORD_WEBHOOK_URL not set.")
        return 0

    emoji = SPORT_EMOJIS.get(sport.lower(), "🎲")

    # Build a single consolidated message
    lines = [f"{emoji} **{sport.title()} SLATE — {len(slate)} Matches**", ""]

    for i, match in enumerate(slate, 1):
        lines.append(f"**{i}. {match['home']} vs {match['away']}**")
        lines.append(f"   ├─ Market: {match.get('market', 'N/A')}")
        lines.append(f"   ├─ Projected: {match.get('projected', 'N/A')}")
        lines.append(f"   ├─ Edge: {match.get('edge', 'N/A')}")
        lines.append(f"   └─ Recommendation: **{match.get('rec', 'PASS')}**")
        lines.append("")

    lines.append("└─ MultiSportPredict • Smart Betting Guide")
    content = "\n".join(lines)

    # Compute hash for dedup
    payload = {"content": content}
    content_id = _content_hash(payload)

    if _is_duplicate(content_id):
        logger.info("Slate push skipped (duplicate content within %ds window).", DEDUP_WINDOW_SECONDS)
        return 1  # Pretend success

    try:
        response = requests.post(
            target_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        if response.status_code in (200, 204):
            logger.info("✓ Slate pushed to Discord successfully (%d matches).", len(slate))
            return 1
        else:
            logger.error("Slate push failed: status=%s", response.status_code)
            return 0
    except Exception as e:
        logger.error("Slate push error: %s", e)
        return 0


# ---------------------------------------------------------------------------
# SOCCER PREDICTION PUSH (convenience wrapper)
# ---------------------------------------------------------------------------

def push_soccer_prediction_to_discord(
    match_name: str,
    prediction_data: dict,
    *,
    dry_run: bool = False,
    webhook_url: Optional[str] = None,
) -> bool:
    """
    Push a soccer match prediction to Discord with a sport-specific embed.

    Args:
        match_name: Display name for the match (e.g. "South Melbourne vs Adelaide United")
        prediction_data: Output dict from SoccerPredictor.predict()
        dry_run: If True, print payload instead of posting
        webhook_url: Override default webhook URL

    Returns:
        True if successful (or dry-run), False otherwise
    """
    game = prediction_data.get("game", {})
    preds = prediction_data.get("predictions", {})
    goals_analysis = prediction_data.get("goals_analysis", {})
    btts_prob = prediction_data.get("btts_probability", 0)
    corner_proj = prediction_data.get("corner_projection", 0)

    home = prediction_data.get("home_team", "Home")
    away = prediction_data.get("away_team", "Away")

    home_win_pct = game.get("home_win_prob", 0) * 100
    away_win_pct = game.get("away_win_prob", 0) * 100

    # Format values for embed fields
    winner_value = (
        f"{home}: {home_win_pct:.1f}%"
        if home_win_pct >= away_win_pct
        else f"{away}: {away_win_pct:.1f}%"
    )
    btts_value = "Yes" if btts_prob > 0.5 else "No"
    totals_value = (
        f"Over {preds.get('total', {}).get('market_total', 2.5)} "
        f"({goals_analysis.get('over_25_prob', 0)*100:.1f}%)"
    )
    corners_value = str(round(corner_proj, 1))

    side = preds.get("side", {})
    total = preds.get("total", {})
    btts = preds.get("btts", {})
    corners = prediction_data.get("corners_analysis", {})
    home_metrics = prediction_data.get("team_metrics", {}).get("home", {})
    away_metrics = prediction_data.get("team_metrics", {}).get("away", {})

    def pct(value: Any) -> str:
        return f"{float(value) * 100:.1f}%"

    def metric_line(label: str, value: Any) -> str:
        return f"{label}: {value}"

    # Keep every market returned by the model visible in Discord. The compact
    # summary above is useful for scanning, while these fields are the full
    # market table for auditability and later comparison with the source JSON.
    additional_fields = {
        "1X2 Market": "\n".join([
            f"{home}: {pct(game.get('home_win_prob', 0))}",
            f"Draw: {pct(game.get('draw_prob', 0))}",
            f"{away}: {pct(game.get('away_win_prob', 0))}",
        ]),
        "Side / Asian Handicap": "\n".join([
            f"Line: {side.get('market_line', 'N/A')}",
            f"Model xG diff: {side.get('model_xg_diff', 0):+.3f}",
            f"Edge: {side.get('edge', 0):+.3f}",
            f"Confidence: {side.get('confidence', 0):.1f}%",
            f"Recommendation: {side.get('recommendation', 'PASS')}",
        ]),
        "Goal Totals Market": "\n".join([
            f"Line: {total.get('market_total', 2.5)}",
            f"Model total xG: {total.get('model_total_xg', 0):.3f}",
            f"Edge: {total.get('edge', 0):+.3f}",
            f"Confidence: {total.get('confidence', 0):.1f}%",
            f"Recommendation: {total.get('recommendation', 'PASS')}",
        ]),
        "Goal Probabilities": "\n".join([
            f"Over 1.5: {pct(goals_analysis.get('over_15_prob', 0))}",
            f"Over 2.5: {pct(goals_analysis.get('over_25_prob', 0))}",
            f"Over 3.5: {pct(goals_analysis.get('over_35_prob', 0))}",
        ]),
        "BTTS Market": "\n".join([
            f"Yes probability: {pct(btts.get('probability', btts_prob))}",
            f"Confidence: {btts.get('confidence', 0):.1f}%",
            f"Recommendation: {btts.get('recommendation', 'PASS')}",
        ]),
        "Corner Totals Market": "\n".join([
            f"Projection: {corners.get('projection', corner_proj):.1f}",
            f"Over 8.5: {pct(corners.get('over_85_prob', 0))}",
            f"Over 9.5: {pct(corners.get('over_95_prob', 0))}",
            f"Over 10.5: {pct(corners.get('over_105_prob', 0))}",
        ]),
        "Projected Score": "\n".join([
            f"{home}: {game.get('projected_home_goals', 0):.2f} goals",
            f"{away}: {game.get('projected_away_goals', 0):.2f} goals",
            f"Total: {game.get('projected_total_goals', 0):.2f} goals",
        ]),
        f"{home} Team Metrics": "\n".join([
            metric_line("xG for", home_metrics.get("xg_for", "N/A")),
            metric_line("xG against", home_metrics.get("xg_against", "N/A")),
            metric_line("Shots", home_metrics.get("shots", "N/A")),
            metric_line("Shots on target", home_metrics.get("sot", "N/A")),
            metric_line("Goals for / against", f"{home_metrics.get('goals_for', 'N/A')} / {home_metrics.get('goals_against', 'N/A')}"),
        ]),
        f"{away} Team Metrics": "\n".join([
            metric_line("xG for", away_metrics.get("xg_for", "N/A")),
            metric_line("xG against", away_metrics.get("xg_against", "N/A")),
            metric_line("Shots", away_metrics.get("shots", "N/A")),
            metric_line("Shots on target", away_metrics.get("sot", "N/A")),
            metric_line("Goals for / against", f"{away_metrics.get('goals_for', 'N/A')} / {away_metrics.get('goals_against', 'N/A')}"),
        ]),
        "Data Source": prediction_data.get("_stats_source", "unknown"),
    }

    if dry_run:
        embed = create_prediction_embed(
            sport="soccer",
            home=home,
            away=away,
            recommendation=preds.get("total", {}).get("recommendation", "PASS"),
            confidence=preds.get("total", {}).get("confidence", 0),
            edge=f"{preds.get('total', {}).get('edge', 0):+.3f}",
            market_total=preds.get("total", {}).get("market_total", 2.5),
            additional_fields=additional_fields,
        )
        payload = {"embeds": [embed]}
        print(f"[DRY RUN] Soccer Prediction Payload for {match_name}:")
        print(json.dumps(payload, indent=2, default=str))
        return True

    return push_to_discord(
        sport="soccer",
        home=home,
        away=away,
        recommendation=preds.get("total", {}).get("recommendation", "PASS"),
        confidence=preds.get("total", {}).get("confidence", 0),
        edge=f"{preds.get('total', {}).get('edge', 0):+.3f}",
        market_total=preds.get("total", {}).get("market_total", 2.5),
        use_embed=True,
        webhook_url=webhook_url,
        additional_fields=additional_fields,
    )


# ---------------------------------------------------------------------------
# RECOMMENDATIONS WEBHOOK (dedicated tennis / value-pick embeds)
# ---------------------------------------------------------------------------

RECOMMENDATIONS_WEBHOOK_URL = os.getenv("DISCORD_RECOMMENDATIONS_WEBHOOK_URL")


def push_recommendation_to_discord(
    prediction_result: dict,
    dry_run: bool = False,
) -> None:
    """
    Pushes a high-value pick or recommendation embed to the dedicated
    recommendations Discord channel.

    The embed is tailored for tennis predictions but can be extended to
    other sports by adjusting the fields.

    Args:
        prediction_result: Dict with keys:
            - home_player / away_player  (or home / away)
            - tournament
            - surface
            - market_home_odds / market_away_odds
            - moneyline: dict with home_win_prob, confidence, recommendation, edge_pct
        dry_run: If True, prints the payload instead of sending it.
    """
    if not RECOMMENDATIONS_WEBHOOK_URL:
        print("[ERROR] DISCORD_RECOMMENDATIONS_WEBHOOK_URL is not configured in .env")
        return

    if requests is None:
        print("[ERROR] requests library not installed. Cannot push to Discord.")
        return

    ml = prediction_result.get("moneyline", {})
    home_player = prediction_result.get("home_player") or prediction_result.get("home", "Player 1")
    away_player = prediction_result.get("away_player") or prediction_result.get("away", "Player 2")
    recommendation = ml.get("recommendation", "PASS")

    # Choose embed colour based on recommendation value
    # Green for active picks, Red/Gray for PASS
    color = 3066993 if recommendation != "PASS" else 15158332

    # Base fields
    fields = [
        {
            "name": "Tournament / Surface",
            "value": f"{prediction_result.get('tournament', 'N/A')} "
                     f"({prediction_result.get('surface', 'N/A').title()})",
            "inline": False,
        },
        {
            "name": "Selection / Rec",
            "value": f"**{recommendation}**",
            "inline": True,
        },
        {
            "name": "Model Win Prob",
            "value": f"{ml.get('home_win_prob', 0):.1%}",
            "inline": True,
        },
        {
            "name": "Confidence",
            "value": f"{ml.get('confidence', 0):.0f}%",
            "inline": True,
        },
        {
            "name": "Calculated Edge",
            "value": f"{ml.get('edge_pct', 0):+.1f}%",
            "inline": True,
        },
        {
            "name": "Market Odds",
            "value": f"{prediction_result.get('market_home_odds', 'N/A')} / "
                     f"{prediction_result.get('market_away_odds', 'N/A')}",
            "inline": True,
        },
    ]

    # Optional value-play fields (both perspectives) when provided by the caller.
    value_plays = prediction_result.get("value_plays")
    if value_plays:
        # Original value plays
        plays = value_plays.get("plays", {})
        if plays:
            lines = [
                f"`{name}` — {odds}" for name, odds in plays.items()
            ]
            fields.append({
                "name": "🎯 Original Value Plays",
                "value": "\n".join(lines),
                "inline": False,
            })
        original_lean = value_plays.get("original_lean")
        if original_lean:
            fields.append({
                "name": "📝 Original Lean",
                "value": original_lean,
                "inline": False,
            })

        # Deep-dive plays
        deep_dive = value_plays.get("deep_dive", {})
        if deep_dive:
            lines = []
            if deep_dive.get("Target"):
                lines.append(f"• **Target:** {deep_dive['Target']}")
            if deep_dive.get("Angle"):
                lines.append(f"• **Angle:** {deep_dive['Angle']}")
            if deep_dive.get("Rationale"):
                lines.append(f"• **Rationale:** {deep_dive['Rationale']}")
            fields.append({
                "name": "🔍 Deep-Dive Analysis",
                "value": "\n".join(lines),
                "inline": False,
            })

        # Model view vs market
        model_view = value_plays.get("model_view", {})
        if model_view:
            fave = model_view.get("favorite", "coin_flip")
            fave_prob = model_view.get("favorite_win_prob", 0.5)
            fave_text = "coin-flip" if fave == "coin_flip" else f"{fave}"
            lines = [f"• **Model favorite:** {fave_text} — {fave_prob:.1%}"]
            if model_view.get("notes"):
                lines.append(f"• **Note:** {model_view['notes']}")
            fields.append({
                "name": "🤖 Model View",
                "value": "\n".join(lines),
                "inline": False,
            })

    embed = {
        "title": f"🎾 Tennis Value Pick: {home_player} vs {away_player}",
        "color": color,
        "fields": fields,
        "footer": {
            "text": f"MultiSportPredict Tennis Engine | "
                    f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        },
    }

    payload = {"embeds": [embed]}

    # ---- DEDUPLICATION: skip if this exact payload was sent recently ----
    content_id = _content_hash(payload)
    if _is_duplicate(content_id):
        logger.info(
            "Recommendation push skipped (duplicate within %ds window): %s vs %s",
            DEDUP_WINDOW_SECONDS, home_player, away_player,
        )
        return
    # --------------------------------------------------------------------

    if dry_run:
        print("[DRY RUN] Recommendation Webhook Payload:")
        print(json.dumps(payload, indent=2, default=str))
        return

    try:
        response = requests.post(
            RECOMMENDATIONS_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        if response.status_code == 204:
            print(
                f"[SUCCESS] Recommendation for {home_player} vs {away_player} "
                f"pushed to Discord."
            )
        else:
            print(
                f"[ERROR] Discord push failed. Status Code: {response.status_code} "
                f"Body: {response.text}"
            )
    except Exception as e:
        print(f"[EXCEPTION] Recommendation Webhook error: {e}")


# ---------------------------------------------------------------------------
# WEBHOOK TEST
# ---------------------------------------------------------------------------

def test_webhook(webhook_url: Optional[str] = None) -> bool:
    """
    Test if the Discord webhook is valid and accessible.

    Args:
        webhook_url: Override default webhook URL

    Returns:
        True if webhook is valid, False otherwise
    """

    if requests is None:
        logger.error("requests library not installed.")
        return False

    target_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")

    if not target_url or target_url == "None":
        logger.error("DISCORD_WEBHOOK_URL not set in environment.")
        return False

    try:
        payload = {
            "embeds": [{
                "title": "🧪 Webhook Test",
                "description": "If you see this message, your Discord webhook is working!",
                "color": 3066993,
            }]
        }

        response = requests.post(
            target_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )

        if response.status_code in (200, 204):
            logger.info("✓ Webhook test successful!")
            return True
        else:
            logger.error(f"Webhook test failed: status={response.status_code}")
            return False

    except Exception as e:
        logger.error(f"Webhook test error: {e}")
        return False


if __name__ == "__main__":
    # Test the webhook
    if test_webhook():
        print("✓ Your Discord webhook is properly configured!")

        # Test rich table rendering
        sample_rows = [
            ("Sport", "Soccer"),
            ("Home", "Liverpool"),
            ("Away", "Manchester United"),
            ("Confidence", "75.5%"),
            ("Edge", "+2.3%"),
        ]
        print(render_prediction_table("PREDICTION SUMMARY", sample_rows))

        # Send a test prediction (dedup will prevent re-sends)
        push_to_discord(
            sport="soccer",
            home="Liverpool",
            away="Manchester United",
            recommendation="BET",
            confidence=75.5,
            edge="+2.3%",
            market_total=2.5,
            use_embed=True,
        )
    else:
        print("✗ Discord webhook is not configured. Check your .env file.")