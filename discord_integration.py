"""
Discord Integration Module for MultiSportPredict
=================================================

Provides rich embed messages, error handling, and flexible Discord webhook integration.

Features:
- Rich embed formatting with colors and fields
- Confidence-based color coding
- Error handling and logging
- Support for various sports and markets
- **Deduplication**  prevents sending duplicate content within 6 hours
- **Rich table formatting**  renders predictions in organized table layout
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
    "soccer": "",
    "football": "",
    "basketball": "",
    "baseball": "",
    "mlb": "",
    "kbo": "",
    "tennis": "",
    "hockey": "",
}

# ---------------------------------------------------------------------------
# DEDUPLICATION CACHE
# ---------------------------------------------------------------------------
# Prevents sending the same Discord content more than once within the window.
# Keys are SHA-256 content hashes; values are Unix timestamps of last send.
_dedup_cache: Dict[str, float] = {}
DEDUP_WINDOW_SECONDS = 6 * 3600  # 6 hours default


def _content_hash(payload: Dict[str, Any], destinations: Any = None) -> str:
    """Hash the payload AND where it is going.

    Keying on content alone made "send this pick to the other server" look like
    a duplicate: the same embed to a different destination was suppressed, and
    the second server got nothing. What the guard is actually for is stopping
    the SAME pick reaching the SAME place twice -- so the destination belongs
    in the key. Re-pushing to one server is still caught; fanning one pick out
    to two servers is not a repeat and now goes through.
    """
    raw = json.dumps(payload, sort_keys=True, default=str)
    if destinations:
        raw += "|" + "|".join(sorted(str(d) for d in destinations))
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

    emoji = SPORT_EMOJIS.get(sport.lower(), "")
    color = get_color_for_recommendation(recommendation)

    # Build fields list
    fields = [
        {
            "name": " Market Probabilities",
            "value": f"**{recommendation}**",
            "inline": True
        },
        {
            "name": " Confidence",
            "value": f"{confidence:.1f}%",
            "inline": True
        },
        {
            "name": " Edge",
            "value": edge,
            "inline": True
        },
    ]

    # Add market information if provided
    if market_line is not None:
        fields.append({
            "name": " Market Line",
            "value": str(market_line),
            "inline": True
        })

    if market_total is not None:
        fields.append({
            "name": " Market Total",
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

    emoji = SPORT_EMOJIS.get(sport.lower(), "")

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
        strong_section = " **STRONG BETS** \n"
        for bet in strong_bets:
            strong_section += f" {bet['name']}: {bet['prob']:.0f}% ({bet.get('edge', 'N/A')})\n"

        fields.append({
            "name": " STRONG BET (65% Confidence)",
            "value": strong_section.strip(),
            "inline": False
        })

    # MEDIUM BETS section
    if medium_bets:
        medium_section = ""
        for bet in medium_bets:
            medium_section += f" {bet['name']}: {bet['prob']:.0f}% ({bet.get('edge', 'N/A')})\n"

        fields.append({
            "name": "  MEDIUM BET (55-65% Confidence)",
            "value": medium_section.strip(),
            "inline": False
        })

    # PASS section
    if pass_bets:
        pass_section = ""
        for bet in pass_bets:
            pass_section += f" {bet['name']}: {bet['prob']:.0f}% (Skip)\n"

        fields.append({
            "name": " PASS (<55% Confidence)",
            "value": pass_section.strip(),
            "inline": False
        })

    # PROJECTED STATS section
    if projected_stats:
        stats_section = ""
        for stat_name, stat_value in projected_stats.items():
            stats_section += f" {stat_name}: {stat_value}\n"

        fields.append({
            "name": " Match Stats",
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
            "text": "MultiSportPredict  Organized Betting Guide"
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
            emoji = SPORT_EMOJIS.get(sport.lower(), "")
            message = (
                f"{emoji} **{sport.upper()}** Prediction\n"
                f"**{home}** vs **{away}**\n"
                f" Recommendation: {recommendation}\n"
                f" Confidence: {confidence:.1f}%\n"
                f" Edge: {edge}\n"
            )

            if market_line is not None:
                message += f" Market Line: {market_line}\n"
            if market_total is not None:
                message += f" Market Total: {market_total}\n"
            if additional_fields:
                for field_name, field_value in additional_fields.items():
                    message += f" {field_name}: {field_value}\n"

            message += " MultiSportPredict"
            payload = {"content": message}

        # ---- DEDUPLICATION: skip if this exact payload was sent recently ----
        content_id = _content_hash(payload, [target_url])
        if _is_duplicate(content_id):
            logger.info(
                "Discord push skipped (duplicate content within %ds window): %s vs %s [%s]",
                DEDUP_WINDOW_SECONDS, home, away, sport
            )
            return True  # Pretend success  we don't want to spam
        # --------------------------------------------------------------------

        response = requests.post(
            target_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )

        if response.status_code in (200, 204):
            logger.info(" Discord prediction pushed successfully: %s vs %s [%s]", home, away, sport)
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



def push_baseball_prediction_to_discord(
    prediction,
    *,
    home,
    away,
    sport="baseball",
    webhook_url=None,
):
    import os, json, requests
    from datetime import datetime

    target_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
    if not target_url:
        return False

    summary = prediction.get("summary", {})
    proj = prediction.get("game_projection", {})
    props = prediction.get("props", {})

    proj_total = proj.get("total", "N/A")
    home_runs = proj.get("home_runs", 0)
    away_runs = proj.get("away_runs", 0)

    # Extract total recommendation and confidence
    rec_text = summary.get("recommendation", "PASS")
    conf = summary.get("confidence", 50)
    edge = summary.get("edge", "+0.00 Runs vs 8.5")

    def emoji_for_rec(rec_str):
        r = str(rec_str).strip().upper()
        if "BET" in r:
            return "🟢"
        elif "PASS" in r:
            return "🔴"
        else:
            return "🟡"

    # 1. TOTAL MARKET (main recommendation)
    total_emoji = emoji_for_rec(rec_text)
    total_display = f"{total_emoji} **{rec_text}**\nEdge: {edge}\nConf: {conf}%"

    # 2. NRFI Formatting
    nrfi_data = props.get("nrfi", {})
    nrfi_prob = nrfi_data.get("probability", nrfi_data.get("prob", None))
    nrfi_rec = nrfi_data.get("recommendation", nrfi_data.get("lean", "N/A"))
    nrfi_emoji = emoji_for_rec(nrfi_rec)
    if nrfi_prob is not None:
        nrfi_display = f"{nrfi_emoji} **{nrfi_rec}** ({float(nrfi_prob)*100:.1f}%)"
    else:
        nrfi_display = f"{nrfi_emoji} **{nrfi_rec}**"

    # 3. Strikeout Props Formatting
    ks_data = props.get("strikeouts", {})
    home_ks = ks_data.get("home_team_projected_ks", "N/A")
    away_ks = ks_data.get("away_team_projected_ks", "N/A")
    ks_display = f"**{home}:** {home_ks} K\n**{away}:** {away_ks} K"

    # 4. Home Run Props Formatting
    hr_data = props.get("home_runs", {})
    home_hrs = hr_data.get("home_team_projected_hrs", "N/A")
    away_hrs = hr_data.get("away_team_projected_hrs", "N/A")
    hr_display = f"**{home}:** {home_hrs} HR\n**{away}:** {away_hrs} HR"

    # Build the embed with clear table format
    fields = [
        {
            "name": "📊 PROJECTION",
            "value": f"**Total:** {proj_total} runs\n**{home}:** {home_runs}R\n**{away}:** {away_runs}R",
            "inline": True
        },
        {
            "name": "🎯 TOTAL O/U",
            "value": total_display,
            "inline": True
        },
        {
            "name": "🔥 NRFI / YRFI",
            "value": nrfi_display,
            "inline": True
        },
        {
            "name": "⚾ STRIKEOUTS",
            "value": ks_display,
            "inline": True
        },
        {
            "name": "🏟️ HOME RUNS",
            "value": hr_display,
            "inline": True
        },
    ]

    color_map = {"BET": 3066993, "LEAN": 16776960, "PASS": 15158332}
    color = next((v for k, v in color_map.items() if k in str(rec_text).upper()), 9807270)

    embed = {
        "title": f"[{sport.upper()}] {home.upper()} @ {away.upper()}",
        "description": f"**{away}** at **{home}**",
        "color": color,
        "fields": fields,
        "footer": {"text": "MultiSportPredict Baseball Slate"},
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    try:
        payload = json.dumps({"embeds": [embed]}, ensure_ascii=False).encode("utf-8")
        resp = requests.post(
            target_url,
            data=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=10,
        )
        return resp.status_code in (200, 204)
    except Exception as e:
        print(f"[ERROR] Baseball Discord push failed: {e}")
        return False

def push_full_prediction_to_discord(
    *,
    sport: str,
    home: str,
    away: str,
    prediction: Dict[str, Any],
    webhook_url: Optional[str] = None,
) -> bool:
    if sport.lower() in {"soccer", "football"}:
        return push_soccer_prediction_to_discord(
            f"{home} vs {away}", prediction, webhook_url=webhook_url
        )
    if sport.lower() == "tennis":
        return push_tennis_prediction_to_discord(
            prediction, home=home, away=away, webhook_url=webhook_url
        )
    if sport.lower() in {"baseball", "mlb", "kbo"}:
        return push_baseball_prediction_to_discord(
            prediction, home=home, away=away, sport=sport, webhook_url=webhook_url
        )

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
            "title": f"{SPORT_EMOJIS.get(sport.lower(), '')} {home} vs {away}",
            "description": f"{sport.title()} full model results",
            "color": COLORS["neutral"],
            "fields": embed_fields,
            "footer": {"text": "MultiSportPredict | Full result"},
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    if not embeds:
        embeds = [{
            "title": f"{SPORT_EMOJIS.get(sport.lower(), '')} {home} vs {away}",
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

    This is the SINGLE canonical entry point for slate pushes  prevents
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

    emoji = SPORT_EMOJIS.get(sport.lower(), "")

    # Build a single consolidated message
    lines = [f"{emoji} **{sport.title()} SLATE  {len(slate)} Matches**", ""]

    for i, match in enumerate(slate, 1):
        lines.append(f"**{i}. {match['home']} vs {match['away']}**")
        lines.append(f"    Market: {match.get('market', 'N/A')}")
        lines.append(f"    Projected: {match.get('projected', 'N/A')}")
        lines.append(f"    Edge: {match.get('edge', 'N/A')}")
        lines.append(f"    Recommendation: **{match.get('rec', 'PASS')}**")
        lines.append("")

    lines.append(" MultiSportPredict  Smart Betting Guide")
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
            logger.info(" Slate pushed to Discord successfully (%d matches).", len(slate))
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
    Push a soccer match prediction to Discord.

    Formatting note: the earlier version put every section in a full-width
    field, so four dense `Label: value | Label: value` paragraphs stacked into
    a wall of text. Discord lays `inline` fields out as a grid three across,
    which is the whole reason the baseball embed reads better -- it was never a
    data problem. Soccer actually carries MORE markets than baseball; they just
    needed to be broken into short, bold, scannable cards.

    Empty sections are omitted rather than rendered as "N/A | N/A | N/A".
    A field that says nothing is worse than no field.
    """
    game = prediction_data.get("game", {}) or {}
    preds = prediction_data.get("predictions", {}) or {}
    goals = prediction_data.get("goals_analysis", {}) or {}
    corners = prediction_data.get("corners_analysis", {}) or {}
    btts = preds.get("btts", {}) or {}
    halftime = prediction_data.get("halftime", {}) or {}
    team_corners = prediction_data.get("team_corners", {}) or {}
    live_market = (prediction_data.get("live_market", {}) or {}).get("market", {}) or {}
    home, away = _tennis_players(prediction_data)
    league_name = prediction_data.get("league", "Soccer")

    def num(value, default=None):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def pct(value):
        parsed = num(value)
        return None if parsed is None else f"{parsed * 100:.1f}%"

    def badge(recommendation, confidence=None):
        text = str(recommendation or "PASS").strip().upper()
        icon = {"STRONG BET": "\U0001F7E2", "BET": "\U0001F7E2",
                "PASS": "\u26AA", "NO BET": "\u26AA"}.get(text, "\U0001F7E1")
        score = num(confidence)
        suffix = f" *(conf {score:.0f})*" if score is not None else ""
        return f"{icon} **{text}**{suffix}"

    def field(name, lines, inline=True):
        kept = [line for line in lines if line]
        return {"name": name, "value": "\n".join(kept), "inline": inline} if kept else None

    fields = []

    # --- moneyline -------------------------------------------------------
    home_prob, draw_prob, away_prob = (pct(game.get("home_win_prob")),
                                       pct(game.get("draw_prob")),
                                       pct(game.get("away_win_prob")))
    if home_prob or away_prob:
        side = preds.get("side", {}) or {}
        fields.append(field("\U0001F4B0 MONEYLINE", [
            f"**{home}** {home_prob}" if home_prob else None,
            f"**Draw** {draw_prob}" if draw_prob else None,
            f"**{away}** {away_prob}" if away_prob else None,
            badge(side.get("recommendation"), side.get("confidence")),
        ]))

    # --- projected scoreline ---------------------------------------------
    ph, pa = num(game.get("projected_home_goals")), num(game.get("projected_away_goals"))
    if ph is not None and pa is not None:
        total = num(game.get("projected_total_goals"), ph + pa)
        fields.append(field("\U0001F4CA PROJECTED", [
            f"**{ph:.2f} - {pa:.2f}**",
            f"Total **{total:.2f}**",
        ]))

    # --- match total ------------------------------------------------------
    total_block = preds.get("total", {}) or {}
    line = total_block.get("market_total")
    if line is not None or total_block.get("recommendation"):
        edge = total_block.get("edge")
        fields.append(field("\U0001F3AF MATCH TOTAL", [
            f"Line **{line}**" if line is not None else None,
            badge(total_block.get("recommendation"), total_block.get("confidence")),
            f"Edge **{edge}**" if edge not in (None, "N/A") else None,
        ]))

    # --- goal lines -------------------------------------------------------
    over15, over25, over35 = (pct(goals.get("over_15_prob")),
                              pct(goals.get("over_25_prob")),
                              pct(goals.get("over_35_prob")))
    if any((over15, over25, over35)):
        fields.append(field("\U0001F945 GOAL LINES", [
            f"O1.5 **{over15}**" if over15 else None,
            f"O2.5 **{over25}**" if over25 else None,
            f"O3.5 **{over35}**" if over35 else None,
        ]))

    # --- BTTS -------------------------------------------------------------
    btts_prob = pct(btts.get("probability", prediction_data.get("btts_probability")))
    if btts_prob or btts.get("recommendation"):
        fields.append(field("\U0001F91D BTTS", [
            f"Yes **{btts_prob}**" if btts_prob else None,
            badge(btts.get("recommendation"), btts.get("confidence")),
        ]))

    # --- first half -------------------------------------------------------
    ht_total = halftime.get("recommendation_1h_total")
    ht_result = halftime.get("predicted_1h_result")
    if ht_total or ht_result:
        fields.append(field("\u23F1\uFE0F FIRST HALF", [
            f"Total {badge(ht_total)}" if ht_total else None,
            f"Result **{ht_result}**" if ht_result else None,
        ]))

    # --- corners ----------------------------------------------------------
    corner_total = corners.get("projection", prediction_data.get("corner_projection"))
    o85, o95, o105 = (pct(corners.get("over_85_prob")), pct(corners.get("over_95_prob")),
                      pct(corners.get("over_105_prob")))
    corner_bits = []
    if corner_total not in (None, "N/A"):
        corner_bits.append(f"Projected **{corner_total}**")
    spread = " | ".join(x for x in (f"O8.5 **{o85}**" if o85 else "",
                                    f"O9.5 **{o95}**" if o95 else "",
                                    f"O10.5 **{o105}**" if o105 else "") if x)
    if spread:
        corner_bits.append(spread)
    hp, ap = team_corners.get("home_proj"), team_corners.get("away_proj")
    if hp not in (None, "N/A") and ap not in (None, "N/A"):
        corner_bits.append(f"{home} **{hp}** | {away} **{ap}**")
    if corner_bits:
        fields.append(field("\U0001F6A9 CORNERS", corner_bits, inline=False))

    # --- book prices, only when they actually arrived ---------------------
    ml_home = live_market.get("moneyline_home")
    ml_away = live_market.get("moneyline_away")
    if ml_home not in (None, "N/A") or ml_away not in (None, "N/A"):
        fields.append(field("\U0001F4C9 BOOK PRICES", [
            f"{home} **{ml_home}** | Draw **{live_market.get('moneyline_draw', 'N/A')}** "
            f"| {away} **{ml_away}**",
        ], inline=False))

    fields = [f for f in fields if f]

    side_rec = str((preds.get("side", {}) or {}).get("recommendation", "PASS")).upper()
    total_rec = str((preds.get("total", {}) or {}).get("recommendation", "PASS")).upper()
    btts_rec = str(btts.get("recommendation", "PASS")).upper()
    all_recs = [side_rec, total_rec, btts_rec]
    best_rec = ("STRONG BET" if "STRONG BET" in all_recs
                else "BET" if "BET" in all_recs else "PASS")
    color_map = {"STRONG BET": 3066993, "BET": 10181046, "PASS": 9807270}

    tier = prediction_data.get("data_tier")
    footer = "MultiSportPredict | Soccer"
    if tier and int(num(tier, 0) or 0) >= 2:
        footer += "  \u2022  Tier 2 data: xG estimated from goals"

    embed = {
        "title": f"{home} vs {away}",
        "description": (f"**{league_name}**  \u2022  "
                        f"{datetime.utcnow().strftime('%B %d, %Y')}  \u2022  "
                        f"Best signal: {badge(best_rec)}"),
        "color": color_map.get(best_rec, 9807270),
        "fields": fields,
        "footer": {"text": footer},
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    if dry_run:
        payload = {"embeds": [embed]}
        print(f"[DRY RUN] Soccer Prediction Payload for {match_name}:")
        print(json.dumps(payload, indent=2, default=str))
        return True

    target_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
    if not target_url or target_url == "None" or requests is None:
        logger.error("Soccer Discord push aborted: webhook or requests unavailable.")
        return False
    payload = {"embeds": [embed]}
    if _is_duplicate(_content_hash(payload)):
        return True
    try:
        response = requests.post(target_url, json=payload,
                                 headers={"Content-Type": "application/json"}, timeout=15)
        return response.status_code in (200, 204)
    except requests.exceptions.RequestException as exc:
        logger.error("Soccer Discord webhook request failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# TENNIS PREDICTION PUSH (single concise embed)
# ---------------------------------------------------------------------------

def push_tennis_prediction_to_discord(
    prediction: Dict[str, Any],
    *,
    home: Optional[str] = None,
    away: Optional[str] = None,
    dry_run: bool = False,
    webhook_url: Optional[str] = None,
) -> bool:
    """Push a tennis result as one readable four-field embed."""
    moneyline = prediction.get("moneyline", {})
    if home and away:
        home_player, away_player = home, away
    else:
        home_player, away_player = _tennis_players(prediction)

    def percent(value: Any) -> str:
        return f"{float(value) * 100:.1f}%"

    overview = "\n".join([
        f"Tournament: {prediction.get('tournament_name', prediction.get('tournament', 'N/A'))}",
        f"Surface: {str(prediction.get('surface', 'N/A')).title()}",
        f"Round: {prediction.get('round_name', prediction.get('round', 'N/A'))}",
    ])
    projections = "\n".join([
        f"{home_player}: {percent(moneyline.get('home_win_prob', 0))}",
        f"{away_player}: {percent(moneyline.get('away_win_prob', 0))}",
    ])
    fair_odds = "\n".join([
        f"Model fair odds: {home_player} {moneyline.get('home_fair_odds', 'N/A')} | {away_player} {moneyline.get('away_fair_odds', 'N/A')}",
        f"Market odds: {prediction.get('market_home_odds', 'N/A')} | {prediction.get('market_away_odds', 'N/A')}",
    ])
    recommendation = "\n".join([
        f"Lean: {moneyline.get('lean', prediction.get('recommendation', 'N/A'))}",
        f"Recommendation: {moneyline.get('recommendation', 'N/A')}",
        f"Confidence: {moneyline.get('confidence', prediction.get('confidence', 0)):.1f}%",
        f"Edge: {moneyline.get('edge_pct', prediction.get('edge_pct', 0)):+.1f}%",
    ])
    embed = {
        "title": f" {home_player} vs {away_player}",
        "description": "Tennis match forecast",
        "color": COLORS["neutral"],
        "fields": [
            {"name": " Match Overview", "value": overview, "inline": False},
            {"name": " Model Projections", "value": projections, "inline": False},
            {"name": " Fair Odds & Market", "value": fair_odds, "inline": False},
            {"name": " Recommendation", "value": recommendation, "inline": False},
        ],
        "footer": {"text": "MultiSportPredict"},
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    payload = {"embeds": [embed]}
    if dry_run:
        print("[DRY RUN] Tennis Prediction Payload:")
        print(json.dumps(payload, indent=2, default=str))
        return True

    target_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
    if not target_url or target_url == "None" or requests is None:
        logger.error("Tennis Discord push aborted: webhook or requests unavailable.")
        return False
    if _is_duplicate(_content_hash(payload)):
        return True
    try:
        response = requests.post(target_url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
        return response.status_code in (200, 204)
    except requests.exceptions.RequestException as exc:
        logger.error("Tennis Discord webhook request failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# RECOMMENDATIONS WEBHOOK (dedicated tennis / value-pick embeds)
# ---------------------------------------------------------------------------

RECOMMENDATIONS_WEBHOOK_URL = os.getenv("DISCORD_RECOMMENDATIONS_WEBHOOK_URL")


# ============================================================================
# MULTI-WEBHOOK BROADCASTER
# ============================================================================

def push_mode() -> str:
    """Where a push is allowed to go: "all", "bot" or "webhooks".

    Set DISCORD_PUSH_TARGET to pick. Default "all" keeps the old behaviour.
    An unrecognised value falls back to "all" rather than silently sending
    nowhere -- a typo in an env var should not look like a delivery.
    """
    mode = (os.getenv("DISCORD_PUSH_TARGET") or "all").strip().lower()
    return mode if mode in ("all", "bot", "webhooks") else "all"


def _bot_configured() -> bool:
    token = os.getenv("DISCORD_BOT_TOKEN") or ""
    channel = os.getenv("DISCORD_BOT_CHANNEL_ID") or ""
    return bool(token.strip()) and bool(channel.strip()) \
        and token.strip() != "None" and channel.strip() != "None"


def _get_target_webhooks(extra_webhooks=None):
    """Gather and deduplicate all configured Discord webhook URLs."""
    if push_mode() == "bot":
        return []          # bot channel only -- see push_mode()
    seen = set()
    urls = []
    def _add(url):
        if url and url.strip() and url.strip() not in ("None", ""):
            cleaned = url.strip()
            if cleaned not in seen:
                seen.add(cleaned)
                urls.append(cleaned)
    _add(os.getenv("DISCORD_WEBHOOK_URL"))
    _add(os.getenv("DISCORD_RECOMMENDATIONS_WEBHOOK_URL"))
    multi = os.getenv("DISCORD_WEBHOOK_URLS")
    if multi:
        for part in multi.replace(",", " ").split():
            _add(part.strip())
    if extra_webhooks:
        for u in extra_webhooks:
            _add(u)
    return urls


def _broadcast_embed(embed, extra_webhooks=None, dry_run=False, label="prediction"):
    """Post the same embed dict to every configured webhook URL."""
    mode = push_mode()
    targets = _get_target_webhooks(extra_webhooks)
    bot_wanted = mode != "webhooks" and _bot_configured()
    if not targets and not bot_wanted:
        print(f"[_broadcast_embed] Nothing to send to "
              f"(DISCORD_PUSH_TARGET={mode}). Nothing sent.")
        return 0
    if requests is None:
        print("[_broadcast_embed] requests library not installed. Cannot push.")
        return 0
    payload = {"embeds": [embed]}
    content_id = _content_hash(payload)
    if _is_duplicate(content_id):
        # This used to return len(targets) -- a full success for a push that
        # never happened -- and said so through logger.info, which is invisible
        # because nothing in this project calls logging.basicConfig. Re-running
        # a match inside the window printed "[OK] pushed" and sent nothing.
        # A suppressed duplicate is not a delivery, so it reports zero.
        print(f"[SKIP] {label}: identical to one sent within the last "
              f"{DEDUP_WINDOW_SECONDS // 3600}h. NOTHING WAS SENT. "
              f"Use clear_dedup_cache() to force it.")
        return 0
    if dry_run:
        print(f"[DRY RUN] Broadcast to {len(targets)} webhook(s) — {label}:")
        import json
        print(json.dumps(payload, indent=2, default=str))
        return len(targets)
    success_count = 0
    for url in targets:
        try:
            resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
            if resp.status_code in (200, 204):
                success_count += 1
            else:
                logger.error("Webhook post failed [%d] %s ... Body: %.200s", resp.status_code, url[:50], resp.text)
        except Exception as exc:
            logger.error("Webhook request error for %s ...: %s", url[:50], exc)
    # ---- Bot channel push (Discord REST API, not webhook) ----
    bot_token = os.getenv("DISCORD_BOT_TOKEN")
    bot_channel = os.getenv("DISCORD_BOT_CHANNEL_ID")
    bot_ok = True
    if bot_wanted:
        if dry_run:
            print(f"[DRY RUN] Would push to bot channel {bot_channel} via REST API.")
        elif requests is not None:
            try:
                bot_url = f"https://discord.com/api/v10/channels/{bot_channel}/messages"
                bot_headers = {"Authorization": f"Bot {bot_token}", "Content-Type": "application/json"}
                bot_resp = requests.post(bot_url, json=payload, headers=bot_headers, timeout=15)
                if bot_resp.status_code in (200, 201):
                    pass  # counted via success_count below
                else:
                    bot_ok = False
                    logger.error("Bot channel push failed [%d] %s", bot_resp.status_code, bot_resp.text[:200])
            except Exception as exc:
                bot_ok = False
                logger.error("Bot channel request error: %s", exc)
    else:
        bot_ok = True  # not configured is not a failure

    if success_count or (bot_wanted and bot_ok):
        printed = success_count
        extra = ""
        if bot_ok and bot_token and bot_channel:
            printed += 1
            extra = " + bot channel"
        print(f"[OK] Pushed {label} to {printed}/{len(targets)} webhook(s){extra}.")
    else:
        print(f"[WARN] {label} — none of {len(targets)} webhook(s) accepted the payload.")
    return success_count + (1 if bot_ok and bot_token and bot_channel else 0)


# ============================================================================
# SOCCER EMBED FORMATTER
# ============================================================================

def _soccer_teams(data: dict) -> Tuple[str, str]:
    """Pull home/away team names from soccer prediction data."""
    for home_key, away_key in (("home_team", "away_team"),
                               ("home", "away"),
                               ("home_player", "away_player")):
        home, away = data.get(home_key), data.get(away_key)
        if home and away:
            return str(home), str(away)
    raise ValueError(
        "Cannot find both team names in soccer prediction. "
        f"Keys present: {sorted(data)}")


def format_soccer_embed(data: dict) -> dict:
    """Format a soccer prediction into a rich Discord embed.

    Reads the actual keys produced by run_soccer_game() / SoccerPredictor
    rather than guessing from the tennis-shaped moneyline dict.
    """
    home, away = _soccer_teams(data)
    game = data.get("game", {}) or {}
    preds = data.get("predictions", {}) or {}
    goals = data.get("goals_analysis", {}) or {}
    corners = data.get("corners_analysis", {}) or {}
    league = data.get("league", "")

    home_prob = game.get("home_win_prob")
    draw_prob = game.get("draw_prob")
    away_prob = game.get("away_win_prob")
    proj_home = game.get("projected_home_goals")
    proj_away = game.get("projected_away_goals")
    proj_total = game.get("projected_total_goals")

    total_block = preds.get("total", {}) or {}
    side_block = preds.get("side", {}) or {}
    btts_block = preds.get("btts", {}) or {}
    total_rec = total_block.get("recommendation", "PASS")
    total_conf = total_block.get("confidence")
    total_edge = total_block.get("edge")
    side_rec = side_block.get("recommendation", "PASS")
    side_conf = side_block.get("confidence")
    side_edge = side_block.get("edge")
    btts_rec = btts_block.get("recommendation", "PASS")
    btts_prob = btts_block.get("probability") or data.get("btts_probability")

    over_15 = goals.get("over_15_prob")
    over_25 = goals.get("over_25_prob")
    over_35 = goals.get("over_35_prob")
    corner_proj = corners.get("projection")

    em = data.get("extra_markets", {}) or {}
    ttg = em.get("team_total_goals", {}) or {}
    fh = em.get("first_half_goals", {}) or {}
    tc = em.get("team_corners", {}) or {}

    conf_num = float(total_conf) if total_conf else 50.0
    if btts_rec.upper() == "BET" and conf_num >= 70:
        color = COLORS["strong_bet"]
    elif total_rec.upper() == "BET" and conf_num >= 65:
        color = COLORS["strong_bet"]
    elif btts_rec.upper() == "BET" or total_rec.upper() == "BET":
        color = COLORS["bet"]
    elif "pass" in str(total_rec).lower() and "pass" in str(side_rec).lower():
        color = COLORS["pass"]
    else:
        color = COLORS["neutral"]

    emoji = SPORT_EMOJIS.get("soccer", "")
    title_parts = [f"{emoji}SOCCER"]
    if league:
        title_parts.append(f" {league}")
    title_parts.append(f" | {home} vs {away}")
    title = "".join(title_parts)

    fields = []

    # Row 1: Score projection
    if proj_home is not None and proj_away is not None:
        score_line = f"**{home}** `{proj_home:.2f}`  \u2014  **{away}** `{proj_away:.2f}`"
        if proj_total is not None:
            score_line += f"\n**Total:** `{proj_total:.2f}`"
        fields.append({"name": "\U0001f4ca Projected Score", "value": score_line, "inline": False})

    # Row 2: 1X2 probabilities
    if any(p is not None for p in (home_prob, draw_prob, away_prob)):
        hp = f"{home_prob*100:.1f}%" if home_prob is not None else "\u2014"
        dp = f"{draw_prob*100:.1f}%" if draw_prob is not None else "\u2014"
        ap = f"{away_prob*100:.1f}%" if away_prob is not None else "\u2014"
        fields.append({
            "name": "\U0001f3af Match Outcome (1X2)",
            "value": f"{home} **{hp}**  |  Draw **{dp}**  |  {away} **{ap}**",
            "inline": False,
        })

    # Row 3: Best picks
    best_picks = []
    if total_rec.upper() in ("BET", "LEAN"):
        te = f" (edge {float(total_edge):+.2f})" if total_edge is not None else ""
        tc_ = f" {float(total_conf):.0f}% conf" if total_conf else ""
        best_picks.append(f"\U0001f4c8 **Total O/U**: {total_rec}{tc_}{te}")
    if btts_rec.upper() in ("BET", "LEAN"):
        bp = f" ({float(btts_prob)*100:.1f}%)" if btts_prob else ""
        bc_ = f" {float(btts_block.get('confidence', 0)):.0f}% conf" if btts_block.get("confidence") else ""
        best_picks.append(f"\U0001f4aa **BTTS**: {btts_rec}{bp}{bc_}")
    if side_rec.upper() in ("BET", "LEAN"):
        se = f" (edge {float(side_edge):+.2f})" if side_edge is not None else ""
        sc_ = f" {float(side_conf):.0f}% conf" if side_conf else ""
        best_picks.append(f"\U0001f3e0 **Side**: {side_rec}{se}{sc_}")
    if best_picks:
        fields.append({"name": "\U0001f514 Active Bets", "value": "\n".join(best_picks), "inline": False})

    # Row 4: Goal probabilities
    goal_vals = []
    if over_15 is not None:
        goal_vals.append(f"O1.5 **{over_15*100:.1f}%**")
    if over_25 is not None:
        goal_vals.append(f"O2.5 **{over_25*100:.1f}%**")
    if over_35 is not None:
        goal_vals.append(f"O3.5 **{over_35*100:.1f}%**")
    if goal_vals:
        fields.append({"name": "\u26bd Goal Probabilities",
                       "value": " \u00b7 ".join(goal_vals), "inline": True})

    # Row 5: Corners
    corner_vals = []
    if corner_proj is not None:
        corner_vals.append(f"Proj **{corner_proj:.1f}**")
    for key, label in [("over_85_prob", "O8.5"), ("over_95_prob", "O9.5"),
                       ("over_105_prob", "O10.5")]:
        v = corners.get(key)
        if v is not None:
            corner_vals.append(f"{label} **{v*100:.1f}%**")
    if corner_vals:
        fields.append({"name": "\U0001f3f0 Corners",
                       "value": " \u00b7 ".join(corner_vals), "inline": True})

    # Row 6: BTTS + FH Goals
    extra_vals = []
    if btts_prob is not None:
        extra_vals.append(f"BTTS Yes **{btts_prob*100:.1f}%**")
    fh_proj = fh.get("projection")
    if fh_proj is not None:
        extra_vals.append(f"FH Goals **{fh_proj}**")
    if extra_vals:
        fields.append({"name": "\U0001f4ca Extra Markets",
                       "value": " \u00b7 ".join(extra_vals), "inline": True})

    # Row 7: Team corners split
    if tc and "_warning" not in tc:
        hc = tc.get("home", {}).get("projection")
        ac = tc.get("away", {}).get("projection")
        if hc is not None and ac is not None:
            fields.append({
                "name": "\U0001f3f0 Team Corners",
                "value": f"{home} **{hc}**  \u2014  {away} **{ac}**",
                "inline": False,
            })

    # Row 8: Team totals
    if ttg:
        home_lines = []
        for k in ("over_05", "over_15", "over_25"):
            v = ttg.get("home", {}).get(k)
            if v is not None:
                lbl = k.replace("over_", "O")
                if len(lbl) == 2:
                    lbl = lbl[0] + "." + lbl[1]
                home_lines.append(f"{lbl} {v*100:.0f}%")
        away_lines = []
        for k in ("over_05", "over_15", "over_25"):
            v = ttg.get("away", {}).get(k)
            if v is not None:
                lbl = k.replace("over_", "O")
                if len(lbl) == 2:
                    lbl = lbl[0] + "." + lbl[1]
                away_lines.append(f"{lbl} {v*100:.0f}%")
        if home_lines or away_lines:
            ttg_text = f"{home}: {' \u00b7 '.join(home_lines)}\n{away}: {' \u00b7 '.join(away_lines)}"
            fields.append({"name": "\U0001f3e0 Team Totals",
                           "value": ttg_text, "inline": False})

    return {"title": title, "color": color, "fields": fields,
            "footer": {"text": "MultiSportPredict Sports Engine | Real-Time Model Feeds"}}


# ============================================================================
# SPORT-TO-FORMATTER ROUTER
# ============================================================================

def format_prediction_embed(sport, prediction_data):
    """Build the embed for any sport. One renderer, one shape.

    This used to route to a per-sport formatter, each guessing at the keys its
    predictor returns, and each wrong in its own way: baseball rendered
    50.0%/50.0% because it read "moneyline" instead of "moneyline_and_side";
    tennis published "Player 1 vs Player 2" because it read "home_player";
    props were never rendered at all. Every fix added a fifth special case.

    embed_builder.py holds the extraction per sport and one renderer for all of
    them. A value it cannot find is OMITTED rather than defaulted, and a
    prediction with nothing readable raises instead of publishing an empty
    card. The old formatters are kept below for anything still calling them
    directly, but nothing routes through them any more.
    """
    from embed_builder import build_embed
    return build_embed(sport, prediction_data)


def push_prediction_to_all(sport, prediction_data, dry_run=False, extra_webhooks=None):
    """Format and broadcast one prediction. Returns the number of destinations.

    A prediction that cannot be rendered is NOT pushed. Publishing a card with
    a title and blank fields is worse than an error, because it reads as a pick
    -- which is exactly what happened for weeks.
    """
    from embed_builder import UnrenderablePrediction
    try:
        embed = format_prediction_embed(sport, prediction_data)
    except UnrenderablePrediction as exc:
        print(f"[REFUSED] Nothing was pushed: {exc}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[REFUSED] Could not build the embed ({type(exc).__name__}: {exc}). "
              f"Nothing was pushed.")
        return 0
    label = f"{sport} {prediction_data.get('match') or ''}".strip()
    return _broadcast_embed(embed, extra_webhooks=extra_webhooks,
                            dry_run=dry_run, label=label or sport)


def _tennis_players(data: dict) -> Tuple[str, str]:
    """Pull the two player names out of a prediction result.

    This used to be:

        home = data.get("home_player") or data.get("home", "Player 1")

    predict_tennis_match() returns neither of those keys. It puts the names in
    moneyline.home / moneyline.away and in a "match" string. So every lookup
    missed, every embed fell through to the default, and subscribers were sent
    "US Open | Player 1 vs Player 2" with a real edge and a real confidence
    score attached -- the numbers were right, the players were placeholders,
    and nothing anywhere reported a problem.

    A default that stands in for a failed lookup is the bug, not the fix. The
    real keys are checked first, and a miss now raises instead of inventing two
    people.
    """
    moneyline = data.get("moneyline") or {}
    for source in (moneyline, data):
        for home_key, away_key in (("home", "away"),
                                   ("home_player", "away_player"),
                                   ("home_team", "away_team"),
                                   ("player1", "player2"),
                                   ("p1", "p2")):
            home, away = source.get(home_key), source.get(away_key)
            if home and away:
                return str(home), str(away)

    # "Lehecka J. vs Carreno Busta P." -- the shape predict_tennis_match builds.
    match = str(data.get("match") or "")
    for separator in (" vs ", " vs. ", " v ", " - "):
        if separator in match:
            home, away = match.split(separator, 1)
            return home.strip(), away.strip()

    raise ValueError(
        "Cannot find both player names in this prediction. Looked at "
        "moneyline.home/away, home_player/away_player, player1/player2, p1/p2 "
        f"and match={match!r}. Refusing to publish a pick with placeholder "
        f"names. Keys present: {sorted(data)}")


def format_tennis_embed(data: dict) -> dict:
    """
    Formats tennis prediction data into a clean, scannable Discord Embed payload.

    Accepts the enriched model result dict (the same dict that
    ``push_recommendation_to_discord`` receives) and maps the raw keys to
    subscriber-friendly fields with dynamic colour coding and signal badges.

    Args:
        data: Enriched result dict with keys:
            - home_player / away_player (or home / away)
            - tournament / tournament_name
            - surface
            - moneyline: dict with home_win_prob, away_win_prob, confidence,
                         recommendation, edge_pct
            - sets: dict with recommendation_sets_ou, recommendation_spread
            - total_games: dict with line, recommendation

    Returns:
        A Discord embed dict ready to be placed inside ``{"embeds": [ ... ]}``.
    """
    home, away = _tennis_players(data)
    ml = data.get("moneyline", {})
    home_prob = ml.get("home_win_prob", 0.5)
    away_prob = ml.get("away_win_prob", round(1.0 - home_prob, 4))
    edge_pct = ml.get("edge_pct", 0.0)
    conf = data.get("confidence_score") or ml.get("confidence", 50)
    rec = ml.get("recommendation", "PASS")
    surface = (data.get("surface") or "Hard").title()
    tournament = data.get("tournament_name") or data.get("tournament") or "ATP Tour"
    sets = data.get("sets", {})
    total_games = data.get("total_games", {})
    m_home = data.get("market_home_odds")
    m_away = data.get("market_away_odds")
    target_odds = f"{m_home}/{m_away}" if (m_home and m_away) else "N/A"

    if edge_pct >= 5.0 and conf >= 65:
        color = 3066993
        signal_badge = "\U0001f7e2 STRONG PLAY"
    elif edge_pct > 0:
        color = 3447003
        signal_badge = "\U0001f535 VALUE PLAY"
    elif conf >= 70:
        color = 3447003
        signal_badge = "\U0001f535 LEAN (Model Conviction)"
    else:
        color = 9807270
        signal_badge = "\u26aa NEUTRAL / PASS"

    fav_star_home = " \u2b50" if home_prob > away_prob else ""
    fav_star_away = " \u2b50" if away_prob > home_prob else ""

    set_prop = sets.get("recommendation_sets_ou", "Over 3.5 Sets")
    spread_prop = sets.get("recommendation_spread", "+1.5 Sets")
    tg_rec = total_games.get("recommendation", "")
    tg_line = total_games.get("line", "40.5")
    total_games_str = f"{tg_rec} ({tg_line})" if tg_rec else f"Over/Under {tg_line}"

    set_dist = data.get("set_distribution", {})
    elo_ratings = data.get("elo_ratings", {})
    home_elo = elo_ratings.get(home)
    away_elo = elo_ratings.get(away)

    if set_dist:
        best_score = max(set_dist, key=set_dist.get)
        best_pct = set_dist[best_score]
        parts = best_score.split("-")
        if home_prob > away_prob:
            readable_score = f"{home} {parts[0]}-{parts[1]}"
        else:
            readable_score = f"{away} {parts[1]}-{parts[0]}"
        most_likely = f"Most likely score: **{readable_score}** ({best_pct:.0%})"
    else:
        most_likely = ""

    fav_name = ml.get("lean", "coin_flip")
    if fav_name == "coin_flip":
        tactical_note = "Model projects a coin-flip matchup \u2014 expect tight exchanges."
    elif edge_pct >= 5.0:
        tactical_note = (
            f"Model sees a clear edge for **{fav_name}** on {surface} court. "
            f"{most_likely}"
        )
    else:
        tactical_note = (
            f"Model leans **{fav_name}** in a competitive match on {surface}. "
            f"{most_likely}"
        )

    if home_elo and away_elo:
        tactical_note += (
            f" Elo spread: **{abs(home_elo - away_elo):.0f}** pts "
            f"({home}: {home_elo:.0f} vs {away}: {away_elo:.0f})."
        )

    fields = [
        {"name": f"\U0001f464 {home}",
         "value": f"**{home_prob:.1%}**{fav_star_home}", "inline": True},
        {"name": f"\U0001f464 {away}",
         "value": f"**{away_prob:.1%}**{fav_star_away}", "inline": True},
        {"name": "\U0001f3af Best Selection",
         "value": f"**{rec}**", "inline": True},
        {"name": "\U0001f4ca Model Edge",
         "value": f"`{edge_pct:+.1f}%`", "inline": True},
        {"name": "\u26a1 Confidence",
         "value": f"`{conf:.0f}%`", "inline": True},
        {"name": "\U0001f4b0 Target Odds",
         "value": f"`{target_odds}`", "inline": True},
        {"name": "\U0001f4e6 Set & Game Derivatives",
         "value": (
             f"\u2022 **Sets:** `{set_prop}`\n"
             f"\u2022 **Total Games:** `{total_games_str}`\n"
             f"\u2022 **Spread:** `{spread_prop}`"
         ), "inline": False},
        {"name": "\U0001f4dd Matchup Context",
         "value": tactical_note, "inline": False},
    ]

    embed = {
        "title": f"\U0001f3be {tournament} | {home} vs {away}",
        "description": f"**Surface:** `{surface}` | **Signal:** `{signal_badge}`",
        "color": color,
        "fields": fields,
        "footer": {"text": "MultiSportPredict Tennis Engine | Real-Time Model Feeds"},
    }

    # Append any caller-provided value_plays below the core fields
    value_plays = data.get("value_plays")
    if value_plays:
        extra_fields = _build_value_play_fields(value_plays)
        embed["fields"].extend(extra_fields)

    return embed


def _build_value_play_fields(value_plays: dict) -> list:
    """Build extra Discord embed fields from a value_plays dict."""
    fields = []

    plays = value_plays.get("plays", {})
    if plays:
        lines = [f"`{name}`  {odds}" for name, odds in plays.items()]
        fields.append({
            "name": "\U0001f3b2 Original Value Plays",
            "value": "\n".join(lines),
            "inline": False,
        })

    original_lean = value_plays.get("original_lean")
    if original_lean:
        fields.append({
            "name": "\U0001f4a1 Original Lean",
            "value": original_lean,
            "inline": False,
        })

    deep_dive = value_plays.get("deep_dive", {})
    if deep_dive:
        lines = []
        if deep_dive.get("Target"):
            lines.append(f"**Target:** {deep_dive['Target']}")
        if deep_dive.get("Angle"):
            lines.append(f"**Angle:** {deep_dive['Angle']}")
        if deep_dive.get("Rationale"):
            lines.append(f"**Rationale:** {deep_dive['Rationale']}")
        if lines:
            fields.append({
                "name": "\U0001f50d Deep-Dive Analysis",
                "value": "\n".join(lines),
                "inline": False,
            })

    model_view = value_plays.get("model_view", {})
    if model_view:
        fave = model_view.get("favorite", "coin_flip")
        fave_prob = model_view.get("favorite_win_prob", 0.5)
        fave_text = "coin-flip" if fave == "coin_flip" else f"{fave}"
        lines = [f"**Model favorite:** {fave_text}  {fave_prob:.1%}"]
        if model_view.get("notes"):
            lines.append(f"**Note:** {model_view['notes']}")
        fields.append({
            "name": "\U0001f916 Model View",
            "value": "\n".join(lines),
            "inline": False,
        })

    return fields


def push_recommendation_to_discord(
    prediction_result: dict,
    dry_run: bool = False,
) -> None:
    """Legacy wrapper — delegates to push_prediction_to_all("tennis", ...)."""
    home, away = _tennis_players(prediction_result)
    print(f"[push_recommendation_to_discord] Delegating {home} vs {away} to push_prediction_to_all...")
    push_prediction_to_all("tennis", prediction_result, dry_run=dry_run)

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
                "title": " Webhook Test",
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
            logger.info(" Webhook test successful!")
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
        print(" Your Discord webhook is properly configured!")

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
        print(" Discord webhook is not configured. Check your .env file.")





