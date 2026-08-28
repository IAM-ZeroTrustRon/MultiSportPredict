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
        content_id = _content_hash(payload)
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

    # Real data structure: game -> confidence -> total/side
    ml  = prediction.get("moneyline_and_side", {})
    game = prediction.get("game", ml)
    proj = prediction.get("game_projection", {})
    props = prediction.get("props", {})

    home_prob = game.get("home_win_probability", ml.get("home_win_probability", 0))
    away_prob = game.get("away_win_probability", ml.get("away_win_probability", 0))
    proj_total = game.get("projected_total_runs", proj.get("total", "N/A"))

    summary = game

    # 1. Format Confidence & Recommendations with Emojis
    def format_rec(recommendation, conf):
        rec_str = str(recommendation).strip().upper()
        emoji = "🟢" if rec_str == "BET" else ("🔴" if rec_str == "PASS" else "🟡")
        return f"{emoji} **{rec_str}**\n*(Conf: {conf})*"

    # 2. Extract Total and Run Line Data
    confidence_sources = (game.get("confidence"), ml.get("confidence"))
    conf_block = next(
        (block for block in confidence_sources if isinstance(block, dict)),
        {},
    )
    
    total_block = conf_block.get("total", {})
    rec = total_block.get("recommendation", summary.get("recommendation", "PASS"))
    conf_score = total_block.get("score", summary.get("confidence", "N/A"))
    total_display = format_rec(rec, conf_score)

    rl_block = conf_block.get("run_line", conf_block.get("side", {}))
    rl_rec = rl_block.get("recommendation", "PASS")
    rl_conf = rl_block.get("score", "N/A")
    run_line_display = format_rec(rl_rec, rl_conf)

    # 3. Clean up NRFI Formatting
    nrfi_data = props.get("nrfi", {})
    nrfi_prob = nrfi_data.get("probability", nrfi_data.get("prob", None))
    nrfi_rec = nrfi_data.get("recommendation", nrfi_data.get("lean", "N/A"))
    if nrfi_prob is not None:
        nrfi_display = f"**Prob:** {float(nrfi_prob)*100:.1f}%\n**Rec:** {nrfi_rec}"
    else:
        nrfi_display = "N/A"

    # 4. Clean up Strikeout Props Formatting
    ks_data = props.get("strikeouts", {})
    home_ks = ks_data.get("home_team_projected_ks", "N/A")
    away_ks = ks_data.get("away_team_projected_ks", "N/A")
    ks_lean = ks_data.get("lean", "N/A")
    ks_display = f"**{home}:** {home_ks} Ks\n**{away}:** {away_ks} Ks\n**Lean:** {ks_lean}"

    # 5. Build the Final Beautiful Embed
    fields = [
        {"name": "💰 MONEYLINE", "value": f"**{home}:** {float(home_prob)*100:.1f}%\n**{away}:** {float(away_prob)*100:.1f}%\n{format_rec(conf_block.get('side', {}).get('recommendation', 'N/A'), conf_block.get('side', {}).get('score', 'N/A'))}", "inline": True},
        {"name": "📈 PROJ TOTAL", "value": f"**{proj_total}** runs", "inline": True},
        {"name": "🎯 TOTAL", "value": total_display, "inline": True},
        {"name": "🏃 RUN LINE", "value": run_line_display, "inline": True},
        {"name": "🔥 NRFI / YRFI", "value": nrfi_display, "inline": True},
        {"name": "⚾ STRIKEOUT PROPS", "value": ks_display, "inline": False}
    ]

    color_map = {"STRONG BET": 3066993, "BET": 10181046, "PASS": 9807270}
    color = color_map.get(str(rec).upper(), 9807270)

    embed = {
        "title": f"[{sport.upper()}] {home.upper()} vs {away.upper()}",
        "description": f"{sport.upper()} Prediction Report",
        "color": color,
        "fields": fields,
        "footer": {"text": "MultiSportPredict | Baseball"},
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
    home = prediction_data.get("home_team", "Home")
    away = prediction_data.get("away_team", "Away")
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
    home_player = home or prediction.get("home_player") or prediction.get("home", "Player 1")
    away_player = away or prediction.get("away_player") or prediction.get("away", "Player 2")

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
                f"`{name}`  {odds}" for name, odds in plays.items()
            ]
            fields.append({
                "name": " Original Value Plays",
                "value": "\n".join(lines),
                "inline": False,
            })
        original_lean = value_plays.get("original_lean")
        if original_lean:
            fields.append({
                "name": " Original Lean",
                "value": original_lean,
                "inline": False,
            })

        # Deep-dive plays
        deep_dive = value_plays.get("deep_dive", {})
        if deep_dive:
            lines = []
            if deep_dive.get("Target"):
                lines.append(f" **Target:** {deep_dive['Target']}")
            if deep_dive.get("Angle"):
                lines.append(f" **Angle:** {deep_dive['Angle']}")
            if deep_dive.get("Rationale"):
                lines.append(f" **Rationale:** {deep_dive['Rationale']}")
            fields.append({
                "name": " Deep-Dive Analysis",
                "value": "\n".join(lines),
                "inline": False,
            })

        # Model view vs market
        model_view = value_plays.get("model_view", {})
        if model_view:
            fave = model_view.get("favorite", "coin_flip")
            fave_prob = model_view.get("favorite_win_prob", 0.5)
            fave_text = "coin-flip" if fave == "coin_flip" else f"{fave}"
            lines = [f" **Model favorite:** {fave_text}  {fave_prob:.1%}"]
            if model_view.get("notes"):
                lines.append(f" **Note:** {model_view['notes']}")
            fields.append({
                "name": " Model View",
                "value": "\n".join(lines),
                "inline": False,
            })

    embed = {
        "title": f" Tennis Value Pick: {home_player} vs {away_player}",
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





